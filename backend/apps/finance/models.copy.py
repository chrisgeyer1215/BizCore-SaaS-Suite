# """
# Finance & Accounting Models - Enhanced QuickBooks-like functionality
# Combines Model 2's clean architecture with Model 1's advanced features
# """

# from django.db import models, transaction
# from django.contrib.auth import get_user_model
# from django.core.validators import MinValueValidator, MaxValueValidator
# from django.utils import timezone
# from django.core.exceptions import ValidationError
# from decimal import Decimal, ROUND_HALF_UP
# import uuid
# from datetime import date, datetime, timedelta
# import json

# from apps.core.models import TenantBaseModel, SoftDeleteMixin
# from apps.core.utils import generate_code
# from apps.crm.models import Customer, Lead, Contact
# from apps.inventory.models import Product, Warehouse, StockItem, PurchaseOrder, StockMovement


# User = get_user_model()


# # ============================================================================
# # CORE FINANCE CONFIGURATION
# # ============================================================================

# class FinanceSettings(TenantBaseModel):
#     """Enhanced finance system configuration per tenant"""
    
#     FISCAL_YEAR_START_CHOICES = [
#         (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
#         (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
#         (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
#     ]
    
#     TAX_CALCULATION_CHOICES = [
#         ('INCLUSIVE', 'Tax Inclusive'),
#         ('EXCLUSIVE', 'Tax Exclusive'),
#     ]
    
#     ACCOUNTING_METHODS = [
#         ('CASH', 'Cash Basis'),
#         ('ACCRUAL', 'Accrual Basis'),
#     ]
    
#     INVENTORY_VALUATION_METHODS = [
#         ('FIFO', 'First In First Out'),
#         ('LIFO', 'Last In First Out'),
#         ('WEIGHTED_AVERAGE', 'Weighted Average'),
#         ('SPECIFIC_ID', 'Specific Identification'),
#         ('STANDARD_COST', 'Standard Cost'),
#     ]
    
#     # Company Information
#     company_name = models.CharField(max_length=200)
#     company_registration_number = models.CharField(max_length=100, blank=True)
#     tax_identification_number = models.CharField(max_length=100, blank=True)
#     vat_number = models.CharField(max_length=50, blank=True)
#     company_address = models.JSONField(default=dict)
#     company_logo = models.ImageField(upload_to='finance/logos/', blank=True)
    
#     # Fiscal Year Settings
#     fiscal_year_start_month = models.IntegerField(
#         choices=FISCAL_YEAR_START_CHOICES,
#         default=1,
#         help_text="Month when fiscal year starts"
#     )
#     current_fiscal_year = models.IntegerField(default=2024)
    
#     # Accounting Method
#     accounting_method = models.CharField(
#         max_length=10,
#         choices=ACCOUNTING_METHODS,
#         default='ACCRUAL'
#     )
    
#     # Currency Settings
#     base_currency = models.CharField(max_length=3, default='USD')
#     enable_multi_currency = models.BooleanField(default=True)
#     currency_precision = models.IntegerField(default=2)
#     auto_update_exchange_rates = models.BooleanField(default=False)
    
#     # Inventory Integration
#     inventory_valuation_method = models.CharField(
#         max_length=20,
#         choices=INVENTORY_VALUATION_METHODS,
#         default='FIFO'
#     )
#     track_inventory_value = models.BooleanField(default=True)
#     auto_create_cogs_entries = models.BooleanField(default=True)
#     enable_landed_costs = models.BooleanField(default=False)
    
#     # Tax Settings
#     tax_calculation_method = models.CharField(
#         max_length=20,
#         choices=TAX_CALCULATION_CHOICES,
#         default='EXCLUSIVE'
#     )
#     default_sales_tax_rate = models.DecimalField(
#         max_digits=5,
#         decimal_places=4,
#         default=Decimal('0.0000')
#     )
#     default_purchase_tax_rate = models.DecimalField(
#         max_digits=5,
#         decimal_places=4,
#         default=Decimal('0.0000')
#     )
#     enable_tax_tracking = models.BooleanField(default=True)
    
#     # Invoice & Bill Settings
#     invoice_prefix = models.CharField(max_length=10, default='INV')
#     invoice_starting_number = models.PositiveIntegerField(default=1000)
#     bill_prefix = models.CharField(max_length=10, default='BILL')
#     bill_starting_number = models.PositiveIntegerField(default=1000)
#     payment_prefix = models.CharField(max_length=10, default='PAY')
#     payment_starting_number = models.PositiveIntegerField(default=1000)
    
#     # Account Settings
#     enable_multi_location = models.BooleanField(default=False)
#     enable_project_accounting = models.BooleanField(default=False)
#     enable_class_tracking = models.BooleanField(default=False)
#     enable_departments = models.BooleanField(default=False)
    
#     # Financial Controls
#     require_customer_on_sales = models.BooleanField(default=True)
#     require_vendor_on_purchases = models.BooleanField(default=True)
#     auto_create_journal_entries = models.BooleanField(default=True)
#     enable_budget_controls = models.BooleanField(default=False)
    
#     # Integration Settings
#     sync_with_inventory = models.BooleanField(default=True)
#     sync_with_ecommerce = models.BooleanField(default=True)
#     sync_with_crm = models.BooleanField(default=True)
#     enable_bank_feeds = models.BooleanField(default=False)
    
#     # Approval Workflows
#     require_invoice_approval = models.BooleanField(default=False)
#     require_bill_approval = models.BooleanField(default=False)
#     invoice_approval_limit = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
#     bill_approval_limit = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
    
#     # Bank Reconciliation Settings
#     auto_match_bank_transactions = models.BooleanField(default=True)
#     bank_match_tolerance = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Amount difference tolerance for auto-matching"
#     )
    
#     # Reporting Settings
#     enable_cash_flow_forecasting = models.BooleanField(default=True)
#     enable_advanced_reporting = models.BooleanField(default=True)
#     default_payment_terms_days = models.PositiveIntegerField(default=30)
#     enable_late_fees = models.BooleanField(default=False)
#     late_fee_percentage = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
    
#     # Automation Settings
#     auto_reconcile = models.BooleanField(default=False)
#     auto_send_reminders = models.BooleanField(default=True)
#     reminder_days_before_due = models.PositiveIntegerField(default=3)
#     auto_backup_enabled = models.BooleanField(default=True)
    
#     class Meta:
#         verbose_name = 'Finance Settings'
#         verbose_name_plural = 'Finance Settings'
        
#     def __str__(self):
#         return f'Finance Settings - {self.company_name}'


# class FiscalYear(TenantBaseModel):
#     """Enhanced fiscal year definition and status"""
    
#     STATUS_CHOICES = [
#         ('OPEN', 'Open'),
#         ('CLOSED', 'Closed'),
#         ('LOCKED', 'Locked'),
#     ]
    
#     year = models.IntegerField()
#     start_date = models.DateField()
#     end_date = models.DateField()
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
#     closed_date = models.DateTimeField(null=True, blank=True)
#     closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
#     # Financial Summary (calculated when closed)
#     total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     net_income = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Balance Sheet Summary
#     total_assets = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_liabilities = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_equity = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     class Meta:
#         ordering = ['-year']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'year'],
#                 name='unique_tenant_fiscal_year'
#             ),
#         ]
        
#     def __str__(self):
#         return f'FY {self.year} ({self.start_date} to {self.end_date})'
    
#     @property
#     def is_current(self):
#         """Check if this is the current fiscal year"""
#         today = date.today()
#         return self.start_date <= today <= self.end_date
    
#     def close_fiscal_year(self, user):
#         """Close the fiscal year"""
#         if self.status == 'CLOSED':
#             raise ValidationError('Fiscal year is already closed')
        
#         # Calculate financial summary
#         self.calculate_financial_summary()
        
#         # Create closing entries
#         self.create_closing_entries(user)
        
#         self.status = 'CLOSED'
#         self.closed_date = timezone.now()
#         self.closed_by = user
#         self.save()
    
#     def calculate_financial_summary(self):
#         """Calculate fiscal year financial summary"""
#         from .services import FinancialReportingService
        
#         reporting_service = FinancialReportingService(self.tenant)
#         summary = reporting_service.get_fiscal_year_summary(self.year)
        
#         self.total_revenue = summary.get('total_revenue', Decimal('0.00'))
#         self.total_expenses = summary.get('total_expenses', Decimal('0.00'))
#         self.total_cogs = summary.get('total_cogs', Decimal('0.00'))
#         self.gross_profit = self.total_revenue - self.total_cogs
#         self.net_income = self.gross_profit - self.total_expenses
#         self.total_assets = summary.get('total_assets', Decimal('0.00'))
#         self.total_liabilities = summary.get('total_liabilities', Decimal('0.00'))
#         self.total_equity = summary.get('total_equity', Decimal('0.00'))
    
#     def create_closing_entries(self, user):
#         """Create year-end closing entries"""
#         from .services import JournalEntryService
        
#         service = JournalEntryService(self.tenant)
#         service.create_year_end_closing_entries(self, user)


# class FinancialPeriod(TenantBaseModel):
#     """Enhanced financial periods for better reporting"""
    
#     PERIOD_TYPES = [
#         ('MONTH', 'Monthly'),
#         ('QUARTER', 'Quarterly'),
#         ('YEAR', 'Yearly'),
#         ('CUSTOM', 'Custom'),
#     ]
    
#     PERIOD_STATUS = [
#         ('OPEN', 'Open'),
#         ('CLOSED', 'Closed'),
#         ('LOCKED', 'Locked'),
#     ]
    
#     # Period Information
#     name = models.CharField(max_length=100)
#     period_type = models.CharField(max_length=10, choices=PERIOD_TYPES)
#     fiscal_year = models.ForeignKey(
#         FiscalYear,
#         on_delete=models.CASCADE,
#         related_name='periods'
#     )
#     start_date = models.DateField()
#     end_date = models.DateField()
    
#     # Status
#     status = models.CharField(max_length=10, choices=PERIOD_STATUS, default='OPEN')
    
#     # Closing Information
#     closed_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='closed_periods'
#     )
#     closed_date = models.DateTimeField(null=True, blank=True)
    
#     # Budget Information
#     budgeted_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     budgeted_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     actual_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     class Meta:
#         ordering = ['-start_date']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'start_date', 'end_date'],
#                 name='unique_tenant_period'
#             ),
#         ]
        
#     def __str__(self):
#         return f"{self.name} ({self.start_date} to {self.end_date})"
    
#     @property
#     def variance_revenue(self):
#         """Revenue variance (actual vs budget)"""
#         return self.actual_revenue - self.budgeted_revenue
    
#     @property
#     def variance_expenses(self):
#         """Expense variance (actual vs budget)"""
#         return self.actual_expenses - self.budgeted_expenses


# # ============================================================================
# # MULTI-CURRENCY SUPPORT
# # ============================================================================

# class Currency(TenantBaseModel):
#     """Currency definitions with exchange rates"""
    
#     code = models.CharField(max_length=3, unique=True)
#     name = models.CharField(max_length=100)
#     symbol = models.CharField(max_length=10)
#     decimal_places = models.IntegerField(default=2)
#     is_active = models.BooleanField(default=True)
#     is_base_currency = models.BooleanField(default=False)
    
#     class Meta:
#         ordering = ['code']
#         verbose_name_plural = 'Currencies'
        
#     def __str__(self):
#         return f'{self.code} - {self.name}'


# class ExchangeRate(TenantBaseModel):
#     """Exchange rates for multi-currency support"""
    
#     from_currency = models.ForeignKey(
#         Currency,
#         on_delete=models.CASCADE,
#         related_name='rates_from'
#     )
#     to_currency = models.ForeignKey(
#         Currency,
#         on_delete=models.CASCADE,
#         related_name='rates_to'
#     )
#     rate = models.DecimalField(max_digits=12, decimal_places=6)
#     effective_date = models.DateField()
#     created_date = models.DateTimeField(auto_now_add=True)
#     source = models.CharField(max_length=50, blank=True)  # API source like 'xe.com', 'manual'
    
#     class Meta:
#         ordering = ['-effective_date']
#         indexes = [
#             models.Index(fields=['from_currency', 'to_currency', 'effective_date']),
#         ]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'from_currency', 'to_currency', 'effective_date'],
#                 name='unique_tenant_exchange_rate'
#             ),
#         ]
        
#     def __str__(self):
#         return f'{self.from_currency.code} to {self.to_currency.code}: {self.rate}'
    
#     @classmethod
#     def get_rate(cls, tenant, from_currency, to_currency, as_of_date=None):
#         """Get exchange rate for currency conversion"""
#         if not as_of_date:
#             as_of_date = date.today()
        
#         rate = cls.objects.filter(
#             tenant=tenant,
#             from_currency=from_currency,
#             to_currency=to_currency,
#             effective_date__lte=as_of_date
#         ).first()
        
#         if rate:
#             return rate.rate
        
#         # Try inverse rate
#         inverse_rate = cls.objects.filter(
#             tenant=tenant,
#             from_currency=to_currency,
#             to_currency=from_currency,
#             effective_date__lte=as_of_date
#         ).first()
        
#         if inverse_rate:
#             return Decimal('1.000000') / inverse_rate.rate
        
#         return Decimal('1.000000')  # Default to 1:1 if no rate found


# # ============================================================================
# # ENHANCED CHART OF ACCOUNTS
# # ============================================================================

# class AccountCategory(TenantBaseModel):
#     """Account categories for better organization"""
    
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
#     account_type = models.CharField(max_length=30)
#     sort_order = models.IntegerField(default=0)
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['account_type', 'sort_order', 'name']
#         verbose_name_plural = 'Account Categories'
        
#     def __str__(self):
#         return self.name


# class Account(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced Chart of Accounts with multi-currency and inventory integration"""
    
#     ACCOUNT_TYPES = [
#         # Assets
#         ('ASSET', 'Asset'),
#         ('CURRENT_ASSET', 'Current Asset'),
#         ('FIXED_ASSET', 'Fixed Asset'),
#         ('OTHER_ASSET', 'Other Asset'),
        
#         # Liabilities
#         ('LIABILITY', 'Liability'),
#         ('CURRENT_LIABILITY', 'Current Liability'),
#         ('LONG_TERM_LIABILITY', 'Long Term Liability'),
        
#         # Equity
#         ('EQUITY', 'Equity'),
#         ('RETAINED_EARNINGS', 'Retained Earnings'),
        
#         # Revenue
#         ('REVENUE', 'Revenue'),
#         ('OTHER_INCOME', 'Other Income'),
        
#         # Expenses
#         ('EXPENSE', 'Expense'),
#         ('COST_OF_GOODS_SOLD', 'Cost of Goods Sold'),
#         ('OTHER_EXPENSE', 'Other Expense'),
#     ]
    
#     NORMAL_BALANCE_CHOICES = [
#         ('DEBIT', 'Debit'),
#         ('CREDIT', 'Credit'),
#     ]
    
#     # Account Identification
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
    
#     # Account Classification
#     account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPES)
#     category = models.ForeignKey(
#         AccountCategory,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
#     parent_account = models.ForeignKey(
#         'self',
#         on_delete=models.CASCADE,
#         null=True,
#         blank=True,
#         related_name='sub_accounts'
#     )
#     level = models.PositiveSmallIntegerField(default=0)
    
#     # Balance Information
#     normal_balance = models.CharField(max_length=10, choices=NORMAL_BALANCE_CHOICES)
#     opening_balance = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
#     current_balance = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
#     opening_balance_date = models.DateField(null=True, blank=True)
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(
#         Currency,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True
#     )
    
#     # Account Settings
#     is_active = models.BooleanField(default=True)
#     is_system_account = models.BooleanField(default=False)
#     is_bank_account = models.BooleanField(default=False)
#     is_cash_account = models.BooleanField(default=False)
#     allow_manual_entries = models.BooleanField(default=True)
#     require_reconciliation = models.BooleanField(default=False)
    
#     # Bank Account Information
#     bank_name = models.CharField(max_length=100, blank=True)
#     bank_account_number = models.CharField(max_length=50, blank=True)
#     bank_routing_number = models.CharField(max_length=20, blank=True)
#     bank_swift_code = models.CharField(max_length=20, blank=True)
    
#     # Tax Settings
#     default_tax_code = models.ForeignKey(
#         'TaxCode',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
#     is_taxable = models.BooleanField(default=False)
#     tax_line = models.CharField(max_length=100, blank=True)
    
#     # Inventory Integration
#     track_inventory = models.BooleanField(default=False)
#     inventory_valuation_method = models.CharField(max_length=20, blank=True)
    
#     # Budget & Controls
#     budget_amount = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
    
#     # Tracking
#     created_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='created_accounts'
#     )
    
#     class Meta:
#         ordering = ['code']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'code'],
#                 name='unique_tenant_account_code'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'account_type', 'is_active']),
#             models.Index(fields=['tenant', 'parent_account']),
#             models.Index(fields=['tenant', 'is_bank_account']),
#         ]
        
#     def __str__(self):
#         return f'{self.code} - {self.name}'
    
#     def save(self, *args, **kwargs):
#         # Auto-calculate level based on parent
#         if self.parent_account:
#             self.level = self.parent_account.level + 1
#         else:
#             self.level = 0
        
#         # Set normal balance based on account type
#         if not self.normal_balance:
#             if self.account_type in ['ASSET', 'EXPENSE', 'COST_OF_GOODS_SOLD']:
#                 self.normal_balance = 'DEBIT'
#             else:
#                 self.normal_balance = 'CREDIT'
        
#         super().save(*args, **kwargs)
    
#     def get_balance(self, as_of_date=None, currency=None):
#         """Get account balance as of specific date with currency conversion"""
#         from .services import AccountingService
        
#         service = AccountingService(self.tenant)
#         return service.get_account_balance(self.id, as_of_date, currency)
    
#     def get_balance_sheet_section(self):
#         """Get balance sheet section for this account"""
#         section_mapping = {
#             'CURRENT_ASSET': 'Current Assets',
#             'FIXED_ASSET': 'Fixed Assets',
#             'OTHER_ASSET': 'Other Assets',
#             'CURRENT_LIABILITY': 'Current Liabilities',
#             'LONG_TERM_LIABILITY': 'Long Term Liabilities',
#             'EQUITY': 'Equity',
#             'RETAINED_EARNINGS': 'Equity',
#         }
#         return section_mapping.get(self.account_type)
    
#     def is_balance_sheet_account(self):
#         """Check if this is a balance sheet account"""
#         balance_sheet_types = [
#             'ASSET', 'CURRENT_ASSET', 'FIXED_ASSET', 'OTHER_ASSET',
#             'LIABILITY', 'CURRENT_LIABILITY', 'LONG_TERM_LIABILITY',
#             'EQUITY', 'RETAINED_EARNINGS'
#         ]
#         return self.account_type in balance_sheet_types


# # ============================================================================
# # ENHANCED TAX MANAGEMENT
# # ============================================================================

# class TaxCode(TenantBaseModel):
#     """Enhanced tax code definitions with multi-jurisdictional support"""
    
#     TAX_TYPE_CHOICES = [
#         ('SALES_TAX', 'Sales Tax'),
#         ('VAT', 'Value Added Tax'),
#         ('GST', 'Goods and Services Tax'),
#         ('EXCISE', 'Excise Tax'),
#         ('WITHHOLDING', 'Withholding Tax'),
#         ('IMPORT_DUTY', 'Import Duty'),
#         ('OTHER', 'Other Tax'),
#     ]
    
#     CALCULATION_METHOD_CHOICES = [
#         ('PERCENTAGE', 'Percentage of Amount'),
#         ('FIXED', 'Fixed Amount'),
#         ('COMPOUND', 'Compound Tax'),
#     ]
    
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
#     tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES)
    
#     # Tax Calculation
#     calculation_method = models.CharField(
#         max_length=20,
#         choices=CALCULATION_METHOD_CHOICES,
#         default='PERCENTAGE'
#     )
#     rate = models.DecimalField(max_digits=8, decimal_places=4)
#     fixed_amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
    
#     # Jurisdictional Information
#     country = models.CharField(max_length=2, blank=True)
#     state_province = models.CharField(max_length=100, blank=True)
#     city = models.CharField(max_length=100, blank=True)
    
#     # Tax Accounts
#     tax_collected_account = models.ForeignKey(
#         Account,
#         on_delete=models.PROTECT,
#         related_name='tax_codes_collected'
#     )
#     tax_paid_account = models.ForeignKey(
#         Account,
#         on_delete=models.PROTECT,
#         related_name='tax_codes_paid',
#         null=True,
#         blank=True
#     )
    
#     # Settings
#     is_active = models.BooleanField(default=True)
#     is_compound = models.BooleanField(default=False)
#     is_recoverable = models.BooleanField(default=True)
#     apply_to_shipping = models.BooleanField(default=False)
    
#     # Effective Dates
#     effective_from = models.DateField(null=True, blank=True)
#     effective_to = models.DateField(null=True, blank=True)
    
#     # Reporting
#     tax_authority = models.CharField(max_length=200, blank=True)
#     reporting_code = models.CharField(max_length=50, blank=True)
    
#     class Meta:
#         ordering = ['code']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'code'],
#                 name='unique_tenant_tax_code'
#             ),
#         ]
        
#     def __str__(self):
#         return f'{self.code} - {self.name} ({self.rate}%)'
    
#     def calculate_tax(self, amount, include_shipping=False):
#         """Calculate tax amount for given base amount"""
#         if not self.is_active:
#             return Decimal('0.00')
        
#         if self.calculation_method == 'PERCENTAGE':
#             return amount * (self.rate / Decimal('100'))
#         elif self.calculation_method == 'FIXED':
#             return self.fixed_amount or Decimal('0.00')
        
#         return Decimal('0.00')
    
#     def is_effective(self, check_date=None):
#         """Check if tax code is effective on given date"""
#         if not check_date:
#             check_date = date.today()
        
#         if self.effective_from and check_date < self.effective_from:
#             return False
        
#         if self.effective_to and check_date > self.effective_to:
#             return False
        
#         return True


# class TaxGroup(TenantBaseModel):
#     """Group multiple tax codes for complex tax scenarios"""
    
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
#     tax_codes = models.ManyToManyField(TaxCode, through='TaxGroupItem')
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['name']
        
#     def __str__(self):
#         return self.name
    
#     def calculate_total_tax(self, amount):
#         """Calculate total tax from all codes in group"""
#         total_tax = Decimal('0.00')
        
#         for item in self.tax_group_items.filter(is_active=True).order_by('sequence'):
#             tax_code = item.tax_code
#             if item.apply_to == 'SUBTOTAL':
#                 base_amount = amount
#             else:  # SUBTOTAL_PLUS_TAX
#                 base_amount = amount + total_tax
            
#             tax_amount = tax_code.calculate_tax(base_amount)
#             total_tax += tax_amount
        
#         return total_tax


# class TaxGroupItem(TenantBaseModel):
#     """Individual tax codes within a tax group"""
    
#     APPLY_TO_CHOICES = [
#         ('SUBTOTAL', 'Apply to Subtotal Only'),
#         ('SUBTOTAL_PLUS_TAX', 'Apply to Subtotal Plus Previous Taxes'),
#     ]
    
#     tax_group = models.ForeignKey(TaxGroup, on_delete=models.CASCADE, related_name='tax_group_items')
#     tax_code = models.ForeignKey(TaxCode, on_delete=models.CASCADE)
#     sequence = models.IntegerField(default=1)
#     apply_to = models.CharField(max_length=20, choices=APPLY_TO_CHOICES, default='SUBTOTAL')
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['tax_group', 'sequence']


# # ============================================================================
# # ENHANCED JOURNAL ENTRIES & TRANSACTIONS
# # ============================================================================

# class JournalEntry(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced journal entries with multi-currency and source tracking"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('POSTED', 'Posted'),
#         ('REVERSED', 'Reversed'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#     ]
    
#     ENTRY_TYPE_CHOICES = [
#         ('MANUAL', 'Manual Entry'),
#         ('AUTOMATIC', 'System Generated'),
#         ('INVOICE', 'Sales Invoice'),
#         ('BILL', 'Purchase Bill'),
#         ('PAYMENT', 'Payment'),
#         ('RECEIPT', 'Receipt'),
#         ('INVENTORY', 'Inventory Adjustment'),
#         ('COGS', 'Cost of Goods Sold'),
#         ('DEPRECIATION', 'Depreciation'),
#         ('ADJUSTMENT', 'Adjusting Entry'),
#         ('CLOSING', 'Closing Entry'),
#         ('REVERSAL', 'Reversal Entry'),
#         ('BANK_RECONCILIATION', 'Bank Reconciliation'),
#         ('CURRENCY_REVALUATION', 'Currency Revaluation'),
#     ]
    
#     # Entry Identification
#     entry_number = models.CharField(max_length=50)
#     reference_number = models.CharField(max_length=100, blank=True)
#     entry_date = models.DateField()
    
#     # Entry Classification
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     entry_type = models.CharField(max_length=25, choices=ENTRY_TYPE_CHOICES, default='MANUAL')
    
#     # Description & Notes
#     description = models.TextField()
#     notes = models.TextField(blank=True)
    
#     # Source Information
#     source_document_type = models.CharField(max_length=50, blank=True)
#     source_document_id = models.IntegerField(null=True, blank=True)
#     source_document_number = models.CharField(max_length=100, blank=True)
    
#     # Financial Information
#     total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
#     base_currency_total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Approval & Control
#     created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_journal_entries')
#     posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journal_entries')
#     posted_date = models.DateTimeField(null=True, blank=True)
#     approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_journal_entries')
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     # Reversal Information
#     reversed_entry = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
#     reversal_reason = models.TextField(blank=True)
    
#     # Financial Period
#     financial_period = models.ForeignKey(
#         FinancialPeriod,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
    
#     # Attachments
#     attachments = models.JSONField(default=list, blank=True)
    
#     class Meta:
#         ordering = ['-entry_date', '-entry_number']
#         verbose_name = 'Journal Entry'
#         verbose_name_plural = 'Journal Entries'
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'entry_number'],
#                 name='unique_tenant_journal_entry'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'entry_date', 'status']),
#             models.Index(fields=['tenant', 'entry_type', 'status']),
#             models.Index(fields=['tenant', 'source_document_type', 'source_document_id']),
#         ]
        
#     def __str__(self):
#         return f'{self.entry_number} - {self.description[:50]}'
    
#     def save(self, *args, **kwargs):
#         if not self.entry_number:
#             self.entry_number = self.generate_entry_number()
#         super().save(*args, **kwargs)
    
#     def generate_entry_number(self):
#         """Generate unique journal entry number"""
#         return generate_code('JE', self.tenant_id)
    
#     def clean(self):
#         """Validate journal entry"""
#         if self.status == 'POSTED':
#             if abs(self.total_debit - self.total_credit) > Decimal('0.01'):
#                 raise ValidationError('Journal entry must be balanced (debits = credits)')
            
#             if abs(self.base_currency_total_debit - self.base_currency_total_credit) > Decimal('0.01'):
#                 raise ValidationError('Base currency amounts must be balanced')
    
#     @transaction.atomic
#     def post_entry(self, user):
#         """Post the journal entry"""
#         if self.status == 'POSTED':
#             raise ValidationError('Journal entry is already posted')
        
#         # Validate that entry is balanced
#         self.calculate_totals()
#         if abs(self.total_debit - self.total_credit) > Decimal('0.01'):
#             raise ValidationError('Journal entry must be balanced')
        
#         # Update account balances
#         for line in self.journal_lines.all():
#             line.update_account_balance()
        
#         self.status = 'POSTED'
#         self.posted_by = user
#         self.posted_date = timezone.now()
#         self.save()
        
#         # Update inventory cost layers if applicable
#         if self.entry_type == 'INVENTORY':
#             self.update_inventory_cost_layers()
    
#     def calculate_totals(self):
#         """Calculate and update total debits and credits"""
#         totals = self.journal_lines.aggregate(
#             total_debit=models.Sum('debit_amount'),
#             total_credit=models.Sum('credit_amount'),
#             base_total_debit=models.Sum('base_currency_debit_amount'),
#             base_total_credit=models.Sum('base_currency_credit_amount')
#         )
        
#         self.total_debit = totals['total_debit'] or Decimal('0.00')
#         self.total_credit = totals['total_credit'] or Decimal('0.00')
#         self.base_currency_total_debit = totals['base_total_debit'] or Decimal('0.00')
#         self.base_currency_total_credit = totals['base_total_credit'] or Decimal('0.00')
        
#         self.save(update_fields=[
#             'total_debit', 'total_credit',
#             'base_currency_total_debit', 'base_currency_total_credit'
#         ])
    
#     def update_inventory_cost_layers(self):
#         """Update inventory cost layers for inventory-related entries"""
#         from .services import InventoryCostingService
        
#         service = InventoryCostingService(self.tenant)
#         service.process_journal_entry(self)
    
#     @transaction.atomic
#     def reverse_entry(self, user, reason):
#         """Create a reversal entry"""
#         if self.status != 'POSTED':
#             raise ValidationError('Only posted entries can be reversed')
        
#         # Create reversal entry
#         reversal = JournalEntry.objects.create(
#             tenant=self.tenant,
#             entry_date=date.today(),
#             entry_type='REVERSAL',
#             description=f'Reversal of {self.entry_number}',
#             notes=reason,
#             currency=self.currency,
#             exchange_rate=self.exchange_rate,
#             created_by=user,
#             reversed_entry=self
#         )
        
#         # Create reversal lines (swap debits and credits)
#         for line in self.journal_lines.all():
#             JournalEntryLine.objects.create(
#                 tenant=self.tenant,
#                 journal_entry=reversal,
#                 account=line.account,
#                 description=f'Reversal: {line.description}',
#                 debit_amount=line.credit_amount,
#                 credit_amount=line.debit_amount,
#                 base_currency_debit_amount=line.base_currency_credit_amount,
#                 base_currency_credit_amount=line.base_currency_debit_amount,
#                 line_number=line.line_number,
#                 customer=line.customer,
#                 vendor=line.vendor,
#                 product=line.product,
#                 project=line.project,
#                 department=line.department,
#                 location=line.location
#             )
        
#         # Post reversal entry
#         reversal.calculate_totals()
#         reversal.post_entry(user)
        
#         # Mark original as reversed
#         self.status = 'REVERSED'
#         self.save()
        
#         return reversal


# class JournalEntryLine(TenantBaseModel):
#     """Enhanced journal entry lines with multi-currency and tracking"""
    
#     journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.CASCADE,
#         related_name='journal_lines'
#     )
#     line_number = models.IntegerField()
    
#     # Account Information
#     account = models.ForeignKey(Account, on_delete=models.PROTECT)
    
#     # Transaction Details
#     description = models.TextField()
#     debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Multi-Currency Support
#     base_currency_debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Additional Tracking
#     customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
#     vendor = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True)
#     product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
#     project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
#     department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
#     location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
    
#     # Tax Information
#     tax_code = models.ForeignKey(TaxCode, on_delete=models.SET_NULL, null=True, blank=True)
#     tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Quantity (for inventory items)
#     quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
#     unit_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
#     class Meta:
#         ordering = ['journal_entry', 'line_number']
        
#     def __str__(self):
#         return f'{self.journal_entry.entry_number} - Line {self.line_number}'
    
#     def save(self, *args, **kwargs):
#         # Calculate base currency amounts if not provided
#         if not self.base_currency_debit_amount and self.debit_amount:
#             self.base_currency_debit_amount = self.debit_amount * self.journal_entry.exchange_rate
        
#         if not self.base_currency_credit_amount and self.credit_amount:
#             self.base_currency_credit_amount = self.credit_amount * self.journal_entry.exchange_rate
        
#         super().save(*args, **kwargs)
    
#     def clean(self):
#         """Validate journal entry line"""
#         if self.debit_amount and self.credit_amount:
#             raise ValidationError('A line cannot have both debit and credit amounts')
#         if not self.debit_amount and not self.credit_amount:
#             raise ValidationError('A line must have either debit or credit amount')
    
#     @property
#     def amount(self):
#         """Get the line amount (debit or credit)"""
#         return self.debit_amount if self.debit_amount else self.credit_amount
    
#     @property
#     def base_amount(self):
#         """Get the base currency amount"""
#         return self.base_currency_debit_amount if self.base_currency_debit_amount else self.base_currency_credit_amount
    
#     @property
#     def is_debit(self):
#         """Check if this is a debit entry"""
#         return bool(self.debit_amount)
    
#     def update_account_balance(self):
#         """Update the account balance when entry is posted"""
#         if self.is_debit:
#             if self.account.normal_balance == 'DEBIT':
#                 self.account.current_balance += self.base_currency_debit_amount
#             else:
#                 self.account.current_balance -= self.base_currency_debit_amount
#         else:
#             if self.account.normal_balance == 'CREDIT':
#                 self.account.current_balance += self.base_currency_credit_amount
#             else:
#                 self.account.current_balance -= self.base_currency_credit_amount
        
#         self.account.save(update_fields=['current_balance'])


# # ============================================================================
# # INVENTORY COST LAYERS & COGS AUTOMATION
# # ============================================================================

# class InventoryCostLayer(TenantBaseModel):
#     """Enhanced inventory cost layers for accurate COGS calculation"""
    
#     COST_LAYER_TYPES = [
#         ('PURCHASE', 'Purchase'),
#         ('PRODUCTION', 'Production'),
#         ('ADJUSTMENT', 'Adjustment'),
#         ('OPENING_BALANCE', 'Opening Balance'),
#         ('TRANSFER_IN', 'Transfer In'),
#         ('LANDED_COST', 'Landed Cost'),
#     ]
    
#     # Product & Location
#     product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cost_layers')
#     warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='cost_layers')
    
#     # Cost Information
#     layer_type = models.CharField(max_length=20, choices=COST_LAYER_TYPES)
#     quantity = models.DecimalField(max_digits=15, decimal_places=4)
#     unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
#     total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
#     base_currency_unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
#     base_currency_total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Source Information
#     source_document_type = models.CharField(max_length=50)
#     source_document_id = models.IntegerField()
#     source_document_number = models.CharField(max_length=100, blank=True)
    
#     # Dates
#     acquisition_date = models.DateField()
#     created_date = models.DateTimeField(auto_now_add=True)
    
#     # Status
#     quantity_remaining = models.DecimalField(max_digits=15, decimal_places=4)
#     is_fully_consumed = models.BooleanField(default=False)
    
#     # Landed Costs
#     landed_cost_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     allocated_landed_costs = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Journal Entry Reference
#     journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
    
#     class Meta:
#         ordering = ['acquisition_date', 'created_date']  # FIFO by default
#         indexes = [
#             models.Index(fields=['tenant', 'product', 'warehouse', 'is_fully_consumed']),
#             models.Index(fields=['tenant', 'acquisition_date']),
#             models.Index(fields=['tenant', 'source_document_type', 'source_document_id']),
#         ]
        
#     def __str__(self):
#         return f"{self.product.name} - {self.quantity} @ {self.unit_cost} ({self.warehouse.name})"
    
#     def save(self, *args, **kwargs):
#         # Calculate totals
#         self.total_cost = self.quantity * self.unit_cost
#         self.base_currency_total_cost = self.base_currency_unit_cost * self.quantity
        
#         # Initialize quantity remaining
#         if not self.pk:  # New record
#             self.quantity_remaining = self.quantity
        
#         super().save(*args, **kwargs)
    
#     def consume_quantity(self, quantity_consumed, cogs_journal_entry=None):
#         """Consume quantity from this cost layer"""
#         if quantity_consumed > self.quantity_remaining:
#             raise ValidationError('Cannot consume more than remaining quantity')
        
#         # Calculate cost for consumed quantity
#         consumed_cost = (quantity_consumed / self.quantity) * self.base_currency_total_cost
        
#         # Update remaining quantity
#         self.quantity_remaining -= quantity_consumed
#         if self.quantity_remaining <= Decimal('0.0001'):  # Essentially zero
#             self.is_fully_consumed = True
        
#         self.save()
        
#         # Create cost consumption record
#         InventoryCostConsumption.objects.create(
#             tenant=self.tenant,
#             cost_layer=self,
#             quantity_consumed=quantity_consumed,
#             unit_cost=self.base_currency_unit_cost,
#             total_cost=consumed_cost,
#             consumption_date=date.today(),
#             cogs_journal_entry=cogs_journal_entry
#         )
        
#         return consumed_cost
    
#     @property
#     def effective_unit_cost(self):
#         """Unit cost including allocated landed costs"""
#         if self.quantity > 0:
#             return (self.base_currency_total_cost + self.allocated_landed_costs) / self.quantity
#         return self.base_currency_unit_cost


# class InventoryCostConsumption(TenantBaseModel):
#     """Track consumption of inventory cost layers"""
    
#     cost_layer = models.ForeignKey(
#         InventoryCostLayer,
#         on_delete=models.CASCADE,
#         related_name='consumptions'
#     )
#     quantity_consumed = models.DecimalField(max_digits=15, decimal_places=4)
#     unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
#     total_cost = models.DecimalField(max_digits=15, decimal_places=2)
#     consumption_date = models.DateField()
    
#     # Source of consumption
#     source_document_type = models.CharField(max_length=50, blank=True)
#     source_document_id = models.IntegerField(null=True, blank=True)
    
#     # COGS Journal Entry
#     cogs_journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
    
#     class Meta:
#         ordering = ['-consumption_date']
        
#     def __str__(self):
#         return f"Consumption: {self.quantity_consumed} @ {self.unit_cost}"


# class LandedCost(TenantBaseModel):
#     """Landed costs allocation for inventory"""
    
#     ALLOCATION_METHODS = [
#         ('QUANTITY', 'By Quantity'),
#         ('WEIGHT', 'By Weight'),
#         ('VALUE', 'By Value'),
#         ('VOLUME', 'By Volume'),
#         ('MANUAL', 'Manual Allocation'),
#     ]
    
#     # Basic Information
#     reference_number = models.CharField(max_length=50)
#     description = models.TextField()
#     total_landed_cost = models.DecimalField(max_digits=15, decimal_places=2)
#     allocation_method = models.CharField(max_length=20, choices=ALLOCATION_METHODS)
    
#     # Source Document
#     source_document_type = models.CharField(max_length=50)
#     source_document_id = models.IntegerField()
#     source_purchase_order = models.ForeignKey(
#         PurchaseOrder,
#         on_delete=models.CASCADE,
#         null=True,
#         blank=True
#     )
    
#     # Status
#     is_allocated = models.BooleanField(default=False)
#     allocated_date = models.DateTimeField(null=True, blank=True)
#     allocated_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
    
#     class Meta:
#         ordering = ['-created_at']
        
#     def __str__(self):
#         return f"{self.reference_number} - {self.total_landed_cost}"
    
#     def allocate_to_products(self):
#         """Allocate landed costs to products"""
#         from .services import LandedCostService
        
#         service = LandedCostService(self.tenant)
#         service.allocate_landed_costs(self)


# class LandedCostAllocation(TenantBaseModel):
#     """Individual allocations of landed costs to products"""
    
#     landed_cost = models.ForeignKey(
#         LandedCost,
#         on_delete=models.CASCADE,
#         related_name='allocations'
#     )
#     cost_layer = models.ForeignKey(
#         InventoryCostLayer,
#         on_delete=models.CASCADE,
#         related_name='landed_cost_allocations'
#     )
#     allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
#     allocation_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
#     class Meta:
#         ordering = ['landed_cost', 'cost_layer']
        
#     def __str__(self):
#         return f"{self.landed_cost.reference_number} -> {self.cost_layer.product.name}: {self.allocated_amount}"


# # ============================================================================
# # BANK RECONCILIATION
# # ============================================================================
# class BankAccount(TenantBaseModel):
#     """Enhanced bank account model combining features from both approaches"""
    
#     # Core Account Relationship
#     account = models.OneToOneField(
#         Account, 
#         on_delete=models.CASCADE, 
#         related_name='bank_details',
#         limit_choices_to={'is_bank_account': True}
#     )
    
#     # Bank Information
#     bank_name = models.CharField(max_length=200)
#     account_number = models.CharField(max_length=50)
#     account_type = models.CharField(max_length=20, choices=[
#         ('CHECKING', 'Checking'),
#         ('SAVINGS', 'Savings'),
#         ('MONEY_MARKET', 'Money Market'),
#         ('CREDIT_CARD', 'Credit Card'),
#         ('LINE_OF_CREDIT', 'Line of Credit'),
#     ])
    
#     # Routing Information
#     routing_number = models.CharField(max_length=20, blank=True)
#     swift_code = models.CharField(max_length=20, blank=True)
#     iban = models.CharField(max_length=34, blank=True)
    
#     # Bank Feed Integration
#     enable_bank_feeds = models.BooleanField(default=False)
#     bank_feed_id = models.CharField(max_length=100, blank=True)
#     last_feed_sync = models.DateTimeField(null=True, blank=True)
    
#     # Statement Import Settings
#     statement_import_format = models.CharField(max_length=20, choices=[
#         ('CSV', 'CSV File'),
#         ('QFX', 'Quicken QFX'),
#         ('OFX', 'Open Financial Exchange'),
#         ('MT940', 'SWIFT MT940'),
#         ('BAI', 'BAI Format'),
#         ('BANK_FEED', 'Bank Feed'),
#     ], default='CSV')
    
#     # Reconciliation Settings
#     auto_reconcile = models.BooleanField(default=False)
#     reconciliation_tolerance = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         default=Decimal('0.01')
#     )
    
#     # Balance Tracking
#     current_balance = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         default=Decimal('0.00')
#     )
#     last_reconciled_balance = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         default=Decimal('0.00')
#     )
#     last_reconciliation_date = models.DateField(null=True, blank=True)
    
#     class Meta:
#         db_table = 'finance_bank_accounts'
#         verbose_name = 'Bank Account'
#         verbose_name_plural = 'Bank Accounts'
#         ordering = ['bank_name', 'account_number']
        
#     def __str__(self):
#         return f"{self.bank_name} - {self.account_number}"


# class BankStatement(TenantBaseModel):
#     """Enhanced bank statement model"""
    
#     bank_account = models.ForeignKey(
#         BankAccount, 
#         on_delete=models.CASCADE, 
#         related_name='statements'
#     )
    
#     # Statement Period
#     statement_date = models.DateField()
#     statement_period_start = models.DateField()
#     statement_period_end = models.DateField()
    
#     # Statement Balances
#     opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
#     closing_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Import Information
#     import_date = models.DateTimeField(auto_now_add=True)
#     imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#     import_file_name = models.CharField(max_length=255, blank=True)
#     import_format = models.CharField(max_length=20)
#     imported_from = models.CharField(max_length=100, blank=True)  # Bank feed, manual, etc.
    
#     # Processing Status
#     processing_status = models.CharField(max_length=20, choices=[
#         ('IMPORTED', 'Imported'),
#         ('PROCESSING', 'Processing'),
#         ('PROCESSED', 'Processed'),
#         ('RECONCILED', 'Reconciled'),
#         ('ERROR', 'Error'),
#     ], default='IMPORTED')
    
#     # Transaction Counts
#     total_transactions = models.IntegerField(default=0)
#     matched_transactions = models.IntegerField(default=0)
#     unmatched_transactions = models.IntegerField(default=0)
    
#     # Reconciliation Status
#     is_reconciled = models.BooleanField(default=False)
#     reconciled_date = models.DateTimeField(null=True, blank=True)
#     econciled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reconciled_statements')
#     is_reconciled = models.BooleanField(default=False)
#     reconciled_date = models.DateTimeField(null=True, blank=True)
#     reconciled_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='reconciled_statements'
#     )
    
#     class Meta:
#         db_table = 'finance_bank_statements'
#         ordering = ['-statement_date']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'bank_account', 'statement_date'],
#                 name='unique_bank_statement_per_date'
#             ),
#         ]
        
#     def __str__(self):
#         return f"{self.bank_account.bank_name} - {self.statement_date}"


# class BankTransaction(TenantBaseModel):
#     """Enhanced bank transaction model with comprehensive features"""
    
#     TRANSACTION_TYPES = [
#         ('DEPOSIT', 'Deposit'),
#         ('WITHDRAWAL', 'Withdrawal'),
#         ('TRANSFER', 'Transfer'),
#         ('FEE', 'Bank Fee'),
#         ('INTEREST', 'Interest'),
#         ('CHECK', 'Check'),
#         ('ATM', 'ATM Transaction'),
#         ('DEBIT_CARD', 'Debit Card'),
#         ('CREDIT_CARD', 'Credit Card'),
#         ('ACH', 'ACH Transaction'),
#         ('WIRE', 'Wire Transfer'),
#         ('CARD', 'Card Transaction'),
#         ('OTHER', 'Other'),
#     ]
    
#     RECONCILIATION_STATUS_CHOICES = [
#         ('UNMATCHED', 'Unmatched'),
#         ('MATCHED', 'Matched'),
#         ('MANUAL_MATCH', 'Manually Matched'),
#         ('AUTO_MATCH', 'Auto Matched'),
#         ('EXCLUDED', 'Excluded'),
#         ('PENDING', 'Pending Review'),
#         ('RECONCILED', 'Reconciled'),
#     ]
    
#     bank_statement = models.ForeignKey(
#         BankStatement, 
#         on_delete=models.CASCADE, 
#         related_name='bank_transactions'
#     )
    
#     # Transaction Details
#     transaction_date = models.DateField()
#     post_date = models.DateField(null=True, blank=True)
#     transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
#     amount = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Description Information
#     description = models.TextField()
#     memo = models.CharField(max_length=255, blank=True)
#     reference_number = models.CharField(max_length=100, blank=True)
#     check_number = models.CharField(max_length=50, blank=True)
    
#     # Payee/Bank Information
#     payee = models.CharField(max_length=200, blank=True)
#     bank_transaction_id = models.CharField(max_length=100, blank=True)
    
#     # Running Balance
#     running_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
#     # Reconciliation Status
#     reconciliation_status = models.CharField(
#         max_length=20, 
#         choices=RECONCILIATION_STATUS_CHOICES, 
#         default='UNMATCHED'
#     )
    
#     # Matching Information
#     matched_payment = models.ForeignKey(
#         'Payment', 
#         on_delete=models.SET_NULL, 
#         null=True, blank=True,
#         related_name='bank_matches'
#     )
#     matched_journal_entry = models.ForeignKey(
#         'JournalEntry',
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='bank_matches'
#     )
#     matched_transaction = models.ForeignKey(
#         'Transaction',
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='bank_matches'
#     )
    
#     # Reconciliation Details
#     reconciliation_difference = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
    
#     # Manual Review
#     reviewed_by = models.ForeignKey(
#         User, 
#         on_delete=models.SET_NULL, 
#         null=True, blank=True,
#         related_name='reviewed_bank_transactions'
#     )
#     reviewed_date = models.DateTimeField(null=True, blank=True)
#     review_notes = models.TextField(blank=True)
    
#     # Duplicate Detection
#     is_duplicate = models.BooleanField(default=False)
#     duplicate_of = models.ForeignKey(
#         'self', 
#         on_delete=models.SET_NULL, 
#         null=True, blank=True
#     )
    
#     # Auto-matching metadata
#     match_confidence = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2, 
#         null=True, blank=True,
#         help_text="Confidence score for auto-matching (0-100)"
#     )
#     matching_rule_applied = models.CharField(max_length=100, blank=True)
    
#     class Meta:
#         db_table = 'finance_bank_transactions'
#         ordering = ['-transaction_date', '-id']
#         indexes = [
#             models.Index(fields=['tenant', 'bank_statement', 'reconciliation_status']),
#             models.Index(fields=['tenant', 'transaction_date', 'amount']),
#             models.Index(fields=['tenant', 'reference_number']),
#             models.Index(fields=['tenant', 'description']),
#             models.Index(fields=['tenant', 'bank_transaction_id']),
#         ]
        
#     def __str__(self):
#         return f"{self.transaction_date} - {self.description}: {self.amount}"
    
#     def auto_match(self):
#         """Attempt to auto-match with existing transactions"""
#         from .services import BankReconciliationService
        
#         service = BankReconciliationService(self.tenant)
#         return service.auto_match_transaction(self)
    
#     def mark_as_matched(self, matched_record, user=None, confidence=None):
#         """Mark transaction as matched with a specific record"""
#         if isinstance(matched_record, Payment):
#             self.matched_payment = matched_record
#         elif isinstance(matched_record, JournalEntry):
#             self.matched_journal_entry = matched_record
#         else:
#             self.matched_transaction = matched_record
            
#         self.reconciliation_status = 'MATCHED'
#         self.match_confidence = confidence
        
#         if user:
#             self.reviewed_by = user
#             self.reviewed_date = timezone.now()
            
#         self.save()


# class BankReconciliation(TenantBaseModel):
#     """Enhanced bank reconciliation model"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('IN_PROGRESS', 'In Progress'),
#         ('COMPLETED', 'Completed'),
#         ('REVIEWED', 'Reviewed'),
#         ('APPROVED', 'Approved'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     bank_account = models.ForeignKey(
#         BankAccount,
#         on_delete=models.CASCADE,
#         related_name='reconciliations'
#     )
#     bank_statement = models.ForeignKey(
#         BankStatement,
#         on_delete=models.CASCADE,
#         related_name='reconciliations'
#     )
    
#     # Reconciliation Period
#     reconciliation_date = models.DateField()
#     previous_reconciliation_date = models.DateField(null=True, blank=True)
    
#     # Starting Balances
#     statement_beginning_balance = models.DecimalField(max_digits=15, decimal_places=2)
#     statement_ending_balance = models.DecimalField(max_digits=15, decimal_places=2)
#     book_beginning_balance = models.DecimalField(max_digits=15, decimal_places=2)
#     book_ending_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Reconciling Items
#     total_deposits_in_transit = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     total_outstanding_checks = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     total_bank_adjustments = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     total_book_adjustments = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
    
#     # Results
#     adjusted_bank_balance = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     adjusted_book_balance = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     difference = models.DecimalField(
#         max_digits=15, decimal_places=2, default=Decimal('0.00')
#     )
#     is_balanced = models.BooleanField(default=False)
    
#     # Status and Workflow
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
#     # Session Information
#     started_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='started_reconciliations'
#     )
#     started_date = models.DateTimeField(auto_now_add=True)
    
#     # Completion
#     completed_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='completed_reconciliations'
#     )
#     completed_date = models.DateTimeField(null=True, blank=True)
    
#     # Review and Approval
#     reviewed_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='reviewed_reconciliations'
#     )
#     reviewed_date = models.DateTimeField(null=True, blank=True)
    
#     approved_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='approved_reconciliations'
#     )
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     # Notes and Comments
#     notes = models.TextField(blank=True)
#     completion_notes = models.TextField(blank=True)
    
#     # Auto-matching statistics
#     auto_matched_count = models.IntegerField(default=0)
#     manual_matched_count = models.IntegerField(default=0)
#     unmatched_count = models.IntegerField(default=0)
    
#     class Meta:
#         db_table = 'finance_bank_reconciliations'
#         ordering = ['-reconciliation_date']
        
#     def __str__(self):
#         return f"{self.bank_account} - {self.reconciliation_date}"
    
#     def calculate_balances(self):
#         """Calculate adjusted balances and difference"""
#         self.adjusted_bank_balance = (
#             self.statement_ending_balance +
#             self.total_deposits_in_transit -
#             self.total_outstanding_checks +
#             self.total_bank_adjustments
#         )
        
#         self.adjusted_book_balance = (
#             self.book_ending_balance + 
#             self.total_book_adjustments
#         )
        
#         self.difference = self.adjusted_bank_balance - self.adjusted_book_balance
#         self.is_balanced = abs(self.difference) <= self.bank_account.reconciliation_tolerance
        
#         self.save()
    
#     def complete_reconciliation(self, user):
#         """Complete the reconciliation process"""
#         if not self.is_balanced:
#             raise ValidationError('Reconciliation must be balanced before completion')
        
#         self.status = 'COMPLETED'
#         self.completed_by = user
#         self.completed_date = timezone.now()
#         self.save()
        
#         # Update bank account
#         self.bank_account.last_reconciled_balance = self.statement_ending_balance
#         self.bank_account.last_reconciliation_date = self.reconciliation_date
#         self.bank_account.save()
        
#         # Mark statement as reconciled
#         self.bank_statement.is_reconciled = True
#         self.bank_statement.reconciled_date = timezone.now()
#         self.bank_statement.reconciled_by = user
#         self.bank_statement.save()
        
#         return True
    
#     def get_reconciliation_summary(self):
#         """Get reconciliation summary data"""
#         return {
#             'statement_balance': self.statement_ending_balance,
#             'book_balance': self.book_ending_balance,
#             'deposits_in_transit': self.total_deposits_in_transit,
#             'outstanding_checks': self.total_outstanding_checks,
#             'bank_adjustments': self.total_bank_adjustments,
#             'book_adjustments': self.total_book_adjustments,
#             'adjusted_bank_balance': self.adjusted_bank_balance,
#             'adjusted_book_balance': self.adjusted_book_balance,
#             'difference': self.difference,
#             'is_balanced': self.is_balanced,
#             'auto_matched': self.auto_matched_count,
#             'manual_matched': self.manual_matched_count,
#             'unmatched': self.unmatched_count,
#         }


# class ReconciliationAdjustment(TenantBaseModel):
#     """Reconciliation adjustments and differences"""
    
#     ADJUSTMENT_TYPES = [
#         ('BANK_FEE', 'Bank Fee'),
#         ('INTEREST_INCOME', 'Interest Income'),
#         ('NSF_FEE', 'NSF Fee'),
#         ('BANK_ERROR', 'Bank Error'),
#         ('BOOK_ERROR', 'Book Error'),
#         ('TIMING_DIFFERENCE', 'Timing Difference'),
#         ('OUTSTANDING_CHECK', 'Outstanding Check'),
#         ('DEPOSIT_IN_TRANSIT', 'Deposit in Transit'),
#         ('SERVICE_CHARGE', 'Service Charge'),
#         ('OTHER', 'Other Adjustment'),
#     ]
    
#     reconciliation = models.ForeignKey(
#         BankReconciliation, 
#         on_delete=models.CASCADE, 
#         related_name='adjustments'
#     )
    
#     # Adjustment Details
#     adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPES)
#     amount = models.DecimalField(max_digits=15, decimal_places=2)
#     description = models.TextField()
    
#     # Related Records
#     bank_transaction = models.ForeignKey(
#         BankTransaction, 
#         on_delete=models.SET_NULL, 
#         null=True, blank=True,
#         related_name='adjustments'
#     )
#     journal_entry = models.ForeignKey(
#         'JournalEntry',
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name='reconciliation_adjustments'
#     )
    
#     # Processing
#     is_processed = models.BooleanField(default=False)
#     processed_date = models.DateTimeField(null=True, blank=True)
#     processed_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True
#     )
    
#     class Meta:
#         db_table = 'finance_reconciliation_adjustments'
#         ordering = ['-created_at']
        
#     def __str__(self):
#         return f"{self.adjustment_type} - {self.amount}"


# class ReconciliationRule(TenantBaseModel):
#     """Enhanced automated matching rules for bank reconciliation"""
    
#     RULE_TYPES = [
#         ('AMOUNT_EXACT', 'Exact Amount Match'),
#         ('AMOUNT_RANGE', 'Amount Range Match'),
#         ('DESCRIPTION_CONTAINS', 'Description Contains'),
#         ('DESCRIPTION_REGEX', 'Description Regex'),
#         ('REFERENCE_MATCH', 'Reference Number Match'),
#         ('PAYEE_MATCH', 'Payee Name Match'),
#         ('DATE_RANGE', 'Date Range Match'),
#         ('COMPOSITE', 'Composite Rule'),
#     ]
    
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
#     rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    
#     # Rule Configuration (JSON field for flexible rule definition)
#     rule_config = models.JSONField(default=dict, help_text="Rule configuration parameters")
    
#     # Matching Criteria
#     amount_tolerance = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         default=Decimal('0.01')
#     )
#     date_tolerance_days = models.IntegerField(default=2)
    
#     # Rule Status
#     is_active = models.BooleanField(default=True)
#     priority = models.IntegerField(default=10, help_text="Lower numbers = higher priority")
    
#     # Statistics
#     matches_found = models.IntegerField(default=0)
#     successful_matches = models.IntegerField(default=0)
#     false_positives = models.IntegerField(default=0)
#     last_used = models.DateTimeField(null=True, blank=True)
    
#     # Performance tracking
#     average_confidence = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2, 
#         null=True, blank=True
#     )
    
#     class Meta:
#         db_table = 'finance_reconciliation_rules'
#         ordering = ['priority', 'name']
        
#     def __str__(self):
#         return f"{self.name} ({self.rule_type})"
    
#     def apply_rule(self, bank_transaction):
#         """Apply this rule to a bank transaction"""
#         from .services import ReconciliationRuleEngine
        
#         engine = ReconciliationRuleEngine(self.tenant)
#         return engine.apply_rule(self, bank_transaction)
    
#     def update_statistics(self, found_match, was_successful, confidence=None):
#         """Update rule performance statistics"""
#         if found_match:
#             self.matches_found += 1
#             if was_successful:
#                 self.successful_matches += 1
#             else:
#                 self.false_positives += 1
                
#         if confidence:
#             if self.average_confidence:
#                 # Running average
#                 total_matches = self.matches_found
#                 self.average_confidence = (
#                     (self.average_confidence * (total_matches - 1) + confidence) / total_matches
#                 )
#             else:
#                 self.average_confidence = confidence
                
#         self.last_used = timezone.now()
#         self.save()


# class ReconciliationLog(TenantBaseModel):
#     """Audit log for reconciliation activities"""
    
#     ACTION_TYPES = [
#         ('RECONCILIATION_STARTED', 'Reconciliation Started'),
#         ('TRANSACTION_MATCHED', 'Transaction Matched'),
#         ('TRANSACTION_UNMATCHED', 'Transaction Unmatched'),
#         ('ADJUSTMENT_ADDED', 'Adjustment Added'),
#         ('RULE_APPLIED', 'Rule Applied'),
#         ('RECONCILIATION_COMPLETED', 'Reconciliation Completed'),
#         ('RECONCILIATION_REVIEWED', 'Reconciliation Reviewed'),
#         ('RECONCILIATION_APPROVED', 'Reconciliation Approved'),
#     ]
    
#     reconciliation = models.ForeignKey(
#         BankReconciliation,
#         on_delete=models.CASCADE,
#         related_name='activity_logs'
#     )
    
#     action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
#     action_date = models.DateTimeField(auto_now_add=True)
#     performed_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True, blank=True
#     )
    
#     # Details
#     description = models.TextField()
#     details = models.JSONField(default=dict, blank=True)
    
#     # Related objects
#     bank_transaction = models.ForeignKey(
#         BankTransaction,
#         on_delete=models.SET_NULL,
#         null=True, blank=True
#     )
#     adjustment = models.ForeignKey(
#         ReconciliationAdjustment,
#         on_delete=models.SET_NULL,
#         null=True, blank=True
#     )
    
#     class Meta:
#         db_table = 'finance_reconciliation_logs'
#         ordering = ['-action_date']
        
#     def __str__(self):
#         return f"{self.action_type} - {self.action_date}"


# class Vendor(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced vendor/supplier management with CRM integration"""
    
#     VENDOR_TYPE_CHOICES = [
#         ('SUPPLIER', 'Supplier'),
#         ('SERVICE_PROVIDER', 'Service Provider'),
#         ('CONTRACTOR', 'Contractor'),
#         ('EMPLOYEE', 'Employee'),
#         ('UTILITY', 'Utility Company'),
#         ('GOVERNMENT', 'Government Agency'),
#         ('OTHER', 'Other'),
#     ]
    
#     PAYMENT_TERMS_CHOICES = [
#         ('NET_15', 'Net 15 Days'),
#         ('NET_30', 'Net 30 Days'),
#         ('NET_60', 'Net 60 Days'),
#         ('NET_90', 'Net 90 Days'),
#         ('COD', 'Cash on Delivery'),
#         ('PREPAID', 'Prepaid'),
#         ('2_10_NET_30', '2/10 Net 30'),
#         ('CUSTOM', 'Custom Terms'),
#     ]
    
#     STATUS_CHOICES = [
#         ('ACTIVE', 'Active'),
#         ('INACTIVE', 'Inactive'),
#         ('ON_HOLD', 'On Hold'),
#         ('BLOCKED', 'Blocked'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#     ]
    
#     # Basic Information
#     vendor_number = models.CharField(max_length=50)
#     company_name = models.CharField(max_length=200)
#     display_name = models.CharField(max_length=200)
#     vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, default='SUPPLIER')
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
#     # Contact Information
#     primary_contact = models.CharField(max_length=100, blank=True)
#     email = models.EmailField(blank=True)
#     phone = models.CharField(max_length=20, blank=True)
#     mobile = models.CharField(max_length=20, blank=True)
#     fax = models.CharField(max_length=20, blank=True)
#     website = models.URLField(blank=True)
    
#     # Address Information
#     billing_address = models.JSONField(default=dict)
#     shipping_address = models.JSONField(default=dict)
#     remit_to_address = models.JSONField(default=dict)
    
#     # Financial Information
#     payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='NET_30')
#     payment_terms_days = models.PositiveIntegerField(default=30)
#     credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    
#     # Tax Information
#     tax_id = models.CharField(max_length=50, blank=True)
#     vat_number = models.CharField(max_length=50, blank=True)
#     is_tax_exempt = models.BooleanField(default=False)
#     tax_exempt_number = models.CharField(max_length=50, blank=True)
#     is_1099_vendor = models.BooleanField(default=False)  # US Tax reporting
    
#     # Default Accounts
#     default_expense_account = models.ForeignKey(
#         Account,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='vendors_expense'
#     )
#     accounts_payable_account = models.ForeignKey(
#         Account,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='vendors_payable'
#     )
    
#     # Banking Information
#     bank_name = models.CharField(max_length=100, blank=True)
#     bank_account_number = models.CharField(max_length=50, blank=True)
#     routing_number = models.CharField(max_length=20, blank=True)
#     swift_code = models.CharField(max_length=20, blank=True)
#     iban = models.CharField(max_length=34, blank=True)
    
#     # CRM Integration
#     crm_contact_id = models.IntegerField(null=True, blank=True)
#     lead_source = models.CharField(max_length=100, blank=True)
    
#     # Inventory Integration
#     is_inventory_supplier = models.BooleanField(default=False)
#     supplier_code = models.CharField(max_length=50, blank=True)
    
#     # Performance Metrics
#     average_payment_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
#     on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
#     quality_rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    
#     # Additional Information
#     notes = models.TextField(blank=True)
#     internal_notes = models.TextField(blank=True)
    
#     # Approval
#     approved_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='approved_vendors'
#     )
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['company_name']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'vendor_number'],
#                 name='unique_tenant_vendor_number'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'status', 'vendor_type']),
#             models.Index(fields=['tenant', 'is_inventory_supplier']),
#         ]
        
#     def __str__(self):
#         return self.display_name or self.company_name
    
#     def save(self, *args, **kwargs):
#         if not self.vendor_number:
#             self.vendor_number = self.generate_vendor_number()
#         if not self.display_name:
#             self.display_name = self.company_name
#         super().save(*args, **kwargs)
    
#     def generate_vendor_number(self):
#         """Generate unique vendor number"""
#         return generate_code('VEN', self.tenant_id)
    
#     @property
#     def full_name(self):
#         """Get full vendor name"""
#         if self.primary_contact:
#             return f'{self.company_name} ({self.primary_contact})'
#         return self.company_name
    
#     def get_outstanding_balance(self):
#         """Get total outstanding balance"""
#         from .services import VendorService
        
#         service = VendorService(self.tenant)
#         return service.get_vendor_balance(self.id)
    
#     def get_ytd_purchases(self):
#         """Get year-to-date purchases"""
#         current_year = timezone.now().year
#         ytd_purchases = self.bills.filter(
#             bill_date__year=current_year,
#             status__in=['PAID', 'PARTIAL', 'OPEN']
#         ).aggregate(total=models.Sum('total_amount'))
        
#         return ytd_purchases['total'] or Decimal('0.00')
    
#     def update_performance_metrics(self):
#         """Update vendor performance metrics"""
#         from .services import VendorPerformanceService
        
#         service = VendorPerformanceService(self.tenant)
#         service.calculate_vendor_metrics(self)


# class VendorContact(TenantBaseModel):
#     """Additional contacts for vendors"""
    
#     CONTACT_TYPES = [
#         ('PRIMARY', 'Primary Contact'),
#         ('ACCOUNTING', 'Accounting Contact'),
#         ('PURCHASING', 'Purchasing Contact'),
#         ('TECHNICAL', 'Technical Contact'),
#         ('SALES', 'Sales Contact'),
#         ('OTHER', 'Other'),
#     ]
    
#     vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contacts')
#     contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    
#     # Contact Information
#     first_name = models.CharField(max_length=100)
#     last_name = models.CharField(max_length=100)
#     title = models.CharField(max_length=100, blank=True)
#     email = models.EmailField()
#     phone = models.CharField(max_length=20, blank=True)
#     mobile = models.CharField(max_length=20, blank=True)
    
#     # Settings
#     is_primary = models.BooleanField(default=False)
#     receive_communications = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['vendor', 'last_name', 'first_name']
        
#     def __str__(self):
#         return f"{self.first_name} {self.last_name} ({self.vendor.company_name})"


# # ============================================================================
# # ENHANCED BILLS & PAYABLES
# # ============================================================================

# class Bill(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced vendor bills with multi-currency and workflow support"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#         ('APPROVED', 'Approved'),
#         ('OPEN', 'Open'),
#         ('PARTIAL', 'Partially Paid'),
#         ('PAID', 'Paid'),
#         ('OVERDUE', 'Overdue'),
#         ('CANCELLED', 'Cancelled'),
#         ('REJECTED', 'Rejected'),
#         ('ON_HOLD', 'On Hold'),
#     ]
    
#     BILL_TYPES = [
#         ('STANDARD', 'Standard Bill'),
#         ('RECURRING', 'Recurring Bill'),
#         ('CREDIT_NOTE', 'Credit Note'),
#         ('DEBIT_NOTE', 'Debit Note'),
#         ('EXPENSE_REPORT', 'Expense Report'),
#     ]
    
#     # Bill Identification
#     bill_number = models.CharField(max_length=50)
#     vendor_invoice_number = models.CharField(max_length=100, blank=True)
#     reference_number = models.CharField(max_length=100, blank=True)
#     bill_type = models.CharField(max_length=20, choices=BILL_TYPES, default='STANDARD')
    
#     # Vendor Information
#     vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='bills')
    
#     # Dates
#     bill_date = models.DateField()
#     due_date = models.DateField()
#     received_date = models.DateField(null=True, blank=True)
#     service_period_start = models.DateField(null=True, blank=True)
#     service_period_end = models.DateField(null=True, blank=True)
    
#     # Status & Approval
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     approved_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='approved_bills'
#     )
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    
#     # Financial Information
#     subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Base Currency Amounts
#     base_currency_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Addresses
#     billing_address = models.JSONField(default=dict)
    
#     # Source Documents
#     source_purchase_order = models.ForeignKey(
#         PurchaseOrder,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='bills'
#     )
    
#     # Recurring Bill Settings
#     is_recurring = models.BooleanField(default=False)
#     recurring_interval_days = models.PositiveIntegerField(null=True, blank=True)
#     next_bill_date = models.DateField(null=True, blank=True)
#     parent_bill = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
#     # Additional Information
#     description = models.TextField(blank=True)
#     notes = models.TextField(blank=True)
#     terms = models.TextField(blank=True)
#     private_notes = models.TextField(blank=True)
    
#     # Journal Entry
#     journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='bills'
#     )
    
#     # Attachments
#     attachments = models.JSONField(default=list, blank=True)
    
#     # Workflow
#     workflow_state = models.CharField(max_length=50, blank=True)
    
#     class Meta:
#         ordering = ['-bill_date', '-bill_number']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'bill_number'],
#                 name='unique_tenant_bill_number'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'status', 'vendor']),
#             models.Index(fields=['tenant', 'due_date', 'status']),
#             models.Index(fields=['tenant', 'bill_date']),
#         ]
        
#     def __str__(self):
#         return f'{self.bill_number} - {self.vendor.company_name}'
    
#     def save(self, *args, **kwargs):
#         if not self.bill_number:
#             self.bill_number = self.generate_bill_number()
        
#         # Calculate totals
#         self.calculate_totals()
        
#         # Calculate base currency amounts
#         self.calculate_base_currency_amounts()
        
#         super().save(*args, **kwargs)
    
#     def generate_bill_number(self):
#         """Generate unique bill number"""
#         settings = FinanceSettings.objects.get(tenant=self.tenant)
#         return generate_code(settings.bill_prefix, self.tenant_id, settings.bill_starting_number)
    
#     def calculate_totals(self):
#         """Calculate bill totals from line items"""
#         line_totals = self.bill_items.aggregate(
#             subtotal=models.Sum(
#                 models.F('quantity') * models.F('unit_cost'),
#                 output_field=models.DecimalField()
#             ),
#             tax_total=models.Sum('tax_amount', output_field=models.DecimalField())
#         )
        
#         self.subtotal = (line_totals['subtotal'] or Decimal('0.00')) - self.discount_amount
#         self.tax_amount = line_totals['tax_total'] or Decimal('0.00')
#         self.total_amount = self.subtotal + self.tax_amount
#         self.amount_due = self.total_amount - self.amount_paid
    
#     def calculate_base_currency_amounts(self):
#         """Calculate amounts in base currency"""
#         self.base_currency_subtotal = self.subtotal * self.exchange_rate
#         self.base_currency_total = self.total_amount * self.exchange_rate
#         self.base_currency_amount_paid = self.amount_paid * self.exchange_rate
#         self.base_currency_amount_due = self.amount_due * self.exchange_rate
    
#     @property
#     def is_overdue(self):
#         """Check if bill is overdue"""
#         return date.today() > self.due_date and self.status in ['OPEN', 'APPROVED']
    
#     @property
#     def days_until_due(self):
#         """Days until due date"""
#         return (self.due_date - date.today()).days
    
#     @property
#     def days_overdue(self):
#         """Days overdue (negative if not overdue)"""
#         return (date.today() - self.due_date).days
    
#     def approve_bill(self, user):
#         """Approve the bill"""
#         if self.status != 'PENDING_APPROVAL':
#             raise ValidationError('Bill is not in pending approval status')
        
#         self.status = 'OPEN'
#         self.approved_by = user
#         self.approved_date = timezone.now()
#         self.save()
        
#         # Create journal entry
#         self.create_journal_entry()
    
#     def create_journal_entry(self):
#         """Create journal entry for the bill"""
#         from .services import JournalEntryService
        
#         service = JournalEntryService(self.tenant)
#         return service.create_bill_journal_entry(self)
    
#     def create_cogs_entries(self):
#         """Create COGS entries for inventory items"""
#         if not self.vendor.is_inventory_supplier:
#             return
        
#         from .services import COGSService
#         service = COGSService(self.tenant)
#         service.create_bill_cogs_entries(self)


# class BillItem(TenantBaseModel):
#     """Enhanced bill line items with inventory integration"""
    
#     ITEM_TYPES = [
#         ('PRODUCT', 'Product'),
#         ('SERVICE', 'Service'),
#         ('EXPENSE', 'Expense'),
#         ('ASSET', 'Asset'),
#         ('OTHER', 'Other'),
#     ]
    
#     bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='bill_items')
#     line_number = models.IntegerField()
    
#     # Item Information
#     item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='EXPENSE')
#     product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
#     description = models.TextField()
#     sku = models.CharField(max_length=100, blank=True)
    
#     # Quantity & Pricing
#     quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('1.0000'))
#     unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
#     discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
#     line_total = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Account Classification
#     expense_account = models.ForeignKey(Account, on_delete=models.PROTECT)
    
#     # Tax Information
#     tax_code = models.ForeignKey(TaxCode, on_delete=models.SET_NULL, null=True, blank=True)
#     tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
#     tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Additional Tracking
#     project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
#     department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
#     location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
#     job_number = models.CharField(max_length=50, blank=True)
    
#     # Inventory Integration
#     warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
#     lot_number = models.CharField(max_length=100, blank=True)
#     serial_numbers = models.JSONField(default=list, blank=True)
    
#     class Meta:
#         ordering = ['bill', 'line_number']
        
#     def __str__(self):
#         return f'{self.bill.bill_number} - Line {self.line_number}: {self.description}'
    
#     def save(self, *args, **kwargs):
#         # Calculate line total
#         line_subtotal = self.quantity * self.unit_cost
#         discount_amount = line_subtotal * self.discount_rate
#         self.line_total = line_subtotal - discount_amount
        
#         # Calculate tax
#         if self.tax_code:
#             self.tax_amount = self.tax_code.calculate_tax(self.line_total)
        
#         super().save(*args, **kwargs)
        
#         # Update inventory if this is a product purchase
#         if self.product and self.item_type == 'PRODUCT':
#             self.update_inventory()
    
#     def update_inventory(self):
#         """Update inventory levels and cost layers"""
#         if not self.product or self.bill.status != 'APPROVED':
#             return
        
#         from .services import InventoryService
#         service = InventoryService(self.tenant)
#         service.process_purchase_receipt(self)


# # ============================================================================
# # ENHANCED INVOICES & RECEIVABLES  
# # ============================================================================

# class Invoice(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced customer invoices with multi-currency and CRM integration"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#         ('APPROVED', 'Approved'),
#         ('SENT', 'Sent'),
#         ('VIEWED', 'Viewed by Customer'),
#         ('OPEN', 'Open'),
#         ('PARTIAL', 'Partially Paid'),
#         ('PAID', 'Paid'),
#         ('OVERDUE', 'Overdue'),
#         ('CANCELLED', 'Cancelled'),
#         ('REFUNDED', 'Refunded'),
#         ('DISPUTED', 'Disputed'),
#     ]
    
#     INVOICE_TYPE_CHOICES = [
#         ('STANDARD', 'Standard Invoice'),
#         ('RECURRING', 'Recurring Invoice'),
#         ('CREDIT_NOTE', 'Credit Note'),
#         ('DEBIT_NOTE', 'Debit Note'),
#         ('ESTIMATE', 'Estimate'),
#         ('QUOTE', 'Quote'),
#         ('PROFORMA', 'Proforma Invoice'),
#     ]
    
#     # Invoice Identification
#     invoice_number = models.CharField(max_length=50)
#     invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES, default='STANDARD')
#     reference_number = models.CharField(max_length=100, blank=True)
#     purchase_order_number = models.CharField(max_length=100, blank=True)
    
#     # Customer Information
#     customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
#     customer_email = models.EmailField()
#     customer_contact = models.ForeignKey(
#         Contact,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
    
#     # Dates
#     invoice_date = models.DateField()
#     due_date = models.DateField()
#     sent_date = models.DateTimeField(null=True, blank=True)
#     viewed_date = models.DateTimeField(null=True, blank=True)
#     service_period_start = models.DateField(null=True, blank=True)
#     service_period_end = models.DateField(null=True, blank=True)
    
#     # Status & Approval
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     approved_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='approved_invoices'
#     )
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    
#     # Financial Information
#     subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
#     tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     shipping_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Base Currency Amounts
#     base_currency_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     base_currency_amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Addresses
#     billing_address = models.JSONField(default=dict)
#     shipping_address = models.JSONField(default=dict)
    
#     # Payment Information
#     payment_terms = models.CharField(max_length=100, blank=True)
#     payment_instructions = models.TextField(blank=True)
#     bank_details = models.JSONField(default=dict, blank=True)
    
#     # Source Documents
#     source_order = models.ForeignKey(
#         'ecommerce.Order',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
#     source_quote = models.ForeignKey(
#         'self',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         limit_choices_to={'invoice_type': 'QUOTE'}
#     )
    
#     # Recurring Invoice Settings
#     is_recurring = models.BooleanField(default=False)
#     recurring_interval_days = models.PositiveIntegerField(null=True, blank=True)
#     next_invoice_date = models.DateField(null=True, blank=True)
#     parent_invoice = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
#     auto_send = models.BooleanField(default=False)
    
#     # Additional Information
#     description = models.TextField(blank=True)
#     notes = models.TextField(blank=True)
#     footer_text = models.TextField(blank=True)
#     customer_message = models.TextField(blank=True)
#     internal_notes = models.TextField(blank=True)
    
#     # Journal Entry
#     journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='invoices'
#     )
    
#     # Shipping Information
#     shipping_method = models.CharField(max_length=100, blank=True)
#     tracking_number = models.CharField(max_length=100, blank=True)
#     shipped_date = models.DateField(null=True, blank=True)
#     delivery_date = models.DateField(null=True, blank=True)
    
#     # Online Payments
#     online_payment_enabled = models.BooleanField(default=True)
#     payment_gateway_settings = models.JSONField(default=dict, blank=True)
    
#     # Attachments
#     attachments = models.JSONField(default=list, blank=True)
    
#     # Analytics
#     view_count = models.PositiveIntegerField(default=0)
#     last_reminder_sent = models.DateTimeField(null=True, blank=True)
#     reminder_count = models.PositiveIntegerField(default=0)
    
#     class Meta:
#         ordering = ['-invoice_date', '-invoice_number']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'invoice_number'],
#                 name='unique_tenant_invoice_number'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'status', 'customer']),
#             models.Index(fields=['tenant', 'due_date', 'status']),
#             models.Index(fields=['tenant', 'invoice_date']),
#             models.Index(fields=['tenant', 'is_recurring']),
#         ]
        
#     def __str__(self):
#         return f'{self.invoice_number} - {self.customer.name}'
    
#     def save(self, *args, **kwargs):
#         if not self.invoice_number:
#             self.invoice_number = self.generate_invoice_number()
        
#         if not self.customer_email and self.customer:
#             self.customer_email = self.customer.email
        
#         # Calculate totals
#         self.calculate_totals()
        
#         # Calculate base currency amounts
#         self.calculate_base_currency_amounts()
        
#         super().save(*args, **kwargs)
    
#     def generate_invoice_number(self):
#         """Generate unique invoice number"""
#         settings = FinanceSettings.objects.get(tenant=self.tenant)
#         return generate_code(settings.invoice_prefix, self.tenant_id, settings.invoice_starting_number)
    
#     def calculate_totals(self):
#         """Calculate invoice totals from line items"""
#         line_totals = self.invoice_items.aggregate(
#             subtotal=models.Sum(
#                 models.F('quantity') * models.F('unit_price') * (1 - models.F('discount_rate') / 100),
#                 output_field=models.DecimalField()
#             ),
#             tax_total=models.Sum('tax_amount', output_field=models.DecimalField())
#         )
        
#         gross_subtotal = line_totals['subtotal'] or Decimal('0.00')
        
#         # Apply invoice-level discount
#         if self.discount_percentage:
#             self.discount_amount = gross_subtotal * (self.discount_percentage / 100)
        
#         self.subtotal = gross_subtotal - self.discount_amount
#         self.tax_amount = line_totals['tax_total'] or Decimal('0.00')
#         self.total_amount = self.subtotal + self.tax_amount + self.shipping_amount
#         self.amount_due = self.total_amount - self.amount_paid
    
#     def calculate_base_currency_amounts(self):
#         """Calculate amounts in base currency"""
#         self.base_currency_subtotal = self.subtotal * self.exchange_rate
#         self.base_currency_total = self.total_amount * self.exchange_rate
#         self.base_currency_amount_paid = self.amount_paid * self.exchange_rate
#         self.base_currency_amount_due = self.amount_due * self.exchange_rate
    
#     @property
#     def is_overdue(self):
#         """Check if invoice is overdue"""
#         return date.today() > self.due_date and self.status in ['OPEN', 'SENT', 'VIEWED']
    
#     @property
#     def days_until_due(self):
#         """Days until due date"""
#         return (self.due_date - date.today()).days
    
#     @property
#     def days_overdue(self):
#         """Days overdue (negative if not overdue)"""
#         return (date.today() - self.due_date).days
    
#     def send_invoice(self, send_copy_to=None):
#         """Send invoice to customer"""
#         from .services import InvoiceService
        
#         service = InvoiceService(self.tenant)
#         result = service.send_invoice(self, send_copy_to)
        
#         if result['success']:
#             self.status = 'SENT'
#             self.sent_date = timezone.now()
#             self.save()
        
#         return result
    
#     def record_view(self, ip_address=None, user_agent=None):
#         """Record invoice view"""
#         self.view_count += 1
#         if self.status == 'SENT':
#             self.status = 'VIEWED'
#             self.viewed_date = timezone.now()
#         self.save()
    
#     def approve_invoice(self, user):
#         """Approve the invoice"""
#         if self.status != 'PENDING_APPROVAL':
#             raise ValidationError('Invoice is not in pending approval status')
        
#         self.status = 'APPROVED'
#         self.approved_by = user
#         self.approved_date = timezone.now()
#         self.save()
        
#         # Create journal entry
#         self.create_journal_entry()
        
#         # Create COGS entries for inventory items
#         self.create_cogs_entries()
    
#     def create_journal_entry(self):
#         """Create journal entry for the invoice"""
#         from .services import JournalEntryService
        
#         service = JournalEntryService(self.tenant)
#         return service.create_invoice_journal_entry(self)
    
#     def create_cogs_entries(self):
#         """Create COGS entries for inventory items"""
#         from .services import COGSService
        
#         service = COGSService(self.tenant)
#         service.create_invoice_cogs_entries(self)
    
#     def create_recurring_invoice(self):
#         """Create next recurring invoice"""
#         if not self.is_recurring or not self.next_invoice_date:
#             return None
        
#         from .services import RecurringInvoiceService
        
#         service = RecurringInvoiceService(self.tenant)
#         return service.create_next_invoice(self)


# class InvoiceItem(TenantBaseModel):
#     """Enhanced invoice line items with inventory integration"""
    
#     ITEM_TYPES = [
#         ('PRODUCT', 'Product'),
#         ('SERVICE', 'Service'),
#         ('DISCOUNT', 'Discount'),
#         ('SHIPPING', 'Shipping'),
#         ('OTHER', 'Other'),
#     ]
    
#     invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_items')
#     line_number = models.IntegerField()
    
#     # Item Information
#     item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='PRODUCT')
#     product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
#     description = models.TextField()
#     sku = models.CharField(max_length=100, blank=True)
    
#     # Quantity & Pricing
#     quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('1.0000'))
#     unit_price = models.DecimalField(max_digits=15, decimal_places=4)
#     discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
#     line_total = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Account Classification
#     revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT)
    
#     # Tax Information
#     tax_code = models.ForeignKey(TaxCode, on_delete=models.SET_NULL, null=True, blank=True)
#     tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
#     tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     is_tax_inclusive = models.BooleanField(default=False)
    
#     # Additional Tracking
#     project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
#     department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
#     location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
#     job_number = models.CharField(max_length=50, blank=True)
    
#     # Inventory Integration
#     warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
#     lot_numbers = models.JSONField(default=list, blank=True)
#     serial_numbers = models.JSONField(default=list, blank=True)
    
#     # Cost Information (for COGS calculation)
#     unit_cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
#     total_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
#     class Meta:
#         ordering = ['invoice', 'line_number']
        
#     def __str__(self):
#         return f'{self.invoice.invoice_number} - Line {self.line_number}: {self.description}'
    
#     def save(self, *args, **kwargs):
#         # Calculate line total
#         line_subtotal = self.quantity * self.unit_price
#         discount_amount = line_subtotal * (self.discount_rate / 100)
#         self.line_total = line_subtotal - discount_amount
        
#         # Calculate tax
#         if self.tax_code:
#             if self.is_tax_inclusive:
#                 # Tax is included in the price
#                 tax_divisor = Decimal('1') + (self.tax_code.rate / 100)
#                 self.tax_amount = self.line_total - (self.line_total / tax_divisor)
#             else:
#                 # Tax is added to the price
#                 self.tax_amount = self.tax_code.calculate_tax(self.line_total)
        
#         # Get cost information for COGS
#         if self.product:
#             cost_info = self.get_product_cost()
#             self.unit_cost = cost_info['unit_cost']
#             self.total_cost = cost_info['total_cost']
        
#         super().save(*args, **kwargs)
    
#     def get_product_cost(self):
#         """Get product cost for COGS calculation"""
#         if not self.product:
#             return {'unit_cost': Decimal('0.00'), 'total_cost': Decimal('0.00')}
        
#         from .services import InventoryCostingService
        
#         service = InventoryCostingService(self.tenant)
#         return service.get_product_cost(self.product, self.quantity, self.warehouse)
    
#     def reserve_inventory(self):
#         """Reserve inventory for this line item"""
#         if not self.product or self.item_type != 'PRODUCT':
#             return
        
#         from .services import InventoryService
        
#         service = InventoryService(self.tenant)
#         service.reserve_inventory(self.product, self.quantity, self.warehouse, self.invoice)
    
#     def release_inventory_reservation(self):
#         """Release inventory reservation"""
#         if not self.product or self.item_type != 'PRODUCT':
#             return
        
#         from .services import InventoryService
        
#         service = InventoryService(self.tenant)
#         service.release_reservation(self.product, self.quantity, self.warehouse, self.invoice)


# # ============================================================================
# # ENHANCED PAYMENTS
# # ============================================================================

# class Payment(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced payment records with multi-currency support"""
    
#     PAYMENT_TYPE_CHOICES = [
#         ('RECEIVED', 'Payment Received'),
#         ('MADE', 'Payment Made'),
#         ('TRANSFER', 'Transfer'),
#         ('DEPOSIT', 'Deposit'),
#         ('WITHDRAWAL', 'Withdrawal'),
#         ('REFUND', 'Refund'),
#     ]
    
#     PAYMENT_METHOD_CHOICES = [
#         ('CASH', 'Cash'),
#         ('CHECK', 'Check'),
#         ('CREDIT_CARD', 'Credit Card'),
#         ('DEBIT_CARD', 'Debit Card'),
#         ('BANK_TRANSFER', 'Bank Transfer'),
#         ('ACH', 'ACH'),
#         ('WIRE_TRANSFER', 'Wire Transfer'),
#         ('PAYPAL', 'PayPal'),
#         ('STRIPE', 'Stripe'),
#         ('SQUARE', 'Square'),
#         ('CRYPTOCURRENCY', 'Cryptocurrency'),
#         ('OTHER', 'Other'),
#     ]
    
#     STATUS_CHOICES = [
#         ('PENDING', 'Pending'),
#         ('PROCESSING', 'Processing'),
#         ('CLEARED', 'Cleared'),
#         ('BOUNCED', 'Bounced'),
#         ('CANCELLED', 'Cancelled'),
#         ('RECONCILED', 'Reconciled'),
#         ('FAILED', 'Failed'),
#     ]
    
#     # Payment Identification
#     payment_number = models.CharField(max_length=50)
#     reference_number = models.CharField(max_length=100, blank=True)
#     external_transaction_id = models.CharField(max_length=200, blank=True)
    
#     # Payment Details
#     payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
#     payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
#     payment_date = models.DateField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
#     # Parties
#     customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True)
#     vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, null=True, blank=True)
    
#     # Multi-Currency Support
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     amount = models.DecimalField(max_digits=15, decimal_places=2)
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
#     base_currency_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Bank Account
#     bank_account = models.ForeignKey(
#         Account,
#         on_delete=models.PROTECT,
#         related_name='payments',
#         limit_choices_to={'is_bank_account': True}
#     )
    
#     # Payment Method Specific Information
#     # Check Information
#     check_number = models.CharField(max_length=50, blank=True)
#     check_date = models.DateField(null=True, blank=True)
    
#     # Credit Card Information (PCI compliant - no sensitive data)
#     card_last_four = models.CharField(max_length=4, blank=True)
#     card_type = models.CharField(max_length=20, blank=True)
#     card_expiry_month = models.CharField(max_length=2, blank=True)
#     card_expiry_year = models.CharField(max_length=4, blank=True)
    
#     # Processing Information
#     processor_name = models.CharField(max_length=100, blank=True)
#     processor_transaction_id = models.CharField(max_length=200, blank=True)
#     processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
#     processing_fee_account = models.ForeignKey(
#         Account,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='processing_fees'
#     )
    
#     # Additional Information
#     description = models.TextField(blank=True)
#     notes = models.TextField(blank=True)
    
#     # Journal Entry
#     journal_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='payments'
#     )
    
#     # Reconciliation
#     bank_transaction = models.ForeignKey(
#         BankTransaction,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True
#     )
#     reconciled_date = models.DateField(null=True, blank=True)
#     reconciled_by = models.ForeignKey(
#         User,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='reconciled_payments'
#     )
    
#     # Attachments
#     attachments = models.JSONField(default=list, blank=True)
    
#     class Meta:
#         ordering = ['-payment_date', '-payment_number']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'payment_number'],
#                 name='unique_tenant_payment_number'
#             ),
#         ]
#         indexes = [
#             models.Index(fields=['tenant', 'payment_type', 'status']),
#             models.Index(fields=['tenant', 'customer', 'status']),
#             models.Index(fields=['tenant', 'vendor', 'status']),
#             models.Index(fields=['tenant', 'payment_date']),
#         ]
        
#     def __str__(self):
#         party = self.customer or self.vendor or 'Unknown'
#         return f'{self.payment_number} - {party} ({self.amount} {self.currency.code})'
    
#     def save(self, *args, **kwargs):
#         if not self.payment_number:
#             self.payment_number = self.generate_payment_number()
        
#         # Calculate base currency amount
#         self.base_currency_amount = self.amount * self.exchange_rate
        
#         super().save(*args, **kwargs)
    
#     def generate_payment_number(self):
#         """Generate unique payment number"""
#         settings = FinanceSettings.objects.get(tenant=self.tenant)
#         prefix = settings.payment_prefix
        
#         if self.payment_type == 'RECEIVED':
#             prefix = 'REC'
#         elif self.payment_type == 'MADE':
#             prefix = 'PAY'
        
#         return generate_code(prefix, self.tenant_id, settings.payment_starting_number)
    
#     def apply_to_invoices(self, invoice_applications):
#         """Apply payment to invoices"""
#         if self.payment_type != 'RECEIVED':
#             raise ValidationError('Only received payments can be applied to invoices')
        
#         total_applied = Decimal('0.00')
        
#         with transaction.atomic():
#             for application in invoice_applications:
#                 invoice_id = application['invoice_id']
#                 amount_applied = Decimal(str(application['amount']))
#                 discount_amount = Decimal(str(application.get('discount_amount', '0.00')))
                
#                 # Create payment application
#                 PaymentApplication.objects.create(
#                     tenant=self.tenant,
#                     payment=self,
#                     invoice_id=invoice_id,
#                     amount_applied=amount_applied,
#                     discount_amount=discount_amount
#                 )
                
#                 total_applied += amount_applied
            
#             if total_applied > self.amount:
#                 raise ValidationError('Cannot apply more than payment amount')
    
#     def apply_to_bills(self, bill_applications):
#         """Apply payment to bills"""
#         if self.payment_type != 'MADE':
#             raise ValidationError('Only made payments can be applied to bills')
        
#         total_applied = Decimal('0.00')
        
#         with transaction.atomic():
#             for application in bill_applications:
#                 bill_id = application['bill_id']
#                 amount_applied = Decimal(str(application['amount']))
#                 discount_amount = Decimal(str(application.get('discount_amount', '0.00')))
                
#                 # Create payment application
#                 PaymentApplication.objects.create(
#                     tenant=self.tenant,
#                     payment=self,
#                     bill_id=bill_id,
#                     amount_applied=amount_applied,
#                     discount_amount=discount_amount
#                 )
                
#                 total_applied += amount_applied
            
#             if total_applied > self.amount:
#                 raise ValidationError('Cannot apply more than payment amount')
    
#     def create_journal_entry(self):
#         """Create journal entry for payment"""
#         from .services import JournalEntryService
        
#         service = JournalEntryService(self.tenant)
#         return service.create_payment_journal_entry(self)
    
#     def process_refund(self, refund_amount=None):
#         """Process a refund for this payment"""
#         if self.payment_type != 'RECEIVED':
#             raise ValidationError('Only received payments can be refunded')
        
#         refund_amount = refund_amount or self.amount
        
#         if refund_amount > self.amount:
#             raise ValidationError('Refund amount cannot exceed original payment amount')
        
#         from .services import PaymentService
        
#         service = PaymentService(self.tenant)
#         return service.process_refund(self, refund_amount)


# class PaymentApplication(TenantBaseModel):
#     """Enhanced payment applications with discount support"""
    
#     payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='applications')
    
#     # Document References
#     invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True)
#     bill = models.ForeignKey(Bill, on_delete=models.CASCADE, null=True, blank=True)
    
#     # Application Details
#     amount_applied = models.DecimalField(max_digits=15, decimal_places=2)
#     discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     application_date = models.DateField(auto_now_add=True)
    
#     # Multi-Currency
#     exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
#     base_currency_amount_applied = models.DecimalField(max_digits=15, decimal_places=2)
    
#     # Notes
#     notes = models.TextField(blank=True)
    
#     class Meta:
#         ordering = ['-application_date']
        
#     def __str__(self):
#         document = self.invoice or self.bill
#         return f'{self.payment.payment_number} -> {document} ({self.amount_applied})'
    
#     def save(self, *args, **kwargs):
#         # Calculate base currency amount
#         self.base_currency_amount_applied = self.amount_applied * self.exchange_rate
        
#         super().save(*args, **kwargs)
        
#         # Update document amounts
#         if self.invoice:
#             self.update_invoice_amounts()
#         elif self.bill:
#             self.update_bill_amounts()
    
#     def update_invoice_amounts(self):
#         """Update invoice payment amounts"""
#         total_applied = self.invoice.applications.aggregate(
#             total=models.Sum('amount_applied')
#         )['total'] or Decimal('0.00')
        
#         self.invoice.amount_paid = total_applied
#         self.invoice.amount_due = self.invoice.total_amount - total_applied
        
#         # Update status
#         if self.invoice.amount_due <= Decimal('0.00'):
#             self.invoice.status = 'PAID'
#         elif self.invoice.amount_paid > Decimal('0.00'):
#             self.invoice.status = 'PARTIAL'
#         else:
#             self.invoice.status = 'OPEN'
        
#         self.invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])
    
#     def update_bill_amounts(self):
#         """Update bill payment amounts"""
#         total_applied = self.bill.applications.aggregate(
#             total=models.Sum('amount_applied')
#         )['total'] or Decimal('0.00')
        
#         self.bill.amount_paid = total_applied
#         self.bill.amount_due = self.bill.total_amount - total_applied
        
#         # Update status
#         if self.bill.amount_due <= Decimal('0.00'):
#             self.bill.status = 'PAID'
#         elif self.bill.amount_paid > Decimal('0.00'):
#             self.bill.status = 'PARTIAL'
#         else:
#             self.bill.status = 'OPEN'
        
#         self.bill.save(update_fields=['amount_paid', 'amount_due', 'status'])


# # ============================================================================
# # CRM INTEGRATION MODELS
# # ============================================================================

# class CustomerFinancialProfile(TenantBaseModel):
#     """Financial profile integration with CRM customer data"""
    
#     CREDIT_RATING_CHOICES = [
#         ('EXCELLENT', 'Excellent'),
#         ('GOOD', 'Good'),
#         ('FAIR', 'Fair'),
#         ('POOR', 'Poor'),
#         ('UNRATED', 'Unrated'),
#     ]
    
#     customer = models.OneToOneField(
#         Customer,
#         on_delete=models.CASCADE,
#         related_name='financial_profile'
#     )
    
#     # Credit Information
#     credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     credit_rating = models.CharField(max_length=20, choices=CREDIT_RATING_CHOICES, default='UNRATED')
#     credit_check_date = models.DateField(null=True, blank=True)
#     credit_notes = models.TextField(blank=True)
    
#     # Payment Terms
#     payment_terms_days = models.PositiveIntegerField(default=30)
#     early_payment_discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
#     late_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
#     # Financial Summary
#     total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_payments = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     highest_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Payment History
#     average_days_to_pay = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
#     payment_history_score = models.IntegerField(default=0)  # 0-100
#     last_payment_date = models.DateField(null=True, blank=True)
    
#     # Risk Assessment
#     risk_level = models.CharField(
#         max_length=20,
#         choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
#         default='MEDIUM'
#     )
#     collection_priority = models.CharField(
#         max_length=20,
#         choices=[('LOW', 'Low'), ('NORMAL', 'Normal'), ('HIGH', 'High'), ('URGENT', 'Urgent')],
#         default='NORMAL'
#     )
    
#     # Account Settings
#     account_on_hold = models.BooleanField(default=False)
#     require_prepayment = models.BooleanField(default=False)
#     auto_send_statements = models.BooleanField(default=True)
#     preferred_payment_method = models.CharField(max_length=50, blank=True)
    
#     class Meta:
#         verbose_name = 'Customer Financial Profile'
        
#     def __str__(self):
#         return f'{self.customer.name} - Financial Profile'
    
#     def update_payment_history(self):
#         """Update payment history metrics"""
#         from .services import CustomerAnalyticsService
        
#         service = CustomerAnalyticsService(self.tenant)
#         service.update_customer_payment_history(self.customer)
    
#     def calculate_credit_utilization(self):
#         """Calculate credit utilization percentage"""
#         if self.credit_limit > 0:
#             return (self.current_balance / self.credit_limit) * 100
#         return Decimal('0.00')
    
#     def is_over_credit_limit(self):
#         """Check if customer is over credit limit"""
#         return self.current_balance > self.credit_limit


# class LeadFinancialData(TenantBaseModel):
#     """Financial data integration for CRM leads"""
    
#     lead = models.OneToOneField(
#         Lead,
#         on_delete=models.CASCADE,
#         related_name='financial_data'
#     )
    
#     # Estimated Values
#     estimated_annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     estimated_deal_size = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     estimated_gross_margin = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
#     # Budget Information
#     stated_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     budget_timeframe = models.CharField(max_length=100, blank=True)
#     decision_maker = models.CharField(max_length=200, blank=True)
    
#     # Company Financials
#     company_annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     company_size_employees = models.PositiveIntegerField(null=True, blank=True)
#     credit_check_required = models.BooleanField(default=False)
    
#     class Meta:
#         verbose_name = 'Lead Financial Data'
        
#     def __str__(self):
#         return f'{self.lead.company_name} - Financial Data'


# # ============================================================================
# # SUPPORTING MODELS
# # ============================================================================

# class Project(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced project tracking for job costing"""
    
#     STATUS_CHOICES = [
#         ('PLANNING', 'Planning'),
#         ('ACTIVE', 'Active'),
#         ('ON_HOLD', 'On Hold'),
#         ('COMPLETED', 'Completed'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     PROJECT_TYPES = [
#         ('INTERNAL', 'Internal Project'),
#         ('CLIENT', 'Client Project'),
#         ('FIXED_PRICE', 'Fixed Price'),
#         ('TIME_MATERIALS', 'Time & Materials'),
#         ('RETAINER', 'Retainer'),
#     ]
    
#     # Project Information
#     project_number = models.CharField(max_length=50)
#     name = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
#     project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='CLIENT')
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    
#     # Customer & Financial
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='projects')
#     estimated_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     estimated_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
#     # Billing
#     billing_method = models.CharField(
#         max_length=20,
#         choices=[
#             ('HOURLY', 'Hourly Rate'),
#             ('FIXED', 'Fixed Price'),
#             ('MILESTONE', 'Milestone Based'),
#             ('EXPENSE_PLUS', 'Cost Plus'),
#         ],
#         default='HOURLY'
#     )
#     hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
#     # Dates
#     start_date = models.DateField()
#     estimated_end_date = models.DateField(null=True, blank=True)
#     actual_end_date = models.DateField(null=True, blank=True)
    
#     # Team
#     project_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#     team_members = models.ManyToManyField(User, through='ProjectTeamMember', blank=True)
    
#     # Progress
#     completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
#     # Settings
#     track_time = models.BooleanField(default=True)
#     track_expenses = models.BooleanField(default=True)
#     billable = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['-start_date']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'project_number'],
#                 name='unique_tenant_project_number'
#             ),
#         ]
        
#     def __str__(self):
#         return f'{self.project_number} - {self.name}'
    
#     def save(self, *args, **kwargs):
#         if not self.project_number:
#             self.project_number = self.generate_project_number()
#         super().save(*args, **kwargs)
    
#     def generate_project_number(self):
#         """Generate unique project number"""
#         return generate_code('PROJ', self.tenant_id)
    
#     @property
#     def gross_profit(self):
#         """Calculate gross profit"""
#         return self.actual_revenue - self.actual_cost
    
#     @property
#     def profit_margin(self):
#         """Calculate profit margin percentage"""
#         if self.actual_revenue > 0:
#             return (self.gross_profit / self.actual_revenue) * 100
#         return Decimal('0.00')
    
#     def update_financials(self):
#         """Update project financial summary"""
#         from .services import ProjectCostingService
        
#         service = ProjectCostingService(self.tenant)
#         service.update_project_costs(self)


# class ProjectTeamMember(TenantBaseModel):
#     """Project team member assignments"""
    
#     ROLE_CHOICES = [
#         ('MANAGER', 'Project Manager'),
#         ('LEAD', 'Team Lead'),
#         ('DEVELOPER', 'Developer'),
#         ('DESIGNER', 'Designer'),
#         ('ANALYST', 'Analyst'),
#         ('CONSULTANT', 'Consultant'),
#         ('OTHER', 'Other'),
#     ]
    
#     project = models.ForeignKey(Project, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OTHER')
#     hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     start_date = models.DateField()
#     end_date = models.DateField(null=True, blank=True)
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['project', 'role', 'user']
        
#     def __str__(self):
#         return f'{self.project.project_number} - {self.user.get_full_name()} ({self.role})'


# class Department(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced department/division tracking with budgets"""
    
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
    
#     # Hierarchy
#     parent_department = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
#     # Management
#     manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#     cost_center = models.CharField(max_length=50, blank=True)
    
#     # Budget Information
#     annual_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
#     current_year_actual = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Settings
#     is_active = models.BooleanField(default=True)
#     is_cost_center = models.BooleanField(default=True)
#     is_profit_center = models.BooleanField(default=False)
    
#     class Meta:
#         ordering = ['code']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'code'],
#                 name='unique_tenant_department_code'
#             ),
#         ]
        
#     def __str__(self):
#         return f'{self.code} - {self.name}'
    
#     @property
#     def budget_utilization(self):
#         """Calculate budget utilization percentage"""
#         if self.annual_budget and self.annual_budget > 0:
#             return (self.current_year_actual / self.annual_budget) * 100
#         return Decimal('0.00')
    
#     def get_budget_variance(self):
#         """Calculate budget variance"""
#         if self.annual_budget:
#             return self.current_year_actual - self.annual_budget
#         return Decimal('0.00')


# class Location(TenantBaseModel, SoftDeleteMixin):
#     """Enhanced location/branch tracking"""
    
#     LOCATION_TYPES = [
#         ('HEADQUARTERS', 'Headquarters'),
#         ('BRANCH', 'Branch Office'),
#         ('WAREHOUSE', 'Warehouse'),
#         ('RETAIL', 'Retail Store'),
#         ('MANUFACTURING', 'Manufacturing'),
#         ('REMOTE', 'Remote Location'),
#     ]
    
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=100)
#     location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='BRANCH')
    
#     # Address
#     address = models.JSONField(default=dict)
#     timezone = models.CharField(max_length=50, blank=True)
    
#     # Management
#     manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
#     # Financial
#     is_profit_center = models.BooleanField(default=False)
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
    
#     # Settings
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         ordering = ['code']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['tenant', 'code'],
#                 name='unique_tenant_location_code'
#             ),
#         ]
        
#     def __str__(self):
#         return f'{self.code} - {self.name}'


# # ============================================================================
# # FINANCIAL REPORTING & ANALYTICS
# # ============================================================================

# class BudgetTemplate(TenantBaseModel):
#     """Budget templates for different entities"""
    
#     TEMPLATE_TYPES = [
#         ('ANNUAL', 'Annual Budget'),
#         ('QUARTERLY', 'Quarterly Budget'),
#         ('MONTHLY', 'Monthly Budget'),
#         ('PROJECT', 'Project Budget'),
#         ('DEPARTMENT', 'Department Budget'),
#     ]
    
#     name = models.CharField(max_length=200)
#     template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
#     description = models.TextField(blank=True)
#     is_active = models.BooleanField(default=True)
    
#     # Template Settings
#     accounts = models.ManyToManyField(Account, through='BudgetTemplateItem')
    
#     class Meta:
#         ordering = ['name']
        
#     def __str__(self):
#         return self.name


# class BudgetTemplateItem(TenantBaseModel):
#     """Individual accounts in budget templates"""
    
#     template = models.ForeignKey(BudgetTemplate, on_delete=models.CASCADE)
#     account = models.ForeignKey(Account, on_delete=models.CASCADE)
#     budget_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     notes = models.TextField(blank=True)
    
#     class Meta:
#         ordering = ['template', 'account']
        
#     def __str__(self):
#         return f'{self.template.name} - {self.account.name}'


# class Budget(TenantBaseModel):
#     """Actual budgets for specific periods"""
    
#     name = models.CharField(max_length=200)
#     fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE)
#     start_date = models.DateField()
#     end_date = models.DateField()
    
#     # Budget Details
#     total_revenue_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     total_expense_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     net_income_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     # Status
#     is_approved = models.BooleanField(default=False)
#     approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#     approved_date = models.DateTimeField(null=True, blank=True)
    
#     # Template Reference
#     template = models.ForeignKey(BudgetTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
#     class Meta:
#         ordering = ['-start_date']
        
#     def __str__(self):
#         return f'{self.name} ({self.start_date} to {self.end_date})'


# class BudgetItem(TenantBaseModel):
#     """Individual budget line items"""
    
#     budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_items')
#     account = models.ForeignKey(Account, on_delete=models.CASCADE)
    
#     # Budget Amounts (can be monthly breakdown)
#     january = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     february = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     march = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     april = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     may = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     june = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     july = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     august = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     september = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     october = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     november = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     december = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
#     total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     notes = models.TextField(blank=True)
    
#     class Meta:
#         ordering = ['budget', 'account']
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['budget', 'account'],
#                 name='unique_budget_account'
#             ),
#         ]
        
#     def save(self, *args, **kwargs):
#         # Calculate total budget
#         self.total_budget = (
#             self.january + self.february + self.march + self.april +
#             self.may + self.june + self.july + self.august +
#             self.september + self.october + self.november + self.december
#         )
#         super().save(*args, **kwargs)
    
#     def __str__(self):
#         return f'{self.budget.name} - {self.account.name}'


# # Model registration for admin and apps
# __all__ = [
#     # Core Configuration
#     'FinanceSettings', 'FiscalYear', 'FinancialPeriod',
    
#     # Multi-Currency
#     'Currency', 'ExchangeRate',
    
#     # Chart of Accounts
#     'AccountCategory', 'Account',
    
#     # Tax Management
#     'TaxCode', 'TaxGroup', 'TaxGroupItem',
    
#     # Journal Entries
#     'JournalEntry', 'JournalEntryLine',
    
#     # Inventory Costing
#     'InventoryCostLayer', 'InventoryCostConsumption', 'LandedCost', 'LandedCostAllocation',
    
#     # Bank Reconciliation
#     'BankAccount', 'BankStatement', 'BankTransaction', 'BankReconciliation',
    
#     # Vendors & Purchases
#     'Vendor', 'VendorContact', 'Bill', 'BillItem',
    
#     # Customers & Sales
#     'Invoice', 'InvoiceItem',
    
#     # Payments
#     'Payment', 'PaymentApplication',
    
#     # CRM Integration
#     'CustomerFinancialProfile', 'LeadFinancialData',
    
#     # Project & Organization
#     'Project', 'ProjectTeamMember', 'Department', 'Location',
    
#     # Budgeting
#     'BudgetTemplate', 'BudgetTemplateItem', 'Budget', 'BudgetItem',
# ]
