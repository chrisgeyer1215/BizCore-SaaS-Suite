# ============================================================================
# backend/apps/crm/filters/document.py - Document Filters
# ============================================================================

import django_filters
from django import forms
from django.db.models import Q

from .base import CRMBaseFilter, DateRangeFilterMixin
from ..models import Document, DocumentCategory


class DocumentCategoryFilter(CRMBaseFilter):
    """Filter for Document Category model"""
    
    parent = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Parent Category'
    )
    
    class Meta:
        model = DocumentCategory
        fields = ['parent', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['parent'].queryset = DocumentCategory.objects.filter(
                tenant=self.request.tenant,
                parent__isnull=True,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class DocumentFilter(CRMBaseFilter, DateRangeFilterMixin):
    """Filter for Document model"""
    
    category = django_filters.ModelChoiceFilter(
        queryset=None,  # Set in __init__
        empty_label="All Categories",
        label='Category'
    )
    file_type = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'placeholder': 'e.g., pdf, doc, jpg'}),
        label='File Type'
    )
    size_min = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='gte',
        widget=forms.NumberInput(attrs={'placeholder': 'Min Size (bytes)'}),
        label='Min File Size'
    )
    size_max = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='lte',
        widget=forms.NumberInput(attrs={'placeholder': 'Max Size (bytes)'}),
        label='Max File Size'
    )
    is_public = django_filters.BooleanFilter(
        widget=forms.Select(choices=[('', 'All'), (True, 'Public'), (False, 'Private')]),
        label='Visibility'
    )
    related_to_model = django_filters.ChoiceFilter(
        choices=[
            ('lead', 'Lead'),
            ('account', 'Account'),
            ('opportunity', 'Opportunity'),
            ('activity', 'Activity'),
            ('campaign', 'Campaign'),
            ('ticket', 'Ticket'),
        ],
        empty_label="All Models",
        label='Related To'
    )
    has_versions = django_filters.BooleanFilter(
        method='filter_has_versions',
        widget=forms.CheckboxInput(),
        label='Has Multiple Versions'
    )
    
    class Meta:
        model = Document
        fields = [
            'category', 'file_type', 'is_public', 'related_to_model'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and self.request.tenant:
            self.filters['category'].queryset = DocumentCategory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            )
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(original_filename__icontains=value) |
            Q(tags__icontains=value)
        )
    
    def filter_has_versions(self, queryset, name, value):
        if value:
            return queryset.filter(version__gt=1)
        return queryset