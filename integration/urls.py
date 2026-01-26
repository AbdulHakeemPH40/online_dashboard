from django.urls import path
from .views import (
    login_view, dashboard, talabat_dashboard, erp_page, dashboard_stats_api,
    system_health_check, quick_stats, create_store, store_list,
    edit_store, delete_store, bulk_item_creation, get_outlets_by_platform,
    product_update, rules_update_price, rules_update_stock,
    rules_update_stock_preview, shop_integration, api_push_integration, save_store_id_api, 
    test_connection_api, push_data_api, export_feed_api, download_export_file,
    erp_export_api, download_erp_export_file,
    search_product_api, item_outlets_api, outlet_lock_toggle_api, save_product_api, outlet_price_update_api, item_deletion, delete_items_api, preview_csv_api, cls_lock_toggle_api,
    list_items_api,
    reports_page, locked_products_report, cost_finder_report, export_all_items, export_platform_items, export_outlet_items,
    report_data_api, report_stats_api, locked_products_data_api, export_locked_products_api, cost_finder_data_api, export_cost_finder_api,
    item_search_api, item_inline_edit_api,
    outlet_reset, data_cleaning, outlet_reset_preview_api, outlet_reset_execute_api,
)
from .promotion_views import (
    promotion_update, promotion_search_api, promotion_calculate_api,
    promotion_save_api, promotion_active_api, promotion_cancel_api, promotion_bulk_cancel_api, promotion_cancel_all_api,
    bulk_promotion_update, bulk_promotion_preview_api, bulk_promotion_upload_api,
    promotion_export_api, promotion_erp_export_api, talabat_promotions_xlsx_export, promotion_inline_update_api
)

# Define app namespace
app_name = 'integration'

# URL patterns - minimal for fresh start
urlpatterns = [
    # Dashboard views
    path('', login_view, name='login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('talabat/', talabat_dashboard, name='talabat_dashboard'),
    path('erp/', erp_page, name='erp_page'),
    
    # API endpoints
    path('api/dashboard/stats/', dashboard_stats_api, name='dashboard-stats'),
    path('api/health/', system_health_check, name='health-check'),
    path('api/quick-stats/', quick_stats, name='quick-stats'),
    path('api/search-product/', search_product_api, name='search-product'),
    path('api/item-outlets/', item_outlets_api, name='item_outlets_api'),
    path('api/outlet-lock-toggle/', outlet_lock_toggle_api, name='outlet_lock_toggle_api'),
    path('api/cls-lock-toggle/', cls_lock_toggle_api, name='cls_lock_toggle_api'),
    path('api/outlet-price-update/', outlet_price_update_api, name='outlet_price_update_api'),
    path('api/items/', list_items_api, name='list_items_api'),
    path('api/save-product/', save_product_api, name='save-product'),
    # Store management
    path('create-store/', create_store, name='create_store'),
    path('stores/', store_list, name='store_list'),
    path('edit-store/<int:store_id>/', edit_store, name='edit_store'),
    path('delete-store/<int:store_id>/', delete_store, name='delete_store'),
    # Bulk operations
    path('bulk-item-creation/', bulk_item_creation, name='bulk_item_creation'),
    path('item-deletion/', item_deletion, name='item_deletion'),
    path('api/outlets-by-platform/', get_outlets_by_platform, name='get_outlets_by_platform'),
    path('api/delete-items/', delete_items_api, name='delete_items_api'),
    path('api/preview-csv/', preview_csv_api, name='preview_csv_api'),
    path('product-update/', product_update, name='product_update'),
    path('rules-update-price/', rules_update_price, name='rules_update_price'),
    path('rules-update-stock/', rules_update_stock, name='rules_update_stock'),
    path('api/rules-update-stock-preview/', rules_update_stock_preview, name='rules_update_stock_preview'),
    path('shop-integration/', shop_integration, name='shop_integration'),
    path('api-push-integration/', api_push_integration, name='api_push_integration'),
    path('api/save-store-id/', save_store_id_api, name='save_store_id_api'),
    path('api/test-connection/', test_connection_api, name='test_connection_api'),
    path('api/push-data/', push_data_api, name='push_data_api'),
    path('api/export-feed/', export_feed_api, name='export_feed_api'),
    path('api/download-export/', download_export_file, name='download_export_file'),
    path('api/erp-export/', erp_export_api, name='erp_export_api'),
    path('api/download-erp-export/', download_erp_export_file, name='download_erp_export_file'),
    # Promotion management
    path('promotion-integration/', promotion_update, name='promotion_update'),
    path('bulk-promotion-update/', bulk_promotion_update, name='bulk_promotion_update'),
    path('api/promotion/search/', promotion_search_api, name='promotion_search_api'),
    path('api/promotion/calculate/', promotion_calculate_api, name='promotion_calculate_api'),
    path('api/promotion/save/', promotion_save_api, name='promotion_save_api'),
    path('api/promotion/active/', promotion_active_api, name='promotion_active_api'),
    path('api/promotion/inline-update/', promotion_inline_update_api, name='promotion_inline_update_api'),
    path('api/promotion/<int:promo_id>/cancel/', promotion_cancel_api, name='promotion_cancel_api'),
    path('api/promotion/bulk-cancel/', promotion_bulk_cancel_api, name='promotion_bulk_cancel_api'),
    path('api/promotion/cancel-all/', promotion_cancel_all_api, name='promotion_cancel_all_api'),
    path('api/bulk-promotion/preview/', bulk_promotion_preview_api, name='bulk_promotion_preview_api'),
    path('api/bulk-promotion/upload/', bulk_promotion_upload_api, name='bulk_promotion_upload_api'),
    path('api/promotion/export/', promotion_export_api, name='promotion_export_api'),
    path('api/promotion/erp-export/', promotion_erp_export_api, name='promotion_erp_export_api'),
    path('api/promotion/talabat-xlsx-export/', talabat_promotions_xlsx_export, name='talabat_promotions_xlsx_export'),
    # Dashboard inline editing
    path('api/item/search/', item_search_api, name='item_search_api'),
    path('api/item/inline-edit/', item_inline_edit_api, name='item_inline_edit_api'),
    # Reports
    path('reports/', reports_page, name='reports'),
    path('locked-products-report/', locked_products_report, name='locked_products_report'),
    path('cost-finder-report/', cost_finder_report, name='cost_finder_report'),
    path('reports/export-all/', export_all_items, name='export_all_items'),
    path('reports/export-platform/', export_platform_items, name='export_platform_items'),
    path('reports/export-outlet/', export_outlet_items, name='export_outlet_items'),
    path('api/locked-products-data/', locked_products_data_api, name='locked_products_data_api'),
    path('api/export-locked-products/', export_locked_products_api, name='export_locked_products_api'),
    path('api/cost-finder-data/', cost_finder_data_api, name='cost_finder_data_api'),
    path('api/export-cost-finder/', export_cost_finder_api, name='export_cost_finder_api'),
    path('api/report-data/', report_data_api, name='report_data_api'),
    path('api/report-stats/', report_stats_api, name='report_stats_api'),
    # Outlet Reset System
    path('outlet-reset/', outlet_reset, name='outlet_reset'),
    path('data-cleaning/', data_cleaning, name='data_cleaning'),
    path('api/outlet-reset/preview/', outlet_reset_preview_api, name='outlet_reset_preview_api'),
    path('api/outlet-reset/execute/', outlet_reset_execute_api, name='outlet_reset_execute_api'),
]