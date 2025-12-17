"""
Unit tests for BLS and CLS lock toggle functionality.

Tests cover:
1. BLS Status Lock: CHECKED=disabled, UNCHECKED=enabled (based on stock)
2. BLS Price Lock: Toggle price_locked field
3. CLS Status Lock: Cascade to all outlets with stock-based calculation
4. CLS Price Lock: Cascade to all outlets
5. Export behavior: Disabled items export with stock_status=0
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from integration.models import Item, Outlet, ItemOutlet
from integration.views import calculate_outlet_enabled_status
from integration.export_service import ExportService


class BLSStatusLockTestCase(TestCase):
    """Test BLS (Branch Locking System) Status Lock toggle"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')
        
        # Create outlet
        self.outlet = Outlet.objects.create(
            name='Test Store',
            store_id='100001',
            platforms='pasons',
            is_active=True
        )
        
        # Create item with sufficient stock
        self.item = Item.objects.create(
            platform='pasons',
            item_code='TEST001',
            description='Test Item',
            units='pcs',
            sku='SKU001',
            wrap='9900',
            minimum_qty=10,
            weight_division_factor=Decimal('1.0'),
            is_active=True
        )
        
        # Create ItemOutlet with stock > minimum_qty (should be enabled)
        self.item_outlet = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet,
            outlet_stock=20,  # > minimum_qty (10)
            outlet_selling_price=Decimal('100.00'),
            is_active_in_outlet=True,
            status_locked=False
        )
    
    def test_bls_status_lock_checked_disables_item(self):
        """Test: CHECKED (locked=True) → Force DISABLED"""
        response = self.client.post('/integration/api/outlet-lock-toggle/', {
            'item_code': 'TEST001',
            'store_id': '100001',
            'lock_type': 'status',
            'value': 'lock'  # CHECKED
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload from DB
        self.item_outlet.refresh_from_db()
        
        # Assertions
        self.assertTrue(self.item_outlet.status_locked, "status_locked should be True")
        self.assertFalse(self.item_outlet.is_active_in_outlet, "is_active_in_outlet should be False (disabled)")
    
    def test_bls_status_unlock_enables_based_on_stock_sufficient(self):
        """Test: UNCHECKED (locked=False) with sufficient stock → ENABLED"""
        # First lock it
        self.item_outlet.status_locked = True
        self.item_outlet.is_active_in_outlet = False
        self.item_outlet.save()
        
        # Now unlock
        response = self.client.post('/integration/api/outlet-lock-toggle/', {
            'item_code': 'TEST001',
            'store_id': '100001',
            'lock_type': 'status',
            'value': 'unlock'  # UNCHECKED
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload from DB
        self.item_outlet.refresh_from_db()
        
        # Assertions
        self.assertFalse(self.item_outlet.status_locked, "status_locked should be False")
        self.assertTrue(self.item_outlet.is_active_in_outlet, "is_active_in_outlet should be True (enabled by stock)")
    
    def test_bls_status_unlock_disabled_insufficient_stock(self):
        """Test: UNCHECKED (locked=False) with insufficient stock → DISABLED"""
        # Set stock below minimum_qty
        self.item_outlet.outlet_stock = 5  # < minimum_qty (10)
        self.item_outlet.status_locked = True
        self.item_outlet.is_active_in_outlet = False
        self.item_outlet.save()
        
        # Now unlock
        response = self.client.post('/integration/api/outlet-lock-toggle/', {
            'item_code': 'TEST001',
            'store_id': '100001',
            'lock_type': 'status',
            'value': 'unlock'  # UNCHECKED
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload from DB
        self.item_outlet.refresh_from_db()
        
        # Assertions
        self.assertFalse(self.item_outlet.status_locked, "status_locked should be False")
        self.assertFalse(self.item_outlet.is_active_in_outlet, "is_active_in_outlet should be False (disabled by stock rules)")


class BLSPriceLockTestCase(TestCase):
    """Test BLS Price Lock toggle"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')
        
        self.outlet = Outlet.objects.create(
            name='Test Store',
            store_id='100001',
            platforms='pasons',
            is_active=True
        )
        
        self.item = Item.objects.create(
            platform='pasons',
            item_code='TEST001',
            description='Test Item',
            units='pcs',
            sku='SKU001',
            is_active=True
        )
        
        self.item_outlet = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet,
            outlet_stock=10,
            outlet_selling_price=Decimal('100.00'),
            price_locked=False
        )
    
    def test_bls_price_lock_toggle(self):
        """Test: BLS price lock toggles correctly"""
        # Lock price
        response = self.client.post('/integration/api/outlet-lock-toggle/', {
            'item_code': 'TEST001',
            'store_id': '100001',
            'lock_type': 'price',
            'value': 'lock'
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        self.item_outlet.refresh_from_db()
        self.assertTrue(self.item_outlet.price_locked)
        
        # Unlock price
        response = self.client.post('/integration/api/outlet-lock-toggle/', {
            'item_code': 'TEST001',
            'store_id': '100001',
            'lock_type': 'price',
            'value': 'unlock'
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        self.item_outlet.refresh_from_db()
        self.assertFalse(self.item_outlet.price_locked)


class CLSStatusLockTestCase(TestCase):
    """Test CLS (Central Locking System) Status Lock cascade"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')
        
        # Create 2 outlets
        self.outlet1 = Outlet.objects.create(
            name='Store 1',
            store_id='100001',
            platforms='pasons',
            is_active=True
        )
        self.outlet2 = Outlet.objects.create(
            name='Store 2',
            store_id='100002',
            platforms='pasons',
            is_active=True
        )
        
        # Create item
        self.item = Item.objects.create(
            platform='pasons',
            item_code='TEST001',
            description='Test Item',
            units='pcs',
            sku='SKU001',
            wrap='9900',
            minimum_qty=10,
            weight_division_factor=Decimal('1.0'),
            status_locked=False,
            is_active=True
        )
        
        # Create ItemOutlets with different stock levels
        self.io1 = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet1,
            outlet_stock=20,  # > minimum_qty → should enable when unlocked
            is_active_in_outlet=True,
            status_locked=False
        )
        self.io2 = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet2,
            outlet_stock=5,  # < minimum_qty → should stay disabled when unlocked
            is_active_in_outlet=True,
            status_locked=False
        )
    
    def test_cls_status_lock_cascades_disable_to_all_outlets(self):
        """Test: CLS LOCKED → Force disable ALL outlets"""
        response = self.client.post('/integration/api/cls-lock-toggle/', {
            'item_code': 'TEST001',
            'platform': 'pasons',
            'lock_type': 'status',
            'value': 'lock'
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload
        self.item.refresh_from_db()
        self.io1.refresh_from_db()
        self.io2.refresh_from_db()
        
        # Assertions
        self.assertTrue(self.item.status_locked, "Item CLS status_locked should be True")
        self.assertTrue(self.io1.status_locked, "Outlet1 BLS status_locked should be True")
        self.assertTrue(self.io2.status_locked, "Outlet2 BLS status_locked should be True")
        self.assertFalse(self.io1.is_active_in_outlet, "Outlet1 should be disabled")
        self.assertFalse(self.io2.is_active_in_outlet, "Outlet2 should be disabled")
    
    def test_cls_status_unlock_calculates_based_on_stock(self):
        """Test: CLS UNLOCKED → Calculate is_active_in_outlet based on stock rules"""
        # First lock
        self.item.status_locked = True
        self.item.save()
        self.io1.status_locked = True
        self.io1.is_active_in_outlet = False
        self.io1.save()
        self.io2.status_locked = True
        self.io2.is_active_in_outlet = False
        self.io2.save()
        
        # Now unlock
        response = self.client.post('/integration/api/cls-lock-toggle/', {
            'item_code': 'TEST001',
            'platform': 'pasons',
            'lock_type': 'status',
            'value': 'unlock'
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload
        self.item.refresh_from_db()
        self.io1.refresh_from_db()
        self.io2.refresh_from_db()
        
        # Assertions
        self.assertFalse(self.item.status_locked, "Item CLS status_locked should be False")
        self.assertFalse(self.io1.status_locked, "Outlet1 BLS status_locked should be False")
        self.assertFalse(self.io2.status_locked, "Outlet2 BLS status_locked should be False")
        
        # Stock-based calculation
        self.assertTrue(self.io1.is_active_in_outlet, "Outlet1 should be enabled (stock=20 > min=10)")
        self.assertFalse(self.io2.is_active_in_outlet, "Outlet2 should be disabled (stock=5 < min=10)")


class CLSPriceLockTestCase(TestCase):
    """Test CLS Price Lock cascade"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')
        
        self.outlet1 = Outlet.objects.create(
            name='Store 1',
            store_id='100001',
            platforms='pasons',
            is_active=True
        )
        self.outlet2 = Outlet.objects.create(
            name='Store 2',
            store_id='100002',
            platforms='pasons',
            is_active=True
        )
        
        self.item = Item.objects.create(
            platform='pasons',
            item_code='TEST001',
            description='Test Item',
            units='pcs',
            sku='SKU001',
            price_locked=False,
            is_active=True
        )
        
        self.io1 = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet1,
            price_locked=False
        )
        self.io2 = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet2,
            price_locked=False
        )
    
    def test_cls_price_lock_cascades_to_all_outlets(self):
        """Test: CLS price lock cascades to ALL outlets"""
        response = self.client.post('/integration/api/cls-lock-toggle/', {
            'item_code': 'TEST001',
            'platform': 'pasons',
            'lock_type': 'price',
            'value': 'lock'
        })
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Reload
        self.item.refresh_from_db()
        self.io1.refresh_from_db()
        self.io2.refresh_from_db()
        
        # Assertions
        self.assertTrue(self.item.price_locked)
        self.assertTrue(self.io1.price_locked)
        self.assertTrue(self.io2.price_locked)


class ExportDisabledItemsTestCase(TestCase):
    """Test that disabled items export with stock_status=0"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        self.outlet = Outlet.objects.create(
            name='Test Store',
            store_id='100001',
            platforms='pasons',
            is_active=True
        )
        
        # Create enabled item
        self.item_enabled = Item.objects.create(
            platform='pasons',
            item_code='ENABLED001',
            description='Enabled Item',
            units='pcs',
            sku='SKU_ENABLED',
            wrap='9900',
            minimum_qty=10,
            weight_division_factor=Decimal('1.0'),
            is_active=True
        )
        
        # Create disabled item
        self.item_disabled = Item.objects.create(
            platform='pasons',
            item_code='DISABLED001',
            description='Disabled Item',
            units='pcs',
            sku='SKU_DISABLED',
            wrap='9900',
            minimum_qty=10,
            weight_division_factor=Decimal('1.0'),
            is_active=True
        )
        
        # Enabled ItemOutlet
        self.io_enabled = ItemOutlet.objects.create(
            item=self.item_enabled,
            outlet=self.outlet,
            outlet_stock=20,  # > minimum_qty
            outlet_selling_price=Decimal('100.00'),
            is_active_in_outlet=True,  # ENABLED
            status_locked=False
        )
        
        # Disabled ItemOutlet (BLS status locked)
        self.io_disabled = ItemOutlet.objects.create(
            item=self.item_disabled,
            outlet=self.outlet,
            outlet_stock=20,  # > minimum_qty but disabled by lock
            outlet_selling_price=Decimal('200.00'),
            is_active_in_outlet=False,  # DISABLED
            status_locked=True
        )
    
    def test_export_includes_disabled_items_with_stock_status_zero(self):
        """Test: Disabled items export with stock_status=0"""
        export_service = ExportService(self.outlet, 'pasons')
        export_data, export_history = export_service.export(user=self.user, manual_export_type='full')
        
        # Should have 2 items
        self.assertEqual(len(export_data), 2, "Should export both enabled and disabled items")
        
        # Find items in export
        enabled_export = next((item for item in export_data if item['sku'] == 'SKU_ENABLED'), None)
        disabled_export = next((item for item in export_data if item['sku'] == 'SKU_DISABLED'), None)
        
        # Assertions
        self.assertIsNotNone(enabled_export, "Enabled item should be in export")
        self.assertIsNotNone(disabled_export, "Disabled item should be in export")
        
        self.assertEqual(enabled_export['stock_status'], 1, "Enabled item should have stock_status=1")
        self.assertEqual(disabled_export['stock_status'], 0, "Disabled item should have stock_status=0")
    
    def test_partial_export_includes_disabled_items_when_status_changes(self):
        """Test: Partial export includes items when status changes from enabled to disabled"""
        # First export (all items)
        export_service = ExportService(self.outlet, 'pasons')
        export_data1, _ = export_service.export(user=self.user, manual_export_type='full')
        
        # Change enabled item to disabled
        self.io_enabled.status_locked = True
        self.io_enabled.is_active_in_outlet = False
        self.io_enabled.save()
        
        # Partial export should include the changed item
        export_data2, _ = export_service.export(user=self.user, manual_export_type='partial')
        
        # Should include the item that changed status
        changed_item = next((item for item in export_data2 if item['sku'] == 'SKU_ENABLED'), None)
        self.assertIsNotNone(changed_item, "Changed item should be in partial export")
        self.assertEqual(changed_item['stock_status'], 0, "Changed item should now have stock_status=0")


class StockCalculationTestCase(TestCase):
    """Test calculate_outlet_enabled_status function"""
    
    def test_stock_zero_returns_disabled(self):
        """Test: Stock=0 → DISABLED"""
        item = Item(minimum_qty=10, wrap='9900')
        result = calculate_outlet_enabled_status(item, outlet_stock=0)
        self.assertFalse(result)
    
    def test_stock_below_minimum_returns_disabled(self):
        """Test: Stock < minimum_qty → DISABLED"""
        item = Item(minimum_qty=10, wrap='9900')
        result = calculate_outlet_enabled_status(item, outlet_stock=5)
        self.assertFalse(result)
    
    def test_stock_above_minimum_returns_enabled(self):
        """Test: Stock > minimum_qty → ENABLED"""
        item = Item(minimum_qty=10, wrap='9900')
        result = calculate_outlet_enabled_status(item, outlet_stock=20)
        self.assertTrue(result)
    
    def test_stock_equal_minimum_returns_disabled(self):
        """Test: Stock = minimum_qty → DISABLED (must be GREATER than)"""
        item = Item(minimum_qty=10, wrap='9900')
        result = calculate_outlet_enabled_status(item, outlet_stock=10)
        self.assertFalse(result)
