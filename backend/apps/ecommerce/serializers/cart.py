"""
Cart serializers for e-commerce functionality
"""

from rest_framework import serializers
from django.db.models import Sum, F
from decimal import Decimal

from .base import (
    EcommerceModelSerializer, TenantAwareSerializer, AuditSerializer,
    StatusSerializer, CustomFieldSerializer
)
from .products import ProductListSerializer, ProductVariantSerializer
from ..models import Cart, CartItem, Wishlist, WishlistItem


class CartItemSerializer(EcommerceModelSerializer):
    """Serializer for cart items"""
    
    product = ProductListSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    line_total = serializers.SerializerMethodField()
    line_total_formatted = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    availability_message = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'cart', 'product', 'variant', 'quantity', 'price',
            'line_total', 'line_total_formatted', 'custom_attributes',
            'is_available', 'availability_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'cart', 'created_at', 'updated_at']
    
    def get_line_total(self, obj):
        """Calculate line total"""
        return obj.price * obj.quantity if obj.price else Decimal('0.00')
    
    def get_line_total_formatted(self, obj):
        """Get formatted line total"""
        total = self.get_line_total(obj)
        return f"${total:,.2f}" if total else "N/A"
    
    def get_is_available(self, obj):
        """Check if item is available"""
        if obj.variant:
            return obj.variant.stock_quantity >= obj.quantity if obj.variant.track_quantity else True
        return obj.product.stock_quantity >= obj.quantity if obj.product.track_quantity else True
    
    def get_availability_message(self, obj):
        """Get availability message"""
        if not self.get_is_available(obj):
            if obj.variant:
                available = obj.variant.stock_quantity
                return f"Only {available} available"
            else:
                available = obj.product.stock_quantity
                return f"Only {available} available"
        return "In stock"


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for creating cart items"""
    
    product_id = serializers.IntegerField(help_text="Product ID")
    variant_id = serializers.IntegerField(required=False, help_text="Product variant ID")
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1, help_text="Quantity")
    custom_attributes = serializers.JSONField(required=False, help_text="Custom attributes")
    
    def validate(self, attrs):
        """Validate cart item data"""
        product_id = attrs.get('product_id')
        variant_id = attrs.get('variant_id')
        quantity = attrs.get('quantity', 1)
        
        # Validate product exists
        from ..models import EcommerceProduct
        try:
            product = EcommerceProduct.objects.get(
                id=product_id,
                is_active=True,
                is_published=True
            )
        except EcommerceProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found or not available")
        
        # Validate variant if provided
        if variant_id:
            from ..models import ProductVariant
            try:
                variant = ProductVariant.objects.get(
                    id=variant_id,
                    product=product,
                    is_active=True
                )
            except ProductVariant.DoesNotExist:
                raise serializers.ValidationError("Product variant not found or not available")
            
            # Check variant stock
            if variant.track_quantity and variant.stock_quantity < quantity:
                raise serializers.ValidationError(f"Insufficient stock. Only {variant.stock_quantity} available.")
        else:
            # Check product stock
            if product.track_quantity and product.stock_quantity < quantity:
                raise serializers.ValidationError(f"Insufficient stock. Only {product.stock_quantity} available.")
        
        return attrs


class CartItemUpdateSerializer(serializers.Serializer):
    """Serializer for updating cart items"""
    
    quantity = serializers.IntegerField(min_value=1, max_value=999, help_text="New quantity")
    custom_attributes = serializers.JSONField(required=False, help_text="Custom attributes")
    
    def validate_quantity(self, value):
        """Validate quantity"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        if value > 999:
            raise serializers.ValidationError("Quantity cannot exceed 999")
        return value


class CartSerializer(EcommerceModelSerializer):
    """Serializer for shopping cart"""
    
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    subtotal_formatted = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    tax_amount_formatted = serializers.SerializerMethodField()
    shipping_amount = serializers.SerializerMethodField()
    shipping_amount_formatted = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    total_amount_formatted = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    discount_amount_formatted = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    is_empty = serializers.SerializerMethodField()
    can_checkout = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'user', 'session_key', 'status', 'items', 'item_count',
            'subtotal', 'subtotal_formatted', 'tax_amount', 'tax_amount_formatted',
            'shipping_amount', 'shipping_amount_formatted', 'total_amount',
            'total_amount_formatted', 'discount_amount', 'discount_amount_formatted',
            'currency', 'coupon_code', 'is_empty', 'can_checkout',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_item_count(self, obj):
        """Get total item count"""
        return sum(item.quantity for item in obj.items.all())
    
    def get_subtotal(self, obj):
        """Get cart subtotal"""
        return obj.subtotal or Decimal('0.00')
    
    def get_subtotal_formatted(self, obj):
        """Get formatted subtotal"""
        subtotal = self.get_subtotal(obj)
        return f"${subtotal:,.2f}" if subtotal else "$0.00"
    
    def get_tax_amount(self, obj):
        """Get tax amount"""
        return obj.tax_amount or Decimal('0.00')
    
    def get_tax_amount_formatted(self, obj):
        """Get formatted tax amount"""
        tax = self.get_tax_amount(obj)
        return f"${tax:,.2f}" if tax else "$0.00"
    
    def get_shipping_amount(self, obj):
        """Get shipping amount"""
        return obj.shipping_amount or Decimal('0.00')
    
    def get_shipping_amount_formatted(self, obj):
        """Get formatted shipping amount"""
        shipping = self.get_shipping_amount(obj)
        return f"${shipping:,.2f}" if shipping else "$0.00"
    
    def get_total_amount(self, obj):
        """Get total amount"""
        return obj.total_amount or Decimal('0.00')
    
    def get_total_amount_formatted(self, obj):
        """Get formatted total amount"""
        total = self.get_total_amount(obj)
        return f"${total:,.2f}" if total else "$0.00"
    
    def get_discount_amount(self, obj):
        """Get discount amount"""
        subtotal = self.get_subtotal(obj)
        total = self.get_total_amount(obj)
        return subtotal - total if subtotal > total else Decimal('0.00')
    
    def get_discount_amount_formatted(self, obj):
        """Get formatted discount amount"""
        discount = self.get_discount_amount(obj)
        return f"${discount:,.2f}" if discount else "$0.00"
    
    def get_currency(self, obj):
        """Get currency"""
        return obj.currency or 'USD'
    
    def get_is_empty(self, obj):
        """Check if cart is empty"""
        return obj.items.count() == 0
    
    def get_can_checkout(self, obj):
        """Check if cart can proceed to checkout"""
        if self.get_is_empty(obj):
            return False
        
        # Check minimum order amount
        total = self.get_total_amount(obj)
        if total < Decimal('10.00'):  # Example minimum
            return False
        
        # Check if all items are available
        for item in obj.items.all():
            if not CartItemSerializer(item).get_is_available(item):
                return False
        
        return True


class CartSummarySerializer(serializers.Serializer):
    """Serializer for cart summary (minimal data)"""
    
    id = serializers.IntegerField(help_text="Cart ID")
    item_count = serializers.IntegerField(help_text="Total item count")
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Total amount")
    total_amount_formatted = serializers.CharField(help_text="Formatted total amount")
    currency = serializers.CharField(help_text="Currency")
    is_empty = serializers.BooleanField(help_text="Is cart empty")
    can_checkout = serializers.BooleanField(help_text="Can proceed to checkout")


class CartCreateSerializer(serializers.Serializer):
    """Serializer for creating a new cart"""
    
    user_id = serializers.IntegerField(required=False, help_text="User ID (optional)")
    session_key = serializers.CharField(required=False, help_text="Session key (optional)")


class WishlistItemSerializer(EcommerceModelSerializer):
    """Serializer for wishlist items"""
    
    product = ProductListSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    availability_message = serializers.SerializerMethodField()
    
    class Meta:
        model = WishlistItem
        fields = [
            'id', 'wishlist', 'product', 'variant', 'quantity',
            'custom_attributes', 'is_available', 'availability_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'wishlist', 'created_at', 'updated_at']
    
    def get_is_available(self, obj):
        """Check if item is available"""
        if obj.variant:
            return obj.variant.stock_quantity > 0 if obj.variant.track_quantity else True
        return obj.product.stock_quantity > 0 if obj.product.track_quantity else True
    
    def get_availability_message(self, obj):
        """Get availability message"""
        if not self.get_is_available(obj):
            return "Out of stock"
        return "In stock"


class WishlistSerializer(EcommerceModelSerializer):
    """Serializer for wishlists"""
    
    items = WishlistItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    is_empty = serializers.SerializerMethodField()
    
    class Meta:
        model = Wishlist
        fields = [
            'id', 'user', 'name', 'description', 'is_default',
            'is_active', 'items', 'item_count', 'is_empty',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_item_count(self, obj):
        """Get total item count"""
        return sum(item.quantity for item in obj.items.all())
    
    def get_is_empty(self, obj):
        """Check if wishlist is empty"""
        return obj.items.count() == 0


class WishlistCreateSerializer(serializers.Serializer):
    """Serializer for creating wishlists"""
    
    name = serializers.CharField(max_length=255, help_text="Wishlist name")
    description = serializers.CharField(required=False, help_text="Wishlist description")
    is_default = serializers.BooleanField(default=False, help_text="Is default wishlist")


class WishlistItemCreateSerializer(serializers.Serializer):
    """Serializer for adding items to wishlist"""
    
    product_id = serializers.IntegerField(help_text="Product ID")
    variant_id = serializers.IntegerField(required=False, help_text="Product variant ID")
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1, help_text="Quantity")
    custom_attributes = serializers.JSONField(required=False, help_text="Custom attributes")
    wishlist_id = serializers.IntegerField(required=False, help_text="Wishlist ID (optional)")


class CartOperationSerializer(serializers.Serializer):
    """Serializer for cart operations"""
    
    action = serializers.ChoiceField(choices=[
        ('add_item', 'Add Item'),
        ('update_item', 'Update Item'),
        ('remove_item', 'Remove Item'),
        ('clear_cart', 'Clear Cart'),
        ('apply_coupon', 'Apply Coupon'),
        ('remove_coupon', 'Remove Coupon'),
        ('move_to_wishlist', 'Move to Wishlist'),
        ('merge_carts', 'Merge Carts'),
    ], help_text="Action to perform")
    
    data = serializers.DictField(help_text="Operation data")


class CartValidationSerializer(serializers.Serializer):
    """Serializer for cart validation"""
    
    is_valid = serializers.BooleanField(help_text="Is cart valid")
    errors = serializers.ListField(
        child=serializers.CharField(),
        help_text="Validation errors"
    )
    warnings = serializers.ListField(
        child=serializers.CharField(),
        help_text="Validation warnings"
    )
    unavailable_items = serializers.ListField(
        child=serializers.DictField(),
        help_text="Unavailable items"
    )
    price_changes = serializers.ListField(
        child=serializers.DictField(),
        help_text="Price changes"
    )


class CartShippingSerializer(serializers.Serializer):
    """Serializer for cart shipping information"""
    
    shipping_address = serializers.DictField(help_text="Shipping address")
    shipping_method = serializers.CharField(help_text="Shipping method")
    shipping_cost = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Shipping cost")
    estimated_delivery = serializers.CharField(help_text="Estimated delivery")
    shipping_options = serializers.ListField(
        child=serializers.DictField(),
        help_text="Available shipping options"
    )


class CartTaxSerializer(serializers.Serializer):
    """Serializer for cart tax information"""
    
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=4, help_text="Tax rate")
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Tax amount")
    taxable_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Taxable amount")
    tax_breakdown = serializers.ListField(
        child=serializers.DictField(),
        help_text="Tax breakdown by item"
    )


class CartDiscountSerializer(serializers.Serializer):
    """Serializer for cart discount information"""
    
    coupon_code = serializers.CharField(help_text="Coupon code")
    discount_type = serializers.CharField(help_text="Discount type")
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Discount value")
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Discount amount")
    minimum_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Minimum order amount")
    is_valid = serializers.BooleanField(help_text="Is coupon valid")
    validation_message = serializers.CharField(help_text="Validation message")


class CartAnalyticsSerializer(serializers.Serializer):
    """Serializer for cart analytics"""
    
    cart_id = serializers.IntegerField(help_text="Cart ID")
    session_duration = serializers.IntegerField(help_text="Session duration in seconds")
    items_added = serializers.IntegerField(help_text="Number of items added")
    items_removed = serializers.IntegerField(help_text="Number of items removed")
    cart_abandoned = serializers.BooleanField(help_text="Was cart abandoned")
    conversion_value = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Conversion value")
    user_behavior = serializers.DictField(help_text="User behavior data")


class CartRecoverySerializer(serializers.Serializer):
    """Serializer for cart recovery"""
    
    cart_id = serializers.IntegerField(help_text="Cart ID")
    recovery_token = serializers.CharField(help_text="Recovery token")
    expires_at = serializers.DateTimeField(help_text="Expiration time")
    is_valid = serializers.BooleanField(help_text="Is recovery token valid")
    recovery_url = serializers.CharField(help_text="Recovery URL")
