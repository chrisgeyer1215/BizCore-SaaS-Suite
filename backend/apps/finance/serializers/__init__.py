# backend/apps/finance/serializers/__init__.py

"""
Finance Module Serializers
API serializers for all finance-related models
"""

from .core import (
    FinanceSettingsSerializer,
    FiscalYearSerializer,
    FinancialPeriodSerializer,
)

from .currency import (
    CurrencySerializer,
    ExchangeRateSerializer,
)

from .accounts import (
    AccountCategorySerializer,
    AccountSerializer,
    AccountTreeSerializer,
)

from .tax import (
    TaxCodeSerializer,
    TaxGroupSerializer,
    TaxGroupItemSerializer,
)

from .journal import (
    JournalEntrySerializer,
    JournalEntryLineSerializer,
    JournalEntryCreateSerializer,
)

from .bank import (
    BankAccountSerializer,
    BankStatementSerializer,
    BankTransactionSerializer,
    BankReconciliationSerializer,
)

from .vendors import (
    VendorSerializer,
    VendorContactSerializer,
    BillSerializer,
    BillItemSerializer,
)

from .invoicing import (
    InvoiceSerializer,
    InvoiceItemSerializer,
    InvoiceCreateSerializer,
)

from .payments import (
    PaymentSerializer,
    PaymentApplicationSerializer,
)

from .reporting import (
    TrialBalanceSerializer,
    BalanceSheetSerializer,
    IncomeStatementSerializer,
    CashFlowSerializer,
)

__all__ = [
    # Core
    'FinanceSettingsSerializer',
    'FiscalYearSerializer', 
    'FinancialPeriodSerializer',
    
    # Currency
    'CurrencySerializer',
    'ExchangeRateSerializer',
    
    # Accounts
    'AccountCategorySerializer',
    'AccountSerializer',
    'AccountTreeSerializer',
    
    # Tax
    'TaxCodeSerializer',
    'TaxGroupSerializer',
    'TaxGroupItemSerializer',
    
    # Journal
    'JournalEntrySerializer',
    'JournalEntryLineSerializer',
    'JournalEntryCreateSerializer',
    
    # Bank
    'BankAccountSerializer',
    'BankStatementSerializer',
    'BankTransactionSerializer',
    'BankReconciliationSerializer',
    
    # Vendors
    'VendorSerializer',
    'VendorContactSerializer',
    'BillSerializer',
    'BillItemSerializer',
    
    # Invoicing
    'InvoiceSerializer',
    'InvoiceItemSerializer',
    'InvoiceCreateSerializer',
    
    # Payments
    'PaymentSerializer',
    'PaymentApplicationSerializer',
    
    # Reporting
    'TrialBalanceSerializer',
    'BalanceSheetSerializer',
    'IncomeStatementSerializer',
    'CashFlowSerializer',
]


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


# backend/apps/finance/serializers/currency.py

"""
Multi-Currency Support Serializers
"""

from rest_framework import serializers
from ..models import Currency, ExchangeRate


class CurrencySerializer(serializers.ModelSerializer):
    """Currency serializer"""
    
    class Meta:
        model = Currency
        fields = [
            'id', 'code', 'name', 'symbol', 'decimal_places',
            'is_active', 'is_base_currency', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_code(self, value):
        if len(value) != 3:
            raise serializers.ValidationError("Currency code must be exactly 3 characters")
        return value.upper()

    def validate_decimal_places(self, value):
        if not 0 <= value <= 8:
            raise serializers.ValidationError("Decimal places must be between 0 and 8")
        return value


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Exchange rate serializer"""
    
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    from_currency_name = serializers.CharField(source='from_currency.name', read_only=True)
    to_currency_name = serializers.CharField(source='to_currency.name', read_only=True)
    
    class Meta:
        model = ExchangeRate
        fields = [
            'id', 'from_currency', 'from_currency_code', 'from_currency_name',
            'to_currency', 'to_currency_code', 'to_currency_name',
            'rate', 'effective_date', 'source', 'created_date'
        ]
        read_only_fields = [
            'id', 'from_currency_code', 'from_currency_name',
            'to_currency_code', 'to_currency_name', 'created_date'
        ]

    def validate_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError("Exchange rate must be positive")
        return value

    def validate(self, data):
        if data['from_currency'] == data['to_currency']:
            raise serializers.ValidationError("From and to currencies cannot be the same")
        return data


# backend/apps/finance/serializers/accounts.py

"""
Chart of Accounts Serializers
"""

from rest_framework import serializers
from ..models import AccountCategory, Account


class AccountCategorySerializer(serializers.ModelSerializer):
    """Account category serializer"""
    
    class Meta:
        model = AccountCategory
        fields = [
            'id', 'name', 'description', 'account_type',
            'sort_order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AccountSerializer(serializers.ModelSerializer):
    """Account serializer"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    parent_account_name = serializers.CharField(source='parent_account.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    balance_sheet_section = serializers.ReadOnlyField()
    is_balance_sheet_account = serializers.ReadOnlyField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'description', 'account_type',
            'category', 'category_name', 'parent_account', 'parent_account_name',
            'level', 'normal_balance', 'opening_balance', 'current_balance',
            'opening_balance_date', 'currency', 'currency_code',
            'is_active', 'is_system_account', 'is_bank_account',
            'is_cash_account', 'allow_manual_entries', 'require_reconciliation',
            'bank_name', 'bank_account_number', 'bank_routing_number',
            'bank_swift_code', 'default_tax_code', 'is_taxable',
            'tax_line', 'track_inventory', 'inventory_valuation_method',
            'budget_amount', 'balance_sheet_section', 'is_balance_sheet_account',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'category_name', 'parent_account_name', 'currency_code',
            'level', 'current_balance', 'balance_sheet_section',
            'is_balance_sheet_account', 'created_at', 'updated_at'
        ]

    def validate_code(self, value):
        # Check for unique code within tenant
        tenant = self.context['request'].tenant
        if Account.objects.filter(tenant=tenant, code=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Account code must be unique")
        return value

    def validate(self, data):
        # Validate parent account relationship
        if 'parent_account' in data and data['parent_account']:
            if data['parent_account'].account_type != data.get('account_type', self.instance.account_type if self.instance else None):
                raise serializers.ValidationError("Parent account must be of the same type")
        return data


class AccountTreeSerializer(serializers.ModelSerializer):
    """Account tree serializer with nested sub-accounts"""
    
    sub_accounts = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'level',
            'current_balance', 'balance', 'is_active', 'sub_accounts'
        ]

    def get_sub_accounts(self, obj):
        if obj.sub_accounts.exists():
            return AccountTreeSerializer(obj.sub_accounts.filter(is_active=True), many=True, context=self.context).data
        return []

    def get_balance(self, obj):
        # Get balance with proper formatting
        return float(obj.current_balance)


# backend/apps/finance/serializers/tax.py

"""
Tax Management Serializers
"""

from rest_framework import serializers
from ..models import TaxCode, TaxGroup, TaxGroupItem


class TaxCodeSerializer(serializers.ModelSerializer):
    """Tax code serializer"""
    
    tax_collected_account_name = serializers.CharField(source='tax_collected_account.name', read_only=True)
    tax_paid_account_name = serializers.CharField(source='tax_paid_account.name', read_only=True)
    is_effective = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxCode
        fields = [
            'id', 'code', 'name', 'description', 'tax_type',
            'calculation_method', 'rate', 'fixed_amount',
            'country', 'state_province', 'city',
            'tax_collected_account', 'tax_collected_account_name',
            'tax_paid_account', 'tax_paid_account_name',
            'is_active', 'is_compound', 'is_recoverable',
            'apply_to_shipping', 'effective_from', 'effective_to',
            'tax_authority', 'reporting_code', 'is_effective',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tax_collected_account_name', 'tax_paid_account_name',
            'is_effective', 'created_at', 'updated_at'
        ]

    def get_is_effective(self, obj):
        return obj.is_effective()

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        return value

    def validate(self, data):
        if data['calculation_method'] == 'FIXED' and not data.get('fixed_amount'):
            raise serializers.ValidationError("Fixed amount is required for fixed calculation method")
        if data['calculation_method'] == 'PERCENTAGE' and not data.get('rate'):
            raise serializers.ValidationError("Rate is required for percentage calculation method")
        return data


class TaxGroupItemSerializer(serializers.ModelSerializer):
    """Tax group item serializer"""
    
    tax_code_name = serializers.CharField(source='tax_code.name', read_only=True)
    tax_code_rate = serializers.DecimalField(source='tax_code.rate', max_digits=8, decimal_places=4, read_only=True)
    
    class Meta:
        model = TaxGroupItem
        fields = [
            'id', 'tax_code', 'tax_code_name', 'tax_code_rate',
            'sequence', 'apply_to', 'is_active'
        ]
        read_only_fields = ['id', 'tax_code_name', 'tax_code_rate']


class TaxGroupSerializer(serializers.ModelSerializer):
    """Tax group serializer"""
    
    tax_group_items = TaxGroupItemSerializer(many=True, read_only=True)
    total_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxGroup
        fields = [
            'id', 'name', 'description', 'is_active',
            'tax_group_items', 'total_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_rate', 'created_at', 'updated_at']

    def get_total_rate(self, obj):
        total = 0
        for item in obj.tax_group_items.filter(is_active=True):
            total += item.tax_code.rate
        return total


# backend/apps/finance/serializers/journal.py

"""
Journal Entry Serializers
"""

from rest_framework import serializers
from decimal import Decimal
from ..models import JournalEntry, JournalEntryLine


class JournalEntryLineSerializer(serializers.ModelSerializer):
    """Journal entry line serializer"""
    
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    amount = serializers.ReadOnlyField()
    is_debit = serializers.ReadOnlyField()
    
    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'line_number', 'account', 'account_name', 'account_code',
            'description', 'debit_amount', 'credit_amount',
            'base_currency_debit_amount', 'base_currency_credit_amount',
            'customer', 'customer_name', 'vendor', 'vendor_name',
            'product', 'product_name', 'project', 'department', 'location',
            'tax_code', 'tax_amount', 'quantity', 'unit_cost',
            'amount', 'is_debit'
        ]
        read_only_fields = ['id', 'account_name', 'account_code', 'customer_name', 'vendor_name', 'product_name', 'amount', 'is_debit']

    def validate(self, data):
        if data.get('debit_amount') and data.get('credit_amount'):
            raise serializers.ValidationError("Line cannot have both debit and credit amounts")
        if not data.get('debit_amount') and not data.get('credit_amount'):
            raise serializers.ValidationError("Line must have either debit or credit amount")
        return data


class JournalEntrySerializer(serializers.ModelSerializer):
    """Journal entry serializer"""
    
    journal_lines = JournalEntryLineSerializer(many=True, read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    posted_by_name = serializers.CharField(source='posted_by.get_full_name', read_only=True)
    is_balanced = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'reference_number', 'entry_date',
            'status', 'entry_type', 'description', 'notes',
            'source_document_type', 'source_document_id', 'source_document_number',
            'total_debit', 'total_credit', 'currency', 'currency_code',
            'exchange_rate', 'base_currency_total_debit', 'base_currency_total_credit',
            'created_by', 'created_by_name', 'posted_by', 'posted_by_name',
            'posted_date', 'approved_by', 'approved_date', 'reversed_entry',
            'reversal_reason', 'financial_period', 'attachments',
            'journal_lines', 'is_balanced', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'entry_number', 'currency_code', 'created_by_name',
            'posted_by_name', 'total_debit', 'total_credit',
            'base_currency_total_debit', 'base_currency_total_credit',
            'posted_date', 'approved_date', 'is_balanced', 'created_at', 'updated_at'
        ]

    def get_is_balanced(self, obj):
        return abs(obj.total_debit - obj.total_credit) < Decimal('0.01')


class JournalEntryCreateSerializer(serializers.ModelSerializer):
    """Journal entry creation serializer with lines"""
    
    lines = JournalEntryLineSerializer(many=True, write_only=True)
    
    class Meta:
        model = JournalEntry
        fields = [
            'entry_date', 'entry_type', 'description', 'notes',
            'reference_number', 'currency', 'exchange_rate', 'lines'
        ]

    def validate_lines(self, lines):
        if len(lines) < 2:
            raise serializers.ValidationError("Journal entry must have at least 2 lines")
        
        total_debit = sum(line.get('debit_amount', 0) for line in lines)
        total_credit = sum(line.get('credit_amount', 0) for line in lines)
        
        if abs(total_debit - total_credit) > Decimal('0.01'):
            raise serializers.ValidationError("Journal entry must be balanced (debits = credits)")
        
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        journal_entry = JournalEntry.objects.create(**validated_data)
        
        for i, line_data in enumerate(lines_data, 1):
            line_data['line_number'] = i
            JournalEntryLine.objects.create(journal_entry=journal_entry, **line_data)
        
        journal_entry.calculate_totals()
        return journal_entry