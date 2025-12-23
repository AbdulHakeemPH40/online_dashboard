# Development Guidelines - Pasons ERP

## Before Making Changes
1. **Read existing code** - Always check current implementation first
2. **Run existing tests** - Verify current functionality works
3. **Understand platform isolation** - Talabat changes must not affect Pasons
4. **Check margin logic** - Understand default vs custom margins

## Testing Requirements
- **Always test zero margin scenarios** - Critical business requirement
- **Test both platforms** - Pasons and Talabat isolation
- **Test wrap vs regular items** - Different calculation methods
- **Run property-based tests** - Use existing test files

## Key Test Files
- `test_zero_margin_fix.py` - Zero margin pricing validation
- `test_talabat_margin_isolation.py` - Platform isolation validation  
- `test_smart_rounding.py` - Smart rounding validation
- `integration/tests/test_zero_margin_properties.py` - Property-based tests

## Common Mistakes to Avoid
- **Don't hardcode margins** - Use effective_talabat_margin property
- **Don't break platform isolation** - Test Pasons remains unaffected
- **Don't apply psychological pricing to 0% margins** - Critical requirement
- **Don't assume item types** - Check wrap field and WDF values

## Code Review Checklist
- [ ] Platform isolation maintained?
- [ ] Zero margin logic preserved?
- [ ] Smart rounding working correctly?
- [ ] Wrap item calculations correct?
- [ ] Tests passing?
- [ ] No hardcoded values?