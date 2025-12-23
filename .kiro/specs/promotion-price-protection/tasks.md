# Implementation Plan: Promotion Price Protection

## Overview

Implement selling price protection for Talabat items during promotion periods. The system will skip selling price recalculation for Talabat items with `is_on_promotion = True` while maintaining normal updates for all other cases.

## Tasks

- [ ] 1. Create promotion protection utility function
- [x] 1.1 Implement `should_protect_selling_price()` function in `integration/utils.py`
  - Check platform type and promotion status
  - Return boolean indicating if selling price should be protected
  - Handle edge cases (missing fields, invalid data)
  - _Requirements: 2.1, 3.1, 3.3_

- [ ]* 1.2 Write unit tests for protection utility function
  - Test Talabat promotion items (should protect)
  - Test Talabat non-promotion items (should not protect)
  - Test Pasons items regardless of promotion status (should not protect)
  - Test edge cases and error conditions
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.4_

- [ ] 2. Integrate protection logic into product_update function
- [x] 2.1 Modify MRP update logic in `product_update()` function
  - Add promotion status check before selling price calculation
  - Skip selling price update for protected items
  - Maintain normal updates for non-protected items
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 2.2 Add protection counters and logging
  - Track protected items vs updated items separately
  - Log when selling price updates are skipped
  - Maintain existing logging for normal updates
  - _Requirements: 5.1, 5.2_

- [ ]* 2.3 Write property test for Talabat promotion protection
  - **Property 1: Talabat Promotion Protection**
  - **Validates: Requirements 2.1, 2.4**

- [ ]* 2.4 Write property test for Pasons normal updates
  - **Property 2: Pasons Normal Updates**
  - **Validates: Requirements 2.3, 2.5, 3.4**

- [ ]* 2.5 Write property test for Talabat non-promotion updates
  - **Property 3: Talabat Non-Promotion Updates**
  - **Validates: Requirements 2.2**

- [ ] 3. Enhance user feedback and messaging
- [x] 3.1 Update success messages to include protection statistics
  - Show count of items with selling price updated
  - Show count of items with selling price protected
  - Distinguish between platforms in messages
  - _Requirements: 5.2, 5.3, 5.4_

- [x] 3.2 Add specific messaging for protection events
  - Clear indication when Talabat promotion protection is applied
  - Maintain existing messaging for normal updates
  - Handle mixed scenarios (some protected, some updated)
  - _Requirements: 5.3, 5.4_

- [ ]* 3.3 Write property test for platform-specific protection logic
  - **Property 4: Platform-Specific Protection Logic**
  - **Validates: Requirements 3.1, 3.2, 3.3**

- [ ] 4. Ensure non-price field updates work correctly
- [-] 4.1 Verify MRP, cost, and stock updates work during protection
  - Test that protected items still get MRP updates
  - Test that protected items still get cost updates
  - Test that protected items still get stock updates
  - _Requirements: 4.1, 4.2, 4.3, 4.6_

- [ ]* 4.2 Write property test for non-price field updates
  - **Property 5: Non-Price Field Updates**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.6**

- [ ] 5. Add comprehensive logging and monitoring
- [ ] 5.1 Implement detailed protection logging
  - Log each protection decision with item details
  - Include platform and promotion status in logs
  - Maintain performance with bulk operations
  - _Requirements: 5.1_

- [ ]* 5.2 Write property test for protection logging accuracy
  - **Property 6: Protection Logging Accuracy**
  - **Validates: Requirements 5.1, 5.2**

- [ ] 6. Integration testing and validation
- [ ] 6.1 Test complete product-update workflow with mixed scenarios
  - CSV with both Pasons and Talabat items
  - Mixed promotion statuses within same platform
  - Verify platform isolation is maintained
  - _Requirements: 3.3, 6.2, 6.4_

- [ ]* 6.2 Write integration tests for bulk operations
  - Test bulk updates with promotion items
  - Verify existing promotion workflows unaffected
  - Test error handling and edge cases
  - _Requirements: 6.2, 6.3, 6.4_

- [ ] 7. Final validation and testing
- [ ] 7.1 Run existing test suite to ensure no regressions
  - Verify existing promotion functionality works
  - Verify existing product-update functionality works
  - Check platform isolation tests still pass
  - _Requirements: 6.2, 6.3_

- [ ] 7.2 Performance testing with large datasets
  - Test protection logic performance with bulk operations
  - Verify logging doesn't impact performance significantly
  - Validate memory usage with large CSV files
  - _Requirements: 5.1, 5.2_

- [ ] 8. Checkpoint - Ensure all tests pass
- Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Integration tests validate end-to-end workflows
- Focus on Talabat-only protection while maintaining Pasons normal behavior