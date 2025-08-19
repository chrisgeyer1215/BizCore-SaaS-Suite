"""
Chart of Accounts Models
Account categories and account definitions
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from .currency import Currency

User = get_user_model()


class AccountCategory(TenantBaseModel):
    """Account categories for better organization"""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    account_type = models.CharField(max_length=30)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Parent-child hierarchy
    parent_category = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    
    # Default settings for accounts in this category
    default_tax_code = models.ForeignKey(
        'finance.TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['account_type', 'sort_order', 'name']
        verbose_name_plural = 'Account Categories'
        db_table = 'finance_account_categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name', 'account_type'],
                name='unique_tenant_account_category'
            ),
        ]
        
    def __str__(self):
        if self.parent_category:
            return f'{self.parent_category.name} > {self.name}'
        return self.name
    
    def get_full_path(self):
        """Get full category path"""
        path = [self.name]
        parent = self.parent_category
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent_category
        return ' > '.join(path)


class Account(TenantBaseModel, SoftDeleteMixin):
    """Enhanced Chart of Accounts with multi-currency and inventory integration"""
    
    ACCOUNT_TYPES = [
        # Assets
        ('ASSET', 'Asset'),
        ('CURRENT_ASSET', 'Current Asset'),
        ('FIXED_ASSET', 'Fixed Asset'),
        ('OTHER_ASSET', 'Other Asset'),
        
        # Liabilities
        ('LIABILITY', 'Liability'),
        ('CURRENT_LIABILITY', 'Current Liability'),
        ('LONG_TERM_LIABILITY', 'Long Term Liability'),
        
        # Equity
        ('EQUITY', 'Equity'),
        ('RETAINED_EARNINGS', 'Retained Earnings'),
        
        # Revenue
        ('REVENUE', 'Revenue'),
        ('OTHER_INCOME', 'Other Income'),
        
        # Expenses
        ('EXPENSE', 'Expense'),
        ('COST_OF_GOODS_SOLD', 'Cost of Goods Sold'),
        ('OTHER_EXPENSE', 'Other Expense'),
    ]
    
    NORMAL_BALANCE_CHOICES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]
    
    # Account Identification
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Account Classification
    account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPES)
    category = models.ForeignKey(
        AccountCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    parent_account = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_accounts'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Balance Information
    normal_balance = models.CharField(max_length=10, choices=NORMAL_BALANCE_CHOICES)
    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    opening_balance_date = models.DateField(null=True, blank=True)
    
    # Multi-Currency Support
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    # Account Settings
    is_active = models.BooleanField(default=True)
    is_system_account = models.BooleanField(default=False)
    is_bank_account = models.BooleanField(default=False)
    is_cash_account = models.BooleanField(default=False)
    allow_manual_entries = models.BooleanField(default=True)
    require_reconciliation = models.BooleanField(default=False)
    
    # Bank Account Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_routing_number = models.CharField(max_length=20, blank=True)
    bank_swift_code = models.CharField(max_length=20, blank=True)
    
    # Tax Settings
    default_tax_code = models.ForeignKey(
        'finance.TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_taxable = models.BooleanField(default=False)
    tax_line = models.CharField(max_length=100, blank=True)
    
    # Inventory Integration
    track_inventory = models.BooleanField(default=False)
    inventory_valuation_method = models.CharField(max_length=20, blank=True)
    
    # Budget & Controls
    budget_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Additional Settings
    require_project = models.BooleanField(default=False)
    require_department = models.BooleanField(default=False)
    require_location = models.BooleanField(default=False)
    
    # Cash Flow Classification
    cash_flow_category = models.CharField(
        max_length=20,
        choices=[
            ('OPERATING', 'Operating Activities'),
            ('INVESTING', 'Investing Activities'),
            ('FINANCING', 'Financing Activities'),
            ('NONE', 'Not Applicable'),
        ],
        default='NONE'
    )
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_accounts'
    )
    
    class Meta:
        ordering = ['code']
        db_table = 'finance_accounts'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_account_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'account_type', 'is_active']),
            models.Index(fields=['tenant', 'parent_account']),
            models.Index(fields=['tenant', 'is_bank_account']),
            models.Index(fields=['tenant', 'is_system_account']),
        ]
        
    def __str__(self):
        return f'{self.code} - {self.name}'
    
    def save(self, *args, **kwargs):
        # Auto-calculate level based on parent
        if self.parent_account:
            self.level = self.parent_account.level + 1
        else:
            self.level = 0
        
        # Set normal balance based on account type
        if not self.normal_balance:
            if self.account_type in ['ASSET', 'EXPENSE', 'COST_OF_GOODS_SOLD']:
                self.normal_balance = 'DEBIT'
            else:
                self.normal_balance = 'CREDIT'
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate account"""
        # Prevent circular references
        if self.parent_account:
            current = self.parent_account
            while current:
                if current == self:
                    raise ValidationError('Circular reference detected in account hierarchy')
                current = current.parent_account
        
        # Validate account code format
        if not self.code.replace('-', '').replace('.', '').isalnum():
            raise ValidationError('Account code can only contain letters, numbers, hyphens, and periods')
        
        # Bank account validation
        if self.is_bank_account and not self.account_type in ['CURRENT_ASSET', 'ASSET']:
            raise ValidationError('Bank accounts must be current assets')
    
    def get_balance(self, as_of_date=None, currency=None):
        """Get account balance as of specific date with currency conversion"""
        from ..services.accounting import AccountingService
        
        service = AccountingService(self.tenant)
        return service.get_account_balance(self.id, as_of_date, currency)
    
    def get_balance_sheet_section(self):
        """Get balance sheet section for this account"""
        section_mapping = {
            'CURRENT_ASSET': 'Current Assets',
            'FIXED_ASSET': 'Fixed Assets',
            'OTHER_ASSET': 'Other Assets',
            'CURRENT_LIABILITY': 'Current Liabilities',
            'LONG_TERM_LIABILITY': 'Long Term Liabilities',
            'EQUITY': 'Equity',
            'RETAINED_EARNINGS': 'Equity',
        }
        return section_mapping.get(self.account_type)
    
    def is_balance_sheet_account(self):
        """Check if this is a balance sheet account"""
        balance_sheet_types = [
            'ASSET', 'CURRENT_ASSET', 'FIXED_ASSET', 'OTHER_ASSET',
            'LIABILITY', 'CURRENT_LIABILITY', 'LONG_TERM_LIABILITY',
            'EQUITY', 'RETAINED_EARNINGS'
        ]
        return self.account_type in balance_sheet_types
    
    def is_income_statement_account(self):
        """Check if this is an income statement account"""
        income_statement_types = [
            'REVENUE', 'OTHER_INCOME',
            'EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'
        ]
        return self.account_type in income_statement_types
    
    def get_children(self, include_inactive=False):
        """Get all child accounts"""
        queryset = self.sub_accounts.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def get_descendants(self, include_inactive=False):
        """Get all descendant accounts (recursive)"""
        descendants = []
        children = self.get_children(include_inactive)
        
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_descendants(include_inactive))
        
        return descendants
    
    def get_full_name(self):
        """Get full account name with parent hierarchy"""
        names = [self.name]
        parent = self.parent_account
        
        while parent:
            names.insert(0, parent.name)
            parent = parent.parent_account
        
        return ' > '.join(names)
    
    def update_balance(self, amount, is_debit=True):
        """Update account balance"""
        if is_debit:
            if self.normal_balance == 'DEBIT':
                self.current_balance += amount
            else:
                self.current_balance -= amount
        else:  # Credit
            if self.normal_balance == 'CREDIT':
                self.current_balance += amount
            else:
                self.current_balance -= amount
        
        self.save(update_fields=['current_balance'])
    
    @property
    def formatted_balance(self):
        """Get formatted balance with currency"""
        if self.currency:
            return self.currency.format_amount(self.current_balance)
        return f"{self.current_balance:,.2f}"
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.budget_amount and self.budget_amount > 0:
            return abs(self.current_balance / self.budget_amount) * 100
        return Decimal('0.00')
    
    @property
    def is_over_budget(self):
        """Check if account is over budget"""
        if not self.budget_amount:
            return False
        
        if self.account_type in ['EXPENSE', 'COST_OF_GOODS_SOLD']:
            return self.current_balance > self.budget_amount
        else:
            return abs(self.current_balance) > abs(self.budget_amount)