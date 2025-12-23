# Pasons ERP - Pricing System Overview

## System Architecture

```
ERP Price (MRP) 
    ↓
Base Price Calculation (wrap-dependent)
    ↓  
Margin Application (platform-dependent)
    ↓
Smart Rounding (margin-dependent)
    ↓
Final Selling Price
```

## Platform Isolation
- **Pasons**: Uses MRP directly, no margins
- **Talabat**: Applies margins with smart rounding
- **Critical**: Changes to Talabat logic must NEVER affect Pasons

## Margin Priority System
1. **Custom margin** (set via CSV upload) - HIGHEST PRIORITY
2. **Auto-detected margin** (based on item code):
   - 9900xxx items → 17%
   - 100xxx items → 15%
3. **Pasons** → Always 0%

## Zero Margin Special Case
When margin = 0%:
- Skip psychological pricing (.00 → .99 conversion)
- Return exact calculated price
- Apply only standard 2-decimal rounding

## Smart Rounding Logic
For non-zero margins:
- Find decimal part of price
- Round UP to nearest target: .25, .49, .75, .99
- Apply psychological pricing (.00 → .99)

## Wrap Item Logic
- **wrap=9900**: Price = (MRP ÷ weight_division_factor) + margin
- **wrap=10000**: Price = MRP + margin
- **No wrap**: Price = MRP + margin

## Implementation Files
- `integration/utils.py` - Core pricing calculations
- `integration/models.py` - Business logic and properties  
- `integration/views.py` - CSV upload and bulk operations