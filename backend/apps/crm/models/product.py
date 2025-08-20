# ============================================================================
# backend/apps/crm/models/product.py - Product & Pricing Models
# ============================================================================

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class ProductCategory(TenantBaseModel, SoftDeleteMixin):
    """Hierarchical product categorization system"""
    
    # Category Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    level = models.PositiveSmallIntegerField(default=0)
    full_path = models.CharField(max_length=500, blank=True)
    
    # Display Settings
    sort_order = models.IntegerField(default=0)
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=7, blank=True)  # Hex color
    
    # SEO and Marketing
    slug = models.SlugField(max_length=100, blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    
    # Business Rules
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    default_markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    # Settings
    is_visible = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['level', 'sort_order', 'name']
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_product_category_code'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'slug'],
                name='unique_tenant_product_category_slug'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'parent', 'is_active']),
            models.Index(fields=['tenant', 'level']),
            models.Index(fields=['tenant', 'is_visible']),
        ]
        
    def __str__(self):
        return self.full_path or self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate code if not provided
        if not self.code:
            self.code = self.name.upper().replace(' ', '_')[:50]
        
        # Auto-generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        
        # Calculate level and full path
        if self.parent:
            self.level = self.parent.level + 1
            self.full_path = f"{self.parent.full_path} > {self.name}" if self.parent.full_path else f"{self.parent.name} > {self.name}"
        else:
            self.level = 0
            self.full_path = self.name
        
        super().save(*args, **kwargs)
    
    def get_descendants(self, include_self=False):
        """Get all descendant categories"""
        descendants = ProductCategory.objects.filter(
            tenant=self.tenant,
            full_path__startswith=self.full_path,
            is_active=True
        )
        
        if not include_self:
            descendants = descendants.exclude(pk=self.pk)
        
        return descendants
    
    def get_ancestors(self, include_self=False):
        """Get all ancestor categories"""
        if not self.parent:
            return ProductCategory.objects.none()
        
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current.pk)
            current = current.parent
        
        queryset = ProductCategory.objects.filter(
            tenant=self.tenant,
            pk__in=ancestors,
            is_active=True
        )
        
        if include_self:
            queryset = queryset | ProductCategory.objects.filter(pk=self.pk)
        
        return queryset


class Product(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive product/service definition"""
    
    PRODUCT_TYPES = [
        ('PHYSICAL', 'Physical Product'),
        ('DIGITAL', 'Digital Product'),
        ('SERVICE', 'Service'),
        ('SUBSCRIPTION', 'Subscription'),
        ('BUNDLE', 'Product Bundle'),
        ('RENTAL', 'Rental Product'),
        ('LICENSE', 'License'),
        ('CONSULTATION', 'Consultation'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('DISCONTINUED', 'Discontinued'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='PHYSICAL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Categorization
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    
    # Pricing Information
    base_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Tax Information
    is_taxable = models.BooleanField(default=True)
    tax_category = models.CharField(max_length=100, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Sales Information
    sales_account = models.CharField(max_length=100, blank=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    discount_eligible = models.BooleanField(default=True)
    
    # Physical Properties
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    weight_unit = models.CharField(
        max_length=10,
        choices=[('g', 'Grams'), ('kg', 'Kilograms'), ('lb', 'Pounds'), ('oz', 'Ounces')],
        default='kg'
    )
    dimensions = models.JSONField(default=dict, blank=True)  # {length, width, height, unit}
    
    # Digital Properties
    download_url = models.URLField(blank=True)
    license_type = models.CharField(max_length=100, blank=True)
    usage_restrictions = models.TextField(blank=True)
    
    # Service Properties
    service_duration_minutes = models.IntegerField(null=True, blank=True)
    requires_scheduling = models.BooleanField(default=False)
    service_location = models.CharField(
        max_length=20,
        choices=[
            ('ONSITE', 'On-site'),
            ('REMOTE', 'Remote'),
            ('OFFICE', 'At Office'),
            ('FLEXIBLE', 'Flexible'),
        ],
        blank=True
    )
    
    # Subscription Properties
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
            ('WEEKLY', 'Weekly'),
            ('DAILY', 'Daily'),
        ],
        blank=True
    )
    trial_period_days = models.IntegerField(null=True, blank=True)
    auto_renewal = models.BooleanField(default=True)
    
    # Inventory Integration
    track_inventory = models.BooleanField(default=True)
    current_stock = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    reorder_level = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True
    )
    reorder_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Media and Documentation
    primary_image = models.URLField(blank=True)
    gallery_images = models.JSONField(default=list, blank=True)
    brochure_url = models.URLField(blank=True)
    manual_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    
    # SEO and Marketing
    slug = models.SlugField(max_length=255, blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    
    # Analytics
    view_count = models.IntegerField(default=0)
    sales_count = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Custom Fields Support
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Approval Workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_products'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Lifecycle Dates
    launch_date = models.DateField(null=True, blank=True)
    discontinue_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_product_code'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'slug'],
                name='unique_tenant_product_slug'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'is_active']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'product_type']),
            models.Index(fields=['tenant', 'track_inventory']),
        ]
        
    def __str__(self):
        return f'{self.code} - {self.name}'
    
    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        
        super().save(*args, **kwargs)
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.base_price > 0 and self.cost_price > 0:
            profit = self.base_price - self.cost_price
            return (profit / self.base_price) * 100
        return Decimal('0.00')
    
    @property
    def markup_percentage(self):
        """Calculate markup percentage"""
        if self.cost_price > 0:
            markup = self.base_price - self.cost_price
            return (markup / self.cost_price) * 100
        return Decimal('0.00')
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        if not self.track_inventory:
            return True
        return self.current_stock > 0
    
    @property
    def needs_reorder(self):
        """Check if product needs reordering"""
        if not self.track_inventory or not self.reorder_level:
            return False
        return self.current_stock <= self.reorder_level
    
    def get_price_for_quantity(self, quantity):
        """Get price for specific quantity (with volume discounts)"""
        # This can be extended to support volume pricing
        return self.base_price * quantity
    
    def update_stock(self, quantity_change, reason=''):
        """Update stock levels"""
        if self.track_inventory:
            self.current_stock += quantity_change
            self.save(update_fields=['current_stock'])
            
            # Log stock movement if inventory app is available
            try:
                from apps.inventory.models import StockMovement
                StockMovement.objects.create(
                    tenant=self.tenant,
                    product=self,
                    movement_type='ADJUSTMENT',
                    quantity=quantity_change,
                    reason=reason
                )
            except ImportError:
                pass


class PricingModel(TenantBaseModel, SoftDeleteMixin):
    """Flexible pricing models for products"""
    
    PRICING_TYPES = [
        ('FIXED', 'Fixed Price'),
        ('TIERED', 'Tiered Pricing'),
        ('VOLUME', 'Volume Discount'),
        ('USAGE', 'Usage-based'),
        ('DYNAMIC', 'Dynamic Pricing'),
        ('AUCTION', 'Auction'),
        ('NEGOTIABLE', 'Negotiable'),
        ('CONTRACT', 'Contract Pricing'),
    ]
    
    # Pricing Model Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPES, default='FIXED')
    
    # Associated Product
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='pricing_models'
    )
    
    # Pricing Rules (flexible JSON structure)
    pricing_rules = models.JSONField(default=dict)
    
    # Validity Period
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Customer Targeting
    customer_segments = models.JSONField(default=list, blank=True)
    geographic_regions = models.JSONField(default=list, blank=True)
    minimum_order_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Approval and Status
    is_active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_pricing_models'
    )
    
    # Priority for multiple pricing models
    priority = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['product', 'priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['tenant', 'pricing_type']),
            models.Index(fields=['tenant', 'valid_from', 'valid_until']),
        ]
        
    def __str__(self):
        return f'{self.product.name} - {self.name}'
    
    def is_valid_now(self):
        """Check if pricing model is currently valid"""
        now = timezone.now()
        if self.valid_until:
            return self.valid_from <= now <= self.valid_until
        return self.valid_from <= now
    
    def calculate_price(self, quantity=1, customer=None, context=None):
        """Calculate price based on pricing model"""
        if not self.is_valid_now() or not self.is_active:
            return None
        
        if self.pricing_type == 'FIXED':
            return self.product.base_price * quantity
        
        elif self.pricing_type == 'TIERED':
            # Implement tiered pricing logic
            tiers = self.pricing_rules.get('tiers', [])
            for tier in sorted(tiers, key=lambda x: x.get('min_quantity', 0)):
                if quantity >= tier.get('min_quantity', 0):
                    unit_price = Decimal(str(tier.get('price', self.product.base_price)))
                    return unit_price * quantity
        
        elif self.pricing_type == 'VOLUME':
            # Implement volume discount logic
            base_price = self.product.base_price
            discounts = self.pricing_rules.get('volume_discounts', [])
            
            for discount in sorted(discounts, key=lambda x: x.get('min_quantity', 0), reverse=True):
                if quantity >= discount.get('min_quantity', 0):
                    discount_rate = Decimal(str(discount.get('discount_rate', 0))) / 100
                    discounted_price = base_price * (1 - discount_rate)
                    return discounted_price * quantity
            
            return base_price * quantity
        
        # Default to base price
        return self.product.base_price * quantity


class ProductBundle(TenantBaseModel, SoftDeleteMixin):
    """Product bundles for cross-selling and packages"""
    
    BUNDLE_TYPES = [
        ('FIXED', 'Fixed Bundle'),
        ('FLEXIBLE', 'Flexible Bundle'),
        ('OPTIONAL', 'Optional Add-ons'),
        ('REQUIRED', 'Required Components'),
    ]
    
    # Bundle Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPES, default='FIXED')
    
    # Pricing
    bundle_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Marketing
    promotional_text = models.CharField(max_length=500, blank=True)
    image_url = models.URLField(blank=True)
    
    # Sales Tracking
    sales_count = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'bundle_type']),
            models.Index(fields=['tenant', 'valid_from', 'valid_until']),
        ]
        
    def __str__(self):
        return self.name
    
    @property
    def individual_total(self):
        """Calculate total price of individual products"""
        total = Decimal('0.00')
        for item in self.bundle_items.filter(is_active=True):
            total += item.product.base_price * item.quantity
        return total
    
    @property
    def bundle_savings(self):
        """Calculate savings from bundle pricing"""
        individual_total = self.individual_total
        effective_price = self.get_effective_price()
        
        if individual_total > 0:
            return individual_total - effective_price
        return Decimal('0.00')
    
    @property
    def savings_percentage(self):
        """Calculate savings percentage"""
        individual_total = self.individual_total
        savings = self.bundle_savings
        
        if individual_total > 0:
            return (savings / individual_total) * 100
        return Decimal('0.00')
    
    def get_effective_price(self):
        """Get the effective bundle price"""
        if self.bundle_price:
            return self.bundle_price
        
        individual_total = self.individual_total
        if self.discount_percentage > 0:
            discount_amount = individual_total * (self.discount_percentage / 100)
            return individual_total - discount_amount
        
        return individual_total
    
    def is_valid_now(self):
        """Check if bundle is currently valid"""
        now = timezone.now()
        if self.valid_until:
            return self.valid_from <= now <= self.valid_until
        return self.valid_from <= now


class ProductBundleItem(TenantBaseModel):
    """Individual products within a bundle"""
    
    bundle = models.ForeignKey(
        ProductBundle,
        on_delete=models.CASCADE,
        related_name='bundle_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='bundle_memberships'
    )
    
    # Quantity in Bundle
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=Decimal('1.0000'),
        validators=[MinValueValidator(0)]
    )
    
    # Optional Overrides
    custom_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Flexibility
    is_required = models.BooleanField(default=True)
    is_substitutable = models.BooleanField(default=False)
    substitute_products = models.ManyToManyField(
        Product,
        related_name='substitute_for_bundles',
        blank=True
    )
    
    # Display
    sort_order = models.IntegerField(default=0)
    description_override = models.TextField(blank=True)
    
    class Meta:
        ordering = ['bundle', 'sort_order', 'product__name']
        constraints = [
            models.UniqueConstraint(
                fields=['bundle', 'product'],
                name='unique_bundle_product'
            ),
        ]
        
    def __str__(self):
        return f'{self.bundle.name} - {self.product.name} (x{self.quantity})'
    
    @property
    def effective_price(self):
        """Get effective price for this bundle item"""
        if self.custom_price:
            return self.custom_price
        return self.product.base_price
    
    @property
    def total_price(self):
        """Get total price for this bundle item"""
        return self.effective_price * self.quantity


class ProductVariant(TenantBaseModel, SoftDeleteMixin):
    """Product variations (size, color, etc.)"""
    
    # Parent Product
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    
    # Variant Information
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Variation Attributes
    attributes = models.JSONField(default=dict)  # {color: 'red', size: 'large'}
    
    # Pricing
    price_adjustment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    cost_adjustment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Inventory
    stock_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    
    # Physical Properties
    weight_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    
    # Media
    image_url = models.URLField(blank=True)
    additional_images = models.JSONField(default=list, blank=True)
    
    # Status
    is_available = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['parent_product', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'sku'],
                name='unique_tenant_variant_sku'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'parent_product', 'is_active']),
            models.Index(fields=['tenant', 'is_available']),
        ]
        
    def __str__(self):
        return f'{self.parent_product.name} - {self.name}'
    
    @property
    def effective_price(self):
        """Get effective price including adjustment"""
        return self.parent_product.base_price + self.price_adjustment
    
    @property
    def effective_cost(self):
        """Get effective cost including adjustment"""
        return self.parent_product.cost_price + self.cost_adjustment
    
    @property
    def effective_weight(self):
        """Get effective weight including adjustment"""
        base_weight = self.parent_product.weight or Decimal('0.000')
        return base_weight + self.weight_adjustment