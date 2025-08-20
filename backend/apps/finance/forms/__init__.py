# backend/apps/finance/forms/__init__.py

"""
Finance Module Forms
Django forms for admin interface and frontend
"""

from .settings import FinanceSettingsForm
from .accounts import AccountCategoryForm, AccountForm
from .journal_entries import JournalEntryForm, JournalEntryLineFormSet
from .invoices import InvoiceForm, InvoiceItemFormSet
from .bills import BillForm, BillItemFormSet
from .payments import PaymentForm, PaymentApplicationFormSet
from .vendors import VendorForm, VendorContactFormSet
from .bank_reconciliation import BankAccountForm, BankReconciliationForm

__all__ = [
    'FinanceSettingsForm',
    'AccountCategoryForm',
    'AccountForm',
    'JournalEntryForm',
    'JournalEntryLineFormSet',
    'InvoiceForm',
    'InvoiceItemFormSet',
    'BillForm',
    'BillItemFormSet',
    'PaymentForm',
    'PaymentApplicationFormSet',
    'VendorForm',
    'VendorContactFormSet',
    'BankAccountForm',
    'BankReconciliationForm',
]


# backend/apps/finance/forms/settings.py

"""
Finance Settings Forms
"""

from django import forms
from django.core.exceptions import ValidationError
from ..models import FinanceSettings, FiscalYear, Currency


class FinanceSettingsForm(forms.ModelForm):
    """Finance settings configuration form"""
    
    class Meta:
        model = FinanceSettings
        fields = [
            'company_name', 'company_registration_number', 'tax_identification_number',
            'vat_number', 'company_logo', 'fiscal_year_start_month', 
            'current_fiscal_year', 'accounting_method', 'base_currency',
            'enable_multi_currency', 'currency_precision', 'auto_update_exchange_rates',
            'inventory_valuation_method', 'track_inventory_value', 'auto_create_cogs_entries',
            'enable_landed_costs', 'tax_calculation_method', 'default_sales_tax_rate',
            'default_purchase_tax_rate', 'enable_tax_tracking', 'invoice_prefix',
            'invoice_starting_number', 'bill_prefix', 'bill_starting_number',
            'payment_prefix', 'payment_starting_number', 'enable_multi_location',
            'enable_project_accounting', 'enable_class_tracking', 'enable_departments',
            'require_customer_on_sales', 'require_vendor_on_purchases',
            'auto_create_journal_entries', 'enable_budget_controls',
            'sync_with_inventory', 'sync_with_ecommerce', 'sync_with_crm',
            'enable_bank_feeds', 'require_invoice_approval', 'require_bill_approval',
            'invoice_approval_limit', 'bill_approval_limit', 'auto_reconcile',
            'bank_match_tolerance', 'enable_cash_flow_forecasting',
            'enable_advanced_reporting', 'default_payment_terms_days',
            'enable_late_fees', 'late_fee_percentage', 'auto_send_reminders',
            'reminder_days_before_due', 'auto_backup_enabled'
        ]
        
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_identification_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vat_number': forms.TextInput(attrs={'class': 'form-control'}),
            'fiscal_year_start_month': forms.Select(attrs={'class': 'form-control'}),
            'current_fiscal_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'accounting_method': forms.Select(attrs={'class': 'form-control'}),
            'base_currency': forms.Select(attrs={'class': 'form-control'}),
            'currency_precision': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 8}),
            'inventory_valuation_method': forms.Select(attrs={'class': 'form-control'}),
            'tax_calculation_method': forms.Select(attrs={'class': 'form-control'}),
            'default_sales_tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'default_purchase_tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'invoice_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_starting_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'bill_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'bill_starting_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_starting_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'invoice_approval_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'bill_approval_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'bank_match_tolerance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_payment_terms_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'late_fee_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reminder_days_before_due': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['customer'].queryset = Customer.objects.filter(tenant=self.tenant)
            self.fields['vendor'].queryset = Vendor.objects.filter(tenant=self.tenant)
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )
            self.fields['bank_account'].queryset = Account.objects.filter(
                tenant=self.tenant, is_bank_account=True, is_active=True
            )

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get('payment_type')
        customer = cleaned_data.get('customer')
        vendor = cleaned_data.get('vendor')
        
        if payment_type == 'RECEIVED' and not customer:
            raise ValidationError("Customer is required for received payments")
        
        if payment_type == 'MADE' and not vendor:
            raise ValidationError("Vendor is required for made payments")
        
        if customer and vendor:
            raise ValidationError("Payment cannot have both customer and vendor")
        
        return cleaned_data


class PaymentApplicationForm(forms.ModelForm):
    """Payment application form"""
    
    class Meta:
        model = PaymentApplication
        fields = [
            'invoice', 'bill', 'amount_applied', 'discount_amount', 'notes'
        ]
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'bill': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'amount_applied': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'notes': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        bill = cleaned_data.get('bill')
        
        if not invoice and not bill:
            raise ValidationError("Either invoice or bill must be selected")
        
        if invoice and bill:
            raise ValidationError("Cannot apply to both invoice and bill")
        
        return cleaned_data


# Create formset for payment applications
PaymentApplicationFormSet = inlineformset_factory(
    Payment,
    PaymentApplication,
    form=PaymentApplicationForm,
    fields=['invoice', 'bill', 'amount_applied', 'discount_amount', 'notes'],
    extra=1,
    can_delete=True
)


# backend/apps/finance/forms/vendors.py

"""
Vendor Forms
"""

from django import forms
from django.forms import inlineformset_factory
from ..models import Vendor, VendorContact, Currency, Account


class VendorForm(forms.ModelForm):
    """Vendor form"""
    
    class Meta:
        model = Vendor
        fields = [
            'company_name', 'display_name', 'vendor_type', 'status',
            'primary_contact', 'email', 'phone', 'mobile', 'fax', 'website',
            'payment_terms', 'payment_terms_days', 'credit_limit', 'currency',
            'tax_id', 'vat_number', 'is_tax_exempt', 'tax_exempt_number',
            'is_1099_vendor', 'default_expense_account', 'accounts_payable_account',
            'bank_name', 'bank_account_number', 'routing_number', 'swift_code',
            'is_inventory_supplier', 'supplier_code', 'notes', 'internal_notes'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'primary_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'fax': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.Select(attrs={'class': 'form-control'}),
            'payment_terms_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'vat_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_exempt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'default_expense_account': forms.Select(attrs={'class': 'form-control'}),
            'accounts_payable_account': forms.Select(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'routing_number': forms.TextInput(attrs={'class': 'form-control'}),
            'swift_code': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier_code': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )
            self.fields['default_expense_account'].queryset = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD'],
                is_active=True
            )
            self.fields['accounts_payable_account'].queryset = Account.objects.filter(
                tenant=self.tenant,
                account_type='CURRENT_LIABILITY',
                is_active=True
            )


class VendorContactForm(forms.ModelForm):
    """Vendor contact form"""
    
    class Meta:
        model = VendorContact
        fields = [
            'contact_type', 'first_name', 'last_name', 'title',
            'email', 'phone', 'mobile', 'is_primary', 'receive_communications'
        ]
        widgets = {
            'contact_type': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'title': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
            'phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }


# Create formset for vendor contacts
VendorContactFormSet = inlineformset_factory(
    Vendor,
    VendorContact,
    form=VendorContactForm,
    fields=[
        'contact_type', 'first_name', 'last_name', 'title',
        'email', 'phone', 'mobile', 'is_primary'
    ],
    extra=1,
    can_delete=True
)


# backend/apps/finance/forms/bills.py

"""
Bill Forms
"""

from django import forms
from django.forms import inlineformset_factory
from ..models import Bill, BillItem, Vendor, Currency, Account, TaxCode


class BillForm(forms.ModelForm):
    """Bill form"""
    
    class Meta:
        model = Bill
        fields = [
            'vendor', 'bill_date', 'due_date', 'bill_type',
            'vendor_invoice_number', 'reference_number', 'currency',
            'exchange_rate', 'discount_amount', 'description',
            'notes', 'terms', 'source_purchase_order'
        ]
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'bill_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'bill_type': forms.Select(attrs={'class': 'form-control'}),
            'vendor_invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'terms': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'source_purchase_order': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['vendor'].queryset = Vendor.objects.filter(tenant=self.tenant)
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )


class BillItemForm(forms.ModelForm):
    """Bill item form"""
    
    class Meta:
        model = BillItem
        fields = [
            'line_number', 'item_type', 'product', 'description',
            'quantity', 'unit_cost', 'discount_rate', 'expense_account',
            'tax_code', 'project', 'department', 'location', 'warehouse'
        ]
        widgets = {
            'line_number': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'item_type': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'product': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'discount_rate': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'expense_account': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'tax_code': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'project': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'location': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'warehouse': forms.Select(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter accounts to expense accounts only
            self.fields['expense_account'].queryset = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD', 'ASSET'],
                is_active=True
            )
            self.fields['tax_code'].queryset = TaxCode.objects.filter(
                tenant=self.tenant, is_active=True
            )


# Create formset for bill items
BillItemFormSet = inlineformset_factory(
    Bill,
    BillItem,
    form=BillItemForm,
    fields=[
        'line_number', 'item_type', 'product', 'description',
        'quantity', 'unit_cost', 'discount_rate', 'expense_account', 'tax_code'
    ],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True
)


# backend/apps/finance/forms/bank_reconciliation.py

"""
Bank Reconciliation Forms
"""

from django import forms
from ..models import BankAccount, BankReconciliation, Account


class BankAccountForm(forms.ModelForm):
    """Bank account form"""
    
    class Meta:
        model = BankAccount
        fields = [
            'account', 'bank_name', 'account_number', 'account_type',
            'routing_number', 'swift_code', 'iban', 'enable_bank_feeds',
            'bank_feed_id', 'statement_import_format', 'auto_reconcile',
            'reconciliation_tolerance'
        ]
        widgets = {
            'account': forms.Select(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'routing_number': forms.TextInput(attrs={'class': 'form-control'}),
            'swift_code': forms.TextInput(attrs={'class': 'form-control'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_feed_id': forms.TextInput(attrs={'class': 'form-control'}),
            'statement_import_format': forms.Select(attrs={'class': 'form-control'}),
            'reconciliation_tolerance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter to bank accounts only
            self.fields['account'].queryset = Account.objects.filter(
                tenant=self.tenant,
                is_bank_account=True,
                is_active=True
            )


class BankReconciliationForm(forms.ModelForm):
    """Bank reconciliation form"""
    
    class Meta:
        model = BankReconciliation
        fields = [
            'bank_account', 'reconciliation_date', 'statement_beginning_balance',
            'statement_ending_balance', 'book_beginning_balance', 'book_ending_balance',
            'notes'
        ]
        widgets = {
            'bank_account': forms.Select(attrs={'class': 'form-control'}),
            'reconciliation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'statement_beginning_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'statement_ending_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'book_beginning_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'book_ending_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                account__tenant=self.tenant
            )(*args, **kwargs)
        
        # Filter currencies by tenant
        if self.tenant:
            self.fields['base_currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )

    def clean_fiscal_year_start_month(self):
        value = self.cleaned_data['fiscal_year_start_month']
        if not 1 <= value <= 12:
            raise ValidationError("Fiscal year start month must be between 1 and 12")
        return value

    def clean_currency_precision(self):
        value = self.cleaned_data['currency_precision']
        if not 0 <= value <= 8:
            raise ValidationError("Currency precision must be between 0 and 8")
        return value


class FiscalYearForm(forms.ModelForm):
    """Fiscal year form"""
    
    class Meta:
        model = FiscalYear
        fields = ['year', 'start_date', 'end_date', 'status']
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        return cleaned_data


# backend/apps/finance/forms/accounts.py

"""
Chart of Accounts Forms
"""

from django import forms
from django.core.exceptions import ValidationError
from ..models import AccountCategory, Account, TaxCode


class AccountCategoryForm(forms.ModelForm):
    """Account category form"""
    
    class Meta:
        model = AccountCategory
        fields = ['name', 'description', 'account_type', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AccountForm(forms.ModelForm):
    """Account form"""
    
    class Meta:
        model = Account
        fields = [
            'code', 'name', 'description', 'account_type', 'category',
            'parent_account', 'normal_balance', 'opening_balance',
            'opening_balance_date', 'currency', 'is_active', 'is_bank_account',
            'is_cash_account', 'allow_manual_entries', 'require_reconciliation',
            'bank_name', 'bank_account_number', 'bank_routing_number',
            'bank_swift_code', 'default_tax_code', 'is_taxable',
            'track_inventory', 'budget_amount'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'parent_account': forms.Select(attrs={'class': 'form-control'}),
            'normal_balance': forms.Select(attrs={'class': 'form-control'}),
            'opening_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'opening_balance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_routing_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_swift_code': forms.TextInput(attrs={'class': 'form-control'}),
            'default_tax_code': forms.Select(attrs={'class': 'form-control'}),
            'budget_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter related fields by tenant
            self.fields['category'].queryset = AccountCategory.objects.filter(
                tenant=self.tenant, is_active=True
            )
            self.fields['parent_account'].queryset = Account.objects.filter(
                tenant=self.tenant, is_active=True
            )
            self.fields['default_tax_code'].queryset = TaxCode.objects.filter(
                tenant=self.tenant, is_active=True
            )

    def clean_code(self):
        code = self.cleaned_data['code']
        
        # Check for unique code within tenant
        if self.tenant:
            existing = Account.objects.filter(
                tenant=self.tenant, 
                code=code
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError("Account code must be unique")
        
        return code

    def clean(self):
        cleaned_data = super().clean()
        parent_account = cleaned_data.get('parent_account')
        account_type = cleaned_data.get('account_type')
        
        # Validate parent account relationship
        if parent_account and account_type:
            if parent_account.account_type != account_type:
                raise ValidationError("Parent account must be of the same type")
        
        return cleaned_data


# backend/apps/finance/forms/journal_entries.py

"""
Journal Entry Forms
"""

from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from decimal import Decimal
from ..models import JournalEntry, JournalEntryLine, Account, Currency


class JournalEntryForm(forms.ModelForm):
    """Journal entry form"""
    
    class Meta:
        model = JournalEntry
        fields = [
            'entry_date', 'entry_type', 'description', 'notes',
            'reference_number', 'currency', 'exchange_rate'
        ]
        widgets = {
            'entry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'entry_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )


class JournalEntryLineForm(forms.ModelForm):
    """Journal entry line form"""
    
    class Meta:
        model = JournalEntryLine
        fields = [
            'line_number', 'account', 'description', 'debit_amount',
            'credit_amount', 'customer', 'vendor', 'product',
            'project', 'department', 'location'
        ]
        widgets = {
            'line_number': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'account': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'debit_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'credit_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'customer': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'vendor': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'product': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'project': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'location': forms.Select(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter related fields by tenant
            self.fields['account'].queryset = Account.objects.filter(
                tenant=self.tenant, is_active=True, allow_manual_entries=True
            )

    def clean(self):
        cleaned_data = super().clean()
        debit_amount = cleaned_data.get('debit_amount') or Decimal('0.00')
        credit_amount = cleaned_data.get('credit_amount') or Decimal('0.00')
        
        if debit_amount and credit_amount:
            raise ValidationError("Line cannot have both debit and credit amounts")
        
        if not debit_amount and not credit_amount:
            raise ValidationError("Line must have either debit or credit amount")
        
        return cleaned_data


# Create formset for journal entry lines
JournalEntryLineFormSet = inlineformset_factory(
    JournalEntry,
    JournalEntryLine,
    form=JournalEntryLineForm,
    fields=[
        'line_number', 'account', 'description', 'debit_amount',
        'credit_amount', 'customer', 'vendor', 'product'
    ],
    extra=2,
    min_num=2,
    validate_min=True,
    can_delete=True
)


# backend/apps/finance/forms/invoices.py

"""
Invoice Forms
"""

from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from ..models import Invoice, InvoiceItem, Customer, Currency, Account, TaxCode


class InvoiceForm(forms.ModelForm):
    """Invoice form"""
    
    class Meta:
        model = Invoice
        fields = [
            'customer', 'invoice_date', 'due_date', 'invoice_type',
            'reference_number', 'purchase_order_number', 'currency',
            'exchange_rate', 'discount_percentage', 'shipping_amount',
            'customer_message', 'notes', 'payment_terms',
            'payment_instructions', 'is_recurring'
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'invoice_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'invoice_type': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'shipping_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'customer_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            self.fields['customer'].queryset = Customer.objects.filter(tenant=self.tenant)
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=self.tenant, is_active=True
            )


class InvoiceItemForm(forms.ModelForm):
    """Invoice item form"""
    
    class Meta:
        model = InvoiceItem
        fields = [
            'line_number', 'item_type', 'product', 'description',
            'quantity', 'unit_price', 'discount_rate', 'revenue_account',
            'tax_code', 'project', 'department', 'location'
        ]
        widgets = {
            'line_number': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'item_type': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'product': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'discount_rate': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'revenue_account': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'tax_code': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'project': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'location': forms.Select(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter accounts to revenue accounts only
            self.fields['revenue_account'].queryset = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=['REVENUE', 'OTHER_INCOME'],
                is_active=True
            )
            self.fields['tax_code'].queryset = TaxCode.objects.filter(
                tenant=self.tenant, is_active=True
            )


# Create formset for invoice items
InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    fields=[
        'line_number', 'item_type', 'product', 'description',
        'quantity', 'unit_price', 'discount_rate', 'revenue_account', 'tax_code'
    ],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True
)


# backend/apps/finance/forms/payments.py

"""
Payment Forms
"""

from django import forms
from django.forms import inlineformset_factory
from ..models import Payment, PaymentApplication, Account, Customer, Vendor, Currency


class PaymentForm(forms.ModelForm):
    """Payment form"""
    
    class Meta:
        model = Payment
        fields = [
            'payment_type', 'payment_method', 'payment_date', 'amount',
            'currency', 'exchange_rate', 'customer', 'vendor',
            'bank_account', 'reference_number', 'description',
            'check_number', 'check_date', 'processing_fee'
        ]
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'bank_account': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'check_number': forms.TextInput(attrs={'class': 'form-control'}),
            'check_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'processing_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__