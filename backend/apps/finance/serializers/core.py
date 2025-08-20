# backend/apps/finance/serializers/core.py

"""
Core Finance Configuration Serializers
"""

from rest_framework import serializers
from ..models import FinanceSettings, FiscalYear, FinancialPeriod


class FinanceSettingsSerializer(serializers.ModelSerializer):
    """Finance settings serializer"""
    
    class Meta:
        model = FinanceSettings
        fields = [
            'id', 'company_name', 'company_registration_number',
            'tax_identification_number', 'vat_number', 'company_address',
            'company_logo', 'fiscal_year_start_month', 'current_fiscal_year',
            'accounting_method', 'base_currency', 'enable_multi_currency',
            'currency_precision', 'auto_update_exchange_rates',
            'inventory_valuation_method', 'track_inventory_value',
            'auto_create_cogs_entries', 'enable_landed_costs',
            'tax_calculation_method', 'default_sales_tax_rate',
            'default_purchase_tax_rate', 'enable_tax_tracking',
            'invoice_prefix', 'invoice_starting_number',
            'bill_prefix', 'bill_starting_number',
            'payment_prefix', 'payment_starting_number',
            'enable_multi_location', 'enable_project_accounting',
            'enable_class_tracking', 'enable_departments',
            'require_customer_on_sales', 'require_vendor_on_purchases',
            'auto_create_journal_entries', 'enable_budget_controls',
            'sync_with_inventory', 'sync_with_ecommerce', 'sync_with_crm',
            'enable_bank_feeds', 'require_invoice_approval',
            'require_bill_approval', 'invoice_approval_limit',
            'bill_approval_limit', 'auto_reconcile', 'bank_match_tolerance',
            'enable_cash_flow_forecasting', 'enable_advanced_reporting',
            'default_payment_terms_days', 'enable_late_fees',
            'late_fee_percentage', 'auto_send_reminders',
            'reminder_days_before_due', 'auto_backup_enabled',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_fiscal_year_start_month(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError("Fiscal year start month must be between 1 and 12")
        return value

    def validate_currency_precision(self, value):
        if not 0 <= value <= 8:
            raise serializers.ValidationError("Currency precision must be between 0 and 8")
        return value


class FiscalYearSerializer(serializers.ModelSerializer):
    """Fiscal year serializer"""
    
    is_current = serializers.ReadOnlyField()
    
    class Meta:
        model = FiscalYear
        fields = [
            'id', 'year', 'start_date', 'end_date', 'status',
            'closed_date', 'closed_by', 'total_revenue', 'total_expenses',
            'total_cogs', 'gross_profit', 'net_income', 'total_assets',
            'total_liabilities', 'total_equity', 'is_current',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_revenue', 'total_expenses', 'total_cogs',
            'gross_profit', 'net_income', 'total_assets', 'total_liabilities',
            'total_equity', 'is_current', 'closed_date', 'closed_by',
            'created_at', 'updated_at'
        ]

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("Start date must be before end date")
        return data


class FinancialPeriodSerializer(serializers.ModelSerializer):
    """Financial period serializer"""
    
    fiscal_year_name = serializers.CharField(source='fiscal_year.year', read_only=True)
    variance_revenue = serializers.ReadOnlyField()
    variance_expenses = serializers.ReadOnlyField()
    
    class Meta:
        model = FinancialPeriod
        fields = [
            'id', 'name', 'period_type', 'fiscal_year', 'fiscal_year_name',
            'start_date', 'end_date', 'status', 'closed_by', 'closed_date',
            'budgeted_revenue', 'budgeted_expenses', 'actual_revenue',
            'actual_expenses', 'variance_revenue', 'variance_expenses',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'fiscal_year_name', 'variance_revenue', 'variance_expenses',
            'closed_by', 'closed_date', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("Start date must be before end date")
        return data