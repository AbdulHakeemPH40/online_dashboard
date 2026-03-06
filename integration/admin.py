# Clean admin.py - minimal setup for fresh start
from django.contrib import admin
from .models import Outlet, Item, ItemOutlet

# Customize admin site
admin.site.site_header = 'Middleware Dashboard Administration'
admin.site.site_title = 'Middleware Dashboard Admin'
admin.site.index_title = 'Welcome to Middleware Dashboard Administration'


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    """Admin interface for Outlet model with OAuth2 credentials"""
    
    list_display = ('name', 'store_id', 'platforms', 'is_active', 'has_oauth_creds')
    list_filter = ('platforms', 'is_active', 'created_at')
    search_fields = ('name', 'location', 'store_id')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'location', 'store_id', 'platforms', 'is_active')
        }),
        ('Pasons Live Configuration', {
            'fields': (
                'pasons_live_store_id',
                'api_endpoint',
                'api_key',
                'push_enabled'
            ),
            'classes': ('collapse',),
            'description': 'Configuration for pasons.live e-commerce platform'
        }),
        ('OAuth2 API Credentials', {
            'fields': (
                'pasons_client_id',
                'pasons_client_secret',
                'pasons_access_token',
                'pasons_refresh_token',
                'pasons_token_expires_at'
            ),
            'classes': ('collapse',),
            'description': 'OAuth2 credentials for pasons.live API integration. Keep these secure!'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('store_id', 'created_at', 'updated_at', 'pasons_access_token', 'pasons_refresh_token', 'pasons_token_expires_at')
    
    def has_oauth_creds(self, obj):
        """Check if outlet has OAuth2 credentials configured"""
        return bool(obj.pasons_client_id and obj.pasons_client_secret)
    has_oauth_creds.short_description = 'OAuth2 Configured'
    has_oauth_creds.boolean = True


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin interface for Item model"""
    
    list_display = ('item_code', 'description', 'sku', 'platform', 'is_active')
    list_filter = ('platform', 'is_active', 'created_at')
    search_fields = ('item_code', 'description', 'sku')
    
    fieldsets = (
        ('Product Information', {
            'fields': ('item_code', 'description', 'sku', 'barcode', 'platform')
        }),
        ('Pricing & Stock', {
            'fields': ('selling_price', 'cost', 'mrp', 'stock', 'units'),
            'classes': ('collapse',),
        }),
        ('Configuration', {
            'fields': ('wrap', 'weight_division_factor', 'converted_cost', 'outer_case_quantity', 'minimum_qty', 'talabat_margin'),
            'classes': ('collapse',),
        }),
        ('Locking System', {
            'fields': ('price_locked', 'status_locked'),
            'description': 'Central Locking System (CLS) - affects all outlets'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ItemOutlet)
class ItemOutletAdmin(admin.ModelAdmin):
    """Admin interface for ItemOutlet model"""
    
    list_display = ('item', 'outlet', 'outlet_stock', 'outlet_selling_price', 'is_active_in_outlet')
    list_filter = ('is_active_in_outlet', 'created_at', 'outlet__platforms')
    search_fields = ('item__item_code', 'outlet__name')
    
    fieldsets = (
        ('Association', {
            'fields': ('item', 'outlet')
        }),
        ('Stock & Pricing', {
            'fields': ('outlet_stock', 'outlet_cost', 'outlet_mrp', 'outlet_selling_price', 'is_active_in_outlet')
        }),
        ('Locking System', {
            'fields': ('price_locked', 'status_locked'),
            'classes': ('collapse',),
            'description': 'Branch Locking System (BLS) - outlet-specific locks'
        }),
        ('Promotion Fields', {
            'fields': ('is_on_promotion', 'promo_price', 'converted_promo', 'original_selling_price', 'promo_start_date', 'promo_end_date'),
            'classes': ('collapse',),
        }),
        ('Change Detection', {
            'fields': ('data_hash', 'export_selling_price', 'export_stock_status', 'erp_export_price'),
            'classes': ('collapse',),
            'description': 'For internal change tracking'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('data_hash', 'created_at', 'updated_at')
