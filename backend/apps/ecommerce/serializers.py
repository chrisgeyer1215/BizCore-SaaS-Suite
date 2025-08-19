from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import (
    EcommerceSettings, Collection, EcommerceProduct, ProductVariant,
    Cart, CartItem, Order, OrderItem, PaymentTransaction,
    Coupon, ProductReview, CustomerAddress, ShippingZone, ShippingMethod,
    ReturnRequest, ReturnRequestItem, ProductAnalytics, AbandonedCart,
    ProductQuestion, CustomerGroup, SalesChannel, ChannelProduct
)
from apps.crm.serializers import CustomerSerializer


class EcommerceSettingsSerializer(serializers.ModelSerializer):
    """Serializer for e-commerce settings"""
    
    class Meta:
        model = EcommerceSettings
        fields = '__all__'
        read_only_fields = ['tenant']


class CollectionSerializer(serializers.ModelSerializer):
    """Serializer for collections"""
    
    product_count = serializers.ReadOnlyField()
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = Collection
        fields = '__all__'
        read_only_fields = ['tenant', 'products_count']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants"""
    
    effective_price = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductVariant
        fields = '__all__'
        read_only_fields = ['tenant']


class EcommerceProductListSerializer(serializers.ModelSerializer):
    """Serializer for product list view"""
    
    current_price = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    primary_collection_name = serializers.CharField(
        source='primary_collection.title', 
        read_only=True
    )
    
    class Meta:
        model = EcommerceProduct
        fields = [
            'id', 'title', 'slug', 'url_handle', 'short_description',
            'regular_price', 'sale_price', 'current_price', 'compare_at_price',
            'is_on_sale', 'discount_percentage', 'featured_image',
            'is_featured', 'is_best_seller', 'is_new_arrival',
            'average_rating', 'review_count', 'is_in_stock',
            'primary_collection_name', 'vendor', 'created_at'
        ]


class EcommerceProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed product view"""
    
    current_price = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    available_inventory = serializers.ReadOnlyField()
    variants = ProductVariantSerializer(many=True, read_only=True)
    collections = CollectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = EcommerceProduct
        exclude = ['tenant']


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items"""
    
    product_title = serializers.CharField(source='product.title', read_only=True)
    variant_title = serializers.CharField(source='variant.title', read_only=True)
    product_image = serializers.CharField(source='product.featured_image', read_only=True)
    line_total = serializers.ReadOnlyField()
    item_name = serializers.ReadOnlyField()
    
    class Meta:
        model = CartItem
        fields = '__all__'
        read_only_fields = ['tenant', 'cart']
    
    def validate(self, data):
        """Validate cart item"""
        product = data.get('product')
        variant = data.get('variant')
        quantity = data.get('quantity', 1)
        
        # Validate variant belongs to product
        if variant and variant.ecommerce_product != product:
            raise serializers.ValidationError(
                "Variant does not belong to the selected product"
            )
        
        # Check stock availability
        if product.track_quantity and not product.continue_selling_when_out_of_stock:
            available_stock = variant.available_quantity if variant else product.available_inventory
            if quantity > available_stock:
                raise serializers.ValidationError(
                    f"Only {available_stock} items available in stock"
                )
        
        return data


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart"""
    
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()
    unique_item_count = serializers.ReadOnlyField()
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = Cart
        fields = '__all__'
        read_only_fields = [
            'tenant', 'cart_id', 'subtotal', 'tax_amount', 
            'shipping_amount', 'discount_amount', 'total'
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items"""
    
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_image = serializers.CharField(source='product.featured_image', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['tenant', 'order']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for payment transactions"""
    
    class Meta:
        model = PaymentTransaction
        exclude = ['gateway_response']  # Sensitive data
        read_only_fields = ['tenant', 'transaction_id']


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for order list view"""
    
    customer_name = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'customer_email',
            'status', 'payment_status', 'fulfillment_status',
            'total_amount', 'currency', 'item_count',
            'order_date', 'confirmed_at', 'shipped_date'
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed order view"""
    
    items = OrderItemSerializer(many=True, read_only=True)
    payment_transactions = PaymentTransactionSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()
    customer_info = CustomerSerializer(source='customer', read_only=True)
    
    class Meta:
        model = Order
        exclude = ['tenant']


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupons"""
    
    is_valid_now = serializers.SerializerMethodField()
    remaining_uses = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        exclude = ['tenant']
        read_only_fields = ['usage_count']
    
    def get_is_valid_now(self, obj):
        """Check if coupon is currently valid"""
        is_valid, message = obj.is_valid()
        return is_valid
    
    def get_remaining_uses(self, obj):
        """Get remaining uses for coupon"""
        if obj.usage_limit_per_coupon:
            return obj.usage_limit_per_coupon - obj.usage_count
        return None


class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for product reviews"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    product_title = serializers.CharField(source='product.title', read_only=True)
    helpfulness_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductReview
        exclude = ['tenant']
        read_only_fields = [
            'customer', 'is_verified_purchase', 'helpful_count', 
            'not_helpful_count', 'status', 'reviewed_by', 'reviewed_at'
        ]
    
    def create(self, validated_data):
        """Create review with customer from request"""
        validated_data['customer'] = self.context['request'].user.customer
        validated_data['tenant'] = self.context['request'].tenant
        
        # Check if customer has purchased this product
        product = validated_data['product']
        customer = validated_data['customer']
        
        has_purchased = OrderItem.objects.filter(
            order__customer=customer,
            product=product,
            order__status__in=['COMPLETED', 'DELIVERED']
        ).exists()
        
        validated_data['is_verified_purchase'] = has_purchased
        
        return super().create(validated_data)


class CustomerAddressSerializer(serializers.ModelSerializer):
    """Serializer for customer addresses"""
    
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = CustomerAddress
        exclude = ['tenant']
        read_only_fields = ['customer']


class ShippingMethodSerializer(serializers.ModelSerializer):
    """Serializer for shipping methods"""
    
    zone_name = serializers.CharField(source='shipping_zone.name', read_only=True)
    
    class Meta:
        model = ShippingMethod
        exclude = ['tenant']


class ShippingZoneSerializer(serializers.ModelSerializer):
    """Serializer for shipping zones"""
    
    shipping_methods = ShippingMethodSerializer(many=True, read_only=True)
    countries_display = serializers.ReadOnlyField()
    
    class Meta:
        model = ShippingZone
        exclude = ['tenant']


class ReturnRequestItemSerializer(serializers.ModelSerializer):
    """Serializer for return request items"""
    
    product_title = serializers.CharField(source='order_item.title', read_only=True)
    product_image = serializers.CharField(source='order_item.product.featured_image', read_only=True)
    
    class Meta:
        model = ReturnRequestItem
        exclude = ['tenant']


class ReturnRequestSerializer(serializers.ModelSerializer):
    """Serializer for return requests"""
    
    items = ReturnRequestItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = ReturnRequest
        exclude = ['tenant']
        read_only_fields = ['return_number', 'customer']
    
    @transaction.atomic
    def create(self, validated_data):
        """Create return request with customer from request"""
        validated_data['customer'] = self.context['request'].user.customer
        validated_data['tenant'] = self.context['request'].tenant
        return super().create(validated_data)


class ProductAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for product analytics"""
    
    product_title = serializers.CharField(source='product.title', read_only=True)
    
    class Meta:
        model = ProductAnalytics
        exclude = ['tenant']


class ProductQuestionSerializer(serializers.ModelSerializer):
    """Serializer for product questions"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    product_title = serializers.CharField(source='product.title', read_only=True)
    helpfulness_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductQuestion
        exclude = ['tenant']
        read_only_fields = [
            'customer', 'is_answered', 'answered_by', 'answered_at',
            'helpful_votes', 'total_votes'
        ]
    
    def create(self, validated_data):
        """Create question with customer from request"""
        validated_data['customer'] = self.context['request'].user.customer
        validated_data['tenant'] = self.context['request'].tenant
        return super().create(validated_data)


class CustomerGroupSerializer(serializers.ModelSerializer):
    """Serializer for customer groups"""
    
    class Meta:
        model = CustomerGroup
        exclude = ['tenant']


class SalesChannelSerializer(serializers.ModelSerializer):
    """Serializer for sales channels"""
    
    class Meta:
        model = SalesChannel
        exclude = ['tenant', 'api_key']  # Hide sensitive data


class ChannelProductSerializer(serializers.ModelSerializer):
    """Serializer for channel products"""
    
    product_title = serializers.CharField(source='product.title', read_only=True)
    channel_name = serializers.CharField(source='sales_channel.name', read_only=True)
    effective_price = serializers.ReadOnlyField()
    
    class Meta:
        model = ChannelProduct
        exclude = ['tenant']


# Specialized serializers for specific use cases

class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout process"""
    
    billing_address = serializers.DictField()
    shipping_address = serializers.DictField()
    shipping_method_id = serializers.IntegerField()
    payment_method = serializers.CharField()
    coupon_codes = serializers.ListField(
        child=serializers.CharField(), 
        required=False, 
        default=list
    )
    customer_notes = serializers.CharField(required=False, default='')
    
    def validate_billing_address(self, value):
        """Validate billing address"""
        required_fields = [
            'first_name', 'last_name', 'address1', 
            'city', 'state', 'postal_code', 'country'
        ]
        
        for field in required_fields:
            if field not in value or not value[field]:
                raise serializers.ValidationError(f"{field} is required")
        
        return value
    
    def validate_shipping_address(self, value):
        """Validate shipping address"""
        required_fields = [
            'first_name', 'last_name', 'address1', 
            'city', 'state', 'postal_code', 'country'
        ]
        
        for field in required_fields:
            if field not in value or not value[field]:
                raise serializers.ValidationError(f"{field} is required")
        
        return value


class ApplyCouponSerializer(serializers.Serializer):
    """Serializer for applying coupons to cart"""
    
    coupon_code = serializers.CharField(max_length=50)
    
    def validate_coupon_code(self, value):
        """Validate coupon exists and is valid"""
        try:
            coupon = Coupon.objects.get(
                tenant=self.context['request'].tenant,
                code=value
            )
            is_valid, message = coupon.is_valid()
            if not is_valid:
                raise serializers.ValidationError(message)
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code")


class ShippingRateSerializer(serializers.Serializer):
    """Serializer for shipping rate calculation"""
    
    method_id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_days_min = serializers.IntegerField()
    estimated_days_max = serializers.IntegerField()


class ProductSearchSerializer(serializers.Serializer):
    """Serializer for product search"""
    
    query = serializers.CharField(required=False, default='')
    collections = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False, 
        default=list
    )
    price_min = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    price_max = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    in_stock = serializers.BooleanField(required=False, default=False)
    on_sale = serializers.BooleanField(required=False, default=False)
    rating_min = serializers.IntegerField(required=False, min_value=1, max_value=5)
    sort_by = serializers.ChoiceField(
        choices=[
            'relevance', 'price_asc', 'price_desc', 
            'rating_desc', 'newest', 'best_selling'
        ],
        required=False,
        default='relevance'
    )
