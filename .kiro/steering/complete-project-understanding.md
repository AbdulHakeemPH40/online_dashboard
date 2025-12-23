# Complete Pasons ERP Project Understanding

## Project Architecture Overview

### Core System Components
1. **ERP Integration System** - Main Django application
2. **Platform Management** - Pasons vs Talabat isolation
3. **Pricing Engine** - Smart rounding and margin calculations
4. **Bulk Operations** - CSV upload processing
5. **Promotion System** - Temporary pricing overrides
6. **Lock System** - CLS (Central) and BLS (Branch) locks

## Data Model Structure

### Core Models
- **Item** - Master product data (shared across outlets)
- **ItemOutlet** - Outlet-specific product data (pricing, stock)
- **Outlet** - Store/branch information with platform assignment
- **UploadHistory** - Audit trail for bulk operations

### Key Relationships
- Item (1) → ItemOutlet (Many) - One product, multiple outlet instances
- Outlet (1) → ItemOutlet (Many) - One outlet, many products
- Platform isolation enforced at Outlet level

## URL Structure & Functions

### Main Operations
1. **`/integration/product-update/`** → `product_update()` function
   - Updates MRP, Cost, Stock via CSV
   - Recalculates selling prices automatically
   - Platform-specific updates only

2. **`/integration/bulk-promotion-update/`** → `bulk_promotion_update()` function
   - Handles promotion pricing during specific periods
   - Temporary price overrides
   - Does NOT affect regular selling prices

3. **`/integration/promotion-integration/`** → `promotion_update()` function
   - Individual promotion management
   - Search and apply promotions
   - Integration with promotion system

### Bulk Operations Logic
- **product_update()**: Updates base prices (MRP → selling_price calculation)
- **bulk_promotion_update()**: Applies temporary promotional pricing
- **promotion_integration()**: Manual promotion management

## Pricing Flow During Updates

### When MRP is Updated (product-update):
```
CSV MRP → Validate → Calculate Base Price → Apply Margin → Smart Rounding → Update outlet_selling_price
```

### During Promotion Period:
```
Regular Price (outlet_selling_price) ← PRESERVED
Promotion Price (separate table) ← ACTIVE during promotion
```

### Key Behavior:
- **Regular updates**: Always recalculate selling_price from MRP
- **Promotion periods**: Promotion price overrides regular price
- **After promotion**: System reverts to regular selling_price

## Platform Isolation Logic

### Pasons Platform:
- No margins applied
- MRP = Selling Price (exact)
- No smart rounding for pricing

### Talabat Platform:
- Margins applied (17% wrap, 15% regular, or custom)
- Smart rounding to .25, .49, .75, .99
- Zero margin special handling (exact prices)

## Lock System Integration

### CLS Locks (Central/Item Level):
- `item.price_locked` - Prevents MRP updates
- `item.status_locked` - Prevents status changes

### BLS Locks (Branch/Outlet Level):
- `item_outlet.price_locked` - Prevents outlet price updates
- `item_outlet.status_locked` - Prevents outlet status changes

### Lock Behavior in Bulk Updates:
- Price locked items: Skip MRP/selling_price updates
- Status locked items: Keep `is_active_in_outlet = False`
- Stock updates: Always allowed (quantity can change)

## Critical Implementation Details

### Selling Price Overwrite Logic:
1. **MRP Update** → **YES, selling_price is recalculated and overwritten**
2. **Stock Update** → **NO, selling_price remains unchanged**
3. **Cost Update** → **NO, selling_price remains unchanged**
4. **Promotion Active** → **Promotion price shown, regular price preserved**

### Zero Margin Handling:
- 0% margin items preserve exact MRP prices
- No psychological pricing (.00 → .99 conversion)
- Standard 2-decimal rounding only

### Wrap Item Calculations:
- wrap=9900: Base price = MRP ÷ weight_division_factor
- wrap=10000: Base price = MRP (as-is)
- Then apply platform-specific margin and rounding

## File Locations & Responsibilities

### Core Logic Files:
- `integration/views.py` - All bulk operation functions
- `integration/promotion_views.py` - Promotion-specific functions
- `integration/utils.py` - PricingCalculator and helper functions
- `integration/models.py` - Data models and business logic properties

### Key Functions:
- `product_update()` - Main bulk MRP/stock update
- `bulk_promotion_update()` - Promotion bulk operations
- `promotion_update()` - Individual promotion management
- `calculate_item_selling_price()` - Core pricing calculation
- `PricingCalculator.calculate_talabat_price()` - Talabat pricing logic

## Business Rules Summary

### Price Calculation Priority:
1. **Promotion active** → Use promotion price
2. **Regular operation** → Use calculated selling_price (MRP + margin + rounding)
3. **Zero margin** → Use exact MRP (no rounding)
4. **Locked items** → Skip updates, preserve existing prices

### Update Behavior:
- **MRP changes** → Selling price automatically recalculated
- **Promotion periods** → Regular prices preserved, promotion prices active
- **Platform isolation** → Changes only affect selected platform
- **Outlet-specific** → Updates only affect selected outlet

This ensures complete understanding of when selling prices are overwritten vs preserved during different types of bulk operations and promotion periods.