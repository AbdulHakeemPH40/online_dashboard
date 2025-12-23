# Implementation Plan: Hardcoded Values Cleanup

## Overview

Systematically fix all hardcoded values and division by zero vulnerabilities in the Pasons ERP pricing system. This implementation follows a fail-fast approach with centralized validation and consistent error handling.

## Tasks

- [x] 1. Create validation utility functions
  - Add `validate_wdf_for_division()` function to utils.py
  - Add `validate_ocq_for_division()` function to utils.py
  - Implement consistent error message formatting
  - Add comprehensive logging for all validation failures
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 3.2, 3.3, 3.4, 3.5_

- [ ]* 1.1 Write property test for validation utilities
  - **Property 1: Division by zero protection**
  - **Validates: Requirements 1.1, 1.2, 2.3**

- [ ] 2. Fix critical division by zero vulnerabilities
  - [x] 2.1 Fix calculate_item_selling_price() WDF divisions (lines 821, 832)
    - Add WDF validation before division operations
    - Remove hardcoded Decimal('1') fallback
    - Use validate_wdf_for_division() utility
    - _Requirements: 1.1, 2.1, 2.3_

  - [x] 2.2 Fix item_search_api() WDF division (line 2261)
    - Add explicit zero check before division
    - Use validate_wdf_for_division() utility
    - _Requirements: 1.1, 1.4_

  - [x] 2.3 Fix is_parent_item() hardcoded fallback (line 776)
    - Remove Decimal('1') fallback
    - Add proper WDF validation
    - _Requirements: 2.1, 2.3_

- [ ]* 2.4 Write property test for division operations
  - **Property 2: No hardcoded fallbacks**
  - **Validates: Requirements 2.1, 2.2**

- [ ] 3. Remove all hardcoded fallback values
  - [x] 3.1 Fix calculate_item_converted_cost() fallback (line 865)
    - Remove Decimal('1') fallback
    - Use validate_wdf_for_division() utility
    - _Requirements: 2.1, 2.3_

  - [x] 3.2 Fix product_update() WDF fallback (line 1300)
    - Remove Decimal('1') fallback
    - Add proper validation before stock calculations
    - _Requirements: 2.1, 4.3_

  - [x] 3.3 Fix product_update() OCQ fallback (line 1304)
    - Remove integer 1 fallback
    - Use validate_ocq_for_division() utility
    - _Requirements: 2.2, 4.4_

- [ ]* 3.4 Write property test for fallback removal
  - **Property 3: Consistent error handling**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [ ] 4. Implement business rule validation
  - [ ] 4.1 Add wrap=9900 WDF validation
    - Validate WDF > 0 for all wrap=9900 items
    - Add validation before price calculations
    - _Requirements: 4.1, 4.3_

  - [ ] 4.2 Add wrap=10000 OCQ validation
    - Validate OCQ > 0 for all wrap=10000 items
    - Add validation before stock calculations
    - _Requirements: 4.2, 4.4_

- [ ]* 4.3 Write property test for business rules
  - **Property 4: Business rule validation**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Add comprehensive error handling tests
  - [ ] 6.1 Add unit tests for WDF validation edge cases
    - Test zero, None, negative values
    - Test error message format and content
    - _Requirements: 1.1, 3.2, 3.4_

  - [ ] 6.2 Add unit tests for OCQ validation edge cases
    - Test zero, None, negative values
    - Test error message format and content
    - _Requirements: 1.2, 3.3, 3.4_

- [ ]* 6.3 Write property test for validation order
  - **Property 5: Validation before calculation**
  - **Validates: Requirements 1.4, 1.5, 3.5**

- [ ] 7. Integration testing and verification
  - [ ] 7.1 Test end-to-end scenarios with invalid data
    - Test complete workflows with invalid WDF/OCQ values
    - Verify proper error propagation and logging
    - _Requirements: 1.3, 1.5, 3.5_

  - [ ] 7.2 Verify no regression in existing functionality
    - Run existing test suite
    - Test normal operations with valid data
    - Verify pricing calculations remain accurate

- [ ] 8. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- All division operations must be protected from zero values
- No hardcoded fallback values should remain in the codebase