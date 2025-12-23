# Requirements Document

## Introduction

Fix the psychological pricing logic in Talabat margin calculations to handle 0% margin correctly. Currently, when a custom margin of 0% is applied, the system incorrectly converts prices ending in .00 to .99 (e.g., 10.00 AED → 9.99 AED). For 0% margin, the system should return the actual MRP price without psychological pricing conversion.

## Glossary

- **System**: Talabat pricing calculation system
- **MRP**: Maximum Retail Price (input price)
- **Margin**: Percentage markup applied to MRP
- **Psychological_Pricing**: Converting .00 endings to .99 for marketing appeal
- **Smart_Ceiling**: Rounding algorithm that applies psychological pricing
- **Wrap_Item**: Items with wrap=9900 (weight-based, uses weight_division_factor)
- **Regular_Item**: Items with wrap=10000 (standard items)

## Requirements

### Requirement 1: Zero Margin Pricing Logic

**User Story:** As a pricing manager, I want 0% margin items to show actual MRP prices, so that I can offer products at exact cost without artificial price reductions.

#### Acceptance Criteria

1. WHEN a Talabat item has 0% custom margin AND MRP ends in .00, THE System SHALL return the exact MRP without psychological pricing conversion
2. WHEN a Talabat item has 0% custom margin AND wrap=10000, THE System SHALL return MRP as final selling price
3. WHEN a Talabat item has 0% custom margin AND wrap=9900, THE System SHALL return MRP divided by weight_division_factor as final selling price
4. WHEN a Talabat item has margin > 0%, THE System SHALL continue applying psychological pricing conversion (.00 → .99)
5. WHEN calculating 0% margin prices, THE System SHALL use standard rounding (0.01) instead of smart ceiling rounding

### Requirement 2: Wrap Item Handling for Zero Margin

**User Story:** As a pricing manager, I want wrap items (9900) with 0% margin to calculate correctly based on weight division factor, so that weight-based pricing remains accurate.

#### Acceptance Criteria

1. WHEN a wrap=9900 item has 0% margin AND MRP=10.00 AND weight_division_factor=2, THE System SHALL return 5.00 as final selling price
2. WHEN a wrap=9900 item has 0% margin AND calculated price has decimals (e.g., 4.995), THE System SHALL round to 2 decimal places using standard rounding
3. WHEN a wrap=9900 item has 0% margin, THE System SHALL NOT apply psychological pricing conversion
4. WHEN a wrap=9900 item has margin > 0%, THE System SHALL apply normal margin calculation then psychological pricing

### Requirement 3: Preserve Existing Behavior for Non-Zero Margins

**User Story:** As a pricing manager, I want items with margins > 0% to continue using psychological pricing, so that marketing appeal is maintained for profitable items.

#### Acceptance Criteria

1. WHEN a Talabat item has margin > 0% AND final price ends in .00, THE System SHALL convert to .99 of previous whole number
2. WHEN a Talabat item has margin > 0%, THE System SHALL continue using smart ceiling rounding
3. WHEN a Talabat item has default margin (17% or 15%), THE System SHALL maintain current psychological pricing behavior
4. WHEN a Talabat item has custom margin > 0%, THE System SHALL apply psychological pricing conversion

### Requirement 4: Platform and Outlet Isolation

**User Story:** As a system architect, I want pricing changes to maintain platform and outlet isolation, so that Pasons pricing remains unaffected and all Talabat outlets get consistent pricing.

#### Acceptance Criteria

1. WHEN zero margin pricing logic is applied, THE System SHALL only affect Talabat platform items
2. WHEN zero margin pricing is calculated, THE System SHALL apply the same price to all Talabat outlets for that item
3. WHEN Pasons items are processed, THE System SHALL continue using existing Pasons pricing logic (no margins)
4. WHEN pricing calculations occur, THE System SHALL maintain strict platform isolation between Pasons and Talabat