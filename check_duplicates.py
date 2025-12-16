#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'middleware_dashboard.settings')
django.setup()

from integration.models import Item
from django.db.models import Count

# Check for wrap=10000 duplicates on Pasons
print('=' * 80)
print('Wrap=10000 Duplicates (item_code + units with multiple SKUs) - Pasons Platform')
print('=' * 80)

duplicates = Item.objects.filter(wrap='10000', platform='pasons').values('item_code', 'units').annotate(count=Count('id')).filter(count__gt=1).order_by('item_code')

if duplicates.exists():
    for dup in duplicates:
        print(f"\nitem_code={dup['item_code']}, units={dup['units']}, SKU count={dup['count']}")
        
        # Get all SKUs for this combination
        items = Item.objects.filter(
            wrap='10000',
            platform='pasons',
            item_code=dup['item_code'],
            units=dup['units']
        ).values('sku', 'description')
        
        for item in items:
            print(f"  → SKU: {item['sku']}, Description: {item['description']}")
    
    print(f'\n\n📊 Summary: {duplicates.count()} item_code+units combinations have duplicates')
else:
    print('\n✅ NO DUPLICATES FOUND! All wrap=10000 items have unique (item_code, units) combinations.')

print('\n' + '=' * 80)
