# apps/ecommerce/models/base.py

"""
Base models and mixins for e-commerce functionality
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid
from enum import TextChoices

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class EcommerceBaseModel(TenantBaseModel):
    """Base model for all e-commerce models with common fields"""
    
    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Abstract model with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SEOMixin(models.Model):
    """SEO fields mixin for e-commerce models"""
    
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(max_length=320, blank=True)
    seo_keywords = models.TextField(blank=True)
    canonical_url = models.URLField(blank=True)
    
    # OpenGraph and social media
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.TextField(max_length=300, blank=True)
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)
    
    # Twitter Card
    twitter_title = models.CharField(max_length=255, blank=True)
    twitter_description = models.TextField(max_length=200, blank=True)
    twitter_image = models.ImageField(upload_to='seo/twitter_images/', blank=True, null=True)
    
    # JSON-LD structured data
    structured_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True


class PricingMixin(models.Model):
    """Pricing fields mixin with multi-currency support"""
    
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        help_text="Current selling price"
    )
    compare_at_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Original price for comparison (strikethrough price)"
    )
    cost_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost of goods sold"
    )
    currency = models.CharField(max_length=3, default='USD')
    
    class Meta:
        abstract = True
    
    @property
    def is_on_sale(self):
        """Check if item is on sale"""
        return self.compare_at_price and self.compare_at_price > self.price
    
    @property
    def discount_amount(self):
        """Calculate discount amount"""
        if self.is_on_sale:
            return self.compare_at_price - self.price
        return Decimal('0.00')
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_on_sale and self.compare_at_price > 0:
            return ((self.compare_at_price - self.price) / self.compare_at_price) * 100
        return Decimal('0.00')
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price and self.price > 0:
            return ((self.price - self.cost_price) / self.price) * 100
        return Decimal('0.00')


class InventoryMixin(models.Model):
    """Inventory tracking mixin"""
    
    class InventoryPolicy(TextChoices):
        DENY = 'DENY', 'Deny purchases when out of stock'
        CONTINUE = 'CONTINUE', 'Continue selling when out of stock'
        
    class FulfillmentService(TextChoices):
        MANUAL = 'MANUAL', 'Manual fulfillment'
        AUTOMATIC = 'AUTOMATIC', 'Automatic fulfillment'
        THIRD_PARTY = 'THIRD_PARTY', 'Third party fulfillment'
    
    # Inventory tracking
    track_quantity = models.BooleanField(
        default=True, 
        help_text="Whether to track inventory for this item"
    )
    inventory_policy = models.CharField(
        max_length=20, 
        choices=InventoryPolicy.choices, 
        default=InventoryPolicy.DENY
    )
    fulfillment_service = models.CharField(
        max_length=20, 
        choices=FulfillmentService.choices, 
        default=FulfillmentService.MANUAL
    )
    
    # Stock information
    stock_quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    committed_quantity = models.IntegerField(default=0)
    incoming_quantity = models.IntegerField(default=0)
    
    # Inventory settings
    low_stock_threshold = models.IntegerField(
        default=10, 
        help_text="Alert when stock falls below this level"
    )
    out_of_stock_threshold = models.IntegerField(
        default=0, 
        help_text="Consider out of stock when below this level"
    )
    
    # Weight and dimensions for shipping
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        null=True, 
        blank=True,
        help_text="Weight in grams"
    )
    length = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Length in cm"
    )
    width = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Width in cm"
    )
    height = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Height in cm"
    )
    
    class Meta:
        abstract = True
    
    @property
    def available_quantity(self):
        """Calculate available quantity"""
        if not self.track_quantity:
            return float('inf')  # Unlimited if not tracking
        return max(0, self.stock_quantity - self.reserved_quantity - self.committed_quantity)
    
    @property
    def is_in_stock(self):
        """Check if item is in stock"""
        if self.inventory_policy == self.InventoryPolicy.CONTINUE:
            return True
        return self.available_quantity > self.out_of_stock_threshold
    
    @property
    def is_low_stock(self):
        """Check if item is low in stock"""
        if not self.track_quantity:
            return False
        return self.available_quantity <= self.low_stock_threshold
    
    @property
    def needs_restock(self):
        """Check if item needs restocking"""
        return self.is_low_stock or not self.is_in_stock


class VisibilityMixin(models.Model):
    """Visibility and publishing mixin"""
    
    class PublishStatus(TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'
        HIDDEN = 'HIDDEN', 'Hidden'
    
    status = models.CharField(
        max_length=20, 
        choices=PublishStatus.choices, 
        default=PublishStatus.DRAFT
    )
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Publishing schedule
    published_at = models.DateTimeField(null=True, blank=True)
    publish_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Schedule publication for future date"
    )
    unpublish_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Schedule unpublication for future date"
    )
    
    # Visibility settings
    is_visible_in_search = models.BooleanField(default=True)
    is_visible_in_storefront = models.BooleanField(default=True)
    requires_authentication = models.BooleanField(default=False)
    
    class Meta:
        abstract = True
    
    @property
    def is_visible(self):
        """Check if item is currently visible"""
        now = timezone.now()
        
        # Check basic visibility
        if not self.is_active or not self.is_published:
            return False
            
        # Check publish schedule
        if self.publish_date and now < self.publish_date:
            return False
            
        if self.unpublish_date and now > self.unpublish_date:
            return False
            
        return True
    
    def publish(self):
        """Publish the item"""
        self.is_published = True
        self.status = self.PublishStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save()
    
    def unpublish(self):
        """Unpublish the item"""
        self.is_published = False
        self.status = self.PublishStatus.DRAFT
        self.save()
    
    def archive(self):
        """Archive the item"""
        self.is_published = False
        self.status = self.PublishStatus.ARCHIVED
        self.save()


class SortableMixin(models.Model):
    """Sortable mixin for ordering items"""
    
    sort_order = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True


class TagMixin(models.Model):
    """Tag system mixin"""
    
    tags = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of tags for categorization and search"
    )
    
    class Meta:
        abstract = True
    
    def add_tag(self, tag):
        """Add a tag to the item"""
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.save()
    
    def remove_tag(self, tag):
        """Remove a tag from the item"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.save()
    
    def has_tag(self, tag):
        """Check if item has a specific tag"""
        return tag in self.tags


class AuditMixin(models.Model):
    """Audit trail mixin"""
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_created'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_updated'
    )
    
    class Meta:
        abstract = True


class CommonChoices:
    """Common choice definitions for e-commerce models"""
    
    class Currency(TextChoices):
        USD = 'USD', 'US Dollar'
        EUR = 'EUR', 'Euro'
        GBP = 'GBP', 'British Pound'
        CAD = 'CAD', 'Canadian Dollar'
        AUD = 'AUD', 'Australian Dollar'
        JPY = 'JPY', 'Japanese Yen'
        CNY = 'CNY', 'Chinese Yuan'
        INR = 'INR', 'Indian Rupee'
        BRL = 'BRL', 'Brazilian Real'
        MXN = 'MXN', 'Mexican Peso'
    
    class PaymentMethod(TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
        PAYPAL = 'PAYPAL', 'PayPal'
        APPLE_PAY = 'APPLE_PAY', 'Apple Pay'
        GOOGLE_PAY = 'GOOGLE_PAY', 'Google Pay'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CASH_ON_DELIVERY = 'COD', 'Cash on Delivery'
        CRYPTOCURRENCY = 'CRYPTO', 'Cryptocurrency'
        GIFT_CARD = 'GIFT_CARD', 'Gift Card'
        STORE_CREDIT = 'STORE_CREDIT', 'Store Credit'
    
    class TransactionStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        CAPTURED = 'CAPTURED', 'Captured'
        PARTIALLY_CAPTURED = 'PARTIALLY_CAPTURED', 'Partially Captured'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        DISPUTED = 'DISPUTED', 'Disputed'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
    
    class OrderStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        PARTIALLY_SHIPPED = 'PARTIALLY_SHIPPED', 'Partially Shipped'
        RETURN_REQUESTED = 'RETURN_REQUESTED', 'Return Requested'
        RETURNED = 'RETURNED', 'Returned'
    
    class FulfillmentStatus(TextChoices):
        UNFULFILLED = 'UNFULFILLED', 'Unfulfilled'
        PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED', 'Partially Fulfilled'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        RESTOCKED = 'RESTOCKED', 'Restocked'
        
    class ShippingStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for Delivery'
        DELIVERED = 'DELIVERED', 'Delivered'
        FAILED_DELIVERY = 'FAILED_DELIVERY', 'Failed Delivery'
        RETURNED_TO_SENDER = 'RETURNED_TO_SENDER', 'Returned to Sender'