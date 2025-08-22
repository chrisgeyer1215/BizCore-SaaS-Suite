# ============================================================================
# backend/apps/crm/filters/ticket.py - Ticket Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .base import CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin
from ..models import Ticket, TicketCategory, SLA


class TicketCategoryFilter(CRMBaseFilter):
    """Filter for Ticket Category model"""
    
    parent = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Parent Category'
    )
    has_sla = django_filters.BooleanFilter(
        method='filter_has_sla',
        widget=forms.CheckboxInput(),
        label='Has SLA'
    )
    
    class Meta:
        model = TicketCategory
        fields = ['parent', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['parent'].queryset = TicketCategory.objects.filter(
                tenant=self.request.tenant,
                parent__isnull=True,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_has_sla(self, queryset, name, value):
        if value:
            return queryset.filter(sla__isnull=False)
        return queryset


class TicketFilter(CRMBaseFilter, DateRangeFilterMixin, AssigneeFilterMixin):
    """Filter for Ticket model"""
    
    category = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Category'
    )
    status = django_filters.ChoiceFilter(
        choices=Ticket.TICKET_STATUSES,
        empty_label="All Statuses",
        label='Status'
    )
    priority = django_filters.ChoiceFilter(
        choices=Ticket.PRIORITY_LEVELS,
        empty_label="All Priorities",
        label='Priority'
    )
    source = django_filters.ChoiceFilter(
        choices=Ticket.TICKET_SOURCES,
        empty_label="All Sources",
        label='Source'
    )
    account = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Accounts",
        label='Account'
    )
    contact = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Contacts",
        label='Contact'
    )
    sla_breached = django_filters.BooleanFilter(
        method='filter_sla_breached',
        widget=forms.CheckboxInput(),
        label='SLA Breached'
    )
    overdue = django_filters.BooleanFilter(
        method='filter_overdue',
        widget=forms.CheckboxInput(),
        label='Overdue'
    )
    escalated = django_filters.BooleanFilter(
        widget=forms.CheckboxInput(),
        label='Escalated'
    )
    resolved_today = django_filters.BooleanFilter(
        method='filter_resolved_today',
        widget=forms.CheckboxInput(),
        label='Resolved Today'
    )
    
    class Meta:
        model = Ticket
        fields = [
            'category', 'status', 'priority', 'source',
            'account', 'contact', 'escalated'
        ]
        assigned_field = 'assigned_to'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            from ..models import Account, Contact
            
            self.filters['category'].queryset = TicketCategory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
            
            self.filters['account'].queryset = Account.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).order_by('name')
            
            self.filters['contact'].queryset = Contact.objects.filter(
                account__tenant=self.request.tenant,
                is_active=True
            ).select_related('account')
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(subject__icontains=value) |
            Q(description__icontains=value) |
            Q(ticket_number__icontains=value) |
            Q(account__name__icontains=value) |
            Q(contact__first_name__icontains=value) |
            Q(contact__last_name__icontains=value)
        )
    
    def filter_sla_breached(self, queryset, name, value):
        if value:
            return queryset.filter(sla_breached=True)
        return queryset
    
    def filter_overdue(self, queryset, name, value):
        if value:
            now = timezone.now()
            return queryset.filter(
                due_date__lt=now,
                status__in=['OPEN', 'IN_PROGRESS']
            )
        return queryset
    
    def filter_resolved_today(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(
                resolved_date__date=today,
                status='RESOLVED'
            )
        return queryset