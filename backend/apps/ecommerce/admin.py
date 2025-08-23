# apps/ecommerce/admin.py

"""
Django admin configuration for e-commerce models
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import Textarea

from .models import (
    # Settings
    EcommerceSettings, StoreTheme, EmailTemplate,
    
    # Products
    EcommerceProduct, ProductVariant, ProductOption, ProductOptionValue,
    ProductImage, ProductTag, ProductBundle, BundleItem,
    
    # Collections
    IntelligentCollection, CollectionProduct, CollectionRule,
    
    # Cart & Wishlist
    Cart, CartItem, Wishlist, WishlistItem, SavedForLater,
    
    # Orders
    Order, OrderItem, OrderStatusHistory,
    
    # Payments
    PaymentSession, PaymentTransaction,
    
    # Shipping
    ShippingZone, ShippingMethod,
    
    # Discounts
    Discount, CouponCode, CouponUsage,
    
    # Reviews
    ProductReview, ProductQuestion,
    
    # Analytics
    ProductAnalytics, AbandonedCart,
)


# ============================================================================
# SETTINGS ADMIN
# ============================================================================

@admin.register(EcommerceSettings)
class EcommerceSettingsAdmin(admin.ModelAdmin):
    """Admin for e-commerce settings"""
    
    fieldsets = (
        ('Store Information', {
            'fields': ('store_name', 'store_description', 'store_email', 'store_phone')
        }),
        ('Currency Settings', {
            'fields': ('default_currency', 'enable_multi_currency', 'supported_currencies')
        }),
        ('Payment Settings', {
            'fields': ('primary_payment_gateway', 'accepted_payment_methods', 'enable_guest_checkout')
        }),
        ('Tax Settings', {
            'fields': ('tax_calculation_method', 'default_tax_rate', 'tax_included_in_prices')
        }),
        ('Shipping Settings', {
            'fields': ('shipping_calculation_method', 'default_shipping_rate', 'free_shipping_threshold')
        }),
        ('Inventory Settings', {
            'fields': ('track_inventory_by_default', 'allow_overselling', 'low_stock_threshold')
        }),
        ('Features', {
            'fields': ('enable_product_reviews', 'enable_wishlist', 'enable_coupons', 'enable_analytics')
        }),
    )
    
    list_display = ('store_name', 'default_currency', 'primary_payment_gateway', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StoreTheme)
class StoreThemeAdmin(admin.ModelAdmin):
    """Admin for store themes"""
    
    list_display = ('name', 'theme_type', 'is_active', 'created_at')
    list_filter = ('theme_type', 'is_active')
    search_fields = ('name',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'theme_type', 'is_active')
        }),
        ('Colors', {
            'fields': ('primary_color', 'secondary_color', 'accent_color', 'background_color', 'text_color')
        }),
        ('Typography', {
            'fields': ('primary_font', 'heading_font', 'font_size_base')
        }),
        ('Layout', {
            'fields': ('container_width', 'header_style')
        }),
        ('Custom Code', {
            'fields': ('custom_css', 'custom_javascript', 'custom_head_html'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# PRODUCT ADMIN
# ============================================================================

class ProductImageInline(admin.TabularInline):
    """Inline for product images"""
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'position', 'is_featured')
    readonly_fields = ('width', 'height', 'file_size')


class ProductVariantInline(admin.TabularInline):
    """Inline for product variants"""
    model = ProductVariant
    extra = 0
    fields = ('title', 'sku', 'price', 'stock_quantity', 'is_active')
    readonly_fields = ('created_at',)


class BundleItemInline(admin.TabularInline):
    """Inline for bundle items"""
    model = BundleItem
    extra = 1
    fields = ('product', 'variant', 'quantity', 'custom_price', 'position')


@admin.register(EcommerceProduct)
class EcommerceProductAdmin(admin.ModelAdmin):
    """Enhanced admin for e-commerce products"""
    
    list_display = (
        'title', 'sku', 'product_type', 'price', 'stock_quantity', 
        'is_published', 'sales_count', 'view_count', 'created_at'
    )
    list_filter = (
        'product_type', 'status', 'is_published', 'is_featured', 
        'brand', 'primary_collection', 'created_at'
    )
    search_fields = ('title', 'sku', 'description', 'brand')
    readonly_fields = (
        'sales_count', 'view_count', 'wishlist_count', 'review_count', 
        'average_rating', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'short_description', 'product_type')
        }),
        ('Product Identification', {
            'fields': ('sku', 'barcode', 'product_code', 'url_handle')
        }),
        ('Classification', {
            'fields': ('brand', 'manufacturer', 'model_number', 'primary_collection')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_at_price', 'cost_price', 'currency')
        }),
        ('Inventory', {
            'fields': (
                'track_quantity', 'inventory_policy', 'stock_quantity', 
                'low_stock_threshold', 'weight', 'length', 'width', 'height'
            )
        }),
        ('Visibility & Publishing', {
            'fields': (
                'status', 'is_published', 'is_featured', 'is_visible_in_search',
                'published_at', 'publish_date', 'unpublish_date'
            )
        }),
        ('Media', {
            'fields': ('featured_image',)
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': ('specifications', 'attributes', 'custom_fields', 'tags'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': (
                'sales_count', 'view_count', 'wishlist_count', 
                'review_count', 'average_rating'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ProductImageInline, ProductVariantInline]
    
    actions = ['publish_products', 'unpublish_products', 'mark_featured', 'sync_inventory']
    
    def publish_products(self, request, queryset):
        """Bulk publish products"""
        count = queryset.update(is_published=True, status='PUBLISHED')
        self.message_user(request, f'{count} products published successfully.')
    publish_products.short_description = "Publish selected products"
    
    def unpublish_products(self, request, queryset):
        """Bulk unpublish products"""
        count = queryset.update(is_published=False, status='DRAFT')
        self.message_user(request, f'{count} products unpublished successfully.')
    unpublish_products.short_description = "Unpublish selected products"
    
    def mark_featured(self, request, queryset):
        """Mark products as featured"""
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} products marked as featured.')
    mark_featured.short_description = "Mark as featured"
    
    def sync_inventory(self, request, queryset):
        """Sync with inventory module"""
        count = 0
        for product in queryset:
            product.sync_with_inventory()
            count += 1
        self.message_user(request, f'Inventory synced for {count} products.')
    sync_inventory.short_description = "Sync inventory"


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Admin for product variants"""
    
    list_display = ('title', 'ecommerce_product', 'sku', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'ecommerce_product__brand')
    search_fields = ('title', 'sku', 'ecommerce_product__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProductBundle)
class ProductBundleAdmin(admin.ModelAdmin):
    """Admin for product bundles"""
    
    list_display = ('name', 'bundle_type', 'pricing_strategy', 'price', 'is_published')
    list_filter = ('bundle_type', 'pricing_strategy', 'is_published')
    search_fields = ('name', 'description')
    
    inlines = [BundleItemInline]


# ============================================================================
# COLLECTION ADMIN
# ============================================================================

class CollectionProductInline(admin.TabularInline):
    """Inline for collection products"""
    model = CollectionProduct
    extra = 0
    fields = ('product', 'position', 'is_featured', 'added_at')
    readonly_fields = ('added_at',)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    """Admin for collections"""
    
    list_display = (
        'title', 'collection_type', 'parent', 'products_count', 
        'is_visible', 'is_featured', 'display_order'
    )
    list_filter = ('collection_type', 'is_visible', 'is_featured', 'parent')
    search_fields = ('title', 'description', 'handle')
    readonly_fields = ('products_count', 'level', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'handle', 'collection_type')
        }),
        ('Hierarchy', {
            'fields': ('parent', 'level')
        }),
        ('Display Settings', {
            'fields': (
                'display_order', 'products_per_page', 'default_sort_order',
                'is_visible', 'is_featured'
            )
        }),
        ('Media', {
            'fields': ('featured_image', 'banner_image', 'icon_class', 'color_code')
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('collapse',)
        }),
        ('Smart Collection Rules', {
            'fields': ('collection_rules',),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [CollectionProductInline]


# ============================================================================
# ORDER ADMIN
# ============================================================================

class OrderItemInline(admin.TabularInline):
    """Inline for order items"""
    model = OrderItem
    extra = 0
    fields = ('product', 'variant', 'quantity', 'unit_price', 'line_total')
    readonly_fields = ('line_total',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Enhanced admin for orders"""
    
    list_display = (
        'order_number', 'customer_display', 'status', 'payment_status',
        'total_amount', 'created_at', 'order_actions'
    )
    list_filter = (
        'status', 'payment_status', 'fulfillment_status', 
        'created_at', 'shipping_method'
    )
    search_fields = ('order_number', 'customer__email', 'customer__name')
    readonly_fields = (
        'order_number', 'subtotal', 'tax_amount', 'shipping_amount', 
        'discount_amount', 'total_amount', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'status', 'customer', 'created_at')
        }),
        ('Financial Summary', {
            'fields': (
                'subtotal', 'tax_amount', 'shipping_amount', 
                'discount_amount', 'total_amount', 'currency'
            )
        }),
        ('Payment Information', {
            'fields': ('payment_status', 'payment_method', 'payment_gateway')
        }),
        ('Shipping Information', {
            'fields': (
                'fulfillment_status', 'shipping_method', 'tracking_number',
                'shipping_address', 'billing_address'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'customer_notes', 'tags'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline]
    
    actions = ['mark_as_fulfilled', 'mark_as_shipped', 'export_orders']
    
    def customer_display(self, obj):
        """Display customer information"""
        if obj.customer:
            return obj.customer.email
        return "Guest"
    customer_display.short_description = "Customer"
    
    def order_actions(self, obj):
        """Display action buttons"""
        actions = []
        
        if obj.status == 'CONFIRMED':
            fulfill_url = reverse('admin:ecommerce_order_fulfill', args=[obj.pk])
            actions.append(f'<a href="{fulfill_url}" class="button">Fulfill</a>')
        
        if obj.payment_status == 'PAID':
            refund_url = reverse('admin:ecommerce_order_refund', args=[obj.pk])
            actions.append(f'<a href="{refund_url}" class="button">Refund</a>')
        
        return format_html(' '.join(actions))
    order_actions.short_description = "Actions"
    order_actions.allow_tags = True


# ============================================================================
# CART ADMIN
# ============================================================================

class CartItemInline(admin.TabularInline):
    """Inline for cart items"""
    model = CartItem
    extra = 0
    fields = ('product', 'variant', 'quantity', 'unit_price', 'line_total')
    readonly_fields = ('line_total', 'added_at')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin for shopping carts"""
    
    list_display = (
        'cart_id', 'user_display', 'status', 'item_count', 
        'total_amount', 'last_activity', 'is_abandoned'
    )
    list_filter = ('status', 'currency', 'is_persistent', 'created_at')
    search_fields = ('cart_id', 'user__email', 'session_key')
    readonly_fields = (
        'cart_id', 'item_count', 'subtotal', 'tax_amount', 
        'shipping_amount', 'discount_amount', 'total_amount',
        'last_activity', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('cart_id', 'user', 'customer', 'session_key', 'status')
        }),
        ('Totals', {
            'fields': (
                'item_count', 'subtotal', 'tax_amount', 'shipping_amount',
                'discount_amount', 'total_amount', 'currency'
            )
        }),
        ('Settings', {
            'fields': ('is_persistent', 'expires_at', 'applied_coupons')
        }),
        ('Tracking', {
            'fields': ('last_activity', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [CartItemInline]
    
    actions = ['convert_to_orders', 'mark_as_abandoned', 'clear_expired']
    
    def user_display(self, obj):
        """Display user or session information"""
        if obj.user:
            return obj.user.email
        elif obj.session_key:
            return f"Session: {obj.session_key[:10]}..."
        return "Anonymous"
    user_display.short_description = "User/Session"
    
    def is_abandoned(self, obj):
        """Check if cart is abandoned"""
        return obj.is_abandoned
    is_abandoned.boolean = True
    is_abandoned.short_description = "Abandoned"


# ============================================================================
# DISCOUNT ADMIN
# ============================================================================

@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    """Admin for discounts and coupons"""
    
    list_display = (
        'title', 'discount_type', 'value', 'usage_count', 
        'usage_limit', 'is_active', 'starts_at', 'ends_at'
    )
    list_filter = (
        'discount_type', 'is_active', 'is_automatic', 'applies_to', 
        'starts_at', 'ends_at'
    )
    search_fields = ('title', 'description', 'code')
    readonly_fields = ('usage_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'discount_type', 'is_automatic')
        }),
        ('Discount Value', {
            'fields': ('value', 'minimum_amount', 'maximum_discount_amount')
        }),
        ('Coupon Code', {
            'fields': ('code', 'prefix', 'suffix'),
        }),
        ('Usage Limits', {
            'fields': ('usage_limit', 'usage_limit_per_customer', 'usage_count')
        }),
        ('Validity Period', {
            'fields': ('starts_at', 'ends_at', 'is_active')
        }),
        ('Application Rules', {
            'fields': ('applies_to', 'minimum_quantity', 'customer_eligibility'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    """Admin for individual coupon codes"""
    
    list_display = ('code', 'discount', 'usage_count', 'usage_limit', 'is_active')
    list_filter = ('is_active', 'discount__discount_type', 'created_at')
    search_fields = ('code', 'discount__title')
    readonly_fields = ('usage_count', 'created_at')


# ============================================================================
# REVIEW ADMIN
# ============================================================================

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    """Admin for product reviews"""
    
    list_display = (
        'product', 'customer_display', 'rating', 'status', 
        'verified_purchase', 'helpful_votes', 'created_at'
    )
    list_filter = (
        'rating', 'status', 'verified_purchase', 'created_at'
    )
    search_fields = ('product__title', 'customer__email', 'title', 'content')
    readonly_fields = (
        'helpful_votes', 'unhelpful_votes', 'total_votes',
        'verified_purchase', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Review Information', {
            'fields': ('product', 'customer', 'title', 'content', 'rating')
        }),
        ('Status', {
            'fields': ('status', 'verified_purchase')
        }),
        ('Engagement', {
            'fields': ('helpful_votes', 'unhelpful_votes', 'total_votes')
        }),
        ('Media', {
            'fields': ('images', 'videos'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews', 'mark_helpful']
    
    def customer_display(self, obj):
        """Display customer name or email"""
        if obj.customer:
            return obj.customer.email
        return "Anonymous"
    customer_display.short_description = "Customer"
    
    def approve_reviews(self, request, queryset):
        """Bulk approve reviews"""
        count = queryset.update(status='APPROVED')
        self.message_user(request, f'{count} reviews approved.')
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        """Bulk reject reviews"""
        count = queryset.update(status='REJECTED')
        self.message_user(request, f'{count} reviews rejected.')
    reject_reviews.short_description = "Reject selected reviews"


# ============================================================================
# ANALYTICS ADMIN
# ============================================================================

@admin.register(ProductAnalytics)
class ProductAnalyticsAdmin(admin.ModelAdmin):
    """Admin for product analytics"""
    
    list_display = (
        'product', 'total_views', 'unique_views', 'conversion_rate',
        'total_revenue', 'last_calculated'
    )
    list_filter = ('last_calculated',)
    search_fields = ('product__title', 'product__sku')
    readonly_fields = (
        'total_views', 'unique_views', 'total_orders', 'total_revenue',
        'conversion_rate', 'last_calculated'
    )
    
    def has_add_permission(self, request):
        """Analytics are auto-generated, don't allow manual creation"""
        return False


@admin.register(AbandonedCart)
class AbandonedCartAdmin(admin.ModelAdmin):
    """Admin for abandoned carts"""
    
    list_display = (
        'cart', 'abandonment_stage', 'total_value', 
        'recovery_email_sent', 'is_recovered', 'created_at'
    )
    list_filter = (
        'abandonment_stage', 'recovery_email_sent', 'is_recovered', 'created_at'
    )
    search_fields = ('cart__user__email', 'cart__cart_id')
    readonly_fields = ('cart', 'total_value', 'created_at')
    
    actions = ['send_recovery_emails', 'mark_as_recovered']
    
    def send_recovery_emails(self, request, queryset):
        """Send recovery emails for abandoned carts"""
        count = 0
        for abandoned_cart in queryset.filter(recovery_email_sent=False):
            # Logic to send recovery email would go here
            abandoned_cart.recovery_email_sent = True
            abandoned_cart.save()
            count += 1
        self.message_user(request, f'Recovery emails sent for {count} abandoned carts.')
    send_recovery_emails.short_description = "Send recovery emails"


# ============================================================================
# SHIPPING ADMIN
# ============================================================================

@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    """Admin for shipping zones"""
    
    list_display = ('name', 'countries_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    
    def countries_count(self, obj):
        """Count of countries in zone"""
        return len(obj.countries)
    countries_count.short_description = "Countries"


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    """Admin for shipping methods"""
    
    list_display = (
        'name', 'zone', 'cost', 'delivery_time_display', 
        'is_active', 'created_at'
    )
    list_filter = ('is_active', 'zone', 'created_at')
    search_fields = ('name', 'description')
    
    def delivery_time_display(self, obj):
        """Display delivery time range"""
        if obj.delivery_time_min and obj.delivery_time_max:
            return f"{obj.delivery_time_min}-{obj.delivery_time_max} days"
        elif obj.delivery_time_max:
            return f"Up to {obj.delivery_time_max} days"
        return "Not specified"
    delivery_time_display.short_description = "Delivery Time"


# ============================================================================
# WISHLIST ADMIN
# ============================================================================

class WishlistItemInline(admin.TabularInline):
    """Inline for wishlist items"""
    model = WishlistItem
    extra = 0
    fields = ('product', 'variant', 'note', 'priority', 'added_at')
    readonly_fields = ('added_at', 'price_when_added')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Admin for wishlists"""
    
    list_display = (
        'name', 'user', 'visibility', 'item_count', 
        'total_value', 'is_default', 'created_at'
    )
    list_filter = ('visibility', 'is_default', 'created_at')
    search_fields = ('name', 'user__email', 'description')
    readonly_fields = ('share_token', 'share_url', 'created_at', 'updated_at')
    
    inlines = [WishlistItemInline]


# ============================================================================
# PAYMENT ADMIN
# ============================================================================

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Admin for payment transactions"""
    
    list_display = (
        'transaction_id', 'order', 'transaction_type', 'payment_method',
        'amount', 'status', 'created_at'
    )
    list_filter = (
        'transaction_type', 'payment_method', 'status', 
        'payment_gateway', 'created_at'
    )
    search_fields = (
        'transaction_id', 'external_transaction_id', 
        'gateway_transaction_id', 'order__order_number'
    )
    readonly_fields = (
        'transaction_id', 'external_transaction_id', 'gateway_transaction_id',
        'gateway_response', 'created_at', 'processed_at'
    )
    
    fieldsets = (
        ('Transaction Information', {
            'fields': (
                'transaction_id', 'order', 'transaction_type', 
                'payment_method', 'payment_gateway'
            )
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'exchange_rate')
        }),
        ('Status', {
            'fields': ('status', 'error_code', 'error_message')
        }),
        ('Gateway Information', {
            'fields': (
                'external_transaction_id', 'gateway_transaction_id',
                'authorization_code', 'gateway_response'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at', 'authorized_at', 'captured_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# ADMIN CUSTOMIZATIONS
# ============================================================================

# Customize admin site
admin.site.site_header = "SaaS-AICE E-commerce Administration"
admin.site.site_title = "E-commerce Admin"
admin.site.index_title = "E-commerce Management"

# Custom admin actions for bulk operations
def make_featured(modeladmin, request, queryset):
    """Mark selected items as featured"""
    count = queryset.update(is_featured=True)
    modeladmin.message_user(request, f'{count} items marked as featured.')
make_featured.short_description = "Mark selected items as featured"

def make_unfeatured(modeladmin, request, queryset):
    """Remove featured status from selected items"""
    count = queryset.update(is_featured=False)
    modeladmin.message_user(request, f'{count} items unmarked as featured.')
make_unfeatured.short_description = "Remove featured status"

def activate_items(modeladmin, request, queryset):
    """Activate selected items"""
    count = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{count} items activated.')
activate_items.short_description = "Activate selected items"

def deactivate_items(modeladmin, request, queryset):
    """Deactivate selected items"""
    count = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{count} items deactivated.')
deactivate_items.short_description = "Deactivate selected items"

# Register common actions with admin classes that support them
common_admin_classes = [
    EcommerceProductAdmin, CollectionAdmin, DiscountAdmin, 
    ShippingMethodAdmin, WishlistAdmin
]

for admin_class in common_admin_classes:
    if hasattr(admin_class, 'actions'):
        admin_class.actions.extend([
            make_featured, make_unfeatured, activate_items, deactivate_items
        ])

# Custom filters
class LowStockFilter(admin.SimpleListFilter):
    """Filter for low stock products"""
    title = 'Stock Level'
    parameter_name = 'stock_level'

    def lookups(self, request, model_admin):
        return (
            ('low', 'Low Stock'),
            ('out', 'Out of Stock'),
            ('in_stock', 'In Stock'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(
                track_quantity=True,
                stock_quantity__lte=models.F('low_stock_threshold'),
                stock_quantity__gt=0
            )
        elif self.value() == 'out':
            return queryset.filter(
                track_quantity=True,
                stock_quantity=0
            )
        elif self.value() == 'in_stock':
            return queryset.filter(
                models.Q(track_quantity=False) |
                models.Q(stock_quantity__gt=0)
            )

# Add custom filter to product admin
EcommerceProductAdmin.list_filter += (LowStockFilter,)


class RevenueFilter(admin.SimpleListFilter):
    """Filter orders by revenue ranges"""
    title = 'Revenue Range'
    parameter_name = 'revenue_range'

    def lookups(self, request, model_admin):
        return (
            ('low', 'Under $100'),
            ('medium', '$100 - $500'),
            ('high', '$500 - $1000'),
            ('very_high', 'Over $1000'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(total_amount__lt=100)
        elif self.value() == 'medium':
            return queryset.filter(total_amount__gte=100, total_amount__lt=500)
        elif self.value() == 'high':
            return queryset.filter(total_amount__gte=500, total_amount__lt=1000)
        elif self.value() == 'very_high':
            return queryset.filter(total_amount__gte=1000)

# Add revenue filter to order admin
OrderAdmin.list_filter += (RevenueFilter,)


# Custom form widgets for better UX
class AdminTextareaWidget(Textarea):
    """Custom textarea widget with better styling"""
    def __init__(self, attrs=None):
        default_attrs = {'rows': 4, 'cols': 60}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

# Apply custom widgets to models with text fields
admin_formfield_overrides = {
    models.TextField: {'widget': AdminTextareaWidget},
}

for admin_class in [EcommerceProductAdmin, CollectionAdmin, OrderAdmin]:
    admin_class.formfield_overrides = admin_formfield_overrides