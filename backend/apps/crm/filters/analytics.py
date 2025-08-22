# ============================================================================
# backend/apps/crm/filters/analytics.py - Analytics Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin
from ..models import Report, Dashboard, Forecast, PerformanceMetric


class ReportFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Report model"""
    
    report_type = django_filters.ChoiceFilter(
        choices=Report.REPORT_TYPES,
        empty_label="All Types",
        label='Report Type'
    )
    category = django_filters.ChoiceFilter(
        choices=Report.REPORT_CATEGORIES,
        empty_label="All Categories",
        label='Category'
    )
    created_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='Created By'
    )
    is_public = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Public'), (False, 'Private')]),
        label='Visibility'
    )
    shared_with_me = django_filters.BooleanFilter(
        method='filter_shared_with_me',
        widget=forms.CheckboxInput(),
        label='Shared With Me'
    )
    
    class Meta:
        model = Report
        fields = ['report_type', 'category', 'created_by', 'is_public', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.filters['created_by'].queryset = User.objects.filter(
                tenant_memberships__tenant=self.request.tenant,
                tenant_memberships__is_active=True
            ).distinct()
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_shared_with_me(self, queryset, name, value):
        if value and hasattr(self.request, 'user'):
            return queryset.filter(shared_with=self.request.user)
        return queryset


class DashboardFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Dashboard model"""
    
    created_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='Created By'
    )
    is_public = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Public'), (False, 'Private')]),
        label='Visibility'
    )
    
    class Meta:
        model = Dashboard
        fields = ['created_by', 'is_public', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.filters['created_by'].queryset = User.objects.filter(
                tenant_memberships__tenant=self.request.tenant,
                tenant_memberships__is_active=True
            ).distinct()
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class ForecastFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Forecast model"""
    
    forecast_type = django_filters.ChoiceFilter(
        choices=Forecast.FORECAST_TYPES,
        empty_label="All Types",
        label='Forecast Type'
    )
    forecast_date_from = django_filters.DateFilter(
        field_name='forecast_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Forecast Date From'
    )
    forecast_date_to = django_filters.DateFilter(
        field_name='forecast_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Forecast Date To'
    )
    accuracy_min = django_filters.NumberFilter(
        field_name='accuracy_score',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Accuracy %'}),
        label='Min Accuracy %'
    )
    
    class Meta:
        model = Forecast
        fields = ['forecast_type']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class PerformanceMetricFilter(CRMBaseFilter):
    """Filter for Performance Metric model"""
    
    metric_name = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Metric Name'}),
        label='Metric Name'
    )
    metric_date_from = django_filters.DateFilter(
        field_name='metric_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date From'
    )
    metric_date_to = django_filters.DateFilter(
        field_name='metric_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date To'
    )
    value_min = django_filters.NumberFilter(
        field_name='metric_value',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Value'}),
        label='Min Value'
    )
    value_max = django_filters.NumberFilter(
        field_name='metric_value',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Value'}),
        label='Max Value'
    )
    
    class Meta:
        model = PerformanceMetric
        fields = ['metric_name']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(metric_name__icontains=value) |
            Q(description__icontains=value)
        )