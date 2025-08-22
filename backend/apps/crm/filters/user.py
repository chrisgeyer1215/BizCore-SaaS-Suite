# ============================================================================
# backend/apps/crm/filters/user.py - User Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin
from ..models import CRMUserProfile, CRMRole


class CRMRoleFilter(CRMBaseFilter):
    """Filter for CRM Role model"""
    
    class Meta:
        model = CRMRole
        fields = ['is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class CRMUserProfileFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for CRM User Profile model"""
    
    user = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='User'
    )
    role = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Roles",
        label='Role'
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
    quota_min = django_filters.NumberFilter(
        field_name='sales_quota',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Quota'}),
        label='Min Sales Quota'
    )
    quota_max = django_filters.NumberFilter(
        field_name='sales_quota',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Quota'}),
        label='Max Sales Quota'
    )
    
    class Meta:
        model = CRMUserProfile
        fields = ['user', 'role', 'department', 'job_title']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            self.filters['user'].queryset = User.objects.filter(
                tenant_memberships__tenant=self.request.tenant,
                tenant_memberships__is_active=True
            ).distinct()
            
            self.filters['role'].queryset = CRMRole.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(user__email__icontains=value) |
            Q(department__icontains=value) |
            Q(job_title__icontains=value)
        )