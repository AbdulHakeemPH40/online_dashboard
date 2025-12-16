#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'middleware_dashboard.settings')
django.setup()

from integration.models import Item, ItemOutlet, Outlet
from decimal import Decimal

# Check for wrap=9900 items with item_codes: 9900127, 9900129, 9900130
item_codes = ['9900127', '9900129', '9900130']

print('=' * 100)
print('WRAP=9900 ITEMS - CHECKING PARENT/CHILD STRUCTURE')
print('=' * 100)

for item_code in item_codes:
    print(f'\n📦 Item Code: {item_code}')
    print('-' * 100)
    
    items = Item.objects.filter(item_code=item_code, wrap='9900').order_by('sku')
    
    if not items.exists():
        print(f'  ❌ NO ITEMS FOUND FOR {item_code}')
        continue
    
    for item in items:
        wdf = item.weight_division_factor or Decimal('1')
        is_parent = wdf == Decimal('1')
        item_type = "PARENT" if is_parent else "CHILD"
        
        print(f'\n  SKU: {item.sku}')
        print(f'  WDF: {wdf} ({item_type})')
        print(f'  Description: {item.description}')
        print(f'  Selling Price: {item.selling_price}')
        print(f'  Cost: {item.cost}')
        
        # Check ItemOutlets for store_id 100001 (if exists)
        outlet_100001 = Outlet.objects.filter(store_id='100001').first()
        if outlet_100001:
            io = ItemOutlet.objects.filter(item=item, outlet=outlet_100001).first()
            if io:
                print(f'  └─ Store ID 100001:')
                print(f'     • Outlet Stock: {io.outlet_stock}')
                print(f'     • Outlet Selling Price: {io.outlet_selling_price}')
                print(f'     • Outlet MRP: {io.outlet_mrp}')
                print(f'     • Outlet Cost: {io.outlet_cost}')
            else:
                print(f'  └─ Store ID 100001: NOT ASSIGNED')
        else:
            print(f'  └─ Store ID 100001: NOT FOUND IN DB')

print('\n' + '=' * 100)
