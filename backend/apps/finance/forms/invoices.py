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