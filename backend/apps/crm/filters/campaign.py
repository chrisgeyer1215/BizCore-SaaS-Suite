# ============================================================================
# backend/apps/crm/filters/campaign.py - Campaign Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Campaign, CampaignMember


class CampaignFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Campaign model"""
    
    campaign_type = django_filters.ChoiceFilter(
        choices=Campaign.CAMPAIGN_TYPES,
        empty_label="All Types",
        label='Campaign Type'
    )
    status = django_filters.ChoiceFilter(
        choices=Campaign.CAMPAIGN_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    budget_min = django_filters.NumberFilter(
        field_name='budget',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Budget'}),
        label='Min Budget'
    )
    budget_max = django_filters.NumberFilter(
        field_name='budget',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Budget'}),
        label='Max Budget'
    )
    start_date_from = django_filters.DateFilter(
        field_name='start_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Start Date From'
    )
    start_date_to = django_filters.DateFilter(
        field_name='start_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Start Date To'
    )
    end_date_from = django_filters.DateFilter(
        field_name='end_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='End Date From'
    )
    end_date_to = django_filters.DateFilter(
        field_name='end_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='End Date To'
    )
    active_campaigns = django_filters.BooleanFilter(
        method='filter_active_campaigns',
        widget=forms.CheckboxInput(),
        label='Currently Active'
    )
    has_members = django_filters.BooleanFilter(
        method='filter_has_members',
        widget=forms.CheckboxInput(),
        label='Has Members'
    )
    
    class Meta:
        model = Campaign
        fields = [
            'campaign_type', 'status', 'budget_min', 'budget_max'
        ]
        assigned_field = 'campaign_manager'
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(target_audience__icontains=value)
        )
    
    def filter_active_campaigns(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(
                start_date__lte=today,
                end_date__gte=today,
                status='ACTIVE'
            )
        return queryset
    
    def filter_has_members(self, queryset, name, value):
        if value:
            return queryset.filter(members__isnull=False).distinct()
        return queryset


class CampaignMemberFilter(CRMBaseFilter):
    """Filter for Campaign Member model"""
    
    campaign = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Campaigns",
        label='Campaign'
    )
    member_type = django_filters.ChoiceFilter(
        choices=CampaignMember.MEMBER_TYPES,
        empty_label="All Types",
        label='Member Type'
    )
    status = django_filters.ChoiceFilter(
        choices=CampaignMember.MEMBER_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    responded = django_filters.BooleanFilter(
        method='filter_responded',
        widget=forms.CheckboxInput(),
        label='Has Responded'
    )
    
    class Meta:
        model = CampaignMember
        fields = ['campaign', 'member_type', 'status']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['campaign'].queryset = Campaign.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(lead__first_name__icontains=value) |
            Q(lead__last_name__icontains=value) |
            Q(lead__email__icontains=value) |
            Q(contact__first_name__icontains=value) |
            Q(contact__last_name__icontains=value) |
            Q(contact__email__icontains=value)
        )
    
    def filter_responded(self, queryset, name, value):
        if value:
            return queryset.filter(response_date__isnull=False)
        return queryset