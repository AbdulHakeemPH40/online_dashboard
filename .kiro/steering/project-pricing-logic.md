# Pasons ERP - Pricing Logic & Business Rules

## Core Platform Architecture
- **Pasons Platform**: No margins, exact MRP prices
- **Talabat Platform**: Margins applied with smart rounding
- **Platform Isolation**: Changes to Talabat margins NEVER affect Pasons

## Margin System Rules

### Default Margins (Auto-detected)
- **wrap=9900 items**: 17% margin (weight-based items)
- **wrap=10000 items**: 15% margin (regular items)

### Custom Margins (Override defaults)
- Set via bulk item creation CSV upload (`talabat_margin` column)
- Set via rules-update-price page CSV upload
- Range: 0-100%

### Zero Margin Special Logic
- **0% margin**: NEVER apply psychological pricing (.00 → .99)
- **0% margin**: Return exact calculated prices
- **Non-zero margins**: Apply smart ceiling rounding

## Smart Rounding Targets
- **.01 to .24** → round to **.25**
- **.25 to .48** → round to **.49** 
- **.49 to .74** → round to **.75**
- **.75 to .98** → round to **.99**
- **.00** → convert to **.99** (psychological pricing) - EXCEPT for 0% margin

## Wrap Item Calculations

### wrap=9900 (Weight-based items)
- **Base price**: MRP ÷ weight_division_factor
- **Example**: MRP 10.00, WDF=2 → Base price = 5.00
- **Then apply margin and rounding**

### wrap=10000 (Regular items)  
- **Base price**: MRP as-is
- **Then apply margin and rounding**

## Critical Implementation Points
- Use `PricingCalculator.calculate_talabat_price()` for all Talabat pricing
- Use `item.effective_talabat_margin` property for margin detection
- Zero margin bypasses ALL smart rounding
- Platform isolation is mandatory - test with `test_talabat_margin_isolation.py`

## Promotion System Integration
- **Regular pricing**: Calculated from MRP + margin + rounding
- **Promotion periods**: Temporary price overrides (separate from regular prices)
- **During promotion**: Promotion price active, regular price preserved
- **After promotion**: System reverts to preserved regular price

## Bulk Update Behavior
### MRP Updates (product-update):
- **YES**: Selling price is recalculated and overwritten
- **Logic**: New MRP → Apply margin → Smart rounding → Update outlet_selling_price
- **Platform isolation**: Only affects selected platform/outlet

### Stock-Only Updates:
- **NO**: Selling price remains unchanged
- **Logic**: Only outlet_stock is updated

### During Promotion Periods:
- **Regular price**: Preserved in outlet_selling_price
- **Active price**: Promotion price (from promotion tables)
- **Bulk MRP updates**: Still update regular price (for post-promotion use)

## File Locations
- **Pricing logic**: `integration/utils.py` (PricingCalculator class)
- **Model logic**: `integration/models.py` (Item.effective_talabat_margin)
- **Bulk operations**: `integration/views.py` (product_update, bulk_item_creation)
- **Promotion system**: `integration/promotion_views.py` (promotion functions)
- **Price updates**: `integration/views.py` (rules_update_price function)