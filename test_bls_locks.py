#!/usr/bin/env python3
"""
Test script to check if there are any BLS locks in the database
and demonstrate how to create them for testing the locked products report.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'middleware_dashboard.settings')
django.setup()

from integration.models import Item, Outlet, ItemOutlet

def check_bls_locks():
    """Check if there are any BLS locks in the database"""
    
    print("=== Checking BLS Locks in Database ===")
    
    # Check for BLS price locks
    bls_price_locks = ItemOutlet.objects.filter(price_locked=True)
    print(f"BLS Price Locks found: {bls_price_locks.count()}")
    
    # Check for BLS status locks  
    bls_status_locks = ItemOutlet.objects.filter(status_locked=True)
    print(f"BLS Status Locks found: {bls_status_locks.count()}")
    
    # Check for CLS locks for comparison
    cls_price_locks = Item.objects.filter(price_locked=True)
    cls_status_locks = Item.objects.filter(status_locked=True)
    print(f"CLS Price Locks found: {cls_price_locks.count()}")
    print(f"CLS Status Locks found: {cls_status_locks.count()}")
    
    # Show detailed BLS lock information
    print("\n=== BLS Price Locks Details ===")
    for lock in bls_price_locks:
        print(f"  - Item: {lock.item.item_code} | Outlet: {lock.outlet.name} ({lock.outlet.store_id}) | Platform: {lock.outlet.platforms}")
    
    print("\n=== BLS Status Locks Details ===")
    for lock in bls_status_locks:
        print(f"  - Item: {lock.item.item_code} | Outlet: {lock.outlet.name} ({lock.outlet.store_id}) | Platform: {lock.outlet.platforms}")
    
    # Test the exact query used by the API
    print("\n=== Testing API Query for Pasons Platform ===")
    pasons_outlets = Outlet.objects.filter(platforms='pasons', is_active=True)
    print(f"Pasons outlets found: {pasons_outlets.count()}")
    
    pasons_bls_status = ItemOutlet.objects.filter(
        outlet__in=pasons_outlets,
        item__platform='pasons',
        status_locked=True
        # Removed is_active_in_outlet=True to match API fix
    ).select_related('item', 'outlet')
    print(f"Pasons BLS Status Locks (API query): {pasons_bls_status.count()}")
    
    for lock in pasons_bls_status:
        print(f"  - Found: {lock.item.item_code} at {lock.outlet.name} | Active: {lock.is_active_in_outlet}")
    
    print("\n=== Testing API Query for Talabat Platform ===")
    talabat_outlets = Outlet.objects.filter(platforms='talabat', is_active=True)
    print(f"Talabat outlets found: {talabat_outlets.count()}")
    
    talabat_bls_status = ItemOutlet.objects.filter(
        outlet__in=talabat_outlets,
        item__platform='talabat',
        status_locked=True
        # Removed is_active_in_outlet=True to match API fix
    ).select_related('item', 'outlet')
    print(f"Talabat BLS Status Locks (API query): {talabat_bls_status.count()}")
    
    for lock in talabat_bls_status:
        print(f"  - Found: {lock.item.item_code} at {lock.outlet.name} | Active: {lock.is_active_in_outlet}")
    
    if bls_price_locks.count() == 0 and bls_status_locks.count() == 0:
        print("\n❌ NO BLS LOCKS FOUND!")
        print("This explains why BLS data doesn't show in the locked products report.")
        print("BLS locks are only created when users manually check the BLS checkboxes in the dashboard.")
        
        # Show how to create test BLS locks
        print("\n=== Creating Test BLS Locks ===")
        create_test_bls_locks()
    else:
        print("\n✅ BLS locks found in database")

def create_test_bls_locks():
    """Create some test BLS locks for demonstration"""
    
    # Find some ItemOutlet records to apply BLS locks to
    test_items = ItemOutlet.objects.filter(
        item__platform='pasons',  # Use Pasons platform
        outlet__is_active=True,
        is_active_in_outlet=True
    )[:5]  # Get first 5 items
    
    if test_items.count() == 0:
        print("❌ No ItemOutlet records found to create test locks")
        return
    
    created_locks = 0
    
    for i, io in enumerate(test_items):
        if i < 2:  # First 2 items get BLS price locks
            io.price_locked = True
            io.save(update_fields=['price_locked'])
            print(f"✅ Created BLS Price Lock: {io.item.item_code} at {io.outlet.name}")
            created_locks += 1
        elif i < 4:  # Next 2 items get BLS status locks
            io.status_locked = True
            io.save(update_fields=['status_locked'])
            print(f"✅ Created BLS Status Lock: {io.item.item_code} at {io.outlet.name}")
            created_locks += 1
    
    print(f"\n✅ Created {created_locks} test BLS locks")
    print("Now you can test the locked products report with BLS data!")

if __name__ == '__main__':
    check_bls_locks()