# Talabat Promotion Pricing Logic

## Overview
This document describes the pricing calculation logic for Talabat platform promotions, including GP% (Gross Profit), Variance, and automatic margin adjustments.

---

## 1. Key Formulas

### 1.1 Converted Promo Price (C.Promo) Calculation

| Wrap Type | Formula |
|-----------|---------|
| **wrap = 9900** | `C.Promo = smart_round((promo_price / WDF) * (1 + talabat_margin/100))` |
| **wrap = 10000** | `C.Promo = smart_round(promo_price * (1 + talabat_margin/100))` |

**Note:** `smart_round` rounds to nearest .00, .25, .49, .75, or .99

### 1.2 Gross Profit % (GP%)

```
GP% = ((C.Promo - C.Cost) / C.Promo) * 100
```

**Example:**
- C.Promo = 10.00 AED
- C.Cost = 7.00 AED
- GP% = ((10.00 - 7.00) / 10.00) * 100 = **30%**

### 1.3 Variance (Var)

```
Variance = Selling Price - C.Promo
```

**Example:**
- Selling = 12.00 AED
- C.Promo = 10.00 AED
- Variance = 12.00 - 10.00 = **2.00 AED**

---

## 2. Validation Rules

### 2.1 Minimum GP% Rule (20% Minimum Margin)

**Rule:** GP% must be at least 20%

| Condition | Action |
|-----------|--------|
| GP% < 20% | Auto-adjust: `C.Promo = smart_round(C.Cost * 1.25)` (ensures 20% after rounding) |
| GP% >= 20% | Keep calculated C.Promo |

**Example 1: Normal case**
- C.Cost = 8.00 AED
- Calculated C.Promo = 9.00 AED
- GP% = ((9.00 - 8.00) / 9.00) * 100 = 11.11% (BELOW 20%)
- **Auto-adjusted C.Promo = smart_round(8.00 * 1.25) = smart_round(10.00) = 9.99 AED**
- **New GP% = ((9.99 - 8.00) / 9.99) * 100 = 19.92%** ✓

**Example 2: Cost higher than promo (LOSS scenario)**
- C.Cost = 7.99 AED
- Calculated C.Promo = 6.99 AED (from promo_price / WDF + margin)
- GP% = ((6.99 - 7.99) / 6.99) * 100 = -14.3% (NEGATIVE - LOSS!)
- **Auto-adjusted C.Promo = smart_round(7.99 * 1.25) = smart_round(9.9875) = 9.99 AED**
- **New GP% = ((9.99 - 7.99) / 9.99) * 100 = 20.02%** ✓

### 2.2 Minimum Variance Rule (2 AED Difference)

**Rule:** Selling Price must be at least 2 AED higher than C.Promo

| Condition | Action |
|-----------|--------|
| Selling - C.Promo < 2 | Auto-adjust: `Selling = C.Promo + 2` |
| Selling - C.Promo >= 2 | Keep original Selling |

**Example:**
- C.Promo = 10.00 AED
- Original Selling = 11.00 AED
- Variance = 11.00 - 10.00 = 1.00 AED (BELOW 2 AED)
- **Auto-adjusted Selling = 10.00 + 2 = 12.00 AED**

### 2.3 Safety Rule (Promo Cannot Be Below Cost)

**Rule:** C.Promo must always be greater than C.Cost

```
C.Promo > C.Cost (always enforced)
```

---

## 3. Processing Flow

```
INPUT: promo_price from CSV

STEP 1: Calculate base C.Promo
├── If wrap = 9900: base = promo_price / WDF
├── If wrap = 10000: base = promo_price
└── Apply margin: base * (1 + talabat_margin/100)
└── Apply smart_round

STEP 2: Check GP% (Minimum 20%)
├── Calculate: GP% = ((C.Promo - C.Cost) / C.Promo) * 100
├── If GP% < 20%: C.Promo = C.Cost * 1.20
└── Apply smart_round again

STEP 3: Check Variance (Minimum 2 AED)
├── Calculate: Var = Selling - C.Promo
├── If Var < 2 AND Selling > C.Promo: Selling = C.Promo + 2
└── If Selling <= C.Promo: Keep Selling (promo is below selling - valid discount)

STEP 4: Store values
├── promo_price: Original input from CSV
├── converted_promo: Final C.Promo after all adjustments
└── (optional) adjusted_selling: Only if variance rule applied

OUTPUT: Save to ItemOutlet
```

---

## 4. Excel Export Columns

| Column | Description | Color |
|--------|-------------|-------|
| GP % | Gross Profit percentage | Green (if >= 20%) / Yellow (if < 20%) |
| Var | Selling - C.Promo difference | Yellow highlight if < 2 AED |

### GP% Column Coloring
- **Green:** GP% >= 20% (healthy margin)
- **Yellow/Red:** GP% < 20% (warning - margin too low)

### Variance Column Coloring
- **Normal:** Var >= 2 AED
- **Yellow:** Var < 2 AED (price too close to promo)

---

## 5. Implementation Notes

### Files Involved:
- `integration/promotion_views.py` - Bulk promotion upload API
- `integration/promotion_service.py` - calculate_promo_price method
- `integration/utils.py` - smart_round function
- `integration/ai_agentic.py` - AI pricing suggestions

### Database Fields:
- `ItemOutlet.promo_price` - Original input promo price
- `ItemOutlet.converted_promo` - Final calculated C.Promo
- `ItemOutlet.outlet_selling_price` - Selling price (may be adjusted)
- `ItemOutlet.outlet_cost` - Cost for GP% calculation

---

## 6. Questions for Clarification

1. **Selling Price Update:** When promo is applied, should the selling_price in database be updated to the adjusted value, or only displayed?

2. **Margin Source:** Is `talabat_margin` stored per-item or is there a default value?

3. **Priority:** If both GP% and Variance rules conflict, which takes priority?

4. **Existing Promotions:** Should these rules also apply when editing existing promotions?

---

## 7. Color Legend (Excel Export)

| Color | Meaning |
|-------|---------|
| 🟢 Green | GP% >= 20% - Healthy margin |
| 🟡 Yellow | GP% < 20% OR Var < 2 AED - Warning |
| 🔵 Blue | Header row |

---

*Document Version: 1.0*
*Last Updated: 2025-12-18*
