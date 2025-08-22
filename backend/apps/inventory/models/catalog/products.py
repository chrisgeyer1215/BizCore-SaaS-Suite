"""
Product catalog and management models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal
from datetime import date

from apps.inventory.models.abstract.auditable import AuditableMixin

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from ..abstract.base import ActivatableMixin
from ...managers.base import InventoryManager
from ...managers.product import ProductManager

class Product(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Comprehensive product management system
    """
    
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
    
    ABC_CLASSIFICATIONS = [
        ('A', 'Class A - High Value'),
        ('B', 'Class B - Medium Value'),
        ('C', 'Class C - Low Value'),
    ]
    
    XYZ_CLASSIFICATIONS = [
        ('X', 'Class X - Stable Demand'),
        ('Y', 'Class Y - Variable Demand'),
        ('Z', 'Class Z - Irregular Demand'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200, db_index=True)
    sku = models.CharField(max_length=50, db_index=True)
    internal_code = models.CharField(max_length=50, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    part_number = models.CharField(max_length=100, blank=True)
    
    # Identification Codes
    barcode = models.CharField(max_length=50, blank=True, db_index=True)
    upc = models.CharField(max_length=20, blank=True)
    ean = models.CharField(max_length=20, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    qr_code = models.CharField(max_length=100, blank=True)
    rfid_tag = models.CharField(max_length=100, blank=True)
    
    # Categorization
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='SIMPLE')
    department = models.ForeignKey(
        'core.Department',
        on_delete=models.PROTECT,
        related_name='products'
    )
    category = models.ForeignKey(
        'core.Category',
        on_delete=models.PROTECT,
        related_name='products'
    )
    subcategory = models.ForeignKey(
        'core.SubCategory',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products'
    )
    brand = models.ForeignKey(
        'core.Brand',
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
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='products'
    )
    
    # Physical Properties
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    weight_unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products_by_weight'
    )
    length = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    volume = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    dimension_unit = models.ForeignKey(
        'core.UnitOfMeasure',
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
    
    # Tax & Compliance
    tax_category = models.CharField(max_length=50, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True)
    commodity_code = models.CharField(max_length=20, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    
    # Suppliers
    preferred_supplier = models.ForeignKey(
        'suppliers.Supplier',
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
    
    # Packaging Information
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
    
    # Important Dates
    launch_date = models.DateField(null=True, blank=True)
    discontinue_date = models.DateField(null=True, blank=True)
    last_sold_date = models.DateTimeField(null=True, blank=True)
    last_purchased_date = models.DateTimeField(null=True, blank=True)
    
    # Analytics & Performance
    sales_velocity = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    abc_classification = models.CharField(max_length=1, choices=ABC_CLASSIFICATIONS, blank=True)
    xyz_classification = models.CharField(max_length=1, choices=XYZ_CLASSIFICATIONS, blank=True)
    
    # Custom Fields & Tags
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    internal_notes = models.TextField(blank=True)
    
    objects = ProductManager()
    class Meta:
        db_table = 'inventory_products'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'sku'], 
                name='unique_tenant_product_sku'
            ),
            models.UniqueConstraint(
                fields=['tenant_id', 'barcode'],
                condition=models.Q(barcode__isnull=False) & ~models.Q(barcode=''),
                name='unique_tenant_product_barcode'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'sku']),
            models.Index(fields=['tenant_id', 'barcode']),
            models.Index(fields=['tenant_id', 'status', 'is_saleable']),
            models.Index(fields=['tenant_id', 'category', 'status']),
            models.Index(fields=['tenant_id', 'brand', 'status']),
            models.Index(fields=['tenant_id', 'product_type']),
            models.Index(fields=['tenant_id', 'abc_classification']),
            models.Index(fields=['tenant_id', 'name']),  # For search
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.name}"
    
    @property
    def margin_percentage(self):
        """Gross margin percentage"""
        if self.selling_price and self.cost_price and self.selling_price > 0:
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
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            product=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        return sum(item.quantity_on_hand for item in stock_items)
    
    @property
    def available_stock(self):
        """Available stock across all warehouses"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            product=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        return sum(item.quantity_available for item in stock_items)
    
    @property
    def reserved_stock(self):
        """Reserved stock across all warehouses"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            product=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        return sum(item.quantity_reserved for item in stock_items)
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Auto-generate SKU if not provided
        if not self.sku:
            last_product = Product.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_product and last_product.sku:
                try:
                    last_num = int(last_product.sku.replace('PRD', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.sku = f"PRD{last_num + 1:06d}"
    
    def calculate_total_volume(self):
        """Calculate total volume including packaging"""
        if self.length and self.width and self.height:
            return self.length * self.width * self.height
        return self.volume or Decimal('0')
    
    def get_supplier_products(self):
        """Get all supplier relationships for this product"""
        from ..suppliers.relationships import ProductSupplier
        
        return ProductSupplier.objects.filter(
            product=self,
            tenant_id=self.tenant_id,
            is_active=True
        )