"""
Django Signals for Item Model

Auto-set default values to prevent validation errors
"""

from django.db.models.signals import pre_save
from django.dispatch import receiver
from decimal import Decimal
from .models import Item
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Item)
def set_default_wdf_for_wrap10000(sender, instance, **kwargs):
    """
    Automatically set WDF=1 for wrap=10000 items if WDF is None
    
    BUSINESS LOGIC:
    - wrap=10000 (regular/packaged items): Don't need WDF for pricing
    - But WDF=1 prevents validation errors in cost conversion
    - WDF=1 means "no division": cost ÷ 1 = cost (no change)
    
    WHEN THIS RUNS:
    - Bulk item creation via CSV
    - Manual item creation via admin
    - Item updates via API
    - Any item.save() call
    """
    # Only process wrap=10000 items
    if instance.wrap == '10000':
        # If WDF is None or 0, set to 1
        if instance.weight_division_factor is None or instance.weight_division_factor == 0:
            instance.weight_division_factor = Decimal('1')
            logger.info(
                f"Auto-set WDF=1 for wrap=10000 item: {instance.item_code} "
                f"(Platform: {instance.platform})"
            )


@receiver(pre_save, sender=Item)
def validate_wrap9900_has_wdf(sender, instance, **kwargs):
    """
    Validate that wrap=9900 items have valid WDF > 0
    
    BUSINESS LOGIC:
    - wrap=9900 (weight-based items): MUST have WDF for price calculations
    - WDF determines how to divide price (e.g., WDF=4 means price÷4)
    
    RAISES:
    - ValueError if wrap=9900 item has no WDF or WDF <= 0
    """
    # Only validate wrap=9900 items
    if instance.wrap == '9900':
        if instance.weight_division_factor is None:
            raise ValueError(
                f"wrap=9900 item {instance.item_code} requires weight_division_factor. "
                f"Cannot save without WDF. Please set WDF based on product specifications."
            )
        if instance.weight_division_factor <= 0:
            raise ValueError(
                f"wrap=9900 item {instance.item_code} has invalid WDF: {instance.weight_division_factor}. "
                f"WDF must be greater than 0."
            )
