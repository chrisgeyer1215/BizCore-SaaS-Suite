# backend/apps/finance/admin/accounts.py

"""
Chart of Accounts Administration
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from ..models import AccountCategory, Account, TaxCode, TaxGroup, TaxGroupItem


@admin.register(AccountCategory)
class AccountCategoryAdmin(admin.ModelAdmin):
    """Account category admin"""
    
    list_display = ['name', 'account_type', 'sort_order', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['account_type', 'sort_order', 'name']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Account admin"""
    
    list_display = [
        'code', 'name', 'account_type', 'normal_balance',
        'current_balance', 'is_active', 'is_bank_account'
    ]
    list_filter = [
        'account_type', 'normal_balance', 'is_active',
        'is_bank_account', 'is_cash_account', 'category'
    ]
    search_fields = ['code', 'name', 'description']
    ordering = ['code']
    readonly_fields = ['current_balance', 'level']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'code', 'name', 'description', 'account_type',
                'category', 'parent_account', 'level'
            )
        }),
        ('Balance Information', {
            'fields': (
                'normal_balance', 'opening_balance', 'current_balance',
                'opening_balance_date', 'currency'
            )
        }),
        ('Settings', {
            'fields': (
                'is_active', 'is_system_account', 'is_bank_account',
                'is_cash_account', 'allow_manual_entries', 'require_reconciliation'
            )
        }),
        ('Bank Information', {
            'fields': (
                'bank_name', 'bank_account_number', 'bank_routing_number',
                'bank_swift_code'
            ),
            'classes': ('collapse',)
        }),
        ('Tax Settings', {
            'fields': ('default_tax_code', 'is_taxable', 'tax_line'),
            'classes': ('collapse',)
        }),
        ('Inventory Integration', {
            'fields': ('track_inventory', 'inventory_valuation_method'),
            'classes': ('collapse',)
        }),
        ('Budget', {
            'fields': ('budget_amount',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_accounts', 'deactivate_accounts']
    
    def activate_accounts(self, request, queryset):
        """Activate selected accounts"""
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} accounts.")
    activate_accounts.short_description = "Activate selected accounts"
    
    def deactivate_accounts(self, request, queryset):
        """Deactivate selected accounts"""
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} accounts.")
    deactivate_accounts.short_description = "Deactivate selected accounts"


class TaxGroupItemInline(admin.TabularInline):
    """Tax group item inline"""
    model = TaxGroupItem
    extra = 1
    fields = ['tax_code', 'sequence', 'apply_to', 'is_active']


@admin.register(TaxCode)
class TaxCodeAdmin(admin.ModelAdmin):
    """Tax code admin"""
    
    list_display = [
        'code', 'name', 'tax_type', 'rate', 'is_active',
        'is_effective', 'effective_from', 'effective_to'
    ]
    list_filter = [
        'tax_type', 'calculation_method', 'is_active',
        'is_compound', 'is_recoverable', 'country'
    ]
    search_fields = ['code', 'name', 'description']
    ordering = ['code']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'tax_type')
        }),
        ('Calculation', {
            'fields': ('calculation_method', 'rate', 'fixed_amount')
        }),
        ('Location', {
            'fields': ('country', 'state_province', 'city')
        }),
        ('Accounts', {
            'fields': ('tax_collected_account', 'tax_paid_account')
        }),
        ('Settings', {
            'fields': (
                'is_active', 'is_compound', 'is_recoverable', 'apply_to_shipping'
            )
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to')
        }),
        ('Reporting', {
            'fields': ('tax_authority', 'reporting_code')
        })
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Filter queryset based on user permissions or other criteria
        return queryset 
        return queryset