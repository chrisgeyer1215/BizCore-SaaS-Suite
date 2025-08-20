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