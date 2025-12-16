from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from integration.models import Item


class Command(BaseCommand):
    help = 'Find duplicate SKUs for wrap=10000 items with same item_code & units'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            default='',
            help='Filter by platform (pasons or talabat). Leave empty to check all platforms.',
        )
        parser.add_argument(
            '--export',
            action='store_true',
            help='Export results to CSV file',
        )

    def handle(self, *args, **options):
        platform_filter = options.get('platform', '').strip()
        export = options.get('export', False)

        # Build query for wrap=10000 items ONLY
        # wrap=9900 items can have multiple SKUs for same (item_code, units), so exclude them
        query = Item.objects.filter(wrap='10000')
        
        if platform_filter:
            if platform_filter not in ('pasons', 'talabat'):
                self.stdout.write(self.style.ERROR(f'Invalid platform: {platform_filter}'))
                return
            query = query.filter(platform=platform_filter)

        # Group by (item_code, units) and find duplicates
        duplicates_dict = {}
        for item in query:
            key = (item.item_code, item.units)
            if key not in duplicates_dict:
                duplicates_dict[key] = []
            duplicates_dict[key].append(item)

        # Filter only keys with multiple SKUs
        duplicate_keys = {k: v for k, v in duplicates_dict.items() if len(v) > 1}

        if not duplicate_keys:
            self.stdout.write(self.style.SUCCESS('✓ No duplicates found!'))
            return

        # Display results
        self.stdout.write(self.style.WARNING(f'\n🔍 Found {len(duplicate_keys)} item_code+units combinations with duplicate SKUs (wrap=10000 only):\n'))

        results = []
        for (item_code, units), items in sorted(duplicate_keys.items()):
            self.stdout.write(f'\n📦 item_code={item_code} | units={units}')
            self.stdout.write(f'   ({len(items)} duplicate SKUs):')
            
            for idx, item in enumerate(items, 1):
                sku_display = f'{item.sku}' if item.sku else '(empty)'
                status_icon = '✓' if item.is_active else '✗'
                
                self.stdout.write(
                    f'   {idx}. SKU: {sku_display:<20} '
                    f'| MRP: {item.mrp:<8} '
                    f'| Cost: {item.cost:<8} '
                    f'| WDF: {item.weight_division_factor or "N/A":<5} '
                    f'| Active: {status_icon} '
                    f'| Platform: {item.platform}'
                )
                
                results.append({
                    'item_code': item_code,
                    'units': units,
                    'sku': item.sku or '(empty)',
                    'mrp': item.mrp,
                    'cost': item.cost,
                    'weight_division_factor': item.weight_division_factor,
                    'is_active': item.is_active,
                    'platform': item.platform,
                    'description': item.description,
                })

        # Summary
        total_duplicate_items = sum(len(items) for items in duplicate_keys.values())
        self.stdout.write(self.style.WARNING(f'\n📊 Summary:'))
        self.stdout.write(f'   • Combinations with duplicates: {len(duplicate_keys)}')
        self.stdout.write(f'   • Total items affected: {total_duplicate_items}')

        # Export to CSV if requested
        if export:
            self._export_to_csv(results, platform_filter)

    def _export_to_csv(self, results, platform_filter):
        """Export duplicate findings to CSV"""
        import csv
        from datetime import datetime

        filename = f'wrap10000_duplicates_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        'item_code', 'units', 'sku', 'description', 'mrp', 
                        'cost', 'weight_division_factor', 'is_active', 'platform'
                    ]
                )
                writer.writeheader()
                writer.writerows(results)
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Exported to: {filename}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Export failed: {str(e)}'))
