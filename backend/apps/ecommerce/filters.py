import django_filters
from django.db.models import Q
from decimal import Decimal
from .models import (
    EcommerceProduct, Collection, Order, Coupon, ProductReview,
    Cart, ReturnRequest, ProductAnalytics
)


class ProductFilter(django_filters.FilterSet):
    """Filter for e-commerce products"""
    
    title = django_filters.CharFilter(
        field_name='title', 
        lookup_expr='icontains',
        label='Product Title'
    )
    
    price_min = django_filters.NumberFilter(
        field_name='regular_price',
        lookup_expr='gte',
        label='Min Price'
    )
    
    price_max = django_filters.NumberFilter(
        field_name='regular_price',
        lookup_expr='lte',
        label='Max Price'
    )
    
    collections = django_filters.ModelMultipleChoiceFilter(
        queryset=Collection.objects.none(),  # Will be set in __init__
        field_name='collections',
        label='Collections'
    )
    
    vendor = django_filters.CharFilter(
        field_name='vendor',
        lookup_expr='icontains',
        label='Vendor'
    )
    
    is_featured = django_filters.BooleanFilter(
        field_name='is_featured',
        label='Featured Products'
    )
    
    is_on_sale = django_filters.BooleanFilter(
        method='filter_on_sale',
        label='On Sale'
    )
    
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='In Stock'
    )
    
    rating_min = django_filters.NumberFilter(
        field_name='average_rating',
        lookup_expr='gte',
        label='Min Rating'
    )
    
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search'
    )
    
    class Meta:
        model = EcommerceProduct
        fields = [
            'status', 'product_type', 'visibility', 'is_published',
            'is_featured', 'is_best_seller', 'is_new_arrival'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'request') and hasattr(self.request, 'tenant'):
            self.filters['collections'].queryset = Collection.objects.filter(
                tenant=self.request.tenant,
                is_visible=True
            )
    
    def filter_on_sale(self, queryset, name, value):
        """Filter products on sale"""
        if value:
            return queryset.filter(
                Q(sale_price__isnull=False) & 
                Q(sale_price__lt=F('regular_price')) &
                (Q(sale_price_start__isnull=True) | Q(sale_price_start__lte=timezone.now())) &
                (Q(sale_price_end__isnull=True) | Q(sale_price_end__gte=timezone.now()))
            )
        return queryset
    
    def filter_in_stock(self, queryset, name, value):
        """Filter products in stock"""
        if value:
            return queryset.filter(
                Q(track_quantity=False) | 
                Q(stock_quantity__gt=0) | 
                Q(continue_selling_when_out_of_stock=True)
            )
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(title__icontains=value) |
                Q(description__icontains=value) |
                Q(short_description__icontains=value) |
                Q(tags__icontains=value) |
                Q(vendor__icontains=value) |
                Q(inventory_product__sku__icontains=value)
            )
        return queryset


class OrderFilter(django_filters.FilterSet):
    """Filter for orders"""
    
    order_number = django_filters.CharFilter(
        field_name='order_number',
        lookup_expr='icontains',
        label='Order Number'
    )
    
    customer_name = django_filters.CharFilter(
        method='filter_customer_name',
        label='Customer Name'
    )
    
    customer_email = django_filters.CharFilter(
        field_name='customer_email',
        lookup_expr='icontains',
        label='Customer Email'
    )
    
    date_from = django_filters.DateFilter(
        field_name='order_date',
        lookup_expr='gte',
        label='From Date'
    )
    
    date_to = django_filters.DateFilter(
        field_name='order_date',
        lookup_expr='lte',
        label='To Date'
    )
    
    total_min = django_filters.NumberFilter(
        field_name='total_amount',
        lookup_expr='gte',
        label='Min Total'
    )
    
    total_max = django_filters.NumberFilter(
        field_name='total_amount',
        lookup_expr='lte',
        label='Max Total'
    )
    
    class Meta:
        model = Order
        fields = [
            'status', 'payment_status', 'fulfillment_status',
            'payment_method', 'source_name', 'risk_level'
        ]
    
    def filter_customer_name(self, queryset, name, value):
        """Search customer name in multiple fields"""
        if value:
            return queryset.filter(
                Q(customer__name__icontains=value) |
                Q(billing_address__first_name__icontains=value) |
                Q(billing_address__last_name__icontains=value)
            )
        return queryset


class CouponFilter(django_filters.FilterSet):
    """Filter for coupons"""
    
    code = django_filters.CharFilter(
        field_name='code',
        lookup_expr='icontains',
        label='Coupon Code'
    )
    
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Coupon Name'
    )
    
    is_valid = django_filters.BooleanFilter(
        method='filter_valid',
        label='Currently Valid'
    )
    
    usage_remaining = django_filters.BooleanFilter(
        method='filter_usage_remaining',
        label='Usage Remaining'
    )
    
    class Meta:
        model = Coupon
        fields = ['coupon_type', 'applicable_to', 'is_active']
    
    def filter_valid(self, queryset, name, value):
        """Filter currently valid coupons"""
        if value:
            now = timezone.now()
            return queryset.filter(
                is_active=True,
                valid_from__lte=now
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=now)
            )
        return queryset
    
    def filter_usage_remaining(self, queryset, name, value):
        """Filter coupons with remaining usage"""
        if value:
            return queryset.filter(
                Q(usage_limit_per_coupon__isnull=True) |
                Q(usage_count__lt=F('usage_limit_per_coupon'))
            )
        return queryset


class ReviewFilter(django_filters.FilterSet):
    """Filter for product reviews"""
    
    product_title = django_filters.CharFilter(
        field_name='product__title',
        lookup_expr='icontains',
        label='Product'
    )
    
    customer_name = django_filters.CharFilter(
        field_name='customer__name',
        lookup_expr='icontains',
        label='Customer'
    )
    
    rating = django_filters.NumberFilter(
        field_name='rating',
        label='Rating'
    )
    
    rating_min = django_filters.NumberFilter(
        field_name='rating',
        lookup_expr='gte',
        label='Min Rating'
    )
    
    date_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='From Date'
    )
    
    date_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='To Date'
    )
    
    class Meta:
        model = ProductReview
        fields = ['status', 'is_verified_purchase']


class CartFilter(django_filters.FilterSet):
    """Filter for shopping carts"""
    
    customer_name = django_filters.CharFilter(
        field_name='customer__name',
        lookup_expr='icontains',
        label='Customer'
    )
    
    total_min = django_filters.NumberFilter(
        field_name='total',
        lookup_expr='gte',
        label='Min Total'
    )
    
    total_max = django_filters.NumberFilter(
        field_name='total',
        lookup_expr='lte',
        label='Max Total'
    )
    
    created_from = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Created From'
    )
    
    created_to = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Created To'
    )
    
    class Meta:
        model = Cart
        fields = ['status', 'currency']


class ReturnRequestFilter(django_filters.FilterSet):
    """Filter for return requests"""
    
    return_number = django_filters.CharFilter(
        field_name='return_number',
        lookup_expr='icontains',
        label='Return Number'
    )
    
    order_number = django_filters.CharFilter(
        field_name='order__order_number',
        lookup_expr='icontains',
        label='Order Number'
    )
    
    customer_name = django_filters.CharFilter(
        field_name='customer__name',
        lookup_expr='icontains',
        label='Customer'
    )
    
    requested_from = django_filters.DateFilter(
        field_name='requested_at',
        lookup_expr='gte',
        label='Requested From'
    )
    
    requested_to = django_filters.DateFilter(
        field_name='requested_at',
        lookup_expr='lte',
        label='Requested To'
    )
    
    class Meta:
        model = ReturnRequest
        fields = ['reason', 'status']


class ProductAnalyticsFilter(django_filters.FilterSet):
    """Filter for product analytics"""
    
    product_title = django_filters.CharFilter(
        field_name='product__title',
        lookup_expr='icontains',
        label='Product'
    )
    
    views_min = django_filters.NumberFilter(
        field_name='total_views',
        lookup_expr='gte',
        label='Min Views'
    )
    
    sales_min = django_filters.NumberFilter(
        field_name='times_purchased',
        lookup_expr='gte',
        label='Min Sales'
    )
    
    revenue_min = django_filters.NumberFilter(
        field_name='total_revenue',
        lookup_expr='gte',
        label='Min Revenue'
    )
    
    conversion_min = django_filters.NumberFilter(
        field_name='conversion_rate',
        lookup_expr='gte',
        label='Min Conversion Rate'
    )
    
    class Meta:
        model = ProductAnalytics
        fields = []
