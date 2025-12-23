# Design Document

## Overview

This design addresses the psychological pricing issue in Talabat margin calculations where 0% margin items incorrectly get converted from .00 to .99 endings. The solution modifies the `PricingCalculator.smart_ceiling()` method to detect zero margin scenarios and bypass psychological pricing conversion, returning exact MRP-based prices instead.

## Architecture

The fix involves modifying the pricing calculation flow in the `integration/utils.py` file:

```
Current Flow:
MRP → Base Price → Add Margin (0%) → Smart Ceiling → Psychological Pricing (.00 → .99)

Fixed Flow:
MRP → Base Price → Add Margin (0%) → Detect Zero Margin → Standard Rounding (preserve .00)
```

## Components and Interfaces

### Modified Components

1. **PricingCalculator.calculate_talabat_price()**
   - Add zero margin detection logic
   - Bypass smart ceiling rounding for 0% margin
   - Use standard rounding instead

2. **PricingCalculator.smart_ceiling()**
   - Add margin_amount parameter to detect zero margin scenarios
   - Preserve existing behavior for non-zero margins

### Interface Changes

```python
# Modified method signature
@staticmethod
def calculate_talabat_price(
    base_price: Decimal,
    margin_percentage: Optional[Decimal] = None,
    item_code: Optional[str] = None
) -> Tuple[Decimal, Decimal]:
    # Returns: (final_price, margin_amount)
```

```python
# Modified method signature  
@staticmethod
def smart_ceiling(price: Decimal, margin_amount: Optional[Decimal] = None) -> Decimal:
    # New parameter: margin_amount to detect zero margin scenarios
```

## Data Models

No database schema changes required. The fix operates at the calculation level using existing fields:
- `Item.talabat_margin` (custom margin field)
- `Item.effective_talabat_margin` (property that returns custom or default margin)
- `Item.wrap` (9900 vs 10000 item type)
- `Item.weight_division_factor` (for wrap=9900 calculations)

## Error Handling

### Edge Cases Handled

1. **Null/None margin values**: Treated as default margin (not zero)
2. **Decimal precision**: Maintain 2 decimal places for final prices
3. **Wrap item calculations**: Handle division by weight_division_factor correctly
4. **Rounding edge cases**: 4.995 → 5.00 using standard rounding

### Error Scenarios

1. **Invalid margin values**: Existing validation in `rules_update_price` view handles this
2. **Division by zero**: Existing weight_division_factor validation prevents this
3. **Decimal overflow**: Existing Decimal precision handling manages this

## Testing Strategy

### Unit Tests
- Test 0% margin with various MRP values (10.00, 15.00, 20.50)
- Test wrap=9900 items with 0% margin and different weight_division_factors
- Test wrap=10000 items with 0% margin
- Test non-zero margins continue using psychological pricing
- Test edge cases (4.995 rounding, null values)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several properties that can be consolidated:
- Properties 1.1, 1.2, 1.3 can be combined into a comprehensive "Zero margin preserves exact calculation" property
- Properties 1.4, 3.1, 3.2, 3.3, 3.4 can be combined into "Non-zero margins preserve psychological pricing" property
- Properties 2.2 and 2.3 are covered by the main zero margin property
- Properties 4.1, 4.3, 4.4 can be combined into "Platform isolation maintained" property

### Core Properties

**Property 1: Zero margin preserves exact calculation**
*For any* Talabat item with 0% margin, the final selling price should equal the exact mathematical result without psychological pricing conversion: wrap=10000 items return MRP, wrap=9900 items return MRP/weight_division_factor, all rounded to 2 decimal places using standard rounding
**Validates: Requirements 1.1, 1.2, 1.3, 1.5, 2.2, 2.3**

**Property 2: Non-zero margins preserve psychological pricing**
*For any* Talabat item with margin > 0%, the system should continue applying smart ceiling rounding and psychological pricing conversion (prices ending in .00 become .99 of previous whole number)
**Validates: Requirements 1.4, 3.1, 3.2, 3.3, 3.4**

**Property 3: Wrap item calculation consistency**
*For any* wrap=9900 item, regardless of margin percentage, the base calculation should be MRP/weight_division_factor before margin application, and margin application should be consistent with wrap=10000 items
**Validates: Requirements 2.1, 2.4**

**Property 4: Platform isolation maintained**
*For any* pricing calculation, Pasons items should remain unaffected by Talabat pricing changes, and all Talabat outlets should receive identical calculated prices for the same item
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property-Based Tests
- Each property will be implemented as a separate property-based test
- Tests will run minimum 100 iterations with randomized inputs
- Each test will be tagged with the corresponding property number and requirements
- Tests will use the existing property-based testing framework specified in the project