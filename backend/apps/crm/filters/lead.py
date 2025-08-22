# ============================================================================
# backend/apps/crm/filters/lead.py - Lead Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Lead, LeadSource


class LeadSourceFilter(CRMBaseFilter):
    """Filter for Lead Source model"""
    
    source_type = django_filters.ChoiceFilter(
        choices=LeadSource.SOURCE_TYPES,
        empty_label="All Types",
        label='Source Type'
    )
    cost_min = django_filters.NumberFilter(
        field_name='cost_per_lead',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Cost'}),
        label='Min Cost per Lead'
    )
    cost_max = django_filters.NumberFilter(
        field_name='cost_per_lead',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Cost'}),
        label='Max Cost per Lead'
    )
    
    class Meta:
        model = LeadSource
        fields = ['source_type', 'is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(campaign_name__icontains=value)
        )


class LeadFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Lead model"""
    
    source = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Sources",
        label='Lead Source'
    )
    status = django_filters.ChoiceFilter(
        choices=Lead.LEAD_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    rating = django_filters.ChoiceFilter(
        choices=Lead.LEAD_RATINGS,
        empty_label="All Ratings",
        label='Rating'
    )
    score_min = django_filters.NumberFilter(
        field_name='score',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Score'}),
        label='Min Score'
    )
    score_max = django_filters.NumberFilter(
        field_name='score',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Score'}),
        label='Max Score'
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
    company = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Company'}),
        label='Company'
    )
    industry = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Industry'}),
        label='Industry'
    )
    converted = django_filters.BooleanFilter(
        method='filter_converted',
        widget=forms.Select(choices=[('', 'All'), (True, 'Converted'), (False, 'Not Converted')]),
        label='Conversion Status'
    )
    has_activities = django_filters.BooleanFilter(
        method='filter_has_activities',
        widget=forms.CheckboxInput(),
        label='Has Recent Activities'
    )
    hot_leads = django_filters.BooleanFilter(
        method='filter_hot_leads',
        widget=forms.CheckboxInput(),
        label='Hot Leads (Score > 80)'
    )
    stale_leads = django_filters.BooleanFilter(
        method='filter_stale_leads',
        widget=forms.CheckboxInput(),
        label='Stale Leads (No activity in 30 days)'
    )
    
    class Meta:
        model = Lead
        fields = [
            'source', 'status', 'rating', 'converted',
            'score_min', 'score_max', 'country', 'state', 'city',
            'company', 'industry'
        ]
        assigned_field = 'owner'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['source'].queryset = LeadSource.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value) |
            Q(phone__icontains=value) |
            Q(company__icontains=value) |
            Q(job_title__icontains=value)
        )
    
    def filter_converted(self, queryset, name, value):
        if value is not None:
            if value:
                return queryset.filter(converted_opportunity__isnull=False)
            else:
                return queryset.filter(converted_opportunity__isnull=True)
        return queryset
    
    def filter_has_activities(self, queryset, name, value):
        if value:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(
                activities__created_at__gte=thirty_days_ago
            ).distinct()
        return queryset
    
    def filter_hot_leads(self, queryset, name, value):
        if value:
            return queryset.filter(score__gt=80)
        return queryset
    
    def filter_stale_leads(self, queryset, name, value):
        if value:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.exclude(
                activities__created_at__gte=thirty_days_ago
            ).exclude(
                updated_at__gte=thirty_days_ago
            )
        return queryset