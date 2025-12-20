"""
Unit tests for Promotion Service

Tests cover:
1. Price calculation logic (Pasons/Talabat)
2. Wrap conversion (9900 vs 10000)
3. Cost margin validation (20% for Talabat)
4. Selling price difference validation (2 AED)
5. search_item function
6. save_promotion function
7. cancel_promotion function
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from integration.promotion_service import PromotionService
from integration.models import Item, ItemOutlet, Outlet


class PromotionServiceCalculationTests(TestCase):
    """Tests for calculate_promo_price function"""
    
    def test_pasons_regular_item_no_conversion(self):
        """Test Pasons regular item (10000) - no conversion"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='pasons',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('120.00')
        )
        
        self.assertEqual(result['converted_promo'], Decimal('100.00'))
        self.assertFalse(result['promo_adjusted'])
        self.assertFalse(result['is_wrap'])
    
    def test_pasons_wrap_item_with_wdf(self):
        """Test Pasons wrap item (9900) - price divided by wdf"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='pasons',
            item_code='99001234',
            wdf=Decimal('2.00'),
            talabat_margin=Decimal('17.00'),
            cost=Decimal('25.00'),
            selling_price=Decimal('60.00')
        )
        
        # 100 / 2 = 50
        self.assertEqual(result['converted_promo'], Decimal('50.00'))
        self.assertTrue(result['is_wrap'])
    
    def test_talabat_regular_item_with_margin(self):
        """Test Talabat regular item - adds margin"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='talabat',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('130.00')
        )
        
        # 100 * 1.15 = 115
        self.assertEqual(result['converted_promo'], Decimal('115.00'))
    
    def test_talabat_wrap_item_with_wdf_and_margin(self):
        """Test Talabat wrap item - divide by wdf then add margin"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='talabat',
            item_code='99001234',
            wdf=Decimal('2.00'),
            talabat_margin=Decimal('17.00'),
            cost=Decimal('25.00'),
            selling_price=Decimal('70.00')
        )
        
        # (100 / 2) * 1.17 = 50 * 1.17 = 58.50
        self.assertEqual(result['converted_promo'], Decimal('58.50'))
    
    def test_talabat_cost_margin_adjustment(self):
        """Test Talabat auto-adjusts if promo < cost + 20%"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('50.00'),
            platform='talabat',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),  # Min promo should be 50 * 1.20 = 60
            selling_price=Decimal('80.00')
        )
        
        # 50 * 1.15 = 57.50, but min is 60 (cost * 1.20)
        self.assertEqual(result['converted_promo'], Decimal('60.00'))
        self.assertTrue(result['promo_adjusted'])
        self.assertIsNotNone(result['margin_warning'])
    
    def test_selling_price_difference_adjustment_talabat(self):
        """Test Talabat auto-adjusts selling price if difference < 2 AED"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='talabat',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('116.00')  # Only 1 AED difference from 115
        )
        
        # Talabat: 100 * 1.15 = 115, selling should be adjusted to 115 + 2 = 117
        self.assertEqual(result['selling_price'], Decimal('117.00'))
        self.assertTrue(result['selling_adjusted'])
        self.assertIsNotNone(result['selling_warning'])
    
    def test_pasons_no_selling_price_adjustment(self):
        """Test Pasons has NO 2 AED rule - selling price stays same"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='pasons',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('101.00')  # Only 1 AED difference - but Pasons has no rule
        )
        
        # Pasons: No adjustment - selling price stays same
        self.assertEqual(result['selling_price'], Decimal('101.00'))
        self.assertFalse(result['selling_adjusted'])
    
    def test_no_adjustment_when_margins_ok(self):
        """Test no adjustment when all margins are OK"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='pasons',
            item_code='10001234',
            wdf=None,
            talabat_margin=Decimal('15.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('110.00')  # 10 AED difference is OK
        )
        
        self.assertFalse(result['promo_adjusted'])
        self.assertFalse(result['selling_adjusted'])
        self.assertEqual(result['selling_price'], Decimal('110.00'))
    
    def test_wrap_item_without_wdf_uses_direct_price(self):
        """Test wrap item without wdf uses direct price"""
        result = PromotionService.calculate_promo_price(
            promo_price=Decimal('100.00'),
            platform='pasons',
            item_code='99001234',
            wdf=None,  # No wdf set
            talabat_margin=Decimal('17.00'),
            cost=Decimal('50.00'),
            selling_price=Decimal('120.00')
        )
        
        # No conversion without wdf
        self.assertEqual(result['converted_promo'], Decimal('100.00'))


class PromotionServiceSearchItemTests(TestCase):
    """Tests for search_item function"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.outlet = Outlet.objects.create(
            name='Test Outlet',
            store_id='TEST001',
            location='Test Location',
            platforms='pasons',
            is_active=True
        )
        
        cls.item = Item.objects.create(
            platform='pasons',
            item_code='10001234',
            description='Test Item',
            units='PCS',
            sku='SKU001',
            weight_division_factor=Decimal('2.00'),
            talabat_margin=Decimal('15.00'),
            is_active=True
        )
        
        cls.item_outlet = ItemOutlet.objects.create(
            item=cls.item,
            outlet=cls.outlet,
            outlet_selling_price=Decimal('100.00'),
            outlet_cost=Decimal('50.00'),
            outlet_stock=10
        )
    
    def test_search_item_found(self):
        """Test search_item returns correct data when item exists"""
        result = PromotionService.search_item('10001234', 'PCS', 'pasons')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['item_code'], '10001234')
        self.assertEqual(result['units'], 'PCS')
        self.assertEqual(result['wdf'], Decimal('2.00'))
        self.assertEqual(result['current_selling_price'], Decimal('100.00'))
        self.assertEqual(result['current_cost'], Decimal('50.00'))
    
    def test_search_item_not_found(self):
        """Test search_item returns None when item doesn't exist"""
        result = PromotionService.search_item('NOTEXIST', 'PCS', 'pasons')
        
        self.assertIsNone(result)
    
    def test_search_item_wrong_platform(self):
        """Test search_item returns None for wrong platform"""
        result = PromotionService.search_item('10001234', 'PCS', 'talabat')
        
        self.assertIsNone(result)


class PromotionServiceSaveTests(TestCase):
    """Tests for save_promotion function"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.outlet = Outlet.objects.create(
            name='Test Outlet',
            store_id='TEST001',
            location='Test Location',
            platforms='pasons',
            is_active=True
        )
        
        cls.item = Item.objects.create(
            platform='pasons',
            item_code='10001234',
            description='Test Item',
            units='PCS',
            sku='SKU001',
            is_active=True
        )
        
        cls.item_outlet = ItemOutlet.objects.create(
            item=cls.item,
            outlet=cls.outlet,
            outlet_selling_price=Decimal('100.00'),
            outlet_cost=Decimal('50.00'),
            outlet_stock=10
        )
    
    def test_save_promotion_success(self):
        """Test saving promotion successfully for specific outlet"""
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=7)
        
        result = PromotionService.save_promotion(
            item_code='10001234',
            units='PCS',
            platform='pasons',
            outlet_id=self.outlet.id,
            promo_price=Decimal('80.00'),
            converted_promo=Decimal('80.00'),
            adjusted_selling=Decimal('100.00'),
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertTrue(result['success'])
        
        # Verify database was updated
        self.item_outlet.refresh_from_db()
        self.assertEqual(self.item_outlet.promo_price, Decimal('80.00'))
        self.assertEqual(self.item_outlet.converted_promo, Decimal('80.00'))
        self.assertTrue(self.item_outlet.is_on_promotion)
        self.assertEqual(self.item_outlet.original_selling_price, Decimal('100.00'))
    
    def test_save_promotion_item_not_found(self):
        """Test saving promotion for non-existent item"""
        result = PromotionService.save_promotion(
            item_code='NOTEXIST',
            units='PCS',
            platform='pasons',
            outlet_id=self.outlet.id,
            promo_price=Decimal('80.00'),
            converted_promo=Decimal('80.00'),
            adjusted_selling=Decimal('100.00'),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7)
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'Item not found')


class PromotionServiceCancelTests(TestCase):
    """Tests for cancel_promotion function"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.outlet = Outlet.objects.create(
            name='Test Outlet',
            store_id='TEST001',
            location='Test Location',
            platforms='pasons',
            is_active=True
        )
        
        cls.item = Item.objects.create(
            platform='pasons',
            item_code='10001234',
            description='Test Item',
            units='PCS',
            sku='SKU001',
            is_active=True
        )
    
    def test_cancel_promotion_success(self):
        """Test cancelling promotion successfully"""
        item_outlet = ItemOutlet.objects.create(
            item=self.item,
            outlet=self.outlet,
            outlet_selling_price=Decimal('80.00'),
            outlet_cost=Decimal('50.00'),
            outlet_stock=10,
            promo_price=Decimal('70.00'),
            converted_promo=Decimal('70.00'),
            original_selling_price=Decimal('100.00'),
            is_on_promotion=True
        )
        
        result = PromotionService.cancel_promotion(item_outlet.id)
        
        self.assertTrue(result['success'])
        
        # Verify database was updated
        item_outlet.refresh_from_db()
        self.assertEqual(item_outlet.outlet_selling_price, Decimal('100.00'))
        self.assertIsNone(item_outlet.promo_price)
        self.assertIsNone(item_outlet.converted_promo)
        self.assertFalse(item_outlet.is_on_promotion)
    
    def test_cancel_promotion_not_found(self):
        """Test cancelling non-existent promotion"""
        result = PromotionService.cancel_promotion(99999)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'Item outlet not found')


class PromotionServiceGetActiveTests(TestCase):
    """Tests for get_active_promotions function"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.outlet = Outlet.objects.create(
            name='Test Outlet',
            store_id='TEST001',
            location='Test Location',
            platforms='pasons',
            is_active=True
        )
        
        cls.item = Item.objects.create(
            platform='pasons',
            item_code='10001234',
            description='Test Item',
            units='PCS',
            sku='SKU001',
            is_active=True
        )
        
        cls.item_outlet = ItemOutlet.objects.create(
            item=cls.item,
            outlet=cls.outlet,
            outlet_selling_price=Decimal('80.00'),
            outlet_cost=Decimal('50.00'),
            outlet_stock=10,
            promo_price=Decimal('70.00'),
            converted_promo=Decimal('70.00'),
            original_selling_price=Decimal('100.00'),
            promo_start_date=datetime.now() - timedelta(days=1),
            promo_end_date=datetime.now() + timedelta(days=7),
            is_on_promotion=True
        )
    
    def test_get_active_promotions(self):
        """Test getting active promotions"""
        result = PromotionService.get_active_promotions()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_code'], '10001234')
        self.assertEqual(result[0]['promo_price'], Decimal('70.00'))
    
    def test_get_active_promotions_by_platform(self):
        """Test getting active promotions filtered by platform"""
        result = PromotionService.get_active_promotions(platform='pasons')
        
        self.assertEqual(len(result), 1)
        
        result = PromotionService.get_active_promotions(platform='talabat')
        
        self.assertEqual(len(result), 0)
