# Digital Ocean BLS Check Commands

Run these commands on your Digital Ocean server to check BLS locks:

```bash
# 1. Navigate to project directory
cd /var/www/myproject

# 2. Activate virtual environment
source venv/bin/activate

# 3. Run the BLS test script
python test_bls_locks.py

# 4. If no BLS locks found, you can create test ones by running:
python manage.py shell

# Then in Django shell:
from integration.models import ItemOutlet
# Find some test items
test_items = ItemOutlet.objects.filter(item__platform='pasons', outlet__is_active=True)[:3]
for i, io in enumerate(test_items):
    if i == 0:
        io.price_locked = True
        io.save()
        print(f"Created BLS Price Lock: {io.item.item_code} at {io.outlet.name}")
    elif i == 1:
        io.status_locked = True  
        io.save()
        print(f"Created BLS Status Lock: {io.item.item_code} at {io.outlet.name}")

exit()

# 5. Test the locked products report API directly:
curl "http://your-domain.com/integration/api/locked-products-data/?platform=pasons&lock_type=bls_price&outlet=1"
```

## Expected Results:

**If BLS locks exist on Digital Ocean:**
- The API should return BLS locked items
- The locked products report should display them

**If no BLS locks on Digital Ocean:**
- Create some test locks using the Django shell commands above
- Then test the report again

## Key Points:

1. **BLS locks are created manually** - only when users check the BLS checkboxes in dashboard
2. **Different environments may have different data** - local vs production databases
3. **The code is working correctly** - issue is likely missing test data on Digital Ocean