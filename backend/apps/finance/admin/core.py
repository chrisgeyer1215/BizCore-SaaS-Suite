# backend/apps/finance/admin/core.py

"""
Core Finance Administration
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from ..models import (
    FinanceSettings, FiscalYear, FinancialPeriod,
    Currency, ExchangeRate
)


@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    """Finance settings admin"""
    
    list_display = [
        'company_name', 'accounting_method', 'base_currency',
        'fiscal_year_start_month', 'current_fiscal_year', 'created_at'
    ]
    
    fieldsets = (
        ('Company Information', {
            'fields': (
                'company_name', 'company_registration_number',
                'tax_identification_number', 'vat_number',
                'company_address', 'company_logo'
            )
        }),
        ('Fiscal Year Settings', {
            'fields': (
                'fiscal_year_start_month', 'current_fiscal_year', 'accounting_method'
            )
        }),
        ('Currency Settings', {
            'fields': (
                'base_currency', 'enable_multi_currency', 'currency_precision',
                'auto_update_exchange_rates'
            )
        }),
        ('Inventory Integration', {
            'fields': (
                'inventory_valuation_method', 'track_inventory_value',
                'auto_create_cogs_entries', 'enable_landed_costs'
            )
        }),
        ('Tax Settings', {
            'fields': (
                'tax_calculation_method', 'default_sales_tax_rate',
                'default_purchase_tax_rate', 'enable_tax_tracking'
            )
        }),
        ('Document Numbering', {
            'fields': (
                ('invoice_prefix', 'invoice_starting_number'),
                ('bill_prefix', 'bill_starting_number'),
                ('payment_prefix', 'payment_starting_number')
            )
        }),
        ('Features & Controls', {
            'fields': (
                'enable_multi_location', 'enable_project_accounting',
                'enable_class_tracking', 'enable_departments',
                'require_customer_on_sales', 'require_vendor_on_purchases',
                'auto_create_journal_entries', 'enable_budget_controls'
            )
        }),
        ('Integration Settings', {
            'fields': (
                'sync_with_inventory', 'sync_with_ecommerce', 'sync_with_crm',
                'enable_bank_feeds'
            )
        }),
        ('Approval Workflows', {
            'fields': (
                'require_invoice_approval', 'require_bill_approval',
                'invoice_approval_limit', 'bill_approval_limit'
            )
        }),
        ('Bank Reconciliation', {
            'fields': (
                'auto_reconcile', 'bank_match_tolerance'
            )
        }),
        ('Reporting & Analytics', {
            'fields': (
                'enable_cash_flow_forecasting', 'enable_advanced_reporting',
                'default_payment_terms_days', 'enable_late_fees',
                'late_fee_percentage'
            )
        }),
        ('Automation', {
            'fields': (
                'auto_send_reminders', 'reminder_days_before_due',
                'auto_backup_enabled'
            )
        })
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one settings record per tenant
        return not FinanceSettings.objects.filter(tenant=request.tenant).exists()


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    """Fiscal year admin"""
    
    list_display = [
        'year', 'start_date', 'end_date', 'status',
        'is_current', 'total_revenue', 'net_income', 'closed_date'
    ]
    list_filter = ['status', 'year']
    search_fields = ['year']
    readonly_fields = [
        'total_revenue', 'total_expenses', 'total_cogs',
        'gross_profit', 'net_income', 'total_assets',
        'total_liabilities', 'total_equity', 'is_current',
        'closed_date', 'closed_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('year', 'start_date', 'end_date', 'status')
        }),
        ('Financial Summary', {
            'fields': (
                'total_revenue', 'total_expenses', 'total_cogs',
                'gross_profit', 'net_income'
            ),
            'classes': ('collapse',)
        }),
        ('Balance Sheet Summary', {
            'fields': ('total_assets', 'total_liabilities', 'total_equity'),
            'classes': ('collapse',)
        }),
        ('Closing Information', {
            'fields': ('closed_date', 'closed_by'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['close_fiscal_year']
    
    def close_fiscal_year(self, request, queryset):
        """Close selected fiscal years"""
        for fiscal_year in queryset.filter(status='OPEN'):
            fiscal_year.close_fiscal_year(request.user)
        self.message_user(request, f"Closed {queryset.count()} fiscal years.")
    close_fiscal_year.short_description = "Close selected fiscal years"


@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    """Financial period admin"""
    
    list_display = [
        'name', 'period_type', 'fiscal_year', 'start_date',
        'end_date', 'status', 'variance_revenue', 'variance_expenses'
    ]
    list_filter = ['period_type', 'status', 'fiscal_year']
    search_fields = ['name']
    readonly_fields = ['variance_revenue', 'variance_expenses']


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Currency admin"""
    
    list_display = ['code', 'name', 'symbol', 'decimal_places', 'is_active', 'is_base_currency']
    list_filter = ['is_active', 'is_base_currency', 'decimal_places']
    search_fields = ['code', 'name']
    ordering = ['code']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    """Exchange rate admin"""
    
    list_display = [
        'from_currency', 'to_currency', 'rate',
        'effective_date', 'source', 'created_date'
    ]
    list_filter = ['effective_date', 'source', 'from_currency', 'to_currency']
    search_fields = ['from_currency__code', 'to_currency__code']
    ordering = ['-effective_date', 'from_currency', 'to_currency']
    readonly_fields = ['created_date']