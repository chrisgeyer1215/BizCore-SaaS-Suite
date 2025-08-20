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