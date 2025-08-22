# backend/apps/crm/filters/base.py - Base Filter Classes
# ============================================================================

import django_filters
from django.db.models import Q
from django import forms
from django.utils import timezone
from datetime import timedelta

from apps.core.filters import TenantFilterMixin


class CRMBaseFilter(TenantFilterMixin, django_filters.FilterSet):
    """Base filter class for CRM models"""
    
    search = django_filters.CharFilter(method='search_filter', label='Search')
    created_date_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Created From'
    )
    created_date_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Created To'
    )
    updated_date_from = django_filters.DateFilter(
        field_name='updated_at',
        lookup_expr='date__gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Updated From'
    )
    updated_date_to = django_filters.DateFilter(
        field_name='updated_at',
        lookup_expr='date__lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Updated To'
    )
    is_active = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Active'), (False, 'Inactive')]),
        label='Status'
    )
    
    class Meta:
        abstract = True
    
    def search_filter(self, queryset, name, value):
        """Override in subclasses to define search logic"""
        return queryset
    
    @property
    def form(self):
        form = super().form
        # Add CSS classes to form widgets
        for field_name, field in form.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.URLInput)):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
        return form


class DateRangeFilterMixin:
    """Mixin for common date range filters"""
    
    date_range = django_filters.ChoiceFilter(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_quarter', 'This Quarter'),
            ('this_year', 'This Year'),
            ('last_year', 'Last Year'),
        ],
        method='filter_date_range',
        label='Date Range'
    )
    
    def filter_date_range(self, queryset, name, value):
        """Filter by predefined date ranges"""
        now = timezone.now()
        today = now.date()
        
        if value == 'today':
            return queryset.filter(created_at__date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif value == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_week)
        elif value == 'last_week':
            start_last_week = today - timedelta(days=today.weekday() + 7)
            end_last_week = start_last_week + timedelta(days=6)
            return queryset.filter(created_at__date__range=[start_last_week, end_last_week])
        elif value == 'this_month':
            start_month = today.replace(day=1)
            return queryset.filter(created_at__date__gte=start_month)
        elif value == 'last_month':
            if today.month == 1:
                last_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                last_month = today.replace(month=today.month - 1, day=1)
            
            if last_month.month == 12:
                end_last_month = last_month.replace(year=last_month.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_last_month = last_month.replace(month=last_month.month + 1, day=1) - timedelta(days=1)
            
            return queryset.filter(created_at__date__range=[last_month, end_last_month])
        elif value == 'this_quarter':
            quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            return queryset.filter(created_at__date__gte=quarter_start)
        elif value == 'this_year':
            year_start = today.replace(month=1, day=1)
            return queryset.filter(created_at__date__gte=year_start)
        elif value == 'last_year':
            last_year_start = today.replace(year=today.year - 1, month=1, day=1)
            last_year_end = today.replace(year=today.year - 1, month=12, day=31)
            return queryset.filter(created_at__date__range=[last_year_start, last_year_end])
        
        return queryset


class AssigneeFilterMixin:
    """Mixin for filtering by assigned users"""
    
    assigned_to = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='Assigned To'
    )
    assigned_to_me = django_filters.BooleanFilter(
        method='filter_assigned_to_me',
        widget=forms.CheckboxInput(),
        label='Assigned to Me'
    )
    unassigned = django_filters.BooleanFilter(
        method='filter_unassigned',
        widget=forms.CheckboxInput(),
        label='Unassigned'
    )
    
    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        
        if request and request.tenant:
            # Set queryset for assigned_to field
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.filters['assigned_to'].queryset = User.objects.filter(
                tenant_memberships__tenant=request.tenant,
                tenant_memberships__is_active=True
            ).distinct()
    
    def filter_assigned_to_me(self, queryset, name, value):
        if value and hasattr(self.request, 'user'):
            field_name = getattr(self.Meta, 'assigned_field', 'assigned_to')
            return queryset.filter(**{field_name: self.request.user})
        return queryset
    
    def filter_unassigned(self, queryset, name, value):
        if value:
            field_name = getattr(self.Meta, 'assigned_field', 'assigned_to')
            return queryset.filter(**{f'{field_name}__isnull': True})
        return queryset