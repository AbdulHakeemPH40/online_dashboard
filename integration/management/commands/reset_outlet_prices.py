"""
Management command to reset all outlet selling prices to 0.00
This clears old incorrect prices so fresh outlet-specific prices can be uploaded

Usage:
    python manage.py reset_outlet_prices
"""

from django.core.management.base import BaseCommand
from integration.models import ItemOutlet


class Command(BaseCommand):
    help = 'Reset all outlet_selling_price values to 0.00 for fresh price upload'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            help='Reset only for specific platform (pasons or talabat)',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm the reset operation',
        )

    def handle(self, *args, **options):
        platform = options.get('platform')
        confirm = options.get('confirm')
        
        # Build query
        queryset = ItemOutlet.objects.all()
        
        if platform:
            queryset = queryset.filter(item__platform=platform.lower())
            platform_msg = f" for platform '{platform}'"
        else:
            platform_msg = " for ALL platforms"
        
        total_count = queryset.count()
        
        # Safety check
        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  WARNING: This will reset outlet_selling_price to 0.00 for {total_count:,} ItemOutlet records{platform_msg}.\n'
                )
            )
            self.stdout.write(
                self.style.NOTICE(
                    'To proceed, run the command again with --confirm flag:\n'
                    f'  python manage.py reset_outlet_prices{" --platform " + platform if platform else ""} --confirm\n'
                )
            )
            return
        
        # Execute reset
        self.stdout.write(f'\n🔄 Resetting {total_count:,} outlet prices{platform_msg}...\n')
        
        updated = queryset.update(outlet_selling_price=0.00)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully reset {updated:,} outlet selling prices to 0.00!\n'
            )
        )
        
        if platform:
            self.stdout.write(
                self.style.NOTICE(
                    f'Next step: Upload fresh prices for {platform} outlets at:\n'
                    '  http://127.0.0.1:8000/integration/price-update/\n'
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    'Next step: Upload fresh prices per outlet at:\n'
                    '  http://127.0.0.1:8000/integration/price-update/\n'
                )
            )
