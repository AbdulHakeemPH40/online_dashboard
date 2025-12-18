"""
Django management command to run promotion activation/deactivation tasks
Run this daily via cron job to automatically activate and deactivate promotions
"""

from django.core.management.base import BaseCommand
from integration.promotion_service import PromotionService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Activate and deactivate promotions based on start/end dates'

    def handle(self, *args, **options):
        """
        Execute promotion activation and deactivation tasks
        """
        self.stdout.write(self.style.SUCCESS('Starting promotion tasks...'))
        
        # Activate promotions that have reached their start date
        activate_result = PromotionService.activate_promotions()
        self.stdout.write(
            self.style.SUCCESS(f"✓ {activate_result['message']}")
        )
        logger.info(activate_result['message'])
        
        # Deactivate expired promotions
        deactivate_result = PromotionService.deactivate_promotions()
        self.stdout.write(
            self.style.SUCCESS(f"✓ {deactivate_result['message']}")
        )
        logger.info(deactivate_result['message'])
        
        self.stdout.write(
            self.style.SUCCESS('Promotion tasks completed successfully!')
        )
