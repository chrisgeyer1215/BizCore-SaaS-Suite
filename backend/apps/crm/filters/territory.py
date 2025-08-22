# ============================================================================
# backend/apps/crm/filters/territory.py - Territory Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Territory, Team


class TerritoryFilter(CRMBaseFilter, AssigneeFilterMixin):
    """Filter for Territory model"""
    
    territory_type = django_filters.ChoiceFilter(
        choices=Territory.TERRITORY_TYPES,
        empty_label="All Types",
        label='Territory Type'
    )
    parent = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Territories",
        label='Parent Territory'
    )
    region = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Region'}),
        label='Region'
    )
    country = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Country'}),
        label='Country'
    )
    state_province = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'State/Province'}),
        label='State/Province'
    )
    has_teams = django_filters.BooleanFilter(
        method='filter_has_teams',
        widget=forms.CheckboxInput(),
        label='Has Teams'
    )
    has_accounts = django_filters.BooleanFilter(
        method='filter_has_accounts',
        widget=forms.CheckboxInput(),
        label='Has Accounts'
    )
    
    class Meta:
        model = Territory
        fields = [
            'territory_type', 'parent', 'region', 'country', 'state_province'
        ]
        assigned_field = 'manager'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['parent'].queryset = Territory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(region__icontains=value) |
            Q(postal_codes__icontains=value)
        )
    
    def filter_has_teams(self, queryset, name, value):
        if value:
            return queryset.filter(teams__isnull=False).distinct()
        return queryset
    
    def filter_has_accounts(self, queryset, name, value):
        if value:
            return queryset.filter(accounts__isnull=False).distinct()
        return queryset


class TeamFilter(CRMBaseFilter, AssigneeFilterMixin):
    """Filter for Team model"""
    
    territory = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Territories",
        label='Territory'
    )
    has_members = django_filters.BooleanFilter(
        method='filter_has_members',
        widget=forms.CheckboxInput(),
        label='Has Members'
    )
    member_count_min = django_filters.NumberFilter(
        method='filter_member_count_min',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Members'}),
        label='Min Members'
    )
    
    class Meta:
        model = Team
        fields = ['territory', 'is_active']
        assigned_field = 'manager'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['territory'].queryset = Territory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_has_members(self, queryset, name, value):
        if value:
            return queryset.filter(memberships__isnull=False).distinct()
        return queryset
    
    def filter_member_count_min(self, queryset, name, value):
        if value:
            from django.db.models import Count
            return queryset.annotate(
                member_count=Count('memberships', filter=Q(memberships__is_active=True))
            ).filter(member_count__gte=value)
        return queryset