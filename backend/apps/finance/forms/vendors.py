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