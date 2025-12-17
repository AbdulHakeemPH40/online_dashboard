# Pasons E-commerce API Push Integration Plan

## Overview

Push `selling_price` and `stock_status` data from Online Dashboard to Pasons E-commerce App via API.
Each branch (outlet) has a unique store_id and will push to its own API endpoint.

**Platform:** Pasons only (Talabat implementation later)

---

## Current State

- Export Feed generates CSV: `sku`, `selling_price`, `stock_status`
- Manual process: Download CSV → Upload to e-commerce
- **Goal:** Auto-push data via API (branch-wise)

---

## Data Format

**JSON Array (expected):**
```json
[
  {"sku": "9340957005965", "selling_price": 13.99, "stock_status": 1},
  {"sku": "9340957005966", "selling_price": 8.50, "stock_status": 0}
]
```

**Our Fields (Online Dashboard):**
| Our Field | Type | Description |
|-----------|------|-------------|
| `sku` | string | Product SKU (unique identifier) |
| `selling_price` | float | Outlet selling price |
| `stock_status` | int | 0 = Out of Stock, 1 = In Stock |
| `enabled` | int | Same as stock_status (for internal use) |

---

## Field Mapping (TBD - From Pasons E-commerce)

**⚠️ IMPORTANT:** Pasons E-commerce API may use different field names. We need to map our fields to their expected format.

| Our Field (Dashboard) | Pasons API Field | Notes |
|-----------------------|------------------|-------|
| `sku` | ❓ `sku` / `product_id` / `item_code` / `barcode` | TBD |
| `selling_price` | ❓ `price` / `selling_price` / `unit_price` / `amount` | TBD |
| `stock_status` | ❓ `stock_status` / `availability` / `in_stock` / `is_available` | TBD |
| `store_id` | ❓ `branch_id` / `outlet_id` / `store_code` | TBD - In URL or body? |

**Example - If Pasons uses different names:**
```json
// Our format:
{"sku": "9340957005965", "selling_price": 13.99, "stock_status": 1}

// Pasons format (example - TBD):
{"product_id": "9340957005965", "price": 13.99, "is_available": true}
```

**Configuration Required:**
```python
# Will be configurable per platform
FIELD_MAPPING = {
    'pasons': {
        'sku': 'product_id',        # Our 'sku' → Their 'product_id'
        'selling_price': 'price',   # Our 'selling_price' → Their 'price'
        'stock_status': 'is_available',  # Our 'stock_status' → Their 'is_available'
    }
}
```

**Questions for Pasons:**
1. What field name do you use for SKU/product identifier?
2. What field name do you use for price?
3. What field name do you use for stock availability?
4. Is stock_status a number (0/1) or boolean (true/false)?
5. How do you identify the branch - in URL path or request body?

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Online Dashboard                              │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ Shop        │───▶│ Push Service │───▶│ Pasons E-commerce │  │
│  │ Integration │    │ (API Client) │    │ API (per branch)  │  │
│  └─────────────┘    └──────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Database Changes

**1.1 Update `Outlet` Model**
```python
# Add to integration/models.py - Outlet model
api_endpoint = models.URLField(blank=True, null=True, help_text="E-commerce API URL")
api_key = models.CharField(max_length=255, blank=True, null=True, help_text="API Key/Token")
api_secret = models.CharField(max_length=255, blank=True, null=True, help_text="API Secret (if needed)")
push_enabled = models.BooleanField(default=False, help_text="Enable API push for this outlet")
```

**1.2 Create `PushHistory` Model**
```python
# New model to track push attempts
class PushHistory(models.Model):
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20)  # 'pasons' or 'talabat'
    push_type = models.CharField(max_length=20)  # 'full' or 'partial'
    push_timestamp = models.DateTimeField(auto_now_add=True)
    item_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20)  # 'success', 'failed', 'partial'
    response_code = models.IntegerField(null=True)
    response_message = models.TextField(blank=True, null=True)
    error_details = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
```

**1.3 Migration**
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Phase 2: Push Service

**2.1 Create `push_service.py`**

Location: `integration/push_service.py`

```python
class PushService:
    """
    API client for pushing data to Pasons E-commerce.
    
    Features:
    - Configurable endpoint per outlet
    - Retry logic with exponential backoff
    - Batch pushing (chunk large datasets)
    - Error handling & logging
    """
    
    def __init__(self, outlet, platform):
        self.outlet = outlet
        self.platform = platform
        self.endpoint = outlet.api_endpoint
        self.api_key = outlet.api_key
    
    def push(self, data, push_type='partial'):
        """
        Push data to e-commerce API.
        
        Args:
            data: List of dicts [{sku, selling_price, stock_status}, ...]
            push_type: 'full' or 'partial'
        
        Returns:
            (success: bool, response: dict)
        """
        pass
    
    def test_connection(self):
        """Test API connectivity"""
        pass
```

**2.2 Key Features:**
- Configurable timeout (default: 30 seconds)
- Retry on failure (3 attempts with exponential backoff)
- Chunk large datasets (500 items per request)
- Log all attempts to `PushHistory`

---

### Phase 3: Admin UI

**3.1 Update Shop Integration Page**

Add new tab: **"API Settings"**

**Form Fields:**
| Field | Type | Description |
|-------|------|-------------|
| Outlet | Dropdown | Select outlet to configure |
| API Endpoint | URL Input | E-commerce API URL |
| API Key | Password Input | Authentication key |
| Push Enabled | Checkbox | Enable/disable push |

**Buttons:**
- **Test Connection** - Verify API connectivity
- **Save Settings** - Save configuration
- **Push Now** - Manual push trigger

**3.2 Push History Table**

Show last 10 pushes with:
- Timestamp
- Outlet name
- Item count
- Status (success/failed)
- Response message

---

### Phase 4: API Endpoints

**4.1 New Views**

```python
# integration/views.py

def save_outlet_api_settings(request):
    """Save API configuration for outlet"""
    pass

def test_outlet_api_connection(request):
    """Test API connectivity"""
    pass

def push_to_ecommerce_api(request):
    """Manual push trigger"""
    pass

def get_push_history_api(request):
    """Get push history for outlet"""
    pass
```

**4.2 New URLs**

```python
# integration/urls.py
path('api/outlet-api-settings/', save_outlet_api_settings, name='save_outlet_api_settings'),
path('api/test-api-connection/', test_outlet_api_connection, name='test_api_connection'),
path('api/push-to-ecommerce/', push_to_ecommerce_api, name='push_to_ecommerce'),
path('api/push-history/', get_push_history_api, name='push_history'),
```

---

### Phase 5: Automation (Future)

**5.1 Scheduled Push**
- Use Celery for background tasks
- Schedule: Every 30 minutes (configurable)
- Only push if changes detected (partial export logic)

**5.2 Auto-Push After Update**
- Trigger push after `product_update` completes
- Optional: User can enable/disable per outlet

---

## API Requirements (TBD - From Pasons)

| Item | Details | Status |
|------|---------|--------|
| API Endpoint URL | `https://api.pasons.ae/v1/inventory` (example) | ❓ Pending |
| Authentication | API Key / Bearer Token / Basic Auth | ❓ Pending |
| Request Method | POST / PUT | ❓ Pending |
| Request Headers | Content-Type, Authorization | ❓ Pending |
| Request Body | JSON Array | ✅ Confirmed |
| Response Format | Success/Error codes | ❓ Pending |
| Rate Limits | Requests per minute | ❓ Pending |
| Max Items/Request | Batch size limit | ❓ Pending |
| Branch Identification | store_id in URL or body | ❓ Pending |

---

## Testing Plan

### Local Testing

1. **Mock API Server**
   - Create simple Flask/FastAPI endpoint
   - Accept JSON array, return success/error
   - Test with local IP: `http://192.168.x.x:5000/api/inventory`

2. **Test Cases**
   - Push single item
   - Push batch (100+ items)
   - Handle API timeout
   - Handle invalid response
   - Handle network error

### Production Testing

1. Configure real Pasons API endpoint
2. Test with single outlet first
3. Monitor `PushHistory` for errors
4. Gradually enable for all outlets

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `integration/models.py` | Modify | Add fields to Outlet, create PushHistory |
| `integration/push_service.py` | Create | API client service |
| `integration/views.py` | Modify | Add push-related views |
| `integration/urls.py` | Modify | Add push-related URLs |
| `templates/shop_integration.html` | Modify | Add API Settings tab |

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Database | 1 day | None |
| Phase 2: Push Service | 2 days | Phase 1 |
| Phase 3: Admin UI | 2 days | Phase 2 |
| Phase 4: API Endpoints | 1 day | Phase 2, 3 |
| Phase 5: Automation | 2 days | Phase 4 + Celery setup |

**Total: ~8 days** (excluding waiting for Pasons API details)

---

## Next Steps

1. ⏳ Wait for Pasons E-commerce API documentation
2. 🔧 Implement Phase 1-4 with placeholder endpoint
3. 🧪 Test locally with mock API
4. 🚀 Connect to real Pasons API when ready

---

*Document created: Dec 17, 2025*
*Status: Planning - Implementation on hold*
