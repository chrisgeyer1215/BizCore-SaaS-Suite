"""
Complete Hybrid Inventory Management System
Combines best practices with maximum functionality for enterprise use
"""

from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from django.utils import timezone
import uuid
import json

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


# ============================================================================
# CORE SETTINGS & CONFIGURATION
# ============================================================================

class InventorySettings(TenantBaseModel):
    """Comprehensive tenant-specific inventory configuration"""
    
    VALUATION_METHODS = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('AVERAGE', 'Weighted Average'),
        ('SPECIFIC', 'Specific Identification'),
        ('STANDARD', 'Standard Cost'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('JPY', 'Japanese Yen'),
        ('INR', 'Indian Rupee'),
        ('CAD', 'Canadian Dollar'),
        ('AUD', 'Australian Dollar'),
    ]
    
    # Core Settings
    valuation_method = models.CharField(max_length=20, choices=VALUATION_METHODS, default='FIFO')
    default_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    enable_multi_currency = models.BooleanField(default=False)
    decimal_precision = models.IntegerField(default=2, validators=[MinValueValidator(0), MaxValueValidator(6)])
    
    # Stock Management
    low_stock_alert_enabled = models.BooleanField(default=True)
    low_stock_threshold_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    auto_reorder_enabled = models.BooleanField(default=False)
    allow_negative_stock = models.BooleanField(default=False)
    enable_reserved_stock = models.BooleanField(default=True)
    enable_allocated_stock = models.BooleanField(default=True)
    
    # Advanced Tracking
    enable_batch_tracking = models.BooleanField(default=True)
    enable_serial_tracking = models.BooleanField(default=False)
    enable_lot_tracking = models.BooleanField(default=True)
    enable_expiry_tracking = models.BooleanField(default=True)
    enable_landed_cost = models.BooleanField(default=False)
    
    # Barcode & Identification
    enable_barcode = models.BooleanField(default=True)
    enable_qr_code = models.BooleanField(default=True)
    auto_generate_barcodes = models.BooleanField(default=True)
    barcode_prefix = models.CharField(max_length=10, default='PRD', blank=True)
    
    # Drop Shipping & Third Party
    enable_dropshipping = models.BooleanField(default=False)
    enable_consignment = models.BooleanField(default=False)
    enable_third_party_logistics = models.BooleanField(default=False)
    
    # Manufacturing & Assembly
    enable_manufacturing = models.BooleanField(default=False)
    enable_kitting = models.BooleanField(default=False)
    enable_bundling = models.BooleanField(default=False)
    
    # Quality Control
    enable_quality_control = models.BooleanField(default=False)
    enable_inspection = models.BooleanField(default=False)
    enable_quarantine = models.BooleanField(default=False)
    
    # Pricing & Costing
    enable_dynamic_pricing = models.BooleanField(default=False)
    enable_tier_pricing = models.BooleanField(default=False)
    enable_promotional_pricing = models.BooleanField(default=False)
    cost_calculation_method = models.CharField(
        max_length=20,
        choices=[
            ('STANDARD', 'Standard Cost'),
            ('ACTUAL', 'Actual Cost'),
            ('AVERAGE', 'Moving Average'),
        ],
        default='AVERAGE'
    )
    
    # Reporting & Analytics
    enable_abc_analysis = models.BooleanField(default=True)
    enable_velocity_analysis = models.BooleanField(default=True)
    enable_seasonality_tracking = models.BooleanField(default=False)
    
    # Integration Settings
    erp_integration_enabled = models.BooleanField(default=False)
    accounting_integration_enabled = models.BooleanField(default=False)
    ecommerce_integration_enabled = models.BooleanField(default=False)
    
    # Audit & Compliance
    require_approval_for_adjustments = models.BooleanField(default=True)
    enable_audit_trail = models.BooleanField(default=True)
    retain_data_years = models.IntegerField(default=7)
    
    class Meta:
        db_table = 'inventory_settings'
        verbose_name = 'Inventory Settings'
        verbose_name_plural = 'Inventory Settings'


# ============================================================================
# UNITS OF MEASURE
# ============================================================================

class UnitOfMeasure(TenantBaseModel):
    """Comprehensive unit of measure system"""
    
    UNIT_TYPES = [
        ('COUNT', 'Count/Each'),
        ('WEIGHT', 'Weight'),
        ('VOLUME', 'Volume'),
        ('LENGTH', 'Length'),
        ('AREA', 'Area'),
        ('TIME', 'Time'),
        ('TEMPERATURE', 'Temperature'),
        ('ENERGY', 'Energy'),
        ('CURRENCY', 'Currency'),
    ]
    
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    symbol = models.CharField(max_length=5, blank=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    
    # Conversion system
    base_unit = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='derived_units'
    )
    conversion_factor = models.DecimalField(
        max_digits=15, decimal_places=6, default=1.000000,
        help_text="Factor to convert to base unit"
    )
    conversion_offset = models.DecimalField(
        max_digits=10, decimal_places=6, default=0,
        help_text="Offset for temperature conversions"
    )
    
    # Properties
    is_active = models.BooleanField(default=True)
    is_base_unit = models.BooleanField(default=False)
    allow_fractions = models.BooleanField(default=True)
    decimal_places = models.IntegerField(default=3)
    
    # Additional info
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_units'
        ordering = ['unit_type', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'abbreviation'], name='unique_tenant_uom_abbrev'),
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_tenant_uom_name'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'unit_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
    
    def convert_to_base(self, value):
        """Convert value to base unit"""
        return (Decimal(str(value)) * self.conversion_factor) + self.conversion_offset
    
    def convert_from_base(self, value):
        """Convert from base unit to this unit"""
        return (Decimal(str(value)) - self.conversion_offset) / self.conversion_factor


# ============================================================================
# CATEGORIZATION SYSTEM
# ============================================================================

class Department(TenantBaseModel, SoftDeleteMixin):
    """Top-level product categorization with enhanced features"""
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    # Properties
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Accounting Integration
    revenue_account_code = models.CharField(max_length=20, blank=True)
    cost_account_code = models.CharField(max_length=20, blank=True)
    
    # Settings
    default_markup_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    
    # Manager
    manager = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )
    
    # Media
    image = models.ImageField(upload_to='departments/', blank=True, null=True)
    icon_class = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'inventory_departments'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_tenant_dept_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'parent']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)


class Category(TenantBaseModel, SoftDeleteMixin):
    """Enhanced category system"""
    
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    # Properties
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Tax & Accounting
    tax_category = models.CharField(max_length=50, blank=True)
    hsn_code = models.CharField(max_length=20, blank=True)  # Harmonized System Nomenclature
    
    # Attributes for this category
    required_attributes = models.JSONField(default=list, blank=True)
    optional_attributes = models.JSONField(default=list, blank=True)
    
    # SEO & Marketing
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.TextField(blank=True)
    
    # Media
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    
    class Meta:
        db_table = 'inventory_categories'
        ordering = ['department', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'department', 'code'], name='unique_tenant_cat_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'department', 'is_active']),
            models.Index(fields=['tenant', 'parent']),
        ]
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return f"{self.department.code}/{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        path.insert(0, self.department.name)
        return " > ".join(path)


class SubCategory(TenantBaseModel, SoftDeleteMixin):
    """Detailed subcategory system"""
    
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Properties
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Specifications template
    specification_template = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'inventory_subcategories'
        ordering = ['category', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'category', 'code'], name='unique_tenant_subcat_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'category', 'is_active']),
        ]
        verbose_name_plural = 'Sub Categories'
    
    def __str__(self):
        return f"{self.category.code}/{self.code} - {self.name}"
    
    @property
    def full_path(self):
        return f"{self.category.department.name} > {self.category.name} > {self.name}"


# ============================================================================
# BRAND & MANUFACTURER
# ============================================================================

class Brand(TenantBaseModel, SoftDeleteMixin):
    """Enhanced brand management"""
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Contact Information
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Business Details
    manufacturer = models.BooleanField(default=False)
    country_of_origin = models.CharField(max_length=100, blank=True)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Quality & Certifications
    certifications = models.JSONField(default=list, blank=True)
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_preferred = models.BooleanField(default=False)
    
    # Media
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    logo_url = models.URLField(blank=True)
    brand_colors = models.JSONField(default=dict, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_brands'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_tenant_brand_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        return self.name


# ============================================================================
# SUPPLIER & VENDOR MANAGEMENT
# ============================================================================

class Supplier(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive supplier management"""
    
    SUPPLIER_TYPES = [
        ('MANUFACTURER', 'Manufacturer'),
        ('WHOLESALER', 'Wholesaler'),
        ('DISTRIBUTOR', 'Distributor'),
        ('RETAILER', 'Retailer'),
        ('DROPSHIPPER', 'Drop Shipper'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('CONSIGNMENT', 'Consignment'),
    ]
    
    PAYMENT_TERMS = [
        ('NET_0', 'Net 0 (Cash)'),
        ('NET_7', 'Net 7'),
        ('NET_15', 'Net 15'),
        ('NET_30', 'Net 30'),
        ('NET_45', 'Net 45'),
        ('NET_60', 'Net 60'),
        ('NET_90', 'Net 90'),
        ('COD', 'Cash on Delivery'),
        ('PREPAID', 'Prepaid'),
        ('CREDIT_CARD', 'Credit Card'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    company_name = models.CharField(max_length=200, blank=True)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPES, default='WHOLESALER')
    
    # Legal Information
    tax_id = models.CharField(max_length=50, blank=True)
    vat_number = models.CharField(max_length=50, blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    
    # Contact Information
    contact_person = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # Billing Address (if different)
    billing_same_as_shipping = models.BooleanField(default=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    
    # Financial Terms
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS, default='NET_30')
    payment_terms_days = models.IntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_used = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Banking Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    # Performance Metrics
    lead_time_days = models.IntegerField(default=7)
    minimum_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_order_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Ratings & Reviews
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    service_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    overall_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Drop Shipping
    supports_dropshipping = models.BooleanField(default=False)
    dropship_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    dropship_handling_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Integration
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    edi_capability = models.BooleanField(default=False)
    
    # Status & Preferences
    is_active = models.BooleanField(default=True)
    is_preferred = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_minority_owned = models.BooleanField(default=False)
    is_woman_owned = models.BooleanField(default=False)
    
    # Documents & Certifications
    certifications = models.JSONField(default=list, blank=True)
    insurance_certificate = models.FileField(upload_to='supplier_docs/', blank=True, null=True)
    tax_certificate = models.FileField(upload_to='supplier_docs/', blank=True, null=True)
    
    # Additional Information
    return_policy = models.TextField(blank=True)
    warranty_terms = models.TextField(blank=True)
    special_terms = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_suppliers'
        ordering = ['-is_preferred', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_tenant_supplier_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'supplier_type']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def credit_available(self):
        """Available credit limit"""
        return self.credit_limit - self.credit_used
    
    @property
    def credit_utilization_percentage(self):
        """Credit utilization as percentage"""
        if self.credit_limit > 0:
            return (self.credit_used / self.credit_limit * 100).quantize(Decimal('0.01'))
        return Decimal('0')


class SupplierContact(TenantBaseModel):
    """Additional contacts for suppliers"""
    
    CONTACT_TYPES = [
        ('PRIMARY', 'Primary Contact'),
        ('SALES', 'Sales Representative'),
        ('SUPPORT', 'Customer Support'),
        ('TECHNICAL', 'Technical Support'),
        ('BILLING', 'Billing/Accounts'),
        ('SHIPPING', 'Shipping/Logistics'),
        ('EMERGENCY', 'Emergency Contact'),
    ]
    
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_supplier_contacts'
        ordering = ['supplier', '-is_primary', 'name']
    
    def __str__(self):
        return f"{self.supplier.name} - {self.name} ({self.contact_type})"


# ============================================================================
# WAREHOUSE & LOCATION MANAGEMENT
# ============================================================================

class Warehouse(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive warehouse management"""
    
    WAREHOUSE_TYPES = [
        ('PHYSICAL', 'Physical Warehouse'),
        ('VIRTUAL', 'Virtual/Drop-ship'),
        ('CONSIGNMENT', 'Consignment'),
        ('TRANSIT', 'In-Transit'),
        ('QUARANTINE', 'Quarantine'),
        ('RETURNED_GOODS', 'Returned Goods'),
        ('WORK_IN_PROGRESS', 'Work in Progress'),
    ]
    
    TEMPERATURE_ZONES = [
        ('AMBIENT', 'Ambient Temperature'),
        ('REFRIGERATED', 'Refrigerated (2-8°C)'),
        ('FROZEN', 'Frozen (-18°C)'),
        ('CONTROLLED', 'Temperature Controlled'),
        ('HAZMAT', 'Hazardous Materials'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='PHYSICAL')
    
    # Address & Location
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # GPS Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Contact Information
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_warehouses'
    )
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Operational Details
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_sellable = models.BooleanField(default=True)
    allow_negative_stock = models.BooleanField(default=False)
    
    # Capacity & Physical Properties
    total_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    storage_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='warehouse_areas'
    )
    max_capacity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_occupancy_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Temperature & Environment
    temperature_zone = models.CharField(max_length=20, choices=TEMPERATURE_ZONES, default='AMBIENT')
    min_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    humidity_controlled = models.BooleanField(default=False)
    
    # Security & Compliance
    security_level = models.CharField(
        max_length=20,
        choices=[
            ('BASIC', 'Basic'),
            ('STANDARD', 'Standard'),
            ('HIGH', 'High Security'),
            ('MAXIMUM', 'Maximum Security'),
        ],
        default='STANDARD'
    )
    cctv_enabled = models.BooleanField(default=False)
    access_control_enabled = models.BooleanField(default=False)
    fire_suppression_system = models.BooleanField(default=False)
    
    # Operating Schedule
    operating_hours = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Cost Centers
    rent_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    utility_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labor_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_costs_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Integration
    wms_system = models.CharField(max_length=50, blank=True)  # Warehouse Management System
    wms_integration_enabled = models.BooleanField(default=False)
    
    # Notes & Description
    description = models.TextField(blank=True)
    special_handling_instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_warehouses'
        ordering = ['-is_default', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_tenant_warehouse_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active', 'is_default']),
            models.Index(fields=['tenant', 'warehouse_type']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default warehouse per tenant
        if self.is_default:
            Warehouse.objects.filter(
                tenant=self.tenant,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def total_monthly_cost(self):
        """Total monthly operational cost"""
        return (self.rent_cost_per_month + self.utility_cost_per_month + 
                self.labor_cost_per_month + self.other_costs_per_month)


class StockLocation(TenantBaseModel):
    """Detailed location tracking within warehouses"""
    
    LOCATION_TYPES = [
        ('RECEIVING', 'Receiving Area'),
        ('STORAGE', 'Storage Area'),
        ('PICKING', 'Picking Area'),
        ('PACKING', 'Packing Area'),
        ('SHIPPING', 'Shipping Area'),
        ('QUARANTINE', 'Quarantine Area'),
        ('RETURNS', 'Returns Area'),
        ('QUALITY_CONTROL', 'Quality Control'),
        ('STAGING', 'Staging Area'),
        ('CROSS_DOCK', 'Cross Dock'),
    ]
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='locations'
    )
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='STORAGE')
    
    # Physical Layout
    zone = models.CharField(max_length=10, blank=True)
    aisle = models.CharField(max_length=10, blank=True)
    rack = models.CharField(max_length=10, blank=True)
    shelf = models.CharField(max_length=10, blank=True)
    bin = models.CharField(max_length=10, blank=True)
    level = models.CharField(max_length=10, blank=True)
    
    # Capacity & Restrictions
    max_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    
    # Environment
    temperature_controlled = models.BooleanField(default=False)
    humidity_controlled = models.BooleanField(default=False)
    hazmat_approved = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_pickable = models.BooleanField(default=True)
    is_receivable = models.BooleanField(default=True)
    
    # Picking sequence
    pick_sequence = models.PositiveIntegerField(default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_locations'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'warehouse', 'code'], name='unique_tenant_location_code'),
        ]
        ordering = ['warehouse', 'zone', 'aisle', 'rack', 'shelf', 'bin']
        indexes = [
            models.Index(fields=['tenant', 'warehouse', 'is_active']),
            models.Index(fields=['tenant', 'warehouse', 'location_type']),
        ]
    
    def __str__(self):
        parts = filter(None, [self.zone, self.aisle, self.rack, self.shelf, self.bin])
        location = '-'.join(parts) if parts else self.code
        return f"{self.warehouse.code}/{location}"
    
    @property
    def full_location_code(self):
        """Full location code including all components"""
        parts = filter(None, [self.zone, self.aisle, self.rack, self.shelf, self.bin, self.level])
        return '-'.join(parts) if parts else self.code
    
    @property
    def capacity_utilization(self):
        """Calculate capacity utilization (if max values are set)"""
        # This would be calculated based on current stock in this location
        # Implementation depends on stock tracking requirements
        pass


# ============================================================================
# PRODUCT ATTRIBUTES & SPECIFICATIONS
# ============================================================================

class ProductAttribute(TenantBaseModel):
    """Flexible product attribute system"""
    
    ATTRIBUTE_TYPES = [
        ('TEXT', 'Text'),
        ('NUMBER', 'Number'),
        ('DECIMAL', 'Decimal'),
        ('BOOLEAN', 'Boolean'),
        ('DATE', 'Date'),
        ('COLOR', 'Color'),
        ('IMAGE', 'Image'),
        ('URL', 'URL'),
        ('EMAIL', 'Email'),
        ('SELECT', 'Single Select'),
        ('MULTISELECT', 'Multiple Select'),
        ('TEXTAREA', 'Text Area'),
        ('JSON', 'JSON Data'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='TEXT')
    
    # Validation & Constraints
    is_required = models.BooleanField(default=False)
    is_unique = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=True)
    is_filterable = models.BooleanField(default=True)
    is_variant_attribute = models.BooleanField(default=False)
    
    # Display Properties
    sort_order = models.PositiveIntegerField(default=0)
    display_name = models.CharField(max_length=100, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    placeholder_text = models.CharField(max_length=100, blank=True)
    
    # Validation Rules (JSON)
    validation_rules = models.JSONField(default=dict, blank=True)
    default_value = models.CharField(max_length=255, blank=True)
    
    # Grouping
    attribute_group = models.CharField(max_length=50, blank=True)
    
    # Units (for numeric attributes)
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attributes'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'inventory_product_attributes'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='unique_tenant_attribute_slug'),
        ]
        ordering = ['attribute_group', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'attribute_type']),
        ]
    
    def __str__(self):
        return self.display_name or self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.display_name:
            self.display_name = self.name
        super().save(*args, **kwargs)


class AttributeValue(TenantBaseModel):
    """Predefined values for select-type attributes"""
    
    attribute = models.ForeignKey(
        ProductAttribute,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
    
    # Additional properties for different types
    color_code = models.CharField(max_length=7, blank=True)  # For color attributes
    image = models.ImageField(upload_to='attribute_values/', blank=True, null=True)
    description = models.TextField(blank=True)
    
    # Properties
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Additional data
    extra_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'inventory_attribute_values'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'attribute', 'value'], name='unique_tenant_attribute_value'),
        ]
        ordering = ['attribute__sort_order', 'sort_order', 'display_name']
        indexes = [
            models.Index(fields=['tenant', 'attribute', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.attribute.name}: {self.display_name or self.value}"
    
    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.value
        super().save(*args, **kwargs)


# ============================================================================
# PRODUCT MANAGEMENT
# ============================================================================

class Product(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive product management system"""
    
    PRODUCT_TYPES = [
        ('SIMPLE', 'Simple Product'),
        ('VARIABLE', 'Variable Product'),
        ('GROUPED', 'Grouped Product'),
        ('BUNDLE', 'Product Bundle'),
        ('KIT', 'Kit Product'),
        ('SERVICE', 'Service'),
        ('DIGITAL', 'Digital Product'),
        ('VIRTUAL', 'Virtual Product'),
        ('CONFIGURABLE', 'Configurable Product'),
        ('COMPOSITE', 'Composite Product'),
    ]
    
    PRODUCT_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('DISCONTINUED', 'Discontinued'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('DRAFT', 'Draft'),
        ('ARCHIVED', 'Archived'),
    ]
    
    LIFECYCLE_STAGES = [
        ('INTRODUCTION', 'Introduction'),
        ('GROWTH', 'Growth'),
        ('MATURITY', 'Maturity'),
        ('DECLINE', 'Decline'),
        ('END_OF_LIFE', 'End of Life'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200, db_index=True)
    sku = models.CharField(max_length=50, db_index=True)
    internal_code = models.CharField(max_length=50, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    part_number = models.CharField(max_length=100, blank=True)
    
    # Identification
    barcode = models.CharField(max_length=50, blank=True, db_index=True)
    upc = models.CharField(max_length=20, blank=True)
    ean = models.CharField(max_length=20, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    qr_code = models.CharField(max_length=100, blank=True)
    rfid_tag = models.CharField(max_length=100, blank=True)
    
    # Categorization
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='SIMPLE')
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products'
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products'
    )
    
    # Description & Content
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    long_description = models.TextField(blank=True)
    technical_specifications = models.JSONField(default=dict, blank=True)
    features = models.JSONField(default=list, blank=True)
    benefits = models.JSONField(default=list, blank=True)
    
    # Units & Measurements
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='products'
    )
    
    # Physical Properties
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    weight_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products_by_weight'
    )
    length = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    volume = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    dimension_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products_by_dimension'
    )
    
    # Inventory Settings
    track_inventory = models.BooleanField(default=True)
    is_serialized = models.BooleanField(default=False)
    is_lot_tracked = models.BooleanField(default=False)
    is_batch_tracked = models.BooleanField(default=False)
    is_perishable = models.BooleanField(default=False)
    shelf_life_days = models.IntegerField(null=True, blank=True)
    allow_backorders = models.BooleanField(default=False)
    allow_preorders = models.BooleanField(default=False)
    
    # Stock Levels & Reordering
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    max_stock_level = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    safety_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    economic_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Pricing
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    standard_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    msrp = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    map_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Minimum Advertised Price
    
    # Tax & Accounting
    tax_category = models.CharField(max_length=50, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True)
    commodity_code = models.CharField(max_length=20, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    
    # Suppliers
    preferred_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_products'
    )
    
    # Status & Lifecycle
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS, default='ACTIVE')
    lifecycle_stage = models.CharField(max_length=20, choices=LIFECYCLE_STAGES, default='INTRODUCTION')
    
    # Sales & Purchase Settings
    is_purchasable = models.BooleanField(default=True)
    is_saleable = models.BooleanField(default=True)
    is_returnable = models.BooleanField(default=True)
    is_shippable = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Quality & Compliance
    requires_inspection = models.BooleanField(default=False)
    quality_control_required = models.BooleanField(default=False)
    hazardous_material = models.BooleanField(default=False)
    controlled_substance = models.BooleanField(default=False)
    
    # Packaging
    package_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    package_length = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    package_width = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    package_height = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    pieces_per_package = models.IntegerField(default=1)
    packages_per_case = models.IntegerField(default=1)
    
    # Media & Documentation
    primary_image = models.ImageField(upload_to='products/', blank=True, null=True)
    image_url = models.URLField(blank=True)
    images = models.JSONField(default=list, blank=True)
    videos = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)
    
    # SEO & Marketing
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.CharField(max_length=500, blank=True)
    meta_tags = models.JSONField(default=dict, blank=True)
    
    # Dates
    launch_date = models.DateField(null=True, blank=True)
    discontinue_date = models.DateField(null=True, blank=True)
    last_sold_date = models.DateTimeField(null=True, blank=True)
    last_purchased_date = models.DateTimeField(null=True, blank=True)
    
    # Analytics & Tracking
    sales_velocity = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    abc_classification = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        blank=True
    )
    xyz_classification = models.CharField(
        max_length=1,
        choices=[('X', 'Class X'), ('Y', 'Class Y'), ('Z', 'Class Z')],
        blank=True
    )
    
    # Custom Fields & Tags
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    internal_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_products'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'sku'], name='unique_tenant_product_sku'),
            models.UniqueConstraint(
                fields=['tenant', 'barcode'],
                condition=models.Q(barcode__isnull=False) & ~models.Q(barcode=''),
                name='unique_tenant_product_barcode'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'sku']),
            models.Index(fields=['tenant', 'barcode']),
            models.Index(fields=['tenant', 'status', 'is_saleable']),
            models.Index(fields=['tenant', 'category', 'status']),
            models.Index(fields=['tenant', 'brand', 'status']),
            models.Index(fields=['tenant', 'product_type']),
            models.Index(fields=['tenant', 'abc_classification']),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.name}"
    
    @property
    def margin_percentage(self):
        """Gross margin percentage"""
        if self.selling_price and self.cost_price:
            margin = ((self.selling_price - self.cost_price) / self.selling_price) * 100
            return round(margin, 2)
        return 0
    
    @property
    def markup_percentage(self):
        """Markup percentage"""
        if self.cost_price and self.cost_price > 0:
            markup = ((self.selling_price - self.cost_price) / self.cost_price) * 100
            return round(markup, 2)
        return 0
    
    @property
    def full_category_path(self):
        """Get full category path"""
        parts = []
        if self.department:
            parts.append(self.department.name)
        if self.category:
            parts.append(self.category.name)
        if self.subcategory:
            parts.append(self.subcategory.name)
        return " > ".join(parts)
    
    @property
    def total_stock(self):
        """Total stock across all warehouses"""
        return self.stock_items.filter(is_active=True).aggregate(
            total=models.Sum('quantity_on_hand')
        )['total'] or Decimal('0')
    
    @property
    def available_stock(self):
        """Available stock across all warehouses"""
        return self.stock_items.filter(is_active=True).aggregate(
            total=models.Sum('quantity_available')
        )['total'] or Decimal('0')
    
    @property
    def reserved_stock(self):
        """Reserved stock across all warehouses"""
        return self.stock_items.filter(is_active=True).aggregate(
            total=models.Sum('quantity_reserved')
        )['total'] or Decimal('0')
    
    def clean(self):
        if not self.sku:
            # Auto-generate SKU
            last_product = Product.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_product:
                try:
                    last_num = int(last_product.sku.replace('PRD', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.sku = f"PRD{last_num + 1:06d}"


class ProductAttributeValue(TenantBaseModel):
    """Junction table for product attributes with flexible value storage"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='attribute_values'
    )
    attribute = models.ForeignKey(
        ProductAttribute,
        on_delete=models.CASCADE
    )
    
    # Value storage (only one should be used based on attribute type)
    value = models.ForeignKey(
        AttributeValue,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(null=True, blank=True)
    
    # For multiple select attributes
    multiple_values = models.ManyToManyField(AttributeValue, blank=True, related_name='product_multi_values')
    
    class Meta:
        db_table = 'inventory_product_attribute_values'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'product', 'attribute'], name='unique_tenant_product_attribute'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'product']),
            models.Index(fields=['tenant', 'attribute']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}: {self.get_display_value()}"
    
    def get_display_value(self):
        """Get the appropriate display value based on attribute type"""
        if self.attribute.attribute_type == 'SELECT' and self.value:
            return self.value.display_name
        elif self.attribute.attribute_type == 'MULTISELECT':
            values = [v.display_name for v in self.multiple_values.all()]
            return ', '.join(values)
        elif self.attribute.attribute_type in ['TEXT', 'TEXTAREA', 'URL', 'EMAIL']:
            return self.text_value
        elif self.attribute.attribute_type in ['NUMBER', 'DECIMAL']:
            return str(self.number_value) if self.number_value else ''
        elif self.attribute.attribute_type == 'DATE':
            return str(self.date_value) if self.date_value else ''
        elif self.attribute.attribute_type == 'BOOLEAN':
            return 'Yes' if self.boolean_value else 'No'
        elif self.attribute.attribute_type == 'JSON':
            return json.dumps(self.json_value) if self.json_value else ''
        return ''
    
    def set_value(self, value):
        """Set value based on attribute type"""
        if self.attribute.attribute_type == 'SELECT':
            if isinstance(value, AttributeValue):
                self.value = value
            elif isinstance(value, str):
                self.value = AttributeValue.objects.get(attribute=self.attribute, value=value)
        elif self.attribute.attribute_type in ['TEXT', 'TEXTAREA', 'URL', 'EMAIL']:
            self.text_value = str(value)
        elif self.attribute.attribute_type in ['NUMBER', 'DECIMAL']:
            self.number_value = Decimal(str(value))
        elif self.attribute.attribute_type == 'DATE':
            self.date_value = value
        elif self.attribute.attribute_type == 'BOOLEAN':
            self.boolean_value = bool(value)
        elif self.attribute.attribute_type == 'JSON':
            self.json_value = value


class ProductVariation(TenantBaseModel, SoftDeleteMixin):
    """Product variations for configurable products"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variations'
    )
    variation_code = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255)
    
    # Override product properties
    sku = models.CharField(max_length=50, blank=True)
    barcode = models.CharField(max_length=50, blank=True)
    
    # Pricing overrides
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    msrp = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Physical property overrides
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    
    # Stock level overrides
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reorder_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Media
    primary_image = models.ImageField(upload_to='variations/', blank=True, null=True)
    images = models.JSONField(default=list, blank=True)
    
    # Attribute combinations (for variant generation)
    attribute_values = models.ManyToManyField(
        AttributeValue,
        blank=True,
        related_name='product_variations'
    )
    
    # Additional properties
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_product_variations'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'product', 'variation_code'], name='unique_tenant_variation_code'),
            models.UniqueConstraint(
                fields=['tenant', 'sku'],
                condition=models.Q(sku__isnull=False) & ~models.Q(sku=''),
                name='unique_tenant_variation_sku'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'barcode'],
                condition=models.Q(barcode__isnull=False) & ~models.Q(barcode=''),
                name='unique_tenant_variation_barcode'
            ),
        ]
        ordering = ['product__name', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['tenant', 'sku']),
            models.Index(fields=['tenant', 'barcode']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"
    
    @property
    def effective_cost_price(self):
        """Get effective cost price (variation or parent product)"""
        return self.cost_price or self.product.cost_price
    
    @property
    def effective_selling_price(self):
        """Get effective selling price (variation or parent product)"""
        return self.selling_price or self.product.selling_price
    
    @property
    def effective_sku(self):
        """Get effective SKU (variation or generated)"""
        return self.sku or f"{self.product.sku}-{self.variation_code}"
    
    @property
    def attribute_display(self):
        """Get attribute combination display"""
        attrs = []
        for attr_value in self.attribute_values.all():
            attrs.append(f"{attr_value.attribute.name}: {attr_value.display_name}")
        return ", ".join(attrs)
    
    @property
    def total_stock(self):
        """Total stock across all warehouses"""
        return self.stock_items.filter(is_active=True).aggregate(
            total=models.Sum('quantity_on_hand')
        )['total'] or Decimal('0')
    
    @property
    def available_stock(self):
        """Available stock across all warehouses"""
        return self.stock_items.filter(is_active=True).aggregate(
            total=models.Sum('quantity_available')
        )['total'] or Decimal('0')
    
    def clean(self):
        if not self.variation_code:
            # Auto-generate variation code
            existing_count = ProductVariation.objects.filter(
                tenant=self.tenant,
                product=self.product
            ).count()
            self.variation_code = f"VAR{existing_count + 1:03d}"
        
        if not self.sku:
            self.sku = f"{self.product.sku}-{self.variation_code}"


# Continuing from Part 1...

# ============================================================================
# PRODUCT SUPPLIER RELATIONSHIPS
# ============================================================================

class ProductSupplier(TenantBaseModel):
    """Many-to-many relationship between products and suppliers with detailed terms"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='supplier_items'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='product_items'
    )
    
    # Supplier-specific product info
    supplier_sku = models.CharField(max_length=50, blank=True)
    supplier_product_name = models.CharField(max_length=200, blank=True)
    manufacturer_part_number = models.CharField(max_length=100, blank=True)
    
    # Pricing & Terms
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    price_valid_from = models.DateField(default=date.today)
    price_valid_to = models.DateField(null=True, blank=True)
    
    # Order Terms
    minimum_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    maximum_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    order_multiple = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    lead_time_days = models.IntegerField(default=0)
    
    # Quality & Performance
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Status & Preferences
    is_active = models.BooleanField(default=True)
    is_preferred = models.BooleanField(default=False)
    
    # Purchase History
    last_purchase_date = models.DateTimeField(null=True, blank=True)
    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_purchases_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_orders_count = models.IntegerField(default=0)
    
    # Additional Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    warranty_terms = models.TextField(blank=True)
    return_policy = models.TextField(blank=True)
    special_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_product_suppliers'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'product', 'supplier'], name='unique_tenant_product_supplier'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['tenant', 'supplier', 'is_active']),
            models.Index(fields=['tenant', 'is_preferred']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - {self.supplier.name}"
    
    @property
    def effective_lead_time(self):
        """Get effective lead time considering supplier's default"""
        return self.lead_time_days or self.supplier.lead_time_days


# ============================================================================
# BATCH & SERIAL NUMBER TRACKING
# ============================================================================

class Batch(TenantBaseModel):
    """Enhanced batch/lot tracking for products"""
    
    BATCH_STATUS = [
        ('ACTIVE', 'Active'),
        ('QUARANTINED', 'Quarantined'),
        ('EXPIRED', 'Expired'),
        ('RECALLED', 'Recalled'),
        ('CONSUMED', 'Fully Consumed'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    batch_number = models.CharField(max_length=50)
    lot_number = models.CharField(max_length=50, blank=True)
    
    # Manufacturing Information
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    best_before_date = models.DateField(null=True, blank=True)
    
    # Quality Information
    quality_grade = models.CharField(
        max_length=1,
        choices=[('A', 'Grade A'), ('B', 'Grade B'), ('C', 'Grade C'), ('D', 'Grade D')],
        default='A'
    )
    quality_notes = models.TextField(blank=True)
    quality_test_results = models.JSONField(default=dict, blank=True)
    
    # Quantities
    initial_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reserved_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    landed_cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Source Information
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='batches'
    )
    purchase_order_number = models.CharField(max_length=50, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    
    # Status & Tracking
    status = models.CharField(max_length=20, choices=BATCH_STATUS, default='ACTIVE')
    received_date = models.DateTimeField(default=timezone.now)
    quarantine_reason = models.TextField(blank=True)
    recall_reason = models.TextField(blank=True)
    
    # Certifications & Compliance
    certifications = models.JSONField(default=list, blank=True)
    compliance_data = models.JSONField(default=dict, blank=True)
    
    # Additional Information
    storage_conditions = models.TextField(blank=True)
    handling_instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_batches'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'product', 'batch_number'], name='unique_tenant_product_batch'),
        ]
        ordering = ['expiry_date', 'received_date']
        indexes = [
            models.Index(fields=['tenant', 'product', 'status']),
            models.Index(fields=['tenant', 'expiry_date']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - Batch: {self.batch_number}"
    
    @property
    def available_quantity(self):
        """Available quantity (current - reserved)"""
        return self.current_quantity - self.reserved_quantity
    
    @property
    def is_expired(self):
        """Check if batch is expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False
    
    @property
    def days_until_expiry(self):
        """Days until expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def is_near_expiry(self):
        """Check if batch is nearing expiry (within 30 days)"""
        days_to_expiry = self.days_until_expiry
        return days_to_expiry is not None and 0 <= days_to_expiry <= 30
    
    def reserve_quantity(self, quantity):
        """Reserve quantity from batch"""
        quantity = Decimal(str(quantity))
        if self.available_quantity >= quantity:
            self.reserved_quantity += quantity
            self.save(update_fields=['reserved_quantity'])
            return True
        return False
    
    def release_reservation(self, quantity):
        """Release reserved quantity"""
        quantity = Decimal(str(quantity))
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
            self.save(update_fields=['reserved_quantity'])
            return True
        return False


class SerialNumber(TenantBaseModel):
    """Serial number tracking for individual items"""
    
    SERIAL_STATUS = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('SOLD', 'Sold'),
        ('RETURNED', 'Returned'),
        ('DEFECTIVE', 'Defective'),
        ('RECALLED', 'Recalled'),
        ('SCRAPPED', 'Scrapped'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='serial_numbers'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='serial_numbers'
    )
    serial_number = models.CharField(max_length=100)
    
    # Manufacturing Details
    manufacture_date = models.DateField(null=True, blank=True)
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    
    # Status & Location
    status = models.CharField(max_length=20, choices=SERIAL_STATUS, default='AVAILABLE')
    current_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='serial_numbers'
    )
    
    # Cost & Value
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Customer Information (if sold)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    sale_date = models.DateTimeField(null=True, blank=True)
    
    # Service History
    service_history = models.JSONField(default=list, blank=True)
    last_service_date = models.DateField(null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    custom_attributes = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'inventory_serial_numbers'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'product', 'serial_number'], name='unique_tenant_product_serial'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'product', 'status']),
            models.Index(fields=['tenant', 'serial_number']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - SN: {self.serial_number}"
    
    @property
    def warranty_active(self):
        """Check if warranty is still active"""
        if self.warranty_end_date:
            return self.warranty_end_date >= timezone.now().date()
        return False
    
    @property
    def warranty_days_remaining(self):
        """Days remaining in warranty"""
        if self.warranty_end_date:
            delta = self.warranty_end_date - timezone.now().date()
            return max(0, delta.days)
        return 0


# ============================================================================
# ADVANCED STOCK MANAGEMENT
# ============================================================================

class StockItem(TenantBaseModel):
    """Enhanced stock item management with comprehensive tracking"""
    
    # Product & Location References
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='stock_items'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_items'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_items'
    )
    
    # Quantity Tracking
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_available = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_incoming = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_on_order = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_picked = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_shipped = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Valuation & Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    standard_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # ABC/XYZ Classification
    abc_classification = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        blank=True
    )
    xyz_classification = models.CharField(
        max_length=1,
        choices=[('X', 'Class X'), ('Y', 'Class Y'), ('Z', 'Class Z')],
        blank=True
    )
    
    # Cycle Counting
    last_counted_date = models.DateTimeField(null=True, blank=True)
    last_counted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='counted_stock_items'
    )
    cycle_count_frequency_days = models.IntegerField(default=90)
    next_count_due = models.DateField(null=True, blank=True)
    variance_tolerance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    
    # Movement Tracking
    last_movement_date = models.DateTimeField(null=True, blank=True)
    last_movement_type = models.CharField(max_length=20, blank=True)
    total_movements_count = models.IntegerField(default=0)
    
    # Performance Metrics
    turnover_rate = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    days_on_hand = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    stockout_count = models.IntegerField(default=0)
    last_stockout_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Flags
    is_active = models.BooleanField(default=True)
    is_quarantined = models.BooleanField(default=False)
    is_consignment = models.BooleanField(default=False)
    is_dropship = models.BooleanField(default=False)
    
    # Special Handling
    requires_special_handling = models.BooleanField(default=False)
    handling_instructions = models.TextField(blank=True)
    storage_temperature_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_temperature_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_humidity_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Integration & External Systems
    external_system_id = models.CharField(max_length=100, blank=True)
    external_system_name = models.CharField(max_length=50, blank=True)
    last_sync_date = models.DateTimeField(null=True, blank=True)
    
    # Notes & Custom Data
    notes = models.TextField(blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'inventory_stock_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'product', 'variation', 'warehouse', 'location', 'batch'],
                name='unique_stock_item_location'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'product', 'warehouse']),
            models.Index(fields=['tenant', 'warehouse', 'quantity_available']),
            models.Index(fields=['tenant', 'abc_classification']),
            models.Index(fields=['tenant', 'next_count_due']),
            models.Index(fields=['tenant', 'is_quarantined']),
        ]
    
    def __str__(self):
        product_name = f"{self.product.sku}"
        if self.variation:
            product_name += f"-{self.variation.variation_code}"
        return f"{product_name} @ {self.warehouse.code}: {self.quantity_available}"
    
    def reserve_stock(self, quantity, reason=''):
        """Reserve stock for orders"""
        quantity = Decimal(str(quantity))
        if self.quantity_available >= quantity:
            self.quantity_reserved += quantity
            self.quantity_available -= quantity
            self.save(update_fields=['quantity_reserved', 'quantity_available'])
            
            # Log the reservation
            self.create_movement('RESERVE', quantity, reason)
            return True
        return False
    
    def release_reservation(self, quantity, reason=''):
        """Release reserved stock"""
        quantity = Decimal(str(quantity))
        if self.quantity_reserved >= quantity:
            self.quantity_reserved -= quantity
            self.quantity_available += quantity
            self.save(update_fields=['quantity_reserved', 'quantity_available'])
            
            # Log the release
            self.create_movement('RELEASE', quantity, reason)
            return True
        return False
    
    def allocate_stock(self, quantity, reason=''):
        """Allocate reserved stock for picking/shipping"""
        quantity = Decimal(str(quantity))
        if self.quantity_reserved >= quantity:
            self.quantity_reserved -= quantity
            self.quantity_allocated += quantity
            self.save(update_fields=['quantity_reserved', 'quantity_allocated'])
            
            # Log the allocation
            self.create_movement('ALLOCATE', quantity, reason)
            return True
        return False
    
    def pick_stock(self, quantity, reason=''):
        """Pick allocated stock"""
        quantity = Decimal(str(quantity))
        if self.quantity_allocated >= quantity:
            self.quantity_allocated -= quantity
            self.quantity_picked += quantity
            self.save(update_fields=['quantity_allocated', 'quantity_picked'])
            
            # Log the pick
            self.create_movement('PICK', quantity, reason)
            return True
        return False
    
    def ship_stock(self, quantity, reason=''):
        """Ship picked stock"""
        quantity = Decimal(str(quantity))
        if self.quantity_picked >= quantity:
            self.quantity_picked -= quantity
            self.quantity_shipped += quantity
            self.quantity_on_hand -= quantity
            self.save(update_fields=['quantity_picked', 'quantity_shipped', 'quantity_on_hand'])
            
            # Log the shipment
            self.create_movement('SHIP', quantity, reason)
            return True
        return False
    
    def receive_stock(self, quantity, unit_cost=None, reason=''):
        """Receive new stock"""
        quantity = Decimal(str(quantity))
        self.quantity_on_hand += quantity
        self.quantity_available += quantity
        
        # Update costs if provided
        if unit_cost:
            self.update_average_cost(quantity, unit_cost)
            self.last_cost = unit_cost
        
        self.save(update_fields=['quantity_on_hand', 'quantity_available', 'average_cost', 'last_cost', 'total_value'])
        
        # Log the receipt
        self.create_movement('RECEIVE', quantity, reason, unit_cost)
        return True
    
    def adjust_stock(self, new_quantity, reason='', user=None):
        """Adjust stock to specific quantity"""
        old_quantity = self.quantity_on_hand
        adjustment = Decimal(str(new_quantity)) - old_quantity
        
        self.quantity_on_hand = Decimal(str(new_quantity))
        self.quantity_available = self.quantity_on_hand - self.quantity_reserved - self.quantity_allocated
        self.update_total_value()
        self.save(update_fields=['quantity_on_hand', 'quantity_available', 'total_value'])
        
        # Log the adjustment
        movement_type = 'ADJUST_IN' if adjustment > 0 else 'ADJUST_OUT'
        self.create_movement(movement_type, abs(adjustment), reason, user=user)
        
        return adjustment
    
    def update_average_cost(self, new_quantity, new_cost):
        """Update average cost using weighted average"""
        total_value = (self.quantity_on_hand * self.average_cost) + (new_quantity * new_cost)
        total_quantity = self.quantity_on_hand + new_quantity
        
        if total_quantity > 0:
            self.average_cost = (total_value / total_quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        self.update_total_value()
    
    def update_total_value(self):
        """Update total inventory value"""
        self.total_value = self.quantity_on_hand * self.average_cost
    
    def create_movement(self, movement_type, quantity, reason='', unit_cost=None, user=None):
        """Create a stock movement record"""
        from apps.inventory.models import StockMovement  # Avoid circular import
        
        return StockMovement.objects.create(
            tenant=self.tenant,
            stock_item=self,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost or self.average_cost,
            total_cost=(quantity * (unit_cost or self.average_cost)),
            reason=reason,
            performed_by=user,
            stock_before=self.quantity_on_hand,
            stock_after=self.quantity_on_hand,
            notes=reason
        )
    
    @property
    def is_low_stock(self):
        """Check if item is below reorder point"""
        reorder_point = self.product.reorder_point
        if self.variation and self.variation.reorder_point:
            reorder_point = self.variation.reorder_point
        return self.quantity_available <= reorder_point
    
    @property
    def is_out_of_stock(self):
        """Check if item is out of stock"""
        return self.quantity_available <= 0
    
    @property
    def stock_coverage_days(self):
        """Calculate days of stock coverage based on consumption"""
        if self.turnover_rate > 0 and self.quantity_available > 0:
            daily_consumption = self.turnover_rate / 365
            return (self.quantity_available / daily_consumption).quantize(Decimal('0.1'))
        return Decimal('0')
    
    def calculate_turnover_rate(self, days=365):
        """Calculate inventory turnover rate"""
        from django.db.models import Sum
        from apps.inventory.models import StockMovement
        
        # Get total outbound movements in the period
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        outbound_quantity = StockMovement.objects.filter(
            stock_item=self,
            movement_date__gte=start_date,
            movement_date__lte=end_date,
            movement_type__in=['OUT', 'SHIP', 'SALE', 'TRANSFER_OUT']
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        # Calculate average inventory
        average_inventory = (self.quantity_on_hand + outbound_quantity) / 2
        
        if average_inventory > 0:
            self.turnover_rate = outbound_quantity / average_inventory * (365 / days)
            self.days_on_hand = 365 / self.turnover_rate if self.turnover_rate > 0 else 0
        else:
            self.turnover_rate = 0
            self.days_on_hand = 0
        
        self.save(update_fields=['turnover_rate', 'days_on_hand'])


# ============================================================================
# STOCK MOVEMENTS & TRANSACTIONS
# ============================================================================

class StockMovement(TenantBaseModel):
    """Comprehensive stock movement tracking with full audit trail"""
    
    MOVEMENT_TYPES = [
        # Inbound
        ('RECEIVE', 'Stock Receipt'),
        ('PURCHASE', 'Purchase Order Receipt'),
        ('TRANSFER_IN', 'Transfer In'),
        ('RETURN_IN', 'Customer Return'),
        ('ADJUST_IN', 'Adjustment Increase'),
        ('MANUFACTURING_IN', 'Manufacturing Output'),
        ('FOUND', 'Found Stock'),
        
        # Outbound
        ('SALE', 'Sale/Shipment'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('RETURN_OUT', 'Return to Supplier'),
        ('ADJUST_OUT', 'Adjustment Decrease'),
        ('MANUFACTURING_OUT', 'Manufacturing Consumption'),
        ('DAMAGE', 'Damaged Stock'),
        ('LOSS', 'Stock Loss'),
        ('EXPIRED', 'Expired Stock'),
        ('SAMPLE', 'Sample Usage'),
        
        # Internal
        ('RESERVE', 'Stock Reservation'),
        ('RELEASE', 'Release Reservation'),
        ('ALLOCATE', 'Stock Allocation'),
        ('PICK', 'Stock Picking'),
        ('SHIP', 'Stock Shipment'),
        ('RELOCATE', 'Location Change'),
        ('QUARANTINE', 'Quarantine Stock'),
        ('RELEASE_QUARANTINE', 'Release from Quarantine'),
    ]
    
    MOVEMENT_REASONS = [
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('SALES_ORDER', 'Sales Order'),
        ('TRANSFER_ORDER', 'Transfer Order'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('CYCLE_COUNT', 'Cycle Count'),
        ('PHYSICAL_COUNT', 'Physical Inventory'),
        ('CUSTOMER_RETURN', 'Customer Return'),
        ('SUPPLIER_RETURN', 'Return to Supplier'),
        ('MANUFACTURING', 'Manufacturing Order'),
        ('QUALITY_CONTROL', 'Quality Control'),
        ('DAMAGE', 'Damaged Goods'),
        ('EXPIRY', 'Product Expiry'),
        ('THEFT', 'Theft/Loss'),
        ('SAMPLE', 'Sample/Demo'),
        ('CORRECTION', 'Data Correction'),
        ('SYSTEM_ADJUSTMENT', 'System Adjustment'),
        ('OTHER', 'Other'),
    ]
    
    # Unique Movement ID
    movement_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # References
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movements'
    )
    
    # Movement Details
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    movement_reason = models.CharField(max_length=20, choices=MOVEMENT_REASONS)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Stock Levels (before and after)
    stock_before = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stock_after = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Location Information
    from_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        related_name='movements_from',
        null=True, blank=True
    )
    to_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        related_name='movements_to',
        null=True, blank=True
    )
    
    # Document References
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    document_url = models.URLField(blank=True)
    
    # Timing
    movement_date = models.DateTimeField(default=timezone.now)
    planned_date = models.DateTimeField(null=True, blank=True)
    actual_date = models.DateTimeField(null=True, blank=True)
    
    # User Information
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_movements'
    )
    authorized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='authorized_movements'
    )
    
    # Status & Workflow
    is_confirmed = models.BooleanField(default=True)
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_movements'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # System Information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    api_source = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'inventory_stock_movements'
        ordering = ['-movement_date']
        indexes = [
            models.Index(fields=['tenant', 'stock_item', '-movement_date']),
            models.Index(fields=['tenant', 'movement_type', '-movement_date']),
            models.Index(fields=['tenant', 'movement_reason', '-movement_date']),
            models.Index(fields=['tenant', 'reference_type', 'reference_id']),
            models.Index(fields=['tenant', 'performed_by', '-movement_date']),
            models.Index(fields=['tenant', '-movement_date']),
        ]
    
    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.stock_item.product.sku} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity * self.unit_cost
        
        # Set actual date if not provided
        if not self.actual_date:
            self.actual_date = self.movement_date
        
        super().save(*args, **kwargs)
    
    @property
    def is_inbound(self):
        """Check if movement is inbound"""
        inbound_types = ['RECEIVE', 'PURCHASE', 'TRANSFER_IN', 'RETURN_IN', 'ADJUST_IN', 
                        'MANUFACTURING_IN', 'FOUND']
        return self.movement_type in inbound_types
    
    @property
    def is_outbound(self):
        """Check if movement is outbound"""
        outbound_types = ['SALE', 'TRANSFER_OUT', 'RETURN_OUT', 'ADJUST_OUT', 
                         'MANUFACTURING_OUT', 'DAMAGE', 'LOSS', 'EXPIRED', 'SAMPLE']
        return self.movement_type in outbound_types
    
    @property
    def cost_impact(self):
        """Calculate cost impact (positive for inbound, negative for outbound)"""
        if self.is_inbound:
            return self.total_cost
        elif self.is_outbound:
            return -self.total_cost
        return Decimal('0')


# ============================================================================
# STOCK VALUATION LAYERS (FOR FIFO/LIFO)
# ============================================================================

class StockValuationLayer(TenantBaseModel):
    """Stock valuation layers for FIFO/LIFO cost tracking"""
    
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='valuation_layers'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='valuation_layers'
    )
    
    # Layer Information
    layer_sequence = models.PositiveIntegerField()
    receipt_date = models.DateTimeField(default=timezone.now)
    
    # Quantities
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_consumed = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_remaining = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Source Information
    source_movement = models.ForeignKey(
        StockMovement,
        on_delete=models.CASCADE,
        related_name='valuation_layers'
    )
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_fully_consumed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'inventory_stock_valuation_layers'
        ordering = ['stock_item', 'receipt_date', 'layer_sequence']  # FIFO order
        indexes = [
            models.Index(fields=['tenant', 'stock_item', 'is_active']),
            models.Index(fields=['tenant', 'stock_item', 'receipt_date']),
        ]
    
    def __str__(self):
        return f"Layer {self.layer_sequence}: {self.stock_item} - {self.quantity_remaining} @ {self.unit_cost}"
    
    def consume_quantity(self, quantity):
        """Consume quantity from this layer (FIFO/LIFO)"""
        quantity = Decimal(str(quantity))
        available = self.quantity_remaining
        
        if available >= quantity:
            # Can consume full quantity from this layer
            self.quantity_consumed += quantity
            self.quantity_remaining -= quantity
            
            if self.quantity_remaining == 0:
                self.is_fully_consumed = True
            
            self.save(update_fields=['quantity_consumed', 'quantity_remaining', 'is_fully_consumed'])
            return quantity
        else:
            # Can only consume what's available
            self.quantity_consumed += available
            self.quantity_remaining = Decimal('0')
            self.is_fully_consumed = True
            
            self.save(update_fields=['quantity_consumed', 'quantity_remaining', 'is_fully_consumed'])
            return available
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_received * self.unit_cost
        
        # Auto-generate sequence if not provided
        if not self.layer_sequence:
            last_layer = StockValuationLayer.objects.filter(
                stock_item=self.stock_item
            ).order_by('-layer_sequence').first()
            
            self.layer_sequence = (last_layer.layer_sequence + 1) if last_layer else 1
        
        super().save(*args, **kwargs)


# ============================================================================
# PURCHASE ORDER MANAGEMENT
# ============================================================================

class PurchaseOrder(TenantBaseModel):
    """Comprehensive purchase order management"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SENT_TO_SUPPLIER', 'Sent to Supplier'),
        ('ACKNOWLEDGED', 'Acknowledged by Supplier'),
        ('CONFIRMED', 'Confirmed'),
        ('PARTIAL_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('INVOICED', 'Invoiced'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
        ('RETURNED', 'Returned'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    # Basic Information
    po_number = models.CharField(max_length=100, blank=True)
    po_type = models.CharField(
        max_length=20,
        choices=[
            ('STANDARD', 'Standard Purchase'),
            ('DROP_SHIP', 'Drop Ship'),
            ('CONSIGNMENT', 'Consignment'),
            ('BLANKET', 'Blanket Order'),
            ('SERVICE', 'Service Order'),
        ],
        default='STANDARD'
    )
    
    # Supplier & Delivery
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    delivery_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    
    # Dates
    order_date = models.DateField(default=date.today)
    required_date = models.DateField()
    promised_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    
    # Status & Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Financial Information
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Payment Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    early_payment_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    late_payment_penalty = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Personnel
    buyer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_purchase_orders'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_purchase_orders'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True)
    shipping_terms = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Supplier References
    supplier_po_number = models.CharField(max_length=100, blank=True)
    supplier_quote_number = models.CharField(max_length=100, blank=True)
    supplier_contact = models.CharField(max_length=100, blank=True)
    
    # Drop Shipping (if applicable)
    is_dropship_order = models.BooleanField(default=False)
    dropship_customer_name = models.CharField(max_length=200, blank=True)
    dropship_address = models.JSONField(default=dict, blank=True)
    
    # Quality & Inspection
    requires_inspection = models.BooleanField(default=False)
    inspection_required_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    quality_standards = models.TextField(blank=True)
    
    # Additional Information
    terms_and_conditions = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    reason_for_purchase = models.TextField(blank=True)
    
    # Document Management
    documents = models.JSONField(default=list, blank=True)
    revision_number = models.IntegerField(default=1)
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='revisions'
    )
    
    class Meta:
        db_table = 'inventory_purchase_orders'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'po_number'], name='unique_tenant_po_number'),
        ]
        ordering = ['-order_date', '-id']
        indexes = [
            models.Index(fields=['tenant', 'supplier', 'status']),
            models.Index(fields=['tenant', 'status', 'order_date']),
            models.Index(fields=['tenant', 'buyer', 'status']),
        ]
    
    def __str__(self):
        return f"PO-{self.po_number} - {self.supplier.name}"
    
    def clean(self):
        if not self.po_number:
            # Auto-generate PO number
            last_po = PurchaseOrder.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_po:
                try:
                    last_num = int(last_po.po_number.replace('PO', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.po_number = f"PO{last_num + 1:06d}"
    
    @property
    def total_items(self):
        """Total number of line items"""
        return self.items.count()
    
    @property
    def total_quantity_ordered(self):
        """Total quantity across all items"""
        return self.items.aggregate(
            total=models.Sum('quantity_ordered')
        )['total'] or Decimal('0')
    
    @property
    def total_quantity_received(self):
        """Total quantity received across all items"""
        return self.items.aggregate(
            total=models.Sum('quantity_received')
        )['total'] or Decimal('0')
    
    @property
    def received_percentage(self):
        """Percentage of total order received"""
        total_ordered = self.total_quantity_ordered
        if total_ordered > 0:
            total_received = self.total_quantity_received
            return (total_received / total_ordered * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_fully_received(self):
        """Check if order is fully received"""
        return self.received_percentage >= 100
    
    @property
    def is_overdue(self):
        """Check if order is overdue"""
        if self.required_date and self.status not in ['RECEIVED', 'COMPLETED', 'CANCELLED']:
            return self.required_date < timezone.now().date()
        return False
    
    def calculate_totals(self):
        """Recalculate all totals"""
        # Calculate subtotal from line items
        self.subtotal = self.items.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0')
        
        # Calculate discount
        if self.discount_percentage > 0:
            self.discount_amount = (self.subtotal * self.discount_percentage / 100).quantize(Decimal('0.01'))
        
        # Calculate tax
        if self.tax_rate > 0:
            taxable_amount = self.subtotal - self.discount_amount
            self.tax_amount = (taxable_amount * self.tax_rate / 100).quantize(Decimal('0.01'))
        
        # Calculate total
        self.total_amount = (
            self.subtotal - self.discount_amount + self.tax_amount + 
            self.shipping_cost + self.handling_cost + self.other_charges
        )
        
        self.save(update_fields=[
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount'
        ])
    
    def approve(self, user):
        """Approve the purchase order"""
        if self.status == 'PENDING_APPROVAL':
            self.status = 'APPROVED'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_by', 'approved_at'])
            return True
        return False
    
    def send_to_supplier(self, user):
        """Mark as sent to supplier"""
        if self.status == 'APPROVED':
            self.status = 'SENT_TO_SUPPLIER'
            self.save(update_fields=['status'])
            # Here you would integrate with email/EDI system
            return True
        return False
    
    def cancel(self, reason, user):
        """Cancel the purchase order"""
        if self.status not in ['RECEIVED', 'COMPLETED', 'CANCELLED']:
            self.status = 'CANCELLED'
            self.internal_notes = f"Cancelled by {user.get_full_name()}: {reason}\n{self.internal_notes}"
            self.save(update_fields=['status', 'internal_notes'])
            return True
        return False


class PurchaseOrderItem(TenantBaseModel):
    """Purchase order line items with comprehensive tracking"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='purchase_order_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='purchase_order_items'
    )
    
    # Supplier Product Information
    supplier_sku = models.CharField(max_length=50, blank=True)
    supplier_product_name = models.CharField(max_length=200, blank=True)
    
    # Quantities
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_invoiced = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit Information
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    unit_conversion_factor = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    required_date = models.DateField(null=True, blank=True)
    promised_date = models.DateField(null=True, blank=True)
    
    # Quality & Inspection
    requires_inspection = models.BooleanField(default=False)
    inspection_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    quality_specifications = models.TextField(blank=True)
    
    # Delivery & Location
    delivery_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchase_order_items'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('ORDERED', 'Ordered'),
            ('CONFIRMED', 'Confirmed'),
            ('PARTIAL_RECEIVED', 'Partially Received'),
            ('RECEIVED', 'Fully Received'),
            ('CANCELLED', 'Cancelled'),
            ('RETURNED', 'Returned'),
        ],
        default='ORDERED'
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_purchase_order_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'purchase_order', 'line_number'],
                name='unique_po_line_number'
            ),
        ]
        ordering = ['purchase_order', 'line_number']
        indexes = [
            models.Index(fields=['tenant', 'purchase_order']),
            models.Index(fields=['tenant', 'product', 'status']),
        ]
    
    def __str__(self):
        product_name = self.product.name
        if self.variation:
            product_name += f" - {self.variation.name}"
        return f"{self.purchase_order.po_number} Line {self.line_number}: {product_name}"
    
    @property
    def pending_quantity(self):
        """Quantity still pending receipt"""
        return self.quantity_ordered - self.quantity_received
    
    @property
    def received_percentage(self):
        """Percentage of line item received"""
        if self.quantity_ordered > 0:
            return (self.quantity_received / self.quantity_ordered * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_fully_received(self):
        """Check if line item is fully received"""
        return self.quantity_received >= self.quantity_ordered
    
    @property
    def is_overdue(self):
        """Check if line item is overdue"""
        if self.required_date and not self.is_fully_received:
            return self.required_date < timezone.now().date()
        return False
    
    def save(self, *args, **kwargs):
        # Calculate discount amount
        if self.discount_percentage > 0:
            self.discount_amount = (self.quantity_ordered * self.unit_cost * self.discount_percentage / 100).quantize(Decimal('0.01'))
        
        # Calculate total amount
        gross_amount = self.quantity_ordered * self.unit_cost
        self.total_amount = gross_amount - self.discount_amount
        
        # Auto-assign line number if not provided
        if not self.line_number:
            last_line = PurchaseOrderItem.objects.filter(
                purchase_order=self.purchase_order
            ).order_by('-line_number').first()
            
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    def receive_quantity(self, quantity, batch_number=None, expiry_date=None, location=None, user=None):
        """Receive quantity for this line item"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_received + quantity > self.quantity_ordered:
            return False, "Cannot receive more than ordered quantity"
        
        # Update received quantity
        self.quantity_received += quantity
        
        # Update status
        if self.quantity_received >= self.quantity_ordered:
            self.status = 'RECEIVED'
        else:
            self.status = 'PARTIAL_RECEIVED'
        
        self.save(update_fields=['quantity_received', 'status'])
        
        # Create or update stock item
        stock_item, created = StockItem.objects.get_or_create(
            tenant=self.tenant,
            product=self.product,
            variation=self.variation,
            warehouse=self.purchase_order.delivery_warehouse,
            location=location or self.delivery_location,
            defaults={
                'unit_cost': self.unit_cost,
                'average_cost': self.unit_cost,
                'last_cost': self.unit_cost,
            }
        )
        
        # Receive stock
        stock_item.receive_stock(
            quantity=quantity,
            unit_cost=self.unit_cost,
            reason=f"PO Receipt: {self.purchase_order.po_number}"
        )
        
        # Create batch if batch tracking is enabled
        if self.product.is_batch_tracked and batch_number:
            batch, batch_created = Batch.objects.get_or_create(
                tenant=self.tenant,
                product=self.product,
                batch_number=batch_number,
                defaults={
                    'initial_quantity': quantity,
                    'current_quantity': quantity,
                    'unit_cost': self.unit_cost,
                    'total_cost': quantity * self.unit_cost,
                    'supplier': self.purchase_order.supplier,
                    'purchase_order_number': self.purchase_order.po_number,
                    'expiry_date': expiry_date,
                }
            )
            
            if not batch_created:
                batch.current_quantity += quantity
                batch.total_cost += (quantity * self.unit_cost)
                batch.save(update_fields=['current_quantity', 'total_cost'])
        
        return True, "Quantity received successfully"
    
    # ============================================================================
# STOCK RECEIPTS & RECEIVING
# ============================================================================

class StockReceipt(TenantBaseModel):
    """Stock receipt management for incoming inventory"""
    
    RECEIPT_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Receipt'),
        ('PARTIAL', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    RECEIPT_TYPES = [
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('TRANSFER', 'Transfer Receipt'),
        ('RETURN', 'Customer Return'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('MANUFACTURING', 'Manufacturing Output'),
        ('FOUND_STOCK', 'Found Stock'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    receipt_number = models.CharField(max_length=100, blank=True)
    receipt_type = models.CharField(max_length=20, choices=RECEIPT_TYPES, default='PURCHASE_ORDER')
    
    # References
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='receipts'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='stock_receipts'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_receipts'
    )
    
    # Dates
    receipt_date = models.DateTimeField(default=timezone.now)
    expected_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=RECEIPT_STATUS, default='DRAFT')
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='received_stock_receipts'
    )
    inspected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inspected_stock_receipts'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_stock_receipts'
    )
    
    # Shipping Information
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    delivery_note_number = models.CharField(max_length=100, blank=True)
    packing_slip_number = models.CharField(max_length=100, blank=True)
    
    # Quality Control
    requires_inspection = models.BooleanField(default=False)
    inspection_completed = models.BooleanField(default=False)
    quality_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Inspection'),
            ('PASSED', 'Passed'),
            ('FAILED', 'Failed'),
            ('PARTIAL_PASS', 'Partial Pass'),
        ],
        default='PENDING'
    )
    
    # Financial
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Additional Information
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    damage_report = models.TextField(blank=True)
    
    # Documents
    receipt_documents = models.JSONField(default=list, blank=True)
    photos = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'inventory_stock_receipts'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'receipt_number'], name='unique_tenant_receipt_number'),
        ]
        ordering = ['-receipt_date']
        indexes = [
            models.Index(fields=['tenant', 'status', '-receipt_date']),
            models.Index(fields=['tenant', 'warehouse', 'status']),
            models.Index(fields=['tenant', 'supplier', 'status']),
        ]
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.warehouse.name}"
    
    def clean(self):
        if not self.receipt_number:
            # Auto-generate receipt number
            last_receipt = StockReceipt.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_receipt:
                try:
                    last_num = int(last_receipt.receipt_number.replace('REC', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.receipt_number = f"REC{last_num + 1:06d}"


class StockReceiptItem(TenantBaseModel):
    """Stock receipt line items"""
    
    receipt = models.ForeignKey(
        StockReceipt,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='receipt_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Purchase Order Reference
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Quantities
    quantity_expected = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_accepted = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit & Location
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='receipt_items'
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Batch & Serial Information
    batch_number = models.CharField(max_length=50, blank=True)
    lot_number = models.CharField(max_length=50, blank=True)
    serial_numbers = models.JSONField(default=list, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Quality Information
    quality_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Inspection'),
            ('PASSED', 'Passed'),
            ('FAILED', 'Failed'),
            ('QUARANTINED', 'Quarantined'),
        ],
        default='PENDING'
    )
    rejection_reason = models.TextField(blank=True)
    quality_notes = models.TextField(blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    damage_description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_receipt_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'receipt', 'line_number'],
                name='unique_receipt_line_number'
            ),
        ]
        ordering = ['receipt', 'line_number']
        indexes = [
            models.Index(fields=['tenant', 'receipt']),
            models.Index(fields=['tenant', 'product', 'quality_status']),
        ]
    
    def __str__(self):
        return f"{self.receipt.receipt_number} Line {self.line_number}: {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_received * self.unit_cost
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockReceiptItem.objects.filter(
                receipt=self.receipt
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)


# ============================================================================
# STOCK TRANSFER MANAGEMENT
# ============================================================================

class StockTransfer(TenantBaseModel):
    """Inter-warehouse stock transfers"""
    
    TRANSFER_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('IN_TRANSIT', 'In Transit'),
        ('PARTIAL_RECEIVED', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]
    
    TRANSFER_TYPES = [
        ('STANDARD', 'Standard Transfer'),
        ('EMERGENCY', 'Emergency Transfer'),
        ('REBALANCING', 'Stock Rebalancing'),
        ('RETURN', 'Return Transfer'),
        ('REPAIR', 'Repair Transfer'),
    ]
    
    # Basic Information
    transfer_number = models.CharField(max_length=100, blank=True)
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES, default='STANDARD')
    
    # Locations
    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='transfers_out'
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='transfers_in'
    )
    
    # Dates
    transfer_date = models.DateField(default=date.today)
    required_date = models.DateField()
    shipped_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS, default='DRAFT')
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requested_transfers'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_transfers'
    )
    shipped_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shipped_transfers'
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='received_transfers'
    )
    
    # Shipping Information
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Priority & Reason
    priority = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low'),
            ('NORMAL', 'Normal'),
            ('HIGH', 'High'),
            ('URGENT', 'Urgent'),
        ],
        default='NORMAL'
    )
    reason = models.TextField(blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    
    # Documents
    transfer_documents = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'inventory_stock_transfers'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'transfer_number'], name='unique_tenant_transfer_number'),
        ]
        ordering = ['-transfer_date']
        indexes = [
            models.Index(fields=['tenant', 'status', '-transfer_date']),
            models.Index(fields=['tenant', 'from_warehouse', 'status']),
            models.Index(fields=['tenant', 'to_warehouse', 'status']),
        ]
    
    def __str__(self):
        return f"Transfer {self.transfer_number}: {self.from_warehouse.code} → {self.to_warehouse.code}"
    
    def clean(self):
        if not self.transfer_number:
            # Auto-generate transfer number
            last_transfer = StockTransfer.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_transfer:
                try:
                    last_num = int(last_transfer.transfer_number.replace('TRN', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.transfer_number = f"TRN{last_num + 1:06d}"


class StockTransferItem(TenantBaseModel):
    """Stock transfer line items"""
    
    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='transfer_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='transfer_items'
    )
    
    # Locations
    from_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_items_from'
    )
    to_location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_items_to'
    )
    
    # Quantities
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_shipped = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_damaged = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit & Batch Information
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='transfer_items'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_items'
    )
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('REQUESTED', 'Requested'),
            ('APPROVED', 'Approved'),
            ('PICKED', 'Picked'),
            ('SHIPPED', 'Shipped'),
            ('RECEIVED', 'Received'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='REQUESTED'
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    damage_description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_transfer_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'transfer', 'line_number'],
                name='unique_transfer_line_number'
            ),
        ]
        ordering = ['transfer', 'line_number']
        indexes = [
            models.Index(fields=['tenant', 'transfer']),
            models.Index(fields=['tenant', 'product', 'status']),
        ]
    
    def __str__(self):
        return f"{self.transfer.transfer_number} Line {self.line_number}: {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_requested * self.unit_cost
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockTransferItem.objects.filter(
                transfer=self.transfer
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)


# ============================================================================
# CYCLE COUNTING & PHYSICAL INVENTORY
# ============================================================================

class CycleCount(TenantBaseModel):
    """Cycle counting management"""
    
    COUNT_STATUS = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    COUNT_TYPES = [
        ('CYCLE', 'Cycle Count'),
        ('PHYSICAL', 'Physical Inventory'),
        ('SPOT', 'Spot Count'),
        ('ABC', 'ABC Count'),
        ('LOCATION', 'Location Count'),
    ]
    
    # Basic Information
    count_number = models.CharField(max_length=100, blank=True)
    count_type = models.CharField(max_length=20, choices=COUNT_TYPES, default='CYCLE')
    
    # Scope
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='cycle_counts'
    )
    locations = models.ManyToManyField(
        StockLocation,
        blank=True,
        related_name='cycle_counts'
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='cycle_counts'
    )
    abc_class = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        blank=True
    )
    
    # Dates
    scheduled_date = models.DateField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    cutoff_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=COUNT_STATUS, default='SCHEDULED')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_cycle_counts'
    )
    assigned_to = models.ManyToManyField(
        User,
        blank=True,
        related_name='assigned_cycle_counts'
    )
    supervised_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supervised_cycle_counts'
    )
    
    # Results
    total_items_to_count = models.PositiveIntegerField(default=0)
    items_counted = models.PositiveIntegerField(default=0)
    items_with_variance = models.PositiveIntegerField(default=0)
    total_variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Instructions
    counting_instructions = models.TextField(blank=True)
    variance_tolerance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    require_approval_for_adjustments = models.BooleanField(default=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    freeze_transactions = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'inventory_cycle_counts'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'count_number'], name='unique_tenant_count_number'),
        ]
        ordering = ['-scheduled_date']
        indexes = [
            models.Index(fields=['tenant', 'warehouse', 'status']),
            models.Index(fields=['tenant', 'status', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"Count {self.count_number} - {self.warehouse.name}"
    
    def clean(self):
        if not self.count_number:
            # Auto-generate count number
            last_count = CycleCount.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_count:
                try:
                    last_num = int(last_count.count_number.replace('CNT', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.count_number = f"CNT{last_num + 1:06d}"


class CycleCountItem(TenantBaseModel):
    """Cycle count line items"""
    
    VARIANCE_STATUS = [
        ('NO_VARIANCE', 'No Variance'),
        ('MINOR_VARIANCE', 'Minor Variance'),
        ('MAJOR_VARIANCE', 'Major Variance'),
        ('PENDING_RECOUNT', 'Pending Recount'),
        ('APPROVED', 'Approved'),
        ('ADJUSTED', 'Adjusted'),
    ]
    
    cycle_count = models.ForeignKey(
        CycleCount,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Product & Location
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='cycle_count_items'
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.CASCADE,
        related_name='cycle_count_items'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cycle_count_items'
    )
    
    # Count Information
    system_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    variance_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    variance_percentage = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    
    # Cost Impact
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Count Details
    counted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='counted_items'
    )
    counted_at = models.DateTimeField(null=True, blank=True)
    recount_required = models.BooleanField(default=False)
    recount_completed = models.BooleanField(default=False)
    
    # Status & Approval
    variance_status = models.CharField(max_length=20, choices=VARIANCE_STATUS, default='NO_VARIANCE')
    adjustment_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_count_items'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    variance_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_cycle_count_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'cycle_count', 'stock_item', 'location'],
                name='unique_count_stock_item'
            ),
        ]
        ordering = ['cycle_count', 'location', 'stock_item']
        indexes = [
            models.Index(fields=['tenant', 'cycle_count']),
            models.Index(fields=['tenant', 'variance_status']),
            models.Index(fields=['tenant', 'counted_by']),
        ]
    
    def __str__(self):
        return f"{self.cycle_count.count_number}: {self.stock_item}"
    
    def calculate_variance(self):
        """Calculate variance when counted quantity is entered"""
        if self.counted_quantity is not None:
            self.variance_quantity = self.counted_quantity - self.system_quantity
            
            # Calculate percentage variance
            if self.system_quantity != 0:
                self.variance_percentage = (self.variance_quantity / self.system_quantity * 100).quantize(Decimal('0.001'))
            else:
                self.variance_percentage = Decimal('100') if self.counted_quantity > 0 else Decimal('0')
            
            # Calculate value variance
            self.variance_value = self.variance_quantity * self.unit_cost
            
            # Determine variance status
            tolerance = self.cycle_count.variance_tolerance_percentage
            abs_variance_percentage = abs(self.variance_percentage)
            
            if abs_variance_percentage == 0:
                self.variance_status = 'NO_VARIANCE'
            elif abs_variance_percentage <= tolerance:
                self.variance_status = 'MINOR_VARIANCE'
            else:
                self.variance_status = 'MAJOR_VARIANCE'
                if abs_variance_percentage >= tolerance * 2:
                    self.recount_required = True
            
            # Set count time
            if not self.counted_at:
                self.counted_at = timezone.now()
        
        self.save(update_fields=[
            'variance_quantity', 'variance_percentage', 'variance_value',
            'variance_status', 'recount_required', 'counted_at'
        ])


# ============================================================================
# STOCK ADJUSTMENT & WRITE-OFF
# ============================================================================

class StockAdjustment(TenantBaseModel):
    """Stock adjustments and write-offs"""
    
    ADJUSTMENT_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]
    
    ADJUSTMENT_TYPES = [
        ('INCREASE', 'Stock Increase'),
        ('DECREASE', 'Stock Decrease'),
        ('WRITE_OFF', 'Write Off'),
        ('WRITE_ON', 'Write On'),
        ('REVALUATION', 'Cost Revaluation'),
        ('CORRECTION', 'Correction'),
        ('DAMAGE', 'Damage'),
        ('THEFT', 'Theft/Loss'),
        ('EXPIRY', 'Expiry'),
        ('OBSOLETE', 'Obsolete Stock'),
        ('FOUND', 'Found Stock'),
        ('SAMPLE', 'Sample/Demo'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    adjustment_number = models.CharField(max_length=100, blank=True)
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    
    # References
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_adjustments'
    )
    cycle_count = models.ForeignKey(
        CycleCount,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustments'
    )
    
    # Dates
    adjustment_date = models.DateField(default=date.today)
    effective_date = models.DateField(default=date.today)
    posting_date = models.DateField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=ADJUSTMENT_STATUS, default='DRAFT')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_adjustments'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_adjustments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='posted_adjustments'
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    
    # Financial Impact
    total_quantity_impact = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_value_impact = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Reason & Documentation
    reason = models.TextField()
    supporting_documents = models.JSONField(default=list, blank=True)
    approval_justification = models.TextField(blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'inventory_stock_adjustments'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'adjustment_number'], name='unique_tenant_adjustment_number'),
        ]
        ordering = ['-adjustment_date']
        indexes = [
            models.Index(fields=['tenant', 'warehouse', 'status']),
            models.Index(fields=['tenant', 'adjustment_type', 'status']),
            models.Index(fields=['tenant', 'status', 'adjustment_date']),
        ]
    
    def __str__(self):
        return f"Adjustment {self.adjustment_number} - {self.get_adjustment_type_display()}"
    
    def clean(self):
        if not self.adjustment_number:
            # Auto-generate adjustment number
            last_adjustment = StockAdjustment.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_adjustment:
                try:
                    last_num = int(last_adjustment.adjustment_number.replace('ADJ', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.adjustment_number = f"ADJ{last_num + 1:06d}"


class StockAdjustmentItem(TenantBaseModel):
    """Stock adjustment line items"""
    
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product & Location
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='adjustment_items'
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustment_items'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustment_items'
    )
    
    # Quantity Changes
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_adjustment = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Cost Information
    unit_cost_before = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost_after = models.DecimalField(max_digits=12, decimal_places=2)
    value_impact = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Reason & Documentation
    reason = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_adjustment_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'adjustment', 'line_number'],
                name='unique_adjustment_line_number'
            ),
        ]
        ordering = ['adjustment', 'line_number']
        indexes = [
            models.Index(fields=['tenant', 'adjustment']),
            models.Index(fields=['tenant', 'stock_item']),
        ]
    
    def __str__(self):
        return f"{self.adjustment.adjustment_number} Line {self.line_number}: {self.stock_item}"
    
    def save(self, *args, **kwargs):
        # Calculate quantity after
        self.quantity_after = self.quantity_before + self.quantity_adjustment
        
        # Calculate value impact
        if self.unit_cost_after != self.unit_cost_before:
            # Cost revaluation impact
            self.value_impact = (self.quantity_after * self.unit_cost_after) - (self.quantity_before * self.unit_cost_before)
        else:
            # Quantity adjustment impact
            self.value_impact = self.quantity_adjustment * self.unit_cost_after
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockAdjustmentItem.objects.filter(
                adjustment=self.adjustment
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)


# ============================================================================
# INVENTORY RESERVATION SYSTEM
# ============================================================================

class StockReservation(TenantBaseModel):
    """Advanced stock reservation management"""
    
    RESERVATION_STATUS = [
        ('ACTIVE', 'Active'),
        ('PARTIAL_FULFILLED', 'Partially Fulfilled'),
        ('FULFILLED', 'Fulfilled'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    RESERVATION_TYPES = [
        ('SALES_ORDER', 'Sales Order'),
        ('WORK_ORDER', 'Work Order'),
        ('TRANSFER_ORDER', 'Transfer Order'),
        ('SAMPLE', 'Sample Request'),
        ('QUALITY_HOLD', 'Quality Hold'),
        ('MANUAL', 'Manual Reservation'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    reservation_number = models.CharField(max_length=100, blank=True)
    reservation_type = models.CharField(max_length=20, choices=RESERVATION_TYPES)
    
    # References
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Customer/Entity Information
    reserved_for_name = models.CharField(max_length=200, blank=True)
    reserved_for_email = models.EmailField(blank=True)
    reserved_for_phone = models.CharField(max_length=20, blank=True)
    
    # Dates
    reservation_date = models.DateTimeField(default=timezone.now)
    required_date = models.DateTimeField()
    expiry_date = models.DateTimeField()
    fulfilled_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=RESERVATION_STATUS, default='ACTIVE')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_reservations'
    )
    fulfilled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fulfilled_reservations'
    )
    
    # Priority
    priority = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low'),
            ('NORMAL', 'Normal'),
            ('HIGH', 'High'),
            ('URGENT', 'Urgent'),
        ],
        default='NORMAL'
    )
    
    # Auto-release settings
    auto_release_on_expiry = models.BooleanField(default=True)
    send_expiry_notifications = models.BooleanField(default=True)
    
    # Additional Information
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_reservations'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'reservation_number'], name='unique_tenant_reservation_number'),
        ]
        ordering = ['-reservation_date']
        indexes = [
            models.Index(fields=['tenant', 'status', 'expiry_date']),
            models.Index(fields=['tenant', 'reservation_type', 'status']),
            models.Index(fields=['tenant', 'reference_type', 'reference_id']),
        ]
    
    def __str__(self):
        return f"Reservation {self.reservation_number} - {self.reserved_for_name}"
    
    def clean(self):
        if not self.reservation_number:
            # Auto-generate reservation number
            last_reservation = StockReservation.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_reservation:
                try:
                    last_num = int(last_reservation.reservation_number.replace('RSV', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.reservation_number = f"RSV{last_num + 1:06d}"


class StockReservationItem(TenantBaseModel):
    """Stock reservation line items"""
    
    reservation = models.ForeignKey(
        StockReservation,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reservation_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reservation_items'
    )
    
    # Stock Item & Location
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='reservation_items'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='reservation_items'
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reservation_items'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reservation_items'
    )
    
    # Quantities
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_fulfilled = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_pending = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='reservation_items'
    )
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('RESERVED', 'Reserved'),
            ('PARTIAL_FULFILLED', 'Partially Fulfilled'),
            ('FULFILLED', 'Fulfilled'),
            ('EXPIRED', 'Expired'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='RESERVED'
    )
    
    # Dates
    reserved_at = models.DateTimeField(default=timezone.now)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_stock_reservation_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'reservation', 'line_number'],
                name='unique_reservation_line_number'
            ),
        ]
        ordering = ['reservation', 'line_number']
        indexes = [
            models.Index(fields=['tenant', 'reservation']),
            models.Index(fields=['tenant', 'stock_item', 'status']),
            models.Index(fields=['tenant', 'product', 'status']),
        ]
    
    def __str__(self):
        return f"{self.reservation.reservation_number} Line {self.line_number}: {self.product.name}"
    
    @property
    def pending_quantity(self):
        """Calculate pending quantity"""
        return self.quantity_reserved - self.quantity_fulfilled
    
    def save(self, *args, **kwargs):
        # Calculate pending quantity
        self.quantity_pending = self.quantity_reserved - self.quantity_fulfilled
        
        # Calculate total value
        self.total_value = self.quantity_reserved * self.unit_cost
        
        # Update status based on fulfillment
        if self.quantity_fulfilled >= self.quantity_reserved:
            self.status = 'FULFILLED'
            if not self.fulfilled_at:
                self.fulfilled_at = timezone.now()
        elif self.quantity_fulfilled > 0:
            self.status = 'PARTIAL_FULFILLED'
        else:
            self.status = 'RESERVED'
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockReservationItem.objects.filter(
                reservation=self.reservation
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)


# ============================================================================
# INVENTORY ALERTS & NOTIFICATIONS
# ============================================================================

class InventoryAlert(TenantBaseModel):
    """Inventory alerts and notifications system"""
    
    ALERT_TYPES = [
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('REORDER_POINT', 'Reorder Point Reached'),
        ('EXPIRY_WARNING', 'Expiry Warning'),
        ('EXPIRED_STOCK', 'Expired Stock'),
        ('NEGATIVE_STOCK', 'Negative Stock'),
        ('SLOW_MOVING', 'Slow Moving Stock'),
        ('DEAD_STOCK', 'Dead Stock'),
        ('VARIANCE_ALERT', 'Stock Variance'),
        ('QUALITY_ISSUE', 'Quality Issue'),
        ('CYCLE_COUNT_DUE', 'Cycle Count Due'),
        ('TRANSFER_OVERDUE', 'Transfer Overdue'),
        ('RESERVATION_EXPIRY', 'Reservation Expiring'),
        ('PRICE_CHANGE', 'Price Change'),
        ('COST_VARIANCE', 'Cost Variance'),
        ('SYSTEM_ERROR', 'System Error'),
        ('OTHER', 'Other'),
    ]
    
    ALERT_SEVERITY = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    ALERT_STATUS = [
        ('ACTIVE', 'Active'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
        ('SNOOZED', 'Snoozed'),
    ]
    
    # Basic Information
    alert_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=ALERT_SEVERITY, default='MEDIUM')
    
    # Alert Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    # References
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    
    # Generic foreign key for flexible references
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Status & Timing
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Personnel
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acknowledged_alerts'
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_alerts'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_alerts'
    )
    
    # Notification Settings
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    notification_count = models.PositiveIntegerField(default=0)
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    
    # Auto-resolution
    auto_resolve = models.BooleanField(default=False)
    resolution_criteria = models.JSONField(default=dict, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'inventory_alerts'
        ordering = ['-created_at', '-severity']
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
            models.Index(fields=['tenant', 'alert_type', 'status']),
            models.Index(fields=['tenant', 'severity', 'status']),
            models.Index(fields=['tenant', 'product', 'status']),
            models.Index(fields=['tenant', 'warehouse', 'status']),
            models.Index(fields=['tenant', 'assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.title}"
    
    def acknowledge(self, user):
        """Acknowledge the alert"""
        if self.status == 'ACTIVE':
            self.status = 'ACKNOWLEDGED'
            self.acknowledged_by = user
            self.acknowledged_at = timezone.now()
            self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
            return True
        return False
    
    def resolve(self, user, notes=''):
        """Resolve the alert"""
        if self.status in ['ACTIVE', 'ACKNOWLEDGED']:
            self.status = 'RESOLVED'
            self.resolved_by = user
            self.resolved_at = timezone.now()
            if notes:
                self.notes = f"{notes}\n{self.notes}" if self.notes else notes
            self.save(update_fields=['status', 'resolved_by', 'resolved_at', 'notes'])
            return True
        return False
    
    def snooze(self, until_datetime):
        """Snooze the alert until specified time"""
        self.status = 'SNOOZED'
        self.snoozed_until = until_datetime
        self.save(update_fields=['status', 'snoozed_until'])
    
    @property
    def is_active(self):
        """Check if alert is currently active"""
        if self.status == 'SNOOZED' and self.snoozed_until:
            if timezone.now() > self.snoozed_until:
                self.status = 'ACTIVE'
                self.snoozed_until = None
                self.save(update_fields=['status', 'snoozed_until'])
                return True
        return self.status == 'ACTIVE'
    
    @property
    def is_expired(self):
        """Check if alert has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


# ============================================================================
# INVENTORY REPORTS & ANALYTICS
# ============================================================================

class InventoryReport(TenantBaseModel):
    """Inventory reports and analytics tracking"""
    
    REPORT_TYPES = [
        ('STOCK_SUMMARY', 'Stock Summary'),
        ('STOCK_VALUATION', 'Stock Valuation'),
        ('ABC_ANALYSIS', 'ABC Analysis'),
        ('VELOCITY_ANALYSIS', 'Velocity Analysis'),
        ('AGING_REPORT', 'Aging Report'),
        ('MOVEMENT_REPORT', 'Movement Report'),
        ('REORDER_REPORT', 'Reorder Report'),
        ('VARIANCE_REPORT', 'Variance Report'),
        ('CYCLE_COUNT_REPORT', 'Cycle Count Report'),
        ('EXPIRY_REPORT', 'Expiry Report'),
        ('DEAD_STOCK_REPORT', 'Dead Stock Report'),
        ('PROFITABILITY_REPORT', 'Profitability Report'),
        ('SUPPLIER_PERFORMANCE', 'Supplier Performance'),
        ('CUSTOM_REPORT', 'Custom Report'),
    ]
    
    REPORT_STATUS = [
        ('GENERATING', 'Generating'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('EXPIRED', 'Expired'),
    ]
    
    # Basic Information
    report_name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Report Parameters
    parameters = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)
    
    # Scope
    warehouses = models.ManyToManyField(
        Warehouse,
        blank=True,
        related_name='reports'
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='reports'
    )
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='reports'
    )
    
    # Generation Info
    status = models.CharField(max_length=20, choices=REPORT_STATUS, default='GENERATING')
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_reports'
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Report Data
    data = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_url = models.URLField(blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    
    # Sharing & Access
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name='shared_reports'
    )
    download_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    
    # Scheduling (for recurring reports)
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('YEARLY', 'Yearly'),
        ],
        blank=True
    )
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'inventory_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['tenant', 'report_type', 'status']),
            models.Index(fields=['tenant', 'generated_by', '-generated_at']),
            models.Index(fields=['tenant', 'is_scheduled', 'next_run']),
        ]
    
    def __str__(self):
        return f"{self.report_name} ({self.get_report_type_display()})"


# ============================================================================
# VENDOR MANAGED INVENTORY (VMI)
# ============================================================================

class VendorManagedInventory(TenantBaseModel):
    """Vendor Managed Inventory agreements and tracking"""
    
    VMI_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDED', 'Suspended'),
        ('TERMINATED', 'Terminated'),
    ]
    
    # Agreement Information
    vmi_number = models.CharField(max_length=100, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='vmi_agreements'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='vmi_agreements'
    )
    
    # Agreement Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=VMI_STATUS, default='ACTIVE')
    
    # Terms & Conditions
    min_stock_days = models.IntegerField(default=7)
    max_stock_days = models.IntegerField(default=30)
    reorder_frequency_days = models.IntegerField(default=7)
    service_level_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=95)
    
    # Financial Terms
    consignment_stock = models.BooleanField(default=False)
    payment_terms_days = models.IntegerField(default=30)
    price_protection_days = models.IntegerField(default=30)
    
    # Performance Tracking
    current_service_level = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stockout_incidents = models.IntegerField(default=0)
    excess_stock_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Contact Information
    supplier_contact = models.CharField(max_length=200, blank=True)
    internal_contact = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_vmi_agreements'
    )
    
    # Additional Information
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_vendor_managed_inventory'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'vmi_number'], name='unique_tenant_vmi_number'),
        ]
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant', 'supplier', 'status']),
            models.Index(fields=['tenant', 'warehouse', 'status']),
        ]
    
    def __str__(self):
        return f"VMI-{self.vmi_number}: {self.supplier.name} → {self.warehouse.name}"
    
    def clean(self):
        if not self.vmi_number:
            # Auto-generate VMI number
            last_vmi = VendorManagedInventory.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_vmi:
                try:
                    last_num = int(last_vmi.vmi_number.replace('VMI', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.vmi_number = f"VMI{last_num + 1:06d}"


class VMIProduct(TenantBaseModel):
    """Products under VMI agreement"""
    
    vmi_agreement = models.ForeignKey(
        VendorManagedInventory,
        on_delete=models.CASCADE,
        related_name='products'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='vmi_products'
    )
    
    # Stock Levels
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    max_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    target_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Demand Information
    average_daily_consumption = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    lead_time_days = models.IntegerField(default=7)
    safety_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Pricing
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2)
    price_valid_until = models.DateField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_replenishment_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    
    # Performance Metrics
    stockout_count = models.IntegerField(default=0)
    excess_stock_days = models.IntegerField(default=0)
    service_level_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    
    class Meta:
        db_table = 'inventory_vmi_products'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'vmi_agreement', 'product'], name='unique_vmi_product'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'vmi_agreement', 'is_active']),
            models.Index(fields=['tenant', 'product', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.vmi_agreement.vmi_number}: {self.product.name}"


# Add this to the end of models.py to ensure all models are properly registered
__all__ = [
    'InventorySettings', 'UnitOfMeasure', 'Department', 'Category', 'SubCategory',
    'Brand', 'Supplier', 'SupplierContact', 'Warehouse', 'StockLocation',
    'ProductAttribute', 'AttributeValue', 'Product', 'ProductAttributeValue',
    'ProductVariation', 'ProductSupplier', 'Batch', 'SerialNumber', 'StockItem',
    'StockMovement', 'StockValuationLayer', 'PurchaseOrder', 'PurchaseOrderItem',
    'StockReceipt', 'StockReceiptItem', 'StockTransfer', 'StockTransferItem',
    'CycleCount', 'CycleCountItem', 'StockAdjustment', 'StockAdjustmentItem',
    'StockReservation', 'StockReservationItem', 'InventoryAlert', 'InventoryReport',
    'VendorManagedInventory', 'VMIProduct'
]
