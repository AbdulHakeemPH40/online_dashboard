# Requirements Document - Promotion Price Protection

## Introduction

During promotion periods, items have adjusted selling prices that should be preserved during daily MRP updates. Currently, the product-update function overwrites these promotion-adjusted selling prices with calculated MRP + margin prices, which breaks the promotion pricing.

## Glossary

- **ItemOutlet**: Outlet-specific product data including pricing and promotion status
- **Product_Update**: Daily MRP update function that recalculates selling prices
- **Promotion_Period**: Time when items have special adjusted selling prices
- **is_on_promotion**: Boolean field indicating if item is currently in promotion
- **Selling_Price_Protection**: Logic to prevent overwriting promotion-adjusted prices

## Requirements

### Requirement 1: Promotion Status Detection

**User Story:** As a system administrator, I want the system to detect when items are in promotion, so that their adjusted selling prices are protected from automatic updates.

#### Acceptance Criteria

1. WHEN an item has `is_on_promotion = True`, THE System SHALL recognize it as a promotion item
2. WHEN an item has `is_on_promotion = False`, THE System SHALL treat it as a regular item
3. THE System SHALL check promotion status before any selling price calculation
4. THE System SHALL maintain promotion status accuracy across all operations

### Requirement 2: Selling Price Protection During Product Updates (Talabat Only)

**User Story:** As a business manager, I want Talabat promotion-adjusted selling prices to be preserved during daily MRP updates, so that Talabat promotion pricing remains intact, while Pasons prices update normally.

#### Acceptance Criteria

1. WHEN a product-update is performed on Talabat items with `is_on_promotion = True`, THE System SHALL skip selling price recalculation
2. WHEN a product-update is performed on Talabat items with `is_on_promotion = False`, THE System SHALL perform normal selling price calculation
3. WHEN a product-update is performed on Pasons items, THE System SHALL always perform normal selling price calculation regardless of promotion status
4. WHEN MRP is updated for Talabat promotion items, THE System SHALL update outlet_mrp but preserve outlet_selling_price
5. WHEN MRP is updated for Pasons items, THE System SHALL update both outlet_mrp and outlet_selling_price normally
6. THE System SHALL log when selling price updates are skipped due to Talabat promotion protection

### Requirement 3: Platform-Specific Promotion Protection Logic

**User Story:** As a platform manager, I want promotion protection to apply only to Talabat platform, so that Pasons pricing updates work normally while Talabat promotions are protected.

#### Acceptance Criteria

1. WHEN Talabat items are in promotion (`is_on_promotion = True`), THE System SHALL protect Talabat selling prices from updates
2. WHEN Pasons items are in promotion (`is_on_promotion = True`), THE System SHALL allow normal selling price updates (no protection)
3. THE System SHALL check platform type before applying promotion protection logic
4. THE System SHALL maintain normal Pasons pricing behavior regardless of promotion status

### Requirement 4: Selective Field Updates During Talabat Promotions

**User Story:** As a data manager, I want non-price fields to update normally during Talabat promotions, so that inventory and cost data stays current while protecting only Talabat promotional pricing.

#### Acceptance Criteria

1. WHEN Talabat items are in promotion, THE System SHALL allow MRP updates (outlet_mrp field)
2. WHEN Talabat items are in promotion, THE System SHALL allow cost updates (outlet_cost field)
3. WHEN Talabat items are in promotion, THE System SHALL allow stock updates (outlet_stock field)
4. WHEN Talabat items are in promotion, THE System SHALL prevent selling price updates (outlet_selling_price field)
5. WHEN Pasons items are in promotion, THE System SHALL update all fields normally including selling price
6. THE System SHALL update all non-selling-price fields normally for both platforms

### Requirement 5: Promotion Protection Logging and Feedback

**User Story:** As a system operator, I want to know when Talabat selling price updates are skipped due to promotions, so that I can verify the protection is working correctly.

#### Acceptance Criteria

1. WHEN Talabat selling price updates are skipped due to promotion protection, THE System SHALL log the action
2. WHEN bulk updates complete, THE System SHALL report how many Talabat items were protected from price updates
3. THE System SHALL distinguish between regular updates, Talabat promotion-protected updates, and normal Pasons updates in messages
4. THE System SHALL provide clear feedback about which Talabat items had protected pricing

### Requirement 6: Integration with Existing Promotion System

**User Story:** As a promotion manager, I want the protection system to work seamlessly with existing promotion management, so that current promotion workflows continue unchanged.

#### Acceptance Criteria

1. THE System SHALL use existing `is_on_promotion` field for protection logic
2. THE System SHALL not modify existing promotion creation or cancellation workflows
3. THE System SHALL work with existing promotion start/end date logic
4. THE System SHALL maintain compatibility with bulk promotion updates