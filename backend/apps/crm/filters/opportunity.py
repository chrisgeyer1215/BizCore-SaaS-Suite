# ============================================================================
# backend/apps/crm/filters/opportunity.py - Opportunity Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Opportunity, Pipeline, PipelineStage


class PipelineFilter(CRMBaseFilter):
    """Filter for Pipeline model"""
    
    class Meta:
        model = Pipeline
        fields = ['is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class PipelineStageFilter(CRMBaseFilter):
    """Filter for Pipeline Stage model"""
    
    pipeline = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Pipelines",
        label='Pipeline'
    )
    stage_type = django_filters.ChoiceFilter(
        choices=PipelineStage.STAGE_TYPES,
        empty_label="All Types",
        label='Stage Type'
    )
    probability_min = django_filters.NumberFilter(
        field_name='probability',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min %'}),
        label='Min Probability %'
    )
    probability_max = django_filters.NumberFilter(
        field_name='probability',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max %'}),
        label='Max Probability %'
    )
    
    class Meta:
        model = PipelineStage
        fields = ['pipeline', 'stage_type', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['pipeline'].queryset = Pipeline.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class OpportunityFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Opportunity model"""
    
    account = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Accounts",
        label='Account'
    )
    pipeline = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Pipelines",
        label='Pipeline'
    )
    stage = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Stages",
        label='Stage'
    )
    amount_min = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Amount'}),
        label='Min Amount'
    )
    amount_max = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Amount'}),
        label='Max Amount'
    )
    probability_min = django_filters.NumberFilter(
        field_name='probability',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min %'}),
        label='Min Probability %'
    )
    probability_max = django_filters.NumberFilter(
        field_name='probability',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max %'}),
        label='Max Probability %'
    )
    close_date_from = django_filters.DateFilter(
        field_name='close_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Close Date From'
    )
    close_date_to = django_filters.DateFilter(
        field_name='close_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Close Date To'
    )
    closed_date_from = django_filters.DateFilter(
        field_name='closed_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Closed Date From'
    )
    closed_date_to = django_filters.DateFilter(
        field_name='closed_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Closed Date To'
    )
    is_closed = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Closed'), (False, 'Open')]),
        label='Status'
    )
    is_won = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Won'), (False, 'Lost')]),
        label='Win/Loss Status'
    )
    closing_soon = django_filters.BooleanFilter(
        method='filter_closing_soon',
        widget=forms.CheckboxInput(),
        label='Closing Soon (30 days)'
    )
    overdue = django_filters.BooleanFilter(
        method='filter_overdue',
        widget=forms.CheckboxInput(),
        label='Overdue'
    )
    has_products = django_filters.BooleanFilter(
        method='filter_has_products',
        widget=forms.CheckboxInput(),
        label='Has Products'
    )
    
    class Meta:
        model = Opportunity
        fields = [
            'account', 'pipeline', 'stage', 'is_closed', 'is_won',
            'amount_min', 'amount_max', 'probability_min', 'probability_max'
        ]
        assigned_field = 'owner'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from ..models import Account
            self.filters['account'].queryset = Account.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
            
            self.filters['pipeline'].queryset = Pipeline.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
            
            self.filters['stage'].queryset = PipelineStage.objects.filter(
                pipeline__tenant=self.request.tenant,
                is_active=True
            ).select_related('pipeline')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(account__name__icontains=value)
        )
    
    def filter_closing_soon(self, queryset, name, value):
        if value:
            thirty_days_from_now = timezone.now().date() + timedelta(days=30)
            return queryset.filter(
                close_date__lte=thirty_days_from_now,
                is_closed=False
            )
        return queryset
    
    def filter_overdue(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(
                close_date__lt=today,
                is_closed=False
            )
        return queryset
    
    def filter_has_products(self, queryset, name, value):
        if value:
            return queryset.filter(products__isnull=False).distinct()
        return queryset