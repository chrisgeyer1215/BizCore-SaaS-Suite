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