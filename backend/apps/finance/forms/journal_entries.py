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