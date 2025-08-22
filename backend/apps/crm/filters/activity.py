# ============================================================================
# backend/apps/crm/filters/activity.py - Activity Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Activity, ActivityType


class ActivityTypeFilter(CRMBaseFilter):
    """Filter for Activity Type model"""
    
    category = django_filters.ChoiceFilter(
        choices=ActivityType.ACTIVITY_CATEGORIES,
        empty_label="All Categories",
        label='Category'
    )
    requires_duration = django_filters.BooleanFilter(
        widget=forms.CheckboxInput(),
        label='Requires Duration'
    )
    
    class Meta:
        model = ActivityType
        fields = ['category', 'requires_duration', 'is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class ActivityFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Activity model"""
    
    activity_type = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Types",
        label='Activity Type'
    )
    status = django_filters.ChoiceFilter(
        choices=Activity.ACTIVITY_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    priority = django_filters.ChoiceFilter(
        choices=Activity.PRIORITY_LEVELS,
        empty_label="All Priorities",
        label='Priority'
    )
    start_date_from = django_filters.DateTimeFilter(
        field_name='start_datetime',
        lookup_expr='gte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Start Date From'
    )
    start_date_to = django_filters.DateTimeFilter(
        field_name='start_datetime',
        lookup_expr='lte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Start Date To'
    )
    due_date_from = django_filters.DateTimeFilter(
        field_name='due_datetime',
        lookup_expr='gte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Due Date From'
    )
    due_date_to = django_filters.DateTimeFilter(
        field_name='due_datetime',
        lookup_expr='lte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Due Date To'
    )
    related_to_model = django_filters.ChoiceFilter(
        choices=[
            ('lead', 'Lead'),
            ('account', 'Account'),
            ('opportunity', 'Opportunity'),
            ('campaign', 'Campaign'),
        ],
        empty_label="All Models",
        label='Related To'
    )
    overdue = django_filters.BooleanFilter(
        method='filter_overdue',
        widget=forms.CheckboxInput(),
        label='Overdue'
    )
    due_today = django_filters.BooleanFilter(
        method='filter_due_today',
        widget=forms.CheckboxInput(),
        label='Due Today'
    )
    completed = django_filters.BooleanFilter(
        method='filter_completed',
        widget=forms.CheckboxInput(),
        label='Completed'
    )
    
    class Meta:
        model = Activity
        fields = [
            'activity_type', 'status', 'priority', 'related_to_model'
        ]
        assigned_field = 'assigned_to'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['activity_type'].queryset = ActivityType.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(subject__icontains=value) |
            Q(description__icontains=value) |
            Q(location__icontains=value)
        )
    
    def filter_overdue(self, queryset, name, value):
        if value:
            now = timezone.now()
            return queryset.filter(
                due_datetime__lt=now,
                status__in=['PLANNED', 'IN_PROGRESS']
            )
        return queryset
    
    def filter_due_today(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(due_datetime__date=today)
        return queryset
    
    def filter_completed(self, queryset, name, value):
        if value:
            return queryset.filter(status='COMPLETED')
        return queryset