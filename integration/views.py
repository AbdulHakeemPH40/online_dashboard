from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.cache import cache
from django.views.decorators.http import require_http_methods
from .models import Outlet, Item, ItemOutlet
from .utils import decode_csv_upload
import logging
from decimal import Decimal, InvalidOperation
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Allowed wrap values for items
ALLOWED_WRAP_VALUES = {"9900", "10000"}


def rate_limit(max_requests: int, time_window_seconds: int):
    """
    Simple rate limiting decorator using Django cache.
    Limits number of requests per user per time window.
    
    Args:
        max_requests: Maximum number of requests allowed
        time_window_seconds: Time window in seconds
    
    Returns:
        HttpResponse with 429 status if limit exceeded
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get user identifier
            user_key = f"rate_limit:{view_func.__name__}:{request.user.id or request.META.get('REMOTE_ADDR')}"
            
            # Get current count
            current_count = cache.get(user_key, 0)
            
            if current_count >= max_requests:
                logger.warning(f"Rate limit exceeded for {request.user} on {view_func.__name__}")
                return JsonResponse({
                    'success': False,
                    'message': f'Rate limit exceeded. Maximum {max_requests} requests per {time_window_seconds} seconds.'
                }, status=429)
            
            # Increment counter
            cache.set(user_key, current_count + 1, time_window_seconds)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def login_view(request):
    """
    Custom login view that handles user authentication
    """
    if request.method == 'GET':
        # If user is already authenticated, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'login.html')
    
    elif request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect to dashboard after successful login
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                # Invalid credentials
                return render(request, 'login.html', {
                    'error': 'Invalid username or password. Please try again.'
                })
        else:
            # Missing username or password
            return render(request, 'login.html', {
                'error': 'Please enter both username and password.'
            })


@login_required
def dashboard(request):
    """
    Main dashboard view that renders the dashboard template for Pasons
    OPTIMIZED: Uses simple database counts instead of complex Python iteration
    """
    try:
        from django.db.models import Sum, Count, Q
        
        # Count total items for this platform
        pasons_total_items = Item.objects.filter(platform='pasons', is_active=True).count()
        
        # Count items that have at least one ItemOutlet with stock > 0
        # This is a simple approximation - active = has stock
        items_with_stock = ItemOutlet.objects.filter(
            outlet__platforms='pasons',
            item__platform='pasons',
            outlet__is_active=True,
            outlet_stock__gt=0
        ).values('item_id').distinct().count()
        
        # Items with outlets but zero/low stock
        items_with_outlets = ItemOutlet.objects.filter(
            outlet__platforms='pasons',
            item__platform='pasons',
            outlet__is_active=True
        ).values('item_id').distinct().count()
        
        pasons_active_items = items_with_stock
        pasons_low_stock_items = max(0, items_with_outlets - items_with_stock)
        
    except Exception as e:
        import sys
        print(f'Dashboard error: {str(e)}', file=sys.stderr)
        pasons_total_items = 0
        pasons_active_items = 0
        pasons_low_stock_items = 0

    context = {
        'page_title': 'Pasons Dashboard Overview',
        'active_nav': 'pasons',
        'total_items': pasons_total_items,
        'active_items': pasons_active_items,
        'low_stock_items': pasons_low_stock_items,
    }
    return render(request, 'dashboard.html', context)


@login_required
def talabat_dashboard(request):
    """
    Dashboard view that renders the Talabat dashboard template
    OPTIMIZED: Uses simple database counts instead of complex Python iteration
    """
    try:
        from django.db.models import Sum, Count, Q
        
        # Count total items for this platform
        talabat_total_items = Item.objects.filter(platform='talabat', is_active=True).count()
        
        # Count items that have at least one ItemOutlet with stock > 0
        items_with_stock = ItemOutlet.objects.filter(
            outlet__platforms='talabat',
            item__platform='talabat',
            outlet__is_active=True,
            outlet_stock__gt=0
        ).values('item_id').distinct().count()
        
        # Items with outlets but zero/low stock
        items_with_outlets = ItemOutlet.objects.filter(
            outlet__platforms='talabat',
            item__platform='talabat',
            outlet__is_active=True
        ).values('item_id').distinct().count()
        
        talabat_active_items = items_with_stock
        talabat_low_stock_items = max(0, items_with_outlets - items_with_stock)
        
    except Exception as e:
        import sys
        print(f'Dashboard error: {str(e)}', file=sys.stderr)
        talabat_total_items = 0
        talabat_active_items = 0
        talabat_low_stock_items = 0

    context = {
        'page_title': 'Talabat Dashboard Overview',
        'active_nav': 'talabat',
        'total_items': talabat_total_items,
        'active_items': talabat_active_items,
        'low_stock_items': talabat_low_stock_items,
    }
    return render(request, 'talabat_dashboard.html', context)


@login_required
def list_items_api(request):
    """
    API endpoint to list items filtered by platform with optional search and pagination.
    Returns data suitable for populating the dashboard table.
    OPTIMIZED: Uses database-level annotations to avoid N+1 queries.
    """
    try:
        platform = request.GET.get('platform', '').strip()
        if platform not in ('pasons', 'talabat'):
            return JsonResponse({'success': False, 'message': 'Invalid or missing platform'}, status=400)

        query = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', '1'))
        page_size = int(request.GET.get('page_size', '50'))
        if page_size <= 0:
            page_size = 50
        if page_size > 200:
            page_size = 200

        from django.db.models import Sum, OuterRef, Subquery, Value
        from django.db.models.functions import Coalesce
        
        # Build base queryset with platform filter
        qs = Item.objects.filter(platform=platform)

        if query:
            qs = qs.filter(
                Q(item_code__icontains=query) |
                Q(description__icontains=query) |
                Q(sku__icontains=query) |
                Q(barcode__icontains=query) |
                Q(pack_description__icontains=query)
            )

        # OPTIMIZATION: Annotate stock sum at database level (single query)
        # This adds a 'platform_stock' field to each item via subquery
        stock_subquery = ItemOutlet.objects.filter(
            item=OuterRef('pk'),
            outlet__platforms=platform,
            outlet__is_active=True
        ).values('item').annotate(
            total=Sum('outlet_stock')
        ).values('total')
        
        qs = qs.annotate(
            platform_stock=Coalesce(Subquery(stock_subquery), Value(0))
        )

        paginator = Paginator(qs.order_by('item_code'), page_size)
        page_obj = paginator.get_page(page)
        
        # Get item IDs for batch outlet lookup
        item_ids = [item.id for item in page_obj.object_list]
        
        # OPTIMIZATION: Batch fetch all outlet names in ONE query
        # Include store_id to prevent duplicate names when multiple outlets have same name
        outlet_data = ItemOutlet.objects.filter(
            item_id__in=item_ids,
            outlet__platforms=platform,
            outlet__is_active=True
        ).select_related('outlet').values('item_id', 'outlet__name', 'outlet__store_id')
        
        # Build lookup: item_id -> set of outlet display names (with store_id for uniqueness)
        outlet_names_map = {}
        for od in outlet_data:
            if od['item_id'] not in outlet_names_map:
                outlet_names_map[od['item_id']] = set()
            # Include store_id to differentiate outlets with identical names
            outlet_display = od['outlet__name']
            if od['outlet__store_id']:
                outlet_display = f"{outlet_display} ({od['outlet__store_id']})"
            outlet_names_map[od['item_id']].add(outlet_display)

        items = []
        for item in page_obj.object_list:
            # Sort outlet names for consistent, readable display
            outlet_names = sorted(list(outlet_names_map.get(item.id, [])))
            
            items.append({
                'item_code': item.item_code,
                'description': item.description,
                'pack_description': item.pack_description or '',
                'locations': outlet_names,
                'mrp': float(item.mrp),
                'stock': int(item.platform_stock or 0),  # From annotation
                'status': 'Active' if item.is_active else 'Inactive',
                'status_code': 'A' if item.is_active else 'I',
                'lock_status': 'N/A',
                'cost': float(item.cost),
                'sku': item.sku,
                'talabat_margin': float(item.effective_talabat_margin) if platform == 'talabat' else None,
            })

        return JsonResponse({
            'success': True,
            'items': items,
            'page': page_obj.number,
            'page_size': page_size,
            'total_items': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
        })
    except Exception as e:
        logger.error(f"list_items_api error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error loading items: {str(e)}'})

def dashboard_stats_api(request):
    """
    API endpoint that provides dashboard statistics in JSON format
    """
    # Placeholder data for fresh start
    return JsonResponse({
        'total_products': 0,
        'active_products': 0,
        'low_stock_products': 0,
        'out_of_stock_products': 0,
        'platform_mapping': {
            'talabat': 0,
            'pasons': 0
        },
        'last_sync': {
            'talabat': None,
            'pasons': None
        },
        'category_breakdown': {},
        'stock_status': {
            'in_stock': 0,
            'low_stock': 0,
            'out_of_stock': 0
        },
        'recent_syncs': [],
        'alerts': [],
        'price_stats': {
            'min_price': 0,
            'max_price': 0,
            'avg_price': 0
        },
        'active_pricing_rules': 0,
        'weight_variants_count': 0,
        'message': 'Dashboard ready for fresh implementation'
    })


def system_health_check(request):
    """
    API endpoint for system health monitoring
    """
    return JsonResponse({
        'status': 'healthy',
        'components': {
            'database': 'healthy',
            'sync_operations': 'healthy',
            'error_rate': 'healthy'
        },
        'metrics': {
            'recent_errors': 0,
            'last_successful_sync': True
        },
        'message': 'System ready for fresh implementation'
    })


def quick_stats(request):
    """
    Lightweight API endpoint for quick dashboard updates
    """
    return JsonResponse({
        'total_products': 0,
        'active_products': 0,
        'running_syncs': 0,
        'message': 'Ready for implementation'
    })


@login_required
def create_store(request):
    """Create new store/outlet"""
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        platforms = request.POST.get('platforms')
        
        if name and location and platforms:
            # Check if store name already exists for this platform
            if Outlet.objects.filter(name=name, platforms=platforms).exists():
                platform_name = {
                    'pasons': 'Pasons Ecommerce',
                    'talabat': 'Talabat Platform'
                }.get(platforms, platforms)
                messages.error(request, f'Store "{name}" already exists on {platform_name}. Please use a different name.')
            else:
                try:
                    outlet = Outlet.objects.create(
                        name=name,
                        location=location,
                        platforms=platforms,
                        is_active=True
                    )
                    platform_name = {
                        'pasons': 'Pasons Ecommerce',
                        'talabat': 'Talabat Platform'
                    }.get(platforms, platforms)
                    
                    messages.success(request, f'Store "{name}" created successfully with ID: {outlet.store_id} for {platform_name}')
                    return redirect('integration:store_list')
                except Exception as e:
                    messages.error(request, f'Error creating store: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields including platform selection.')
    
    context = {
        'page_title': 'Create New Store',
        'active_nav': 'stores'
    }
    return render(request, 'create_store.html', context)


@login_required
def store_list(request):
    """List all stores"""
    outlets = Outlet.objects.all().order_by('-created_at')
    
    # Calculate platform-specific statistics
    pasons_outlets = outlets.filter(platforms='pasons')
    talabat_outlets = outlets.filter(platforms='talabat')
    
    context = {
        'page_title': 'Store Management',
        'active_nav': 'stores',
        'outlets': outlets,
        'total_stores': outlets.count(),
        'active_stores': outlets.filter(is_active=True).count(),
        'pasons_stores': pasons_outlets.count(),
        'talabat_stores': talabat_outlets.count()
    }
    return render(request, 'store_list.html', context)


@login_required
def edit_store(request, store_id):
    """Edit existing store/outlet"""
    from .models import Outlet
    from django.shortcuts import get_object_or_404
    
    outlet = get_object_or_404(Outlet, id=store_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        platforms = request.POST.get('platforms')
        
        if name and location and platforms:
            # Check if store name already exists for this platform (excluding current store)
            if Outlet.objects.filter(name=name, platforms=platforms).exclude(id=outlet.id).exists():
                platform_name = {
                    'pasons': 'Pasons Ecommerce',
                    'talabat': 'Talabat Platform'
                }.get(platforms, platforms)
                messages.error(request, f'Store "{name}" already exists on {platform_name}. Please use a different name.')
            else:
                # Check if platform has changed
                platform_changed = outlet.platforms != platforms
                
                outlet.name = name
                outlet.location = location
                
                # If platform changed, generate new store ID
                if platform_changed:
                    outlet.platforms = platforms
                    # Generate new store ID based on new platform
                    outlet.store_id = outlet.generate_unique_store_id()
                    messages.success(request, f'Store updated successfully! New Store ID: {outlet.store_id} (Platform: {platforms.title()})')
                else:
                    messages.success(request, f'Store "{name}" updated successfully!')
                
                outlet.save()
                return redirect('integration:store_list')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'page_title': 'Edit Store',
        'active_nav': 'stores',
        'outlet': outlet
    }
    return render(request, 'edit_store.html', context)


@login_required
def delete_store(request, store_id):
    """Delete existing store/outlet"""
    from .models import Outlet
    from django.shortcuts import get_object_or_404
    
    outlet = get_object_or_404(Outlet, id=store_id)
    
    if request.method == 'POST':
        outlet.delete()
        return redirect('integration:store_list')
    
    context = {
        'page_title': 'Delete Store',
        'active_nav': 'stores',
        'outlet': outlet
    }
    return render(request, 'delete_store.html', context)


@login_required
def bulk_item_creation(request):
    """
    Bulk item creation view with platform-specific outlet filtering
    """
    if request.method == 'POST':
        # Handle CSV upload and item creation
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        
        if platform and csv_file:
            try:
                # Get all outlets that support the selected platform
                from .models import Outlet, Item, ItemOutlet
                from django.contrib import messages
                from django.db import models, transaction
                
                # Filter outlets by platform - STRICT ISOLATION
                outlets = Outlet.objects.filter(
                    is_active=True,
                    platforms=platform
                )
                
                if not outlets.exists():
                    messages.error(request, f"No active outlets found for {platform.title()} platform.")
                    return redirect('integration:bulk_item_creation')
                
                # Process CSV file
                import csv
                import io

                # Read CSV content with encoding fallback
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                # Strict header validation
                required_headers = {'wrap', 'item_code', 'description', 'units', 'sku', 'pack_description'}
                optional_headers = {'barcode', 'mrp', 'selling_price', 'cost', 'stock', 'weight_division_factor', 'outer_case_quantity', 'minimum_qty'}
                allowed_headers = required_headers | optional_headers
                # Filter out empty header fields (from trailing delimiters)
                headers = [h.strip().lower() for h in (csv_reader.fieldnames or []) if h and h.strip()]
                if not headers:
                    messages.error(request, 'CSV file is missing a header row. Include headers exactly as specified.')
                    return redirect('integration:bulk_item_creation')
                # Disallow is_active column entirely
                if 'is_active' in headers:
                    messages.error(request, "Column 'is_active' is not allowed in bulk creation CSV. Please remove it.")
                    return redirect('integration:bulk_item_creation')
                missing_required = sorted(list(required_headers - set(headers)))
                unknown_headers = sorted([h for h in headers if h and h not in allowed_headers])
                if missing_required:
                    messages.error(request, f"Missing required columns: {', '.join(missing_required)}. The file was rejected.")
                    return redirect('integration:bulk_item_creation')
                if unknown_headers:
                    messages.error(request, f"Unknown columns present: {', '.join(unknown_headers)}. Only defined headers are allowed. The file was rejected.")
                    return redirect('integration:bulk_item_creation')
                
                errors = []
                BATCH_SIZE = 1000
                
                # Collect one unique row per SKU from CSV (deduplicate within upload)
                unique_rows_by_sku = {}
                duplicate_skus_in_csv = []
                # OPTIMIZATION: Track wrap=10000 items by (item_code, units) for O(1) duplicate check
                wrap10000_pairs_in_csv = {}  # {(item_code, units): sku}
                
                for row_num, original_row in enumerate(csv_reader, start=2):  # Start from 2 (header is row 1)
                    try:
                        from django.utils.html import escape
                        
                        # Normalize row keys to lowercase for consistent access
                        row = {k.lower().strip(): v for k, v in original_row.items()}
                        
                        base_item_code = escape(row.get('item_code', '').strip())
                        base_sku = escape(row.get('sku', '').strip())
                        
                        # Validate mandatory fields first
                        mandatory_fields = {
                            'wrap': escape(row.get('wrap', '').strip()),
                            'item_code': base_item_code,
                            'description': escape(row.get('description', '').strip()),
                            'units': escape(row.get('units', '').strip()),
                            'sku': base_sku,
                            'pack_description': escape(row.get('pack_description', '').strip())
                        }
                        
                        missing_fields = [field for field, value in mandatory_fields.items() if not value]
                        if missing_fields:
                            errors.append(f"Row {row_num}: Missing mandatory fields: {', '.join(missing_fields)}")
                            continue

                        # Validate wrap strictly
                        if mandatory_fields['wrap'] not in ALLOWED_WRAP_VALUES:
                            errors.append(f"Row {row_num}: Wrap must be 9900 or 10000 (got '{mandatory_fields['wrap']}')")
                            continue
                        
                        # No additional mandatory field validation needed

                        # Optional fields parsing
                        barcode = escape(row.get('barcode', '').strip())
                        # NOTE: mrp, selling_price, cost, stock are OUTLET-SPECIFIC
                        # They should NOT be set during item creation (always default to 0)
                        weight_division_factor_str = row.get('weight_division_factor', '').strip()
                        outer_case_quantity_str = row.get('outer_case_quantity', '').strip()
                        minimum_qty_str = row.get('minimum_qty', '').strip()

                        # Defaults (outlet-specific fields always 0)
                        weight_division_factor = None
                        outer_case_quantity = None
                        minimum_qty = None

                        # Numeric validations for optional fields
                        try:
                            if weight_division_factor_str:
                                weight_division_factor = Decimal(weight_division_factor_str)
                            if outer_case_quantity_str:
                                outer_case_quantity = int(outer_case_quantity_str)
                            if minimum_qty_str:
                                minimum_qty = int(minimum_qty_str)
                        except (InvalidOperation, ValueError):
                            errors.append(f"Row {row_num}: Invalid numeric values in one of [weight_division_factor, outer_case_quantity, minimum_qty]")
                            continue

                        # No boolean parsing; is_active not allowed in CSV
                        
                        # WRAP=10000 SPECIFIC: Check for duplicates by (item_code, units) within CSV
                        # OPTIMIZATION: Use dictionary lookup O(1) instead of loop O(n)
                        is_duplicate_in_csv = False
                        if mandatory_fields['wrap'] == '10000':
                            pair = (base_item_code, mandatory_fields['units'])
                            if pair in wrap10000_pairs_in_csv:
                                # This pair already exists in CSV with a different SKU
                                if base_sku not in duplicate_skus_in_csv:
                                    duplicate_skus_in_csv.append(base_sku)
                                is_duplicate_in_csv = True
                        
                        # Skip this row if it's a wrap=10000 duplicate
                        if is_duplicate_in_csv:
                            continue
                        
                        # Deduplicate within the uploaded file (by SKU)
                        if base_sku in unique_rows_by_sku:
                            if base_sku not in duplicate_skus_in_csv:
                                duplicate_skus_in_csv.append(base_sku)
                            continue
                        
                        # Store normalized data for later bulk_create
                        unique_rows_by_sku[base_sku] = {
                            'platform': platform,  # Platform isolation
                            'item_code': base_item_code,
                            'description': mandatory_fields['description'],
                            'pack_description': mandatory_fields['pack_description'],
                            'units': mandatory_fields['units'],
                            'sku': base_sku,
                            'barcode': barcode,
                            'wrap': mandatory_fields['wrap'],
                            # Item configuration fields
                            'weight_division_factor': weight_division_factor,
                            'outer_case_quantity': outer_case_quantity,
                            'minimum_qty': minimum_qty,
                            # Outlet-specific fields (always default to 0)
                            'selling_price': 0,
                            'stock': 0,
                            'cost': 0,
                            'mrp': 0,
                        }
                        
                        # Track wrap=10000 pairs for future duplicate checking
                        if mandatory_fields['wrap'] == '10000':
                            pair = (base_item_code, mandatory_fields['units'])
                            wrap10000_pairs_in_csv[pair] = base_sku
                    except Exception as e:
                        logger.error(f"Bulk item creation error - Row {row_num}: {type(e).__name__}: {str(e)}", exc_info=True)
                        errors.append(f"Row {row_num}: Error parsing row - {str(e)}")

                unique_skus = list(unique_rows_by_sku.keys())
                # Items are identified by platform + SKU (unique per platform)
                # Same SKU on different platforms = TWO separate Item records
                # WRAP=10000: Also check for duplicates by (item_code, units) in DATABASE
                
                # Find items that already exist for THIS platform (by platform + SKU)
                existing_items_for_platform = Item.objects.filter(
                    platform=platform,
                    sku__in=unique_skus
                )
                
                # Map by SKU
                existing_items_map = {item.sku: item for item in existing_items_for_platform}
                
                # For wrap=10000 items: Check if (item_code, units) already exists in database
                # OPTIMIZATION: Use simpler approach - avoid massive OR conditions
                wrap10000_duplicates_in_db = []
                
                # Collect all wrap=10000 items to check
                wrap10000_items_to_check = [
                    (sku, row_data) for sku, row_data in unique_rows_by_sku.items()
                    if row_data.get('wrap') == '10000' and sku not in existing_items_map
                ]
                
                # ONLY check database if there are wrap=10000 items in CSV
                if wrap10000_items_to_check:
                    # Get ALL wrap=10000 items for this platform in one simple query (no OR conditions)
                    all_wrap10000_in_db = Item.objects.filter(
                        wrap='10000',
                        platform=platform
                    ).values_list('item_code', 'units')
                    
                    existing_pairs = set(all_wrap10000_in_db)
                    
                    # Mark SKUs as duplicates if their (item_code, units) pair exists in database
                    for sku, row_data in wrap10000_items_to_check:
                        pair = (row_data.get('item_code'), row_data.get('units'))
                        if pair in existing_pairs:
                            wrap10000_duplicates_in_db.append(sku)
                            duplicate_skus_in_csv.append(sku)
                
                # Items to CREATE: SKU doesn't exist on THIS platform AND not a wrap=10000 duplicate
                # Items to UPDATE: SKU exists on THIS platform
                to_create_skus = [sku for sku in unique_skus if sku not in existing_items_map and sku not in wrap10000_duplicates_in_db]
                
                items_to_create = [
                    Item(**unique_rows_by_sku[sku])
                    for sku in to_create_skus
                ]
                
                # If any errors were detected, reject entire file without creating
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        messages.error(request, error)
                    if len(errors) > 5:
                        messages.warning(request, f"And {len(errors) - 5} more errors...")
                    # Persist a structured breakdown to show on page
                    try:
                        request.session['bulk_creation_summary'] = {
                            'platform': platform,
                            'outlet_count': outlets.count(),
                            'outlet_names': [o.name for o in outlets],
                            'created_count': 0,
                            'existing_count': 0,
                            'associations_attempted': 0,
                            'associations_created_new_items': 0,
                            'unique_csv_skus': len(unique_skus),
                            'duplicate_skus': duplicate_skus_in_csv,
                            'error_messages': errors,
                            'upload_file_name': getattr(csv_file, 'name', ''),
                        }
                    except Exception:
                        pass
                    messages.error(request, 'CSV validation failed; the file was rejected. Fix the reported issues and try again.')
                    return redirect('integration:bulk_item_creation')

                # Create items in bulk for THIS platform
                created_items_qs = []
                updated_items_count = 0
                with transaction.atomic():
                    if items_to_create:
                        # Get SKUs being created (unique identifiers for this batch)
                        skus_to_create = to_create_skus
                        
                        Item.objects.bulk_create(items_to_create, batch_size=BATCH_SIZE)
                        
                        # Refetch created items by platform + SKU (not just SKU)
                        created_items_qs = list(Item.objects.filter(platform=platform, sku__in=skus_to_create))
                    
                    # UPDATE existing items on THIS platform with new data from CSV
                    for sku, item in existing_items_map.items():
                        csv_data = unique_rows_by_sku.get(sku)
                        if csv_data:
                            # Update fields with new data (only if CSV has value)
                            if csv_data.get('barcode'):
                                item.barcode = csv_data['barcode']
                            if csv_data.get('units'):
                                item.units = csv_data['units']
                            if csv_data.get('description'):
                                item.description = csv_data['description']
                            if csv_data.get('pack_description'):
                                item.pack_description = csv_data['pack_description']
                            if csv_data.get('wrap'):
                                item.wrap = csv_data['wrap']
                            if csv_data.get('weight_division_factor') is not None:
                                item.weight_division_factor = csv_data['weight_division_factor']
                            if csv_data.get('outer_case_quantity') is not None:
                                item.outer_case_quantity = csv_data['outer_case_quantity']
                            if csv_data.get('minimum_qty') is not None:
                                item.minimum_qty = csv_data['minimum_qty']
                            item.save()
                            updated_items_count += 1
                
                # NOTE: Item creation NO LONGER auto-assigns items to outlets
                # Items are only assigned to outlets when price/stock is updated via:
                # - /price-update/
                # - /stock-update/
                # - /product-update/
                
                total_items_created = len(created_items_qs)
                
                # Build clear success message
                if total_items_created > 0:
                    messages.success(request, f"Successfully created {total_items_created} items for {platform.title()} platform.")
                
                if updated_items_count > 0:
                    messages.info(request, f"Updated {updated_items_count} existing items with new data.")
                
                if duplicate_skus_in_csv:
                    if len(duplicate_skus_in_csv) <= 5:
                        messages.info(request, f"Duplicate SKUs in CSV ignored: {', '.join(duplicate_skus_in_csv)}")
                    else:
                        messages.info(request, f"Duplicate SKUs in CSV (first 5): {', '.join(duplicate_skus_in_csv[:5])}... and {len(duplicate_skus_in_csv) - 5} more.")
                
                # Show warning only if truly nothing was processed
                if total_items_created == 0 and updated_items_count == 0 and not errors:
                    messages.warning(request, "No items were processed. Please check your CSV file format and content.")
                
                # Build detailed duplicate information
                # Group duplicates by (item_code, units) combination
                duplicates_detailed = {}
                for sku in duplicate_skus_in_csv:
                    row_data = unique_rows_by_sku.get(sku)
                    if row_data:
                        key = f"{row_data.get('item_code')}|{row_data.get('units')}"
                        if key not in duplicates_detailed:
                            duplicates_detailed[key] = {
                                'item_code': row_data.get('item_code'),
                                'units': row_data.get('units'),
                                'skipped_skus': [],
                                'wrap_type': row_data.get('wrap')
                            }
                        duplicates_detailed[key]['skipped_skus'].append({
                            'sku': sku,
                            'description': row_data.get('description', ''),
                            'reason': 'wrap=10000 duplicate - first occurrence kept'
                        })
                                
                # Convert to list for JSON serialization
                duplicates_list = list(duplicates_detailed.values())
                                
                # At this point, no errors remain; creation has succeeded or associated
                
                # Persist a structured breakdown for the next page render
                try:
                    request.session['bulk_creation_summary'] = {
                        'platform': platform,
                        'created_count': total_items_created,
                        'updated_count': updated_items_count,
                        'existing_count': len(existing_items_map),
                        'unique_csv_skus': len(unique_skus),
                        'duplicate_skus': duplicate_skus_in_csv,
                        'duplicates_detailed': duplicates_list,  # NEW: Detailed duplicate info
                        'error_messages': errors,
                        'upload_file_name': getattr(csv_file, 'name', ''),
                    }
                except Exception:
                    # If session write fails for any reason, continue with redirect
                    pass
                
                # Log upload history
                from .models import UploadHistory
                total_records = len(unique_skus)
                upload_status = 'success' if not errors else ('partial' if total_items_created > 0 else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform=platform,
                    outlet=None,  # Bulk creation is global
                    update_type='bulk_creation',
                    records_total=total_records,
                    records_success=total_items_created + updated_items_count,
                    records_failed=len(errors),
                    records_skipped=len(existing_items_map),
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )

                return redirect('integration:bulk_item_creation')
                
            except Exception as e:
                logger.error(f"Bulk item creation CSV processing failed: {type(e).__name__}: {str(e)}", exc_info=True)
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            from django.contrib import messages
            if not platform:
                messages.error(request, "Please select a platform.")
            elif not csv_file:
                messages.error(request, "Please select a CSV file.")
            else:
                messages.error(request, "Please fill all required fields and select a CSV file.")
    
    # Get all active outlets for initial load (will be filtered by JavaScript)
    from .models import Outlet
    outlets = Outlet.objects.filter(is_active=True).order_by('name')
    
    # Pull structured breakdown from session (if available)
    bulk_summary = request.session.pop('bulk_creation_summary', None)

    context = {
        'page_title': 'Bulk Item Creation',
        'active_nav': 'bulk_operations',
        'outlets': outlets,
        'bulk_summary': bulk_summary
    }
    return render(request, 'bulk_item_creation.html', context)


@login_required
def get_outlets_by_platform(request):
    """
    AJAX endpoint to get outlets filtered by platform
    """
    platform = request.GET.get('platform')
    
    if not platform:
        return JsonResponse({'outlets': []})
    
    from .models import Outlet
    from django.db import models
    
    # Filter outlets based on platform
    if platform == 'all':
        # Return all active outlets when 'all' is selected
        outlets = Outlet.objects.filter(is_active=True).order_by('name')
    elif platform in ['pasons', 'talabat']:
        # STRICT platform isolation - no 'both'
        outlets = Outlet.objects.filter(
            is_active=True,
            platforms=platform
        ).order_by('name')
    else:
        # Return empty list for invalid platforms
        return JsonResponse({'outlets': []})
    
    outlets_data = []
    for outlet in outlets:
        outlets_data.append({
            'id': outlet.id,
            'name': outlet.name,
            'store_id': outlet.store_id,
            'location': outlet.location,
            'platforms': outlet.platforms
        })
    
    return JsonResponse({'outlets': outlets_data})


def product_update(request):
    """
    Product update view for updating existing products via CSV
    Uses Item Code + Units combination as unique identifier within platform
    
    Required CSV headers: item_code, units
    Optional CSV headers: mrp, cost, stock
    
    OPTIMIZED: Uses hash-based change detection for 15-20x faster updates
    - Industry-standard CDC (Change Data Capture) approach
    - O(1) hash comparison skips unchanged rows
    - bulk_update for database efficiency
    """
    from .models import Outlet, Item, ItemOutlet
    from .utils import compute_data_hash, update_item_outlet_hash
    from django.contrib import messages
    from decimal import Decimal, InvalidOperation
    
    if request.method == 'POST':
        platform = request.POST.get('platform')
        outlet_id = request.POST.get('outlet')
        csv_file = request.FILES.get('csv_file')
        
        if platform and outlet_id and csv_file:
            try:
                outlet = Outlet.objects.get(id=outlet_id)
                
                if outlet.platforms != platform:  # STRICT isolation
                    messages.error(request, f"Outlet '{outlet.name}' does not support {platform.title()} platform.")
                    return redirect('integration:product_update')
                
                import csv
                import io
                
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                if not csv_reader.fieldnames:
                    messages.error(request, "CSV file has no headers")
                    return redirect('integration:product_update')
                
                # Filter out empty header fields (from trailing delimiters)
                headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
                
                # STRICT HEADER VALIDATION: Only these headers allowed
                allowed_headers = {'item_code', 'units', 'mrp', 'cost', 'stock'}
                required_headers = {'item_code', 'units'}
                
                # Check for missing required headers
                missing = required_headers - set(headers)
                if missing:
                    messages.error(request, f"Missing required columns: {', '.join(sorted(missing))}")
                    return redirect('integration:product_update')
                
                # Check for invalid/extra headers
                extra_headers = set(headers) - allowed_headers
                if extra_headers:
                    messages.error(request, f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, mrp, cost, stock")
                    return redirect('integration:product_update')
                
                # Parse all rows first
                csv_rows = []
                for row_num, original_row in enumerate(csv_reader, start=2):
                    row = {k.strip().lower(): v.strip() if v else '' for k, v in original_row.items()}
                    if row.get('item_code') and row.get('units'):
                        csv_rows.append((row_num, row))
                
                if not csv_rows:
                    messages.warning(request, "No valid rows found in CSV")
                    return redirect('integration:product_update')
                
                # Build lookup keys for bulk prefetch
                lookup_keys = [(r['item_code'], r['units']) for _, r in csv_rows]
                
                # Chunked bulk fetch to avoid "Expression tree too large" error
                # Process in batches of 400 to stay under Django's 1000 limit
                from django.db.models import Q
                CHUNK_SIZE = 400
                items_map = {}
                
                for i in range(0, len(lookup_keys), CHUNK_SIZE):
                    chunk = lookup_keys[i:i + CHUNK_SIZE]
                    item_filter = Q()
                    for item_code, units in chunk:
                        item_filter |= Q(item_code=item_code, units=units)
                    
                    chunk_items = Item.objects.filter(platform=platform).filter(item_filter)
                    for item in chunk_items:
                        key = (item.item_code, item.units)
                        # For wrap=9900 items with multiple SKUs (same item_code+units),
                        # prioritize the PARENT item (SKU == item_code) for cascade to work
                        existing = items_map.get(key)
                        if existing is None:
                            items_map[key] = item
                        elif item.wrap == '9900':
                            # Check if current item is parent (SKU == item_code)
                            is_current_parent = str(item.sku).strip() == str(item.item_code).strip()
                            is_existing_parent = str(existing.sku).strip() == str(existing.item_code).strip()
                            # Prioritize parent over child for cascade to work
                            if is_current_parent and not is_existing_parent:
                                items_map[key] = item
                
                # Bulk fetch existing ItemOutlet relationships
                all_items = list(items_map.values())
                outlets_map = {}
                
                for i in range(0, len(all_items), CHUNK_SIZE):
                    chunk_items = all_items[i:i + CHUNK_SIZE]
                    chunk_outlets = ItemOutlet.objects.filter(
                        item__in=chunk_items,
                        outlet=outlet
                    ).select_related('item')
                    for io in chunk_outlets:
                        outlets_map[io.item_id] = io
                
                # ============================================================
                # PERFORMANCE: Pre-fetch ALL sibling items for wrap=9900 parents
                # This prevents N+1 queries in the cascade loop
                # ============================================================
                parent_item_codes = set()
                for item in all_items:
                    if item.wrap == '9900':
                        wdf = item.weight_division_factor or Decimal('1')
                        if wdf == Decimal('1'):  # Parent item
                            parent_item_codes.add(item.item_code)
                
                # Bulk fetch ALL sibling items for these parents
                siblings_map = {}  # {item_code: [sibling_items...]}
                if parent_item_codes:
                    parent_codes_list = list(parent_item_codes)
                    for i in range(0, len(parent_codes_list), CHUNK_SIZE):
                        chunk_codes = parent_codes_list[i:i + CHUNK_SIZE]
                        sibling_items = Item.objects.filter(
                            item_code__in=chunk_codes,
                            platform=platform,
                            wrap='9900'
                        ).exclude(weight_division_factor=Decimal('1')).exclude(weight_division_factor__isnull=True)
                        for sib in sibling_items:
                            if sib.item_code not in siblings_map:
                                siblings_map[sib.item_code] = []
                            siblings_map[sib.item_code].append(sib)
                
                # Bulk fetch ItemOutlets for ALL sibling items
                all_sibling_items = [sib for sibs in siblings_map.values() for sib in sibs]
                sibling_outlets_map = {}  # {item_id: ItemOutlet}
                if all_sibling_items:
                    for i in range(0, len(all_sibling_items), CHUNK_SIZE):
                        chunk_sibs = all_sibling_items[i:i + CHUNK_SIZE]
                        chunk_sib_outlets = ItemOutlet.objects.filter(
                            item__in=chunk_sibs,
                            outlet=outlet
                        ).select_related('item')
                        for sio in chunk_sib_outlets:
                            sibling_outlets_map[sio.item_id] = sio
                
                # Lists for collecting cascade updates (bulk save at end)
                sibling_items_to_update = []
                sibling_outlets_to_update = []
                sibling_outlets_to_create = []
                
                # Process rows and collect updates
                items_to_update = []
                outlets_to_update = []
                outlets_to_create = []
                updated_count = 0
                not_found_items = []
                errors = []
                no_change_count = 0
                
                for row_num, row in csv_rows:
                    try:
                        item_code = row['item_code']
                        units = row['units']
                        
                        item = items_map.get((item_code, units))
                        if not item:
                            not_found_items.append(f"{item_code} ({units})")
                            continue
                        
                        # Get or prepare ItemOutlet
                        item_outlet = outlets_map.get(item.id)
                        if not item_outlet:
                            item_outlet = ItemOutlet(
                                item=item,
                                outlet=outlet,
                                outlet_stock=item.stock or 0,
                                outlet_selling_price=item.selling_price or Decimal('0'),
                                outlet_mrp=item.mrp or Decimal('0'),
                                is_active_in_outlet=True
                            )
                            outlets_map[item.id] = item_outlet
                            outlets_to_create.append(item_outlet)
                        
                        # ============================================================
                        # HASH-BASED CHANGE DETECTION (Industry-standard CDC approach)
                        # Skip unchanged rows for 15-20x performance improvement
                        # ============================================================
                        mrp_str = row.get('mrp', '')
                        cost_str = row.get('cost', '')
                        stock_str = row.get('stock', '')
                        
                        # Compute hash of incoming CSV data
                        mrp_clean = mrp_str.replace(',', '') if mrp_str else None
                        cost_clean = cost_str.replace(',', '') if cost_str else None
                        stock_clean = stock_str.replace(',', '') if stock_str else None
                        incoming_hash = compute_data_hash(mrp=mrp_clean, cost=cost_clean, stock=stock_clean)
                        
                        # Early exit: If hash matches, skip this row (no changes detected)
                        if item_outlet.data_hash and item_outlet.data_hash == incoming_hash:
                            no_change_count += 1
                            continue  # Skip to next row - O(1) optimization!
                        
                        item_changed = False
                        outlet_changed = False
                        
                        # Update MRP and calculate selling_price
                        if mrp_str:
                            try:
                                # Remove commas from formatted numbers
                                mrp_clean = mrp_str.replace(',', '')
                                new_mrp = Decimal(mrp_clean)
                                if new_mrp < 0:
                                    new_mrp = Decimal('0')
                                if item.mrp != new_mrp:
                                    item.mrp = new_mrp
                                    item_changed = True
                                    
                                    # Calculate selling_price based on platform and wrap
                                    # Import PricingCalculator for Talabat margin calculations
                                    from .utils import PricingCalculator
                                    
                                    if item.wrap == '9900':
                                        # wrap=9900: Parent=MRP, Child=MRP÷WDF
                                        wdf = item.weight_division_factor or Decimal('1')
                                        # Use WDF to detect parent (WDF=1 means 1 KG = parent)
                                        # SKU can be any value from CSV, so we use WDF instead
                                        is_parent = wdf == Decimal('1')
                                        
                                        if platform == 'talabat':
                                            # Talabat: Apply margin calculation
                                            calc = PricingCalculator()
                                            if is_parent:
                                                # Parent: Use MRP directly with margin
                                                new_selling_price, _ = calc.calculate_talabat_price(
                                                    new_mrp,
                                                    margin_percentage=item.effective_talabat_margin
                                                )
                                            else:
                                                # Child: First divide MRP by WDF, then apply margin
                                                base_price = (new_mrp / wdf).quantize(Decimal('0.01'))
                                                new_selling_price, _ = calc.calculate_talabat_price(
                                                    base_price,
                                                    margin_percentage=item.effective_talabat_margin
                                                )
                                        else:
                                            # Pasons: No margin applied
                                            if is_parent:
                                                new_selling_price = new_mrp
                                            else:
                                                new_selling_price = (new_mrp / wdf).quantize(Decimal('0.01'))
                                        
                                        item.selling_price = new_selling_price
                                        item_outlet.outlet_selling_price = new_selling_price
                                        outlet_changed = True
                                        
                                    elif item.wrap == '10000' or item.wrap is None:
                                        # wrap=10000 or no wrap: selling_price based on MRP
                                        if platform == 'talabat':
                                            # Talabat: Apply margin calculation
                                            calc = PricingCalculator()
                                            new_selling_price, _ = calc.calculate_talabat_price(
                                                new_mrp,
                                                margin_percentage=item.effective_talabat_margin
                                            )
                                        else:
                                            # Pasons: Just use MRP, no margin
                                            new_selling_price = new_mrp
                                        
                                        item.selling_price = new_selling_price
                                        item_outlet.outlet_selling_price = new_selling_price
                                        outlet_changed = True
                                
                                if item_outlet.outlet_mrp != new_mrp:
                                    item_outlet.outlet_mrp = new_mrp
                                    outlet_changed = True
                            except InvalidOperation:
                                errors.append(f"Row {row_num}: Invalid MRP '{mrp_str}'")
                        
                        # Update Cost and calculate converted_cost
                        # (cost_str already extracted for hash calculation above)
                        if cost_str:
                            try:
                                # Remove commas from formatted numbers
                                cost_clean = cost_str.replace(',', '')
                                new_cost = Decimal(cost_clean)
                                if new_cost < 0:
                                    new_cost = Decimal('0')
                                if item.cost != new_cost:
                                    item.cost = new_cost
                                    # wrap=9900: converted_cost = cost ÷ WDF (3 decimals)
                                    # wrap=10000: converted_cost = cost (no division)
                                    if item.wrap == '9900':
                                        wdf = item.weight_division_factor or Decimal('1')
                                        if wdf > 0:
                                            item.converted_cost = (new_cost / wdf).quantize(Decimal('0.001'))
                                    else:
                                        item.converted_cost = new_cost
                                    item_changed = True
                                
                                # Update OUTLET-LEVEL cost
                                # Store RAW cost (same as item.cost) - conversion happens in converted_cost
                                # This prevents double-division when displaying
                                if item_outlet.outlet_cost != new_cost:
                                    item_outlet.outlet_cost = new_cost
                                    outlet_changed = True
                            except InvalidOperation:
                                errors.append(f"Row {row_num}: Invalid cost '{cost_str}'")
                        
                        # Update Stock
                        # (stock_str already extracted for hash calculation above)
                        if stock_str:
                            try:
                                # Remove commas from formatted numbers (e.g., "1,350.00" → "1350.00")
                                stock_clean = stock_str.replace(',', '')
                                csv_stock_kg = int(float(stock_clean))
                                if csv_stock_kg < 0:
                                    csv_stock_kg = 0
                                
                                # For wrap=9900: stock_kg × WDF = available units for this size
                                # Example: 3 KG × WDF 4 = 12 packs (for 250gm item)
                                if item.wrap == '9900':
                                    wdf = item.weight_division_factor or Decimal('1')
                                    new_stock = int(csv_stock_kg * float(wdf))
                                else:
                                    new_stock = csv_stock_kg
                                
                                if item.stock != new_stock:
                                    item.stock = new_stock
                                    item_changed = True
                                if item_outlet.outlet_stock != new_stock:
                                    item_outlet.outlet_stock = new_stock
                                    outlet_changed = True
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid stock '{stock_str}'")
                        
                        # ============================================================
                        # CASCADE LOGIC: Parent to Children ONLY
                        # For wrap=9900 items, cascade from PARENT (WDF=1) to children (WDF>1)
                        # Do NOT cascade from children back to parent!
                        # ============================================================
                        # Only cascade if this item is a PARENT (WDF=1)
                        wdf_for_cascade = item.weight_division_factor or Decimal('1')
                        is_cascade_parent = wdf_for_cascade == Decimal('1')
                        has_mrp_to_cascade = bool(mrp_str)
                        has_cost_to_cascade = bool(cost_str)
                        has_stock_to_cascade = bool(stock_str)
                        
                        # Only cascade FROM parent (WDF=1) TO children (WDF>1)
                        # OPTIMIZED: Use pre-fetched siblings_map instead of querying per row
                        if item.wrap == '9900' and is_cascade_parent and (has_mrp_to_cascade or has_cost_to_cascade or has_stock_to_cascade):
                            # Get pre-fetched sibling items (no DB query here!)
                            sibling_items_list = siblings_map.get(item_code, [])
                            
                            for sibling_item in sibling_items_list:
                                try:
                                    # Skip self
                                    if sibling_item.sku == item.sku:
                                        continue
                                        
                                    sibling_wdf = sibling_item.weight_division_factor or Decimal('1')
                                    
                                    # Only cascade to CHILDREN (WDF > 1), not to other parents
                                    if sibling_wdf == Decimal('1'):
                                        continue
                                    
                                    # Only cascade if SKU starts with item_code (e.g., 9900422 -> 9900422500)
                                    if not str(sibling_item.sku).startswith(str(item_code)):
                                        continue
                                    
                                    # Only cascade if units match (normalized - remove dots, lowercase)
                                    parent_units = (item.units or '').replace('.', '').lower().strip()
                                    child_units = (sibling_item.units or '').replace('.', '').lower().strip()
                                    if parent_units != child_units:
                                        continue
                                    
                                    if sibling_wdf != 0:
                                        # OPTIMIZED: Use pre-fetched outlet or create new (no DB query!)
                                        sibling_item_outlet = sibling_outlets_map.get(sibling_item.id)
                                        sibling_is_new = sibling_item_outlet is None
                                        
                                        if sibling_is_new:
                                            sibling_item_outlet = ItemOutlet(
                                                item=sibling_item,
                                                outlet=outlet,
                                                outlet_stock=sibling_item.stock or 0,
                                                is_active_in_outlet=True
                                            )
                                            sibling_outlets_map[sibling_item.id] = sibling_item_outlet
                                        
                                        sibling_item_changed = False
                                        sibling_outlet_changed = False
                                        
                                        # CASCADE MRP: sibling_selling_price = csv_mrp ÷ sibling_wdf
                                        if has_mrp_to_cascade:
                                            virtual_parent_mrp = Decimal(mrp_str.replace(',', ''))
                                            sibling_mrp = virtual_parent_mrp  # Sibling uses same MRP
                                            if sibling_item_outlet.outlet_mrp != sibling_mrp:
                                                sibling_item_outlet.outlet_mrp = sibling_mrp
                                                sibling_outlet_changed = True
                                            
                                            # Calculate sibling selling_price
                                            if platform == 'talabat':
                                                from .utils import PricingCalculator
                                                base_price = (virtual_parent_mrp / sibling_wdf).quantize(Decimal('0.01'))
                                                calc = PricingCalculator()
                                                sibling_selling_price, _ = calc.calculate_talabat_price(
                                                    base_price,
                                                    margin_percentage=sibling_item.effective_talabat_margin
                                                )
                                            else:
                                                # Pasons: sibling_selling_price = csv_mrp ÷ sibling_wdf
                                                sibling_selling_price = (virtual_parent_mrp / sibling_wdf).quantize(Decimal('0.01'))
                                            
                                            if sibling_item_outlet.outlet_selling_price != sibling_selling_price:
                                                sibling_item_outlet.outlet_selling_price = sibling_selling_price
                                                sibling_outlet_changed = True
                                        
                                        # CASCADE COST: Store raw cost, calculate converted_cost
                                        if has_cost_to_cascade:
                                            virtual_parent_cost = Decimal(cost_str.replace(',', ''))
                                            if virtual_parent_cost < 0:
                                                virtual_parent_cost = Decimal('0')
                                            if sibling_item_outlet.outlet_cost != virtual_parent_cost:
                                                sibling_item_outlet.outlet_cost = virtual_parent_cost
                                                sibling_outlet_changed = True
                                            
                                            # Update sibling item: cost = raw, converted_cost = cost/WDF
                                            converted_cost = (virtual_parent_cost / sibling_wdf).quantize(Decimal('0.001'))
                                            if converted_cost < 0:
                                                converted_cost = Decimal('0')
                                            if sibling_item.cost != virtual_parent_cost:
                                                sibling_item.cost = virtual_parent_cost
                                                sibling_item.converted_cost = converted_cost
                                                sibling_item_changed = True
                                        
                                        # CASCADE STOCK: stock_kg × WDF = available units
                                        if has_stock_to_cascade:
                                            virtual_parent_stock = int(float(stock_str.replace(',', '')))
                                            sibling_stock = int(virtual_parent_stock * float(sibling_wdf))
                                            sibling_stock = max(0, sibling_stock)
                                            if sibling_item_outlet.outlet_stock != sibling_stock:
                                                sibling_item_outlet.outlet_stock = sibling_stock
                                                sibling_outlet_changed = True
                                            if sibling_item.stock != sibling_stock:
                                                sibling_item.stock = sibling_stock
                                                sibling_item_changed = True
                                        
                                        # Collect for bulk update (no individual save!)
                                        if sibling_item_changed and sibling_item not in sibling_items_to_update:
                                            sibling_items_to_update.append(sibling_item)
                                        
                                        if sibling_outlet_changed or sibling_is_new:
                                            update_item_outlet_hash(sibling_item_outlet)
                                            if sibling_is_new:
                                                if sibling_item_outlet not in sibling_outlets_to_create:
                                                    sibling_outlets_to_create.append(sibling_item_outlet)
                                            elif sibling_item_outlet not in sibling_outlets_to_update:
                                                sibling_outlets_to_update.append(sibling_item_outlet)
                                        
                                except Exception as cascade_error:
                                    errors.append(f"Row {row_num}: Cascade failed for {sibling_item.sku} - {str(cascade_error)}")
                        
                        # Track changes
                        if item_changed:
                            items_to_update.append(item)
                        if outlet_changed and item_outlet not in outlets_to_create:
                            # Update data_hash for future change detection
                            update_item_outlet_hash(item_outlet)
                            outlets_to_update.append(item_outlet)
                        
                        # Also update hash for newly created outlets
                        if item_outlet in outlets_to_create and outlet_changed:
                            update_item_outlet_hash(item_outlet)
                        
                        if item_changed or outlet_changed:
                            updated_count += 1
                        else:
                            no_change_count += 1
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                
                # Bulk create new ItemOutlets
                if outlets_to_create:
                    ItemOutlet.objects.bulk_create(outlets_to_create, ignore_conflicts=True)
                
                # Bulk update Items
                if items_to_update:
                    Item.objects.bulk_update(
                        items_to_update,
                        ['mrp', 'cost', 'stock', 'converted_cost', 'selling_price'],
                        batch_size=500
                    )
                
                # Bulk update ItemOutlets (including data_hash for future change detection)
                if outlets_to_update:
                    ItemOutlet.objects.bulk_update(
                        outlets_to_update,
                        ['outlet_mrp', 'outlet_stock', 'outlet_selling_price', 'outlet_cost', 'data_hash'],
                        batch_size=500
                    )
                
                # PERFORMANCE: Bulk operations for CASCADE sibling items/outlets
                # This replaces individual saves in the cascade loop
                if sibling_items_to_update:
                    Item.objects.bulk_update(
                        sibling_items_to_update,
                        ['cost', 'converted_cost', 'stock'],
                        batch_size=500
                    )
                
                if sibling_outlets_to_create:
                    ItemOutlet.objects.bulk_create(sibling_outlets_to_create, ignore_conflicts=True)
                
                if sibling_outlets_to_update:
                    ItemOutlet.objects.bulk_update(
                        sibling_outlets_to_update,
                        ['outlet_mrp', 'outlet_stock', 'outlet_selling_price', 'outlet_cost', 'data_hash'],
                        batch_size=500
                    )
                
                # Success message
                if updated_count > 0:
                    messages.success(request, f"Updated {updated_count} products at {outlet.name} ({platform.title()}).")
                if no_change_count > 0:
                    messages.info(request, f"{no_change_count} products already up-to-date (no changes).")
                if not_found_items:
                    messages.warning(request, f"{len(not_found_items)} items not found on {platform.title()}.")
                if errors:
                    for error in errors[:3]:
                        messages.error(request, error)
                    if len(errors) > 3:
                        messages.warning(request, f"And {len(errors) - 3} more errors...")
                
                # Log upload history
                from .models import UploadHistory
                upload_status = 'success' if not errors else ('partial' if updated_count > 0 else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform=platform,
                    outlet=outlet,
                    update_type='product',
                    records_total=len(csv_rows),
                    records_success=updated_count,
                    records_failed=len(errors),
                    records_skipped=len(not_found_items) + no_change_count,
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                
                return redirect('integration:product_update')
                
            except Outlet.DoesNotExist:
                messages.error(request, "Selected outlet not found.")
            except Exception as e:
                messages.error(request, f"Error processing CSV: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields and select a CSV file.")
    
    # Get outlets for both platforms
    outlets = Outlet.objects.filter(is_active=True).order_by('platforms', 'name')
    
    context = {
        'page_title': 'Product Update',
        'active_nav': 'bulk_operations',
        'outlets': outlets,
        'platforms': ['pasons', 'talabat']
    }
    return render(request, 'product_update.html', context)


@login_required
@rate_limit(max_requests=20, time_window_seconds=60)  # 20 requests per minute
def stock_update(request):
    """
    Stock update view for updating stock quantities via CSV
    Uses Item Code + Units combination as unique identifier within platform
    
    Required CSV headers: item_code, units, stock
    """
    from .models import Outlet, Item, ItemOutlet
    from django.contrib import messages
    
    if request.method == 'POST':
        # Handle CSV upload and stock updates
        platform = request.POST.get('platform')
        outlet_id = request.POST.get('outlet')
        operation = request.POST.get('operation')
        csv_file = request.FILES.get('csv_file')
        
        # Validate operation parameter - only SET operation allowed
        valid_operations = {'set'}
        if operation and operation not in valid_operations:
            messages.error(request, f"Invalid operation '{operation}'. Only 'set' (replace stock) is allowed.")
            return redirect('integration:stock_update')
        
        if platform and outlet_id and operation and csv_file:
            try:
                # Get the selected outlet
                outlet = Outlet.objects.get(id=outlet_id)
                
                # Process CSV file
                import csv
                import io
                
                # Read CSV content with encoding fallback
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                # Normalize headers to lowercase
                if csv_reader.fieldnames:
                    headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
                else:
                    messages.error(request, "CSV file has no headers")
                    return redirect('integration:stock_update')
                
                # STRICT HEADER VALIDATION: Only these 3 headers allowed
                allowed_headers = {'item_code', 'units', 'stock'}
                required_headers = {'item_code', 'units', 'stock'}
                
                # Check for missing required headers
                missing = required_headers - set(headers)
                if missing:
                    messages.error(request, f"Missing required columns: {', '.join(sorted(missing))}")
                    return redirect('integration:stock_update')
                
                # Check for invalid/extra headers
                extra_headers = set(headers) - allowed_headers
                if extra_headers:
                    messages.error(request, f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, stock")
                    return redirect('integration:stock_update')
                
                updated_items = []
                not_found_items = []
                errors = []
                
                for row_num, original_row in enumerate(csv_reader, start=2):
                    try:
                        # Normalize row keys to lowercase
                        row = {k.strip().lower(): v for k, v in original_row.items()}
                        
                        item_code = row.get('item_code', '').strip()
                        units = row.get('units', '').strip()
                        stock_value = row.get('stock', '').strip()
                        
                        if not item_code:
                            errors.append(f"Row {row_num}: item_code is required")
                            continue
                        if not units:
                            errors.append(f"Row {row_num}: units is required")
                            continue
                        if not stock_value:
                            errors.append(f"Row {row_num}: stock is required")
                            continue
                        
                        try:
                            # Accept both integers and decimals for weight-based items
                            stock_float = float(stock_value)
                            stock_quantity = int(stock_float) if stock_float == int(stock_float) else stock_float
                            # Replace negative stock with 0 (except for subtract operation)
                            if stock_quantity < 0 and operation != 'subtract':
                                stock_quantity = 0  # Replace negative with 0
                        except ValueError:
                            errors.append(f"Row {row_num}: Stock value must be a number")
                            continue
                        
                        # Find existing item by platform + item_code + units
                        item = Item.objects.filter(platform=platform, item_code=item_code, units=units).first()
                        if not item:
                            not_found_items.append(f"{item_code} ({units})")
                            continue
                        
                        # Get or create ItemOutlet
                        item_outlet, created = ItemOutlet.objects.get_or_create(
                            item=item,
                            outlet=outlet,
                            defaults={
                                'outlet_stock': item.stock,
                                'outlet_selling_price': item.selling_price,
                                'is_active_in_outlet': True
                            }
                        )
                        
                        # SET operation: Replace stock with new value - only if changed
                        new_stock = stock_quantity
                        
                        # ZERO FLOOR: Child SKUs (SKU != item_code) cannot have negative stock
                        is_child_sku = str(item.sku).strip() != str(item.item_code).strip()
                        if is_child_sku and new_stock < 0:
                            new_stock = 0
                        
                        # Track what changed for optimized update
                        item_changed = False
                        outlet_changed = False
                        
                        # Only update Item.stock if different
                        if item.stock != new_stock:
                            item.stock = new_stock
                            item.save(update_fields=['stock'])
                            item_changed = True
                        
                        # Only update ItemOutlet.outlet_stock if different
                        if item_outlet.outlet_stock != new_stock:
                            item_outlet.outlet_stock = new_stock
                            item_outlet.save(update_fields=['outlet_stock'])
                            outlet_changed = True
                        
                        if item_changed or outlet_changed:
                            updated_items.append(f"{item_code} ({units})")
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")
                
                # Success message
                if updated_items:
                    messages.success(request, f"Successfully updated stock for {len(updated_items)} items on {platform.title()} at {outlet.name}.")
                
                # Not found items
                if not_found_items:
                    if len(not_found_items) <= 5:
                        messages.warning(request, f"Items not found on {platform.title()}: {', '.join(not_found_items)}")
                    else:
                        messages.warning(request, f"{len(not_found_items)} items not found on {platform.title()}")
                
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        messages.error(request, error)
                    if len(errors) > 5:
                        messages.warning(request, f"And {len(errors) - 5} more errors...")
                
                # Log upload history
                from .models import UploadHistory
                total_records = len(updated_items) + len(not_found_items) + len(errors)
                upload_status = 'success' if not errors else ('partial' if updated_items else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform=platform,
                    outlet=outlet,
                    update_type='stock',
                    records_total=total_records,
                    records_success=len(updated_items),
                    records_failed=len(errors),
                    records_skipped=len(not_found_items),
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                
                return redirect('integration:stock_update')
                
            except Outlet.DoesNotExist:
                messages.error(request, "Selected outlet not found.")
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields and select a CSV file.")
    
    context = {
        'page_title': 'Stock Update',
        'active_nav': 'bulk_operations'
    }
    return render(request, 'stock_update.html', context)


@login_required
def stock_update_preview(request):
    """
    Preview endpoint for stock update CSV
    Returns preview data in JSON format
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        from .models import Item
        import csv
        import io
        
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        
        if not platform or not csv_file:
            return JsonResponse({'success': False, 'message': 'Platform and CSV file are required'})
        
        # Read CSV content
        csv_content, _encoding_used = decode_csv_upload(csv_file)
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # Normalize headers
        if csv_reader.fieldnames:
            headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
        else:
            return JsonResponse({'success': False, 'message': 'CSV file has no headers'})
        
        # STRICT HEADER VALIDATION: Only these 3 headers allowed
        allowed_headers = {'item_code', 'units', 'stock'}
        required_headers = {'item_code', 'units', 'stock'}
        
        # Check for missing required headers
        missing_headers = [h for h in required_headers if h not in headers]
        if missing_headers:
            return JsonResponse({
                'success': False,
                'message': f"Missing required columns: {', '.join(missing_headers)}"
            })
        
        # Check for invalid/extra headers
        extra_headers = set(headers) - allowed_headers
        if extra_headers:
            return JsonResponse({
                'success': False,
                'message': f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, stock"
            })
        
        rows = []
        errors = []
        total_rows = 0
        preview_limit = 50
        
        for row_num, original_row in enumerate(csv_reader, start=2):
            total_rows += 1
            
            # Normalize row keys
            row = {k.strip().lower(): v for k, v in original_row.items()}
            
            item_code = row.get('item_code', '').strip()
            units = row.get('units', '').strip()
            stock = row.get('stock', '').strip()
            
            row_errors = []
            status = 'valid'
            
            # Validate required fields
            if not item_code:
                row_errors.append('item_code is required')
            if not units:
                row_errors.append('units is required')
            if not stock:
                row_errors.append('stock is required')
            else:
                try:
                    stock_val = float(stock.replace(',', ''))
                    if stock_val < 0:
                        row_errors.append('stock cannot be negative')
                except ValueError:
                    row_errors.append('stock must be a number')
            
            # Check if item exists (only for preview)
            if item_code and units and not row_errors:
                exists = Item.objects.filter(
                    platform=platform,
                    item_code=item_code,
                    units=units
                ).exists()
                if not exists:
                    row_errors.append(f'Item not found in {platform}')
            
            if row_errors:
                status = 'error'
                errors.extend([f"Row {row_num}: {e}" for e in row_errors])
            
            # Only include first N rows in preview
            if len(rows) < preview_limit:
                rows.append({
                    'row_number': row_num,
                    'status': status,
                    'data': {
                        'item_code': item_code,
                        'units': units,
                        'stock': stock
                    },
                    'errors': row_errors
                })
        
        return JsonResponse({
            'success': True,
            'total_rows': total_rows,
            'preview_rows': len(rows),
            'rows': rows,
            'errors': errors[:10],  # Limit displayed errors
            'platform': platform
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error processing CSV: {str(e)}'})


@login_required
@rate_limit(max_requests=20, time_window_seconds=60)  # 20 requests per minute
def price_update(request):
    """
    Price update view for updating product prices via CSV
    Uses Item Code + Units combination as unique identifier within platform
    
    Required CSV headers: item_code, units
    Price headers based on type: selling_price, cost, mrp
    """
    from .models import Outlet, Item, ItemOutlet
    from django.contrib import messages
    from decimal import Decimal, InvalidOperation
    
    if request.method == 'POST':
        # Handle CSV upload and price updates
        platform = request.POST.get('platform')
        outlet_id = request.POST.get('outlet')
        price_type = request.POST.get('price_type')
        csv_file = request.FILES.get('csv_file')
        
        if platform and outlet_id and price_type and csv_file:
            try:
                # Get the selected outlet
                outlet = Outlet.objects.get(id=outlet_id)
                
                # Process CSV file
                import csv
                import io
                
                # Read CSV content with encoding fallback
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                # Normalize headers to lowercase
                if csv_reader.fieldnames:
                    headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
                else:
                    messages.error(request, "CSV file has no headers")
                    return redirect('integration:price_update')
                
                # STRICT HEADER VALIDATION based on price_type
                # Base required headers
                base_headers = {'item_code', 'units'}
                
                # Determine allowed headers based on price_type
                if price_type == 'cost':
                    allowed_headers = {'item_code', 'units', 'cost'}
                    required_headers = {'item_code', 'units', 'cost'}
                elif price_type == 'mrp':
                    allowed_headers = {'item_code', 'units', 'mrp'}
                    required_headers = {'item_code', 'units', 'mrp'}
                elif price_type == 'cost_mrp':
                    allowed_headers = {'item_code', 'units', 'cost', 'mrp'}
                    required_headers = {'item_code', 'units', 'cost', 'mrp'}
                else:
                    messages.error(request, "Invalid price type selected")
                    return redirect('integration:price_update')
                
                # Check for missing required headers
                missing = required_headers - set(headers)
                if missing:
                    messages.error(request, f"Missing required columns: {', '.join(sorted(missing))}")
                    return redirect('integration:price_update')
                
                # Check for invalid/extra headers
                extra_headers = set(headers) - allowed_headers
                if extra_headers:
                    messages.error(request, f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: {', '.join(sorted(allowed_headers))}")
                    return redirect('integration:price_update')
                
                # OPTIMIZATION: Parse CSV once to collect all item codes
                csv_reader_list = list(csv_reader)
                item_keys = set()
                for original_row in csv_reader_list:
                    row = {k.strip().lower(): v for k, v in original_row.items()}
                    item_code = row.get('item_code', '').strip()
                    units = row.get('units', '').strip()
                    if item_code and units:
                        item_keys.add((item_code, units))
                
                # OPTIMIZATION: Batch load items in chunks to avoid "Expression tree too large" error
                # Split item_keys into chunks of 500 to stay within Django's query limit
                items_dict = {}
                item_keys_list = list(item_keys)
                CHUNK_SIZE = 500
                
                for i in range(0, len(item_keys_list), CHUNK_SIZE):
                    chunk = item_keys_list[i:i + CHUNK_SIZE]
                    
                    # Build Q query for this chunk only
                    from django.db.models import Q
                    query = Q()
                    for item_code, units in chunk:
                        query |= Q(item_code=item_code, units=units)
                    
                    # Fetch items for this chunk
                    items_in_chunk = Item.objects.filter(platform=platform).filter(query)
                    for item in items_in_chunk:
                        # Store as LIST to handle multiple items with same (item_code, units)
                        key = (item.item_code, item.units)
                        if key not in items_dict:
                            items_dict[key] = []
                        items_dict[key].append(item)
                
                # OPTIMIZATION: Pre-load all ItemOutlet records for this outlet
                # This prevents get_or_create queries in the loop
                # Flatten items_dict (which now contains lists) to get all item IDs
                item_ids = [item.id for items_list in items_dict.values() for item in items_list]
                existing_item_outlets = ItemOutlet.objects.filter(
                    outlet=outlet,
                    item_id__in=item_ids
                ).select_related('item')
                
                # Build ItemOutlet lookup dictionary
                item_outlet_dict = {}
                for io in existing_item_outlets:
                    item_outlet_dict[io.item_id] = io
                
                updated_items = []
                not_found_items = []
                unchanged_items = []  # Track items that didn't need updating
                errors = []
                items_to_create = []  # For bulk creating new ItemOutlets
                new_item_count = 0  # Track NEW ItemOutlet records
                
                for row_num, original_row in enumerate(csv_reader_list, start=2):
                    try:
                        # Normalize row keys to lowercase
                        row = {k.strip().lower(): v for k, v in original_row.items()}
                        
                        item_code = row.get('item_code', '').strip()
                        units = row.get('units', '').strip()
                        
                        if not item_code:
                            errors.append(f"Row {row_num}: item_code is required")
                            continue
                        if not units:
                            errors.append(f"Row {row_num}: units is required")
                            continue
                        
                        # OPTIMIZATION: Look up items from pre-loaded dictionary (now returns LIST)
                        items_list = items_dict.get((item_code, units))
                        if not items_list:
                            not_found_items.append(f"{item_code} ({units})")
                            continue
                        
                        # CRITICAL FIX: Process ALL items in list, not just the first
                        # Reason: When there's NO PARENT (WDF=1), all SKUs are CHILDREN (WDF>1)
                        # Each child must be updated independently with its own WDF calculation
                        for item_index, item in enumerate(items_list):
                        
                            # OPTIMIZATION: Look up or prepare ItemOutlet from pre-loaded dictionary
                            item_outlet = item_outlet_dict.get(item.id)
                            is_new_item_outlet = False
                            if not item_outlet:
                                # Create new ItemOutlet (will be bulk-created later)
                                item_outlet = ItemOutlet(
                                    item=item,
                                    outlet=outlet,
                                    is_active_in_outlet=True,
                                    outlet_stock=0
                                )
                                items_to_create.append(item_outlet)
                                item_outlet_dict[item.id] = item_outlet
                                is_new_item_outlet = True
                                new_item_count += 1
                            
                            # Calculate outlet-specific MRP and selling price
                            outlet_changed_fields = []
                        
                            if price_type in ['mrp', 'cost_mrp']:
                                mrp_str = row.get('mrp', '').strip()
                                if mrp_str:
                                    try:
                                        mrp = Decimal(mrp_str)
                                        if mrp < 0:
                                            errors.append(f"Row {row_num}: MRP cannot be negative")
                                            continue
                                        
                                        # Store outlet-specific MRP (round to 2 decimal places)
                                        mrp_rounded = mrp.quantize(Decimal('0.01'))
                                        current_mrp = item_outlet.outlet_mrp.quantize(Decimal('0.01')) if item_outlet.outlet_mrp else Decimal('0.00')
                                        
                                        if current_mrp != mrp_rounded:
                                            item_outlet.outlet_mrp = mrp_rounded
                                            outlet_changed_fields.append('outlet_mrp')
                                        
                                        # Calculate outlet-specific selling price based on wrap type
                                        from .utils import PricingCalculator
                                        
                                        if item.wrap == '9900':
                                            # Wrap items (weighed: fruits, fish, etc.)
                                            # Parent (KGS/KG): selling_price = MRP (as-is)
                                            # Child (100GM, 250GM, etc.): selling_price = MRP ÷ WDF
                                            # 
                                            # Detection Logic:
                                            # Use WDF to detect parent (WDF=1 means 1 KG = parent)
                                            # SKU can be any value from CSV, so we use WDF instead of SKU comparison
                                            # WDF=1 → Parent (1 KG)
                                            # WDF=2 → Child (500GM)
                                            # WDF=4 → Child (250GM)
                                            # WDF=10 → Child (100GM)
                                            wdf = item.weight_division_factor or Decimal('1')
                                            is_parent_unit = wdf == Decimal('1')
                                            
                                            if outlet.platforms == 'talabat':
                                                # Talabat: Apply margin calculation
                                                if is_parent_unit:
                                                    # Parent: Use MRP directly with margin
                                                    calc = PricingCalculator()
                                                    outlet_selling_price, _ = calc.calculate_talabat_price(
                                                        mrp_rounded,
                                                        margin_percentage=item.effective_talabat_margin
                                                    )
                                                else:
                                                    # Child: First divide MRP by WDF, then apply margin
                                                    wdf = item.weight_division_factor or Decimal('1')
                                                    base_price = (mrp_rounded / wdf).quantize(Decimal('0.01'))
                                                    calc = PricingCalculator()
                                                    outlet_selling_price, _ = calc.calculate_talabat_price(
                                                        base_price,
                                                        margin_percentage=item.effective_talabat_margin
                                                    )
                                            else:
                                                # Pasons: No margin applied
                                                if is_parent_unit:
                                                    # Parent (KGS): selling_price = MRP (as-is)
                                                    outlet_selling_price = mrp_rounded
                                                else:
                                                    # Child (100GM, 250GM, etc.): selling_price = MRP ÷ WDF
                                                    wdf = item.weight_division_factor or Decimal('1')
                                                    outlet_selling_price = (mrp_rounded / wdf).quantize(Decimal('0.01'))
                                        else:
                                            # Regular items (wrap=10000): Use MRP as-is, no WDF division
                                            if outlet.platforms == 'talabat':
                                                calc = PricingCalculator()
                                                outlet_selling_price, _ = calc.calculate_talabat_price(
                                                    mrp_rounded,
                                                    margin_percentage=item.effective_talabat_margin
                                                )
                                            else:
                                                # Pasons: Just use MRP, no margin
                                                outlet_selling_price = mrp_rounded
                                        
                                        # Only update if value changed (compare rounded values)
                                        current_selling_price = item_outlet.outlet_selling_price.quantize(Decimal('0.01')) if item_outlet.outlet_selling_price else Decimal('0.00')
                                        
                                        if current_selling_price != outlet_selling_price:
                                            item_outlet.outlet_selling_price = outlet_selling_price
                                            outlet_changed_fields.append('outlet_selling_price')
                                        
                                        # CASCADE LOGIC: When parent item (e.g., KGS) is updated,
                                        # also update all other units of same item_code (e.g., 250GM, 100GM)
                                        # Each child gets its own MRP and selling_price calculated independently
                                        # Only cascade from PARENT items (WDF=1 means 1 KG = parent)
                                        parent_wdf = item.weight_division_factor or Decimal('1')
                                        is_cascade_parent = parent_wdf == Decimal('1')
                                        
                                        if outlet_changed_fields and item.wrap == '9900' and is_cascade_parent:
                                            # Find all items with same item_code but different SKU (children)
                                            all_items_same_code = Item.objects.filter(
                                                item_code=item_code,
                                                platform=platform
                                            ).exclude(sku=item.sku)  # Exclude the parent we just updated
                                            
                                            for child_item in all_items_same_code:
                                                try:
                                                    # Calculate child MRP from parent MRP
                                                    # Formula: child_mrp = parent_mrp ÷ child_wdf
                                                    # Example: parent=9.95 per KG, child_wdf=2 → child_mrp=4.98 per 500GM
                                                    child_wdf = child_item.weight_division_factor or Decimal('1')
                                                    
                                                    # Only cascade to CHILDREN (WDF > 1), not to other parents
                                                    if child_wdf == Decimal('1'):
                                                        continue
                                                    
                                                    # Only cascade if SKU starts with item_code (e.g., 9900422 -> 9900422500)
                                                    if not str(child_item.sku).startswith(str(item_code)):
                                                        continue
                                                    
                                                    # Only cascade if units match (normalized - remove dots, lowercase)
                                                    parent_units = (item.units or '').replace('.', '').lower().strip()
                                                    child_units = (child_item.units or '').replace('.', '').lower().strip()
                                                    if parent_units != child_units:
                                                        continue
                                                    
                                                    if child_wdf != 0:
                                                        child_mrp = (mrp_rounded / child_wdf).quantize(Decimal('0.01'))
                                                        
                                                        # Get or create ItemOutlet for child item
                                                        child_item_outlet, is_new = ItemOutlet.objects.get_or_create(
                                                            item=child_item,
                                                            outlet=outlet,
                                                            defaults={'outlet_mrp': child_mrp}
                                                        )
                                                        
                                                        # Update child MRP if it changed
                                                        child_current_mrp = child_item_outlet.outlet_mrp.quantize(Decimal('0.01')) if child_item_outlet.outlet_mrp else Decimal('0.00')
                                                        
                                                        if child_current_mrp != child_mrp or is_new:
                                                            child_item_outlet.outlet_mrp = child_mrp
                                                            
                                                            # Calculate child selling price using CHILD's own WDF
                                                            # Formula: child_selling_price = parent_mrp ÷ child_wdf
                                                            # Each child uses its own WDF to get correct price per unit
                                                            child_wdf = child_item.weight_division_factor or Decimal('1')
                                                            
                                                            if outlet.platforms == 'talabat':
                                                                # For Talabat: Apply margin on top of the base price
                                                                base_selling_price = (mrp_rounded / child_wdf).quantize(Decimal('0.01'))
                                                                calc = PricingCalculator()
                                                                child_selling_price, _ = calc.calculate_talabat_price(
                                                                    base_selling_price,
                                                                    margin_percentage=child_item.effective_talabat_margin
                                                                )
                                                            else:
                                                                # For Pasons: Use base price directly (parent_mrp ÷ child_wdf)
                                                                child_selling_price = (mrp_rounded / child_wdf).quantize(Decimal('0.01'))
                                                            
                                                            child_item_outlet.outlet_selling_price = child_selling_price
                                                            child_item_outlet.save(update_fields=['outlet_mrp', 'outlet_selling_price'])
                                                except Exception as cascade_error:
                                                    # Log cascade error but continue processing
                                                    errors.append(f"Row {row_num}: Cascade update failed for {child_item.item_code} ({child_item.units}) - {str(cascade_error)}")
                                        
                                    except (InvalidOperation, ValueError):
                                        errors.append(f"Row {row_num}: Invalid MRP format")
                                        continue
                            elif price_type == 'mrp':
                                errors.append(f"Row {row_num}: MRP is required")
                                continue
                        
                        if price_type in ['cost', 'cost_mrp']:
                            cost_str = row.get('cost', '').strip()
                            original_csv_cost = None  # Save original for additional items
                            if cost_str:
                                try:
                                    cost = Decimal(cost_str)
                                    # Replace negative cost with 0
                                    if cost < 0:
                                        cost = Decimal('0')
                                    original_csv_cost = cost  # Store after validation
                                    
                                    # COST LOGIC: Store RAW cost, calculate converted_cost
                                    # item.cost = RAW cost from CSV (same for parent and all children)
                                    # item.converted_cost = cost ÷ WDF (calculated)
                                    # outlet_cost = RAW cost
                                    
                                    # Update item-level cost (RAW)
                                    item_cost_changed = False
                                    if item.cost != cost:
                                        item.cost = cost
                                        item_cost_changed = True
                                    
                                    # Calculate converted_cost based on wrap type
                                    if item.wrap == '9900':
                                        # wrap=9900: converted_cost = cost ÷ WDF (3 decimals)
                                        wdf = item.weight_division_factor or Decimal('1')
                                        if wdf > 0:
                                            new_converted_cost = (cost / wdf).quantize(Decimal('0.001'))
                                        else:
                                            new_converted_cost = cost
                                    else:
                                        # wrap=10000: converted_cost = cost (no division)
                                        new_converted_cost = cost
                                    
                                    if item.converted_cost != new_converted_cost:
                                        item.converted_cost = new_converted_cost
                                        item_cost_changed = True
                                    
                                    if item_cost_changed:
                                        item.save(update_fields=['cost', 'converted_cost'])
                                    
                                    # Update OUTLET-LEVEL cost (RAW cost, same as item.cost)
                                    if item_outlet.outlet_cost != cost:
                                        item_outlet.outlet_cost = cost
                                        outlet_changed_fields.append('outlet_cost')
                                    
                                    # CASCADE COST LOGIC: When parent cost is updated (wrap=9900 only)
                                    # Parent detection: WDF == 1 (not SKU-based)
                                    # Each child gets: same RAW cost, but converted_cost = cost ÷ child_wdf
                                    parent_wdf_for_cost = item.weight_division_factor or Decimal('1')
                                    is_cascade_cost_parent = parent_wdf_for_cost == Decimal('1')
                                    
                                    if item.wrap == '9900' and is_cascade_cost_parent:
                                        # Find all children with same item_code (exclude current item)
                                        all_items_same_code = Item.objects.filter(
                                            item_code=item_code,
                                            platform=platform
                                        ).exclude(pk=item.pk)
                                        
                                        for child_item in all_items_same_code:
                                            try:
                                                child_wdf = child_item.weight_division_factor or Decimal('1')
                                                
                                                # Only cascade to CHILDREN (WDF > 1), not to other parents
                                                if child_wdf == Decimal('1'):
                                                    continue
                                                
                                                # Only cascade if SKU starts with item_code (e.g., 9900422 -> 9900422500)
                                                if not str(child_item.sku).startswith(str(item_code)):
                                                    continue
                                                
                                                # Only cascade if units match (normalized - remove dots, lowercase)
                                                parent_units = (item.units or '').replace('.', '').lower().strip()
                                                child_units = (child_item.units or '').replace('.', '').lower().strip()
                                                if parent_units != child_units:
                                                    continue
                                                
                                                if child_wdf != 0:
                                                    # Child gets same RAW cost as parent
                                                    # converted_cost = cost ÷ child_wdf (3 decimals)
                                                    child_converted_cost = (cost / child_wdf).quantize(Decimal('0.001'))
                                                    
                                                    # ZERO FLOOR: Child SKUs cannot have negative cost
                                                    if child_converted_cost < 0:
                                                        child_converted_cost = Decimal('0')
                                                    
                                                    # Update child item: RAW cost + converted_cost
                                                    child_changed = False
                                                    if child_item.cost != cost:
                                                        child_item.cost = cost
                                                        child_changed = True
                                                    if child_item.converted_cost != child_converted_cost:
                                                        child_item.converted_cost = child_converted_cost
                                                        child_changed = True
                                                    if child_changed:
                                                        child_item.save(update_fields=['cost', 'converted_cost'])
                                                    
                                                    # Update child outlet_cost (RAW cost)
                                                    child_item_outlet, _ = ItemOutlet.objects.get_or_create(
                                                        item=child_item,
                                                        outlet=outlet,
                                                        defaults={'outlet_cost': cost}
                                                    )
                                                    if child_item_outlet.outlet_cost != cost:
                                                        child_item_outlet.outlet_cost = cost
                                                        child_item_outlet.save(update_fields=['outlet_cost'])
                                            except Exception as cost_cascade_error:
                                                errors.append(f"Row {row_num}: Cost cascade failed for {child_item.sku} - {str(cost_cascade_error)}")
                                except (InvalidOperation, ValueError):
                                    errors.append(f"Row {row_num}: Invalid cost format")
                                    continue
                            elif price_type == 'cost':
                                errors.append(f"Row {row_num}: Cost is required")
                                continue
                        
                            # FIXED: This block must be INSIDE the for loop (28 spaces indent)
                            if outlet_changed_fields:
                                if not is_new_item_outlet:
                                    # Only save existing ItemOutlet records
                                    # New ones will be bulk-created later
                                    item_outlet.save(update_fields=outlet_changed_fields)
                                updated_items.append(f"{item_code} ({units}) - SKU:{item.sku}")
                            else:
                                # Item found but no changes needed
                                if not is_new_item_outlet:
                                    unchanged_items.append(f"{item_code} ({units}) - SKU:{item.sku}")
                        
                        # REMOVED: Old duplicate logic for "REMAINING items" - now handled by main loop above
                        # The for loop at line 1986 now correctly processes ALL items in items_list
                        if False and len(items_list) > 1:  # DISABLED - no longer needed
                            for additional_item in items_list[1:]:
                                try:
                                    # Get or create ItemOutlet for additional item
                                    add_item_outlet = item_outlet_dict.get(additional_item.id)
                                    add_is_new = False
                                    if not add_item_outlet:
                                        add_item_outlet = ItemOutlet(
                                            item=additional_item,
                                            outlet=outlet,
                                            is_active_in_outlet=True,
                                            outlet_stock=0
                                        )
                                        items_to_create.append(add_item_outlet)
                                        item_outlet_dict[additional_item.id] = add_item_outlet
                                        add_is_new = True
                                        new_item_count += 1
                                    
                                    # Copy MRP from first item and calculate selling_price
                                    if price_type in ['mrp', 'cost_mrp'] and item_outlet.outlet_mrp:
                                        add_item_outlet.outlet_mrp = item_outlet.outlet_mrp
                                        
                                        # Calculate selling_price based on wrap type and parent/child status
                                        if additional_item.wrap == '9900':
                                            is_add_parent = str(additional_item.sku).strip() == str(additional_item.item_code).strip()
                                            if outlet.platforms == 'talabat':
                                                from .utils import PricingCalculator
                                                if is_add_parent:
                                                    calc = PricingCalculator()
                                                    add_selling_price, _ = calc.calculate_talabat_price(
                                                        add_item_outlet.outlet_mrp,
                                                        margin_percentage=additional_item.effective_talabat_margin
                                                    )
                                                else:
                                                    wdf = additional_item.weight_division_factor or Decimal('1')
                                                    base_price = (add_item_outlet.outlet_mrp / wdf).quantize(Decimal('0.01'))
                                                    calc = PricingCalculator()
                                                    add_selling_price, _ = calc.calculate_talabat_price(
                                                        base_price,
                                                        margin_percentage=additional_item.effective_talabat_margin
                                                    )
                                            else:
                                                if is_add_parent:
                                                    add_selling_price = add_item_outlet.outlet_mrp
                                                else:
                                                    wdf = additional_item.weight_division_factor or Decimal('1')
                                                    add_selling_price = (add_item_outlet.outlet_mrp / wdf).quantize(Decimal('0.01'))
                                        else:
                                            add_selling_price = add_item_outlet.outlet_mrp
                                        
                                        add_item_outlet.outlet_selling_price = add_selling_price
                                        if not add_is_new:
                                            add_item_outlet.save(update_fields=['outlet_mrp', 'outlet_selling_price'])
                                    
                                    # COST: Also process cost for additional items
                                    # Use ORIGINAL CSV cost (RAW), calculate converted_cost
                                    if price_type in ['cost', 'cost_mrp'] and original_csv_cost:
                                        # Store RAW cost, calculate converted_cost based on wrap type
                                        add_cost_changed = False
                                        
                                        if additional_item.cost != original_csv_cost:
                                            additional_item.cost = original_csv_cost
                                            add_cost_changed = True
                                        
                                        # Calculate converted_cost based on wrap type
                                        if additional_item.wrap == '9900':
                                            add_wdf = additional_item.weight_division_factor or Decimal('1')
                                            if add_wdf > 0:
                                                add_converted_cost = (original_csv_cost / add_wdf).quantize(Decimal('0.001'))
                                            else:
                                                add_converted_cost = original_csv_cost
                                        else:
                                            # wrap=10000: converted_cost = cost (no division)
                                            add_converted_cost = original_csv_cost
                                        
                                        if additional_item.converted_cost != add_converted_cost:
                                            additional_item.converted_cost = add_converted_cost
                                            add_cost_changed = True
                                        
                                        if add_cost_changed:
                                            additional_item.save(update_fields=['cost', 'converted_cost'])
                                        
                                        # Update outlet_cost (RAW cost)
                                        if add_item_outlet.outlet_cost != original_csv_cost:
                                            add_item_outlet.outlet_cost = original_csv_cost
                                            if not add_is_new:
                                                add_item_outlet.save(update_fields=['outlet_cost'])
                                except Exception as add_error:
                                    errors.append(f"Row {row_num}: Additional item update failed for {additional_item.sku} - {str(add_error)}")
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")
                
                # OPTIMIZATION: Bulk create new ItemOutlets (if any)
                if items_to_create:
                    ItemOutlet.objects.bulk_create(items_to_create, ignore_conflicts=True)
                
                # Success message - show NEW vs CHANGED separately
                changed_count = len(updated_items) - new_item_count
                if new_item_count > 0:
                    messages.success(request, f"Created {new_item_count} NEW outlet-item associations on {platform.title()} at {outlet.name}.")
                if changed_count > 0:
                    messages.success(request, f"Updated prices for {changed_count} existing items on {platform.title()} at {outlet.name}.")
                
                # Unchanged items (already up-to-date)
                if unchanged_items:
                    messages.info(request, f"{len(unchanged_items)} items already have correct prices (no changes needed).")
                
                # Not found items
                if not_found_items:
                    if len(not_found_items) <= 5:
                        messages.warning(request, f"Items not found on {platform.title()}: {', '.join(not_found_items)}")
                    else:
                        messages.warning(request, f"{len(not_found_items)} items not found on {platform.title()}")
                
                # Errors
                if errors:
                    for error in errors[:5]:
                        messages.error(request, error)
                    if len(errors) > 5:
                        messages.warning(request, f"And {len(errors) - 5} more errors...")
                
                # Log upload history
                from .models import UploadHistory
                # Determine update type based on price_type
                update_type_map = {'cost': 'price_cost', 'mrp': 'price_mrp', 'cost_mrp': 'price_both'}
                total_records = len(updated_items) + len(unchanged_items) + len(not_found_items) + len(errors)
                upload_status = 'success' if not errors else ('partial' if updated_items else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform=platform,
                    outlet=outlet,
                    update_type=update_type_map.get(price_type, 'price_both'),
                    records_total=total_records,
                    records_success=len(updated_items),
                    records_failed=len(errors),
                    records_skipped=len(not_found_items) + len(unchanged_items),
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                
                return redirect('integration:price_update')
                
            except Outlet.DoesNotExist:
                messages.error(request, "Selected outlet not found.")
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields and select a CSV file.")
    
    context = {
        'page_title': 'Price Update',
        'active_nav': 'bulk_operations'
    }
    return render(request, 'price_update.html', context)


def rules_update_price(request):
    """
    TALABAT-ONLY Margin Update via CSV
    
    This endpoint is EXCLUSIVELY for updating Talabat platform margins.
    CSV Required Headers: item_code, units, sku, margin
    
    - Platform MUST be 'talabat' (enforced)
    - Updates Item.talabat_margin field
    - Uses Item Code + Units + SKU for matching
    - Margin is stored as percentage (e.g., 17 for 17%)
    """
    from .models import Outlet, Item
    from django.contrib import messages
    from decimal import Decimal, InvalidOperation
    import csv
    import io
    
    if request.method == 'POST':
        # Handle CSV upload for Talabat margin updates
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        
        # ENFORCE: Talabat-only platform
        if platform != 'talabat':
            messages.error(request, "This endpoint is ONLY for Talabat platform margin updates. Please select Talabat.")
            return redirect('integration:rules_update_price')
        
        if platform and csv_file:
            try:
                # Process CSV file
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                # Normalize headers to lowercase
                if csv_reader.fieldnames:
                    headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
                else:
                    messages.error(request, "CSV file has no headers")
                    return redirect('integration:rules_update_price')
                
                # STRICT HEADER VALIDATION: Only these 4 headers allowed
                allowed_headers = {'item_code', 'units', 'sku', 'margin'}
                required_headers = {'item_code', 'units', 'sku', 'margin'}
                
                # Check for missing required headers
                missing_headers = required_headers - set(headers)
                if missing_headers:
                    messages.error(request, f"Missing required columns: {', '.join(sorted(missing_headers))}")
                    messages.info(request, "Required: item_code, units, sku, margin")
                    return redirect('integration:rules_update_price')
                
                # Check for invalid/extra headers
                extra_headers = set(headers) - allowed_headers
                if extra_headers:
                    messages.error(request, f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, sku, margin")
                    return redirect('integration:rules_update_price')
                
                updated_items = []
                not_found_items = []
                errors = []
                
                # Build rows to process
                rows_to_process = []
                for row_num, original_row in enumerate(csv_reader, start=2):
                    try:
                        row = {k.strip().lower(): v for k, v in original_row.items()}
                        
                        item_code = row.get('item_code', '').strip()
                        units = row.get('units', '').strip()
                        sku = row.get('sku', '').strip()
                        margin_str = row.get('margin', '').strip()
                        
                        if not item_code:
                            errors.append(f"Row {row_num}: item_code is required")
                            continue
                        if not units:
                            errors.append(f"Row {row_num}: units is required")
                            continue
                        if not sku:
                            errors.append(f"Row {row_num}: sku is required")
                            continue
                        if not margin_str:
                            errors.append(f"Row {row_num}: margin is required")
                            continue
                        
                        try:
                            margin = Decimal(margin_str)
                            if margin < 0:
                                errors.append(f"Row {row_num}: Margin cannot be negative")
                                continue
                            if margin > 100:
                                errors.append(f"Row {row_num}: Margin cannot exceed 100%")
                                continue
                        except (InvalidOperation, ValueError):
                            errors.append(f"Row {row_num}: Invalid margin format '{margin_str}'")
                            continue
                        
                        rows_to_process.append({
                            'row_num': row_num,
                            'item_code': item_code,
                            'units': units,
                            'sku': sku,
                            'margin': margin
                        })
                    
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")
                
                # Bulk fetch all items
                item_keys = [(r['item_code'], r['units'], r['sku']) for r in rows_to_process]
                items_qs = Item.objects.filter(
                    platform='talabat',
                    item_code__in=[k[0] for k in item_keys],
                    units__in=[k[1] for k in item_keys],
                    sku__in=[k[2] for k in item_keys]
                )
                
                # Create lookup dict
                items_dict = {}
                for item in items_qs:
                    key = (item.item_code, item.units, item.sku)
                    items_dict[key] = item
                
                # Process and update margins
                items_to_update = []
                for row_data in rows_to_process:
                    key = (row_data['item_code'], row_data['units'], row_data['sku'])
                    item = items_dict.get(key)
                    
                    if not item:
                        not_found_items.append(f"{row_data['item_code']} ({row_data['units']}) - SKU: {row_data['sku']}")
                        continue
                    
                    # Only update if margin actually changed
                    old_margin = item.talabat_margin
                    new_margin = row_data['margin']
                    
                    if old_margin != new_margin:
                        item.talabat_margin = new_margin
                        items_to_update.append(item)
                        
                        updated_items.append({
                            'item_code': row_data['item_code'],
                            'units': row_data['units'],
                            'sku': row_data['sku'],
                            'old_margin': old_margin if old_margin else 'None (auto-detect)',
                            'new_margin': f"{new_margin}%"
                        })
                
                # Bulk update all items
                if items_to_update:
                    Item.objects.bulk_update(
                        items_to_update,
                        ['talabat_margin', 'updated_at']
                    )
                
                # Display results
                if updated_items:
                    success_summary = f"Successfully updated {len(updated_items)} Talabat margin(s)"
                    messages.success(request, success_summary)
                
                if not_found_items:
                    not_found_summary = f"{len(not_found_items)} item(s) not found in Talabat platform"
                    messages.warning(request, not_found_summary)
                
                if errors:
                    error_summary = f"{len(errors)} error(s) occurred during processing"
                    messages.error(request, error_summary)
                
                if not updated_items and not errors and not not_found_items:
                    messages.warning(request, "No items were processed. Please check your CSV file.")
                
                # Log upload history
                from .models import UploadHistory
                total_records = len(updated_items) + len(not_found_items) + len(errors)
                upload_status = 'success' if not errors else ('partial' if updated_items else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform='talabat',
                    outlet=None,  # Rules update is global
                    update_type='rules_price',
                    records_total=total_records,
                    records_success=len(updated_items),
                    records_failed=len(errors),
                    records_skipped=len(not_found_items),
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                
                return redirect('integration:rules_update_price')
                
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            messages.error(request, "Please select Talabat platform and upload a CSV file.")
    
    context = {
        'page_title': 'Talabat Margin Update',
        'active_nav': 'bulk_operations'
    }
    return render(request, 'rules_update_price.html', context)


@login_required
def rules_update_stock_preview(request):
    """
    Preview endpoint for stock conversion rules update - parses CSV and shows ONLY items with changes
    """
    if request.method == 'POST':
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        
        if not platform or not csv_file:
            return JsonResponse({'success': False, 'message': 'Platform and CSV file required'})
        
        try:
            from .models import Item
            from decimal import Decimal, InvalidOperation
            import csv
            import io
            
            csv_content, _encoding_used = decode_csv_upload(csv_file)
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            if not csv_reader.fieldnames:
                return JsonResponse({'success': False, 'message': 'CSV has no headers'})
            
            headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
            
            # STRICT HEADER VALIDATION: Only these 6 headers allowed
            allowed_headers = {'item_code', 'units', 'sku', 'weight_division_factor', 'outer_case_quantity', 'minimum_qty'}
            required_headers = {'item_code', 'units', 'sku'}
            
            # Check for missing required headers
            missing_headers = required_headers - set(headers)
            if missing_headers:
                return JsonResponse({'success': False, 'message': f"Missing columns: {', '.join(sorted(missing_headers))}"})
            
            # Check for invalid/extra headers
            extra_headers = set(headers) - allowed_headers
            if extra_headers:
                return JsonResponse({'success': False, 'message': f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, sku, weight_division_factor, outer_case_quantity, minimum_qty"})
            
            items_with_changes = []
            total_rows = 0
            errors = []
            
            for row_num, original_row in enumerate(csv_reader, start=2):
                total_rows += 1
                try:
                    row = {k.strip().lower(): v for k, v in original_row.items()}
                    
                    item_code = row.get('item_code', '').strip()
                    units = row.get('units', '').strip()
                    sku = row.get('sku', '').strip()
                    
                    if not item_code or not units or not sku:
                        errors.append(f"Row {row_num}: Missing item_code, units, or sku")
                        continue
                    
                    item = Item.objects.filter(
                        platform=platform,
                        item_code=item_code,
                        units=units,
                        sku=sku
                    ).first()
                    
                    if not item:
                        continue  # Skip not found items in preview
                    
                    changes = {}
                    has_changes = False
                    
                    # Check WDF
                    wdf_str = row.get('weight_division_factor', '').strip()
                    if wdf_str:
                        try:
                            new_wdf = Decimal(wdf_str)
                            if new_wdf != item.weight_division_factor:
                                changes['wdf'] = {
                                    'old': float(item.weight_division_factor) if item.weight_division_factor else None,
                                    'new': float(new_wdf)
                                }
                                has_changes = True
                        except (InvalidOperation, ValueError):
                            errors.append(f"Row {row_num}: Invalid WDF '{wdf_str}'")
                            continue
                    
                    # Check OCQ
                    ocq_str = row.get('outer_case_quantity', '').strip()
                    if ocq_str:
                        try:
                            new_ocq = int(ocq_str)
                            if new_ocq != item.outer_case_quantity:
                                changes['ocq'] = {
                                    'old': item.outer_case_quantity,
                                    'new': new_ocq
                                }
                                has_changes = True
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid OCQ '{ocq_str}'")
                            continue
                    
                    # Check MinQty
                    minqty_str = row.get('minimum_qty', '').strip()
                    if minqty_str:
                        try:
                            new_minqty = int(minqty_str)
                            if new_minqty != item.minimum_qty:
                                changes['minqty'] = {
                                    'old': item.minimum_qty,
                                    'new': new_minqty
                                }
                                has_changes = True
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid MinQty '{minqty_str}'")
                            continue
                    
                    if has_changes:
                        items_with_changes.append({
                            'row': row_num,
                            'item_code': item_code,
                            'units': units,
                            'sku': sku,
                            'changes': changes
                        })
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'platform': platform,
                'total_rows': total_rows,
                'items_with_changes': items_with_changes[:100],  # Limit to 100 for display
                'total_changes': len(items_with_changes),
                'errors': errors[:10] if errors else []
            })
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def rules_update_stock(request):
    """
    Stock conversion rules update - updates weight_division_factor, outer_case_quantity, minimum_qty
    for existing items on a specific platform. Rules apply to ALL outlets/branches for that platform.
    """
    if request.method == 'POST':
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        
        if platform and csv_file:
            try:
                from .models import Item, ItemOutlet
                from django.contrib import messages
                from decimal import Decimal, InvalidOperation
                import csv
                import io
                
                # Process CSV file
                csv_content, _encoding_used = decode_csv_upload(csv_file)
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                
                # Normalize headers
                if not csv_reader.fieldnames:
                    messages.error(request, "CSV file has no headers")
                    return redirect('integration:rules_update_stock')
                
                headers = [h.strip().lower() for h in csv_reader.fieldnames if h and h.strip()]
                
                # STRICT HEADER VALIDATION: Only these 6 headers allowed
                allowed_headers = {'item_code', 'units', 'sku', 'weight_division_factor', 'outer_case_quantity', 'minimum_qty'}
                required_headers = {'item_code', 'units', 'sku'}
                
                # Check for missing required headers
                missing_headers = required_headers - set(headers)
                if missing_headers:
                    messages.error(request, f"Missing required columns: {', '.join(sorted(missing_headers))}")
                    return redirect('integration:rules_update_stock')
                
                # Check for invalid/extra headers
                extra_headers = set(headers) - allowed_headers
                if extra_headers:
                    messages.error(request, f"Invalid columns not allowed: {', '.join(sorted(extra_headers))}. Only allowed: item_code, units, sku, weight_division_factor, outer_case_quantity, minimum_qty")
                    return redirect('integration:rules_update_stock')
                
                updated_items = []
                not_found_items = []
                errors = []
                
                # Build lookup dict for fast comparison
                rows_to_process = []
                for row_num, original_row in enumerate(csv_reader, start=2):
                    try:
                        row = {k.strip().lower(): v for k, v in original_row.items()}
                        
                        item_code = row.get('item_code', '').strip()
                        units = row.get('units', '').strip()
                        sku = row.get('sku', '').strip()
                        
                        if not item_code or not units or not sku:
                            errors.append(f"Row {row_num}: item_code, units, and sku are required")
                            continue
                        
                        rows_to_process.append({
                            'row_num': row_num,
                            'item_code': item_code,
                            'units': units,
                            'sku': sku,
                            'wdf': row.get('weight_division_factor', '').strip(),
                            'ocq': row.get('outer_case_quantity', '').strip(),
                            'minqty': row.get('minimum_qty', '').strip()
                        })
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")
                
                # Bulk fetch all items at once
                item_keys = [(r['item_code'], r['units'], r['sku']) for r in rows_to_process]
                items_qs = Item.objects.filter(
                    platform=platform,
                    item_code__in=[k[0] for k in item_keys],
                    units__in=[k[1] for k in item_keys],
                    sku__in=[k[2] for k in item_keys]
                )
                
                # Create lookup dict
                items_dict = {}
                for item in items_qs:
                    key = (item.item_code, item.units, item.sku)
                    items_dict[key] = item
                
                # Process rows and detect changes
                items_to_update = []
                for row_data in rows_to_process:
                    key = (row_data['item_code'], row_data['units'], row_data['sku'])
                    item = items_dict.get(key)
                    
                    if not item:
                        not_found_items.append(f"{row_data['item_code']} ({row_data['units']}, {row_data['sku']})")
                        continue
                    
                    try:
                        has_changes = False
                        old_values = {}
                        new_values = {}
                        
                        # Check WDF
                        if row_data['wdf']:
                            try:
                                new_wdf = Decimal(row_data['wdf'])
                                if new_wdf != item.weight_division_factor:
                                    old_values['wdf'] = item.weight_division_factor
                                    item.weight_division_factor = new_wdf
                                    new_values['wdf'] = new_wdf
                                    has_changes = True
                            except (InvalidOperation, ValueError):
                                errors.append(f"Row {row_data['row_num']}: Invalid WDF '{row_data['wdf']}'")
                                continue
                        
                        # Check OCQ
                        if row_data['ocq']:
                            try:
                                new_ocq = int(row_data['ocq'])
                                if new_ocq != item.outer_case_quantity:
                                    old_values['ocq'] = item.outer_case_quantity
                                    item.outer_case_quantity = new_ocq
                                    new_values['ocq'] = new_ocq
                                    has_changes = True
                            except ValueError:
                                errors.append(f"Row {row_data['row_num']}: Invalid OCQ '{row_data['ocq']}'")
                                continue
                        
                        # Check MinQty
                        if row_data['minqty']:
                            try:
                                new_minqty = int(row_data['minqty'])
                                if new_minqty != item.minimum_qty:
                                    old_values['minqty'] = item.minimum_qty
                                    item.minimum_qty = new_minqty
                                    new_values['minqty'] = new_minqty
                                    has_changes = True
                            except ValueError:
                                errors.append(f"Row {row_data['row_num']}: Invalid MinQty '{row_data['minqty']}'")
                                continue
                        
                        if has_changes:
                            items_to_update.append(item)
                            updated_items.append({
                                'item_code': row_data['item_code'],
                                'units': row_data['units'],
                                'sku': row_data['sku'],
                                'old': old_values,
                                'new': new_values
                            })
                    
                    except Exception as e:
                        errors.append(f"Row {row_data['row_num']}: Error - {str(e)}")
                
                # Bulk update all items at once
                if items_to_update:
                    Item.objects.bulk_update(
                        items_to_update,
                        ['weight_division_factor', 'outer_case_quantity', 'minimum_qty']
                    )
                
                # Display consolidated messages
                if updated_items:
                    success_summary = f"Successfully updated {len(updated_items)} item(s) for {platform.title()} platform"
                    messages.success(request, success_summary)
                
                if not_found_items:
                    not_found_summary = f"{len(not_found_items)} item(s) not found in {platform.title()} platform"
                    messages.warning(request, not_found_summary)
                
                if errors:
                    error_summary = f"{len(errors)} error(s) occurred during processing"
                    messages.error(request, error_summary)
                
                # Log upload history
                from .models import UploadHistory
                total_records = len(updated_items) + len(not_found_items) + len(errors)
                upload_status = 'success' if not errors else ('partial' if updated_items else 'failed')
                UploadHistory.objects.create(
                    file_name=csv_file.name,
                    platform=platform,
                    outlet=None,  # Rules update is global
                    update_type='rules_stock',
                    records_total=total_records,
                    records_success=len(updated_items),
                    records_failed=len(errors),
                    records_skipped=len(not_found_items),
                    status=upload_status,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                
                return redirect('integration:rules_update_stock')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            from django.contrib import messages
            if not platform:
                messages.error(request, "Please select a platform.")
            elif not csv_file:
                messages.error(request, "Please select a CSV file.")
    
    context = {
        'page_title': 'Stock Conversion Rules Update',
        'active_nav': 'bulk_operations'
    }
    return render(request, 'rules_update_stock.html', context)



@login_required
def search_product_api(request):
    """
    API endpoint to search for products - supports both single search and bulk loading
    """
    from .models import Item
    from django.db import models
    from django.core.paginator import Paginator
    
    # Determine platform and whether this is bulk mode (item deletion page)
    platform = request.GET.get('platform', '').strip()
    include_inactive = request.GET.get('include_inactive', '').strip() in ('1', 'true', 'True')
    # Bulk mode triggers: explicit pagination or filter parameters
    bulk_mode = (
        ('page' in request.GET) or
        ('page_size' in request.GET) or
        ('item_code' in request.GET) or
        ('description' in request.GET) or
        ('barcode' in request.GET) or
        ('sku' in request.GET) or
        ('price_min' in request.GET) or
        ('price_max' in request.GET) or
        ('stock_min' in request.GET) or
        ('stock_max' in request.GET)
    ) and bool(platform)

    if bulk_mode:
        # Bulk loading for item deletion page with server-side pagination and filters
        try:
            # Page and page size (default 100 per page)
            page = int(request.GET.get('page', '1'))
            page_size = int(request.GET.get('page_size', '100'))
            if page_size <= 0:
                page_size = 100
            if page_size > 1000:  # prevent excessive queries
                page_size = 1000

            # Filters
            item_code = request.GET.get('item_code', '').strip()
            description = request.GET.get('description', '').strip()
            barcode = request.GET.get('barcode', '').strip()
            sku = request.GET.get('sku', '').strip()
            price_min = request.GET.get('price_min', '').strip()
            price_max = request.GET.get('price_max', '').strip()
            stock_min = request.GET.get('stock_min', '').strip()
            stock_max = request.GET.get('stock_max', '').strip()

            qs = Item.objects.all() if include_inactive else Item.objects.filter(is_active=True)
            if platform in ('pasons', 'talabat'):
                qs = qs.filter(platform=platform)
            elif platform == 'all':
                qs = qs.filter(platform__in=['pasons', 'talabat'])

            # Apply filters
            if item_code:
                qs = qs.filter(item_code__icontains=item_code)
            if description:
                qs = qs.filter(description__icontains=description)
            if barcode:
                qs = qs.filter(barcode__icontains=barcode)
            if sku:
                qs = qs.filter(sku__icontains=sku)
            # Numeric filters
            try:
                if price_min:
                    qs = qs.filter(selling_price__gte=float(price_min))
            except ValueError:
                pass
            try:
                if price_max:
                    qs = qs.filter(selling_price__lte=float(price_max))
            except ValueError:
                pass
            try:
                if stock_min:
                    qs = qs.filter(stock__gte=int(stock_min))
            except ValueError:
                pass
            try:
                if stock_max:
                    qs = qs.filter(stock__lte=int(stock_max))
            except ValueError:
                pass

            qs = qs.order_by('item_code')

            # Pagination
            paginator = Paginator(qs, page_size)
            page_obj = paginator.get_page(page)

            items_data = []
            for item in page_obj.object_list:
                combination_key = f"{item.item_code}|{item.description}|{item.sku}"
                items_data.append({
                    'id': item.id,
                    'item_code': item.item_code,
                    'description': item.description,
                    'pack_description': item.pack_description or '',
                    'sku': item.sku,
                    'units': item.units,
                    'selling_price': float(item.selling_price),
                    'stock': item.stock,
                    'mrp': float(item.mrp),
                    'cost': float(item.cost),
                    'is_active': item.is_active,
                    # CLS flags for UI consistency
                    'price_locked': bool(getattr(item, 'price_locked', False)),
                    'status_locked': bool(getattr(item, 'status_locked', False)),
                    'barcode': item.barcode or '',
                    'wrap': item.wrap or '',
                    'weight_division_factor': item.weight_division_factor,
                    'outer_case_quantity': item.outer_case_quantity,
                    'minimum_qty': item.minimum_qty,
                    'talabat_margin': float(item.effective_talabat_margin) if platform == 'talabat' else None,
                    'combination_key': combination_key
                })

            return JsonResponse({
                'success': True,
                'items': items_data,
                'page': page_obj.number,
                'page_size': page_size,
                'total_items': paginator.count,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error loading items: {str(e)}'
            })
    
    # Single product search (original functionality)
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'found': False, 'message': 'No search query provided'})
    
    try:
        # Base queryset restricted by platform. Honor include_inactive for consistency.
        qs = Item.objects.all() if include_inactive else Item.objects.filter(is_active=True)
        if platform in ('pasons', 'talabat'):
            qs = qs.filter(platform=platform)
        elif platform == 'all':
            qs = qs.filter(platform__in=['pasons', 'talabat'])
        # Search by item_code, sku, barcode, or description
        qs = qs.filter(
            models.Q(item_code__iexact=query) |
            models.Q(sku__iexact=query) |
            models.Q(barcode__iexact=query) |
            models.Q(description__icontains=query) |
            models.Q(item_code__icontains=query) |
            models.Q(sku__icontains=query)
        )[:20]  # Limit to 20 results
        
        if qs.exists():
            items_data = []
            for item in qs:
                # Create unique combination key for item_code + item_name + sku
                combination_key = f"{item.item_code}|{item.description}|{item.sku}"
                
                items_data.append({
                    'id': item.id,
                    'item_code': item.item_code,
                    'description': item.description,
                    'pack_description': item.pack_description or '',
                    'sku': item.sku,
                    'units': item.units,
                    'selling_price': float(item.selling_price),
                    'stock': item.stock,
                    'mrp': float(item.mrp),
                    'cost': float(item.cost),
                    'price_locked': bool(getattr(item, 'price_locked', False)),
                    'status_locked': bool(getattr(item, 'status_locked', False)),
                    'barcode': item.barcode or '',
                    'wrap': item.wrap or '',
                    'weight_division_factor': item.weight_division_factor,
                    'outer_case_quantity': item.outer_case_quantity,
                    'minimum_qty': item.minimum_qty,
                    'talabat_margin': float(item.effective_talabat_margin) if platform == 'talabat' else None,
                    'combination_key': combination_key
                })
            
            return JsonResponse({
                'success': True,
                'items': items_data,
                'total_count': len(items_data)
            })
        else:
            return JsonResponse({'success': False, 'message': 'No items found matching your search'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Search error: {str(e)}'})


def calculate_outlet_enabled_status(item, outlet_stock):
    """
    Calculate if an outlet should show as Enabled or Disabled
    based on stock, outer_case_quantity, and minimum_qty.
    
    Rules:
    1. stock ≤ 0 → Disabled (No stock = always disabled)
    2. For wrap=9900: outlet_stock is already in packs (no OCQ division)
       For wrap=10000: converted_stock = outlet_stock ÷ OCQ
    3. If converted_stock < minimum_qty → Disabled
    4. If converted_stock ≥ minimum_qty → Enabled
    
    Examples (wrap=9900, 250gm item with WDF=4):
    - CSV stock=3 KG → outlet_stock=12 packs, min_qty=10 → 12≥10 → Enabled
    - CSV stock=2 KG → outlet_stock=8 packs, min_qty=10 → 8<10 → Disabled
    
    Examples (wrap=10000):
    - stock=10, OCQ=5, min_qty=2 → converted=2 → 2≥2 → Enabled
    - stock=4, OCQ=5, min_qty=1 → converted=0.8 → 0.8<1 → Disabled
    
    Returns:
        bool: True = Enabled (stock_status=1), False = Disabled (stock_status=0)
    """
    stock = outlet_stock or 0
    
    # Rule 1: No stock or negative stock = Always Disabled
    if stock <= 0:
        return False
    
    # Rule 2: Calculate converted_stock based on wrap type
    if item.wrap == '9900':
        # wrap=9900: outlet_stock is already in packs (stock_kg × WDF)
        # No OCQ division needed
        converted_stock = stock
    else:
        # wrap=10000: divide by OCQ to get cases
        ocq = item.outer_case_quantity
        if ocq and ocq > 0:
            converted_stock = stock / ocq
        else:
            converted_stock = stock
    
    # Rule 3: Check if converted_stock meets minimum_qty requirement
    min_qty = item.minimum_qty
    if min_qty is not None and min_qty > 0:
        if converted_stock < min_qty:
            return False
    
    # All checks passed = Enabled
    return True


@login_required
def item_outlets_api(request):
    """
    Return outlet availability for a given item on a given platform.
    Accepts: platform (required), item_code + units OR item_id
    Responds with: product summary and list of outlets with price/stock.
    
    IMPORTANT: item_code + units together form a unique item identifier!
    Same item_code can have multiple units (e.g., 100010915 with PCS, DZN, OUT, JAR)
    
    NOTE: 'active' field is now AUTO-CALCULATED based on:
    - stock > 0
    - stock >= outer_case_quantity (if set)
    - stock >= minimum_qty (if set)
    """
    from .models import Item, ItemOutlet, Outlet

    platform = request.GET.get('platform', '').strip()
    item_code = request.GET.get('item_code', '').strip()
    units = request.GET.get('units', '').strip()  # NEW: Accept units parameter
    sku = request.GET.get('sku', '').strip()  # NEW: Accept SKU for unique identification (wrap=9900)
    item_id = request.GET.get('item_id', '').strip()
    include_inactive = request.GET.get('include_inactive', '').strip() in ('1', 'true', 'True')

    # STRICT ISOLATION: Only 'pasons' or 'talabat' allowed
    if platform not in ('pasons', 'talabat'):
        return JsonResponse({'success': False, 'message': 'Invalid or missing platform'})

    try:
        item = None
        if item_id:
            try:
                if include_inactive:
                    item = Item.objects.filter(pk=int(item_id)).first()
                else:
                    item = Item.objects.filter(pk=int(item_id), is_active=True).first()
            except ValueError:
                item = None
        if item is None and item_code:
            # FIXED: Filter by item_code, units, sku, AND platform for unique identification
            # Platform is CRITICAL - same item_code can exist on both Pasons and Talabat!
            item_filter = {'item_code__iexact': item_code}
            
            # CRITICAL FIX: Filter by platform to ensure we get the right item!
            # Without this, Talabat dashboard might find a Pasons item and show no outlets!
            if platform in ('pasons', 'talabat'):
                item_filter['platform'] = platform
            
            if sku:  # SKU is the most specific - use it first
                item_filter['sku__iexact'] = sku
            elif units:  # Fallback to units if no SKU
                item_filter['units__iexact'] = units
            if not include_inactive:
                item_filter['is_active'] = True
            item = Item.objects.filter(**item_filter).first()

        if item is None:
            return JsonResponse({'success': True, 'product': None, 'outlets': []})

        # Platform scoping: STRICT platform isolation
        # Pasons and Talabat are completely separate platforms - no overlap!
        pfilter = {'outlet__platforms': platform}  # Strict isolation

        io_qs = ItemOutlet.objects.select_related('outlet').filter(
            item=item,
            outlet__is_active=True,
            **pfilter
        ).order_by('outlet__name')

        outlets = []
        if io_qs.exists():
            for io in io_qs:
                # Display outlet-specific selling price
                # If outlet has a price set (even 0.00), show it
                # Do NOT auto-calculate from MRP - prices are outlet-specific now
                if io.outlet_selling_price is not None:
                    # Use the outlet's specific price (could be 0.00 if not yet updated)
                    price = io.outlet_selling_price
                else:
                    # No price set at all, default to 0.00
                    price = 0.00
                
                # Calculate enabled status based on stock rules
                # Only show as Enabled if: has stock AND meets quantity requirements
                calculated_enabled = calculate_outlet_enabled_status(item, io.outlet_stock)
                
                # Final status: Must pass both manual flag AND stock rules
                # If manually disabled (is_active_in_outlet=False), stay disabled
                # If stock rules fail, show disabled regardless of manual flag
                effective_active = io.is_active_in_outlet and calculated_enabled
                
                outlets.append({
                    'outlet_name': io.outlet.name,
                    'store_id': io.outlet.store_id,
                    'location': io.outlet.location,
                    'platform': io.outlet.platforms,
                    'price': float(price),
                    'stock': io.outlet_stock,
                    'active': effective_active,  # Now auto-calculated!
                    'stock_status_reason': 'ok' if calculated_enabled else 'insufficient_stock',
                    # Cost fields (OUTLET-LEVEL)
                    # wrap=9900: converted_cost = outlet_cost / WDF
                    # wrap=10000: converted_cost = outlet_cost (no conversion)
                    'outlet_cost': float(io.outlet_cost) if io.outlet_cost is not None else 0.00,
                    'outlet_converted_cost': (
                        float((io.outlet_cost / item.weight_division_factor).quantize(Decimal('0.001')))
                        if io.outlet_cost is not None and item.wrap == '9900' and item.weight_division_factor
                        else (float(io.outlet_cost) if io.outlet_cost is not None else 0.00)
                    ),
                    # MRP and S.Price (OUTLET-SPECIFIC, not global)
                    'outlet_mrp': float(io.outlet_mrp) if io.outlet_mrp else 0.00,
                    'outlet_selling_price': float(price),
                    # BLS states
                    'locked': bool(getattr(io, 'price_locked', False)),
                    'price_locked': bool(getattr(io, 'price_locked', False)),
                    'status_locked': bool(getattr(io, 'status_locked', False)),
                    'associated': True,
                })
        # No fallback - if no ItemOutlet records, return empty outlets list
        # Outlets only appear AFTER price/stock is updated via price-update

        product = {
            'item_code': item.item_code,
            'description': item.description,
            'pack_description': item.pack_description or '',
            'units': item.units,  # ADDED: Include units for unique identification
            'sku': item.sku,  # ADDED: SKU for unique item identification
            'wrap': item.wrap,  # ADDED: wrap type (9900 or 10000)
            'mrp': float(item.mrp),
            'cost': float(item.cost),
            'converted_cost': float(item.converted_cost) if item.converted_cost else None,
            'selling_price': float(item.selling_price),
            'weight_division_factor': float(item.weight_division_factor) if item.weight_division_factor else None,
            # Talabat margin (uses effective_talabat_margin which auto-detects if not set)
            'talabat_margin': float(item.effective_talabat_margin) if item.platform == 'talabat' else None,
            # CLS states
            'price_locked': bool(getattr(item, 'price_locked', False)),
            'status_locked': bool(getattr(item, 'status_locked', False)),
        }

        return JsonResponse({'success': True, 'product': product, 'outlets': outlets})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Outlet availability error: {str(e)}'})


@login_required
def outlet_price_update_api(request):
    """
    Update outlet-specific selling price for an item.
    Expects POST with: item_code or item_id, store_id, price (or new_price).
    """
    from .models import Item, Outlet, ItemOutlet

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})

    try:
        item_code = (request.POST.get('item_code') or '').strip()
        item_id = (request.POST.get('item_id') or '').strip()
        units = (request.POST.get('units') or '').strip()  # NEW: Accept units
        store_id = (request.POST.get('store_id') or '').strip()
        platform = (request.POST.get('platform') or '').strip().lower()
        price_str = (request.POST.get('price') or request.POST.get('new_price') or '').strip()

        if not store_id:
            return JsonResponse({'success': False, 'message': 'store_id is required'})
        if not (item_code or item_id):
            return JsonResponse({'success': False, 'message': 'item_code or item_id is required'})
        if not price_str:
            return JsonResponse({'success': False, 'message': 'price is required'})
        if platform not in ('pasons', 'talabat'):
            return JsonResponse({'success': False, 'message': 'Invalid or missing platform parameter'})

        try:
            new_price = Decimal(price_str)
            if new_price < 0:
                return JsonResponse({'success': False, 'message': 'price must be non-negative'})
        except (InvalidOperation, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid price format'})

        # Resolve item with platform filter
        item = None
        if item_id:
            try:
                item = Item.objects.filter(pk=int(item_id), platform=platform, is_active=True).first()
            except ValueError:
                item = None
        if item is None and item_code:
            # FIXED: Filter by BOTH item_code AND units for unique identification
            item_filter = {'item_code__iexact': item_code, 'platform': platform, 'is_active': True}
            if units:  # If units provided, use it for exact match
                item_filter['units__iexact'] = units
            item = Item.objects.filter(**item_filter).first()
        if item is None:
            return JsonResponse({'success': False, 'message': 'Item not found or inactive'})

        # Resolve outlet
        outlet = Outlet.objects.filter(store_id=store_id, is_active=True).first()
        if outlet is None:
            return JsonResponse({'success': False, 'message': 'Outlet not found or inactive'})

        # CHECK CLS PRICE LOCK FIRST - before any ItemOutlet operations
        if bool(getattr(item, 'price_locked', False)):
            return JsonResponse({'success': False, 'message': 'Price is locked at item level (CLS). Unlock to edit.'})

        # Resolve relation - auto-link if item is already on this platform (via other outlets)
        io = ItemOutlet.objects.filter(item=item, outlet=outlet).first()
        if io is None:
            # Check if item is already associated with this platform via other outlets
            platform = outlet.platforms
            existing_on_platform = ItemOutlet.objects.filter(
                item=item,
                outlet__platforms=platform
            ).exists()
            
            if not existing_on_platform:
                # Item is NOT on this platform yet - don't auto-create (would change platform count)
                return JsonResponse({
                    'success': False, 
                    'message': f'Item is not available on {platform} platform. Please add it via bulk upload first.'
                })
            
            # Item IS on this platform - safe to link to another outlet on same platform
            # Create WITHOUT price first, set price after lock check
            io = ItemOutlet.objects.create(
                item=item,
                outlet=outlet,
                is_active_in_outlet=True,
                outlet_selling_price=item.selling_price  # Default to item price
            )

        # Enforce BLS price lock (CLS already checked above)
        if bool(getattr(io, 'price_locked', False)):
            return JsonResponse({'success': False, 'message': 'Price is locked for this outlet (BLS). Unlock to edit.'})

        io.outlet_selling_price = new_price
        io.save()

        return JsonResponse({
            'success': True,
            'message': 'Outlet price updated',
            'item_code': item.item_code,
            'store_id': outlet.store_id,
            'price': float(new_price)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error updating outlet price: {str(e)}'})


@login_required
def outlet_lock_toggle_api(request):
    """
    Toggle outlet-level status/price lock for an item.
    Current model does not define explicit lock fields; we support status lock
    by toggling `is_active_in_outlet`. Price lock is acknowledged but not persisted.

    Expects POST with: item_code or item_id, store_id, lock_type ('status'|'price'),
    optional 'value' ('true'|'false' or 'lock'|'unlock').
    """
    from .models import Item, Outlet, ItemOutlet

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})

    try:
        item_code = (request.POST.get('item_code') or '').strip()
        item_id = (request.POST.get('item_id') or '').strip()
        units = (request.POST.get('units') or '').strip()  # NEW: Accept units
        store_id = (request.POST.get('store_id') or '').strip()
        lock_type = (request.POST.get('lock_type') or 'status').strip().lower()
        value_raw = (request.POST.get('value') or '').strip().lower()

        if not store_id:
            return JsonResponse({'success': False, 'message': 'store_id is required'})
        if not (item_code or item_id):
            return JsonResponse({'success': False, 'message': 'item_code or item_id is required'})

        # Resolve item
        item = None
        if item_id:
            try:
                item = Item.objects.filter(pk=int(item_id), is_active=True).first()
            except ValueError:
                item = None
        if item is None and item_code:
            # FIXED: Filter by BOTH item_code AND units for unique identification
            item_filter = {'item_code__iexact': item_code, 'is_active': True}
            if units:  # If units provided, use it for exact match
                item_filter['units__iexact'] = units
            item = Item.objects.filter(**item_filter).first()
        if item is None:
            return JsonResponse({'success': False, 'message': 'Item not found or inactive'})

        # Resolve outlet
        outlet = Outlet.objects.filter(store_id=store_id, is_active=True).first()
        if outlet is None:
            return JsonResponse({'success': False, 'message': 'Outlet not found or inactive'})

        # Resolve relation - auto-link if item is already on this platform (via other outlets)
        io = ItemOutlet.objects.filter(item=item, outlet=outlet).first()
        if io is None:
            # Check if item is already associated with this platform via other outlets
            platform = outlet.platforms
            existing_on_platform = ItemOutlet.objects.filter(
                item=item,
                outlet__platforms=platform
            ).exists()
            
            if not existing_on_platform:
                # Item is NOT on this platform yet - don't auto-create (would change platform count)
                return JsonResponse({
                    'success': False, 
                    'message': f'Item is not available on {platform} platform. Please add it via bulk upload first.'
                })
            
            # Item IS on this platform - safe to link to another outlet on same platform
            io = ItemOutlet.objects.create(
                item=item,
                outlet=outlet,
                is_active_in_outlet=True
            )

        # Parse desired value
        desired = None
        if value_raw in ('true', 'lock', 'locked', '1'):
            desired = True
        elif value_raw in ('false', 'unlock', 'unlocked', '0'):
            desired = False

        # Prevent manual BLS Status changes when CLS Status Lock is enabled
        if lock_type == 'status' and bool(getattr(item, 'status_locked', False)):
            return JsonResponse({
                'success': False,
                'message': 'Central Status Lock is enabled for this item; outlet status cannot be changed.'
            })

        # Prevent manual BLS Price changes when CLS Price Lock is enabled
        if lock_type == 'price' and bool(getattr(item, 'price_locked', False)):
            return JsonResponse({
                'success': False,
                'message': 'Central Price Lock is enabled for this item; outlet price lock cannot be changed.'
            })

        if lock_type == 'status':
            # BLS: toggle status lock and reflect in active state (locked => inactive)
            current = bool(getattr(io, 'status_locked', False))
            new_val = (not current) if desired is None else bool(desired)
            io.status_locked = new_val
            io.is_active_in_outlet = not new_val
            io.save(update_fields=['status_locked', 'is_active_in_outlet'])
            
            # Calculate effective status based on stock rules
            # BLS unchecked does NOT auto-enable if stock rules fail
            calculated_enabled = calculate_outlet_enabled_status(item, io.outlet_stock)
            effective_active = io.is_active_in_outlet and calculated_enabled
            
            return JsonResponse({
                'success': True,
                'message': 'Outlet status lock toggled',
                'store_id': outlet.store_id,
                'item_code': item.item_code,
                'active_in_outlet': effective_active,  # Now returns calculated status!
                'status_locked': io.status_locked,
            })
        elif lock_type == 'price':
            # BLS: toggle price lock (no immediate UI badge change)
            current = bool(getattr(io, 'price_locked', False))
            new_val = (not current) if desired is None else bool(desired)
            io.price_locked = new_val
            io.save(update_fields=['price_locked'])
            return JsonResponse({
                'success': True,
                'message': 'Outlet price lock toggled',
                'store_id': outlet.store_id,
                'item_code': item.item_code,
                'price_locked': io.price_locked,
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid lock_type; use status or price'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error toggling outlet lock: {str(e)}'})

@login_required
def cls_lock_toggle_api(request):
    """
    Toggle Central Locking System (CLS) locks for an item.
    Supports both Status and Price locks.

    POST fields:
      - item_code or item_id
      - lock_type: 'status' | 'price' (optional; default 'status')
      - value: 'true'|'false'|'lock'|'unlock' (optional; toggles when missing)
      - Alternatively for price: 'price_locked' can be provided ('on'|'true'|'1')
    """
    from .models import Item, ItemOutlet

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})

    try:
        item_code = (request.POST.get('item_code') or '').strip()
        item_id = (request.POST.get('item_id') or '').strip()
        lock_type = (request.POST.get('lock_type') or 'status').strip().lower()
        value_raw = (request.POST.get('value') or '').strip().lower()

        # Helper to parse boolean-ish values
        def _parse_bool(val):
            return str(val).lower() in ('on', 'true', '1', 'yes', 'locked')

        # Resolve item
        item = None
        if item_id:
            try:
                item = Item.objects.filter(pk=int(item_id), is_active=True).first()
            except ValueError:
                item = None
        if item is None and item_code:
            item = Item.objects.filter(item_code__iexact=item_code, is_active=True).first()
        if item is None:
            return JsonResponse({'success': False, 'message': 'Item not found or inactive'})

        # Parse desired value
        desired = None
        if value_raw in ('true', 'lock', 'locked', '1'):
            desired = True
        elif value_raw in ('false', 'unlock', 'unlocked', '0'):
            desired = False

        if lock_type == 'status':
            current = bool(getattr(item, 'status_locked', False))
            new_val = (not current) if desired is None else bool(desired)

            # Update item CLS status lock
            item.status_locked = new_val
            item.save(update_fields=['status_locked'])

            # Cascade to all ItemOutlet rows via model helper
            cascade_success = True
            try:
                item.cascade_cls_status_to_outlets(new_val)
            except Exception as e:
                logger.warning(f"CLS status cascade failed for item {item.item_code}: {e}")
                cascade_success = False

            # Verify cascade by checking ItemOutlet records
            outlet_locks = ItemOutlet.objects.filter(
                item=item,
                outlet__platforms=item.platform
            ).values('outlet__name', 'status_locked')
            
            outlet_lock_summary = {
                str(ol['outlet__name']): ol['status_locked']
                for ol in outlet_locks
            }

            return JsonResponse({
                'success': True,
                'message': 'CLS Status Lock updated',
                'item_code': item.item_code,
                'status_locked': item.status_locked,
                'cascade_success': cascade_success,
                'outlet_locks': outlet_lock_summary,  # ← Frontend can refresh with this
            })

        elif lock_type == 'price':
            # Allow either explicit 'price_locked' param or generic 'value'
            if request.POST.get('price_locked') is not None and desired is None:
                desired = _parse_bool(request.POST.get('price_locked'))
            current = bool(getattr(item, 'price_locked', False))
            new_val = (not current) if desired is None else bool(desired)

            # Update item CLS price lock
            item.price_locked = new_val
            item.save(update_fields=['price_locked'])

            # Cascade to outlets' price locks via model helper
            cascade_success = True
            try:
                item.cascade_cls_price_to_outlets(new_val)
            except Exception as e:
                logger.warning(f"CLS price cascade failed for item {item.item_code}: {e}")
                cascade_success = False

            # Verify cascade by checking ItemOutlet records
            outlet_locks = ItemOutlet.objects.filter(
                item=item,
                outlet__platforms=item.platform
            ).values('outlet__name', 'price_locked')
            
            outlet_lock_summary = {
                str(ol['outlet__name']): ol['price_locked']
                for ol in outlet_locks
            }

            return JsonResponse({
                'success': True,
                'message': 'CLS Price Lock updated',
                'item_code': item.item_code,
                'price_locked': item.price_locked,
                'cascade_success': cascade_success,
                'outlet_locks': outlet_lock_summary,  # ← Frontend can refresh with this
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid lock_type; use status or price'})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'CLS lock toggle error: {str(e)}'})

@login_required
def save_product_api(request):
    """
    API endpoint to save/update a product
    Supports both JSON body and form data
    """
    from .models import Item, ItemOutlet
    import json
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        # Parse request data - support both JSON and form data
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        else:
            # Fallback to form data
            data = request.POST
        
        # Helper to get value from parsed data
        def get_val(key, default=''):
            val = data.get(key, default)
            if val is None:
                return default
            return val
        
        item_code = str(get_val('item_code', '')).strip()
        if not item_code:
            return JsonResponse({'success': False, 'message': 'Item code is required'})
        
        # Normalize incoming fields and provide sensible fallbacks
        name = str(get_val('description', get_val('name', '')))
        pack_description = str(get_val('pack_description', ''))
        stock_quantity = int(get_val('stock', get_val('stock_quantity', 0)) or 0)
        selling_price = float(get_val('selling_price', 0) or 0)
        mrp = float(get_val('mrp', 0) or 0)
        sku = str(get_val('sku', ''))
        barcode = str(get_val('barcode', ''))
        # Support both 'cost' and 'cost_price' field names
        cost_str = get_val('cost', get_val('cost_price', 0))
        cost = float(cost_str or 0)
        wrap = str(get_val('wrap', ''))
        weight_division_factor_str = str(get_val('weight_division_factor', ''))
        weight_division_factor = float(weight_division_factor_str) if weight_division_factor_str else None
        outer_case_quantity_str = str(get_val('outer_case_quantity', ''))
        outer_case_quantity = int(outer_case_quantity_str) if outer_case_quantity_str else None
        minimum_qty_str = str(get_val('minimum_qty', ''))
        minimum_qty = int(minimum_qty_str) if minimum_qty_str else None
        is_active_val = get_val('is_active', '')
        is_active = str(is_active_val).lower() in ('on', 'true', '1', 'yes') if is_active_val else True
        # CLS toggles
        def _parse_bool(val):
            return str(val).lower() in ('on', 'true', '1', 'yes')
        price_locked_flag = _parse_bool(get_val('price_locked', ''))
        status_locked_flag = _parse_bool(get_val('status_locked', ''))
        # Note: stock_status is auto-calculated on frontend based on outlet stock (not stored in DB)

        # Validate wrap strictly when provided
        if wrap and wrap not in ALLOWED_WRAP_VALUES:
            return JsonResponse({'success': False, 'message': "Wrap must be 9900 or 10000"})
        
        # Get platform from request
        platform = str(get_val('platform', '')).strip()
        if platform not in ('pasons', 'talabat'):
            return JsonResponse({'success': False, 'message': 'Invalid or missing platform parameter'})
        
        # Try to get existing item or create new one - WITH PLATFORM FILTER
        item, created = Item.objects.get_or_create(
            platform=platform,  # ✓ Add platform filter for platform isolation
            item_code=item_code,
            defaults={
                'platform': platform,  # ✓ Set platform in defaults
                'description': name,
                'pack_description': pack_description,
                'stock': stock_quantity,
                'selling_price': selling_price,
                'mrp': mrp,
                'sku': sku,
                'barcode': barcode,
                'cost': cost,
                'wrap': wrap,
                'weight_division_factor': weight_division_factor,
                'outer_case_quantity': outer_case_quantity,
                'minimum_qty': minimum_qty,
                'units': str(get_val('units', '')),
                'is_active': is_active,
                'price_locked': price_locked_flag,
                'status_locked': status_locked_flag,
                # stock_status is frontend-calculated field (not stored)
            }
        )
        
        # Calculate converted_cost = cost / weight_division_factor
        if weight_division_factor and weight_division_factor > 0:
            from decimal import Decimal
            converted_cost = Decimal(str(cost)) / Decimal(str(weight_division_factor))
            item.converted_cost = converted_cost
        else:
            item.converted_cost = None
        
        # Track original CLS status to determine cascade needs
        original_status_locked = item.status_locked if not created else None

        if not created:
            # Update existing item
            item.description = name or item.description
            item.pack_description = pack_description or item.pack_description
            item.stock = stock_quantity if 'stock' in data or 'stock_quantity' in data else item.stock
            item.selling_price = selling_price if 'selling_price' in data else item.selling_price
            item.mrp = mrp if 'mrp' in data else item.mrp
            item.sku = sku or item.sku
            item.barcode = barcode or item.barcode
            item.cost = cost if ('cost' in data or 'cost_price' in data) else item.cost
            item.wrap = wrap or item.wrap
            item.weight_division_factor = weight_division_factor if weight_division_factor_str else item.weight_division_factor
            item.outer_case_quantity = outer_case_quantity if outer_case_quantity_str else item.outer_case_quantity
            item.minimum_qty = minimum_qty if minimum_qty_str else item.minimum_qty
            item.units = str(get_val('units', '')) or item.units
            item.is_active = is_active
            # Only update locks if provided
            if 'price_locked' in data:
                item.price_locked = price_locked_flag
            if 'status_locked' in data:
                item.status_locked = status_locked_flag
            
            # Recalculate converted_cost when weight_division_factor is updated
            if weight_division_factor_str:
                if weight_division_factor and weight_division_factor > 0:
                    from decimal import Decimal
                    item.converted_cost = Decimal(str(item.cost)) / Decimal(str(weight_division_factor))
                else:
                    item.converted_cost = None
            
            item.save()
        else:
            # Item created with initial flags already set in get_or_create defaults
            pass

        # Cascade CLS Status Lock to all ItemOutlet rows for this item when provided
        if 'status_locked' in data:
            try:
                ItemOutlet.objects.filter(
                    item=item,
                    outlet__platforms=platform  # STRICT platform isolation
                ).update(
                    status_locked=status_locked_flag,
                    is_active_in_outlet=(not status_locked_flag)
                )
            except Exception as e:
                # Do not fail save; report cascade issue in message for awareness
                logger.warning(f"CLS status cascade failed for item {item.item_code}: {e}")
        
        action = 'created' if created else 'updated'
        return JsonResponse({
            'success': True, 
            'message': f'Product {action} successfully!',
            'item_code': item.item_code
        })
        
    except ValueError as e:
        return JsonResponse({'success': False, 'message': f'Invalid data format: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error saving product: {str(e)}'})


@login_required
def item_deletion(request):
    """
    Item deletion page view that renders the item deletion template
    """
    context = {
        'page_title': 'Item Deletion Management',
        'active_page': 'item_deletion'
    }
    return render(request, 'item_deletion.html', context)


@login_required
def shop_integration(request):
    """
    Shop Integration page with tabs for different integration methods
    Tabs: CSV/Manual | SFTP | API
    Sub-tabs: Pasons | Talabat
    """
    from .models import UploadHistory, Outlet, ExportHistory
    
    # Get recent uploads for each platform (load more for pagination)
    pasons_uploads = UploadHistory.objects.filter(platform='pasons').select_related('outlet')[:100]
    talabat_uploads = UploadHistory.objects.filter(platform='talabat').select_related('outlet')[:100]
    global_uploads = UploadHistory.objects.filter(platform='global').select_related('outlet')[:100]
    
    # Get export history for each platform
    pasons_exports = ExportHistory.objects.filter(platform='pasons').select_related('outlet').order_by('-export_timestamp')[:50]
    talabat_exports = ExportHistory.objects.filter(platform='talabat').select_related('outlet').order_by('-export_timestamp')[:50]
    
    # Get outlets for each platform (for export dropdown)
    pasons_outlets = Outlet.objects.filter(platforms='pasons', is_active=True).order_by('name')
    talabat_outlets = Outlet.objects.filter(platforms='talabat', is_active=True).order_by('name')
    
    context = {
        'page_title': 'Shop Integration',
        'active_page': 'shop_integration',
        'pasons_uploads': pasons_uploads,
        'talabat_uploads': talabat_uploads,
        'global_uploads': global_uploads,
        'pasons_exports': pasons_exports,
        'talabat_exports': talabat_exports,
        'pasons_outlets': pasons_outlets,
        'talabat_outlets': talabat_outlets,
    }
    return render(request, 'shop_integration.html', context)


@login_required
def preview_csv_api(request):
    """
    API endpoint to preview CSV data before creating items or updating products
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        platform = request.POST.get('platform')
        csv_file = request.FILES.get('csv_file')
        operation_type = request.POST.get('operation_type', 'bulk_creation')  # Default to bulk creation
        
        if not platform or not csv_file:
            return JsonResponse({'success': False, 'message': 'Platform and CSV file are required'})
        
        # Process CSV file for preview
        import csv
        import io
        
        # Read CSV content with encoding fallback
        csv_content, encoding_used = decode_csv_upload(csv_file)
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        preview_data = []
        errors = []
        warnings = []

        # Header validation based on operation type
        if operation_type == 'product_update':
            # Product update: only these 5 fields allowed
            required_headers = {'item_code', 'units'}
            optional_headers = {'mrp', 'cost', 'stock'}
            allowed_headers = required_headers | optional_headers
        else:
            # Bulk creation: requires all item creation fields
            required_headers = {'wrap', 'item_code', 'description', 'units', 'sku', 'pack_description'}
            optional_headers = {'barcode', 'mrp', 'selling_price', 'cost', 'stock', 'weight_division_factor', 'outer_case_quantity', 'minimum_qty'}
            allowed_headers = required_headers | optional_headers
        
        # Filter out empty header fields (from trailing delimiters)
        header_fields = [h.strip().lower() for h in (csv_reader.fieldnames or []) if h and h.strip()]
        if not header_fields:
            return JsonResponse({'success': False, 'message': 'CSV is missing header row. Include headers exactly as specified.'})
        if 'is_active' in header_fields:
            return JsonResponse({'success': False, 'message': "Column 'is_active' is not allowed in the CSV. Remove it and try again."})
        missing_required = sorted(list(required_headers - set(header_fields)))
        unknown_headers = sorted([h for h in header_fields if h and h not in allowed_headers])
        if missing_required:
            return JsonResponse({'success': False, 'message': f"Missing required columns: {', '.join(missing_required)}. The file was rejected."})
        if unknown_headers:
            return JsonResponse({'success': False, 'message': f"Unknown columns present: {', '.join(unknown_headers)}. Only defined headers are allowed."})

        # Read CSV rows for preview
        csv_rows = list(csv_reader)
        
        # Detect operation type based on CSV headers if not specified
        if csv_rows and operation_type == 'bulk_creation':
            headers = list(csv_rows[0].keys())
            # Check if this looks like a product update CSV (has Item Code, Units, MRP, Stock)
            product_update_headers = ['Item Code', 'Units', 'MRP', 'Stock']
            if all(header in headers for header in product_update_headers):
                operation_type = 'product_update'
        
        # Validate entire file rows strictly; reject on any missing required or invalid numeric
        if operation_type == 'bulk_creation':
            fatal_row_errors = []
            for idx, r in enumerate(csv_rows, start=2):
                m = {
                    'wrap': r.get('wrap', '').strip(),
                    'item_code': r.get('item_code', '').strip(),
                    'description': r.get('description', '').strip(),
                    'units': r.get('units', '').strip(),
                    'sku': r.get('sku', '').strip(),
                    'pack_description': r.get('pack_description', '').strip(),
                }
                missing = [k for k, v in m.items() if not v]
                if missing:
                    fatal_row_errors.append(f"Row {idx}: Missing mandatory fields: {', '.join(missing)}")
                    continue
                # Validate wrap strictly
                if m['wrap'] not in ALLOWED_WRAP_VALUES:
                    fatal_row_errors.append(f"Row {idx}: Wrap must be 9900 or 10000 (got '{m['wrap']}')")
                    continue
                # Optional numeric validations
                try:
                    sp = r.get('selling_price', '').strip()
                    st = r.get('stock', '').strip()
                    c = r.get('cost', '').strip()
                    mval = r.get('mrp', '').strip()
                    wdf = r.get('weight_division_factor', '').strip()
                    ocq = r.get('outer_case_quantity', '').strip()
                    minq = r.get('minimum_qty', '').strip()
                    if sp:
                        Decimal(sp)
                    if st:
                        int(st)
                    if c:
                        Decimal(c)
                    if mval:
                        Decimal(mval)
                    if wdf:
                        Decimal(wdf)
                    if ocq:
                        int(ocq)
                    if minq:
                        int(minq)
                except (InvalidOperation, ValueError):
                    fatal_row_errors.append(f"Row {idx}: Invalid numeric values in one of [selling_price, stock, cost, mrp, weight_division_factor, outer_case_quantity, minimum_qty]")
                    continue
            if fatal_row_errors:
                # Return a concise message; front-end shows only message when success=false
                first = fatal_row_errors[:3]
                return JsonResponse({
                    'success': False,
                    'message': 'CSV validation failed; the file was rejected. First issues: ' + ' | '.join(first)
                })

        for row_num, row in enumerate(csv_rows[:20], start=2):  # Preview first 20 rows
            try:
                if operation_type == 'product_update':
                    # Product Update CSV validation
                    item_code = row.get('Item Code', row.get('item_code', '')).strip()
                    units = row.get('Units', row.get('units', '')).strip()
                    mrp_str = row.get('MRP', row.get('mrp', '')).strip()
                    cost_str = row.get('Cost', row.get('cost', '')).strip()
                    stock_str = row.get('Stock', row.get('stock', '')).strip()
                    
                    # Validate mandatory fields for product update (only item_code and units required)
                    row_status = 'valid'
                    row_errors = []
                    
                    if not item_code:
                        row_errors.append("Missing: item_code")
                        row_status = 'error'
                    if not units:
                        row_errors.append("Missing: units")
                        row_status = 'error'
                    
                    # Validate numeric fields
                    mrp = 0.0
                    cost = 0.0
                    stock = 0
                    try:
                        if mrp_str:
                            mrp = float(mrp_str)
                        if cost_str:
                            cost = float(cost_str)
                        if stock_str:
                            stock = int(float(stock_str))  # Handle decimal stock values
                    except ValueError:
                        row_errors.append("Invalid numeric values")
                        row_status = 'error'
                    
                    # Check if item exists for product update
                    from .models import Item
                    if item_code and units:
                        if not Item.objects.filter(item_code=item_code, units=units).exists():
                            row_errors.append(f"Item '{item_code}' ({units}) not found")
                            row_status = 'error'
                    
                    preview_data.append({
                        'row_number': row_num,
                        'status': row_status,
                        'errors': row_errors,
                        'data': {
                            'item_code': item_code,
                            'units': units,
                            'mrp': mrp,
                            'cost': cost,
                            'stock': stock
                        }
                    })
                    
                else:
                    # Bulk Item Creation CSV validation (original logic)
                    base_item_code = row.get('item_code', '').strip()
                    base_sku = row.get('sku', '').strip()
                    
                    # Validate mandatory fields
                    mandatory_fields = {
                        'wrap': row.get('wrap', '').strip(),
                        'item_code': base_item_code,
                        'description': row.get('description', '').strip(),
                        'units': row.get('units', '').strip(),
                        'sku': base_sku,
                        'pack_description': row.get('pack_description', '').strip()
                    }
                    
                    # Handle optional fields
                    selling_price_str = row.get('selling_price', '').strip()
                    stock_str = row.get('stock', '').strip()
                    cost_str = row.get('cost', '').strip()
                    mrp_str = row.get('mrp', '').strip()
                    wdf_str = row.get('weight_division_factor', '').strip()
                    ocq_str = row.get('outer_case_quantity', '').strip()
                    minq_str = row.get('minimum_qty', '').strip()
                    
                    # Check for missing mandatory fields
                    missing_fields = [field for field, value in mandatory_fields.items() if not value]
                    row_status = 'valid'
                    row_errors = []
                    
                    if missing_fields:
                        row_errors.append(f"Missing: {', '.join(missing_fields)}")
                        row_status = 'error'
                    
                    # Validate numeric fields (optional fields are now weight_division_factor, outer_case_quantity, minimum_qty)
                    try:
                        selling_price = float(selling_price_str) if selling_price_str else 0.0
                        stock = int(stock_str) if stock_str else 0
                        cost = float(cost_str) if cost_str else 0.0
                        mrp = float(mrp_str) if mrp_str else 0.0
                        wdf = float(wdf_str) if wdf_str else None
                        ocq = int(ocq_str) if ocq_str else None
                        minq = int(minq_str) if minq_str else None
                    except ValueError:
                        row_errors.append("Invalid numeric values in one of [selling_price, stock, cost, mrp, weight_division_factor, outer_case_quantity, minimum_qty]")
                        row_status = 'error'
                        selling_price = 0.0
                        stock = 0
                        cost = 0.0
                        mrp = 0.0
                        wdf = None
                        ocq = None
                        minq = None
                    
                    # Handle optional fields
                    barcode = row.get('barcode', '').strip()
                    
                    # Check if item already exists and apply platform-specific duplicate handling
                    from .models import Item, ItemOutlet
                    existing_item = Item.objects.filter(sku=base_sku).first()
                    if existing_item:
                        if platform in ('pasons', 'talabat'):
                            linked = ItemOutlet.objects.filter(
                                item=existing_item,
                                outlet__platforms=platform  # STRICT isolation
                            ).exists()
                            if linked:
                                # Duplicate within selected platform: mark as row error
                                row_errors.append(
                                    f"SKU '{base_sku}' already exists for {platform}; duplicate creation is not allowed."
                                )
                                row_status = 'error'
                            else:
                                # Cross-platform reuse: no warning; item will be linked on upload
                                pass
                        else:
                            # Unknown platform context: keep as valid without warnings
                            pass
                    
                    preview_data.append({
                        'row_number': row_num,
                        'status': row_status,
                        'errors': row_errors,
                        'data': {
                            'wrap': mandatory_fields['wrap'],
                            'item_code': base_item_code,
                            'description': mandatory_fields['description'],
                            'pack_description': mandatory_fields['pack_description'],
                            'units': mandatory_fields['units'],
                            'barcode': barcode,
                            'sku': base_sku,
                            'selling_price': selling_price,
                            'stock': stock,
                            'cost': cost,
                            'mrp': mrp,
                            'weight_division_factor': wdf,
                            'outer_case_quantity': ocq,
                            'minimum_qty': minq
                        }
                    })
                
            except Exception as e:
                errors.append(f"Row {row_num}: Error processing - {str(e)}")
        
        # Get platform outlets info
        from .models import Outlet
        from django.db import models
        outlets = Outlet.objects.filter(
            is_active=True,
            platforms=platform  # STRICT isolation
        )
        
        return JsonResponse({
            'success': True,
            'preview_data': preview_data,
            'total_rows': len(csv_rows),
            'preview_rows': len(preview_data),
            'errors': errors,
            'warnings': warnings,
            'platform': platform,
            'outlets': [{'name': outlet.name, 'id': outlet.id} for outlet in outlets],
            'encoding_used': encoding_used
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error processing CSV: {str(e)}'})


@login_required
@rate_limit(max_requests=10, time_window_seconds=60)  # 10 requests per minute
def delete_items_api(request):
    """
    API endpoint for deleting items (both bulk and single deletion)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        import json
        from .models import Item
        from django.db import models
        
        data = json.loads(request.body)
        combination_keys = data.get('combination_keys', [])  # item_code|description|sku
        deletion_type = data.get('deletion_type', 'single')
        delete_scope = data.get('delete_scope', 'selected')  # selected | current_page | filtered | all
        platform = (data.get('platform') or '').strip()

        from django.db.models import Q, Count

        # Build queryset to delete based on scope
        items_to_delete = Item.objects.none()
        scope_description = ''

        if delete_scope == 'selected':
            if not combination_keys:
                return JsonResponse({'success': False, 'message': 'No items selected for deletion'})

            query = Q()
            for combination_key in combination_keys:
                parts = combination_key.split('|')
                if len(parts) != 3:
                    continue
                item_code, description, sku = parts
                query |= Q(
                    item_code__iexact=item_code,
                    description__iexact=description,
                    sku__iexact=sku
                )
            items_to_delete = Item.objects.filter(query)
            if platform in ('pasons', 'talabat'):
                items_to_delete = items_to_delete.filter(platform=platform)
            scope_description = f"selected ({len(combination_keys)})"

        elif delete_scope == 'current_page':
            # Expect combination_keys of the currently displayed items (100/200)
            if not combination_keys:
                return JsonResponse({'success': False, 'message': 'No page items provided for deletion'})
            query = Q()
            for combination_key in combination_keys:
                parts = combination_key.split('|')
                if len(parts) != 3:
                    continue
                item_code, description, sku = parts
                query |= Q(
                    item_code__iexact=item_code,
                    description__iexact=description,
                    sku__iexact=sku
                )
            items_to_delete = Item.objects.filter(query)
            if platform in ('pasons', 'talabat'):
                items_to_delete = items_to_delete.filter(platform=platform)
            scope_description = f"current_page ({len(combination_keys)})"

        elif delete_scope == 'filtered':
            # Filters payload matching search_product_api params
            filters = data.get('filters', {})
            platform = (data.get('platform') or '').strip()
            include_inactive = (data.get('include_inactive') or False) in (True, '1', 'true', 'True')
            item_code = (filters.get('item_code') or '').strip()
            description = (filters.get('description') or '').strip()
            barcode = (filters.get('barcode') or '').strip()
            sku = (filters.get('sku') or '').strip()
            price_min = (filters.get('price_min') or '').strip()
            price_max = (filters.get('price_max') or '').strip()
            stock_min = (filters.get('stock_min') or '').strip()
            stock_max = (filters.get('stock_max') or '').strip()

            qs = Item.objects.all() if include_inactive else Item.objects.filter(is_active=True)
            if platform in ('pasons', 'talabat'):
                qs = qs.filter(platform=platform)
            if item_code:
                qs = qs.filter(item_code__icontains=item_code)
            if description:
                qs = qs.filter(description__icontains=description)
            if barcode:
                qs = qs.filter(barcode__icontains=barcode)
            if sku:
                qs = qs.filter(sku__icontains=sku)
            if price_min:
                try:
                    qs = qs.filter(selling_price__gte=float(price_min))
                except ValueError:
                    pass
            if price_max:
                try:
                    qs = qs.filter(selling_price__lte=float(price_max))
                except ValueError:
                    pass
            if stock_min:
                try:
                    qs = qs.filter(stock__gte=int(stock_min))
                except ValueError:
                    pass
            if stock_max:
                try:
                    qs = qs.filter(stock__lte=int(stock_max))
                except ValueError:
                    pass

            items_to_delete = qs
            scope_description = "filtered"

        elif delete_scope == 'all':
            # Require strong confirmation to prevent accidental wipe
            confirm_all = data.get('confirm_all', False)
            confirm_text = (data.get('confirm_text') or '').strip()
            if not (confirm_all and confirm_text.upper() == 'DELETE ALL'):
                return JsonResponse({'success': False, 'message': 'Full delete requires confirmation: type "DELETE ALL"'})
            # If a platform is provided, limit to items linked to that platform; otherwise entire database
            if (data.get('platform') or '').strip() in ('pasons', 'talabat'):
                platform = (data.get('platform') or '').strip()
                items_to_delete = Item.objects.filter(platform=platform)
                scope_description = f"entire_database_for_platform_{platform}"
            else:
                items_to_delete = Item.objects.all()
                scope_description = "entire_database"

        else:
            return JsonResponse({'success': False, 'message': 'Invalid delete scope'})

        if not items_to_delete.exists():
            return JsonResponse({'success': False, 'message': 'No items found for deletion'})

        # For platform-safe deletion: first remove ItemOutlet associations for selected platform,
        # then delete Item objects that become orphaned (no outlets remain)
        # Collect brief audit info (limit to first 50 to avoid log blow-up)
        deleted_items_info = []
        for item in items_to_delete[:50]:
            deleted_items_info.append({
                'id': item.id,
                'item_code': item.item_code,
                'description': item.description,
                'sku': item.sku
            })

        # Delete associations specific to selected platform if provided; otherwise, delete all associations
        if platform in ('pasons', 'talabat'):
            associations_qs = ItemOutlet.objects.filter(
                item__in=items_to_delete,
                outlet__platforms=platform
            )
        else:
            associations_qs = ItemOutlet.objects.filter(item__in=items_to_delete)

        associations_count = associations_qs.count()
        associations_qs.delete()

        # Now delete items that are no longer associated with any outlet
        orphan_items_qs = Item.objects.filter(id__in=items_to_delete.values_list('id', flat=True))\
            .annotate(outlet_count=Count('item_outlets')).filter(outlet_count=0)
        items_deleted_count = orphan_items_qs.count()
        orphan_items_qs.delete()

        logger.info(
            f"User {request.user.username} deletion via {deletion_type} ({scope_description}) | Associations removed: {associations_count}, Items deleted: {items_deleted_count}"
        )

        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {items_deleted_count} item(s) and removed {associations_count} association(s)',
            'deleted_count': items_deleted_count,
            'associations_deleted': associations_count,
            'deletion_type': deletion_type,
            'delete_scope': delete_scope
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    except Exception as e:
        logger.error(f"Error in delete_items_api: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error deleting items: {str(e)}'})


@login_required
def export_feed_api(request):
    """
    API endpoint to export production data (SKU, selling_price, stock_status) for e-commerce sync.
    
    FEATURES:
    ✓ Full export: All items at outlet
    ✓ Partial export: Only items changed since last successful export
    ✓ Data validation: All items checked before export
    ✓ Integrity tracking: ExportHistory records every export
    ✓ Transaction safety: Atomic operations
    
    Query parameters:
    - platform: 'pasons' or 'talabat' (required)
    - outlet_id: ID of outlet to export (required)
    - export_type: 'full' or 'partial' (optional, default='partial' for auto-detect)
    
    Returns:
    - Success: CSV file download with headers [sku, selling_price, stock_status]
    - Error: JSON response with error details
    
    CSV FILENAME FORMAT:
        OutletName_YYYY-MM-DD_HHMMSS.csv
        Example: PASONS_14_2025-12-15_143530.csv
    
    EXPORT LOGIC:
    - Full: Export all active items at outlet
    - Partial: Export only items changed since last successful full/partial export
    - First export: Always treated as full export
    """
    import csv
    from django.http import HttpResponse
    from django.utils import timezone
    from .export_service import ExportService
    
    # Parse query parameters
    platform = request.GET.get('platform', '').strip()
    outlet_id = request.GET.get('outlet_id', '').strip()
    export_type_param = request.GET.get('export_type', '').strip()  # Can be '', 'full', or 'partial'
    
    # VALIDATION 1: Platform
    if platform not in ('pasons', 'talabat'):
        logger.warning(f"Invalid platform: {platform}")
        return JsonResponse({
            'success': False,
            'message': 'Invalid platform. Must be "pasons" or "talabat".'
        })
    
    # VALIDATION 2: Outlet ID
    if not outlet_id or not outlet_id.isdigit():
        logger.warning(f"Invalid outlet_id: {outlet_id}")
        return JsonResponse({
            'success': False,
            'message': 'Outlet ID is required and must be numeric.'
        })
    
    try:
        outlet = Outlet.objects.get(id=int(outlet_id), platforms=platform)
    except Outlet.DoesNotExist:
        logger.warning(f"Outlet not found: id={outlet_id}, platform={platform}")
        return JsonResponse({
            'success': False,
            'message': f'Outlet with ID {outlet_id} not found on {platform} platform.'
        })
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Outlet ID must be numeric.'
        })
    
    try:
        # Create export service
        export_service = ExportService(outlet, platform)
        
        # Determine export type
        # If user explicitly requested full/partial, use that; otherwise auto-detect
        manual_export_type = export_type_param if export_type_param in ('full', 'partial') else None
        
        # Execute export
        export_data, export_history = export_service.export(
            user=request.user if request.user.is_authenticated else None,
            manual_export_type=manual_export_type
        )
        
        # Check if export succeeded
        if export_data is None:
            logger.error(
                f"Export failed for {outlet.name}: {export_history.status}. "
                f"Errors: {export_history.validation_errors}"
            )
            # Parse validation errors from JSON string
            import json
            validation_errors_list = []
            if export_history.validation_errors:
                try:
                    validation_errors_list = json.loads(export_history.validation_errors)
                except (json.JSONDecodeError, TypeError):
                    validation_errors_list = [export_history.validation_errors]
            
            return JsonResponse({
                'success': False,
                'message': f'Export validation failed: {export_history.get_status_display()}',
                'validation_errors': validation_errors_list,
                'export_history_id': export_history.id
            })
        
        # EXPORT SUCCEEDED - Generate CSV
        now = timezone.localtime(timezone.now())
        outlet_name_clean = outlet.name.replace(' ', '-').replace('/', '-')
        filename = f"{outlet_name_clean}-{now.strftime('%Y-%m-%d-%H%M%S')}.csv"
        
        # Update ExportHistory with filename
        export_history.file_name = filename
        export_history.save(update_fields=['file_name'])
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow(['sku', 'selling_price', 'stock_status'])
        
        # Write data rows
        for row in export_data:
            writer.writerow([
                row['sku'],
                row['selling_price'],
                row['stock_status']
            ])
        
        logger.info(
            f"Export successful: {outlet.name} ({platform}) - "
            f"{export_history.get_export_type_display()} - "
            f"{len(export_data)} items - File: {filename}"
        )
        
        return response
    
    except Exception as e:
        logger.exception(f"Unexpected error in export_feed_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An unexpected error occurred during export.',
            'error_details': str(e)
        })
