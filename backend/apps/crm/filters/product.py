# ============================================================================
# backend/apps/crm/filters/product.py - Product Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin
from ..models import Product, ProductCategory, ProductBundle


class ProductCategoryFilter(CRMBaseFilter):
    """Filter for Product Category model"""
    
    parent = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Parent Category'
    )
    has_products = django_filters.BooleanFilter(
        method='filter_has_products',
        widget=forms.CheckboxInput(),
        label='Has Products'
    )
    
    class Meta:
        model = ProductCategory
        fields = ['parent', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['parent'].queryset = ProductCategory.objects.filter(
                tenant=self.request.tenant,
                parent__isnull=True,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_has_products(self, queryset, name, value):
        if value:
            return queryset.filter(products__isnull=False).distinct()
        return queryset


class ProductFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Product model"""
    
    category = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Category'
    )
    price_min = django_filters.NumberFilter(
        field_name='base_price',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Price'}),
        label='Min Price'
    )
    price_max = django_filters.NumberFilter(
        field_name='base_price',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Price'}),
        label='Max Price'
    )
    sku = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'SKU'}),
        label='SKU'
    )
    brand = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Brand'}),
        label='Brand'
    )
    has_bundles = django_filters.BooleanFilter(
        method='filter_has_bundles',
        widget=forms.CheckboxInput(),
        label='Part of Bundles'
    )
    never_sold = django_filters.BooleanFilter(
        method='filter_never_sold',
        widget=forms.CheckboxInput(),
        label='Never Sold'
    )
    top_selling = django_filters.BooleanFilter(
        method='filter_top_selling',
        widget=forms.CheckboxInput(),
        label='Top Selling'
    )
    
    class Meta:
        model = Product
        fields = [
            'category', 'price_min', 'price_max', 'sku', 'brand', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['category'].queryset = ProductCategory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(sku__icontains=value) |
            Q(brand__icontains=value)
        )
    
    def filter_has_bundles(self, queryset, name, value):
        if value:
            return queryset.filter(bundles_containing__isnull=False).distinct()
        return queryset
    
    def filter_never_sold(self, queryset, name, value):
        if value:
            return queryset.filter(opportunity_products__isnull=True)
        return queryset
    
    def filter_top_selling(self, queryset, name, value):
        if value:
            from django.db.models import Count
            return queryset.annotate(
                sales_count=Count('opportunity_products')
            ).filter(sales_count__gt=0).order_by('-sales_count')
        return queryset


class ProductBundleFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Product Bundle model"""
    
    bundle_price_min = django_filters.NumberFilter(
        field_name='bundle_price',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Bundle Price'}),
        label='Min Bundle Price'
    )
    bundle_price_max = django_filters.NumberFilter(
        field_name='bundle_price',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Bundle Price'}),
        label='Max Bundle Price'
    )
    discount_min = django_filters.NumberFilter(
        field_name='discount_amount',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Discount'}),
        label='Min Discount'
    )
    product_count_min = django_filters.NumberFilter(
        method='filter_product_count_min',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Products'}),
        label='Min Products'
    )
    
    class Meta:
        model = ProductBundle
        fields = ['is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_product_count_min(self, queryset, name, value):
        if value:
            from django.db.models import Count
            return queryset.annotate(
                product_count=Count('products')
            ).filter(product_count__gte=value)
        return queryset