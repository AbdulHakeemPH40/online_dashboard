"""
Promotion Price Update Service

Handles promotional pricing logic including:
- Platform-specific price calculations (Pasons/Talabat)
- Wrap-based conversions (9900/1000)
- Validation rules (cost margin, price difference)
- Promotion activation/deactivation
"""

import logging
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
from django.db.models import Q
from django.utils import timezone
from .models import Item, ItemOutlet, Outlet

logger = logging.getLogger(__name__)


class PromotionService:
    """Service for managing promotional pricing"""
    
    # Validation thresholds
    MIN_COST_MARGIN_PCT = Decimal('20.00')  # 20% minimum margin for Talabat
    MIN_PRICE_DIFFERENCE = Decimal('2.00')  # 2 AED minimum difference
    
    @staticmethod
    def calculate_promo_price(
        promo_price: Decimal,
        platform: str,
        item_code: str,
        wdf: Optional[Decimal],
        talabat_margin: Decimal,
        cost: Decimal,
        selling_price: Decimal
    ) -> Dict:
        """
        Calculate promotional price with platform/wrap conversions and validations
        
        Args:
            promo_price: Input promotional price
            platform: 'pasons' or 'talabat'
            item_code: Item code to detect wrap type
            wdf: Weight division factor (for wrap items)
            talabat_margin: Talabat margin percentage
            cost: Current cost price (outlet_cost)
            selling_price: Current selling price
            
        Returns:
            Dict with calculated values and validation flags
        """
        from .utils import PricingCalculator
        
        is_wrap = str(item_code).strip().startswith('9900')
        
        # Calculate converted cost (C.Cost) for GP% validation
        if is_wrap and cost and wdf and wdf > 0:
            converted_cost = cost / wdf
        else:
            converted_cost = cost
        
        # Step 1: Calculate base converted price
        if is_wrap and wdf and wdf > 0:
            base_converted = promo_price / wdf
        else:
            base_converted = promo_price
        
        # Step 2: Add Talabat margin if applicable
        if platform == 'talabat':
            converted_promo = base_converted * (Decimal('1') + talabat_margin / Decimal('100'))
        else:
            converted_promo = base_converted
        
        # Apply smart rounding for Talabat
        if platform == 'talabat':
            converted_promo = PricingCalculator.smart_round(converted_promo)
        else:
            converted_promo = converted_promo.quantize(Decimal('0.01'))
        
        # Step 3: Validate GP% margin (Talabat only - minimum 20%)
        promo_adjusted = False
        adjusted_promo = converted_promo
        margin_warning = None
        
        if platform == 'talabat' and converted_cost and converted_cost > 0:
            # Calculate GP% = ((C.Promo - C.Cost) / C.Promo) * 100
            gp_percent = ((converted_promo - converted_cost) / converted_promo * Decimal('100')) if converted_promo > 0 else Decimal('0')
            
            # If GP% < 20%, adjust C.Promo = C.Cost * 1.35 (~26% margin)
            if gp_percent < Decimal('20'):
                adjusted_promo = converted_cost * Decimal('1.35')
                adjusted_promo = PricingCalculator.smart_round(adjusted_promo)
                promo_adjusted = True
                margin_warning = f"Promo price adjusted from {converted_promo} to {adjusted_promo} AED to meet 20% GP margin"
        
        # Calculate actual GP percentage
        if converted_cost and converted_cost > 0 and adjusted_promo > 0:
            margin_pct = ((adjusted_promo - converted_cost) / adjusted_promo * Decimal('100')).quantize(Decimal('0.01'))
        else:
            margin_pct = Decimal('0.00')
        
        # Step 4: Validate selling price difference (Talabat only - minimum 2 AED variance)
        selling_adjusted = False
        adjusted_selling = selling_price
        selling_warning = None
        
        if platform == 'talabat' and selling_price:
            variance = selling_price - adjusted_promo
            
            # Only adjust if selling > promo but variance < 2 AED
            if selling_price > adjusted_promo and variance < PromotionService.MIN_PRICE_DIFFERENCE:
                adjusted_selling = adjusted_promo + PromotionService.MIN_PRICE_DIFFERENCE
                adjusted_selling = adjusted_selling.quantize(Decimal('0.01'))
                selling_adjusted = True
                selling_warning = f"Selling price adjusted from {selling_price} to {adjusted_selling} AED to maintain 2 AED variance"
        
        return {
            'promo_price': promo_price,
            'converted_promo': adjusted_promo,
            'promo_adjusted': promo_adjusted,
            'margin_warning': margin_warning,
            'selling_price': adjusted_selling,
            'selling_adjusted': selling_adjusted,
            'selling_warning': selling_warning,
            'margin_pct': margin_pct,
            'difference': (adjusted_selling - adjusted_promo).quantize(Decimal('0.01')) if adjusted_selling else Decimal('0.00'),
            'is_wrap': is_wrap,
            'wdf': wdf
        }
    
    @staticmethod
    def search_item(item_code: str, units: str, platform: str) -> Optional[Dict]:
        """
        Search for item and return details needed for promotion setup
        
        Args:
            item_code: Item code
            units: Units (e.g., 'PCS', 'KGS')
            platform: Platform filter
            
        Returns:
            Dict with item details or None if not found
        """
        # Use filter().first() to handle potential duplicates
        item = Item.objects.filter(
            item_code=item_code,
            units=units,
            platform=platform
        ).first()
        
        if not item:
            return None
        
        # Get first outlet data (assuming promotions apply to all outlets)
        item_outlet = item.item_outlets.first()
        
        if not item_outlet:
            return None
        
        return {
            'item_id': item.id,
            'item_code': item.item_code,
            'units': item.units,
            'description': item.description,
            'platform': item.platform,
            'wdf': item.weight_division_factor,
            'talabat_margin': item.effective_talabat_margin,
            'current_selling_price': item_outlet.outlet_selling_price,
            'current_cost': item_outlet.outlet_cost,
            'is_wrap': str(item.item_code).startswith('9900'),
            'outlet_id': item_outlet.outlet_id
        }
    
    @staticmethod
    def save_promotion(
        item_code: str,
        units: str,
        platform: str,
        outlet_id: int,
        promo_price: Decimal,
        converted_promo: Decimal,
        adjusted_selling: Decimal,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Save promotion to database.
        Applies promotion to ALL items matching (item_code, units, platform) - handles multiple SKUs.
        
        Args:
            item_code: Item code
            units: Units
            platform: Platform
            promo_price: Input promo price
            converted_promo: Calculated promo price
            adjusted_selling: Adjusted selling price
            start_date: Promotion start date
            end_date: Promotion end date
            
        Returns:
            Dict with success status and message
        """
        try:
            # CRITICAL: Validate outlet belongs to platform
            try:
                outlet = Outlet.objects.get(id=outlet_id)
                if outlet.platforms != platform:
                    return {
                        'success': False,
                        'message': f'Outlet "{outlet.name}" belongs to {outlet.platforms.title()} platform, not {platform.title()} platform.'
                    }
            except Outlet.DoesNotExist:
                return {
                    'success': False,
                    'message': 'Outlet not found'
                }
            
            # Find ALL items matching (item_code, units, platform) - there can be multiple with different SKUs
            # e.g., 9900127 KGS has SKU 9900127250 AND SKU 9900127100
            items = Item.objects.filter(
                item_code=item_code,
                units=units,
                platform=platform
            )
            
            if not items.exists():
                return {
                    'success': False,
                    'message': 'Item not found'
                }
            
            outlets_updated = 0
            
            # Apply promotion to ALL items with this (item_code, units) combination
            for item in items:
                item_outlet = ItemOutlet.objects.filter(
                    item=item,
                    outlet_id=outlet_id
                ).first()
                
                if item_outlet:
                    # Backup original selling price if not already backed up
                    if not item_outlet.original_selling_price:
                        item_outlet.original_selling_price = item_outlet.outlet_selling_price
                    
                    # Calculate converted_promo for THIS specific SKU
                    # Each SKU may have different WDF, so we need to recalculate
                    from .utils import PricingCalculator
                    
                    is_wrap_9900 = item.wrap == '9900'
                    item_wdf = item.weight_division_factor
                    
                    # Calculate converted cost for GP% validation
                    if is_wrap_9900 and item_outlet.outlet_cost and item_wdf and item_wdf > 0:
                        converted_cost = item_outlet.outlet_cost / item_wdf
                    else:
                        converted_cost = item_outlet.outlet_cost or Decimal('0')
                    
                    # Calculate base converted promo
                    if is_wrap_9900 and item_wdf and item_wdf > 0:
                        base_converted = promo_price / item_wdf
                    else:
                        base_converted = promo_price
                    
                    # Add Talabat margin
                    if platform == 'talabat':
                        talabat_margin = item.effective_talabat_margin
                        item_converted_promo = base_converted * (Decimal('1') + talabat_margin / Decimal('100'))
                        item_converted_promo = PricingCalculator.smart_round(item_converted_promo)
                        
                        # Validate GP% >= 20%
                        if converted_cost > 0 and item_converted_promo > 0:
                            gp_percent = ((item_converted_promo - converted_cost) / item_converted_promo * Decimal('100'))
                            
                            if gp_percent < Decimal('20'):
                                # Adjust to meet 20% margin
                                item_converted_promo = converted_cost * Decimal('1.35')
                                item_converted_promo = PricingCalculator.smart_round(item_converted_promo)
                    else:
                        item_converted_promo = base_converted.quantize(Decimal('0.01'))
                    
                    # Set promotion fields
                    item_outlet.promo_price = promo_price
                    item_outlet.converted_promo = item_converted_promo
                    
                    # For Talabat: Ensure selling price meets variance requirement (minimum 2 AED above promo)
                    if platform == 'talabat':
                        current_selling = item_outlet.outlet_selling_price or Decimal('0')
                        variance = current_selling - item_converted_promo
                        
                        # If selling is 0, less than promo, or variance < 2 AED, adjust it
                        if current_selling <= item_converted_promo or variance < PromotionService.MIN_PRICE_DIFFERENCE:
                            item_outlet.outlet_selling_price = item_converted_promo + PromotionService.MIN_PRICE_DIFFERENCE
                    
                    item_outlet.promo_start_date = start_date
                    item_outlet.promo_end_date = end_date
                    item_outlet.is_on_promotion = True
                    item_outlet.save()
                    outlets_updated += 1
            
            if outlets_updated == 0:
                return {
                    'success': False,
                    'message': f'Item not found in selected outlet'
                }
            
            return {
                'success': True,
                'message': f'Promotion saved for {outlets_updated} SKU(s)',
                'outlets_updated': outlets_updated
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error saving promotion: {str(e)}'
            }
    
    @staticmethod
    def expire_ended_promotions(platform: str = None) -> int:
        """
        Auto-expire promotions whose end date has passed.
        Restores original selling price and clears promotion fields.
        
        Args:
            platform: Optional platform filter ('pasons' or 'talabat')
        
        Returns:
            int: Number of promotions expired
        """
        now = timezone.now()
        
        # PLATFORM ISOLATED: Filter by platform if specified
        query_filter = {
            'is_on_promotion': True,
            'promo_end_date__lt': now
        }
        
        if platform:
            query_filter['item__platform'] = platform
        
        expired_promos = ItemOutlet.objects.filter(**query_filter)
        
        count = 0
        for io in expired_promos:
            # Restore original selling price
            if io.original_selling_price:
                io.outlet_selling_price = io.original_selling_price
            
            # Clear promotion fields
            io.promo_price = None
            io.converted_promo = None
            io.original_selling_price = None
            io.promo_start_date = None
            io.promo_end_date = None
            io.is_on_promotion = False
            io.save()
            count += 1
        
        return count
    
    @staticmethod
    def check_existing_promotion(item_code: str, units: str, platform: str, outlet_id: int) -> Dict:
        """
        Check if an item already has an active promotion
        
        Args:
            item_code: Item code
            units: Units
            platform: Platform
            outlet_id: Outlet ID
            
        Returns:
            Dict with existing promotion info if found
        """
        try:
            item = Item.objects.filter(
                item_code=item_code,
                units=units,
                platform=platform
            ).first()
            
            if not item:
                return {'exists': False}
            
            existing = ItemOutlet.objects.filter(
                item=item,
                outlet_id=outlet_id,
                is_on_promotion=True
            ).first()
            
            if existing:
                return {
                    'exists': True,
                    'promo_price': str(existing.promo_price) if existing.promo_price else None,
                    'start_date': timezone.localtime(existing.promo_start_date).strftime('%d/%m/%Y %I:%M %p') if existing.promo_start_date else None,
                    'end_date': timezone.localtime(existing.promo_end_date).strftime('%d/%m/%Y %I:%M %p') if existing.promo_end_date else None
                }
            
            return {'exists': False}
        except Exception:
            return {'exists': False}
    
    @staticmethod
    def get_active_promotions(platform: Optional[str] = None, outlet_id: Optional[int] = None, page: int = 1, page_size: int = 20) -> Dict:
        """
        Get list of active promotions with pagination and status categorization
        
        Args:
            platform: Optional platform filter
            outlet_id: Optional outlet filter
            page: Page number (1-indexed)
            page_size: Items per page
            
        Returns:
            Dict with promotions list, pagination info, and status summary
        """
        from django.utils import timezone
        from datetime import datetime
        
        # First, auto-expire any ended promotions
        expired_count = PromotionService.expire_ended_promotions()
        
        # Get current time for status calculation
        now = timezone.now()
        
        # CRITICAL: Only get promotions that are NOT expired (end_date >= now)
        # This ensures expired promotions are COMPLETELY excluded from the query
        query = Q(
            promo_start_date__isnull=False,
            promo_end_date__isnull=False,
            promo_price__isnull=False,
            promo_end_date__gte=now  # EXCLUDE expired promotions at database level
        )
        
        if platform:
            query &= Q(item__platform=platform)
        
        if outlet_id:
            query &= Q(outlet_id=outlet_id)
        
        # Get only NON-EXPIRED promotions (upcoming and running only)
        all_promotions = ItemOutlet.objects.filter(query).select_related('item', 'outlet').order_by('-promo_start_date')
        
        # Categorize promotions by status - ONLY upcoming and running (no expired possible)
        upcoming_promotions = []
        running_promotions = []
        
        for io in all_promotions:
            if io.promo_start_date > now:
                # Upcoming promotion
                upcoming_promotions.append(io)
            elif io.promo_start_date <= now <= io.promo_end_date:
                # Currently running promotion
                running_promotions.append(io)
            # Note: No else clause for expired - they're already excluded by query
        
        # Combine ONLY visible promotions (upcoming + running) - NO expired promotions possible
        visible_promotions = upcoming_promotions + running_promotions
        
        # Apply pagination
        total_count = len(visible_promotions)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        # Calculate offset
        offset = (page - 1) * page_size
        page_promotions = visible_promotions[offset:offset + page_size]
        
        result = []
        for io in page_promotions:
            # Calculate promotion status - ONLY show upcoming and running
            if io.promo_start_date > now:
                status = 'upcoming'
                status_text = 'Upcoming'
                days_info = (io.promo_start_date.date() - now.date()).days
                if days_info == 0:
                    days_text = "Starts today"
                elif days_info == 1:
                    days_text = "Starts tomorrow"
                else:
                    days_text = f"Starts in {days_info}d"
            elif io.promo_start_date <= now <= io.promo_end_date:
                status = 'running'
                status_text = 'Running'
                days_info = (io.promo_end_date.date() - now.date()).days
                if days_info == 0:
                    days_text = "Ends today"
                elif days_info == 1:
                    days_text = "Ends tomorrow"
                else:
                    days_text = f"{days_info}d remaining"
            else:
                # This should NEVER happen since we exclude expired promotions at database level
                continue
            
            # Calculate converted cost based on wrap type
            # wrap=9900: converted_cost = outlet_cost / wdf (3 decimals)
            # wrap=10000: converted_cost = outlet_cost (2 decimals)
            is_wrap_9900 = io.item.wrap == '9900'
            outlet_cost = io.outlet_cost
            
            if is_wrap_9900 and outlet_cost and io.item.weight_division_factor and io.item.weight_division_factor > 0:
                converted_cost = (outlet_cost / io.item.weight_division_factor).quantize(Decimal('0.001'))
            else:
                converted_cost = outlet_cost.quantize(Decimal('0.01')) if outlet_cost else None
            
            # Debug logging
            logger.debug(f"Item {io.item.item_code}: wrap={io.item.wrap}, outlet_cost={outlet_cost}, wdf={io.item.weight_division_factor}, converted_cost={converted_cost}")
            
            # Format dates with better readability
            start_date_formatted = timezone.localtime(io.promo_start_date).strftime('%d %b %Y, %I:%M %p') if io.promo_start_date else None
            end_date_formatted = timezone.localtime(io.promo_end_date).strftime('%d %b %Y, %I:%M %p') if io.promo_end_date else None
            
            result.append({
                'id': io.id,
                'item_code': io.item.item_code,
                'units': io.item.units,
                'sku': io.item.sku,
                'description': io.item.description,
                'platform': io.item.platform,
                'wrap': io.item.wrap,
                'outlet_id': io.outlet_id,
                'outlet_name': io.outlet.name,
                'promo_price': str(io.promo_price) if io.promo_price else None,
                'converted_promo': str(io.converted_promo) if io.converted_promo else None,
                'selling_price': str(io.outlet_selling_price) if io.outlet_selling_price else None,
                'mrp': str(io.outlet_mrp) if io.outlet_mrp else None,
                'cost': str(outlet_cost) if outlet_cost else None,
                'converted_cost': str(converted_cost) if converted_cost else None,
                'original_selling_price': str(io.original_selling_price) if io.original_selling_price else None,
                'stock': io.outlet_stock,
                'is_active': io.is_active_in_outlet,
                'start_date': start_date_formatted,
                'end_date': end_date_formatted,
                'start_date_raw': timezone.localtime(io.promo_start_date).strftime('%d/%m/%Y %I:%M %p') if io.promo_start_date else None,
                'end_date_raw': timezone.localtime(io.promo_end_date).strftime('%d/%m/%Y %I:%M %p') if io.promo_end_date else None,
                'days_remaining': days_info,
                'days_text': days_text,
                'status': status,
                'status_text': status_text,
                'is_upcoming': status == 'upcoming',
                'is_running': status == 'running',
                'is_expired': False  # Never show expired promotions
            })
        
        return {
            'promotions': result,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
            'status_summary': {
                'upcoming_count': len(upcoming_promotions),
                'running_count': len(running_promotions),
                'total_visible': len(visible_promotions)  # Only visible promotions (no expired)
            }
        }
    
    @staticmethod
    def bulk_cancel_promotions(item_outlet_ids: List[int]) -> Dict:
        """
        Cancel multiple promotions at once
        
        Args:
            item_outlet_ids: List of ItemOutlet IDs to cancel
            
        Returns:
            Dict with success count
        """
        success_count = 0
        for item_outlet_id in item_outlet_ids:
            result = PromotionService.cancel_promotion(item_outlet_id)
            if result['success']:
                success_count += 1
        
        return {
            'success': True,
            'message': f'Cancelled {success_count} promotion(s)',
            'cancelled_count': success_count
        }
    
    @staticmethod
    def cancel_all_promotions_for_outlet(platform: str, outlet_id: int) -> Dict:
        """
        Cancel ALL promotions for a specific outlet
        
        Args:
            platform: Platform filter
            outlet_id: Outlet ID
            
        Returns:
            Dict with success count
        """
        query = Q(is_on_promotion=True, outlet_id=outlet_id, item__platform=platform)
        promotions = ItemOutlet.objects.filter(query)
        
        count = 0
        for io in promotions:
            # Restore original selling price
            if io.original_selling_price:
                io.outlet_selling_price = io.original_selling_price
            
            # Clear promotion fields
            io.promo_price = None
            io.converted_promo = None
            io.original_selling_price = None
            io.promo_start_date = None
            io.promo_end_date = None
            io.is_on_promotion = False
            io.save()
            count += 1
        
        return {
            'success': True,
            'message': f'Cancelled all {count} promotion(s) for this outlet',
            'cancelled_count': count
        }
    
    @staticmethod
    def cancel_promotion(item_outlet_id: int) -> Dict:
        """
        Cancel a promotion and restore original price
        
        Args:
            item_outlet_id: ItemOutlet ID
            
        Returns:
            Dict with success status and message
        """
        try:
            item_outlet = ItemOutlet.objects.get(id=item_outlet_id)
            
            # Restore original selling price
            if item_outlet.original_selling_price:
                item_outlet.outlet_selling_price = item_outlet.original_selling_price
            
            # Clear promotion fields
            item_outlet.promo_price = None
            item_outlet.converted_promo = None
            item_outlet.original_selling_price = None
            item_outlet.promo_start_date = None
            item_outlet.promo_end_date = None
            item_outlet.is_on_promotion = False
            item_outlet.save()
            
            return {
                'success': True,
                'message': 'Promotion cancelled and original price restored'
            }
        except ItemOutlet.DoesNotExist:
            return {
                'success': False,
                'message': 'Item outlet not found'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error cancelling promotion: {str(e)}'
            }
    
    @staticmethod
    def activate_promotions() -> Dict:
        """
        Activate promotions that have reached their start date
        Called by scheduled task
        
        Returns:
            Dict with count of activated promotions
        """
        # Ensure we use Dubai date for comparison
        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        
        # Find promotions that should be active but aren't yet
        promotions = ItemOutlet.objects.filter(
            promo_start_date__lte=now_local,
            promo_end_date__gte=now_local,
            is_on_promotion=False,
            promo_price__isnull=False
        )
        
        count = 0
        for io in promotions:
            io.is_on_promotion = True
            io.save()
            count += 1
        
        return {
            'activated': count,
            'message': f'Activated {count} promotion(s)'
        }
    
    @staticmethod
    def deactivate_promotions() -> Dict:
        """
        Deactivate expired promotions and restore original prices
        Called by scheduled task
        
        Returns:
            Dict with count of deactivated promotions
        """
        # Ensure we use Dubai time for comparison
        now_local = timezone.localtime(timezone.now())
        
        # Find expired promotions
        promotions = ItemOutlet.objects.filter(
            promo_end_date__lt=now_local,
            is_on_promotion=True
        )
        
        count = 0
        for io in promotions:
            # Restore original selling price
            if io.original_selling_price:
                io.outlet_selling_price = io.original_selling_price
            
            # Clear promotion fields
            io.promo_price = None
            io.converted_promo = None
            io.original_selling_price = None
            io.promo_start_date = None
            io.promo_end_date = None
            io.is_on_promotion = False
            io.save()
            count += 1
        
        return {
            'deactivated': count,
            'message': f'Deactivated {count} expired promotion(s)'
        }
