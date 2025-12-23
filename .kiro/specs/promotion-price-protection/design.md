# Design Document - Promotion Price Protection

## Overview

This feature implements selling price protection for Talabat items during promotion periods. When Talabat items have `is_on_promotion = True`, the daily product-update function will skip selling price recalculation to preserve promotion-adjusted prices. Pasons items will continue to have normal selling price updates regardless of promotion status.

## Architecture

The protection logic will be integrated into the existing `product_update()` function in `integration/views.py`. The system will check both platform type and promotion status before deciding whether to recalculate selling prices.

```
Product Update Flow:
CSV Input → Parse → Validate → Check Platform & Promotion Status → Apply Updates
                                        ↓
                    Talabat + is_on_promotion = True → Skip selling price calculation
                    All other cases → Normal selling price calculation
```

## Components and Interfaces

### Core Components

#### 1. Promotion Status Checker
**Location**: `integration/utils.py`
**Purpose**: Utility function to determine if selling price should be protected

```python
def should_protect_selling_price(platform: str, item_outlet) -> bool:
    """
    Determine if selling price should be protected from updates
    
    Args:
        platform: 'pasons' or 'talabat'
        item_outlet: ItemOutlet instance
        
    Returns:
        True if selling price should be protected, False otherwise
    """
```

#### 2. Enhanced Product Update Logic
**Location**: `integration/views.py` (product_update function)
**Purpose**: Modified logic to conditionally skip selling price updates

**Key Changes**:
- Add promotion status check before selling price calculation
- Maintain separate counters for protected vs updated items
- Enhanced logging and user feedback

#### 3. Protection Logging System
**Purpose**: Track and report when protection is applied

**Metrics Tracked**:
- Total items processed
- Items with selling price updated (normal)
- Items with selling price protected (Talabat promotions)
- Platform-specific breakdown

### Interface Modifications

#### ItemOutlet Model Usage
**Existing Fields Used**:
- `is_on_promotion`: Boolean flag for promotion status
- `outlet_selling_price`: Field to be protected
- `outlet_mrp`: Field that always updates
- `outlet_cost`: Field that always updates
- `outlet_stock`: Field that always updates

#### Product Update Function Enhancement
**Input**: Same CSV format as existing
**Output**: Enhanced feedback messages with protection statistics

## Data Models

No new models required. Uses existing `ItemOutlet` model with `is_on_promotion` field.

**Key Field Behavior During Updates**:

| Field | Pasons (All Items) | Talabat (Non-Promotion) | Talabat (Promotion) |
|-------|-------------------|-------------------------|-------------------|
| `outlet_mrp` | ✅ Updated | ✅ Updated | ✅ Updated |
| `outlet_cost` | ✅ Updated | ✅ Updated | ✅ Updated |
| `outlet_stock` | ✅ Updated | ✅ Updated | ✅ Updated |
| `outlet_selling_price` | ✅ **Updated** | ✅ **Updated** | ❌ **Protected** |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Talabat Promotion Protection
*For any* Talabat ItemOutlet with `is_on_promotion = True`, when product-update is performed, the `outlet_selling_price` should remain unchanged while `outlet_mrp` gets updated
**Validates: Requirements 2.1, 2.4**

### Property 2: Pasons Normal Updates
*For any* Pasons ItemOutlet regardless of promotion status, when product-update is performed, both `outlet_mrp` and `outlet_selling_price` should be updated according to normal pricing logic
**Validates: Requirements 2.3, 2.5, 3.4**

### Property 3: Talabat Non-Promotion Updates
*For any* Talabat ItemOutlet with `is_on_promotion = False`, when product-update is performed, both `outlet_mrp` and `outlet_selling_price` should be updated according to normal pricing logic
**Validates: Requirements 2.2**

### Property 4: Platform-Specific Protection Logic
*For any* product-update operation, protection should only be applied to Talabat items with `is_on_promotion = True`, and all other combinations should receive normal updates
**Validates: Requirements 3.1, 3.2, 3.3**

### Property 5: Non-Price Field Updates
*For any* ItemOutlet regardless of platform or promotion status, when product-update is performed, non-selling-price fields (`outlet_mrp`, `outlet_cost`, `outlet_stock`) should always be updated normally
**Validates: Requirements 4.1, 4.2, 4.3, 4.6**

### Property 6: Protection Logging Accuracy
*For any* bulk update operation, the count of protected items should equal the number of Talabat items with `is_on_promotion = True` that were processed
**Validates: Requirements 5.1, 5.2**

## Error Handling

### Protection Logic Errors
- **Invalid promotion status**: Handle cases where `is_on_promotion` field is corrupted
- **Platform mismatch**: Ensure platform validation before applying protection
- **Database consistency**: Handle cases where ItemOutlet records are missing

### Logging Errors
- **Log write failures**: Graceful degradation if logging fails
- **Counter accuracy**: Ensure protection counters remain accurate even with errors

### User Feedback Errors
- **Message formatting**: Handle cases where protection statistics can't be calculated
- **Partial failures**: Clear messaging when some items are protected and others fail

## Testing Strategy

### Unit Tests
- Test `should_protect_selling_price()` function with various platform/promotion combinations
- Test protection logic integration in product_update function
- Test logging and counter accuracy
- Test error handling for edge cases

### Property-Based Tests
- Generate random ItemOutlet instances with various platform/promotion combinations
- Verify protection is applied correctly across all scenarios
- Test bulk operations with mixed promotion statuses
- Validate field update behavior matches specifications

**Property Test Configuration**:
- Minimum 100 iterations per property test
- Each test references its design document property
- Tag format: **Feature: promotion-price-protection, Property {number}: {property_text}**

### Integration Tests
- Test complete product-update workflow with promotion items
- Verify existing promotion workflows remain unaffected
- Test platform isolation with mixed updates
- Validate user feedback and logging accuracy

**Testing Approach**:
- **Unit tests**: Verify specific protection logic and edge cases
- **Property tests**: Verify universal protection behavior across all inputs
- Both types complement each other for comprehensive coverage