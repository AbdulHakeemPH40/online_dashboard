from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator
from django.utils import timezone
import random
import string

# Using Django's built-in User model for authentication
# User model provides: username, password, email, first_name, last_name, is_active, is_staff, is_superuser


class Outlet(models.Model):
    """Store/Outlet model with unique 6-digit store IDs and platform support
    
    IMPORTANT: Each outlet belongs to ONE platform only.
    Same physical store on both platforms = TWO separate outlet records.
    Example: "Karama" on Pasons (100001) and "Karama" on Talabat (700001) are different records.
    """
    PLATFORM_CHOICES = [
        ('pasons', 'Pasons Ecommerce'),
        ('talabat', 'Talabat Platform'),
        # NOTE: 'both' is REMOVED - strict platform isolation enforced
    ]
    
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    store_id = models.CharField(max_length=6, unique=True, editable=False)
    platforms = models.CharField(
        max_length=20, 
        choices=PLATFORM_CHOICES, 
        default='pasons',
        help_text="Platform where this outlet is available"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.store_id:
            self.store_id = self.generate_unique_store_id()
        super().save(*args, **kwargs)
    
    def generate_unique_store_id(self):
        """Generate unique platform-specific 6-digit store ID"""
        # Determine starting range based on platform
        if self.platforms == 'pasons':
            start_range = 100001
            end_range = 699999
        elif self.platforms == 'talabat':
            start_range = 700001
            end_range = 999999
        else:
            # Fallback to Pasons if invalid platform
            start_range = 100001
            end_range = 699999
        
        # Get the last outlet with store_id in the platform range
        last_outlet = Outlet.objects.filter(
            platforms=self.platforms,
            store_id__gte=str(start_range),
            store_id__lte=str(end_range)
        ).order_by('-store_id').first()
        
        if last_outlet and last_outlet.store_id:
            try:
                last_id = int(last_outlet.store_id)
                next_id = last_id + 1
            except ValueError:
                next_id = start_range
        else:
            next_id = start_range
        
        return str(next_id).zfill(6)
    
    def __str__(self):
        return f"{self.name} ({self.store_id})"
    
    class Meta:
        ordering = ['name']
        unique_together = ('name', 'platforms')  # Prevent duplicate names on same platform


# Allowed wrap codes for items
WRAP_CHOICES = [
    ('9900', '9900'),
    ('10000', '10000'),
]

class Item(models.Model):
    """Product/Item model with central locking support
    
    PLATFORM ISOLATION: Each platform has its own items.
    Same item_code + SKU on different platforms = TWO separate Item records.
    
    Central Locking System (CLS):
    - price_locked: When True, selling_price cannot be modified at outlet level
    - status_locked: When True, is_active status cannot be modified at outlet level
    """
    PLATFORM_CHOICES = [
        ('pasons', 'Pasons Ecommerce'),
        ('talabat', 'Talabat Platform'),
    ]
    
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default='pasons',
        help_text="Platform this item belongs to"
    )
    item_code = models.CharField(max_length=50, help_text="Item identifier (can have multiple variants with different SKUs)")
    description = models.TextField(help_text="Item name/description")
    pack_description = models.TextField(blank=True, null=True, help_text="Pack description/details")
    units = models.CharField(max_length=20, help_text="Unit of measurement (e.g., pcs, kg, ltr)")
    sku = models.CharField(max_length=100, help_text="Stock Keeping Unit")
    barcode = models.CharField(max_length=50, blank=True, null=True, help_text="Product barcode")
    # Legacy fields - NOT USED for outlet-based pricing (use ItemOutlet fields instead)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="[DEPRECATED] Use ItemOutlet.outlet_selling_price instead")
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)], help_text="[DEPRECATED] Use ItemOutlet.outlet_stock instead. Cannot be negative.")
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)], help_text="[DEPRECATED] Use ItemOutlet fields instead. Cannot be negative.")
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)], help_text="[DEPRECATED] Use ItemOutlet.outlet_mrp instead. Cannot be negative.")
    wrap = models.CharField(
        max_length=5,
        choices=WRAP_CHOICES,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^(9900|10000)$', message='Wrap must be 9900 or 10000.')],
        help_text="Wrap code (allowed: 9900 or 10000)"
    )
    # Weight and quantity conversion fields
    weight_division_factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Price division factor for weight-based items (e.g., 2 means price/2). Used to calculate selling price from ERP base price."
    )
    converted_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Converted cost = cost / weight_division_factor. Auto-calculated when weight_division_factor is set."
    )
    outer_case_quantity = models.IntegerField(
        blank=True,
        null=True,
        help_text="Outer case pack quantity (e.g., 9 pcs per case). Used for stock validation: stock_qty / outer_case_qty must be >= 1"
    )
    minimum_qty = models.IntegerField(
        blank=True,
        null=True,
        help_text="Minimum order/stock quantity threshold (e.g., 3 = minimum 3 units required for orders)"
    )
    
    # Talabat-specific margin (optional override)
    talabat_margin = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Custom Talabat margin percentage (optional). If not set, defaults: 9900xxx=17%, 100xxx=15%"
    )
    
    # Central Locking System (CLS)
    price_locked = models.BooleanField(default=False, help_text="Lock price updates at item level")
    status_locked = models.BooleanField(default=False, help_text="Lock status changes at item level")
    outlets = models.ManyToManyField(Outlet, through='ItemOutlet', related_name='items', help_text="Outlets where this item is available")

    is_active = models.BooleanField(default=True, help_text="Active status of the item")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.item_code} - {self.description}"
    
    @property
    def effective_talabat_margin(self):
        """
        Get effective Talabat margin with smart defaults:
        - Priority 1: Use custom margin if set (talabat_margin field)
        - Priority 2: Auto-detect based on item code:
          * 9900xxx (Wrap items) → 17%
          * 100xxx (Regular items) → 15%
          * Others → 15% (default)
        
        Returns:
            Decimal: Margin percentage (e.g., Decimal('17.00'))
        """
        from decimal import Decimal
        
        # Priority 1: Use custom margin if explicitly set
        if self.talabat_margin is not None:
            return self.talabat_margin
        
        # Priority 2: Smart defaults based on item code
        item_code_str = str(self.item_code).strip()
        
        if item_code_str.startswith('9900'):
            # Wrap items → 17%
            return Decimal('17.00')
        else:
            # Regular items (100xxx and others) → 15%
            return Decimal('15.00')
    

    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost > 0:
            return ((self.selling_price - self.cost) / self.cost) * 100
        return 0
    
    def get_cases_count(self):
        """Calculate number of cases based on stock and outer_case_quantity
        
        Example: stock=9, outer_case_quantity=6 → 9/6 = 1.5 cases
        
        Returns:
            float or None: Number of cases (can be decimal), or None if outer_case_quantity not set
        """
        if not self.outer_case_quantity or self.outer_case_quantity == 0:
            return None
        return self.stock / self.outer_case_quantity
    
    def validate_stock(self):
        """Validate stock configuration against minimum_qty and outer_case_quantity
        
        Returns:
            dict: {
                'is_valid': bool,
                'issues': list of error messages
            }
        """
        issues = []
        
        # Check 1: Stock >= minimum_qty
        if self.minimum_qty and self.minimum_qty > 0:
            if self.stock < self.minimum_qty:
                issues.append(
                    f"Stock {self.stock} is below minimum {self.minimum_qty} units required"
                )
        
        # Check 2: Stock divisibility by outer_case_quantity
        if self.outer_case_quantity and self.outer_case_quantity > 0:
            if self.stock % self.outer_case_quantity != 0:
                cases = self.get_cases_count()
                issues.append(
                    f"Stock {self.stock} not divisible by case quantity {self.outer_case_quantity}. "
                    f"Current: {cases} cases (invalid). "
                    f"Use valid quantities: {self.outer_case_quantity}, {self.outer_case_quantity * 2}, "
                    f"{self.outer_case_quantity * 3}, etc."
                )
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues
        }
    
    class Meta:
        ordering = ['item_code']
        indexes = [
            models.Index(fields=['platform', 'is_active']),  # Dashboard query optimization
            models.Index(fields=['platform', 'item_code', 'units']),  # Product update CSV lookup optimization
        ]
        verbose_name = "Item"
        verbose_name_plural = "Items"


class ItemOutlet(models.Model):
    """Intermediate model for Item-Outlet relationship with outlet-specific data
    
    OPTIMIZATION: data_hash field stores MD5 hash of (mrp|cost|stock) for O(1) change detection.
    When updating via CSV, compare incoming hash vs stored hash to skip unchanged rows.
    This provides 15-20x performance improvement for large datasets (14,000+ rows).
    """
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='item_outlets')
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE, related_name='outlet_items')
    outlet_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)], help_text="Stock quantity for this outlet. Cannot be negative.")
    outlet_cost = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Outlet-specific cost. Cannot be negative.")
    outlet_mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Outlet-specific MRP (optional). Cannot be negative.")
    outlet_selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Outlet-specific selling price (optional). Cannot be negative.")
    is_active_in_outlet = models.BooleanField(default=True, help_text="Whether item is active in this outlet")
    # Branch Locking System (BLS)
    price_locked = models.BooleanField(default=False, help_text="Lock price updates for this outlet")
    status_locked = models.BooleanField(default=False, help_text="Lock status changes for this outlet")
    # Hash-based change detection for CSV bulk updates (Industry-standard CDC approach)
    data_hash = models.CharField(
        max_length=32, 
        blank=True, 
        null=True, 
        db_index=True,
        help_text="MD5 hash of (mrp|cost|stock) for O(1) change detection. Auto-updated on save."
    )
    # Delta export tracking: Store last exported values for comparison
    export_selling_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Last exported selling_price. Used for delta export detection."
    )
    export_stock_status = models.IntegerField(
        null=True,
        blank=True,
        choices=[(0, 'Disabled'), (1, 'Enabled')],
        help_text="Last exported stock_status (0=disabled, 1=enabled). Used for delta export detection."
    )
    # ERP export tracking
    erp_export_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Last exported ERP price (converted). Used for ERP delta export detection."
    )
    # Promotion pricing fields
    promo_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Input promotional price (base price before conversion)"
    )
    converted_promo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated promotional price after platform/wrap conversion"
    )
    original_selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Backup of original selling price before promotion (for restoration)"
    )
    promo_start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Promotion start date and time"
    )
    promo_end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Promotion end date and time"
    )
    is_on_promotion = models.BooleanField(
        default=False,
        help_text="Whether item is currently on promotion"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('item', 'outlet')
        indexes = [
            models.Index(fields=['outlet', 'item']),
            models.Index(fields=['item']),  # For dashboard queries by item
        ]
        ordering = ['item__item_code', 'outlet__name']
        verbose_name = "Item-Outlet Association"
        verbose_name_plural = "Item-Outlet Associations"
    
    def __str__(self):
        return f"{self.item.item_code} - {self.outlet.name}"

    # --- Effective lock state helpers ---
    @property
    def effective_price_locked(self):
        return bool(getattr(self, 'price_locked', False) or getattr(self.item, 'price_locked', False))

    @property
    def effective_status_locked(self):
        return bool(getattr(self, 'status_locked', False) or getattr(self.item, 'status_locked', False))

    @property
    def can_edit_price(self):
        return not self.effective_price_locked

    @property
    def is_effectively_active(self):
        # Check BOTH BLS and CLS locks
        # Item is active only if: outlet_flag is True AND no BLS lock AND no CLS lock
        return bool(
            self.is_active_in_outlet 
            and not self.status_locked                    # BLS check
            and not getattr(self.item, 'status_locked', False)  # CLS check
        )
    
    def get_cases_count(self):
        """Calculate number of cases for this outlet's stock
        
        Returns:
            float or None: outlet_stock / item.outer_case_quantity (can be decimal)
        """
        if not self.item.outer_case_quantity or self.item.outer_case_quantity == 0:
            return None
        return self.outlet_stock / self.item.outer_case_quantity
    
    def validate_stock(self):
        """Validate outlet stock against item's constraints
        
        Returns:
            dict: {
                'is_valid': bool,
                'issues': list of error messages
            }
        """
        issues = []
        
        # Check 1: outlet_stock >= item.minimum_qty
        if self.item.minimum_qty and self.item.minimum_qty > 0:
            if self.outlet_stock < self.item.minimum_qty:
                issues.append(
                    f"Outlet stock {self.outlet_stock} is below minimum {self.item.minimum_qty} required"
                )
        
        # Check 2: outlet_stock divisible by item.outer_case_quantity
        if self.item.outer_case_quantity and self.item.outer_case_quantity > 0:
            if self.outlet_stock % self.item.outer_case_quantity != 0:
                cases = self.get_cases_count()
                issues.append(
                    f"Outlet stock {self.outlet_stock} not divisible by case qty {self.item.outer_case_quantity}. "
                    f"Current: {cases} cases (invalid). "
                    f"Valid quantities: {self.item.outer_case_quantity}, "
                    f"{self.item.outer_case_quantity * 2}, {self.item.outer_case_quantity * 3}, etc."
                )
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues
        }


# --- Item-level helpers for cascading CLS to BLS ---
def _cascade_cls_status_to_outlets(item, new_val):
    """
    Cascade CLS status lock to all outlets.
    
    LOGIC:
    - If new_val=True (LOCKED): Force disable all outlets (is_active_in_outlet=False)
    - If new_val=False (UNLOCKED): Enable outlets based on stock rules
    """
    from .views import calculate_outlet_enabled_status
    
    # Only cascade to outlets on the SAME platform as the item (STRICT ISOLATION)
    item_outlets = ItemOutlet.objects.filter(
        item=item,
        outlet__platforms=item.platform  # Strict platform isolation
    )
    
    if bool(new_val):
        # LOCKED: Force disable all outlets
        item_outlets.update(
            status_locked=True,
            is_active_in_outlet=False
        )
    else:
        # UNLOCKED: Enable based on stock rules for each outlet
        for io in item_outlets:
            calculated_enabled = calculate_outlet_enabled_status(item, io.outlet_stock)
            io.status_locked = False
            io.is_active_in_outlet = calculated_enabled
            io.save(update_fields=['status_locked', 'is_active_in_outlet'])


def _cascade_cls_price_to_outlets(item, new_val):
    # Only cascade to outlets on the SAME platform as the item (STRICT ISOLATION)
    ItemOutlet.objects.filter(
        item=item,
        outlet__platforms=item.platform  # Strict platform isolation
    ).update(price_locked=bool(new_val))


# Attach helper methods to Item without circular imports
def _item_cascade_status(self, new_val):
    _cascade_cls_status_to_outlets(self, new_val)


def _item_cascade_price(self, new_val):
    _cascade_cls_price_to_outlets(self, new_val)


Item.cascade_cls_status_to_outlets = _item_cascade_status
Item.cascade_cls_price_to_outlets = _item_cascade_price


class UploadHistory(models.Model):
    """Track CSV upload history for assortment display"""
    
    UPDATE_TYPE_CHOICES = [
        ('product', 'Product Update'),
        ('stock', 'Stock Update'),
        ('price_cost', 'Price Update (Cost)'),
        ('price_mrp', 'Price Update (MRP)'),
        ('price_both', 'Price Update (Both)'),
        ('rules_price', 'Rules Update (Price/Margin)'),
        ('rules_stock', 'Rules Update (Stock)'),
        ('bulk_creation', 'Bulk Item Creation'),
        ('promotion_update', 'Promotion Update'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]
    
    PLATFORM_CHOICES = [
        ('pasons', 'Pasons'),
        ('talabat', 'Talabat'),
        ('global', 'Global'),
    ]
    
    file_name = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='pasons')
    outlet = models.ForeignKey(Outlet, on_delete=models.SET_NULL, null=True, blank=True)
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPE_CHOICES)
    records_total = models.IntegerField(default=0)
    records_success = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    records_skipped = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True, null=True)
    response_data = models.JSONField(blank=True, null=True, default=dict, help_text='JSON data including created_skus, updated_skus for report generation')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Upload History'
        verbose_name_plural = 'Upload Histories'
    
    def __str__(self):
        return f"{self.file_name} - {self.get_update_type_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def outlet_name(self):
        return self.outlet.name if self.outlet else 'Global'


class ExportHistory(models.Model):
    """
    Track export history for partial export functionality.
    
    PURPOSE: Enables delta export - exporting only items changed since last successful export.
    
    DATA INTEGRITY GUARANTEES:
    - Each (outlet, platform) has exactly ONE latest successful export record (via unique_together)
    - Timestamps are captured at export completion (AFTER data validation)
    - Item count allows verification: if exported count < query count, something failed
    - Transaction safety: Created within DB transaction, not until export succeeds
    
    PARTIAL EXPORT LOGIC:
    1. Find latest ExportHistory for (outlet, platform)
    2. If not found: First export → do FULL export, create ExportHistory
    3. If found: Partial export → find ItemOutlets WHERE updated_at > last_export_at
    4. After successful export: Create new ExportHistory with current timestamp
    
    EDGE CASES HANDLED:
    - First export (no prior history): Treated as full export
    - Deleted items: Filtered out by is_active_in_outlet check
    - Concurrent updates: Using transaction for consistency
    - Export timeout: Transaction rollback prevents incomplete data logging
    """
    
    EXPORT_TYPE_CHOICES = [
        ('full', 'Full Export'),
        ('partial', 'Partial Export - Delta sync'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success - File generated'),
        ('failed', 'Failed - No file created'),
        ('validation_failed', 'Validation Failed - Data issues'),
    ]
    
    # Relationships
    outlet = models.ForeignKey(
        Outlet,
        on_delete=models.CASCADE,
        related_name='export_histories',
        help_text="Which outlet was exported"
    )
    platform = models.CharField(
        max_length=20,
        choices=[('pasons', 'Pasons'), ('talabat', 'Talabat')],
        help_text="Platform for this outlet"
    )
    
    # Export metadata
    export_type = models.CharField(
        max_length=20,
        choices=EXPORT_TYPE_CHOICES,
        help_text="Full export or partial delta export"
    )
    export_timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Exact time when export completed (= current DB time at export completion)"
    )
    
    # Export statistics
    item_count = models.IntegerField(
        default=0,
        help_text="Total items included in this export (for validation)"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Generated CSV filename"
    )
    
    # Validation & status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='success',
        help_text="Whether export succeeded or failed"
    )
    validation_errors = models.TextField(
        blank=True,
        null=True,
        help_text="JSON array of validation errors found during export"
    )
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this record was created")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who triggered export (optional)"
    )
    
    class Meta:
        # For each outlet+platform, we want latest successful export
        # This index optimizes the "find latest export" query
        indexes = [
            models.Index(fields=['outlet', 'platform', '-export_timestamp']),
            models.Index(fields=['outlet', 'status']),
        ]
        ordering = ['-export_timestamp']
        verbose_name = 'Export History'
        verbose_name_plural = 'Export Histories'
    
    def __str__(self):
        return f"{self.outlet.name} ({self.get_platform_display()}) - {self.get_export_type_display()} at {self.export_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def get_latest_successful_export(cls, outlet, platform):
        """
        Get the most recent SUCCESSFUL export for an outlet.
        
        Returns:
            ExportHistory or None: Latest successful export, or None if never exported
            
        IMPORTANT: Only returns SUCCESSFUL exports.
        Failed/validation_failed exports are skipped to prevent syncing bad data.
        """
        return cls.objects.filter(
            outlet=outlet,
            platform=platform,
            status='success'
        ).order_by('-export_timestamp').first()
    
    def is_valid(self):
        """Check if export completed successfully (no validation errors)"""
        return self.status == 'success' and not self.validation_errors


class ERPExportHistory(models.Model):
    """
    Track ERP export history for Talabat platform.
    Similar to ExportHistory but for ERP-specific exports with different CSV format.
    
    CSV FORMAT: Party, Item Code, Location, Unit, Price
    - Party: Fixed value "DT0072"
    - Item Code: item.item_code
    - Location: Placeholder (empty)
    - Unit: item.units
    - Price: Converted selling price (wrap=9900: price*WDF, wrap=10000: same price)
    """
    
    EXPORT_TYPE_CHOICES = [
        ('full', 'Full Export'),
        ('partial', 'Partial Export - Delta sync'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success - File generated'),
        ('failed', 'Failed - No file created'),
        ('validation_failed', 'Validation Failed - Data issues'),
    ]
    
    # Relationships
    outlet = models.ForeignKey(
        Outlet,
        on_delete=models.CASCADE,
        related_name='erp_export_histories',
        help_text="Which outlet was exported"
    )
    
    # Export metadata
    export_type = models.CharField(
        max_length=20,
        choices=EXPORT_TYPE_CHOICES,
        help_text="Full export or partial delta export"
    )
    export_timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Exact time when export completed"
    )
    
    # Export statistics
    item_count = models.IntegerField(
        default=0,
        help_text="Total items included in this export"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Generated CSV filename"
    )
    
    # Validation & status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='success',
        help_text="Whether export succeeded or failed"
    )
    validation_errors = models.TextField(
        blank=True,
        null=True,
        help_text="JSON array of validation errors found during export"
    )
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['outlet', '-export_timestamp']),
            models.Index(fields=['outlet', 'status']),
        ]
        ordering = ['-export_timestamp']
        verbose_name = 'ERP Export History'
        verbose_name_plural = 'ERP Export Histories'
    
    def __str__(self):
        return f"ERP: {self.outlet.name} - {self.get_export_type_display()} at {self.export_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def get_latest_successful_export(cls, outlet):
        """Get the most recent SUCCESSFUL ERP export for an outlet."""
        return cls.objects.filter(
            outlet=outlet,
            status='success'
        ).order_by('-export_timestamp').first()
