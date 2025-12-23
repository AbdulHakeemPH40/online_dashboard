# Design Document

## Overview

This design addresses critical hardcoded values and division by zero vulnerabilities in the Pasons ERP pricing system. The solution implements consistent error handling, removes hardcoded fallback values, and ensures robust validation for all mathematical operations involving Weight Division Factor (WDF) and Outer Case Quantity (OCQ).

## Architecture

### Current Issues
- **Division by Zero Risk**: Missing zero checks in 3 critical functions
- **Hardcoded Fallbacks**: 5 locations using `Decimal('1')` or `1` as fallbacks
- **Inconsistent Error Handling**: Some functions raise errors, others use fallbacks
- **Business Logic Gaps**: No validation preventing invalid WDF/OCQ values

### Solution Architecture
- **Centralized Validation**: Create utility functions for WDF/OCQ validation
- **Consistent Error Handling**: Use ValueError with descriptive messages throughout
- **Fail-Fast Approach**: Validate early, fail immediately on invalid values
- **Comprehensive Logging**: Log all validation failures with context

## Components and Interfaces

### 1. Validation Utilities (New)

**Location**: `integration/utils.py`

```python
def validate_wdf_for_division(wdf: Optional[Decimal], item_code: str, operation: str) -> Decimal:
    """Validate WDF before division operations"""
    
def validate_ocq_for_division(ocq: Optional[int], item_code: str, operation: str) -> int:
    """Validate OCQ before division operations"""
```

### 2. Updated Functions

#### **PricingCalculator Methods**
- `calculate_item_selling_price()` - Add WDF validation
- `calculate_item_converted_cost()` - Remove hardcoded fallback

#### **Views Functions**
- `item_search_api()` - Add WDF zero check
- `product_update()` - Remove hardcoded fallbacks

#### **Utility Functions**
- `is_parent_item()` - Remove hardcoded fallback
- All WDF/OCQ division operations - Add proper validation

## Data Models

### Validation Rules
- **WDF**: Must be > 0 for wrap=9900 items
- **OCQ**: Must be > 0 for wrap=10000 items
- **Error Context**: Include item_code, operation, and current value

### Error Message Format
```
"Invalid {field} for {operation} on item {item_code}: {current_value}. {field} must be greater than zero."
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several properties that can be consolidated:
- Properties 1.1 and 1.2 (WDF and OCQ zero handling) can be combined into a single comprehensive division validation property
- Properties 2.1, 2.2, and 2.3 (hardcoded fallback removal) can be combined into one property testing absence of fallbacks
- Properties 3.2 and 3.3 (error message content) can be combined into one property testing error message format
- Properties 4.1 and 4.2 (business rule validation) can be combined into one property testing wrap-specific validation

### Core Properties

**Property 1: Division by zero protection**
*For any* WDF or OCQ division operation with zero, None, or invalid values, the system should raise ValueError instead of attempting division or using fallback values
**Validates: Requirements 1.1, 1.2, 2.3**

**Property 2: No hardcoded fallbacks**
*For any* function that processes WDF or OCQ values, when values are missing or invalid, the system should raise errors instead of using hardcoded fallbacks like Decimal('1') or integer 1
**Validates: Requirements 2.1, 2.2**

**Property 3: Consistent error handling**
*For any* validation failure involving WDF or OCQ values, the system should raise ValueError with error messages containing item_code, field name, current value, and operation context
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

**Property 4: Business rule validation**
*For any* wrap=9900 item, WDF must be greater than zero, and for any wrap=10000 item, OCQ must be greater than zero before any calculations
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

**Property 5: Validation before calculation**
*For any* mathematical operation involving WDF or OCQ, validation must occur before the calculation and log errors with sufficient context
**Validates: Requirements 1.4, 1.5, 3.5**

<function_calls>
<invoke name="prework">
<parameter name="featureName">hardcoded-values-cleanup

## Error Handling

### Error Types
- **ValueError**: For all invalid WDF/OCQ values
- **Logging**: All validation failures logged with context

### Error Message Format
```
"Invalid {field} for {operation} on item {item_code}: {current_value}. {field} must be greater than zero."
```

### Examples
```python
# WDF validation error
"Invalid weight_division_factor for price calculation on item 9900123: 0. weight_division_factor must be greater than zero."

# OCQ validation error  
"Invalid outer_case_quantity for stock calculation on item 100456: None. outer_case_quantity must be greater than zero."
```

## Testing Strategy

### Unit Tests
- Test each validation function with zero, None, and negative values
- Verify error messages contain required information
- Test all division operations with invalid inputs

### Property-Based Tests
- Generate random items with invalid WDF/OCQ values
- Test all functions that perform division operations
- Verify consistent error handling across all functions
- Test that no hardcoded fallbacks are used

### Integration Tests
- End-to-end scenarios with invalid data
- Database validation testing
- Logging verification

### Test Configuration
- Minimum 100 iterations per property test
- Each property test references design document property
- Tag format: **Feature: hardcoded-values-cleanup, Property {number}: {property_text}**

## Implementation Plan

### Phase 1: Create Validation Utilities
1. Add `validate_wdf_for_division()` function
2. Add `validate_ocq_for_division()` function
3. Add comprehensive logging

### Phase 2: Fix Critical Division Operations
1. Fix `calculate_item_selling_price()` - lines 821, 832
2. Fix `item_search_api()` - line 2261
3. Add validation to all identified functions

### Phase 3: Remove Hardcoded Fallbacks
1. Replace all `Decimal('1')` fallbacks with validation
2. Replace all `1` fallbacks with validation
3. Update error handling consistently

### Phase 4: Testing and Validation
1. Add comprehensive unit tests
2. Add property-based tests
3. Verify no regression in existing functionality