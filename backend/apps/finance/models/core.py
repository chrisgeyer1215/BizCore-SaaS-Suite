"""
Finance Core Configuration Models
Core settings and fiscal year management for the finance module
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date
import uuid

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class FinanceSettings(TenantBaseModel):
    """Enhanced finance system configuration per tenant"""
    
    FISCAL_YEAR_START_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]
    
    TAX_CALCULATION_CHOICES = [
        ('INCLUSIVE', 'Tax Inclusive'),
        ('EXCLUSIVE', 'Tax Exclusive'),
    ]
    
    ACCOUNTING_METHODS = [
        ('CASH', 'Cash Basis'),
        ('ACCRUAL', 'Accrual Basis'),
    ]
    
    INVENTORY_VALUATION_METHODS = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('WEIGHTED_AVERAGE', 'Weighted Average'),
        ('SPECIFIC_ID', 'Specific Identification'),
        ('STANDARD_COST', 'Standard Cost'),
    ]
    
    # Company Information
    company_name = models.CharField(max_length=200)
    company_registration_number = models.CharField(max_length=100, blank=True)
    tax_identification_number = models.CharField(max_length=100, blank=True)
    vat_number = models.CharField(max_length=50, blank=True)
    company_address = models.JSONField(default=dict)
    company_logo = models.ImageField(upload_to='finance/logos/', blank=True)
    
    # Fiscal Year Settings
    fiscal_year_start_month = models.IntegerField(
        choices=FISCAL_YEAR_START_CHOICES,
        default=1,
        help_text="Month when fiscal year starts"
    )
    current_fiscal_year = models.IntegerField(default=2024)
    
    # Accounting Method
    accounting_method = models.CharField(
        max_length=10,
        choices=ACCOUNTING_METHODS,
        default='ACCRUAL'
    )
    
    # Currency Settings
    base_currency = models.CharField(max_length=3, default='USD')
    enable_multi_currency = models.BooleanField(default=True)
    currency_precision = models.IntegerField(default=2)
    auto_update_exchange_rates = models.BooleanField(default=False)
    
    # Inventory Integration
    inventory_valuation_method = models.CharField(
        max_length=20,
        choices=INVENTORY_VALUATION_METHODS,
        default='FIFO'
    )
    track_inventory_value = models.BooleanField(default=True)
    auto_create_cogs_entries = models.BooleanField(default=True)
    enable_landed_costs = models.BooleanField(default=False)
    
    # Tax Settings
    tax_calculation_method = models.CharField(
        max_length=20,
        choices=TAX_CALCULATION_CHOICES,
        default='EXCLUSIVE'
    )
    default_sales_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    default_purchase_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    enable_tax_tracking = models.BooleanField(default=True)
    
    # Invoice & Bill Settings
    invoice_prefix = models.CharField(max_length=10, default='INV')
    invoice_starting_number = models.PositiveIntegerField(default=1000)
    bill_prefix = models.CharField(max_length=10, default='BILL')
    bill_starting_number = models.PositiveIntegerField(default=1000)
    payment_prefix = models.CharField(max_length=10, default='PAY')
    payment_starting_number = models.PositiveIntegerField(default=1000)
    
    # Account Settings
    enable_multi_location = models.BooleanField(default=False)
    enable_project_accounting = models.BooleanField(default=False)
    enable_class_tracking = models.BooleanField(default=False)
    enable_departments = models.BooleanField(default=False)
    
    # Financial Controls
    require_customer_on_sales = models.BooleanField(default=True)
    require_vendor_on_purchases = models.BooleanField(default=True)
    auto_create_journal_entries = models.BooleanField(default=True)
    enable_budget_controls = models.BooleanField(default=False)
    
    # Integration Settings
    sync_with_inventory = models.BooleanField(default=True)
    sync_with_ecommerce = models.BooleanField(default=True)
    sync_with_crm = models.BooleanField(default=True)
    enable_bank_feeds = models.BooleanField(default=False)
    
    # Approval Workflows
    require_invoice_approval = models.BooleanField(default=False)
    require_bill_approval = models.BooleanField(default=False)
    invoice_approval_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    bill_approval_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Bank Reconciliation Settings
    auto_match_bank_transactions = models.BooleanField(default=True)
    bank_match_tolerance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount difference tolerance for auto-matching"
    )
    
    # Reporting Settings
    enable_cash_flow_forecasting = models.BooleanField(default=True)
    enable_advanced_reporting = models.BooleanField(default=True)
    default_payment_terms_days = models.PositiveIntegerField(default=30)
    enable_late_fees = models.BooleanField(default=False)
    late_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Automation Settings
    auto_reconcile = models.BooleanField(default=False)
    auto_send_reminders = models.BooleanField(default=True)
    reminder_days_before_due = models.PositiveIntegerField(default=3)
    auto_backup_enabled = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Finance Settings'
        verbose_name_plural = 'Finance Settings'
        db_table = 'finance_settings'
        
    def __str__(self):
        return f'Finance Settings - {self.company_name}'
    
    def clean(self):
        """Validate finance settings"""
        if self.invoice_approval_limit and self.invoice_approval_limit < 0:
            raise ValidationError('Invoice approval limit cannot be negative')
        
        if self.bill_approval_limit and self.bill_approval_limit < 0:
            raise ValidationError('Bill approval limit cannot be negative')
        
        if self.default_payment_terms_days > 365:
            raise ValidationError('Payment terms cannot exceed 365 days')


class FiscalYear(TenantBaseModel):
    """Enhanced fiscal year definition and status"""
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('LOCKED', 'Locked'),
    ]
    
    year = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    closed_date = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Financial Summary (calculated when closed)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    net_income = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Balance Sheet Summary
    total_assets = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_liabilities = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_equity = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        ordering = ['-year']
        db_table = 'finance_fiscal_years'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'year'],
                name='unique_tenant_fiscal_year'
            ),
        ]
        
    def __str__(self):
        return f'FY {self.year} ({self.start_date} to {self.end_date})'
    
    def clean(self):
        """Validate fiscal year"""
        if self.start_date >= self.end_date:
            raise ValidationError('Fiscal year start date must be before end date')
        
        # Check for overlapping fiscal years
        overlapping = FiscalYear.objects.filter(
            tenant=self.tenant
        ).exclude(id=self.id).filter(
            models.Q(start_date__lte=self.end_date, end_date__gte=self.start_date)
        )
        
        if overlapping.exists():
            raise ValidationError('Fiscal year dates cannot overlap with existing fiscal years')
    
    @property
    def is_current(self):
        """Check if this is the current fiscal year"""
        today = date.today()
        return self.start_date <= today <= self.end_date
    
    @property
    def days_remaining(self):
        """Days remaining in fiscal year"""
        if self.status != 'OPEN':
            return 0
        return (self.end_date - date.today()).days
    
    def close_fiscal_year(self, user):
        """Close the fiscal year"""
        if self.status == 'CLOSED':
            raise ValidationError('Fiscal year is already closed')
        
        # Calculate financial summary
        self.calculate_financial_summary()
        
        # Create closing entries
        self.create_closing_entries(user)
        
        self.status = 'CLOSED'
        self.closed_date = timezone.now()
        self.closed_by = user
        self.save()
    
    def calculate_financial_summary(self):
        """Calculate fiscal year financial summary"""
        from ..services.reporting import FinancialReportingService
        
        reporting_service = FinancialReportingService(self.tenant)
        summary = reporting_service.get_fiscal_year_summary(self.year)
        
        self.total_revenue = summary.get('total_revenue', Decimal('0.00'))
        self.total_expenses = summary.get('total_expenses', Decimal('0.00'))
        self.total_cogs = summary.get('total_cogs', Decimal('0.00'))
        self.gross_profit = self.total_revenue - self.total_cogs
        self.net_income = self.gross_profit - self.total_expenses
        self.total_assets = summary.get('total_assets', Decimal('0.00'))
        self.total_liabilities = summary.get('total_liabilities', Decimal('0.00'))
        self.total_equity = summary.get('total_equity', Decimal('0.00'))
    
    def create_closing_entries(self, user):
        """Create year-end closing entries"""
        from ..services.journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        service.create_year_end_closing_entries(self, user)


class FinancialPeriod(TenantBaseModel):
    """Enhanced financial periods for better reporting"""
    
    PERIOD_TYPES = [
        ('MONTH', 'Monthly'),
        ('QUARTER', 'Quarterly'),
        ('YEAR', 'Yearly'),
        ('CUSTOM', 'Custom'),
    ]
    
    PERIOD_STATUS = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('LOCKED', 'Locked'),
    ]
    
    # Period Information
    name = models.CharField(max_length=100)
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPES)
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.CASCADE,
        related_name='periods'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=10, choices=PERIOD_STATUS, default='OPEN')
    
    # Closing Information
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_periods'
    )
    closed_date = models.DateTimeField(null=True, blank=True)
    
    # Budget Information
    budgeted_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    budgeted_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        ordering = ['-start_date']
        db_table = 'finance_financial_periods'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'start_date', 'end_date'],
                name='unique_tenant_period'
            ),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        """Validate financial period"""
        if self.start_date >= self.end_date:
            raise ValidationError('Period start date must be before end date')
        
        # Check if period is within fiscal year
        if not (self.fiscal_year.start_date <= self.start_date <= self.fiscal_year.end_date):
            raise ValidationError('Period must be within the fiscal year')
        
        if not (self.fiscal_year.start_date <= self.end_date <= self.fiscal_year.end_date):
            raise ValidationError('Period must be within the fiscal year')
    
    @property
    def variance_revenue(self):
        """Revenue variance (actual vs budget)"""
        return self.actual_revenue - self.budgeted_revenue
    
    @property
    def variance_expenses(self):
        """Expense variance (actual vs budget)"""
        return self.actual_expenses - self.budgeted_expenses
    
    @property
    def variance_percentage_revenue(self):
        """Revenue variance percentage"""
        if self.budgeted_revenue > 0:
            return (self.variance_revenue / self.budgeted_revenue) * 100
        return Decimal('0.00')
    
    @property
    def variance_percentage_expenses(self):
        """Expense variance percentage"""
        if self.budgeted_expenses > 0:
            return (self.variance_expenses / self.budgeted_expenses) * 100
        return Decimal('0.00')
    
    def close_period(self, user):
        """Close the financial period"""
        if self.status == 'CLOSED':
            raise ValidationError('Period is already closed')
        
        # Calculate actual amounts
        self.calculate_actual_amounts()
        
        self.status = 'CLOSED'
        self.closed_by = user
        self.closed_date = timezone.now()
        self.save()
    
    def calculate_actual_amounts(self):
        """Calculate actual revenue and expenses for the period"""
        from ..services.reporting import FinancialReportingService
        
        service = FinancialReportingService(self.tenant)
        actuals = service.get_period_actuals(self.start_date, self.end_date)
        
        self.actual_revenue = actuals.get('revenue', Decimal('0.00'))
        self.actual_expenses = actuals.get('expenses', Decimal('0.00'))