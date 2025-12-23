# Pricing Feature Template

## Prerequisites
Before implementing any pricing feature:

1. **Read steering files**:
   - `.kiro/steering/project-pricing-logic.md`
   - `.kiro/steering/development-guidelines.md`

2. **Understand existing system**:
   - `docs/PRICING_SYSTEM_OVERVIEW.md`
   - `integration/utils.py` (PricingCalculator class)
   - `integration/models.py` (effective_talabat_margin property)

3. **Run existing tests**:
   - `test_zero_margin_fix.py`
   - `test_talabat_margin_isolation.py`
   - `test_smart_rounding.py`

## Critical Requirements
- [ ] Platform isolation maintained (Pasons unaffected)
- [ ] Zero margin logic preserved (no .00 → .99 conversion)
- [ ] Smart rounding working (.25, .49, .75, .99 targets)
- [ ] Wrap item calculations correct (MRP ÷ WDF)
- [ ] Custom margin support maintained

## Testing Checklist
- [ ] Zero margin scenarios tested
- [ ] Both platforms tested (Pasons + Talabat)
- [ ] Wrap vs regular items tested
- [ ] Property-based tests passing
- [ ] Integration tests passing