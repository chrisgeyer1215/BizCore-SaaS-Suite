# apps/ecommerce/models/products.py

"""
Product and product variant models for e-commerce
"""

from django.db import models
from django.contrib.postgres.search import SearchVector
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from decimal import Decimal
import uuid

from .base import (
    EcommerceBaseModel, 
    SEOMixin, 
    PricingMixin, 
    InventoryMixin, 
    VisibilityMixin, 
    TagMixin,
    AuditMixin
)
from .managers import PublishedProductManager


class EcommerceProduct(EcommerceBaseModel, SEOMixin, PricingMixin, InventoryMixin, 
                      VisibilityMixin, TagMixin, AuditMixin):
    """Enhanced e-commerce product model with comprehensive features"""
    
    class ProductType(models.TextChoices):
        PHYSICAL = 'PHYSICAL', 'Physical Product'
        DIGITAL = 'DIGITAL', 'Digital Product'
        SERVICE = 'SERVICE', 'Service'
        SUBSCRIPTION = 'SUBSCRIPTION', 'Subscription'
        GIFT_CARD = 'GIFT_CARD', 'Gift Card'
        BUNDLE = 'BUNDLE', 'Product Bundle'
        VARIABLE = 'VARIABLE', 'Variable Product'
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField()
    short_description = models.TextField(max_length=500, blank=True)
    
    # Product Identification
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=50, blank=True)
    product_code = models.CharField(max_length=50, blank=True)
    
    # Product Type and Classification
    product_type = models.CharField(
        max_length=20, 
        choices=ProductType.choices, 
        default=ProductType.PHYSICAL
    )
    brand = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    
    # URL and SEO
    url_handle = models.SlugField(max_length=255, unique=True)
    
    # Product Options and Variants
    has_variants = models.BooleanField(default=False)
    options = models.ManyToManyField('ProductOption', blank=True)
    
    # Pricing Information (inherited from PricingMixin)
    # - price, compare_at_price, cost_price, currency
    
    # Inventory Management (inherited from InventoryMixin)
    # - track_quantity, inventory_policy, stock_quantity, etc.
    
    # Categorization
    primary_collection = models.ForeignKey(
        'Collection', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='primary_products'
    )
    collections = models.ManyToManyField(
        'Collection', 
        through='CollectionProduct', 
        blank=True,
        related_name='products'
    )
    
    # Integration with Inventory Module
    inventory_product = models.OneToOneField(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecommerce_product'
    )
    
    # Shipping Information
    requires_shipping = models.BooleanField(default=True)
    is_digital_product = models.BooleanField(default=False)
    shipping_profile = models.ForeignKey(
        'ShippingProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Tax Information
    is_taxable = models.BooleanField(default=True)
    tax_code = models.CharField(max_length=50, blank=True)
    
    # Product Media
    featured_image = models.ImageField(upload_to='products/featured/', blank=True, null=True)
    gallery_images = models.JSONField(default=list, blank=True)
    product_videos = models.JSONField(default=list, blank=True)
    
    # Product Specifications and Attributes
    specifications = models.JSONField(default=dict, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Sales and Performance Data
    sales_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    wishlist_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Date Information
    available_date = models.DateTimeField(null=True, blank=True)
    discontinued_date = models.DateTimeField(null=True, blank=True)
    
    # Search and Performance
    search_vector = SearchVector('title', 'description', 'sku', 'brand')
    
    # Managers
    objects = models.Manager()
    published = PublishedProductManager()
    
    class Meta:
        db_table = 'ecommerce_products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'is_published']),
            models.Index(fields=['tenant', 'sku']),
            models.Index(fields=['tenant', 'product_type']),
            models.Index(fields=['tenant', 'brand']),
            models.Index(fields=['tenant', 'primary_collection']),
            models.Index(fields=['tenant', 'price']),
            models.Index(fields=['tenant', 'sales_count']),
            models.Index(fields=['url_handle']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'sku'], name='unique_product_sku_per_tenant'),
            models.UniqueConstraint(fields=['tenant', 'url_handle'], name='unique_product_handle_per_tenant'),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Generate URL handle if not provided
        if not self.url_handle:
            self.url_handle = slugify(self.title)
            
        # Ensure URL handle is unique
        if self.pk:  # Updating existing product
            existing = EcommerceProduct.objects.filter(
                tenant=self.tenant, 
                url_handle=self.url_handle
            ).exclude(pk=self.pk)
        else:  # Creating new product
            existing = EcommerceProduct.objects.filter(
                tenant=self.tenant, 
                url_handle=self.url_handle
            )
            
        if existing.exists():
            base_handle = self.url_handle
            counter = 1
            while existing.exists():
                self.url_handle = f"{base_handle}-{counter}"
                existing = EcommerceProduct.objects.filter(
                    tenant=self.tenant, 
                    url_handle=self.url_handle
                )
                if self.pk:
                    existing = existing.exclude(pk=self.pk)
                counter += 1
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Validate price fields
        if self.compare_at_price and self.compare_at_price <= self.price:
            raise ValidationError({
                'compare_at_price': 'Compare at price must be higher than selling price'
            })
        
        # Validate digital product settings
        if self.product_type == self.ProductType.DIGITAL:
            self.is_digital_product = True
            self.requires_shipping = False
            self.track_quantity = False
    
    def get_absolute_url(self):
        """Get product detail URL"""
        return reverse('ecommerce:product_detail', kwargs={'slug': self.url_handle})
    
    @property
    def current_price(self):
        """Get current selling price"""
        return self.price
    
    @property
    def formatted_price(self):
        """Get formatted price string"""
        # This would use the tenant's currency formatting settings
        return f"${self.price:.2f}"
    
    @property
    def is_available(self):
        """Check if product is available for purchase"""
        if not self.is_visible:
            return False
        if self.track_quantity and not self.is_in_stock:
            return False
        return True
    
    @property
    def main_image(self):
        """Get main product image"""
        if self.featured_image:
            return self.featured_image
        if self.gallery_images:
            return self.gallery_images[0]
        return None
    
    def add_to_collection(self, collection, position=None, is_featured=False):
        """Add product to collection"""
        from .collections import CollectionProduct
        
        if position is None:
            last_position = CollectionProduct.objects.filter(
                tenant=self.tenant,
                collection=collection
            ).aggregate(
                max_position=models.Max('position')
            )['max_position'] or 0
            position = last_position + 1
        
        CollectionProduct.objects.get_or_create(
            tenant=self.tenant,
            collection=collection,
            product=self,
            defaults={
                'position': position,
                'is_featured': is_featured
            }
        )
    
    def remove_from_collection(self, collection):
        """Remove product from collection"""
        from .collections import CollectionProduct
        
        CollectionProduct.objects.filter(
            tenant=self.tenant,
            collection=collection,
            product=self
        ).delete()
    
    def update_sales_count(self, quantity=1):
        """Update sales count"""
        self.sales_count += quantity
        self.save(update_fields=['sales_count'])
    
    def update_rating(self):
        """Update average rating from reviews"""
        from .reviews import ProductReview
        
        reviews = ProductReview.objects.filter(
            tenant=self.tenant,
            product=self,
            status='APPROVED'
        )
        
        if reviews.exists():
            avg_rating = reviews.aggregate(
                avg=models.Avg('rating')
            )['avg'] or Decimal('0.00')
            self.average_rating = round(avg_rating, 2)
            self.review_count = reviews.count()
        else:
            self.average_rating = Decimal('0.00')
            self.review_count = 0
        
        self.save(update_fields=['average_rating', 'review_count'])
    
    def get_variant_options(self):
        """Get available variant options"""
        if not self.has_variants:
            return {}
        
        options = {}
        for variant in self.variants.filter(is_active=True):
            for option in variant.option_values.all():
                if option.option.name not in options:
                    options[option.option.name] = []
                if option.value not in options[option.option.name]:
                    options[option.option.name].append(option.value)
        
        return options
    
    def sync_with_inventory(self):
        """Sync with inventory module"""
        if self.inventory_product:
            # Update stock quantity from inventory
            stock_items = self.inventory_product.stock_items.filter(
                warehouse__is_active=True
            )
            total_stock = sum(item.available_stock for item in stock_items)
            self.stock_quantity = total_stock
            self.save(update_fields=['stock_quantity'])


class ProductVariant(EcommerceBaseModel, PricingMixin, InventoryMixin, AuditMixin):
    """Product variants for products with options"""
    
    # Parent Product
    ecommerce_product = models.ForeignKey(
        EcommerceProduct,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    
    # Variant Information
    title = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=50, blank=True)
    
    # Option Values
    option_values = models.ManyToManyField('ProductOptionValue')
    
    # Variant-specific Pricing (inherits from PricingMixin)
    # These override the parent product's pricing if set
    
    # Variant-specific Inventory (inherits from InventoryMixin)
    
    # Integration with Inventory Module
    inventory_variation = models.OneToOneField(
        'inventory.ProductVariation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecommerce_variant'
    )
    
    # Variant Media
    image = models.ImageField(upload_to='products/variants/', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_product_variants'
        ordering = ['position', 'title']
        indexes = [
            models.Index(fields=['tenant', 'ecommerce_product', 'is_active']),
            models.Index(fields=['tenant', 'sku']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'sku'], 
                name='unique_variant_sku_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.ecommerce_product.title} - {self.title}"
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Price validation
        if self.compare_at_price and self.price and self.compare_at_price <= self.price:
            raise ValidationError({
                'compare_at_price': 'Compare at price must be higher than selling price'
            })
    
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
            return self.available_quantity > 0
        return True  # CONTINUE policy allows overselling
    
    @property
    def option_summary(self):
        """Get summary of option values"""
        return " / ".join([
            f"{ov.option.name}: {ov.value}" 
            for ov in self.option_values.all()
        ])
    
    def sync_with_inventory(self):
        """Sync with inventory module"""
        if self.inventory_variation:
            self.stock_quantity = self.inventory_variation.available_stock
            self.save(update_fields=['stock_quantity'])


class ProductOption(EcommerceBaseModel):
    """Product options (e.g., Size, Color, Material)"""
    
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_product_options'
        ordering = ['position', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'], 
                name='unique_option_name_per_tenant'
            ),
        ]
    
    def __str__(self):
        return self.display_name or self.name


class ProductOptionValue(EcommerceBaseModel):
    """Values for product options (e.g., Small, Medium, Large for Size)"""
    
    option = models.ForeignKey(
        ProductOption,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.CharField(max_length=100)
    display_value = models.CharField(max_length=100, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    # Visual representation for colors, patterns, etc.
    color_code = models.CharField(max_length=7, blank=True)  # Hex color
    image = models.ImageField(upload_to='options/', blank=True, null=True)
    
    class Meta:
        db_table = 'ecommerce_product_option_values'
        ordering = ['option', 'position', 'value']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'option', 'value'], 
                name='unique_option_value_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.option.name}: {self.display_value or self.value}"


class ProductImage(EcommerceBaseModel):
    """Product images with enhanced metadata"""
    
    product = models.ForeignKey(
        EcommerceProduct,
        on_delete=models.CASCADE,
        related_name='images'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='images'
    )
    
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    # Image metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # in bytes
    
    # Settings
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_product_images'
        ordering = ['product', 'position']
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['tenant', 'variant', 'is_active']),
        ]
    
    def __str__(self):
        return f"Image for {self.product.title}"
    
    def save(self, *args, **kwargs):
        # Auto-generate alt text if not provided
        if not self.alt_text and self.product:
            self.alt_text = f"Image of {self.product.title}"
        
        super().save(*args, **kwargs)


class ProductTag(EcommerceBaseModel):
    """Product tags for categorization and filtering"""
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, blank=True)  # Hex color
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ecommerce_product_tags'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'], 
                name='unique_tag_name_per_tenant'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'slug'], 
                name='unique_tag_slug_per_tenant'
            ),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductBundle(EcommerceBaseModel, PricingMixin, VisibilityMixin, SEOMixin):
    """Product bundles - packages of multiple products sold together"""
    
    class BundleType(models.TextChoices):
        FIXED = 'FIXED', 'Fixed Bundle'
        DYNAMIC = 'DYNAMIC', 'Dynamic Bundle'
        UPSELL = 'UPSELL', 'Upsell Bundle'
        CROSS_SELL = 'CROSS_SELL', 'Cross-sell Bundle'
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    bundle_type = models.CharField(max_length=20, choices=BundleType.choices, default=BundleType.FIXED)
    
    # Bundle products
    products = models.ManyToManyField(EcommerceProduct, through='BundleItem')
    
    # Pricing
    pricing_strategy = models.CharField(
        max_length=20,
        choices=[
            ('FIXED_PRICE', 'Fixed Bundle Price'),
            ('PERCENTAGE_DISCOUNT', 'Percentage Discount'),
            ('FIXED_DISCOUNT', 'Fixed Amount Discount'),
            ('SUM_OF_PARTS', 'Sum of Individual Prices'),
        ],
        default='FIXED_PRICE'
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Bundle settings
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    
    # Media
    image = models.ImageField(upload_to='bundles/', blank=True, null=True)
    
    class Meta:
        db_table = 'ecommerce_product_bundles'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def individual_total(self):
        """Calculate total of individual product prices"""
        total = Decimal('0.00')
        for item in self.bundle_items.all():
            total += item.product.price * item.quantity
        return total
    
    @property
    def bundle_savings(self):
        """Calculate savings from bundle pricing"""
        if self.pricing_strategy == 'FIXED_PRICE':
            return self.individual_total - self.price
        elif self.pricing_strategy == 'PERCENTAGE_DISCOUNT':
            return self.individual_total * (self.discount_percentage / 100)
        elif self.pricing_strategy == 'FIXED_DISCOUNT':
            return self.discount_amount
        return Decimal('0.00')
    
    def calculate_bundle_price(self):
        """Calculate bundle price based on strategy"""
        individual_total = self.individual_total
        
        if self.pricing_strategy == 'FIXED_PRICE':
            return self.price
        elif self.pricing_strategy == 'PERCENTAGE_DISCOUNT':
            discount = individual_total * (self.discount_percentage / 100)
            return individual_total - discount
        elif self.pricing_strategy == 'FIXED_DISCOUNT':
            return max(Decimal('0.00'), individual_total - self.discount_amount)
        else:  # SUM_OF_PARTS
            return individual_total


class BundleItem(EcommerceBaseModel):
    """Items within a product bundle"""
    
    bundle = models.ForeignKey(
        ProductBundle,
        on_delete=models.CASCADE,
        related_name='bundle_items'
    )
    product = models.ForeignKey(
        EcommerceProduct,
        on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    quantity = models.PositiveIntegerField(default=1)
    is_optional = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    
    # Custom pricing for this item in the bundle
    custom_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    class Meta:
        db_table = 'ecommerce_bundle_items'
        ordering = ['bundle', 'position']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'bundle', 'product'], 
                name='unique_bundle_product_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.bundle.name} - {self.product.title}"
    
    @property
    def effective_price(self):
        """Get effective price for this bundle item"""
        if self.custom_price:
            return self.custom_price
        if self.variant:
            return self.variant.effective_price
        return self.product.price


class ProductSEO(EcommerceBaseModel):
    """Extended SEO settings for products"""
    
    product = models.OneToOneField(
        EcommerceProduct,
        on_delete=models.CASCADE,
        related_name='seo_settings'
    )
    
    # Advanced SEO
    focus_keyword = models.CharField(max_length=100, blank=True)
    meta_robots = models.CharField(
        max_length=100,
        default='index,follow',
        help_text='Robot instructions (e.g., index,follow, noindex,nofollow)'
    )
    
    # Social Media
    facebook_title = models.CharField(max_length=255, blank=True)
    facebook_description = models.TextField(max_length=300, blank=True)
    facebook_image = models.ImageField(upload_to='seo/facebook/', blank=True, null=True)
    
    twitter_title = models.CharField(max_length=255, blank=True)
    twitter_description = models.TextField(max_length=200, blank=True)
    twitter_image = models.ImageField(upload_to='seo/twitter/', blank=True, null=True)
    twitter_card_type = models.CharField(
        max_length=20,
        choices=[
            ('summary', 'Summary'),
            ('summary_large_image', 'Summary Large Image'),
            ('app', 'App'),
            ('player', 'Player'),
        ],
        default='summary_large_image'
    )
    
    # JSON-LD Structured Data
    product_schema = models.JSONField(default=dict, blank=True)
    breadcrumb_schema = models.JSONField(default=dict, blank=True)
    
    # Performance
    preload_images = models.BooleanField(default=False)
    lazy_load_images = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_product_seo'
    
    def __str__(self):
        return f"SEO for {self.product.title}"
    
    def generate_product_schema(self):
        """Generate Product JSON-LD schema"""
        product = self.product
        
        schema = {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": product.title,
            "description": product.description,
            "sku": product.sku,
            "brand": {
                "@type": "Brand",
                "name": product.brand
            } if product.brand else None,
            "offers": {
                "@type": "Offer",
                "price": str(product.price),
                "priceCurrency": product.currency,
                "availability": "https://schema.org/InStock" if product.is_in_stock else "https://schema.org/OutOfStock",
                "url": product.get_absolute_url()
            }
        }
        
        # Add images if available
        if product.main_image:
            schema["image"] = [product.main_image.url]
        
        # Add reviews if available
        if product.review_count > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(product.average_rating),
                "reviewCount": product.review_count,
                "bestRating": "5",
                "worstRating": "1"
            }
        
        return schema


class ProductMetric(EcommerceBaseModel):
    """Product performance metrics and analytics"""
    
    product = models.OneToOneField(
        EcommerceProduct,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # View metrics
    total_views = models.PositiveIntegerField(default=0)
    unique_views = models.PositiveIntegerField(default=0)
    views_today = models.PositiveIntegerField(default=0)
    views_this_week = models.PositiveIntegerField(default=0)
    views_this_month = models.PositiveIntegerField(default=0)
    
    # Sales metrics
    total_orders = models.PositiveIntegerField(default=0)
    total_quantity_sold = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Engagement metrics
    add_to_cart_count = models.PositiveIntegerField(default=0)
    wishlist_add_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Conversion metrics
    conversion_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    cart_abandonment_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Last updated
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecommerce_product_metrics'
    
    def __str__(self):
        return f"Metrics for {self.product.title}"
    
    def calculate_conversion_rate(self):
        """Calculate conversion rate"""
        if self.total_views > 0:
            self.conversion_rate = (self.total_orders / self.total_views) * 100
        else:
            self.conversion_rate = Decimal('0.00')
        self.save(update_fields=['conversion_rate'])
    
    def update_view_metrics(self):
        """Update view-related metrics"""
        # This would typically be called by analytics services
        pass
    
    def update_sales_metrics(self):
        """Update sales-related metrics"""
        from .orders import OrderItem
        
        # Calculate from order items
        order_items = OrderItem.objects.filter(
            tenant=self.tenant,
            product=self.product,
            order__status__in=['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED']
        )
        
        metrics = order_items.aggregate(
            total_orders=models.Count('order', distinct=True),
            total_quantity=models.Sum('quantity'),
            total_revenue=models.Sum(
                models.F('quantity') * models.F('unit_price'),
                output_field=models.DecimalField()
            )
        )
        
        self.total_orders = metrics['total_orders'] or 0
        self.total_quantity_sold = metrics['total_quantity'] or 0
        self.total_revenue = metrics['total_revenue'] or Decimal('0.00')
        
        self.save(update_fields=[
            'total_orders', 
            'total_quantity_sold', 
            'total_revenue'
        ])