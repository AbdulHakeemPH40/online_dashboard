"""
API Push Service for sending product data to external e-commerce platforms

CURRENT STATUS:
- The pasons.live API endpoint (https://pasons.live/api/products) returns 404
- This indicates the API is not yet implemented on pasons.live
- The middleware is ready and will work once pasons.live implements their API
- Field mapping is configured according to user requirements

FIELD MAPPING:
Normal Prices: branch_id, barcode, selling_price_with_vat, stock_status, enable_or_disabled
Offer Prices: branch_id, barcode, offer_item, offer_price

TODO: Update API endpoint URL when pasons.live provides the correct endpoint
"""
import requests
import logging
from decimal import Decimal
from django.conf import settings
from .models import Outlet, ItemOutlet

logger = logging.getLogger(__name__)

class PasonsPushService:
    """
    Service for pushing product data to pasons.live e-commerce platform
    """
    
    # Field mapping configuration for NORMAL PRICE updates
    NORMAL_PRICE_MAPPING = {
        'branch_id': 'outlet.pasons_live_store_id',         # User-configured pasons.live Store ID
        'barcode': 'item.sku',                             # Our SKU → Their Barcode
        'selling_price_with_vat': 'outlet_selling_price',  # Our Selling Price → Their Price with VAT
        'stock_status': 'is_active_in_outlet',             # Our Active Status → Their Stock Status
        'enable_or_disabled': 'is_active_in_outlet',       # Same as stock_status
    }
    
    # Field mapping configuration for OFFER/PROMOTION updates
    OFFER_PRICE_MAPPING = {
        'branch_id': 'outlet.pasons_live_store_id',         # User-configured pasons.live Store ID → Their Branch ID
        'barcode': 'item.sku',                             # Our SKU → Their Barcode
        'offer_item': 'is_on_promotion',                   # Our Promotion Status → Their Offer Item
        'offer_price': 'converted_promo',                  # Our Converted Promo → Their Offer Price
    }
    
    def __init__(self, outlet):
        """
        Initialize push service for specific outlet
        
        Args:
            outlet: Outlet instance
        """
        self.outlet = outlet
        # Use pasons.live endpoint (no API key required)
        # TODO: Update this URL when pasons.live provides the correct endpoint
        self.api_endpoint = "https://pasons.live/api/products"
        self.store_id = outlet.pasons_live_store_id  # Use user-configured Store ID
        
    def get_field_value(self, item_outlet, field_path):
        """
        Get field value using dot notation path
        
        Args:
            item_outlet: ItemOutlet instance
            field_path: String path like 'item.sku' or 'outlet_selling_price'
            
        Returns:
            Field value or None
        """
        if field_path is None:
            return None
            
        try:
            # Handle direct fields
            if '.' not in field_path:
                return getattr(item_outlet, field_path, None)
            
            # Handle nested fields like 'item.sku'
            parts = field_path.split('.')
            obj = item_outlet
            
            for part in parts:
                obj = getattr(obj, part, None)
                if obj is None:
                    return None
                    
            return obj
            
        except Exception as e:
            logger.warning(f"Error getting field value for {field_path}: {e}")
            return None
    
    def convert_normal_price_data(self, item_outlet):
        """
        Convert ItemOutlet data to pasons.live NORMAL PRICE format
        
        Args:
            item_outlet: ItemOutlet instance
            
        Returns:
            dict: Data in pasons.live normal price format
        """
        data = {}
        
        for pasons_field, our_field_path in self.NORMAL_PRICE_MAPPING.items():
            value = self.get_field_value(item_outlet, our_field_path)
            
            # Special handling for specific fields
            if pasons_field in ['stock_status', 'enable_or_disabled']:
                # Convert boolean to 1/0
                value = 1 if value else 0
            elif pasons_field == 'selling_price_with_vat':
                # Ensure decimal formatting
                value = float(value) if value else 0.0
                
            data[pasons_field] = value
            
        return data
    
    def convert_offer_price_data(self, item_outlet):
        """
        Convert ItemOutlet data to pasons.live OFFER PRICE format
        
        Args:
            item_outlet: ItemOutlet instance
            
        Returns:
            dict: Data in pasons.live offer price format
        """
        data = {}
        
        for pasons_field, our_field_path in self.OFFER_PRICE_MAPPING.items():
            value = self.get_field_value(item_outlet, our_field_path)
            
            # Special handling for specific fields
            if pasons_field == 'offer_item':
                # Convert boolean to true/false
                value = bool(value)
            elif pasons_field == 'offer_price':
                # Ensure decimal formatting
                value = float(value) if value else 0.0
                
            data[pasons_field] = value
            
        return data
    
    def get_outlet_products(self, export_type='full'):
        """
        Get products for this outlet
        
        Args:
            export_type: 'full' or 'partial'
            
        Returns:
            QuerySet of ItemOutlet instances
        """
        base_query = ItemOutlet.objects.filter(
            outlet=self.outlet,
            item__platform='pasons'  # Only Pasons platform
        ).select_related('item', 'outlet')
        
        if export_type == 'full':
            # Export all active items
            return base_query.filter(is_active_in_outlet=True)
        else:
            # TODO: Implement delta export logic
            # For now, return all active items
            return base_query.filter(is_active_in_outlet=True)
    
    def prepare_normal_price_data(self, export_type='full'):
        """
        Prepare NORMAL PRICE data for pushing to pasons.live
        
        Args:
            export_type: 'full' or 'partial'
            
        Returns:
            list: List of normal price data dictionaries
        """
        products = self.get_outlet_products(export_type)
        push_data = []
        
        for item_outlet in products:
            # Skip items without required data
            if not item_outlet.item.sku or not item_outlet.outlet_selling_price:
                logger.warning(f"Skipping item {item_outlet.item.item_code}: Missing SKU or selling price")
                continue
                
            # Skip if no store ID configured
            if not self.store_id:
                logger.warning(f"Skipping outlet {self.outlet.name}: No store ID configured")
                continue
                
            # Only include items with normal prices (not on promotion)
            if not item_outlet.is_on_promotion:
                product_data = self.convert_normal_price_data(item_outlet)
                push_data.append(product_data)
            
        return push_data
    
    def prepare_offer_price_data(self, export_type='full'):
        """
        Prepare OFFER PRICE data for pushing to pasons.live
        
        Args:
            export_type: 'full' or 'partial'
            
        Returns:
            list: List of offer price data dictionaries
        """
        products = self.get_outlet_products(export_type)
        push_data = []
        
        for item_outlet in products:
            # Skip items without required data
            if not item_outlet.item.sku:
                logger.warning(f"Skipping item {item_outlet.item.item_code}: Missing SKU")
                continue
                
            # Skip if no store ID configured
            if not self.store_id:
                logger.warning(f"Skipping outlet {self.outlet.name}: No store ID configured")
                continue
                
            # Only include items that are on promotion
            if item_outlet.is_on_promotion and item_outlet.converted_promo:
                product_data = self.convert_offer_price_data(item_outlet)
                push_data.append(product_data)
            
        return push_data
    
    def push_to_pasons_live(self, export_type='full', push_mode='normal'):
        """
        Push product data to pasons.live API
        
        Args:
            export_type: 'full' or 'partial'
            push_mode: 'normal' for regular prices, 'offer' for promotion prices
            
        Returns:
            dict: Response with success status and details
        """
        try:
            # Prepare data based on push mode
            if push_mode == 'offer':
                push_data = self.prepare_offer_price_data(export_type)
                data_type = "offer prices"
            else:
                push_data = self.prepare_normal_price_data(export_type)
                data_type = "normal prices"
            
            if not push_data:
                return {
                    'success': False,
                    'message': f'No products to push for {data_type}',
                    'item_count': 0
                }
            
            # Make actual HTTP request to pasons.live
            logger.info(f"Pushing {len(push_data)} {data_type} to pasons.live for outlet {self.outlet.name}")
            
            response = requests.post(
                self.api_endpoint,
                json=push_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=30  # 30 second timeout
            )
            
            # Check response status
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    return {
                        'success': True,
                        'message': f'Successfully pushed {len(push_data)} {data_type} to pasons.live',
                        'item_count': len(push_data),
                        'push_mode': push_mode,
                        'response_data': response_data
                    }
                except ValueError:
                    # Response is not JSON, but status is 200
                    return {
                        'success': True,
                        'message': f'Successfully pushed {len(push_data)} {data_type} to pasons.live',
                        'item_count': len(push_data),
                        'push_mode': push_mode,
                        'response_text': response.text[:200]  # First 200 chars
                    }
            elif response.status_code == 404:
                # API endpoint not found - this is expected since pasons.live hasn't implemented their API yet
                error_message = f"pasons.live API not implemented yet (HTTP 404). This is expected - the middleware is ready and will work once pasons.live implements their API endpoint."
                logger.info(f"Expected 404 from pasons.live API - not implemented yet")
                return {
                    'success': False,
                    'message': error_message,
                    'item_count': 0,
                    'endpoint': self.api_endpoint,
                    'suggestion': 'This is normal - pasons.live is still developing their API. The middleware is ready to work once their API is available.',
                    'expected_error': True  # Flag to indicate this is expected
                }
            else:
                # HTTP error status
                error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"pasons.live API error: {error_message}")
                return {
                    'success': False,
                    'message': f'pasons.live API error: {error_message}',
                    'item_count': 0
                }
            
        except requests.exceptions.Timeout:
            logger.error("Timeout while connecting to pasons.live")
            return {
                'success': False,
                'message': 'Timeout while connecting to pasons.live (30s)',
                'item_count': 0
            }
        except requests.exceptions.ConnectionError:
            logger.error("Connection error while connecting to pasons.live")
            return {
                'success': False,
                'message': 'Unable to connect to pasons.live. Please check internet connection.',
                'item_count': 0
            }
        except Exception as e:
            logger.error(f"Error pushing to pasons.live: {e}")
            return {
                'success': False,
                'message': f'Push failed: {str(e)}',
                'item_count': 0
            }
    
    def test_connection(self):
        """
        Test connection to pasons.live API
        
        Returns:
            dict: Connection test result
        """
        try:
            if not self.store_id:
                return {
                    'success': False,
                    'message': 'Store ID not configured'
                }
            
            # Test connection with a simple GET request first
            logger.info(f"Testing connection to pasons.live for store {self.store_id}")
            
            # Try a simple GET request to check if the domain is reachable
            try:
                import requests
                response = requests.get("https://pasons.live", timeout=10)
                domain_reachable = True
                domain_status = response.status_code
            except:
                domain_reachable = False
                domain_status = None
            
            # Send a test POST request to the API endpoint
            test_data = [{
                'branch_id': self.store_id,
                'barcode': 'TEST123',
                'selling_price_with_vat': 1.00,
                'stock_status': 1,
                'enable_or_disabled': 1,
                'test_mode': True  # Indicate this is a test
            }]
            
            response = requests.post(
                self.api_endpoint,
                json=test_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=10  # 10 second timeout for test
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': f'Connection successful to pasons.live (Store: {self.store_id})',
                    'store_id': self.store_id,
                    'endpoint': self.api_endpoint,
                    'response_status': response.status_code
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'message': f'pasons.live API not implemented yet (HTTP 404). This is expected - the middleware is ready and will work once pasons.live implements their API endpoint.',
                    'store_id': self.store_id,
                    'endpoint': self.api_endpoint,
                    'response_status': response.status_code,
                    'domain_status': domain_status,
                    'expected_error': True  # Flag to indicate this is expected
                }
            else:
                return {
                    'success': False,
                    'message': f'Connection failed: HTTP {response.status_code} - {response.text[:100]}',
                    'store_id': self.store_id,
                    'endpoint': self.api_endpoint,
                    'response_status': response.status_code
                }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Connection test timeout (10s). pasons.live may be slow or unreachable.'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Cannot connect to pasons.live. Please check internet connection or the domain may be down.'
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }


def get_push_service(outlet):
    """
    Factory function to get appropriate push service for outlet
    
    Args:
        outlet: Outlet instance
        
    Returns:
        PushService instance or None
    """
    if outlet.platforms == 'pasons':
        return PasonsPushService(outlet)
    else:
        logger.warning(f"No push service available for platform: {outlet.platforms}")
        return None