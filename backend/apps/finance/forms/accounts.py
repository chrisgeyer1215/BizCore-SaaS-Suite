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