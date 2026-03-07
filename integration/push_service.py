"""
API Push Service for sending product data to pasons.live e-commerce platform

AUTHENTICATION:
- OAuth2 Client Credentials flow
- Token endpoint: POST https://pasons.live/oauth/token
- Access token type: Bearer (JWT)
- Token expiry: 3600 seconds (1 hour)
- Refresh token: Automatically refresh when token expires
- Rate limit: 10 requests per minute for token, 100 requests per minute for bulk operations

API ENDPOINTS:
1. Get/Refresh Token: POST /oauth/token
2. Bulk Update Price & Stock: POST /api/v1/bulk-update/price-stock
3. Schedule Bulk Update: POST /api/v1/bulk-update/schedule
4. Update Offers: POST /api/v1/bulk-update/offers
5. Get Batch Status: GET /api/v1/bulk-update/status/{batchId}
6. Get Batch Logs: GET /api/v1/bulk-update/logs/{batchId}
7. Last Sync Time: GET /api/v1/bulk-update/last-sync/{storeId}

FIELD MAPPING:
Price-Stock: product_code, selling_price, mrp, stock, enabled
Offers: product_code, offer_price
"""
import os
import requests
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from decouple import config
from django.conf import settings
from django.utils import timezone
from .models import Outlet, ItemOutlet

logger = logging.getLogger(__name__)

class PasonsPushService:
    """
    Service for pushing product data to pasons.live e-commerce platform via OAuth2
    
    AUTHENTICATION FLOW:
    1. Exchange Client ID + Secret for access token via OAuth2 token endpoint
    2. Store access token + refresh token in Outlet model
    3. Use Bearer token for all API requests
    4. Automatically refresh token before expiry
    
    API ENDPOINTS:
    - Token: https://pasons.live/oauth/token
    - Bulk Update: https://pasons.live/api/v1/bulk-update
    """
    
    # OAuth2 endpoints - configurable via .env
    # Default: https://pasons.live:9898/oauth/token (verified working)
    OAUTH_TOKEN_ENDPOINT = config('PASONS_OAUTH_URL', default='https://pasons.live:9898/oauth/token')
    API_BASE_URL = config('PASONS_API_URL', default='https://pasons.live:9898/api/v1')
    
    # API endpoints
    BULK_UPDATE_PRICE_STOCK_ENDPOINT = f"{API_BASE_URL}/bulk-update/price-stock"
    BULK_UPDATE_SCHEDULE_ENDPOINT = f"{API_BASE_URL}/bulk-update/schedule"
    BULK_UPDATE_OFFERS_ENDPOINT = f"{API_BASE_URL}/bulk-update/offers"
    BULK_UPDATE_STATUS_ENDPOINT = f"{API_BASE_URL}/bulk-update/status"
    BULK_UPDATE_LOGS_ENDPOINT = f"{API_BASE_URL}/bulk-update/logs"
    BULK_UPDATE_LAST_SYNC_ENDPOINT = f"{API_BASE_URL}/bulk-update/last-sync"
    
    # OAuth2 scopes required for API access
    OAUTH_SCOPES = "update:prices update:stock update:enabled"
    
    # Field mapping configuration for PRICE-STOCK updates (POST /api/v1/bulk-update/price-stock)
    PRICE_STOCK_MAPPING = {
        'product_code': 'item.sku',                    # SKU = unique product identifier for pasons.live
        'selling_price': 'outlet_selling_price',        # Our Selling Price
        'mrp': 'outlet_mrp',                           # Our MRP
        'stock': 'is_active_in_outlet',                # Optimized: Push 1/0 based on active status instead of real stock
        'enabled': 'is_active_in_outlet',              # Active status (1=enabled, 0=disabled)
    }
    
    # Field mapping configuration for OFFER updates (POST /api/v1/bulk-update/offers)
    OFFER_MAPPING = {
        'product_code': 'item.sku',                    # SKU = unique product identifier for pasons.live
        'offer_price': 'converted_promo',               # Our Promotional Price (after conversion)
    }
    
    def __init__(self, outlet):
        """
        Initialize push service for specific outlet.
        OAuth2 credentials are loaded from .env file (not stored in DB).
        """
        self.outlet = outlet
        self.store_id = outlet.pasons_live_store_id
        # Read from .env — same credentials for all Pasons outlets
        self.client_id = config('PASONS_CLIENT_ID', default=None)
        self.client_secret = config('PASONS_CLIENT_SECRET', default=None)
        
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
    
    def get_valid_access_token(self):
        """
        Get a valid OAuth2 access token, refreshing if necessary.
        
        Returns:
            str: Valid Bearer token (JWT)
            
        Raises:
            ValueError: If unable to obtain access token
        """
        # Check if current token exists and is still valid
        if (self.outlet.pasons_access_token and 
            self.outlet.pasons_token_expires_at and
            timezone.now() < self.outlet.pasons_token_expires_at - timedelta(minutes=5)):
            # Token is still valid (with 5-minute buffer)
            return self.outlet.pasons_access_token
        
        # Token is expired or missing - refresh it
        if self.outlet.pasons_refresh_token:
            return self._refresh_access_token()
        else:
            # No refresh token, get new token using client credentials
            return self._get_new_access_token()
    
    def _get_new_access_token(self):
        """
        Get a new OAuth2 access token using Client Credentials flow.
        
        Returns:
            str: Access token
            
        Raises:
            ValueError: If token request fails
        """
        if not self.client_id or not self.client_secret:
            raise ValueError(f"OAuth2 credentials not configured for outlet {self.outlet.name}")
        
        try:
            response = requests.post(
                self.OAUTH_TOKEN_ENDPOINT,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'scope': self.OAUTH_SCOPES
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code != 200:
                error_msg = f"OAuth2 token request failed: HTTP {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            token_data = response.json()
            
            # Extract token info
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
            
            if not access_token:
                raise ValueError("No access_token in OAuth2 response")
            
            # Calculate expiry time
            expires_at = timezone.now() + timedelta(seconds=expires_in)
            
            # Store tokens in Outlet model
            self.outlet.pasons_access_token = access_token
            if refresh_token:
                self.outlet.pasons_refresh_token = refresh_token
            self.outlet.pasons_token_expires_at = expires_at
            self.outlet.save(update_fields=[
                'pasons_access_token', 
                'pasons_refresh_token', 
                'pasons_token_expires_at'
            ])
            
            logger.info(f"OAuth2 token obtained for outlet {self.outlet.name}, expires at {expires_at}")
            return access_token
            
        except requests.exceptions.RequestException as e:
            error_msg = f"OAuth2 token request error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _refresh_access_token(self):
        """
        Refresh OAuth2 access token using refresh token.
        
        Returns:
            str: New access token
            
        Raises:
            ValueError: If refresh fails
        """
        if not self.outlet.pasons_refresh_token:
            raise ValueError("No refresh token available")
        
        try:
            response = requests.post(
                self.OAUTH_TOKEN_ENDPOINT,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.outlet.pasons_refresh_token,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code != 200:
                error_msg = f"OAuth2 token refresh failed: HTTP {response.status_code}"
                logger.error(error_msg)
                # Fall back to getting new token
                return self._get_new_access_token()
            
            token_data = response.json()
            
            # Extract new token info
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token', self.outlet.pasons_refresh_token)
            expires_in = token_data.get('expires_in', 3600)
            
            if not access_token:
                raise ValueError("No access_token in refresh response")
            
            # Calculate expiry time
            expires_at = timezone.now() + timedelta(seconds=expires_in)
            
            # Store new tokens
            self.outlet.pasons_access_token = access_token
            self.outlet.pasons_refresh_token = refresh_token
            self.outlet.pasons_token_expires_at = expires_at
            self.outlet.save(update_fields=[
                'pasons_access_token',
                'pasons_refresh_token',
                'pasons_token_expires_at'
            ])
            
            logger.info(f"OAuth2 token refreshed for outlet {self.outlet.name}")
            return access_token
            
        except requests.exceptions.RequestException as e:
            error_msg = f"OAuth2 token refresh error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    def convert_price_stock_data(self, item_outlet):
        """
        Convert ItemOutlet data to pasons.live PRICE-STOCK format
        Endpoint: POST /api/v1/bulk-update/price-stock
        
        Args:
            item_outlet: ItemOutlet instance
            
        Returns:
            dict: Data in pasons.live price-stock format
        """
        data = {}
        
        for pasons_field, our_field_path in self.PRICE_STOCK_MAPPING.items():
            value = self.get_field_value(item_outlet, our_field_path)
            
            # Special handling for specific fields
            if pasons_field == 'enabled':
                # API expects integer 1/0
                value = 1 if value else 0
            elif pasons_field in ('selling_price', 'mrp'):
                # Ensure decimal formatting
                value = float(value) if value else 0.0
            elif pasons_field == 'stock':
                value = int(value) if value else 0
                
            data[pasons_field] = value
            
        return data
    
    def convert_offer_data(self, item_outlet):
        """
        Convert ItemOutlet data to pasons.live OFFER format
        Endpoint: POST /api/v1/bulk-update/offers
        
        Args:
            item_outlet: ItemOutlet instance
            
        Returns:
            dict: Data in pasons.live offer format
        """
        data = {}
        
        for pasons_field, our_field_path in self.OFFER_MAPPING.items():
            value = self.get_field_value(item_outlet, our_field_path)
            
            # Special handling for specific fields
            if pasons_field == 'offer_price':
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
            # Full: ALL items (active AND inactive) that have a price
            return base_query.filter(
                outlet_selling_price__isnull=False
            )
        else:
            # Partial: Only items where price or stock CHANGED since last export
            # (Same logic as CSV export)
            from decimal import Decimal
            
            # Get the latest successful export for this outlet and platform
            from .models import ExportHistory
            last_export = ExportHistory.objects.filter(
                outlet=self.outlet,
                platform='pasons',
                status='success'
            ).order_by('-export_timestamp').first()
            
            if not last_export:
                # No prior export - return recent items as fallback
                from django.utils import timezone
                two_hours_ago = timezone.now() - timezone.timedelta(hours=2)
                logger.info(f"Partial push: No prior export found, using last 2 hours")
                return base_query.filter(
                    is_active_in_outlet=True,
                    updated_at__gt=two_hours_ago
                )
            
            # Compare current values vs last exported values
            all_items = base_query.filter(outlet_selling_price__isnull=False)
            
            changed_items = []
            for io in all_items:
                current_price = io.outlet_selling_price or Decimal('0')
                exported_price = io.export_selling_price or Decimal('0')
                
                # Check if price changed or was never exported
                price_changed = current_price != exported_price
                never_exported = io.export_selling_price is None
                
                if price_changed or never_exported:
                    changed_items.append(io.id)
            
            logger.info(f"Partial push: Found {len(changed_items)} items with changed prices")
            return base_query.filter(id__in=changed_items)
    
    def prepare_price_stock_data(self, export_type='full', items=None):
        """
        Prepare PRICE-STOCK data for pushing to pasons.live
        Endpoint: POST /api/v1/bulk-update/price-stock
        
        Args:
            export_type: 'full' or 'partial'
            items: Optional pre-filtered list/queryset of items. If provided, skips DB query.
            
        Returns:
            list: List of price-stock item dictionaries
        """
        products = items if items is not None else self.get_outlet_products(export_type)
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
                product_data = self.convert_price_stock_data(item_outlet)
                push_data.append(product_data)
            
        return push_data
    
    def prepare_offer_data(self, export_type='full'):
        """
        Prepare OFFER data for pushing to pasons.live
        Endpoint: POST /api/v1/bulk-update/offers
        
        Args:
            export_type: 'full' or 'partial'
            
        Returns:
            list: List of offer item dictionaries
        """
        products = self.get_outlet_products(export_type)
        push_data = []
        
        for item_outlet in products:
            # Skip items without required data
            if not item_outlet.item.sku:
                logger.warning(f"Skipping item {item_outlet.item.item_code}: Missing SKU")
                continue
                
            # Only include items that are on promotion with valid promo price
            if item_outlet.is_on_promotion and item_outlet.converted_promo:
                product_data = self.convert_offer_data(item_outlet)
                push_data.append(product_data)
            
        return push_data
    
    def push_to_pasons_live(self, export_type='full', push_mode='normal', items=None):
        """
        Push product data to pasons.live API via OAuth2
        
        Args:
            export_type: 'full' or 'partial'
            push_mode: 'normal' for price-stock, 'offer' for promotions
            items: Optional pre-filtered items list to optimize processing speed
            
        Returns:
            dict: Response with success status, batch_id, and details
        """
        try:
            # Prepare data based on push mode
            if push_mode == 'offer':
                # Offers don't currently support passing precomputed items, fallback to full recalculation
                push_data = self.prepare_offer_data(export_type)
                data_type = "offers"
                endpoint = self.BULK_UPDATE_OFFERS_ENDPOINT
            else:
                push_data = self.prepare_price_stock_data(export_type, items=items)
                data_type = "price-stock"
                endpoint = self.BULK_UPDATE_PRICE_STOCK_ENDPOINT
            
            if not push_data:
                return {
                    'success': False,
                    'message': f'No products to push for {data_type}',
                    'item_count': 0
                }
            
            # Validate store_id
            if not self.store_id:
                return {
                    'success': False,
                    'message': 'Pasons.live Store ID not configured for this outlet.',
                    'item_count': 0
                }
            
            # Get valid OAuth2 access token
            try:
                access_token = self.get_valid_access_token()
            except ValueError as e:
                logger.error(f"Failed to get OAuth2 token: {str(e)}")
                return {
                    'success': False,
                    'message': f'OAuth2 authentication failed: {str(e)}',
                    'item_count': 0
                }
            
            # Dynamic timeout based on item count
            # Base: 30s for up to 1000 items, add 10s per 1000 items, max 120s
            item_count = len(push_data)
            dynamic_timeout = min(120, max(30, 30 + (item_count // 1000) * 10))
            
            # For very large datasets, use batching
            BATCH_SIZE = 1000  # Push in batches of 1000
            
            if item_count > BATCH_SIZE:
                # Split into batches
                batches = [push_data[i:i + BATCH_SIZE] for i in range(0, item_count, BATCH_SIZE)]
                logger.info(f"Large dataset detected: {item_count} items, splitting into {len(batches)} batches")
                
                all_results = []
                total_success = 0
                total_failed = 0
                failed_items = []
                
                for batch_idx, batch in enumerate(batches):
                    logger.info(f"Pushing batch {batch_idx + 1}/{len(batches)} ({len(batch)} items)")
                    
                    # Build batch payload
                    if push_mode == 'offer':
                        payload = {
                            'offer_id': self.store_id,
                            'items': batch
                        }
                    else:
                        payload = {
                            'store_id': int(self.store_id) if self.store_id.isdigit() else self.store_id,
                            'items': batch
                        }
                    
                    response = requests.post(
                        endpoint,
                        json=payload,
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Bearer {access_token}',
                            'User-Agent': 'Pasons-ERP-Middleware/1.0'
                        },
                        timeout=dynamic_timeout
                    )
                    
                    try:
                        response_data = response.json()
                    except ValueError:
                        response_data = {}
                    
                    if response.status_code == 200 and response_data.get('status') == '1':
                        batch_success = int(response_data.get('success_count') or len(batch))
                        batch_failed = int(response_data.get('failed_count')) if response_data.get('failed_count') is not None else 0
                        total_success += batch_success
                        total_failed += batch_failed
                        
                        if response_data.get('failed_items'):
                            failed_items.extend(response_data.get('failed_items', []))
                    else:
                        # Batch failed, add all items as failed
                        total_failed += len(batch)
                        failed_items.extend([{'product_code': item.get('product_code'), 'error': 'Batch failed'} for item in batch])
                    
                    # Small delay between batches to respect rate limits (Pasons: 100 req/min)
                    import time
                    time.sleep(1)  # 1 second between batches
                
                # Return combined result
                batch_id = f"batched-{len(batches)}-batches"
                return {
                    'success': total_failed == 0,
                    'message': f'Pushed {item_count} items in {len(batches)} batches. Success: {total_success}, Failed: {total_failed}',
                    'item_count': item_count,
                    'success_count': total_success,
                    'failed_count': total_failed,
                    'batch_id': batch_id,
                    'push_mode': push_mode,
                    'failed_items': failed_items[:50] if failed_items else []  # Limit failed items in response
                }
            
            # Single push (no batching needed)
            # Build request payload per API spec
            if push_mode == 'offer':
                # Offers endpoint uses offer_id and items array
                payload = {
                    'offer_id': self.store_id,  # Using store_id as offer_id
                    'items': push_data
                }
            else:
                # Price-Stock endpoint uses store_id and items array
                payload = {
                    'store_id': int(self.store_id) if self.store_id.isdigit() else self.store_id,
                    'items': push_data
                }
            
            # Make API request to pasons.live bulk update endpoint
            logger.info(f"Pushing {len(push_data)} {data_type} to pasons.live for outlet {self.outlet.name} (timeout: {dynamic_timeout}s)")
            
            response = requests.post(
                endpoint,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=dynamic_timeout
            )
            
            # Parse response - API returns {"status": "1", "data": {...}} on success
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}
            
            # Check response status
            if response.status_code == 200:
                # Check if API indicates success (status: "1")
                if response_data.get('status') == '1':
                    # API returns batch_id at root level, not in data
                    batch_id = response_data.get('batch_id', 'unknown')
                    # Get success/failed counts from response
                    success_count = response_data.get('success_count')
                    failed_count = response_data.get('failed_count') if response_data.get('failed_count') is not None else 0
                    failed_items_list = response_data.get('failed_items', [])
                    
                    return {
                        'success': True,
                        'message': f'Successfully queued {len(push_data)} {data_type} for processing',
                        'item_count': len(push_data),
                        'success_count': success_count or len(push_data),
                        'failed_count': failed_count,
                        'batch_id': batch_id,
                        'push_mode': push_mode,
                        'failed_items': failed_items_list[:50] if failed_items_list else [],
                        'response_data': response_data
                    }
                else:
                    # API returned 200 but status is not "1"
                    error_msg = response_data.get('message', response_data.get('error', 'Unknown error'))
                    return {
                        'success': False,
                        'message': f'API error: {error_msg}',
                        'item_count': 0,
                        'response_data': response_data
                    }
            elif response.status_code == 401:
                logger.error(f"OAuth2 authorization failed: HTTP 401")
                return {
                    'success': False,
                    'message': 'OAuth2 authorization failed. Please check your credentials.',
                    'item_count': 0
                }
            elif response.status_code == 400:
                error_msg = response_data.get('message', response_data.get('error', response.text[:200]))
                logger.error(f"API validation error: {error_msg}")
                return {
                    'success': False,
                    'message': f'API validation error: {error_msg}',
                    'item_count': 0,
                    'response_data': response_data
                }
            else:
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
    
    def get_batch_status(self, batch_id):
        """
        Get the status of a bulk update batch
        Endpoint: GET /api/v1/bulk-update/status/{batchId}
        
        Args:
            batch_id: The batch ID returned from push operation
            
        Returns:
            dict: Batch status details
        """
        try:
            access_token = self.get_valid_access_token()
        except ValueError as e:
            return {
                'success': False,
                'message': f'OAuth2 authentication failed: {str(e)}'
            }
        
        try:
            url = f"{self.BULK_UPDATE_STATUS_ENDPOINT}/{batch_id}"
            response = requests.get(
                url,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=15
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == '1':
                    return {
                        'success': True,
                        'batch_data': response_data.get('data', {})
                    }
                return {
                    'success': False,
                    'message': response_data.get('message', 'Failed to get batch status')
                }
            return {
                'success': False,
                'message': f'HTTP {response.status_code}: {response.text[:200]}'
            }
        except Exception as e:
            logger.error(f"Error getting batch status: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_batch_logs(self, batch_id, status=None, product_code=None, per_page=100):
        """
        Get logs for a bulk update batch
        Endpoint: GET /api/v1/bulk-update/logs/{batchId}
        
        Args:
            batch_id: The batch ID returned from push operation
            status: Filter by 'success', 'failed', 'skipped'
            product_code: Filter by specific product code
            per_page: Items per page (default 100)
            
        Returns:
            dict: Batch logs
        """
        try:
            access_token = self.get_valid_access_token()
        except ValueError as e:
            return {
                'success': False,
                'message': f'OAuth2 authentication failed: {str(e)}'
            }
        
        try:
            url = f"{self.BULK_UPDATE_LOGS_ENDPOINT}/{batch_id}"
            params = {'per_page': per_page}
            if status:
                params['status'] = status
            if product_code:
                params['product_code'] = product_code
            
            response = requests.get(
                url,
                params=params,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=15
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == '1':
                    return {
                        'success': True,
                        'logs_data': response_data.get('data', {})
                    }
                return {
                    'success': False,
                    'message': response_data.get('message', 'Failed to get batch logs')
                }
            return {
                'success': False,
                'message': f'HTTP {response.status_code}: {response.text[:200]}'
            }
        except Exception as e:
            logger.error(f"Error getting batch logs: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_last_sync(self):
        """
        Get last sync time for the store
        Endpoint: GET /api/v1/bulk-update/last-sync/{storeId}
        
        Returns:
            dict: Last sync information
        """
        try:
            access_token = self.get_valid_access_token()
        except ValueError as e:
            return {
                'success': False,
                'message': f'OAuth2 authentication failed: {str(e)}'
            }
        
        if not self.store_id:
            return {
                'success': False,
                'message': 'Store ID not configured'
            }
        
        try:
            url = f"{self.BULK_UPDATE_LAST_SYNC_ENDPOINT}/{self.store_id}"
            response = requests.get(
                url,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=15
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == '1':
                    return {
                        'success': True,
                        'sync_data': response_data
                    }
                return {
                    'success': False,
                    'message': response_data.get('message', 'Failed to get last sync')
                }
            return {
                'success': False,
                'message': f'HTTP {response.status_code}: {response.text[:200]}'
            }
        except Exception as e:
            logger.error(f"Error getting last sync: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def schedule_bulk_update(self, export_type='full', scheduled_at=None):
        """
        Schedule a bulk update for future execution
        Endpoint: POST /api/v1/bulk-update/schedule
        
        Args:
            export_type: 'full' or 'partial'
            scheduled_at: ISO format datetime string (e.g., "2026-03-01T02:00:00Z")
            
        Returns:
            dict: Response with batch_id and details
        """
        try:
            push_data = self.prepare_price_stock_data(export_type)
            
            if not push_data:
                return {
                    'success': False,
                    'message': 'No products to schedule',
                    'item_count': 0
                }
            
            if not self.store_id:
                return {
                    'success': False,
                    'message': 'Store ID not configured',
                    'item_count': 0
                }
            
            try:
                access_token = self.get_valid_access_token()
            except ValueError as e:
                return {
                    'success': False,
                    'message': f'OAuth2 authentication failed: {str(e)}',
                    'item_count': 0
                }
            
            payload = {
                'store_id': int(self.store_id) if self.store_id.isdigit() else self.store_id,
                'items': push_data
            }
            
            if scheduled_at:
                payload['scheduled_at'] = scheduled_at
            
            logger.info(f"Scheduling {len(push_data)} items for outlet {self.outlet.name} at {scheduled_at}")
            
            response = requests.post(
                self.BULK_UPDATE_SCHEDULE_ENDPOINT,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': 'Pasons-ERP-Middleware/1.0'
                },
                timeout=30
            )
            
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}
            
            if response.status_code == 200 and response_data.get('status') == '1':
                batch_id = response_data.get('data', {}).get('batch_id', 'unknown')
                return {
                    'success': True,
                    'message': f'Successfully scheduled {len(push_data)} items',
                    'item_count': len(push_data),
                    'batch_id': batch_id,
                    'scheduled_at': scheduled_at,
                    'response_data': response_data
                }
            elif response.status_code == 401:
                return {
                    'success': False,
                    'message': 'OAuth2 authorization failed',
                    'item_count': 0
                }
            else:
                error_msg = response_data.get('message', response.text[:200])
                return {
                    'success': False,
                    'message': f'Schedule failed: {error_msg}',
                    'item_count': 0
                }
        except Exception as e:
            logger.error(f"Error scheduling bulk update: {e}")
            return {
                'success': False,
                'message': f'Schedule failed: {str(e)}',
                'item_count': 0
            }
    
    def test_connection(self):
        """
        Test OAuth2 authentication and connectivity to pasons.live API.
        Steps:
          1. Check credentials are set in .env
          2. Check store_id is configured
          3. Try to obtain OAuth2 access token
          4. Report result with clear status
        """
        # Step 1 — Check credentials from .env
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'message': 'OAuth2 credentials not found in .env. Add PASONS_CLIENT_ID and PASONS_CLIENT_SECRET to your .env file.',
                'step': 'credentials_check'
            }

        # Step 2 — Check store_id
        if not self.store_id:
            return {
                'success': False,
                'message': 'Pasons.live Store ID not configured for this outlet.',
                'step': 'store_id_check'
            }

        # Step 3 — Try OAuth2 token request
        try:
            logger.info(f"Testing OAuth2 connection for store {self.store_id}")
            token_response = requests.post(
                self.OAUTH_TOKEN_ENDPOINT,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15
            )

            if token_response.status_code == 200:
                token_data = token_response.json()
                access_token = token_data.get('access_token', '')
                expires_in = token_data.get('expires_in', 3600)
                return {
                    'success': True,
                    'message': f'✅ OAuth2 authentication successful! Token expires in {expires_in}s. Store: {self.store_id}',
                    'store_id': self.store_id,
                    'token_preview': f"{access_token[:20]}..." if access_token else 'N/A',
                    'step': 'oauth2_success'
                }
            elif token_response.status_code == 401:
                return {
                    'success': False,
                    'message': 'OAuth2 authentication failed — Invalid Client ID or Client Secret. Check your .env credentials.',
                    'step': 'oauth2_failed',
                    'http_status': 401
                }
            else:
                return {
                    'success': False,
                    'message': f'OAuth2 token request failed: HTTP {token_response.status_code} — {token_response.text[:200]}',
                    'step': 'oauth2_error',
                    'http_status': token_response.status_code
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Connection timeout (15s). pasons.live is unreachable or slow.',
                'step': 'timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Cannot connect to pasons.live. Check internet connection.',
                'step': 'connection_error'
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'message': f'Connection test error: {str(e)}',
                'step': 'exception'
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