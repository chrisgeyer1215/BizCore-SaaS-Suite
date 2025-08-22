"""
Finance Accounts Forms
Forms for managing chart of accounts and account categories
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from ..models import Account, AccountCategory, AccountType


class AccountCategoryForm(forms.ModelForm):
    """Form for creating/editing account categories"""
    
    class Meta:
        model = AccountCategory
        fields = [
            'name', 'code', 'description', 'parent_category',
            'account_type', 'is_active', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category code'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter category description'
            }),
            'parent_category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
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
            # Filter parent categories by tenant
            self.fields['parent_category'].queryset = AccountCategory.objects.filter(
                tenant=tenant,
                is_active=True
            ).exclude(id=self.instance.id if self.instance.id else 0)
            
            # Filter account types
            self.fields['account_type'].choices = AccountType.choices
    
    def clean_code(self):
        """Validate category code uniqueness within tenant"""
        code = self.cleaned_data['code']
        tenant = getattr(self.instance, 'tenant', None)
        
        if not tenant:
            return code
        
        # Check for duplicate codes within the same tenant
        existing = AccountCategory.objects.filter(
            tenant=tenant,
            code=code
        ).exclude(id=self.instance.id if self.instance.id else 0)
        
        if existing.exists():
            raise ValidationError(_('A category with this code already exists.'))
        
        return code.upper()
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        parent_category = cleaned_data.get('parent_category')
        account_type = cleaned_data.get('account_type')
        
        # Ensure parent category has compatible account type
        if parent_category and account_type:
            if parent_category.account_type != account_type:
                raise ValidationError(_(
                    'Child category must have the same account type as its parent.'
                ))
        
        return cleaned_data


class AccountForm(forms.ModelForm):
    """Form for creating/editing accounts"""
    
    class Meta:
        model = Account
        fields = [
            'name', 'code', 'description', 'category', 'account_type',
            'currency', 'is_active', 'allow_manual_entries',
            'require_approval', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter account name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter account code'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter account description'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'allow_manual_entries': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'require_approval': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
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
            # Filter categories by tenant
            self.fields['category'].queryset = AccountCategory.objects.filter(
                tenant=tenant,
                is_active=True
            )
            
            # Filter currencies by tenant
            from ..models import Currency
            self.fields['currency'].queryset = Currency.objects.filter(
                tenant=tenant,
                is_active=True
            )
            
            # Filter account types
            self.fields['account_type'].choices = AccountType.choices
    
    def clean_code(self):
        """Validate account code uniqueness within tenant"""
        code = self.cleaned_data['code']
        tenant = getattr(self.instance, 'tenant', None)
        
        if not tenant:
            return code
        
        # Check for duplicate codes within the same tenant
        existing = Account.objects.filter(
            tenant=tenant,
            code=code
        ).exclude(id=self.instance.id if self.instance.id else 0)
        
        if existing.exists():
            raise ValidationError(_('An account with this code already exists.'))
        
        return code.upper()
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        account_type = cleaned_data.get('account_type')
        
        # Ensure account type matches category type
        if category and account_type:
            if category.account_type != account_type:
                raise ValidationError(_(
                    'Account type must match the selected category type.'
                ))
        
        return cleaned_data


class AccountSearchForm(forms.Form):
    """Form for searching accounts"""
    
    SEARCH_CHOICES = [
        ('name', 'Account Name'),
        ('code', 'Account Code'),
        ('category', 'Category'),
        ('type', 'Account Type'),
        ('status', 'Status')
    ]
    
    search_term = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search accounts...'
        })
    )
    
    search_by = forms.ChoiceField(
        choices=SEARCH_CHOICES,
        initial='name',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=AccountCategory.objects.none(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    account_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(AccountType.choices),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_active = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('True', 'Active'),
            ('False', 'Inactive')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if tenant:
            # Filter categories by tenant
            self.fields['category'].queryset = AccountCategory.objects.filter(
                tenant=tenant,
                is_active=True
            ).order_by('name')


class AccountImportForm(forms.Form):
    """Form for importing accounts from CSV/Excel"""
    
    file = forms.FileField(
        label='Import File',
        help_text='Upload CSV or Excel file with account data',
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
        help_text='Update existing accounts if they exist',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    create_categories = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Automatically create missing categories',
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


class AccountExportForm(forms.Form):
    """Form for exporting accounts"""
    
    EXPORT_FORMATS = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON')
    ]
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='csv',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    include_inactive = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Include inactive accounts',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    include_balances = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Include current account balances',
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
            ('custom', 'Custom Range')
        ],
        initial='all',
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