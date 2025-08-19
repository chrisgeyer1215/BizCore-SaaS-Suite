from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils import timezone
from .models import (
    EcommerceSettings, Collection, EcommerceProduct, ProductVariant,
    Cart, CartItem, Order, OrderItem, PaymentTransaction,
    Coupon, CouponUsage, ProductReview, CustomerAddress,
    ShippingZone, ShippingMethod, ReturnRequest, ReturnRequestItem,
    ProductAnalytics, AbandonedCart, ProductQuestion, CustomerGroup,
    SalesChannel, ChannelProduct, CollectionProduct
)


@admin.register(EcommerceSettings)
class EcommerceSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Store Information', {
            'fields': ('store_name', 'store_tagline', 'store_description', 'store_logo', 'store_favicon')
        }),
        ('Contact Details', {
            'fields': ('store_email', 'support_email', 'store_phone')
        }),
        ('Business Address', {
            'fields': ('business_address_line1', 'business_address_line2', 'business_city', 
                      'business_state', 'business_country', 'business_postal_code')
        }),
        ('Currency & Pricing', {
            'fields': ('default_currency', 'currency_symbol', 'currency_position', 
                      'enable_multi_currency', 'price_includes_tax', 'display_prices_with_tax')
        }),
        ('Payment Settings', {
            'fields': ('primary_payment_gateway', 'enable_guest_checkout', 'require_account_for_purchase')
        }),
        ('Tax Settings', {
            'fields': ('tax_calculation_method', 'default_tax_rate', 'tax_included_in_prices')
        }),
        ('Shipping Settings', {
            'fields': ('shipping_calculation_method', 'free_shipping_threshold', 'default_shipping_rate')
        }),
        ('Inventory Settings', {
            'fields': ('deduct_inventory_on', 'allow_overselling', 'track_inventory', 
                      'auto_sync_inventory', 'show_stock_levels', 'low_stock_threshold')
        }),
        ('Store Status', {
            'fields': ('is_live', 'maintenance_mode', 'maintenance_message')
        }),
        ('SEO & Marketing', {
            'fields': ('meta_title', 'meta_description', 'google_analytics_id', 'facebook_pixel_id')
        }),
    )
    
    list_display = ['store_name', 'is_live', 'maintenance_mode', 'default_currency']
    list_filter = ['is_live', 'maintenance_mode', 'default_currency']


class CollectionProductInline(admin.TabularInline):
    model = CollectionProduct
    extra = 0
    fields = ['product', 'position', 'is_featured']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'collection_type', 'is_visible', 'is_featured', 'products_count', 'created_at']
    list_filter = ['collection_type', 'is_visible', 'is_featured', 'created_at']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CollectionProductInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'description', 'collection_type', 'parent')
        }),
        ('Display Settings', {
            'fields': ('sort_order', 'products_per_page', 'is_featured', 'is_visible', 
                      'show_in_navigation', 'display_order')
        }),
        ('Images', {
            'fields': ('featured_image', 'banner_image', 'icon_class', 'color_code')
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('collapse',)
        }),
    )


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['title', 'sku', 'price', 'inventory_quantity', 'is_active']


@admin.register(EcommerceProduct)
class EcommerceProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'is_published', 'current_price', 'stock_quantity', 
                   'sales_count', 'view_count', 'created_at']
    list_filter = ['status', 'is_published', 'is_featured', 'product_type', 'vendor', 
                   'created_at', 'published_at']
    search_fields = ['title', 'description', 'tags', 'vendor', 'sku']
    prepopulated_fields = {'slug': ('title',), 'url_handle': ('title',)}
    filter_horizontal = ['collections']
    inlines = [ProductVariantInline]
    
    fieldsets = (
        (None, {
            'fields': ('inventory_product', 'title', 'slug', 'url_handle', 'product_type', 'status')
        }),
        ('Publishing', {
            'fields': ('is_published', 'published_at', 'visibility')
        }),
        ('Pricing', {
            'fields': ('regular_price', 'sale_price', 'sale_price_start', 'sale_price_end', 
                      'compare_at_price', 'cost_price')
        }),
        ('Inventory', {
            'fields': ('manage_stock', 'track_quantity', 'stock_quantity', 'low_stock_threshold',
                      'stock_status', 'allow_backorders', 'inventory_policy')
        }),
        ('Product Details', {
            'fields': ('short_description', 'description', 'additional_info')
        }),
        ('Organization', {
            'fields': ('collections', 'primary_collection', 'vendor', 'product_type_custom', 'tags')
        }),
        ('Images', {
            'fields': ('featured_image', 'gallery_images')
        }),
        ('Shipping & Tax', {
            'fields': ('requires_shipping', 'is_digital', 'weight', 'length', 'width', 'height',
                      'shipping_class', 'is_taxable', 'tax_class')
        }),
        ('Display Settings', {
            'fields': ('is_featured', 'is_best_seller', 'is_new_arrival')
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords', 'search_keywords'),
            'classes': ('collapse',)
        }),
        ('Metrics', {
            'fields': ('view_count', 'sales_count', 'average_rating', 'review_count'),
            'classes': ('collapse',)
        }),
    )
    
    def current_price(self, obj):
        return f"${obj.current_price}"
    current_price.short_description = 'Current Price'


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ['product', 'variant', 'quantity', 'price', 'line_total']
    readonly_fields = ['line_total']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['cart_id', 'customer', 'status', 'total_amount', 'item_count', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['cart_id', 'customer__name', 'customer__email']
    inlines = [CartItemInline]
    
    def item_count(self, obj):
        return obj.item_count
    item_count.short_description = 'Items'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ['title', 'variant_title', 'sku', 'quantity', 'price', 'line_total', 'fulfillment_status']
    readonly_fields = ['line_total']


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    fields = ['transaction_type', 'payment_method', 'amount', 'status', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_name', 'status', 'payment_status', 
                   'fulfillment_status', 'total_amount', 'order_date']
    list_filter = ['status', 'payment_status', 'fulfillment_status', 'order_date', 
                   'payment_method', 'source_name']
    search_fields = ['order_number', 'customer__name', 'customer__email', 'customer_email']
    date_hierarchy = 'order_date'
    inlines = [OrderItemInline, PaymentTransactionInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'customer_email', 'customer_phone')
        }),
        ('Status', {
            'fields': ('status', 'payment_status', 'fulfillment_status', 'risk_level')
        }),
        ('Financial', {
            'fields': ('currency', 'subtotal', 'tax_amount', 'shipping_amount', 
                      'discount_amount', 'total_amount')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_gateway', 'transaction_id')
        }),
        ('Shipping', {
            'fields': ('shipping_method', 'tracking_number', 'tracking_url', 'shipping_carrier')
        }),
        ('Dates', {
            'fields': ('order_date', 'confirmed_at', 'payment_date', 'shipped_date', 
                      'delivered_date', 'cancelled_at')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'admin_notes', 'notes', 'tags'),
            'classes': ('collapse',)
        }),
        ('Source', {
            'fields': ('source_name', 'referring_site', 'landing_site'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['order_date']
    
    def customer_name(self, obj):
        return obj.customer_name
    customer_name.short_description = 'Customer'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'coupon_type', 'discount_value', 'usage_count', 
                   'valid_from', 'valid_until', 'is_active']
    list_filter = ['coupon_type', 'applicable_to', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['code', 'name', 'description']
    filter_horizontal = ['applicable_categories', 'applicable_products']
    
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'description', 'coupon_type', 'discount_value')
        }),
        ('Application Rules', {
            'fields': ('applicable_to', 'applicable_categories', 'applicable_products')
        }),
        ('Constraints', {
            'fields': ('minimum_order_amount', 'maximum_discount_amount')
        }),
        ('Usage Limits', {
            'fields': ('usage_limit_per_coupon', 'usage_limit_per_customer', 'usage_count')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'is_active')
        }),
    )
    
    readonly_fields = ['usage_count']


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'rating', 'status', 'is_verified_purchase', 
                   'helpful_count', 'created_at']
    list_filter = ['rating', 'status', 'is_verified_purchase', 'created_at']
    search_fields = ['product__title', 'customer__name', 'title', 'review_text']
    
    fieldsets = (
        (None, {
            'fields': ('product', 'customer', 'order', 'rating', 'title', 'review_text')
        }),
        ('Status', {
            'fields': ('status', 'is_verified_purchase', 'reviewed_by', 'reviewed_at')
        }),
        ('Engagement', {
            'fields': ('helpful_count', 'not_helpful_count')
        }),
        ('Media', {
            'fields': ('images',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(status='APPROVED', reviewed_by=request.user, reviewed_at=timezone.now())
    approve_reviews.short_description = 'Approve selected reviews'
    
    def reject_reviews(self, request, queryset):
        queryset.update(status='REJECTED', reviewed_by=request.user, reviewed_at=timezone.now())
    reject_reviews.short_description = 'Reject selected reviews'


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'countries_display', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    
    def countries_display(self, obj):
        return ', '.join(obj.countries[:3]) + ('...' if len(obj.countries) > 3 else '')
    countries_display.short_description = 'Countries'


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'shipping_zone', 'rate_type', 'base_rate', 'is_active']
    list_filter = ['rate_type', 'is_active', 'shipping_zone']
    search_fields = ['name', 'description']


class ReturnRequestItemInline(admin.TabularInline):
    model = ReturnRequestItem
    extra = 0
    fields = ['order_item', 'quantity_requested', 'quantity_received', 
              'condition_received', 'action_taken', 'refund_amount']


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['return_number', 'order', 'customer', 'reason', 'status', 
                   'refund_amount', 'requested_at']
    list_filter = ['reason', 'status', 'requested_at']
    search_fields = ['return_number', 'order__order_number', 'customer__name']
    inlines = [ReturnRequestItemInline]
    
    fieldsets = (
        (None, {
            'fields': ('return_number', 'order', 'customer', 'reason', 'detailed_reason', 'status')
        }),
        ('Financial', {
            'fields': ('refund_amount', 'refund_method')
        }),
        ('Shipping', {
            'fields': ('return_shipping_label_url', 'return_tracking_number')
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at')
        }),
        ('Dates', {
            'fields': ('requested_at', 'approved_at', 'received_at', 'refunded_at')
        }),
        ('Notes', {
            'fields': ('notes', 'admin_notes', 'images'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['return_number', 'requested_at']


@admin.register(ProductAnalytics)
class ProductAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['product', 'total_views', 'times_added_to_cart', 'times_purchased', 
                   'conversion_rate', 'total_revenue', 'last_calculated_at']
    list_filter = ['last_calculated_at']
    search_fields = ['product__title']
    readonly_fields = ['last_calculated_at']


@admin.register(AbandonedCart)
class AbandonedCartAdmin(admin.ModelAdmin):
    list_display = ['cart', 'recovery_email_sent', 'recovery_email_count', 'recovered', 'created_at']
    list_filter = ['recovery_email_sent', 'recovered', 'created_at']
    search_fields = ['cart__customer__name', 'cart__customer__email']


@admin.register(ProductQuestion)
class ProductQuestionAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'is_answered', 'is_public', 'is_featured', 'created_at']
    list_filter = ['is_answered', 'is_public', 'is_featured', 'created_at']
    search_fields = ['product__title', 'customer__name', 'question', 'answer']
    
    fieldsets = (
        (None, {
            'fields': ('product', 'customer', 'question', 'answer')
        }),
        ('Status', {
            'fields': ('is_answered', 'is_public', 'is_featured', 'answered_by', 'answered_at')
        }),
        ('Engagement', {
            'fields': ('helpful_votes', 'total_votes')
        }),
    )


@admin.register(CustomerGroup)
class CustomerGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_percentage', 'free_shipping_threshold', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']


@admin.register(SalesChannel)
class SalesChannelAdmin(admin.ModelAdmin):
    list_display = ['name', 'channel_type', 'is_active', 'total_orders', 'total_revenue']
    list_filter = ['channel_type', 'is_active']
    search_fields = ['name', 'description']
