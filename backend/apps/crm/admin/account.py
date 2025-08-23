# backend/apps/crm/admin/account.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.urls import reverse, path
from django.http import HttpResponseRedirect
from .base import BaseModelAdmin, TenantAwareAdmin
from ..models import Account, Contact, Industry

@admin.register(Account)
class AccountAdmin(TenantAwareAdmin):
    """Admin for Accounts."""
    
    list_display = [
        'name', 'industry', 'status', 'annual_revenue_display',
        'employees', 'owner', 'opportunity_count', 'last_activity'
    ]
    list_filter = [
        'status', 'industry', 'priority', 'account_type',
        'created_at', 'updated_at'
    ]
    search_fields = [
        'name', 'email', 'phone', 'website', 'description'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name', 'account_type', 'industry', 'website',
                'description'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'email', 'phone', 'fax',
                ('billing_street', 'billing_city'),
                ('billing_state', 'billing_postal_code'),
                'billing_country',
                ('shipping_street', 'shipping_city'),
                ('shipping_state', 'shipping_postal_code'),
                'shipping_country'
            )
        }),
        (_('Business Information'), {
            'fields': (
                'annual_revenue', 'employees', 'ownership_type',
                'sic_code', 'ticker_symbol'
            )
        }),
        (_('Relationship Management'), {
            'fields': (
                'status', 'priority', 'owner', 'territory',
                'lead_source', 'partner'
            )
        }),
        (_('Additional Information'), {
            'fields': ('tags', 'custom_fields'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = []  # Will be added below
    
    actions = [
        'mark_as_customer', 'mark_as_prospect', 'assign_territory',
        'export_selected'
    ]
    
    def annual_revenue_display(self, obj):
        """Display formatted annual revenue."""
        if obj.annual_revenue:
            return f"${obj.annual_revenue:,.0f}"
        return "-"
    annual_revenue_display.short_description = _('Annual Revenue')
    annual_revenue_display.admin_order_field = 'annual_revenue'
    
    def opportunity_count(self, obj):
        """Display opportunity count with link."""
        count = obj.opportunities.count()
        if count:
            url = reverse('admin:crm_opportunity_changelist')
            return mark_safe(
                f'<a href="{url}?account__id={obj.id}">{count}</a>'
            )
        return 0
    opportunity_count.short_description = _('Opportunities')
    
    def last_activity(self, obj):
        """Display last activity date."""
        activity = obj.activities.order_by('-created_at').first()
        if activity:
            return activity.created_at.strftime('%Y-%m-%d')
        return _('No activity')
    last_activity.short_description = _('Last Activity')
    
    def mark_as_customer(self, request, queryset):
        """Action to mark accounts as customers."""
        updated = queryset.update(status='customer')
        self.message_user(
            request, 
            f'{updated} accounts marked as customers.'
        )
    mark_as_customer.short_description = _('Mark selected accounts as customers')
    
    def mark_as_prospect(self, request, queryset):
        """Action to mark accounts as prospects."""
        updated = queryset.update(status='prospect')
        self.message_user(
            request,
            f'{updated} accounts marked as prospects.'
        )
    mark_as_prospect.short_description = _('Mark selected accounts as prospects')
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'industry', 'owner__user', 'territory'
        ).prefetch_related('opportunities', 'activities')

@admin.register(Contact)
class ContactAdmin(TenantAwareAdmin):
    """Admin for Contacts."""
    
    list_display = [
        'full_name', 'title', 'account_link', 'email',
        'phone', 'is_primary', 'is_active'
    ]
    list_filter = [
        'is_primary', 'is_active', 'department',
        'created_at'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'phone',
        'title', 'account__name'
    ]
    
    fieldsets = (
        (_('Personal Information'), {
            'fields': (
                ('first_name', 'last_name'), 'title',
                'department', 'reports_to'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'email', 'phone', 'mobile', 'fax',
                ('mailing_street', 'mailing_city'),
                ('mailing_state', 'mailing_postal_code'),
                'mailing_country'
            )
        }),
        (_('Account Relationship'), {
            'fields': (
                'account', 'is_primary', 'contact_role',
                'lead_source'
            )
        }),
        (_('Additional Information'), {
            'fields': (
                'description', 'is_active', 'tags',
                'social_profiles'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        """Display full name."""
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = _('Name')
    full_name.admin_order_field = 'first_name'
    
    def account_link(self, obj):
        """Display account with link."""
        if obj.account:
            url = reverse('admin:crm_account_change', args=[obj.account.pk])
            return mark_safe(f'<a href="{url}">{obj.account.name}</a>')
        return "-"
    account_link.short_description = _('Account')
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'account', 'reports_to'
        )

@admin.register(Industry)
class IndustryAdmin(BaseModelAdmin):
    """Admin for Industries."""
    
    list_display = ['name', 'code', 'parent', 'is_active', 'account_count']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'parent', 'description')
        }),
        (_('Settings'), {
            'fields': ('is_active', 'sort_order')
        }),
    )
    
    def account_count(self, obj):
        """Display account count for industry."""
        return obj.accounts.count()
    account_count.short_description = _('Accounts')