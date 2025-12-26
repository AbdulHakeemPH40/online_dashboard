"""
Outlet Reset Operations Engine

This module handles all outlet reset operations for fixing data corruption scenarios
where prices, stock, or item assignments are accidentally updated to wrong outlets.

Business Context:
- When users mistakenly update "Outlet A" data to "Outlet B"
- Provides controlled way to reset ItemOutlet records for specific outlets
- Maintains platform isolation and prevents accidental data loss
- Provides audit trail through OutletResetLog model

Reset Types:
1. Reset Prices Only - Clear MRP, selling_price, cost to NULL (cleaner than 0.00)
2. Reset Stock Only - Clear outlet_stock and unassign from outlet
3. Complete Reset - Reset all outlet-specific data to NULL/default values
4. Unassign Items - Set is_active_in_outlet = False and clear export tracking

Key Improvements:
- Price fields set to NULL instead of 0.00 for cleaner data
- Preserves CLS (Central Locking System) item-level locks
- Only resets BLS (Branch Locking System) outlet-level locks
- Complete outlet assignment cleanup with export tracking reset
"""

from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
import logging

from .models import Outlet, ItemOutlet, OutletResetLog

logger = logging.getLogger(__name__)


class OutletResetEngine:
    """
    Core engine for performing outlet reset operations with full audit trail.
    
    Features:
    - Platform isolation enforcement
    - Batch processing for performance
    - Comprehensive logging and audit trail
    - Error handling and recovery
    - Progress tracking for large datasets
    """
    
    def __init__(self, outlet, platform, reset_type, user=None):
        """
        Initialize reset engine for specific outlet and operation type.
        
        Args:
            outlet (Outlet): Target outlet to reset
            platform (str): Platform ('pasons' or 'talabat') for isolation verification
            reset_type (str): Type of reset ('prices_only', 'stock_only', 'complete_reset', 'unassign_items')
            user (User, optional): User performing the reset operation
        """
        self.outlet = outlet
        self.platform = platform
        self.reset_type = reset_type
        self.user = user
        self.reset_log = None
        self.batch_size = 500  # Process in batches for performance
        
        # Validate platform isolation
        if outlet.platforms != platform:
            raise ValueError(f"Platform mismatch: outlet is {outlet.platforms}, requested {platform}")
    
    def get_affected_items_preview(self, limit=10):
        """
        Get preview of items that will be affected by the reset operation.
        
        Args:
            limit (int): Maximum number of items to return for preview
            
        Returns:
            dict: {
                'total_count': int,
                'preview_items': list of ItemOutlet objects,
                'total_price_value': Decimal,
                'total_stock_value': int
            }
        """
        # Get all ItemOutlet records for this outlet with platform isolation
        queryset = ItemOutlet.objects.filter(
            outlet=self.outlet,
            item__platform=self.platform  # FIXED: Ensure platform isolation
        ).select_related('item')
        
        total_count = queryset.count()
        preview_items = list(queryset[:limit])
        
        # Calculate financial impact
        total_price_value = Decimal('0.00')
        total_stock_value = 0
        
        for item_outlet in queryset:
            # Price value calculation depends on reset type
            if self.reset_type in ['prices_only', 'complete_reset']:
                if item_outlet.outlet_selling_price:
                    total_price_value += item_outlet.outlet_selling_price
                if item_outlet.outlet_mrp:
                    total_price_value += item_outlet.outlet_mrp
                if item_outlet.outlet_cost:
                    total_price_value += item_outlet.outlet_cost
            
            # Stock value calculation
            if self.reset_type in ['stock_only', 'complete_reset']:
                total_stock_value += item_outlet.outlet_stock or 0
        
        return {
            'total_count': total_count,
            'preview_items': preview_items,
            'total_price_value': total_price_value,
            'total_stock_value': total_stock_value
        }
    
    def execute_reset(self, notes=None):
        """
        Execute the reset operation with full transaction safety and audit logging.
        
        Args:
            notes (str, optional): Additional notes about why reset was performed
            
        Returns:
            dict: {
                'success': bool,
                'reset_log': OutletResetLog,
                'message': str,
                'items_affected': int,
                'items_success': int,
                'items_failed': int
            }
        """
        # Create reset log entry
        self.reset_log = OutletResetLog.objects.create(
            outlet=self.outlet,
            platform=self.platform,
            reset_type=self.reset_type,
            performed_by=self.user,
            notes=notes,
            status='processing'
        )
        
        try:
            with transaction.atomic():
                # Get all affected items for this specific outlet
                queryset = ItemOutlet.objects.filter(
                    outlet=self.outlet,
                    item__platform=self.platform  # FIXED: Ensure platform isolation
                ).select_related('item')
                
                total_items = queryset.count()
                items_success = 0
                items_failed = 0
                total_price_value = Decimal('0.00')
                total_stock_value = 0
                
                # Process in batches for performance
                for i in range(0, total_items, self.batch_size):
                    batch = queryset[i:i + self.batch_size]
                    
                    for item_outlet in batch:
                        try:
                            # Calculate values before reset (for audit)
                            price_value_before = self._calculate_price_value(item_outlet)
                            stock_value_before = item_outlet.outlet_stock or 0
                            
                            # Perform the specific reset operation
                            if self.reset_type == 'prices_only':
                                self._reset_prices_only(item_outlet)
                            elif self.reset_type == 'stock_only':
                                self._reset_stock_only(item_outlet)
                            elif self.reset_type == 'complete_reset':
                                self._reset_complete(item_outlet)
                            elif self.reset_type == 'unassign_items':
                                self._unassign_items(item_outlet)
                            
                            item_outlet.save()
                            items_success += 1
                            
                            # Accumulate reset values for audit
                            total_price_value += price_value_before
                            total_stock_value += stock_value_before
                            
                        except Exception as e:
                            logger.error(f"Failed to reset item {item_outlet.item.item_code}: {str(e)}")
                            items_failed += 1
                
                # Update reset log with final statistics
                self.reset_log.items_affected = total_items
                self.reset_log.items_success = items_success
                self.reset_log.items_failed = items_failed
                self.reset_log.total_price_value_reset = total_price_value
                self.reset_log.total_stock_value_reset = total_stock_value
                
                # Determine final status
                if items_failed == 0:
                    status = 'success'
                    message = f"Successfully reset {items_success} items"
                elif items_success > 0:
                    status = 'partial'
                    message = f"Partially completed: {items_success} success, {items_failed} failed"
                else:
                    status = 'failed'
                    message = f"Reset failed: {items_failed} items could not be reset"
                
                self.reset_log.mark_completed(status=status)
                
                return {
                    'success': status in ['success', 'partial'],
                    'reset_log': self.reset_log,
                    'message': message,
                    'items_affected': total_items,
                    'items_success': items_success,
                    'items_failed': items_failed
                }
                
        except Exception as e:
            logger.error(f"Reset operation failed for outlet {self.outlet.name}: {str(e)}")
            self.reset_log.mark_completed(status='failed', error_message=str(e))
            
            return {
                'success': False,
                'reset_log': self.reset_log,
                'message': f"Reset operation failed: {str(e)}",
                'items_affected': 0,
                'items_success': 0,
                'items_failed': 0
            }
    
    def _calculate_price_value(self, item_outlet):
        """Calculate total price value for an ItemOutlet (for audit purposes)"""
        total = Decimal('0.00')
        if item_outlet.outlet_selling_price:
            total += item_outlet.outlet_selling_price
        if item_outlet.outlet_mrp:
            total += item_outlet.outlet_mrp
        if item_outlet.outlet_cost:
            total += item_outlet.outlet_cost
        return total
    
    def _reset_prices_only(self, item_outlet):
        """Reset only price-related fields to NULL (better than 0.00)"""
        # Set price fields to NULL instead of 0.00 for cleaner data
        item_outlet.outlet_mrp = None
        item_outlet.outlet_selling_price = None
        item_outlet.outlet_cost = None
        
        # IMPORTANT: When outlet_cost is reset, also reset Item.converted_cost
        # This ensures reports show clean data after outlet reset
        if hasattr(item_outlet.item, 'converted_cost'):
            item_outlet.item.converted_cost = None
            item_outlet.item.save(update_fields=['converted_cost'])
        
        # Clear promotion pricing as well
        item_outlet.promo_price = None
        item_outlet.converted_promo = None
        item_outlet.original_selling_price = None
        item_outlet.is_on_promotion = False
        # Clear export tracking for prices
        item_outlet.export_selling_price = None
        item_outlet.erp_export_price = None
    
    def _reset_stock_only(self, item_outlet):
        """Reset only stock-related fields and outlet assignment"""
        item_outlet.outlet_stock = 0  # Stock remains 0 (not NULL for counting)
        # Reset outlet assignment - make item unassigned from outlet
        item_outlet.is_active_in_outlet = False  # Unassign from outlet
        # Clear export tracking for stock
        item_outlet.export_stock_status = None
    
    def _reset_complete(self, item_outlet):
        """Reset all outlet-specific data to NULL/default values (complete cleanup)"""
        # Reset prices to NULL (cleaner than 0.00)
        self._reset_prices_only(item_outlet)
        # Reset stock and outlet assignment
        self._reset_stock_only(item_outlet)
        # Reset promotion dates to NULL
        item_outlet.promo_start_date = None
        item_outlet.promo_end_date = None
        # Reset BLS locks (outlet-level only, preserve CLS item-level locks)
        item_outlet.price_locked = False
        item_outlet.status_locked = False
        # Clear all export tracking to NULL
        item_outlet.export_selling_price = None
        item_outlet.export_stock_status = None
        item_outlet.erp_export_price = None
        # Clear data hash for fresh start
        item_outlet.data_hash = None
    
    def _unassign_items(self, item_outlet):
        """Unassign items from outlet (set inactive and clear export tracking)"""
        # Unassign from outlet
        item_outlet.is_active_in_outlet = False
        # Clear export tracking since item is no longer assigned to outlet
        item_outlet.export_selling_price = None
        item_outlet.export_stock_status = None
        item_outlet.erp_export_price = None


def get_outlets_for_platform(platform):
    """
    Get all outlets that support the specified platform.
    
    Args:
        platform (str): 'pasons' or 'talabat'
        
    Returns:
        QuerySet: Outlets filtered by platform, ordered by name
    """
    return Outlet.objects.filter(
        platforms=platform,
        is_active=True
    ).order_by('name')


def validate_reset_operation(outlet, platform, reset_type):
    """
    Validate that a reset operation can be performed safely.
    
    Args:
        outlet (Outlet): Target outlet
        platform (str): Platform for isolation check
        reset_type (str): Type of reset operation
        
    Returns:
        dict: {
            'is_valid': bool,
            'errors': list of error messages,
            'warnings': list of warning messages
        }
    """
    errors = []
    warnings = []
    
    # Check platform isolation
    if outlet.platforms != platform:
        errors.append(f"Platform mismatch: outlet is {outlet.platforms}, requested {platform}")
    
    # Check if outlet is active
    if not outlet.is_active:
        warnings.append("Outlet is currently inactive")
    
    # Check if there are items to reset
    item_count = ItemOutlet.objects.filter(
        outlet=outlet,
        outlet__platforms=platform
    ).count()
    
    if item_count == 0:
        warnings.append("No items found for this outlet - nothing to reset")
    
    # Check for locked items that might prevent reset
    from django.db import models
    locked_items = ItemOutlet.objects.filter(
        outlet=outlet,
        outlet__platforms=platform
    ).filter(
        models.Q(price_locked=True) | models.Q(status_locked=True) |
        models.Q(item__price_locked=True) | models.Q(item__status_locked=True)
    ).count()
    
    if locked_items > 0:
        warnings.append(f"{locked_items} items have locks that may prevent complete reset")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }