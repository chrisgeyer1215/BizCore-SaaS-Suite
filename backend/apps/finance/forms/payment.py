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

