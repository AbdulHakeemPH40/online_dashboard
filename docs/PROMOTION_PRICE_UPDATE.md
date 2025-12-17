# Promotion Price Update - Requirements Document

## Overview
A page to update promotional prices for items across Pasons and Talabat platforms with scheduled start/end dates.

---

## Input Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Item Code | Text | Yes | Product item code |
| Units | Text | Yes | Unit of measure |
| Promo Price | Decimal | Yes | Base promotional price |
| Platform | Select | Yes | Pasons / Talabat / Both |
| Start Date | Date | Yes | Promotion start date |
| End Date | Date | Yes | Promotion end date |

---

## Platform-Specific Price Calculation

### Pasons Platform
| Wrap | Formula | Description |
|------|---------|-------------|
| 9900 | `round(promo_price / wdf, 2)` | Convert to selling units |
| 1000 | `promo_price` | Direct price (no conversion) |

### Talabat Platform
| Wrap | Formula | Description |
|------|---------|-------------|
| 9900 | `(promo_price / wdf) + talabat_margin` | Convert + add margin |
| 1000 | `promo_price + talabat_margin` | Direct + margin |

---

## Auto-Detect Validation Rules

### Rule 1: Minimum Cost + 20% Margin (Talabat Only)
```
IF converted_promo < converted_cost * 1.20:
    converted_promo = converted_cost * 1.20  # Auto-adjust
ELSE:
    # No change needed - margin is OK
```
- **Trigger:** Only when margin < 20%
- **Action:** Auto-adjust promo to `cost + 20%`
- **If margin >= 20%:** Keep original promo price (no change)

### Rule 2: Minimum 2 AED Difference (Selling vs Promo)
```
difference = selling_price - converted_promo

IF difference < 2:
    selling_price = converted_promo + 2  # Auto-adjust
ELSE:
    # No change needed - difference is OK
```
- **Trigger:** Only when difference < 2 AED (including negative)
- **Action:** Auto-adjust selling price to `promo + 2`
- **If difference >= 2:** Keep original selling price (no change)

### Combined Auto-Detect Flow
```python
def calculate_promo(promo_price, platform, wrap, wdf, cost, selling_price, margin_pct):
    # Step 1: Calculate converted_promo based on platform/wrap
    if wrap == 9900:
        converted_promo = promo_price / wdf
    else:  # wrap == 1000
        converted_promo = promo_price
    
    # Add Talabat margin if applicable
    if platform == 'talabat':
        converted_promo = converted_promo * (1 + margin_pct / 100)
    
    # Step 2: Auto-detect cost margin (Talabat only)
    adjusted_promo = converted_promo
    promo_adjusted = False
    if platform == 'talabat':
        min_promo = cost * 1.20  # Cost + 20%
        if converted_promo < min_promo:
            adjusted_promo = min_promo
            promo_adjusted = True
    
    # Step 3: Auto-detect selling price difference
    adjusted_selling = selling_price
    selling_adjusted = False
    difference = selling_price - adjusted_promo
    if difference < 2:
        adjusted_selling = adjusted_promo + 2
        selling_adjusted = True
    
    return {
        'converted_promo': adjusted_promo,
        'promo_adjusted': promo_adjusted,
        'selling_price': adjusted_selling,
        'selling_adjusted': selling_adjusted,
        'margin_pct': ((adjusted_promo - cost) / cost) * 100,
        'difference': adjusted_selling - adjusted_promo
    }
```

---

## Fields Updated in Database

### ItemOutlet Model
| Field | Description |
|-------|-------------|
| `promo_price` | Input promo price (stored as-is) |
| `converted_promo` | Calculated based on wrap/platform |
| `selling_price` | Auto-adjusted if needed (temporary) |
| `original_selling_price` | Backup of original price (for restoration) |
| `promo_start_date` | Promotion start date |
| `promo_end_date` | Promotion end date |
| `is_on_promotion` | Boolean flag |

---

## Workflow

### Creating a Promotion
1. User enters Item Code + Units
2. System fetches item details and current prices
3. User enters Promo Price, Platform, Start Date, End Date
4. System calculates `converted_promo` based on wrap/platform
5. System validates:
   - Talabat: Check cost + 20% margin
   - Both: Check 2 AED difference with selling price
6. System shows preview with any auto-adjustments
7. User confirms → System saves:
   - Backs up `original_selling_price`
   - Updates `promo_price`, `converted_promo`
   - Updates `selling_price` if needed
   - Sets `promo_start_date`, `promo_end_date`
   - Sets `is_on_promotion = True`

### Auto-Activation (Scheduled Task)
- Daily job checks `promo_start_date`
- If today >= start_date and today <= end_date:
  - Activate promotion prices
  - Set `is_on_promotion = True`

### Auto-Deactivation (Scheduled Task)
- Daily job checks `promo_end_date`
- If today > end_date:
  - Restore `selling_price` from `original_selling_price`
  - Clear promo fields
  - Set `is_on_promotion = False`

---

## UI Design

### Page: `/promotion-update/`

#### Section 1: Item Search
```
[Item Code: ________] [Units: ________] [Search]
```

#### Section 2: Item Details (after search)
```
Item: COCA COLA 330ML
Current Selling Price: 5.50 AED
Current Cost Price: 3.20 AED
Wrap: 9900 | WDF: 24
```

#### Section 3: Promotion Setup
```
Platform: [Pasons ▼] [Talabat ▼] [Both ▼]
Promo Price: [________] AED
Start Date: [________] 
End Date: [________]

[Calculate Preview]
```

#### Section 4: Preview & Validation
```
╔════════════════════════════════════════════════════════╗
║ PREVIEW                                                ║
╠════════════════════════════════════════════════════════╣
║ Platform: Talabat                                      ║
║ Original Selling: 5.50 AED                             ║
║ Promo Price Input: 4.00 AED                            ║
║ Converted Promo: 4.25 AED (after margin)               ║
║                                                        ║
║ ⚠️ Warning: Selling price adjusted to 6.25 AED         ║
║    (Minimum 2 AED difference required)                 ║
║                                                        ║
║ ✅ Cost margin OK (32% > 20%)                          ║
╚════════════════════════════════════════════════════════╝

[Confirm & Save] [Cancel]
```

---

## Database Migration Required

Add to `ItemOutlet` model:
```python
promo_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
converted_promo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
original_selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
promo_start_date = models.DateField(null=True, blank=True)
promo_end_date = models.DateField(null=True, blank=True)
is_on_promotion = models.BooleanField(default=False)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/promotion/search/?item_code=X&units=Y` | Get item details |
| POST | `/api/promotion/calculate/` | Calculate preview |
| POST | `/api/promotion/save/` | Save promotion |
| GET | `/api/promotion/active/` | List active promotions |
| DELETE | `/api/promotion/{id}/cancel/` | Cancel promotion |

---

## Sidebar Menu
Add under "Price Management":
- 📢 Promotion Update

---

## Questions for Confirmation
1. Should promotions apply to all outlets or specific outlets?
2. Should we allow bulk promotion upload via CSV?
3. Should there be an approval workflow before activation?
