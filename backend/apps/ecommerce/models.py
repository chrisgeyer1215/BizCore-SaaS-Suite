from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import uuid
import random
import string
from enum import TextChoices

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.inventory.models import Product, ProductVariation, Warehouse, StockItem
from apps.crm.models import Customer

User = get_user_model()


# ============================================================================
# E-COMMERCE SETTINGS & CONFIGURATION
# ============================================================================

class EcommerceSettings(TenantBaseModel):
    """Comprehensive e-commerce platform settings"""
    
    class PaymentGateway(TextChoices):
        STRIPE = 'STRIPE', 'Stripe'
        PAYPAL = 'PAYPAL', 'PayPal'
        RAZORPAY = 'RAZORPAY', 'Razorpay'
        SQUARE = 'SQUARE', 'Square'
        CUSTOM = 'CUSTOM', 'Custom Gateway'
    
    class TaxCalculation(TextChoices):
        EXCLUSIVE = 'EXCLUSIVE', 'Tax Exclusive'
        INCLUSIVE = 'INCLUSIVE', 'Tax Inclusive'
        BY_LOCATION = 'BY_LOCATION', 'By Customer Location'
        AVALARA = 'AVALARA', 'Avalara Integration'
    
    class ShippingCalculation(TextChoices):
        FLAT_RATE = 'FLAT_RATE', 'Flat Rate'
        BY_WEIGHT = 'BY_WEIGHT', 'By Weight'
        BY_LOCATION = 'BY_LOCATION', 'By Location'
        REAL_TIME = 'REAL_TIME', 'Real-time Carrier Rates'
    
    class CheckoutType(TextChoices):
        GUEST_AND_ACCOUNT = 'GUEST_AND_ACCOUNT', 'Guest & Account Checkout'
        ACCOUNT_ONLY = 'ACCOUNT_ONLY', 'Account Required'
        GUEST_ONLY = 'GUEST_ONLY', 'Guest Only'
    
    class Currency(TextChoices):
        USD = 'USD', 'US Dollar'
        EUR = 'EUR', 'Euro'
        GBP = 'GBP', 'British Pound'
        CAD = 'CAD', 'Canadian Dollar'
        AUD = 'AUD', 'Australian Dollar'
        INR = 'INR', 'Indian Rupee'
        BDT = 'BDT', 'Bangladeshi Taka'
    
    # Store Information
    store_name = models.CharField(max_length=255)
    store_tagline = models.CharField(max_length=255, blank=True)
    store_description = models.TextField(blank=True)
    store_logo = models.ImageField(upload_to='store/logos/', blank=True)
    store_favicon = models.ImageField(upload_to='store/favicons/', blank=True)
    
    # Store URLs and Domain
    store_domain = models.CharField(max_length=255, blank=True)
    custom_domain = models.CharField(max_length=255, blank=True)
    
    # Contact Information
    contact_email = models.EmailField()
    support_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Business Address
    street_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Currency & Pricing
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.USD)
    currency_symbol = models.CharField(max_length=5, default='$')
    currency_position = models.CharField(
        max_length=10, 
        choices=[('before', 'Before'), ('after', 'After')], 
        default='before'
    )
    enable_multi_currency = models.BooleanField(default=False)
    
    # Tax Settings
    tax_calculation = models.CharField(
        max_length=20,
        choices=TaxCalculation.choices,
        default=TaxCalculation.EXCLUSIVE
    )
    default_tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    tax_included_in_prices = models.BooleanField(default=False)
    display_prices_with_tax = models.BooleanField(default=True)
    
    # Payment Settings
    primary_payment_gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        default=PaymentGateway.STRIPE
    )
    enable_guest_checkout = models.BooleanField(default=True)
    checkout_type = models.CharField(
        max_length=20, 
        choices=CheckoutType.choices, 
        default=CheckoutType.GUEST_AND_ACCOUNT
    )
    
    # Shipping Configuration
    shipping_calculation_method = models.CharField(
        max_length=20,
        choices=ShippingCalculation.choices,
        default=ShippingCalculation.FLAT_RATE
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    default_shipping_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    require_shipping_address = models.BooleanField(default=True)
    
    # Inventory Integration
    auto_sync_inventory = models.BooleanField(default=True)
    deduct_inventory_on = models.CharField(
        max_length=20,
        choices=[
            ('ORDER', 'Order Placed'),
            ('PAYMENT', 'Payment Confirmed'),
            ('SHIP', 'Order Shipped')
        ],
        default='PAYMENT'
    )
    allow_overselling = models.BooleanField(default=False)
    track_inventory = models.BooleanField(default=True)
    show_stock_levels = models.BooleanField(default=True)
    low_stock_threshold = models.IntegerField(default=5)
    
    # Store Status
    is_live = models.BooleanField(default=False)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    # SEO & Marketing
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    enable_seo_urls = models.BooleanField(default=True)
    enable_sitemap = models.BooleanField(default=True)
    enable_reviews = models.BooleanField(default=True)
    enable_wishlists = models.BooleanField(default=True)
    enable_coupons = models.BooleanField(default=True)
    
    # Analytics & Social
    google_analytics_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    enable_social_login = models.BooleanField(default=False)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Security & Privacy
    enable_captcha = models.BooleanField(default=False)
    gdpr_compliance = models.BooleanField(default=True)
    cookie_consent_required = models.BooleanField(default=True)
    
    # Performance
    enable_caching = models.BooleanField(default=True)
    cache_duration_minutes = models.PositiveIntegerField(default=60)
    enable_compression = models.BooleanField(default=True)
    
    # Legal Policies
    terms_of_service = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)
    return_policy = models.TextField(blank=True)
    shipping_policy = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_settings'
        verbose_name = 'E-commerce Settings'
        verbose_name_plural = 'E-commerce Settings'
    
    def __str__(self):
        return f'{self.store_name} Settings'


# ============================================================================
# PRODUCT CATALOG
# ============================================================================

class Collection(TenantBaseModel, SoftDeleteMixin):
    """Product collections/categories - Shopify-style collections"""
    
    class CollectionType(TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        AUTOMATIC = 'AUTOMATIC', 'Automatic'
        SMART = 'SMART', 'Smart Collection'
    
    class SortOrder(TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        BEST_SELLING = 'BEST_SELLING', 'Best Selling'
        ALPHABETICAL_ASC = 'ALPHABETICAL_ASC', 'Alphabetical A-Z'
        ALPHABETICAL_DESC = 'ALPHABETICAL_DESC', 'Alphabetical Z-A'
        PRICE_ASC = 'PRICE_ASC', 'Price Low to High'
        PRICE_DESC = 'PRICE_DESC', 'Price High to Low'
        CREATED_ASC = 'CREATED_ASC', 'Date Created Old to New'
        CREATED_DESC = 'CREATED_DESC', 'Date Created New to Old'
    
    # Basic Information
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    collection_type = models.CharField(
        max_length=20, 
        choices=CollectionType.choices, 
        default=CollectionType.MANUAL
    )
    
    # Hierarchy Support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Inventory Integration
    inventory_category = models.ForeignKey(
        'inventory.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecommerce_collections'
    )
    
    # Display Settings
    sort_order = models.CharField(
        max_length=20, 
        choices=SortOrder.choices, 
        default=SortOrder.MANUAL
    )
    products_per_page = models.IntegerField(default=20)
    is_featured = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    show_in_navigation = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    
    # Smart Collection Rules (for automatic collections)
    collection_rules = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Rules for automatic collections"
    )
    
    # Images
    featured_image = models.ImageField(upload_to='collections/', blank=True)
    banner_image = models.ImageField(upload_to='collections/banners/', blank=True)
    icon_class = models.CharField(max_length=50, blank=True)
    color_code = models.CharField(max_length=7, blank=True)  # Hex color
    
    # SEO
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.TextField(blank=True)
    
    # Performance (Cached)
    products_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_collection'
        unique_together = [('tenant', 'slug')]
        ordering = ['display_order', 'title']
        indexes = [
            models.Index(fields=['tenant', 'is_visible', 'is_featured']),
            models.Index(fields=['tenant', 'collection_type']),
            models.Index(fields=['tenant', 'parent']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Get full collection path"""
        path = [self.title]
        parent = self.parent
        while parent:
            path.insert(0, parent.title)
            parent = parent.parent
        return ' > '.join(path)
    
    @property
    def active_products_count(self):
        """Get active products count"""
        return self.products.filter(
            is_active=True, 
            is_published=True,
            status='PUBLISHED'
        ).count()


class EcommerceProduct(TenantBaseModel, SoftDeleteMixin):
    """Enhanced e-commerce product model combining best features"""
    
    class ProductStatus(TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'
        INACTIVE = 'INACTIVE', 'Inactive'
    
    class ProductType(TextChoices):
        SIMPLE = 'SIMPLE', 'Simple Product'
        VARIABLE = 'VARIABLE', 'Variable Product'
        GROUPED = 'GROUPED', 'Grouped Product'
        DIGITAL = 'DIGITAL', 'Digital Product'
        SUBSCRIPTION = 'SUBSCRIPTION', 'Subscription Product'
    
    class Visibility(TextChoices):
        VISIBLE = 'VISIBLE', 'Catalog & Search'
        CATALOG = 'CATALOG', 'Catalog Only'
        SEARCH = 'SEARCH', 'Search Only'
        HIDDEN = 'HIDDEN', 'Hidden'
        PASSWORD_PROTECTED = 'PASSWORD_PROTECTED', 'Password Protected'
    
    # Core Product Integration
    inventory_product = models.OneToOneField(
        Product, 
        on_delete=models.CASCADE, 
        related_name='ecommerce_product'
    )
    
    # E-commerce Basic Information
    title = models.CharField(max_length=255, help_text="Display title for e-commerce")
    slug = models.SlugField(max_length=255)
    url_handle = models.SlugField(max_length=255, help_text="URL slug for product page")
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True, help_text="Rich text description")
    additional_info = models.TextField(blank=True)
    
    # Product Classification
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.SIMPLE
    )
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.VISIBLE
    )
    
    # Collections
    collections = models.ManyToManyField(
        Collection,
        through='CollectionProduct',
        related_name='products',
        blank=True
    )
    primary_collection = models.ForeignKey(
        Collection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_products'
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Primary selling price"
    )
    compare_at_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Original price for discount display"
    )
    cost_per_item = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True
    )
    
    # Sale Pricing
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    sale_price_start = models.DateTimeField(null=True, blank=True)
    sale_price_end = models.DateTimeField(null=True, blank=True)
    
    # Inventory Management
    track_quantity = models.BooleanField(default=True)
    continue_selling_when_out_of_stock = models.BooleanField(default=False)
    inventory_policy = models.CharField(
        max_length=20, 
        choices=[
            ('DENY', 'Don\'t track quantity'),
            ('CONTINUE', 'Continue selling when out of stock'),
            ('TRACK', 'Track quantity')
        ], 
        default='TRACK'
    )
    stock_quantity = models.PositiveIntegerField(default=0)  # Cached from inventory
    low_stock_threshold = models.PositiveIntegerField(default=0)
    allow_backorders = models.BooleanField(default=False)
    
    # Shipping & Physical Properties
    requires_shipping = models.BooleanField(default=True)
    is_digital = models.BooleanField(default=False)
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        null=True, 
        blank=True,
        help_text="Weight in kg"
    )
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Tax
    is_taxable = models.BooleanField(default=True)
    tax_class = models.CharField(max_length=50, blank=True)
    
    # Product Variants Support
    has_variants = models.BooleanField(default=False)
    
    # Additional E-commerce Fields
    vendor = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Images
    featured_image = models.ImageField(upload_to='products/ecommerce/', blank=True)
    gallery_images = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of additional image URLs"
    )
    
    # SEO
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.TextField(blank=True)
    
    # Status & Visibility
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    
    # Search and Filter
    search_keywords = models.TextField(blank=True)
    
    # Performance Metrics (Cached)
    view_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00')
    )
    review_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_product'
        unique_together = [
            ('tenant', 'slug'),
            ('tenant', 'url_handle')
        ]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'is_published']),
            models.Index(fields=['tenant', 'visibility', 'is_featured']),
            models.Index(fields=['tenant', 'product_type']),
            models.Index(fields=['tenant', 'vendor']),
            models.Index(fields=['tenant', 'brand']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Auto-generate slug and url_handle if not provided
        if not self.slug:
            self.slug = slugify(self.title)
        
        if not self.url_handle:
            base_slug = slugify(self.title)
            counter = 1
            url_handle = base_slug
            while EcommerceProduct.objects.filter(
                tenant=self.tenant, 
                url_handle=url_handle
            ).exclude(pk=self.pk).exists():
                url_handle = f"{base_slug}-{counter}"
                counter += 1
            self.url_handle = url_handle
        
        # Set published timestamp
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        elif not self.is_published:
            self.published_at = None
        
        super().save(*args, **kwargs)
    
    @property
    def name(self):
        """Get product name from inventory"""
        return self.inventory_product.name if self.inventory_product else self.title
    
    @property
    def sku(self):
        """Get SKU from inventory"""
        return self.inventory_product.product_code if self.inventory_product else None
    
    @property
    def current_price(self):
        """Get current selling price (sale or regular)"""
        if self.is_on_sale and self.sale_price:
            return self.sale_price
        return self.price
    
    @property
    def is_on_sale(self):
        """Check if product is currently on sale"""
        if not self.sale_price or not self.compare_at_price:
            return False
        
        now = timezone.now()
        if self.sale_price_start and now < self.sale_price_start:
            return False
        if self.sale_price_end and now > self.sale_price_end:
            return False
        
        return self.sale_price < self.compare_at_price
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_on_sale and self.compare_at_price:
            return round(((self.compare_at_price - self.current_price) / self.compare_at_price) * 100, 2)
        return 0
    
    @property
    def total_inventory(self):
        """Get total inventory from linked inventory product"""
        if self.inventory_product:
            return self.inventory_product.total_stock
        return 0
    
    @property
    def available_inventory(self):
        """Get available inventory from linked inventory product"""
        if self.inventory_product:
            return self.inventory_product.available_stock
        return 0
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        if not self.track_quantity:
            return True
        return self.available_inventory > 0 or self.continue_selling_when_out_of_stock
    
    def get_stock_quantity(self):
        """Get actual stock quantity from inventory"""
        if not self.track_quantity:
            return None
        
        if self.inventory_product:
            return self.inventory_product.stock_items.filter(
                warehouse__is_sellable=True
            ).aggregate(
                total=models.Sum('quantity_available')
            )['total'] or 0
        
        return self.stock_quantity


class ProductVariant(TenantBaseModel, SoftDeleteMixin):
    """Enhanced product variant model"""
    
    ecommerce_product = models.ForeignKey(
        EcommerceProduct, 
        on_delete=models.CASCADE, 
        related_name='variants'
    )
    inventory_variation = models.OneToOneField(
        ProductVariation, 
        on_delete=models.CASCADE, 
        related_name='ecommerce_variant',
        blank=True, 
        null=True
    )
    
    # Variant Identification
    title = models.CharField(max_length=255, help_text="Variant title (e.g., 'Large / Red')")
    sku = models.CharField(max_length=100)
    barcode = models.CharField(max_length=100, blank=True)
    
    # Variant Attributes
    attributes = models.JSONField(default=dict, help_text="Variant attributes like color, size")
    
    # Pricing (can override product pricing)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cost_per_item = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Stock Management
    stock_quantity = models.PositiveIntegerField(default=0)
    inventory_policy = models.CharField(
        max_length=20, 
        choices=[
            ('DENY', 'Don\'t track quantity'),
            ('CONTINUE', 'Continue selling when out of stock'),
            ('TRACK', 'Track quantity')
        ], 
        default='TRACK'
    )
    
    # Physical Properties
    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    length = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    width = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    height = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    requires_shipping = models.BooleanField(default=True)
    
    # Display
    image = models.ImageField(upload_to='products/variants/', blank=True)
    position = models.IntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_product_variant'
        unique_together = [('tenant', 'sku')]
        ordering = ['position']
        indexes = [
            models.Index(fields=['tenant', 'ecommerce_product', 'is_active']),
            models.Index(fields=['sku']),
        ]
    
    def __str__(self):
        return f"{self.ecommerce_product.title} - {self.title}"
    
    @property
    def effective_price(self):
        """Get effective price (variant override or product price)"""
        return self.price or self.ecommerce_product.current_price
    
    @property
    def effective_compare_at_price(self):
        """Get effective compare at price"""
        return self.compare_at_price or self.ecommerce_product.compare_at_price
    
    @property
    def is_on_sale(self):
        """Check if variant is on sale"""
        effective_compare = self.effective_compare_at_price
        return effective_compare and effective_compare > self.effective_price
    
    @property
    def available_quantity(self):
        """Get available quantity from inventory"""
        if self.inventory_variation:
            return self.inventory_variation.available_stock
        return self.stock_quantity
    
    @property
    def is_in_stock(self):
        """Check if variant is in stock"""
        if self.inventory_policy == 'DENY':
            return True
        if self.inventory_policy == 'CONTINUE':
            return True
        return self.available_quantity > 0


class CollectionProduct(TenantBaseModel):
    """Through model for collection-product relationship with enhanced features"""
    
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ecommerce_collection_product'
        unique_together = [('tenant', 'collection', 'product')]
        ordering = ['position']


# ============================================================================
# SHOPPING CART & WISHLIST
# ============================================================================

class Cart(TenantBaseModel):
    """Enhanced shopping cart model"""
    
    class CartStatus(TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ABANDONED = 'ABANDONED', 'Abandoned'
        COMPLETED = 'COMPLETED', 'Completed'
        EXPIRED = 'EXPIRED', 'Expired'
    
    # Cart Identification
    cart_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session_id = models.CharField(max_length=255, blank=True)
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='carts'
    )
    
    # Cart Status
    status = models.CharField(
        max_length=20, 
        choices=CartStatus.choices, 
        default=CartStatus.ACTIVE
    )
    is_abandoned = models.BooleanField(default=False)
    abandoned_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Totals (calculated fields)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Applied Promotions
    discount_codes = models.JSONField(default=list, blank=True)
    applied_coupons = models.JSONField(default=list, blank=True)
    
    # Shipping Information
    shipping_address = models.JSONField(null=True, blank=True)
    shipping_method = models.CharField(max_length=100, blank=True)
    
    # Currency
    currency = models.CharField(max_length=3, default='USD')
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_cart'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'session_id']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['cart_id']),
        ]
    
    def __str__(self):
        if self.customer:
            return f"Cart - {self.customer.name}"
        return f"Cart - {self.session_id or self.cart_id}"
    
    @property
    def item_count(self):
        """Total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def unique_item_count(self):
        """Number of unique items in cart"""
        return self.items.count()
    
    def calculate_totals(self):
        """Calculate cart totals"""
        items = self.items.select_related('product', 'variant')
        self.subtotal = sum(item.line_total for item in items)
        
        # Tax calculation based on settings
        settings = EcommerceSettings.objects.filter(tenant=self.tenant).first()
        if settings and settings.default_tax_rate:
            if settings.tax_calculation == 'EXCLUSIVE':
                self.tax_amount = self.subtotal * (settings.default_tax_rate / 100)
            # For inclusive, tax is already included in prices
        
        # Total calculation
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_amount - self.discount_amount
        self.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        
        return self.total_amount
    
    def add_item(self, product, variant=None, quantity=1, custom_attributes=None):
        """Add item to cart"""
        price = variant.effective_price if variant else product.current_price
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=self,
            product=product,
            variant=variant,
            defaults={
                'tenant': self.tenant,
                'quantity': quantity,
                'unit_price': price,
                'custom_attributes': custom_attributes or {}
            }
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save(update_fields=['quantity'])
        
        self.calculate_totals()
        return cart_item
    
    def update_item_quantity(self, item_id, quantity):
        """Update item quantity"""
        try:
            item = self.items.get(id=item_id)
            if quantity <= 0:
                item.delete()
            else:
                item.quantity = quantity
                item.save(update_fields=['quantity'])
            self.calculate_totals()
            return True
        except CartItem.DoesNotExist:
            return False
    
    def remove_item(self, item_id):
        """Remove item from cart"""
        try:
            item = self.items.get(id=item_id)
            item.delete()
            self.calculate_totals()
            return True
        except CartItem.DoesNotExist:
            return False
    
    def clear(self):
        """Clear all items from cart"""
        self.items.all().delete()
        self.calculate_totals()


class CartItem(TenantBaseModel):
    """Enhanced cart item model"""
    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE, related_name='cart_items')
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='cart_items'
    )
    
    # Item Details
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Price at time of adding to cart"
    )
    
    # Custom attributes (e.g., personalization, gift message)
    custom_attributes = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ecommerce_cart_item'
        unique_together = [('tenant', 'cart', 'product', 'variant')]
        indexes = [
            models.Index(fields=['tenant', 'cart']),
            models.Index(fields=['tenant', 'product']),
        ]
    
    def __str__(self):
        variant_info = f" - {self.variant.title}" if self.variant else ""
        return f"{self.product.title}{variant_info} x {self.quantity}"
    
    @property
    def line_total(self):
        """Calculate line total for this item"""
        return self.quantity * self.unit_price
    
    @property
    def item_name(self):
        """Get full item name including variant"""
        if self.variant:
            return f"{self.product.title} - {self.variant.title}"
        return self.product.title


class Wishlist(TenantBaseModel):
    """Enhanced customer wishlist"""
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='wishlists')
    name = models.CharField(max_length=255, default='My Wishlist')
    description = models.TextField(blank=True)
    
    # Privacy Settings
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'ecommerce_wishlist'
        unique_together = [('tenant', 'customer', 'name')]
    
    def __str__(self):
        return f"{self.customer.name} - {self.name}"
    
    @property
    def items_count(self):
        """Get wishlist items count"""
        return self.items.count()


class WishlistItem(TenantBaseModel):
    """Enhanced wishlist item"""
    
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE, related_name='wishlist_items')
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='wishlist_items'
    )
    
    # Item Details
    added_at = models.DateTimeField(auto_now_add=True)
    priority = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_wishlist_item'
        unique_together = [('tenant', 'wishlist', 'product', 'variant')]
        ordering = ['-priority', '-added_at']
    
    def __str__(self):
        variant_info = f" - {self.variant.title}" if self.variant else ""
        return f"{self.product.title}{variant_info} in {self.wishlist.name}"


# ============================================================================
# ORDERS & FULFILLMENT
# ============================================================================

class Order(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive order model"""
    
    class OrderStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        RETURNED = 'RETURNED', 'Returned'
    
    class PaymentStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        PAID = 'PAID', 'Paid'
        PARTIAL = 'PARTIAL', 'Partially Paid'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    class FulfillmentStatus(TextChoices):
        UNFULFILLED = 'UNFULFILLED', 'Unfulfilled'
        PARTIAL = 'PARTIAL', 'Partially Fulfilled'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    # Order Identification
    order_number = models.CharField(max_length=50, unique=True)
    order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Customer Information
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='orders'
    )
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Order Status
    status = models.CharField(
        max_length=20, 
        choices=OrderStatus.choices, 
        default=OrderStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=20, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING
    )
    fulfillment_status = models.CharField(
        max_length=20, 
        choices=FulfillmentStatus.choices, 
        default=FulfillmentStatus.UNFULFILLED
    )
    
    # Financial Information
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Applied Discounts
    applied_discounts = models.JSONField(default=list, blank=True)
    discount_codes = models.JSONField(default=list, blank=True)
    
    # Billing Address
    billing_first_name = models.CharField(max_length=100)
    billing_last_name = models.CharField(max_length=100)
    billing_company = models.CharField(max_length=100, blank=True)
    billing_address_line1 = models.CharField(max_length=255)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=100)
    billing_postal_code = models.CharField(max_length=20)
    billing_country = models.CharField(max_length=100)
    
    # Shipping Address
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_company = models.CharField(max_length=100, blank=True)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_url = models.URLField(blank=True)
    shipping_carrier = models.CharField(max_length=100, blank=True)
    
    # Payment Information
    payment_method = models.CharField(max_length=50)
    payment_gateway = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Fulfillment
    fulfillment_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Important Dates
    order_date = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    payment_date = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    # Source Information
    source_cart = models.ForeignKey(
        Cart, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='orders'
    )
    source_name = models.CharField(max_length=50, default='web')  # web, mobile, api, pos
    referring_site = models.URLField(blank=True)
    landing_site = models.URLField(blank=True)
    
    # Order Notes
    notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Risk Assessment
    risk_level = models.CharField(
        max_length=20, 
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High')
        ], 
        default='LOW'
    )
    
    # Processing Information
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    # Integration References
    inventory_invoice_id = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_order'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'order_date']),
            models.Index(fields=['tenant', 'payment_status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['customer_email']),
        ]
        ordering = ['-order_date']
    
    def __str__(self):
        return f"Order #{self.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number"""
        year = timezone.now().year
        count = Order.objects.filter(
            tenant=self.tenant,
            order_date__year=year
        ).count() + 1
        return f"{year}-{count:06d}"
    
    @property
    def customer_name(self):
        """Get customer full name"""
        return f"{self.billing_first_name} {self.billing_last_name}"
    
    @property
    def shipping_address_formatted(self):
        """Get formatted shipping address"""
        address_parts = [
            f"{self.shipping_first_name} {self.shipping_last_name}",
            self.shipping_company,
            self.shipping_address_line1,
            self.shipping_address_line2,
            f"{self.shipping_city}, {self.shipping_state} {self.shipping_postal_code}",
            self.shipping_country
        ]
        return '\n'.join(filter(None, address_parts))
    
    @property
    def item_count(self):
        """Total number of items in order"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in ['PENDING', 'CONFIRMED'] and self.payment_status != 'PAID'
    
    @property
    def can_refund(self):
        """Check if order can be refunded"""
        return self.payment_status == 'PAID' and self.status not in ['CANCELLED', 'REFUNDED']
    
    def get_items_count(self):
        """Get total items in order"""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0


class OrderItem(TenantBaseModel):
    """Enhanced order item model"""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(EcommerceProduct, on_delete=models.PROTECT, related_name='order_items')
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='order_items'
    )
    
    # Item Details at Time of Purchase (snapshot)
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100, blank=True)
    variant_title = models.CharField(max_length=255, blank=True)
    variant_attributes = models.JSONField(default=dict)
    
    # Pricing
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Unit price at time of purchase"
    )
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Totals
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Physical Properties
    weight = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True)
    requires_shipping = models.BooleanField(default=True)
    
    # Fulfillment
    fulfillment_status = models.CharField(
        max_length=20, 
        choices=[
            ('UNFULFILLED', 'Unfulfilled'),
            ('FULFILLED', 'Fulfilled'),
            ('CANCELLED', 'Cancelled'),
        ], 
        default='UNFULFILLED'
    )
    quantity_fulfilled = models.PositiveIntegerField(default=0)
    
    # Custom Properties
    custom_attributes = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ecommerce_order_item'
        indexes = [
            models.Index(fields=['tenant', 'order']),
            models.Index(fields=['tenant', 'product']),
            models.Index(fields=['fulfillment_status']),
        ]
    
    def __str__(self):
        variant_info = f" - {self.variant_title}" if self.variant_title else ""
        return f"{self.product_name}{variant_info} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate total price
        self.total_price = (self.quantity * self.unit_price) - self.discount_amount
        super().save(*args, **kwargs)
    
    @property
    def unfulfilled_quantity(self):
        """Get unfulfilled quantity"""
        return self.quantity - self.quantity_fulfilled


# ============================================================================
# PAYMENT PROCESSING
# ============================================================================

class PaymentSession(TenantBaseModel):
    """Enhanced payment session for checkout process"""
    
    class SessionStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        EXPIRED = 'EXPIRED', 'Expired'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='payment_sessions')
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_sessions'
    )
    
    # Payment Details
    payment_gateway = models.CharField(max_length=50)
    gateway_session_id = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(max_length=50)
    
    # Amounts
    currency = models.CharField(max_length=3, default='USD')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.PENDING
    )
    
    # Checkout Information
    billing_address = models.JSONField(null=True, blank=True)
    shipping_address = models.JSONField(null=True, blank=True)
    
    # Gateway Response
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'ecommerce_payment_session'
        indexes = [
            models.Index(fields=['tenant', 'session_id']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f'Payment Session {self.session_id}'


class PaymentTransaction(TenantBaseModel):
    """Enhanced payment transaction model"""
    
    class TransactionType(TextChoices):
        PAYMENT = 'PAYMENT', 'Payment'
        REFUND = 'REFUND', 'Refund'
        PARTIAL_REFUND = 'PARTIAL_REFUND', 'Partial Refund'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
        AUTHORIZATION = 'AUTHORIZATION', 'Authorization'
        CAPTURE = 'CAPTURE', 'Capture'
        VOID = 'VOID', 'Void'
    
    class PaymentMethod(TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
        PAYPAL = 'PAYPAL', 'PayPal'
        STRIPE = 'STRIPE', 'Stripe'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CASH_ON_DELIVERY = 'CASH_ON_DELIVERY', 'Cash on Delivery'
        WALLET = 'WALLET', 'Digital Wallet'
        CRYPTOCURRENCY = 'CRYPTOCURRENCY', 'Cryptocurrency'
    
    class TransactionStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'
    
    # Transaction Identification
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    external_transaction_id = models.CharField(max_length=255, blank=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True)
    
    # Related Order
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_transactions')
    payment_session = models.ForeignKey(
        PaymentSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        max_length=20, 
        choices=TransactionType.choices,
        default=TransactionType.PAYMENT
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PaymentMethod.choices
    )
    payment_gateway = models.CharField(max_length=50, blank=True)
    
    # Financial Information
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))
    
    # Transaction Status
    status = models.CharField(
        max_length=20, 
        choices=TransactionStatus.choices, 
        default=TransactionStatus.PENDING
    )
    
    # Gateway Response
    gateway_response = models.JSONField(default=dict, blank=True)
    gateway_reference = models.CharField(max_length=255, blank=True)
    authorization_code = models.CharField(max_length=100, blank=True)
    
    # Error Information
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    processed_at = models.DateTimeField(blank=True, null=True)
    authorized_at = models.DateTimeField(blank=True, null=True)
    captured_at = models.DateTimeField(blank=True, null=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_payment_transaction'
        indexes = [
            models.Index(fields=['tenant', 'order']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'transaction_type']),
            models.Index(fields=['external_transaction_id']),
            models.Index(fields=['gateway_transaction_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type.title()} - {self.amount} {self.currency}"


# ============================================================================
# PROMOTIONS & COUPONS
# ============================================================================

class Discount(TenantBaseModel, SoftDeleteMixin):
    """Enhanced discount/coupon model"""
    
    class DiscountType(TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Percentage'
        FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount'
        FREE_SHIPPING = 'FREE_SHIPPING', 'Free Shipping'
        BUY_X_GET_Y = 'BUY_X_GET_Y', 'Buy X Get Y'
    
    class AppliesTo(TextChoices):
        ALL = 'ALL', 'All Products'
        SPECIFIC_PRODUCTS = 'SPECIFIC_PRODUCTS', 'Specific Products'
        SPECIFIC_COLLECTIONS = 'SPECIFIC_COLLECTIONS', 'Specific Collections'
        MINIMUM_AMOUNT = 'MINIMUM_AMOUNT', 'Minimum Purchase Amount'
    
    # Basic Information
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    
    # Discount Settings
    discount_type = models.CharField(
        max_length=20, 
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE
    )
    value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Percentage or fixed amount"
    )
    applies_to = models.CharField(
        max_length=20, 
        choices=AppliesTo.choices, 
        default=AppliesTo.ALL
    )
    
    # Constraints
    minimum_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True
    )
    maximum_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    minimum_quantity = models.IntegerField(blank=True, null=True)
    
    # Usage Limits
    usage_limit = models.IntegerField(
        blank=True, 
        null=True, 
        help_text="Total number of times this discount can be used"
    )
    usage_limit_per_customer = models.IntegerField(blank=True, null=True)
    current_uses = models.IntegerField(default=0)
    
    # Date Range
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Applicable Products and Collections
    applicable_products = models.ManyToManyField(
        EcommerceProduct, 
        blank=True, 
        related_name='discounts'
    )
    applicable_collections = models.ManyToManyField(
        Collection, 
        blank=True, 
        related_name='discounts'
    )
    
    class Meta:
        db_table = 'ecommerce_discount'
        unique_together = [('tenant', 'code')]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'valid_from', 'valid_until']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.code})"
    
    @property
    def is_valid(self):
        """Check if discount is currently valid"""
        now = timezone.now()
        
        # Check if active
        if not self.is_active:
            return False
        
        # Check date range
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        
        # Check usage limit
        if self.usage_limit and self.current_uses >= self.usage_limit:
            return False
        
        return True
    
    def can_apply_to_cart(self, cart):
        """Check if discount can be applied to a cart"""
        if not self.is_valid:
            return False, "Discount is not valid"
        
        # Check minimum amount
        if self.minimum_amount and cart.subtotal < self.minimum_amount:
            return False, f"Minimum purchase amount of {self.minimum_amount} required"
        
        # Check minimum quantity
        if self.minimum_quantity and cart.item_count < self.minimum_quantity:
            return False, f"Minimum quantity of {self.minimum_quantity} items required"
        
        # Check applicable products/collections
        if self.applies_to == 'SPECIFIC_PRODUCTS':
            applicable_product_ids = set(self.applicable_products.values_list('id', flat=True))
            cart_product_ids = set(cart.items.values_list('product_id', flat=True))
            if not applicable_product_ids.intersection(cart_product_ids):
                return False, "No applicable products in cart"
        
        elif self.applies_to == 'SPECIFIC_COLLECTIONS':
            # Check if any cart items belong to applicable collections
            applicable_collection_ids = set(self.applicable_collections.values_list('id', flat=True))
            cart_product_ids = list(cart.items.values_list('product_id', flat=True))
            
            # Get collections for cart products
            product_collections = CollectionProduct.objects.filter(
                product_id__in=cart_product_ids,
                collection_id__in=applicable_collection_ids
            )
            
            if not product_collections.exists():
                return False, "No applicable products from specified collections in cart"
        
        return True, "Discount can be applied"
    
    def calculate_discount_amount(self, cart):
        """Calculate discount amount for a cart"""
        can_apply, message = self.can_apply_to_cart(cart)
        if not can_apply:
            return Decimal('0')
        
        if self.discount_type == 'PERCENTAGE':
            discount = cart.subtotal * (self.value / 100)
        elif self.discount_type == 'FIXED_AMOUNT':
            discount = min(self.value, cart.subtotal)
        elif self.discount_type == 'FREE_SHIPPING':
            discount = cart.shipping_amount
        else:
            discount = Decimal('0')
        
        # Apply maximum discount limit if set
        if self.maximum_discount_amount:
            discount = min(discount, self.maximum_discount_amount)
        
        return discount


class CouponUsage(TenantBaseModel):
    """Track individual coupon usage"""
    
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='usage_records')
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='coupon_usage'
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='coupon_usage')
    
    # Usage Details
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)
    
    # Session Information
    session_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_coupon_usage'
        indexes = [
            models.Index(fields=['tenant', 'discount']),
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['used_at']),
        ]
    
    def __str__(self):
        customer_info = self.customer.name if self.customer else "Guest"
        return f"{self.discount.code} used by {customer_info}"


# ============================================================================
# SHIPPING & ZONES
# ============================================================================

class ShippingZone(TenantBaseModel, SoftDeleteMixin):
    """Enhanced shipping zone model"""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Countries and regions in this zone
    countries = models.JSONField(default=list, help_text="List of country codes")
    states = models.JSONField(default=list, blank=True, help_text="List of state/province codes")
    postal_codes = models.JSONField(default=list, blank=True, help_text="List of postal code patterns")
    
    # Zone settings
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_shipping_zone'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name


class ShippingMethod(TenantBaseModel, SoftDeleteMixin):
    """Enhanced shipping method model"""
    
    class RateType(TextChoices):
        FLAT_RATE = 'FLAT_RATE', 'Flat Rate'
        FREE = 'FREE', 'Free Shipping'
        CALCULATED = 'CALCULATED', 'Calculated Rate'
        PICKUP = 'PICKUP', 'Local Pickup'
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    shipping_zone = models.ForeignKey(
        ShippingZone, 
        on_delete=models.CASCADE, 
        related_name='shipping_methods'
    )
    
    # Rate Configuration
    rate_type = models.CharField(max_length=20, choices=RateType.choices)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Conditions
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    maximum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    minimum_weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    maximum_weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    
    # Delivery Information
    estimated_delivery_days_min = models.IntegerField(blank=True, null=True)
    estimated_delivery_days_max = models.IntegerField(blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_shipping_method'
        ordering = ['shipping_zone', 'sort_order', 'name']
    
    def __str__(self):
        return f"{self.shipping_zone.name} - {self.name}"
    
    def calculate_rate(self, order_total, weight):
        """Calculate shipping rate for given order total and weight"""
        # Check conditions
        if self.minimum_order_amount and order_total < self.minimum_order_amount:
            return None
        if self.maximum_order_amount and order_total > self.maximum_order_amount:
            return None
        if self.minimum_weight and weight < self.minimum_weight:
            return None
        if self.maximum_weight and weight > self.maximum_weight:
            return None
        
        # Calculate rate based on type
        if self.rate_type == 'FREE':
            return Decimal('0')
        elif self.rate_type == 'FLAT_RATE':
            return self.base_rate
        elif self.rate_type == 'CALCULATED':
            return self.base_rate + (weight * self.rate_per_kg)
        elif self.rate_type == 'PICKUP':
            return Decimal('0')
        
        return self.base_rate


# ============================================================================
# REVIEWS & RATINGS
# ============================================================================

class ProductReview(TenantBaseModel, SoftDeleteMixin):
    """Enhanced product reviews and ratings"""
    
    class ReviewStatus(TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SPAM = 'SPAM', 'Marked as Spam'
    
    product = models.ForeignKey(
        EcommerceProduct,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews'
    )
    
    # Review Content
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255, blank=True)
    review_text = models.TextField()
    
    # Review Images
    images = models.JSONField(default=list, blank=True, help_text="URLs of uploaded images")
    
    # Moderation
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reviews'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    total_votes = models.PositiveIntegerField(default=0)
    
    # Verified purchase
    is_verified_purchase = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Response from Store
    store_response = models.TextField(blank=True)
    store_response_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'ecommerce_product_review'
        unique_together = [('tenant', 'product', 'customer', 'order')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'product', 'status']),
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['rating']),
            models.Index(fields=['is_verified_purchase']),
        ]
    
    def __str__(self):
        return f'Review for {self.product.title} by {self.customer.name}'
    
    @property
    def helpfulness_percentage(self):
        """Calculate helpfulness percentage"""
        if self.total_votes == 0:
            return 0
        return round((self.helpful_count / self.total_votes) * 100, 1)


class ProductQuestion(TenantBaseModel, SoftDeleteMixin):
    """Customer questions about products"""
    
    product = models.ForeignKey(
        EcommerceProduct, 
        on_delete=models.CASCADE, 
        related_name='questions'
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='product_questions')
    
    # Question Content
    question = models.TextField()
    answer = models.TextField(blank=True)
    
    # Status
    is_answered = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Staff Response
    answered_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    answered_at = models.DateTimeField(blank=True, null=True)
    
    # Helpful Votes
    helpful_votes = models.PositiveIntegerField(default=0)
    total_votes = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_product_question'
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_public']),
            models.Index(fields=['is_answered']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Question about {self.product.title} by {self.customer.name}"


# ============================================================================
# CUSTOMER DATA
# ============================================================================

class CustomerAddress(TenantBaseModel, SoftDeleteMixin):
    """Enhanced customer saved addresses"""
    
    class AddressType(TextChoices):
        BILLING = 'BILLING', 'Billing Address'
        SHIPPING = 'SHIPPING', 'Shipping Address'
        BOTH = 'BOTH', 'Billing & Shipping'
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    
    # Address Details
    type = models.CharField(
        max_length=20, 
        choices=AddressType.choices, 
        default=AddressType.BOTH
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=200, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20, blank=True)
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_customer_address'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
        ]
    
    def __str__(self):
        return f'{self.first_name} {self.last_name} - {self.city}, {self.state}'
    
    def get_full_address(self):
        """Get formatted full address"""
        parts = [
            f'{self.first_name} {self.last_name}',
            self.company,
            self.address_line1,
            self.address_line2,
            f'{self.city}, {self.state} {self.postal_code}',
            self.country
        ]
        return '\n'.join(part for part in parts if part)


class CustomerGroup(TenantBaseModel, SoftDeleteMixin):
    """Customer group for targeted pricing and discounts"""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Group Benefits
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Automatic Assignment Rules
    auto_assign_rules = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Rules for automatic customer assignment"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Members
    customers = models.ManyToManyField(Customer, related_name='customer_groups', blank=True)
    
    class Meta:
        db_table = 'ecommerce_customer_group'
    
    def __str__(self):
        return self.name


# ============================================================================
# GIFT CARDS
# ============================================================================

class GiftCard(TenantBaseModel):
    """Enhanced gift card model"""
    
    class Status(TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        REDEEMED = 'REDEEMED', 'Fully Redeemed'
        EXPIRED = 'EXPIRED', 'Expired'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    # Gift Card Information
    code = models.CharField(max_length=50, unique=True)
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Status and Dates
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    issued_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(blank=True, null=True)
    
    # Recipient Information
    recipient_email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    
    # Purchase Information
    purchased_by = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='purchased_gift_cards'
    )
    purchase_order = models.ForeignKey(
        Order, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='gift_cards'
    )
    
    # Usage Tracking
    first_used_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    times_used = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_gift_card'
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['recipient_email']),
        ]
    
    def __str__(self):
        return f"Gift Card {self.code} - ${self.current_balance}"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_gift_card_code()
        if not self.current_balance:
            self.current_balance = self.initial_value
        super().save(*args, **kwargs)
    
    def generate_gift_card_code(self):
        """Generate unique gift card code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not GiftCard.objects.filter(code=code).exists():
                return code
    
    @property
    def is_expired(self):
        """Check if gift card is expired"""
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False
    
    @property
    def is_active(self):
        """Check if gift card can be used"""
        return (self.status == 'ACTIVE' and 
                self.current_balance > 0 and 
                not self.is_expired)


class GiftCardTransaction(TenantBaseModel):
    """Track gift card usage transactions"""
    
    class TransactionType(TextChoices):
        REDEMPTION = 'REDEMPTION', 'Redemption'
        REFUND = 'REFUND', 'Refund'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
    
    gift_card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='transactions')
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='gift_card_transactions'
    )
    
    # Transaction Details
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Additional Information
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    
    class Meta:
        db_table = 'ecommerce_gift_card_transaction'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.gift_card.code} - {self.transaction_type} ${self.amount}"


# ============================================================================
# SUBSCRIPTIONS
# ============================================================================

class SubscriptionPlan(TenantBaseModel, SoftDeleteMixin):
    """Enhanced subscription plans"""
    
    class BillingInterval(TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        QUARTERLY = 'QUARTERLY', 'Quarterly'
        YEARLY = 'YEARLY', 'Yearly'
    
    # Plan Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    setup_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Billing Configuration
    billing_interval = models.CharField(max_length=20, choices=BillingInterval.choices)
    billing_interval_count = models.IntegerField(default=1)
    
    # Trial Period
    trial_period_days = models.IntegerField(default=0)
    
    # Plan Features
    features = models.JSONField(default=list, blank=True)
    limitations = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'ecommerce_subscription_plan'
    
    def __str__(self):
        return f"{self.name} - ${self.price}/{self.billing_interval}"


class Subscription(TenantBaseModel):
    """Enhanced customer subscriptions"""
    
    class Status(TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'
        PAUSED = 'PAUSED', 'Paused'
        PAST_DUE = 'PAST_DUE', 'Past Due'
    
    # Subscription Information
    subscription_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions')
    
    # Status and Dates
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    
    # Billing Information
    next_billing_date = models.DateTimeField()
    last_payment_date = models.DateTimeField(blank=True, null=True)
    failed_payment_count = models.IntegerField(default=0)
    
    # Customization
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_subscription'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.plan.name}"
    
    @property
    def is_in_trial(self):
        """Check if subscription is in trial period"""
        if self.trial_ends_at:
            return timezone.now() < self.trial_ends_at
        return False
    
    @property
    def effective_price(self):
        """Get effective price considering custom pricing and discounts"""
        base_price = self.custom_price or self.plan.price
        if self.discount_percentage > 0:
            discount_amount = base_price * (self.discount_percentage / 100)
            return base_price - discount_amount
        return base_price


# ============================================================================
# DIGITAL PRODUCTS
# ============================================================================

class DigitalProduct(TenantBaseModel, SoftDeleteMixin):
    """Digital products and downloadable content"""
    
    ecommerce_product = models.OneToOneField(
        EcommerceProduct, 
        on_delete=models.CASCADE, 
        related_name='digital_product'
    )
    
    # Digital Content
    file_url = models.URLField(blank=True)
    file_size = models.BigIntegerField(blank=True, null=True, help_text="File size in bytes")
    file_type = models.CharField(max_length=50, blank=True)
    
    # Download Configuration
    download_limit = models.IntegerField(default=5, help_text="Number of allowed downloads")
    download_link_expiry_hours = models.IntegerField(default=24)
    
    # License Information
    license_type = models.CharField(max_length=100, blank=True)
    license_terms = models.TextField(blank=True)
    
    # Version Control
    version = models.CharField(max_length=20, default='1.0')
    changelog = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_digital_product'
    
    def __str__(self):
        return f"Digital: {self.ecommerce_product.title}"


class DigitalDownload(TenantBaseModel):
    """Track digital product downloads"""
    
    digital_product = models.ForeignKey(
        DigitalProduct, 
        on_delete=models.CASCADE, 
        related_name='downloads'
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='digital_downloads')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='digital_downloads')
    
    # Download Information
    download_token = models.UUIDField(default=uuid.uuid4, unique=True)
    download_count = models.IntegerField(default=0)
    last_downloaded_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField()
    
    # Access Control
    is_active = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_digital_download'
        unique_together = [('tenant', 'digital_product', 'customer', 'order')]
    
    def __str__(self):
        return f"Download: {self.digital_product.ecommerce_product.title} for {self.customer.name}"
    
    @property
    def is_expired(self):
        """Check if download link is expired"""
        return timezone.now() > self.expires_at
    
    @property
    def can_download(self):
        """Check if customer can still download"""
        return (self.is_active and 
                not self.is_expired and 
                self.download_count < self.digital_product.download_limit)


# ============================================================================
# ANALYTICS & PERFORMANCE
# ============================================================================

class ProductAnalytics(TenantBaseModel):
    """Product analytics and performance tracking"""
    
    product = models.OneToOneField(
        EcommerceProduct, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    
    # View Statistics
    total_views = models.IntegerField(default=0)
    unique_views = models.IntegerField(default=0)
    views_this_month = models.IntegerField(default=0)
    
    # Cart Statistics
    times_added_to_cart = models.IntegerField(default=0)
    times_purchased = models.IntegerField(default=0)
    
    # Revenue Statistics
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Performance Metrics
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # Percentage
    cart_abandonment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # SEO & Search
    search_ranking_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    organic_traffic_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Last Updated
    last_calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecommerce_product_analytics'
    
    def __str__(self):
        return f"Analytics for {self.product.title}"


class AbandonedCart(TenantBaseModel):
    """Abandoned cart tracking for recovery campaigns"""
    
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE, related_name='abandoned_cart')
    
    # Recovery Information
    recovery_email_sent = models.BooleanField(default=False)
    recovery_email_sent_at = models.DateTimeField(blank=True, null=True)
    recovery_email_count = models.IntegerField(default=0)
    
    # Recovery Success
    recovered = models.BooleanField(default=False)
    recovered_at = models.DateTimeField(blank=True, null=True)
    recovery_order = models.ForeignKey(Order, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Additional Tracking
    browser_info = models.JSONField(default=dict, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'ecommerce_abandoned_cart'
    
    def __str__(self):
        return f"Abandoned Cart - {self.cart.cart_id}"


# ============================================================================
# MULTI-CHANNEL SELLING
# ============================================================================

class SalesChannel(TenantBaseModel):
    """Sales channels for multi-channel selling"""
    
    class ChannelType(TextChoices):
        ONLINE_STORE = 'ONLINE_STORE', 'Online Store'
        MARKETPLACE = 'MARKETPLACE', 'Marketplace'
        SOCIAL_MEDIA = 'SOCIAL_MEDIA', 'Social Media'
        POS = 'POS', 'Point of Sale'
        WHOLESALE = 'WHOLESALE', 'Wholesale'
        API = 'API', 'API'
    
    # Channel Information
    name = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    description = models.TextField(blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    auto_sync_inventory = models.BooleanField(default=True)
    auto_sync_pricing = models.BooleanField(default=True)
    
    # Integration Settings
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    webhook_url = models.URLField(blank=True)
    
    # Channel Specific Settings
    channel_settings = models.JSONField(default=dict, blank=True)
    
    # Performance Tracking
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        db_table = 'ecommerce_sales_channel'
    
    def __str__(self):
        return f"{self.name} ({self.channel_type})"


class ChannelProduct(TenantBaseModel):
    """Product configuration per sales channel"""
    
    class SyncStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        SYNCED = 'SYNCED', 'Synced'
        ERROR = 'ERROR', 'Error'
    
    sales_channel = models.ForeignKey(
        SalesChannel, 
        on_delete=models.CASCADE, 
        related_name='channel_products'
    )
    product = models.ForeignKey(
        EcommerceProduct, 
        on_delete=models.CASCADE, 
        related_name='channel_products'
    )
    
    # Channel Specific Configuration
    is_active = models.BooleanField(default=True)
    channel_product_id = models.CharField(max_length=100, blank=True)
    
    # Pricing Override
    price_override = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    markup_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Inventory Override
    inventory_override = models.IntegerField(blank=True, null=True)
    
    # Channel Specific Data
    channel_title = models.CharField(max_length=255, blank=True)
    channel_description = models.TextField(blank=True)
    channel_images = models.JSONField(default=list, blank=True)
    channel_categories = models.JSONField(default=list, blank=True)
    
    # Sync Status
    last_synced_at = models.DateTimeField(blank=True, null=True)
    sync_status = models.CharField(
        max_length=20, 
        choices=SyncStatus.choices, 
        default=SyncStatus.PENDING
    )
    sync_error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_channel_product'
        unique_together = [('tenant', 'sales_channel', 'product')]
    
    def __str__(self):
        return f"{self.product.title} on {self.sales_channel.name}"
    
    @property
    def effective_price(self):
        """Get effective price for this channel"""
        if self.price_override:
            return self.price_override
        
        base_price = self.product.current_price
        if self.markup_percentage > 0:
            markup = base_price * (self.markup_percentage / 100)
            return base_price + markup
        
        return base_price


# ============================================================================
# RETURN & REFUND MANAGEMENT
# ============================================================================

class ReturnRequest(TenantBaseModel, SoftDeleteMixin):
    """Return request management"""
    
    class ReturnStatus(TextChoices):
        REQUESTED = 'REQUESTED', 'Requested'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        RECEIVED = 'RECEIVED', 'Received'
        PROCESSED = 'PROCESSED', 'Processed'
        REFUNDED = 'REFUNDED', 'Refunded'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    class ReturnReason(TextChoices):
        DEFECTIVE = 'DEFECTIVE', 'Defective Item'
        WRONG_ITEM = 'WRONG_ITEM', 'Wrong Item Sent'
        NOT_AS_DESCRIBED = 'NOT_AS_DESCRIBED', 'Not as Described'
        DAMAGED_SHIPPING = 'DAMAGED_SHIPPING', 'Damaged in Shipping'
        CHANGED_MIND = 'CHANGED_MIND', 'Changed Mind'
        SIZE_ISSUE = 'SIZE_ISSUE', 'Size Issue'
        QUALITY_ISSUE = 'QUALITY_ISSUE', 'Quality Issue'
        OTHER = 'OTHER', 'Other'
    
    # Request Information
    return_number = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='return_requests')
    
    # Return Details
    reason = models.CharField(max_length=20, choices=ReturnReason.choices)
    detailed_reason = models.TextField()
    status = models.CharField(max_length=20, choices=ReturnStatus.choices, default=ReturnStatus.REQUESTED)
    
    # Financial Information
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    refund_method = models.CharField(max_length=50, blank=True)
    
    # Return Shipping
    return_shipping_label_url = models.URLField(blank=True)
    return_tracking_number = models.CharField(max_length=100, blank=True)
    
    # Processing Information
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    # Important Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    images = models.JSONField(default=list, blank=True, help_text="URLs of uploaded images")
    
    class Meta:
        db_table = 'ecommerce_return_request'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['return_number']),
        ]
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Return #{self.return_number} - {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.return_number:
            self.return_number = self.generate_return_number()
        super().save(*args, **kwargs)
    
    def generate_return_number(self):
        """Generate unique return number"""
        year = timezone.now().year
        count = ReturnRequest.objects.filter(
            tenant=self.tenant,
            requested_at__year=year
        ).count() + 1
        return f"RET-{year}-{count:06d}"


class ReturnRequestItem(TenantBaseModel):
    """Individual items in a return request"""
    
    class ItemCondition(TextChoices):
        NEW = 'NEW', 'Like New'
        GOOD = 'GOOD', 'Good Condition'
        DAMAGED = 'DAMAGED', 'Damaged'
        DEFECTIVE = 'DEFECTIVE', 'Defective'
        UNUSABLE = 'UNUSABLE', 'Unusable'
    
    class ActionTaken(TextChoices):
        REFUND = 'REFUND', 'Refund'
        EXCHANGE = 'EXCHANGE', 'Exchange'
        STORE_CREDIT = 'STORE_CREDIT', 'Store Credit'
        REJECT = 'REJECT', 'Reject'
    
    return_request = models.ForeignKey(
        ReturnRequest, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_items')
    
    # Return Quantity
    quantity_requested = models.IntegerField()
    quantity_received = models.IntegerField(default=0)
    
    # Item Condition
    condition_received = models.CharField(
        max_length=20, 
        choices=ItemCondition.choices, 
        blank=True
    )
    
    # Processing Decision
    action_taken = models.CharField(
        max_length=20, 
        choices=ActionTaken.choices, 
        blank=True
    )
    
    # Financial
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_return_request_item'
    
    def __str__(self):
        return f"{self.order_item.product_name} x {self.quantity_requested}"


# ============================================================================
# BUSINESS LOGIC MANAGER
# ============================================================================

class EcommerceManager:
    """Enhanced manager class for e-commerce business logic"""
    
    @staticmethod
    def create_order_from_cart(cart, customer_info, shipping_info, payment_info):
        """Create order from cart with comprehensive error handling"""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                # Validate cart
                if not cart.items.exists():
                    raise ValueError("Cart is empty")
                
                # Check inventory availability
                for item in cart.items.all():
                    if item.product.track_quantity and not item.product.is_in_stock:
                        raise ValueError(f"Product {item.product.title} is out of stock")
                
                # Create order
                order = Order.objects.create(
                    tenant=cart.tenant,
                    customer=cart.customer,
                    customer_email=customer_info.get('email'),
                    customer_phone=customer_info.get('phone', ''),
                    
                    # Financial
                    currency=cart.currency,
                    subtotal=cart.subtotal,
                    tax_amount=cart.tax_amount,
                    shipping_amount=cart.shipping_amount,
                    discount_amount=cart.discount_amount,
                    total_amount=cart.total_amount,
                    
                    # Applied discounts
                    applied_discounts=cart.applied_coupons,
                    discount_codes=cart.discount_codes,
                    
                    # Billing address
                    billing_first_name=customer_info.get('first_name'),
                    billing_last_name=customer_info.get('last_name'),
                    billing_company=customer_info.get('company', ''),
                    billing_address_line1=customer_info.get('address1'),
                    billing_address_line2=customer_info.get('address2', ''),
                    billing_city=customer_info.get('city'),
                    billing_state=customer_info.get('state'),
                    billing_postal_code=customer_info.get('postal_code'),
                    billing_country=customer_info.get('country'),
                    
                    # Shipping address
                    shipping_first_name=shipping_info.get('first_name'),
                    shipping_last_name=shipping_info.get('last_name'),
                    shipping_company=shipping_info.get('company', ''),
                    shipping_address_line1=shipping_info.get('address1'),
                    shipping_address_line2=shipping_info.get('address2', ''),
                    shipping_city=shipping_info.get('city'),
                    shipping_state=shipping_info.get('state'),
                    shipping_postal_code=shipping_info.get('postal_code'),
                    shipping_country=shipping_info.get('country'),
                    
                    # Payment info
                    payment_method=payment_info.get('method'),
                    payment_gateway=payment_info.get('gateway'),
                    
                    # Source
                    source_cart=cart,
                    source_name=customer_info.get('source', 'web'),
                )
                
                # Create order items from cart items
                for cart_item in cart.items.select_related('product', 'variant'):
                    OrderItem.objects.create(
                        tenant=cart.tenant,
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        product_name=cart_item.product.title,
                        product_sku=cart_item.variant.sku if cart_item.variant else cart_item.product.sku,
                        variant_title=cart_item.variant.title if cart_item.variant else '',
                        variant_attributes=cart_item.variant.attributes if cart_item.variant else {},
                        quantity=cart_item.quantity,
                        unit_price=cart_item.unit_price,
                        custom_attributes=cart_item.custom_attributes,
                        requires_shipping=cart_item.variant.requires_shipping if cart_item.variant else cart_item.product.requires_shipping,
                        weight=cart_item.variant.weight if cart_item.variant else cart_item.product.weight,
                    )
                
                # Mark cart as completed
                cart.status = Cart.CartStatus.COMPLETED
                cart.save()
                
                # Update discount usage counts
                for coupon_code in cart.discount_codes:
                    try:
                        discount = Discount.objects.get(tenant=cart.tenant, code=coupon_code)
                        discount.current_uses += 1
                        discount.save()
                        
                        # Create usage record
                        CouponUsage.objects.create(
                            tenant=cart.tenant,
                            discount=discount,
                            customer=cart.customer,
                            order=order,
                            discount_amount=cart.discount_amount  # This could be improved to track individual discount amounts
                        )
                    except Discount.DoesNotExist:
                        pass  # Discount might have been deleted
                
                return order
                
        except Exception as e:
            raise Exception(f"Failed to create order: {str(e)}")
    
    @staticmethod
    def calculate_shipping_rates(cart, shipping_address):
        """Calculate available shipping rates for cart"""
        country = shipping_address.get('country')
        state = shipping_address.get('state')
        postal_code = shipping_address.get('postal_code')
        
        # Find applicable shipping zones
        zones = ShippingZone.objects.filter(
            tenant=cart.tenant,
            is_active=True
        )
        
        applicable_zones = []
        for zone in zones:
            if country in zone.countries:
                # Check state/postal code if specified
                if zone.states and state not in zone.states:
                    continue
                if zone.postal_codes:
                    # Simple postal code matching (can be enhanced with regex)
                    postal_match = any(
                        postal_code.startswith(pattern) 
                        for pattern in zone.postal_codes
                    )
                    if not postal_match:
                        continue
                
                applicable_zones.append(zone)
        
        # Get shipping methods for applicable zones
        shipping_rates = []
        total_weight = sum(
            (item.variant.weight if item.variant else item.product.weight) or 0
            for item in cart.items.select_related('product', 'variant')
        )
        
        for zone in applicable_zones:
            methods = zone.shipping_methods.filter(is_active=True)
            for method in methods:
                rate = method.calculate_rate(cart.subtotal, total_weight)
                if rate is not None:
                    shipping_rates.append({
                        'method_id': method.id,
                        'name': method.name,
                        'description': method.description,
                        'rate': rate,
                        'estimated_days_min': method.estimated_delivery_days_min,
                        'estimated_days_max': method.estimated_delivery_days_max,
                    })
        
        return sorted(shipping_rates, key=lambda x: x['rate'])
    
    @staticmethod
    def apply_discount_to_cart(cart, discount_code):
        """Apply discount to cart with comprehensive validation"""
        try:
            discount = Discount.objects.get(
                tenant=cart.tenant,
                code=discount_code,
                is_active=True
            )
            
            can_apply, message = discount.can_apply_to_cart(cart)
            if not can_apply:
                return False, message
            
            # Check if already applied
            if discount_code in cart.discount_codes:
                return False, "Discount already applied"
            
            # Check customer usage limit
            if discount.usage_limit_per_customer and cart.customer:
                customer_usage = CouponUsage.objects.filter(
                    tenant=cart.tenant,
                    discount=discount,
                    customer=cart.customer
                ).count()
                
                if customer_usage >= discount.usage_limit_per_customer:
                    return False, "Customer usage limit reached for this discount"
            
            # Calculate discount amount
            discount_amount = discount.calculate_discount_amount(cart)
            
            if discount_amount <= 0:
                return False, "Discount amount is zero"
            
            # Apply discount
            cart.discount_amount += discount_amount
            cart.discount_codes.append(discount_code)
            cart.applied_coupons.append({
                'code': discount_code,
                'title': discount.title,
                'amount': float(discount_amount),
                'type': discount.discount_type
            })
            
            # Recalculate totals
            cart.calculate_totals()
            
            return True, f"Discount applied: {discount.title} (-${discount_amount})"
            
        except Discount.DoesNotExist:
            return False, "Invalid discount code"
        except Exception as e:
            return False, f"Error applying discount: {str(e)}"
    
    @staticmethod
    def remove_discount_from_cart(cart, discount_code):
        """Remove discount from cart"""
        try:
            if discount_code not in cart.discount_codes:
                return False, "Discount not applied to cart"
            
            # Remove from codes list
            cart.discount_codes.remove(discount_code)
            
            # Remove from applied coupons and recalculate discount amount
            cart.applied_coupons = [
                coupon for coupon in cart.applied_coupons 
                if coupon['code'] != discount_code
            ]
            
            # Recalculate discount amount
            cart.discount_amount = sum(
                Decimal(str(coupon['amount'])) 
                for coupon in cart.applied_coupons
            )
            
            # Recalculate totals
            cart.calculate_totals()
            
            return True, "Discount removed successfully"
            
        except Exception as e:
            return False, f"Error removing discount: {str(e)}"
    
    @staticmethod
    def get_product_recommendations(product, limit=4):
        """Get enhanced product recommendations"""
        recommendations = []
        
        try:
            # Get products from same collections
            if product.collections.exists():
                collection_products = EcommerceProduct.objects.filter(
                    tenant=product.tenant,
                    collections__in=product.collections.all(),
                    is_active=True,
                    is_published=True,
                    status='PUBLISHED'
                ).exclude(id=product.id).distinct()[:limit]
                
                recommendations.extend(collection_products)
            
            # Fill remaining slots with products from same category
            if len(recommendations) < limit and product.inventory_product:
                remaining_slots = limit - len(recommendations)
                category_products = EcommerceProduct.objects.filter(
                    tenant=product.tenant,
                    inventory_product__category=product.inventory_product.category,
                    is_active=True,
                    is_published=True,
                    status='PUBLISHED'
                ).exclude(id=product.id).exclude(
                    id__in=[p.id for p in recommendations]
                )[:remaining_slots]
                
                recommendations.extend(category_products)
            
            # Fill remaining slots with featured products
            if len(recommendations) < limit:
                remaining_slots = limit - len(recommendations)
                featured_products = EcommerceProduct.objects.filter(
                    tenant=product.tenant,
                    is_featured=True,
                    is_active=True,
                    is_published=True,
                    status='PUBLISHED'
                ).exclude(id=product.id).exclude(
                    id__in=[p.id for p in recommendations]
                )[:remaining_slots]
                
                recommendations.extend(featured_products)
            
            return recommendations[:limit]
            
        except Exception as e:
            # Return empty list on error
            return []
    
    @staticmethod
    def process_gift_card_payment(order, gift_card_code, amount=None):
        """Process gift card payment for an order"""
        try:
            gift_card = GiftCard.objects.get(
                tenant=order.tenant,
                code=gift_card_code
            )
            
            if not gift_card.is_active:
                return False, "Gift card is not active"
            
            # Determine amount to charge
            charge_amount = min(
                amount or order.total_amount,
                gift_card.current_balance,
                order.total_amount
            )
            
            if charge_amount <= 0:
                return False, "Invalid charge amount"
            
            # Create transaction record
            transaction = GiftCardTransaction.objects.create(
                tenant=order.tenant,
                gift_card=gift_card,
                order=order,
                transaction_type=GiftCardTransaction.TransactionType.REDEMPTION,
                amount=charge_amount,
                balance_before=gift_card.current_balance,
                balance_after=gift_card.current_balance - charge_amount
            )
            
            # Update gift card balance
            gift_card.current_balance -= charge_amount
            gift_card.times_used += 1
            
            if not gift_card.first_used_at:
                gift_card.first_used_at = timezone.now()
            gift_card.last_used_at = timezone.now()
            
            if gift_card.current_balance <= 0:
                gift_card.status = GiftCard.Status.REDEEMED
            
            gift_card.save()
            
            return True, f"Gift card charged ${charge_amount}"
            
        except GiftCard.DoesNotExist:
            return False, "Invalid gift card code"
        except Exception as e:
            return False, f"Error processing gift card: {str(e)}"
    
    @staticmethod
    def update_product_analytics(product):
        """Update product analytics"""
        try:
            analytics, created = ProductAnalytics.objects.get_or_create(
                tenant=product.tenant,
                product=product
            )
            
            # Update sales statistics
            order_items = OrderItem.objects.filter(
                tenant=product.tenant,
                product=product,
                order__status__in=['COMPLETED', 'DELIVERED']
            )
            
            analytics.times_purchased = order_items.count()
            analytics.total_revenue = order_items.aggregate(
                total=models.Sum('total_price')
            )['total'] or Decimal('0.00')
            
            if analytics.times_purchased > 0:
                analytics.average_order_value = analytics.total_revenue / analytics.times_purchased
            
            # Update cart statistics
            analytics.times_added_to_cart = CartItem.objects.filter(
                tenant=product.tenant,
                product=product
            ).count()
            
            # Calculate conversion rate
            if analytics.total_views > 0:
                analytics.conversion_rate = (analytics.times_purchased / analytics.total_views) * 100
            
            # Calculate cart abandonment rate
            if analytics.times_added_to_cart > 0:
                completed_purchases = analytics.times_purchased
                analytics.cart_abandonment_rate = ((analytics.times_added_to_cart - completed_purchases) / analytics.times_added_to_cart) * 100
            
            analytics.save()
            
            return analytics
            
        except Exception as e:
            # Log error but don't raise exception
            print(f"Error updating product analytics: {str(e)}")
            return None


# ============================================================================
# SIGNAL HANDLERS (Optional - for automatic updates)
# ============================================================================

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=OrderItem)
def update_product_sales_count(sender, instance, created, **kwargs):
    """Update product sales count when order item is created"""
    if created and instance.order.status in ['COMPLETED', 'DELIVERED']:
        product = instance.product
        product.sales_count = OrderItem.objects.filter(
            tenant=product.tenant,
            product=product,
            order__status__in=['COMPLETED', 'DELIVERED']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        product.save(update_fields=['sales_count'])

@receiver(post_save, sender=ProductReview)
def update_product_rating(sender, instance, created, **kwargs):
    """Update product average rating when review is created/updated"""
    if instance.status == ProductReview.ReviewStatus.APPROVED:
        product = instance.product
        reviews = ProductReview.objects.filter(
            tenant=product.tenant,
            product=product,
            status=ProductReview.ReviewStatus.APPROVED
        )
        
        product.review_count = reviews.count()
        if product.review_count > 0:
            product.average_rating = reviews.aggregate(
                avg=models.Avg('rating')
            )['avg'] or Decimal('0.00')
        else:
            product.average_rating = Decimal('0.00')
        
        product.save(update_fields=['review_count', 'average_rating'])

@receiver(post_save, sender=Cart)
def create_abandoned_cart_tracking(sender, instance, created, **kwargs):
    """Create abandoned cart tracking when cart becomes abandoned"""
    if not created and instance.status == Cart.CartStatus.ABANDONED:
        abandoned_cart, created = AbandonedCart.objects.get_or_create(
            tenant=instance.tenant,
            cart=instance
        )
        if created:
            # Initialize tracking data
            abandoned_cart.save()
