"""
Finance Journal Entries Forms
Forms for managing journal entries and journal entry lines
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.db.models import Q
from decimal import Decimal

from ..models import JournalEntry, JournalEntryLine, Account


class JournalEntryForm(forms.ModelForm):
    """Form for creating/editing journal entries"""
    
    class Meta:
        model = JournalEntry
        fields = [
            'entry_date', 'entry_type', 'reference', 'reference_type',
            'reference_id', 'description', 'status', 'notes'
        ]
        widgets = {
            'entry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'entry_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter reference number or description'
            }),
            'reference_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'reference_id': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter reference ID'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter journal entry description'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            })
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter reference types based on available models
            self.fields['reference_type'].choices = [
                ('', 'Select reference type'),
                ('invoice', 'Invoice'),
                ('bill', 'Bill'),
                ('payment', 'Payment'),
                ('receipt', 'Receipt'),
                ('adjustment', 'Adjustment'),
                ('manual', 'Manual Entry')
            ]
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        entry_type = cleaned_data.get('entry_type')
        reference_type = cleaned_data.get('reference_type')
        reference_id = cleaned_data.get('reference_id')
        
        # Validate reference ID is provided when reference type is selected
        if reference_type and reference_type != 'manual' and not reference_id:
            raise ValidationError(_('Reference ID is required when reference type is selected.'))
        
        return cleaned_data


class JournalEntryLineForm(forms.ModelForm):
    """Form for individual journal entry lines"""
    
    class Meta:
        model = JournalEntryLine
        fields = [
            'account', 'description', 'debit_amount', 'credit_amount',
            'tax_code', 'project', 'department', 'location'
        ]
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-control account-select',
                'data-placeholder': 'Select account'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter line description'
            }),
            'debit_amount': forms.NumberInput(attrs={
                'class': 'form-control debit-amount',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'credit_amount': forms.NumberInput(attrs={
                'class': 'form-control credit-amount',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'tax_code': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select tax code'
            }),
            'project': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select project'
            }),
            'department': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select department'
            }),
            'location': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select location'
            })
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter accounts by tenant
            self.fields['account'].queryset = Account.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('code')
            
            # Filter tax codes by tenant
            from ..models import TaxCode
            self.fields['tax_code'].queryset = TaxCode.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('code')
            
            # Filter projects by tenant
            from ..models import Project
            self.fields['project'].queryset = Project.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('name')
            
            # Filter departments by tenant
            from ..models import Department
            self.fields['department'].queryset = Department.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('name')
            
            # Filter locations by tenant
            from ..models import Location
            self.fields['location'].queryset = Location.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('name')
    
    def clean(self):
        """Validate line data"""
        cleaned_data = super().clean()
        debit_amount = cleaned_data.get('debit_amount') or Decimal('0.00')
        credit_amount = cleaned_data.get('credit_amount') or Decimal('0.00')
        account = cleaned_data.get('account')
        
        # Ensure only one amount is entered
        if debit_amount > 0 and credit_amount > 0:
            raise ValidationError(_('Enter either debit or credit amount, not both.'))
        
        if debit_amount == 0 and credit_amount == 0:
            raise ValidationError(_('Either debit or credit amount must be entered.'))
        
        # Validate account is selected
        if not account:
            raise ValidationError(_('Account is required.'))
        
        return cleaned_data


class JournalEntryLineFormSet(BaseInlineFormSet):
    """Formset for journal entry lines with validation"""
    
    def clean(self):
        """Validate the entire formset"""
        super().clean()
        
        if not self.forms:
            raise ValidationError(_('At least one journal entry line is required.'))
        
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        has_lines = False
        
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                has_lines = True
                debit = form.cleaned_data.get('debit_amount') or Decimal('0.00')
                credit = form.cleaned_data.get('credit_amount') or Decimal('0.00')
                total_debit += debit
                total_credit += credit
        
        if not has_lines:
            raise ValidationError(_('At least one journal entry line is required.'))
        
        # Check if debits equal credits
        if abs(total_debit - total_credit) > Decimal('0.01'):
            raise ValidationError(_(
                'Total debits ({}) must equal total credits ({}). '
                'Difference: {}'.format(
                    total_debit, total_credit, total_debit - total_credit
                )
            ))


# Create the inline formset factory
JournalEntryLineFormSet = inlineformset_factory(
    JournalEntry,
    JournalEntryLine,
    form=JournalEntryLineForm,
    formset=JournalEntryLineFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class JournalEntrySearchForm(forms.Form):
    """Form for searching journal entries"""
    
    SEARCH_CHOICES = [
        ('entry_number', 'Entry Number'),
        ('reference', 'Reference'),
        ('description', 'Description'),
        ('account', 'Account')
    ]
    
    search_term = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search journal entries...'
        })
    )
    
    search_by = forms.ChoiceField(
        choices=SEARCH_CHOICES,
        initial='entry_number',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    entry_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(JournalEntry.ENTRY_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(JournalEntry.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        empty_label="All Accounts",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    min_amount = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Min amount'
        })
    )
    
    max_amount = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Max amount'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter accounts by tenant
            self.fields['account'].queryset = Account.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('code')
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise ValidationError(_('Start date must be before end date.'))
        
        # Validate amount range
        if min_amount and max_amount and min_amount > max_amount:
            raise ValidationError(_('Minimum amount must be less than maximum amount.'))
        
        return cleaned_data


class JournalEntryImportForm(forms.Form):
    """Form for importing journal entries from CSV/Excel"""
    
    file = forms.FileField(
        label='Import File',
        help_text='Upload CSV or Excel file with journal entry data',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        })
    )
    
    file_format = forms.ChoiceField(
        choices=[
            ('csv', 'CSV'),
            ('excel', 'Excel')
        ],
        initial='csv',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Update existing entries if they exist',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    auto_balance = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Automatically balance debits and credits',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    create_accounts = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Automatically create missing accounts',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Preview changes without saving (recommended)',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class JournalEntryExportForm(forms.Form):
    """Form for exporting journal entries"""
    
    EXPORT_FORMATS = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('pdf', 'PDF')
    ]
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='csv',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    include_lines = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Include journal entry lines',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    include_balances = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Include running balances',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    include_metadata = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Include creation/modification dates',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    date_range = forms.ChoiceField(
        choices=[
            ('all', 'All Time'),
            ('current_year', 'Current Year'),
            ('current_month', 'Current Month'),
            ('current_quarter', 'Current Quarter'),
            ('custom', 'Custom Range')
        ],
        initial='current_month',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError(_('Start and end dates are required for custom range.'))
            
            if start_date > end_date:
                raise ValidationError(_('Start date must be before end date.'))
        
        return cleaned_data