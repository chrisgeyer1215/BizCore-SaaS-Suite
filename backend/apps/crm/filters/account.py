# ============================================================================
# backend/apps/crm/filters/account.py - Account Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Account, Contact, Industry


class IndustryFilter(CRMBaseFilter):
    """Filter for Industry model"""
    
    parent = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Parent Industry'
    )
    has_children = django_filters.BooleanFilter(
        method='filter_has_children',
        widget=forms.CheckboxInput(),
        label='Has Sub-industries'
    )
    
    class Meta:
        model = Industry
        fields = ['parent', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['parent'].queryset = Industry.objects.filter(
                tenant=self.request.tenant,
                parent__isnull=True,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_has_children(self, queryset, name, value):
        if value:
            return queryset.filter(children__isnull=False).distinct()
        return queryset


class AccountFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Account model"""
    
    industry = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Industries",
        label='Industry'
    )
    account_type = django_filters.ChoiceFilter(
        choices=Account.ACCOUNT_TYPES,
        empty_label="All Types",
        label='Account Type'
    )
    revenue_min = django_filters.NumberFilter(
        field_name='annual_revenue',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Revenue'}),
        label='Min Revenue'
    )
    revenue_max = django_filters.NumberFilter(
        field_name='annual_revenue',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Revenue'}),
        label='Max Revenue'
    )
    employees_min = django_filters.NumberFilter(
        field_name='number_of_employees',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Employees'}),
        label='Min Employees'
    )
    employees_max = django_filters.NumberFilter(
        field_name='number_of_employees',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Employees'}),
        label='Max Employees'
    )
    country = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Country'}),
        label='Country'
    )
    state = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'State/Province'}),
        label='State/Province'
    )
    city = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'City'}),
        label='City'
    )
    has_opportunities = django_filters.BooleanFilter(
        method='filter_has_opportunities',
        widget=forms.CheckboxInput(),
        label='Has Opportunities'
    )
    has_activities = django_filters.BooleanFilter(
        method='filter_has_activities',
        widget=forms.CheckboxInput(),
        label='Has Recent Activities'
    )
    
    class Meta:
        model = Account
        fields = [
            'industry', 'account_type', 'is_active',
            'revenue_min', 'revenue_max', 'employees_min', 'employees_max',
            'country', 'state', 'city'
        ]
        assigned_field = 'account_manager'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['industry'].queryset = Industry.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(website__icontains=value) |
            Q(description__icontains=value) |
            Q(contacts__first_name__icontains=value) |
            Q(contacts__last_name__icontains=value) |
            Q(contacts__email__icontains=value)
        ).distinct()
    
    def filter_has_opportunities(self, queryset, name, value):
        if value:
            return queryset.filter(opportunities__isnull=False).distinct()
        return queryset
    
    def filter_has_activities(self, queryset, name, value):
        if value:
            from django.utils import timezone
            from datetime import timedelta
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(
                activities__created_at__gte=thirty_days_ago
            ).distinct()
        return queryset


class ContactFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Contact model"""
    
    account = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Accounts",
        label='Account'
    )
    is_primary = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Primary'), (False, 'Secondary')]),
        label='Contact Type'
    )
    has_email = django_filters.BooleanFilter(
        method='filter_has_email',
        widget=forms.CheckboxInput(),
        label='Has Email'
    )
    has_phone = django_filters.BooleanFilter(
        method='filter_has_phone',
        widget=forms.CheckboxInput(),
        label='Has Phone'
    )
    department = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Department'}),
        label='Department'
    )
    job_title = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Job Title'}),
        label='Job Title'
    )
    
    class Meta:
        model = Contact
        fields = ['account', 'is_primary', 'department', 'job_title', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['account'].queryset = Account.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value) |
            Q(phone__icontains=value) |
            Q(account__name__icontains=value)
        )
    
    def filter_has_email(self, queryset, name, value):
        if value:
            return queryset.exclude(Q(email__isnull=True) | Q(email__exact=''))
        return queryset
    
    def filter_has_phone(self, queryset, name, value):
        if value:
            return queryset.exclude(Q(phone__isnull=True) | Q(phone__exact=''))
        return queryset