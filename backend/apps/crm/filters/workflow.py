# ============================================================================
# backend/apps/crm/filters/workflow.py - Workflow Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin
from ..models import WorkflowRule, WorkflowExecution, Integration, WebhookConfiguration, CustomField


class WorkflowRuleFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Workflow Rule model"""
    
    trigger_type = django_filters.ChoiceFilter(
        choices=WorkflowRule.TRIGGER_TYPES,
        empty_label="All Trigger Types",
        label='Trigger Type'
    )
    target_model = django_filters.ChoiceFilter(
        choices=WorkflowRule.TARGET_MODELS,
        empty_label="All Models",
        label='Target Model'
    )
    created_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='Created By'
    )
    has_executions = django_filters.BooleanFilter(
        method='filter_has_executions',
        widget=forms.CheckboxInput(),
        label='Has Executions'
    )
    
    class Meta:
        model = WorkflowRule
        fields = ['trigger_type', 'target_model', 'created_by', 'is_active']
    
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
    
    def filter_has_executions(self, queryset, name, value):
        if value:
            return queryset.filter(executions__isnull=False).distinct()
        return queryset


class WorkflowExecutionFilter(CRMBaseFilter):
    """Filter for Workflow Execution model"""
    
    rule = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Rules",
        label='Workflow Rule'
    )
    status = django_filters.ChoiceFilter(
        choices=WorkflowExecution.EXECUTION_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    triggered_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Users",
        label='Triggered By'
    )
    executed_date_from = django_filters.DateTimeFilter(
        field_name='executed_at',
        lookup_expr='gte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Executed From'
    )
    executed_date_to = django_filters.DateTimeFilter(
        field_name='executed_at',
        lookup_expr='lte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Executed To'
    )
    execution_time_min = django_filters.NumberFilter(
        field_name='execution_time_ms',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min ms'}),
        label='Min Execution Time (ms)'
    )
    
    class Meta:
        model = WorkflowExecution
        fields = ['rule', 'status', 'triggered_by']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            self.filters['rule'].queryset = WorkflowRule.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
            
            self.filters['triggered_by'].queryset = User.objects.filter(
                tenant_memberships__tenant=self.request.tenant,
                tenant_memberships__is_active=True
            ).distinct()
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(rule__name__icontains=value) |
            Q(error_message__icontains=value)
        )


class IntegrationFilter(CRMBaseFilter):
    """Filter for Integration model"""
    
    service_type = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Service Type'}),
        label='Service Type'
    )
    is_connected = django_filters.BooleanFilter(
        method='filter_is_connected',
        widget=forms.CheckboxInput(),
        label='Connected'
    )
    last_sync_from = django_filters.DateTimeFilter(
        field_name='last_sync_at',
        lookup_expr='gte',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Last Sync From'
    )
    
    class Meta:
        model = Integration
        fields = ['service_type', 'is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(service_type__icontains=value)
        )
    
    def filter_is_connected(self, queryset, name, value):
        # This would depend on your integration logic
        # For now, consider active integrations as connected
        if value is not None:
            return queryset.filter(is_active=value)
        return queryset


class WebhookConfigurationFilter(CRMBaseFilter):
    """Filter for Webhook Configuration model"""
    
    integration = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Integrations",
        label='Integration'
    )
    method = django_filters.ChoiceFilter(
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
        ],
        empty_label="All Methods",
        label='HTTP Method'
    )
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'Event Type'}),
        label='Event Type'
    )
    
    class Meta:
        model = WebhookConfiguration
        fields = ['integration', 'method', 'event_type', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['integration'].queryset = Integration.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(url__icontains=value) |
            Q(event_type__icontains=value)
        )


class CustomFieldFilter(CRMBaseFilter):
    """Filter for Custom Field model"""
    
    model_name = django_filters.ChoiceFilter(
        choices=CustomField.MODEL_CHOICES,
        empty_label="All Models",
        label='Model'
    )
    field_type = django_filters.ChoiceFilter(
        choices=CustomField.FIELD_TYPE_CHOICES,
        empty_label="All Types",
        label='Field Type'
    )
    is_required = django_filters.BooleanFilter(
        widget=forms.CheckboxInput(),
        label='Required'
    )
    
    class Meta:
        model = CustomField
        fields = ['model_name', 'field_type', 'is_required', 'is_active']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(field_name__icontains=value) |
            Q(label__icontains=value) |
            Q(help_text__icontains=value)
        )