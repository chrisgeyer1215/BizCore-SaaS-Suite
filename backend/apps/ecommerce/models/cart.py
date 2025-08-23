# apps/ecommerce/models/cart.py

"""
Advanced AI-Powered Shopping Cart and Wishlist System
Featuring machine learning recommendations, predictive analytics, and intelligent optimization
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid
import json
import logging
from datetime import timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Tuple

from .base import EcommerceBaseModel, CommonChoices, AIOptimizedPricingMixin
from .managers import CartManager
from .cart_ai_methods import CartAIMixin

User = get_user_model()
logger = logging.getLogger(__name__)


class IntelligentCart(EcommerceBaseModel, CartAIMixin):
    """
    AI-Powered Intelligent Shopping Cart with advanced analytics, 
    personalization, and predictive optimization
    """
    
    class CartStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ABANDONED = 'ABANDONED', 'Abandoned'
        COMPLETED = 'COMPLETED', 'Completed'
        EXPIRED = 'EXPIRED', 'Expired'
        MERGED = 'MERGED', 'Merged'
        OPTIMIZING = 'OPTIMIZING', 'AI Optimizing'
        PERSONALIZED = 'PERSONALIZED', 'Personalized'
    
    # Cart Identification
    cart_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session_key = models.CharField(max_length=255, blank=True)
    
    # User Association
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='carts'
    )
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts'
    )
    
    # Cart Status and Metadata
    status = models.CharField(
        max_length=20, 
        choices=CartStatus.choices, 
        default=CartStatus.ACTIVE
    )
    currency = models.CharField(
        max_length=3, 
        choices=CommonChoices.Currency.choices,
        default=CommonChoices.Currency.USD
    )
    
    # AI-powered features
    ai_recommendations = models.JSONField(default=list, blank=True)
    personalization_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI personalization effectiveness score (0-100)"
    )
    conversion_probability = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI-predicted conversion probability (0-100%)"
    )
    abandonment_risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI-calculated abandonment risk (0-100)"
    )
    
    # Behavioral analytics
    interaction_history = models.JSONField(default=list, blank=True)
    behavioral_segments = ArrayField(
        models.CharField(max_length=50), default=list, blank=True
    )
    engagement_metrics = models.JSONField(default=dict, blank=True)
    
    # Intelligent pricing
    dynamic_pricing_applied = models.BooleanField(default=False)
    price_optimizations = models.JSONField(default=dict, blank=True)
    discount_recommendations = models.JSONField(default=list, blank=True)
    
    # Cross-selling and upselling
    recommended_products = models.JSONField(default=list, blank=True)
    bundle_suggestions = models.JSONField(default=list, blank=True)
    upsell_opportunities = models.JSONField(default=list, blank=True)
    
    # Predictive analytics
    predicted_final_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    completion_likelihood = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    optimal_checkout_time = models.DateTimeField(null=True, blank=True)
    
    # Smart notifications
    notification_preferences = models.JSONField(default=dict, blank=True)
    auto_save_reminders = models.BooleanField(default=True)
    price_drop_alerts = models.BooleanField(default=True)
    stock_alerts = models.BooleanField(default=True)
    
    # Totals (cached for performance)
    item_count = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Shipping Information
    shipping_address = models.JSONField(default=dict, blank=True)
    shipping_method = models.CharField(max_length=100, blank=True)
    
    # Applied Discounts
    applied_coupons = models.JSONField(default=list, blank=True)
    
    # Cart Behavior
    is_persistent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    last_activity = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Marketing
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    referrer_url = models.URLField(blank=True)
    
    # Custom manager
    objects = CartManager()
    
    class Meta:
        db_table = 'ecommerce_carts'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['tenant', 'user', 'status']),
            models.Index(fields=['tenant', 'session_key', 'status']),
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['cart_id']),
            models.Index(fields=['status', 'last_activity']),
        ]
    
    def __str__(self):
        if self.user:
            return f"AI Cart for {self.user.email} (Score: {self.personalization_score or 'N/A'})"
        return f"Anonymous AI Cart {self.cart_id}"
    
    def save(self, *args, **kwargs):
        # Set expiration if not set
        if not self.expires_at and self.status == self.CartStatus.ACTIVE:
            # Get cart expiration from settings (default 30 days)
            expiration_days = getattr(self.tenant, 'cart_expiration_days', 30)
            self.expires_at = timezone.now() + timedelta(days=expiration_days)
        
        super().save(*args, **kwargs)
    
    @property
    def is_empty(self):
        """Check if cart is empty"""
        return self.item_count == 0
    
    @property
    def is_expired(self):
        """Check if cart is expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def is_abandoned(self):
        """Check if cart is abandoned (no activity for X hours)"""
        if self.status != self.CartStatus.ACTIVE:
            return False
        
        # Consider abandoned after 24 hours of inactivity
        abandonment_threshold = timezone.now() - timedelta(hours=24)
        return self.last_activity < abandonment_threshold
    
    def add_item(self, product, variant=None, quantity=1, custom_price=None, trigger_ai_analysis=True):
        """Add item to cart with AI-powered optimization"""
        if self.status not in [self.CartStatus.ACTIVE, self.CartStatus.PERSONALIZED]:
            raise ValidationError("Cannot add items to inactive cart")
        
        # Record interaction for behavioral analysis
        self.record_interaction('add_item', {
            'product_id': str(product.id),
            'variant_id': str(variant.id) if variant else None,
            'quantity': quantity,
            'timestamp': timezone.now().isoformat()
        })
        
        # AI-powered price optimization
        optimized_price = custom_price
        if not optimized_price and hasattr(product, 'calculate_ai_optimized_price'):
            ai_price = product.calculate_ai_optimized_price()
            if ai_price and product.enable_dynamic_pricing:
                optimized_price = ai_price
                self.dynamic_pricing_applied = True
        
        # Check if item already exists
        existing_item = self.items.filter(
            product=product,
            variant=variant
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            if optimized_price:
                existing_item.unit_price = optimized_price
            existing_item.save()
            cart_item = existing_item
        else:
            # Create new cart item
            cart_item = IntelligentCartItem.objects.create(
                tenant=self.tenant,
                cart=self,
                product=product,
                variant=variant,
                quantity=quantity,
                unit_price=optimized_price or (variant.effective_price if variant else product.price)
            )
        
        # Trigger AI analysis and recommendations
        if trigger_ai_analysis:
            self.analyze_cart_with_ai()
            self.generate_recommendations()
        
        # Update cart totals
        self.update_totals()
        return cart_item
    
    def remove_item(self, cart_item_id):
        """Remove item from cart"""
        try:
            item = self.items.get(id=cart_item_id)
            item.delete()
            self.update_totals()
            return True
        except CartItem.DoesNotExist:
            return False
    
    def update_item_quantity(self, cart_item_id, quantity):
        """Update item quantity"""
        try:
            item = self.items.get(id=cart_item_id)
            if quantity <= 0:
                item.delete()
            else:
                item.quantity = quantity
                item.save()
            self.update_totals()
            return True
        except CartItem.DoesNotExist:
            return False
    
    def clear(self):
        """Clear all items from cart"""
        self.items.all().delete()
        self.update_totals()
    
    def update_totals(self):
        """Update cart totals based on items"""
        items = self.items.select_related('product', 'variant')
        
        item_count = 0
        subtotal = Decimal('0.00')
        
        for item in items:
            item_count += item.quantity
            subtotal += item.line_total
        
        # Calculate tax (simplified - would integrate with tax service)
        tax_rate = Decimal('0.08')  # This would come from settings/tax service
        tax_amount = subtotal * tax_rate
        
        # Calculate shipping (simplified)
        shipping_amount = self.calculate_shipping()
        
        # Apply discounts
        discount_amount = self.calculate_discounts(subtotal)
        
        # Calculate total
        total_amount = subtotal + tax_amount + shipping_amount - discount_amount
        
        # Update fields
        self.item_count = item_count
        self.subtotal = subtotal
        self.tax_amount = tax_amount
        self.shipping_amount = shipping_amount
        self.discount_amount = discount_amount
        self.total_amount = max(Decimal('0.00'), total_amount)
        
        self.save(update_fields=[
            'item_count', 'subtotal', 'tax_amount', 
            'shipping_amount', 'discount_amount', 'total_amount'
        ])
    
    def calculate_shipping(self):
        """Calculate shipping cost"""
        # This would integrate with shipping service
        if self.subtotal >= Decimal('50.00'):  # Free shipping threshold
            return Decimal('0.00')
        return Decimal('10.00')  # Flat rate
    
    def calculate_discounts(self, subtotal):
        """Calculate discount amount"""
        total_discount = Decimal('0.00')
        
        # Apply coupon discounts
        for coupon_code in self.applied_coupons:
            # This would integrate with discount service
            # For now, simple percentage discount
            if coupon_code == 'SAVE10':
                total_discount += subtotal * Decimal('0.10')
        
        return total_discount
    
    def apply_coupon(self, coupon_code):
        """Apply coupon to cart"""
        # This would integrate with coupon/discount service
        if coupon_code not in self.applied_coupons:
            self.applied_coupons.append(coupon_code)
            self.save(update_fields=['applied_coupons'])
            self.update_totals()
            return True
        return False
    
    def remove_coupon(self, coupon_code):
        """Remove coupon from cart"""
        if coupon_code in self.applied_coupons:
            self.applied_coupons.remove(coupon_code)
            self.save(update_fields=['applied_coupons'])
            self.update_totals()
            return True
        return False
    
    def merge_with(self, other_cart):
        """Merge another cart into this cart"""
        if other_cart.tenant != self.tenant:
            raise ValidationError("Cannot merge carts from different tenants")
        
        # Move items from other cart to this cart
        for item in other_cart.items.all():
            self.add_item(
                product=item.product,
                variant=item.variant,
                quantity=item.quantity,
                custom_price=item.unit_price
            )
        
        # Mark other cart as merged
        other_cart.status = self.CartStatus.MERGED
        other_cart.save()
        
        # Update totals
        self.update_totals()
    
    def convert_to_order(self):
        """Convert cart to order"""
        from .orders import Order
        
        if self.is_empty:
            raise ValidationError("Cannot convert empty cart to order")
        
        # Create order from cart
        order = Order.objects.create(
            tenant=self.tenant,
            user=self.user,
            customer=self.customer,
            currency=self.currency,
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            shipping_amount=self.shipping_amount,
            discount_amount=self.discount_amount,
            total_amount=self.total_amount,
            shipping_address=self.shipping_address,
            billing_address=self.shipping_address,  # Default to same
        )
        
        # Create order items from cart items
        for cart_item in self.items.all():
            order.items.create(
                tenant=self.tenant,
                product=cart_item.product,
                variant=cart_item.variant,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                line_total=cart_item.line_total
            )
        
        # Mark cart as completed
        self.status = self.CartStatus.COMPLETED
        self.save()
        
        return order
    
    def abandon(self):
        """Mark cart as abandoned"""
        if self.status == self.CartStatus.ACTIVE:
            self.status = self.CartStatus.ABANDONED
            self.save()


class IntelligentCartItem(EcommerceBaseModel, AIOptimizedPricingMixin):
    """Individual items in shopping cart"""
    
    cart = models.ForeignKey(
        IntelligentCart, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        'EcommerceProduct', 
        on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        'ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    # Quantity and Pricing
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Item customization
    custom_attributes = models.JSONField(default=dict, blank=True)
    gift_message = models.TextField(blank=True)
    
    # Tracking
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecommerce_cart_items'
        ordering = ['added_at']
        indexes = [
            models.Index(fields=['tenant', 'cart']),
            models.Index(fields=['tenant', 'product']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'cart', 'product', 'variant'],
                name='unique_cart_item_per_tenant'
            ),
        ]
    
    def __str__(self):
        variant_info = f" ({self.variant.title})" if self.variant else ""
        return f"{self.product.title}{variant_info} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calculate line total
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than 0'})
        
        # Check stock availability
        if self.variant:
            available_stock = self.variant.available_quantity
        else:
            available_stock = self.product.available_quantity
        
        if self.product.track_quantity and available_stock < self.quantity:
            raise ValidationError({
                'quantity': f'Only {available_stock} items available in stock'
            })
    
    @property
    def item_name(self):
        """Get display name for item"""
        if self.variant:
            return f"{self.product.title} - {self.variant.title}"
        return self.product.title
    
    @property
    def item_image(self):
        """Get item image"""
        if self.variant and self.variant.image:
            return self.variant.image
        return self.product.featured_image


class Wishlist(EcommerceBaseModel):
    """Customer wishlist for saving products"""
    
    class WishlistVisibility(models.TextChoices):
        PRIVATE = 'PRIVATE', 'Private'
        PUBLIC = 'PUBLIC', 'Public'
        SHARED = 'SHARED', 'Shared with Link'
    
    # Wishlist Identification
    name = models.CharField(max_length=255, default='My Wishlist')
    description = models.TextField(blank=True)
    
    # Owner
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='wishlists'
    )
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wishlists'
    )
    
    # Settings
    visibility = models.CharField(
        max_length=20, 
        choices=WishlistVisibility.choices, 
        default=WishlistVisibility.PRIVATE
    )
    is_default = models.BooleanField(default=False)
    
    # Sharing
    share_token = models.UUIDField(default=uuid.uuid4, unique=True)
    share_url = models.URLField(blank=True)
    
    # Products
    products = models.ManyToManyField(
        'EcommerceProduct', 
        through='WishlistItem',
        blank=True
    )
    
    class Meta:
        db_table = 'ecommerce_wishlists'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['share_token']),
            models.Index(fields=['visibility']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'user', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_wishlist_per_user'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        # Generate share URL
        if not self.share_url:
            self.share_url = f"/wishlists/shared/{self.share_token}/"
        
        super().save(*args, **kwargs)
        
        # Ensure only one default wishlist per user
        if self.is_default:
            Wishlist.objects.filter(
                tenant=self.tenant,
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
    
    def add_product(self, product, variant=None, note=''):
        """Add product to wishlist"""
        wishlist_item, created = WishlistItem.objects.get_or_create(
            tenant=self.tenant,
            wishlist=self,
            product=product,
            variant=variant,
            defaults={'note': note}
        )
        return wishlist_item, created
    
    def remove_product(self, product, variant=None):
        """Remove product from wishlist"""
        return WishlistItem.objects.filter(
            tenant=self.tenant,
            wishlist=self,
            product=product,
            variant=variant
        ).delete()
    
    def has_product(self, product, variant=None):
        """Check if product is in wishlist"""
        return WishlistItem.objects.filter(
            tenant=self.tenant,
            wishlist=self,
            product=product,
            variant=variant
        ).exists()
    
    def get_items(self):
        """Get wishlist items with related data"""
        return self.items.select_related(
            'product', 'variant'
        ).order_by('-added_at')
    
    @property
    def item_count(self):
        """Get number of items in wishlist"""
        return self.items.count()
    
    @property
    def total_value(self):
        """Calculate total value of wishlist items"""
        total = Decimal('0.00')
        for item in self.items.all():
            if item.variant:
                total += item.variant.effective_price
            else:
                total += item.product.price
        return total


class WishlistItem(EcommerceBaseModel):
    """Individual items in wishlist"""
    
    wishlist = models.ForeignKey(
        Wishlist, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        'EcommerceProduct', 
        on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        'ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    # Item details
    note = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
        ],
        default='MEDIUM'
    )
    
    # Tracking
    added_at = models.DateTimeField(auto_now_add=True)
    price_when_added = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    class Meta:
        db_table = 'ecommerce_wishlist_items'
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['tenant', 'wishlist']),
            models.Index(fields=['tenant', 'product']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'wishlist', 'product', 'variant'],
                name='unique_wishlist_item_per_tenant'
            ),
        ]
    
    def __str__(self):
        variant_info = f" ({self.variant.title})" if self.variant else ""
        return f"{self.product.title}{variant_info}"
    
    def save(self, *args, **kwargs):
        # Record price when added
        if not self.price_when_added:
            if self.variant:
                self.price_when_added = self.variant.effective_price
            else:
                self.price_when_added = self.product.price
        
        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        """Get current price of the item"""
        if self.variant:
            return self.variant.effective_price
        return self.product.price
    
    @property
    def price_change(self):
        """Calculate price change since added"""
        if self.price_when_added:
            return self.current_price - self.price_when_added
        return Decimal('0.00')
    
    @property
    def price_change_percentage(self):
        """Calculate price change percentage"""
        if self.price_when_added and self.price_when_added > 0:
            return (self.price_change / self.price_when_added) * 100
        return Decimal('0.00')
    
    @property
    def is_price_dropped(self):
        """Check if price has dropped since added"""
        return self.price_change < 0
    
    @property
    def is_in_stock(self):
        """Check if item is currently in stock"""
        if self.variant:
            return self.variant.is_in_stock
        return self.product.is_in_stock
    
    def add_to_cart(self, cart, quantity=1):
        """Add this wishlist item to cart"""
        return cart.add_item(
            product=self.product,
            variant=self.variant,
            quantity=quantity
        )


class SavedForLater(EcommerceBaseModel):
    """Items saved for later from cart"""
    
    # User/Customer
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='saved_items'
    )
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='saved_items'
    )
    session_key = models.CharField(max_length=255, blank=True)
    
    # Product Details
    product = models.ForeignKey(
        'EcommerceProduct', 
        on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        'ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    # Item Configuration
    quantity = models.PositiveIntegerField(default=1)
    custom_attributes = models.JSONField(default=dict, blank=True)
    
    # Pricing at time of saving
    saved_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Metadata
    saved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_saved_for_later'
        ordering = ['-saved_at']
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'session_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        variant_info = f" ({self.variant.title})" if self.variant else ""
        return f"Saved: {self.product.title}{variant_info}"
    
    def save(self, *args, **kwargs):
        # Set expiration (default 30 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        
        # Set saved price
        if not self.saved_price:
            if self.variant:
                self.saved_price = self.variant.effective_price
            else:
                self.saved_price = self.product.price
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if saved item is expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def current_price(self):
        """Get current price of the item"""
        if self.variant:
            return self.variant.effective_price
        return self.product.price
    
    @property
    def price_difference(self):
        """Calculate price difference since saved"""
        return self.current_price - self.saved_price
    
    def move_to_cart(self, cart=None):
        """Move saved item back to cart"""
        if not cart:
            # Get or create active cart for user
            if self.user:
                cart, _ = Cart.objects.get_or_create(
                    tenant=self.tenant,
                    user=self.user,
                    status=Cart.CartStatus.ACTIVE,
                    defaults={'currency': 'USD'}  # Would get from settings
                )
            else:
                raise ValueError("Cannot move to cart without user or specified cart")
        
        # Add to cart
        cart_item = cart.add_item(
            product=self.product,
            variant=self.variant,
            quantity=self.quantity
        )
        
        # Delete saved item
        self.delete()
        
        return cart_item
    
    def move_to_wishlist(self, wishlist=None):
        """Move saved item to wishlist"""
        if not wishlist and self.user:
            # Get or create default wishlist
            wishlist, _ = Wishlist.objects.get_or_create(
                tenant=self.tenant,
                user=self.user,
                is_default=True,
                defaults={'name': 'My Wishlist'}
            )
        
        if not wishlist:
            raise ValueError("Cannot move to wishlist without user or specified wishlist")
        
        # Add to wishlist
        wishlist_item, _ = wishlist.add_product(
            product=self.product,
            variant=self.variant
        )
        
        # Delete saved item
        self.delete()
        
        return wishlist_item


class CartAbandonmentEvent(EcommerceBaseModel):
    """Track cart abandonment events for analytics and recovery"""
    
    class AbandonmentReason(models.TextChoices):
        UNEXPECTED_COSTS = 'UNEXPECTED_COSTS', 'Unexpected Costs'
        HIGH_SHIPPING = 'HIGH_SHIPPING', 'High Shipping Cost'
        LONG_CHECKOUT = 'LONG_CHECKOUT', 'Checkout Too Long'
        ACCOUNT_REQUIRED = 'ACCOUNT_REQUIRED', 'Account Creation Required'
        PAYMENT_ISSUES = 'PAYMENT_ISSUES', 'Payment Issues'
        CHANGED_MIND = 'CHANGED_MIND', 'Changed Mind'
        PRICE_COMPARISON = 'PRICE_COMPARISON', 'Comparing Prices'
        TECHNICAL_ISSUES = 'TECHNICAL_ISSUES', 'Technical Issues'
        OTHER = 'OTHER', 'Other'
        UNKNOWN = 'UNKNOWN', 'Unknown'
    
    cart = models.ForeignKey(
        'IntelligentCart', 
        on_delete=models.CASCADE, 
        related_name='abandonment_events'
    )
    
    # Event details
    abandonment_stage = models.CharField(
        max_length=50,
        choices=[
            ('CART', 'Cart Page'),
            ('CHECKOUT_SHIPPING', 'Checkout - Shipping'),
            ('CHECKOUT_PAYMENT', 'Checkout - Payment'),
            ('CHECKOUT_REVIEW', 'Checkout - Review'),
            ('PAYMENT_PROCESSING', 'Payment Processing'),
        ]
    )
    abandonment_reason = models.CharField(
        max_length=30,
        choices=AbandonmentReason.choices,
        default=AbandonmentReason.UNKNOWN
    )
    
    # Recovery tracking
    recovery_email_sent = models.BooleanField(default=False)
    recovery_email_opened = models.BooleanField(default=False)
    recovery_email_clicked = models.BooleanField(default=False)
    is_recovered = models.BooleanField(default=False)
    recovered_at = models.DateTimeField(null=True, blank=True)
    
    # Context
    page_url = models.URLField(blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ecommerce_cart_abandonment_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'cart']),
            models.Index(fields=['abandonment_stage']),
            models.Index(fields=['is_recovered']),
        ]
    
    def __str__(self):
        return f"Abandonment: {self.cart} at {self.abandonment_stage}"
    
    def mark_as_recovered(self):
        """Mark abandonment as recovered"""
        self.is_recovered = True
        self.recovered_at = timezone.now()
        self.save(update_fields=['is_recovered', 'recovered_at'])


class CartShare(EcommerceBaseModel):
    """Share cart with others for collaborative shopping"""
    
    class SharePermission(models.TextChoices):
        VIEW_ONLY = 'VIEW_ONLY', 'View Only'
        ADD_ITEMS = 'ADD_ITEMS', 'Add Items'
        EDIT_ITEMS = 'EDIT_ITEMS', 'Edit Items'
        FULL_ACCESS = 'FULL_ACCESS', 'Full Access'
    
    cart = models.ForeignKey(
        'IntelligentCart', 
        on_delete=models.CASCADE, 
        related_name='shares'
    )
    
    # Share details
    share_token = models.UUIDField(default=uuid.uuid4, unique=True)
    share_url = models.URLField(blank=True)
    
    # Recipient
    shared_with_email = models.EmailField(blank=True)
    shared_with_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='shared_carts'
    )
    
    # Permissions
    permission_level = models.CharField(
        max_length=20,
        choices=SharePermission.choices,
        default=SharePermission.VIEW_ONLY
    )
    
    # Share settings
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Tracking
    shared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cart_shares_made'
    )
    viewed_at = models.DateTimeField(null=True, blank=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_cart_shares'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['cart', 'is_active']),
        ]
    
    def __str__(self):
        recipient = self.shared_with_email or self.shared_with_user.email
        return f"Cart shared with {recipient}"
    
    def save(self, *args, **kwargs):
        # Generate share URL
        if not self.share_url:
            self.share_url = f"/carts/shared/{self.share_token}/"
        
        # Set default expiration (7 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if share is expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    def record_access(self):
        """Record that the shared cart was accessed"""
        now = timezone.now()
        if not self.viewed_at:
            self.viewed_at = now
        self.last_accessed = now
        self.save(update_fields=['viewed_at', 'last_accessed'])
    
    def can_add_items(self):
        """Check if user can add items"""
        return self.permission_level in [
            self.SharePermission.ADD_ITEMS,
            self.SharePermission.EDIT_ITEMS,
            self.SharePermission.FULL_ACCESS
        ]
    
    def can_edit_items(self):
        """Check if user can edit items"""
        return self.permission_level in [
            self.SharePermission.EDIT_ITEMS,
            self.SharePermission.FULL_ACCESS
        ]
    
    def can_checkout(self):
        """Check if user can checkout"""
        return self.permission_level == self.SharePermission.FULL_ACCESS