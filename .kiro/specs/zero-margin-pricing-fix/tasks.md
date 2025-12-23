# Implementation Plan: Zero Margin Pricing Fix

## Overview

Fix the psychological pricing logic in Talabat margin calculations to handle 0% margin correctly. The implementation modifies the `PricingCalculator.calculate_talabat_price()` and `smart_ceiling()` methods in `integration/utils.py` to detect zero margin scenarios and bypass psychological pricing conversion.

## Tasks

- [ ] 1. Modify PricingCalculator.calculate_talabat_price() method
  - Add zero margin detection logic
  - Bypass smart ceiling rounding for 0% margin cases
  - Use standard rounding for zero margin scenarios
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 1.1 Write property test for zero margin calculation
  - **Property 1: Zero margin preserves exact calculation**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.5, 2.2, 2.3**

- [ ] 2. Update PricingCalculator.smart_ceiling() method signature
  - Add optional margin_amount parameter
  - Preserve existing behavior for non-zero margins
  - Skip psychological pricing when margin_amount is zero
  - _Requirements: 1.4, 3.1_

- [ ] 2.1 Write property test for non-zero margin psychological pricing
  - **Property 2: Non-zero margins preserve psychological pricing**
  - **Validates: Requirements 1.4, 3.1, 3.2, 3.3, 3.4**

- [ ] 3. Update calculate_item_selling_price() function calls
  - Ensure all calls to calculate_talabat_price() work with new logic
  - Verify wrap=9900 and wrap=10000 items calculate correctly
  - Test integration with existing product update flows
  - _Requirements: 2.1, 2.4_

- [ ] 3.1 Write property test for wrap item calculation consistency
  - **Property 3: Wrap item calculation consistency**
  - **Validates: Requirements 2.1, 2.4**

- [ ] 4. Checkpoint - Test zero margin scenarios
  - Test 10.00 AED MRP with 0% margin returns 10.00 AED (not 9.99 AED)
  - Test wrap=9900 item with MRP=10.00, WDF=2, 0% margin returns 5.00 AED
  - Test wrap=10000 item with 0% margin returns exact MRP
  - Ensure all tests pass, ask the user if questions arise

- [ ] 5. Verify platform and outlet isolation
  - Ensure Pasons items remain unaffected
  - Verify all Talabat outlets get consistent pricing
  - Test that only Talabat platform items use new logic
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 5.1 Write property test for platform isolation
  - **Property 4: Platform isolation maintained**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [ ] 6. Integration testing with existing flows
  - Test product update CSV uploads with 0% margin items
  - Test rules-update-price CSV uploads with 0% margin
  - Verify ERP export calculations work correctly
  - Test shop integration export with zero margin items
  - _Requirements: All requirements_

- [ ] 6.1 Write integration tests for CSV upload flows
  - Test product update with zero margin items
  - Test rules-update-price with zero margin items
  - _Requirements: All requirements_

- [ ] 7. Final checkpoint - Comprehensive testing
  - Run all property-based tests (minimum 100 iterations each)
  - Verify no regression in existing non-zero margin behavior
  - Test edge cases (4.995 rounding, null values, division scenarios)
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Integration tests ensure compatibility with existing CSV upload flows
- The fix preserves all existing behavior for non-zero margins