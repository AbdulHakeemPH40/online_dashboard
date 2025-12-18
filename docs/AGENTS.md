# Online Dashboard - Multi-Platform E-commerce Integration System

## Project Overview

This is a **Django-based multi-platform e-commerce management dashboard** that handles inventory, pricing, and stock management across **two isolated platforms**: **Pasons Ecommerce** and **Talabat**. Each platform operates independently with its own items, outlets, and associations.

**Key Principle**: Platform Isolation - Items and outlets are platform-specific. Same physical item on both platforms = TWO separate database records.

---

## Technology Stack

### Backend
- **Framework**: Django 5.2.5
- **Database**: SQLite3 (development), PostgreSQL (production recommended)
- **API**: Django REST Framework (DRF)
- **Authentication**: Django built-in User model with session-based auth
- **Python**: 3.9+

### Frontend
- **Templates**: Django Templates (Jinja2-like syntax)
- **CSS**: Custom CSS with modern clean design
- **JavaScript**: Vanilla JavaScript (ES6+)
- **Icons**: Bootstrap Icons
- **Charts**: Chart.js (for analytics)

### Key Dependencies
- `django-cors-headers`: CORS support
- `rest_framework`: API endpoints
- CSV processing: Built-in Python csv module with encoding detection

---

## Database Models & Relationships

### Model Hierarchy

```
User (Django Auth)
    ↓
Outlet (Store/Branch)
    ↓ (Many-to-Many through ItemOutlet)
Item (Product)
    ↓
ItemOutlet (Junction table with outlet-specific data)
```

### 1. Outlet Model
**Purpose**: Represents physical stores/branches

**Key Fields**:
- `name`: Store name (e.g., "Karama", "Deira")
- `location`: Physical address
- `store_id`: Auto-generated 6-digit unique ID
  - Pasons: 100001 - 699999
  - Talabat: 700001 - 999999
- `platforms`: Choice field ('pasons', 'talabat', 'both' - deprecated)
- `is_active`: Boolean for soft delete

**Platform Isolation**:
- Same physical store on both platforms = TWO separate Outlet records
- Example: "Karama Pasons" (100001) ≠ "Karama Talabat" (700001)

### 2. Item Model
**Purpose**: Represents products/SKUs

**Key Fields**:
- `platform`: Platform identifier ('pasons' or 'talabat') - **CRITICAL**
- `item_code`: Product identifier
- `description`: Product name
- `sku`: Stock Keeping Unit (unique per platform)
- `barcode`: Optional product barcode
- `units`: Measurement unit (pcs, kg, ltr, etc.)
- `selling_price`: Base selling price
- `cost`: Cost price
- `mrp`: Maximum Retail Price
- `stock`: Base stock quantity
- `wrap`: Allowed values ('9900', '10000')
- `pack_description`: Package details
- `convert_units`: Unit conversion info
- `price_convert`: Price conversion value

**Central Locking System (CLS)**:
- `price_locked`: When True, price cannot be modified at outlet level
- `status_locked`: When True, status cannot be modified at outlet level

**Platform Isolation**:
- Same SKU on different platforms = TWO separate Item records
- Example: "MILK-001" on Pasons ≠ "MILK-001" on Talabat

### 3. ItemOutlet Model (Junction Table)
**Purpose**: Links Items to Outlets with outlet-specific overrides

**Key Fields**:
- `item`: ForeignKey to Item
- `outlet`: ForeignKey to Outlet
- `outlet_stock`: Stock quantity for this specific outlet
- `outlet_selling_price`: Optional outlet-specific price override
- `is_active_in_outlet`: Active status for this outlet

**Branch Locking System (BLS)**:
- `price_locked`: Outlet-level price lock
- `status_locked`: Outlet-level status lock

**Unique Constraint**: (`item`, `outlet`) - One item can only be linked once per outlet

**Effective Lock Logic**:
- `effective_price_locked`: BLS price_locked OR CLS price_locked
- `effective_status_locked`: BLS status_locked OR CLS status_locked

---

## URL Structure & API Endpoints

### Authentication
- `/` - Login page
- `/logout/` - Logout (POST)
- `/dashboard/` - Pasons dashboard (requires login)
- `/talabat/` - Talabat dashboard (requires login)

### Store Management
- `/integration/stores/` - List all stores
- `/integration/create-store/` - Create new store
- `/integration/edit-store/<id>/` - Edit store
- `/integration/delete-store/<id>/` - Delete store
- `/integration/api/outlets-by-platform/?platform=<pasons|talabat>` - Get outlets by platform (AJAX)

### Bulk Operations
- `/integration/bulk-item-creation/` - Bulk create items via CSV
- `/integration/item-deletion/` - Item deletion management page
- `/integration/product-update/` - Bulk product update via CSV
- `/integration/stock-update/` - Bulk stock update via CSV
- `/integration/price-update/` - Bulk price update via CSV
- `/integration/rules-update-price/` - Rule-based price updates
- `/integration/rules-update-stock/` - Rule-based stock updates

### API Endpoints
- `/integration/api/items/?platform=<platform>&page=<num>&page_size=<num>` - List items with pagination
- `/integration/api/search-product/?q=<query>&platform=<platform>` - Search products
- `/integration/api/delete-items/` - Delete items (POST JSON)
- `/integration/api/preview-csv/` - Preview CSV before upload (POST)
- `/integration/api/save-product/` - Save/update product (POST)
- `/integration/api/item-outlets/` - Get item-outlet associations
- `/integration/api/outlet-lock-toggle/` - Toggle BLS locks (POST)
- `/integration/api/cls-lock-toggle/` - Toggle CLS locks (POST)
- `/integration/api/outlet-price-update/` - Update outlet price (POST)
- `/integration/api/dashboard/stats/` - Dashboard statistics
- `/integration/api/health/` - System health check
- `/integration/api/quick-stats/` - Quick stats for dashboard

---

## HTML Templates & Their Functions

### Template Structure
All templates extend `base.html` which includes:
- Navigation sidebar with platform tabs
- Common CSS/JS resources
- Message display system

### Template-View-API Mapping

| Template | View Function | Primary APIs Used | Purpose |
|----------|--------------|-------------------|---------|
| `login.html` | `login_view` | None | User authentication |
| `dashboard.html` | `dashboard` | `/api/items/`, `/api/dashboard/stats/` | Pasons dashboard |
| `talabat_dashboard.html` | `talabat_dashboard` | `/api/items/`, `/api/dashboard/stats/` | Talabat dashboard |
| `store_list.html` | `store_list` | None (server-rendered) | List all stores |
| `create_store.html` | `create_store` | None (form POST) | Create new store |
| `edit_store.html` | `edit_store` | None (form POST) | Edit store |
| `delete_store.html` | `delete_store` | None (form POST) | Delete store confirmation |
| `bulk_item_creation.html` | `bulk_item_creation` | `/api/outlets-by-platform/` | CSV upload for items |
| `item_deletion.html` | `item_deletion` | `/api/search-product/`, `/api/delete-items/` | Delete items (bulk/single) |
| `product_update.html` | `product_update` | `/api/outlets-by-platform/` | CSV product updates |
| `stock_update.html` | `stock_update` | `/api/outlets-by-platform/` | CSV stock updates |
| `price_update.html` | `price_update` | `/api/outlets-by-platform/` | CSV price updates |
| `rules_update_price.html` | `rules_update_price` | `/api/outlets-by-platform/` | Rule-based pricing |
| `rules_update_stock.html` | `rules_update_stock` | `/api/outlets-by-platform/` | Rule-based stock |

---

## Platform Isolation Architecture

### Core Principle
**Each platform is completely isolated from the other.**

### Implementation Rules

1. **Outlet Creation**:
   - Choose platform: 'pasons' OR 'talabat' (not 'both')
   - Store ID auto-assigned based on platform range
   - One physical store = Two outlet records if on both platforms

2. **Item Creation**:
   - MUST specify platform during creation
   - Same SKU on different platforms = Different Item records
   - Bulk upload filters outlets by selected platform

3. **ItemOutlet Associations**:
   - Only link items to outlets on the SAME platform
   - Validation prevents cross-platform associations

4. **Deletion Behavior**:
   - DELETE ALL on platform 'pasons' ONLY deletes Pasons items
   - Deletes ItemOutlet associations first
   - Then deletes orphaned Items (items with no remaining outlets)

### Example Scenario
```
Physical Store: "Karama Branch"
Platform: Both

Database Records:
1. Outlet (ID: 100023, platform: 'pasons', name: 'Karama')
2. Outlet (ID: 700045, platform: 'talabat', name: 'Karama')

Product: "Fresh Milk 1L"
SKU: MILK-001

Database Records:
1. Item (ID: 501, platform: 'pasons', sku: 'MILK-001')
2. Item (ID: 842, platform: 'talabat', sku: 'MILK-001')

Associations:
1. ItemOutlet (item_id: 501, outlet_id: 100023) - Pasons
2. ItemOutlet (item_id: 842, outlet_id: 700045) - Talabat
```

---

## CSV Upload Formats

### Bulk Item Creation CSV
**Required Headers**:
- `wrap`: '9900' or '10000'
- `item_code`: Product code
- `description`: Product name
- `units`: Unit of measurement
- `convert_units`: Conversion unit (numeric)
- `sku`: Stock Keeping Unit
- `pack_description`: Package description

**Optional Headers**:
- `barcode`: Product barcode
- `mrp`: Maximum Retail Price
- `selling_price`: Selling price
- `cost`: Cost price
- `stock`: Stock quantity
- `price_convert`: Price conversion value

**Forbidden Headers**:
- `is_active`: NOT allowed (all items created as active)

**Validation**:
- Strict header validation (unknown columns rejected)
- Duplicate SKUs within file: only first occurrence processed
- Existing SKU on platform: Item updated, not duplicated
- All mandatory fields required per row
- Numeric fields validated

### Product Update CSV
**Required Headers**:
- `item_code`: Product identifier
- `units`: Unit of measurement

**Optional Headers**:
- `mrp`: Update MRP
- `selling_price`: Update price
- `cost`: Update cost
- `stock`: Update stock

**Identifier**: `item_code` + `units` (unique per platform)

### Stock Update CSV
**Required Headers**:
- `item_code`: Product identifier
- `units`: Unit of measurement
- `stock`: New stock value

**Operations**:
- `replace`: Set exact stock value
- `add`: Increment stock
- `subtract`: Decrement stock

### Price Update CSV
**Required Headers**:
- `item_code`: Product identifier
- `units`: Unit of measurement
- `selling_price`: New selling price

**Optional Headers**:
- `mrp`: Update MRP
- `cost`: Update cost

---

## Critical Business Logic

### Central Locking System (CLS)
**Purpose**: Control item pricing/status from central level

**Behavior**:
- When `Item.price_locked = True`:
  - Outlet-level price changes blocked
  - All associated ItemOutlet records get `price_locked = True`
- When `Item.status_locked = True`:
  - Outlet-level status changes blocked
  - All associated ItemOutlet records get `status_locked = True`
  - All associated ItemOutlet records get `is_active_in_outlet = False`

**Cascade Rules**:
- Changing CLS locks cascades to ALL outlets via `ItemOutlet.objects.filter(item=item).update(...)`
- Functions: `Item.cascade_cls_status_to_outlets()`, `Item.cascade_cls_price_to_outlets()`

### Branch Locking System (BLS)
**Purpose**: Control individual outlet pricing/status

**Behavior**:
- Outlet-level locks work independently
- CLS locks override BLS locks (`effective_price_locked`, `effective_status_locked`)

### Item Deletion Logic
**Delete ALL Process** (from `delete_items_api`):

1. **Scope Determination**:
   - `selected`: Delete specific items by combination_key
   - `current_page`: Delete all items on current page
   - `filtered`: Delete all items matching filters
   - `all`: Delete entire database (requires "DELETE ALL" confirmation)

2. **Platform Filtering**:
   - If platform specified: Only affects that platform's items
   - If no platform: Affects all platforms (dangerous!)

3. **Deletion Steps**:
   ```python
   # Step 1: Delete ItemOutlet associations for platform
   associations = ItemOutlet.objects.filter(
       item__in=items_to_delete,
       outlet__platforms=platform
   )
   associations.delete()
   
   # Step 2: Delete orphaned Items (no outlets remaining)
   orphan_items = Item.objects.filter(
       id__in=items_to_delete.values_list('id', flat=True)
   ).annotate(
       outlet_count=Count('item_outlets')
   ).filter(outlet_count=0)
   orphan_items.delete()
   ```

4. **Response**:
   - Returns count of associations removed
   - Returns count of items deleted
   - Logs deletion with username and scope

---

## Issue Resolution Status

All previously identified issues have been successfully implemented and are fully functional.

### ✅ Resolved Issues

**1. showModal() Function**
- **Status**: ✅ IMPLEMENTED  
- **Location**: `static/js/modal.js` (lines 1-88)  
- **Implementation**: Global `window.showModal()` and `window.confirmModal()` functions  
- **Features**: Promise-based, type-based styling, HTML content support, keyboard shortcuts  

**2. DELETE ALL Confirmation & Feedback**
- **Status**: ✅ FULLY FUNCTIONAL  
- **Backend**: Validates "DELETE ALL" confirmation (case-insensitive, lines 2817-2831)  
- **Frontend**: Displays success/error modals with deletion metrics  
- **Response**: Returns deleted_count & associations_deleted  

**3. Platform Validation**
- **Status**: ✅ COMPREHENSIVE  
- **Coverage**: 18+ validation checks across all API endpoints  
- **Implementation**: Strict validation in: list_items_api, search_product_api, item_outlets_api, save_product_api, delete_items_api  
- **TALABAT ONLY**: rules_update_price endpoint enforces Talabat-only access  

**4. CSV Encoding Detection**
- **Status**: ✅ WORKING CORRECTLY  
- **Location**: `utils.py` `decode_csv_upload()`  
- **Fallback Chain**: UTF-8 → UTF-8-BOM → CP1252 → Latin-1 → UTF-8 with error replacement  

**5. DRF Serializers**
- **Status**: ✅ INTENTIONALLY MINIMALIST  
- **Location**: `serializers.py`  
- **Approach**: Manual dict construction for simple payloads (clearer, less boilerplate)  
- **Future**: Ready to add serializers when complex nested structures required

---

## Development Workflow

### Running the Server
```bash
python manage.py runserver
# Access: http://localhost:8000/
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Creating Superuser
```bash
python manage.py createsuperuser
```

### Static Files
```bash
python manage.py collectstatic
```

### Testing CSV Uploads
1. Select platform (Pasons or Talabat)
2. Ensure outlets exist for that platform
3. Upload CSV with correct headers
4. Check validation messages
5. Verify items created with correct platform

---

## Code Style & Conventions

### Python/Django
- **Imports**: Standard library → Django → Third-party → Local
- **Views**: Function-based views (not class-based)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Docstrings**: Always include for views and complex functions
- **Error Handling**: Try/except with specific exceptions, log errors
- **Messages**: Use Django messages framework for user feedback

### JavaScript
- **Style**: ES6+ features allowed
- **Naming**: camelCase for functions/variables
- **Async**: Use fetch() for AJAX calls
- **Error Handling**: Always include .catch() for promises
- **CSRF**: Always include CSRF token for POST requests

### HTML/Templates
- **Indentation**: 4 spaces (consistent with Python)
- **Template Tags**: `{% %}` for logic, `{{ }}` for variables
- **Comments**: `{# #}` for template comments
- **Blocks**: Always define `{% block %}` sections for extension

### CSS
- **Methodology**: BEM-like naming for components
- **Colors**: Use consistent color scheme (defined in variables)
- **Responsive**: Mobile-first approach with media queries
- **Spacing**: Consistent padding/margin scale (4px, 8px, 12px, 16px, 20px, 24px)

---

## Security Considerations

### Authentication
- All views except login require `@login_required` decorator
- Session-based authentication
- CSRF protection enabled for all POST requests

### Input Validation
- CSV headers strictly validated
- Numeric fields type-checked
- SQL injection prevented by Django ORM
- XSS prevention via Django template auto-escaping

### Platform Isolation Enforcement
- Always filter by platform in queries
- Validate platform parameter in APIs
- Prevent cross-platform associations

---

## Performance Optimization

### Database
- Indexes on frequently queried fields
- `unique_together` constraint on ItemOutlet
- Bulk operations for large datasets (`bulk_create`, `bulk_update`)
- Prefetch related objects to avoid N+1 queries

### Frontend
- Pagination for large item lists (50-200 items per page)
- Lazy loading for tables
- Debounce on search inputs
- Minimize AJAX calls

---

## Testing Strategy

### Manual Testing Checklist
1. **Platform Isolation**:
   - Create items on Pasons → Verify not visible on Talabat
   - Create outlets for each platform → Verify store IDs in correct range
   - Delete all Pasons items → Verify Talabat items intact

2. **CSV Upload**:
   - Invalid headers → Should reject
   - Duplicate SKUs in file → Only first should process
   - Existing SKU → Should update, not duplicate
   - Missing mandatory fields → Should show row errors

3. **Locking System**:
   - Enable CLS status lock → All outlets should lock
   - Try to change outlet status when CLS locked → Should fail
   - Enable BLS price lock → Only that outlet locked

4. **Deletion**:
   - Delete selected items → Should remove associations + orphans
   - Delete all with platform → Only that platform affected
   - Delete all without confirmation → Should reject

---

## Future Enhancements

### Planned Features
1. **PostgreSQL Migration**: Move from SQLite to PostgreSQL for production
2. **Real-time Sync**: WebSocket integration for real-time updates
3. **Analytics Dashboard**: Enhanced reporting with Chart.js
4. **Export Functionality**: Export filtered items to CSV/Excel
5. **Audit Trail**: Track all changes with user attribution
6. **Advanced Filtering**: More filter options for item search
7. **Bulk Edit**: Edit multiple items at once via UI
8. **API Documentation**: Auto-generated API docs with Swagger/OpenAPI
9. **Unit Tests**: Comprehensive test coverage for models/views
10. **Docker Support**: Containerization for easy deployment

### Technical Debt
1. Implement DRF serializers properly
2. Add missing `showModal()` function
3. Strengthen platform validation across all endpoints
4. Add comprehensive error logging
5. Implement rate limiting for API endpoints
6. Add database connection pooling
7. Implement caching strategy (Redis)

---

## Common Pitfalls & Best Practices

### ❌ DON'T
- Don't use 'both' for new outlets (deprecated)
- Don't create items without specifying platform
- Don't assume SKU uniqueness across platforms
- Don't delete items without checking platform
- Don't skip CSV validation
- Don't hardcode platform values in templates
- **Don't add DecimalFields to existing tables without proper NULL handling in migrations**

### ✅ DO
- Always specify platform when creating items/outlets
- Use combination_key (item_code|description|sku) for item identification
- Validate platform parameter in all API endpoints
- Test CSV uploads with small files first
- Use Django messages for user feedback
- Log all critical operations
- Handle encoding issues in CSV uploads
- Use transactions for multi-step operations
- **When adding DecimalFields to existing tables, explicitly set `null=True, blank=True` and ensure migrations set default to NULL**
- **Always check `is not None` before converting Decimal/float values in API responses**

---

## Critical Lessons Learned

### Database Migration: DecimalField Corruption Issue (Dec 2024)

**Problem**: After adding new DecimalField columns (`converted_promo`, `promo_price`, `original_selling_price`) to the `ItemOutlet` model via migrations, the production database had corrupted/invalid values in these fields. This caused `TypeError: argument must be int or float` when Django's SQLite backend tried to convert the values to Python Decimal objects.

**Root Cause**:
- SQLite stored invalid data in DecimalField columns during migration
- Django's `create_decimal(value)` converter crashed when encountering non-numeric values
- Error occurred at the database layer (before Python code execution), making it hard to debug
- The error appeared in: `django/db/backends/sqlite3/operations.py:342`

**Symptoms**:
- API endpoints returned: `"Outlet availability error: argument must be int or float"`
- Error occurred when iterating over `ItemOutlet.objects.all()`
- Fixing Python code (NULL checks) didn't help because error was in database layer
- Local environment worked fine (clean data), production failed (corrupted data)

**Solution**:
```python
# Use raw SQL to bypass Django ORM and clean corrupted data
from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    UPDATE integration_itemoutlet 
    SET converted_promo = NULL, 
        promo_price = NULL, 
        original_selling_price = NULL
""")
connection.commit()
```

**Prevention**:
1. **Migration Design**:
   ```python
   # ✅ CORRECT - Always set null=True for new DecimalFields on existing tables
   class Migration(migrations.Migration):
       operations = [
           migrations.AddField(
               model_name='itemoutlet',
               name='converted_promo',
               field=models.DecimalField(
                   max_digits=10, 
                   decimal_places=2, 
                   null=True,  # ← CRITICAL
                   blank=True,
                   default=None  # ← Explicit NULL default
               ),
           ),
       ]
   ```

2. **Code Safety**:
   ```python
   # ✅ CORRECT - Always check is not None before float() conversion
   'mrp': float(item.mrp) if item.mrp is not None else 0.00
   'talabat_margin': float(item.effective_talabat_margin) if item.platform == 'talabat' and item.effective_talabat_margin is not None else None
   
   # ❌ WRONG - Will crash if value is None
   'mrp': float(item.mrp)
   'talabat_margin': float(item.effective_talabat_margin) if platform == 'talabat' else None
   ```

3. **Testing**:
   - Always test migrations on a copy of production database
   - Check for NULL/invalid values after migration
   - Test API endpoints after deploying migrations

**Key Takeaway**: When adding DecimalFields to tables with existing data, the migration must explicitly set values to NULL. Never rely on implicit defaults or assume Django will handle it correctly, especially with SQLite.

---

## Quick Reference Commands

```bash
# Start development server
python manage.py runserver

# Create migrations
python manage.py makemigrations integration

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# Check for errors
python manage.py check

# Collect static files
python manage.py collectstatic --noinput

# Flush database (careful!)
python manage.py flush
```

---

## Contact & Support

**Project Type**: Internal Business Tool  
**Stack**: Django 5.2.5 + Vanilla JS  
**Database**: SQLite (dev), PostgreSQL (production)  
**Deployment**: Not yet deployed  

---

**Last Updated**: December 10, 2024  
**Version**: 1.0.0  
**Status**: Active Development
