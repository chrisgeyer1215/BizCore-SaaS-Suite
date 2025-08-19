"""
Finance Services - Core Accounting Service
Advanced accounting operations with multi-currency and multi-tenant support
"""

from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Sum, Case, When, DecimalField, Value
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any, Union

from apps.core.utils import generate_code
from ..models import (
    Account, AccountCategory, JournalEntry, JournalEntryLine,
    Currency, ExchangeRate, FinanceSettings, FiscalYear, FinancialPeriod,
    TaxCode, Invoice, Bill, Payment, Customer, Vendor,
    InventoryCostLayer, Project, Department, Location
)


logger = logging.getLogger(__name__)


class AccountingService:
    """Core accounting service for financial operations and calculations"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
        self.base_currency = self._get_base_currency()
        self.current_fiscal_year = self._get_current_fiscal_year()
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
            # Create default settings
            return FinanceSettings.objects.create(
                tenant=self.tenant,
                company_name=f"{self.tenant.name} Inc.",
                base_currency='USD',
                accounting_method='ACCRUAL'
            )
    
    def _get_base_currency(self):
        """Get base currency for tenant"""
        try:
            return Currency.objects.get(
                tenant=self.tenant,
                code=self.settings.base_currency,
                is_active=True
            )
        except Currency.DoesNotExist:
            # Create default base currency
            return Currency.objects.create(
                tenant=self.tenant,
                code=self.settings.base_currency,
                name='US Dollar',
                symbol='$',
                decimal_places=2,
                is_active=True,
                is_base_currency=True
            )
    
    def _get_current_fiscal_year(self):
        """Get current fiscal year"""
        try:
            return FiscalYear.objects.get(
                tenant=self.tenant,
                start_date__lte=date.today(),
                end_date__gte=date.today()
            )
        except FiscalYear.DoesNotExist:
            # Create current fiscal year if not exists
            current_year = date.today().year
            start_month = self.settings.fiscal_year_start_month
            
            if date.today().month >= start_month:
                fiscal_year = current_year
            else:
                fiscal_year = current_year - 1
            
            start_date = date(fiscal_year, start_month, 1)
            end_date = date(fiscal_year + 1, start_month - 1, 1) - timedelta(days=1)
            
            return FiscalYear.objects.create(
                tenant=self.tenant,
                year=fiscal_year,
                start_date=start_date,
                end_date=end_date,
                status='OPEN'
            )
    
    # ============================================================================
    # ACCOUNT MANAGEMENT
    # ============================================================================
    
    def get_account_balance(self, account_id: int, as_of_date: date = None, 
                          currency_code: str = None, include_unposted: bool = False) -> Decimal:
        """
        Get account balance as of specific date with optional currency conversion
        
        Args:
            account_id: Account ID
            as_of_date: Date to calculate balance (defaults to today)
            currency_code: Currency to convert to (defaults to base currency)
            include_unposted: Include draft journal entries
        
        Returns:
            Account balance in specified currency
        """
        if not as_of_date:
            as_of_date = date.today()
        
        try:
            account = Account.objects.get(id=account_id, tenant=self.tenant)
        except Account.DoesNotExist:
            raise ValidationError(f"Account {account_id} not found")
        
        # Build query for journal entry lines
        journal_lines_query = JournalEntryLine.objects.filter(
            tenant=self.tenant,
            account=account,
            journal_entry__entry_date__lte=as_of_date
        )
        
        # Filter by status
        if include_unposted:
            journal_lines_query = journal_lines_query.filter(
                journal_entry__status__in=['POSTED', 'DRAFT']
            )
        else:
            journal_lines_query = journal_lines_query.filter(
                journal_entry__status='POSTED'
            )
        
        # Calculate balance based on account type
        balance_data = journal_lines_query.aggregate(
            total_debits=Sum('base_currency_debit_amount'),
            total_credits=Sum('base_currency_credit_amount')
        )
        
        total_debits = balance_data['total_debits'] or Decimal('0.00')
        total_credits = balance_data['total_credits'] or Decimal('0.00')
        
        # Calculate net balance based on normal balance
        if account.normal_balance == 'DEBIT':
            net_balance = total_debits - total_credits
        else:
            net_balance = total_credits - total_debits
        
        # Add opening balance if applicable
        if account.opening_balance_date and account.opening_balance_date <= as_of_date:
            net_balance += account.opening_balance
        
        # Convert currency if requested
        if currency_code and currency_code != self.base_currency.code:
            target_currency = Currency.objects.get(
                tenant=self.tenant,
                code=currency_code
            )
            exchange_rate = self._get_exchange_rate(
                self.base_currency, target_currency, as_of_date
            )
            net_balance = net_balance / exchange_rate
        
        return net_balance
    
    def get_trial_balance(self, as_of_date: date = None, 
                         include_zero_balances: bool = False) -> Dict:
        """
        Generate trial balance for all accounts
        
        Args:
            as_of_date: Date for trial balance (defaults to today)
            include_zero_balances: Include accounts with zero balance
        
        Returns:
            Dictionary with trial balance data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all active accounts
        accounts = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('code')
        
        trial_balance_data = []
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for account in accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            
            # Skip zero balances if not requested
            if not include_zero_balances and balance == Decimal('0.00'):
                continue
            
            # Determine debit/credit presentation
            if account.normal_balance == 'DEBIT':
                debit_balance = balance if balance > 0 else Decimal('0.00')
                credit_balance = abs(balance) if balance < 0 else Decimal('0.00')
            else:
                credit_balance = balance if balance > 0 else Decimal('0.00')
                debit_balance = abs(balance) if balance < 0 else Decimal('0.00')
            
            trial_balance_data.append({
                'account_code': account.code,
                'account_name': account.name,
                'account_type': account.account_type,
                'account_category': account.category.name if account.category else '',
                'debit_balance': debit_balance,
                'credit_balance': credit_balance,
                'balance': balance,
                'normal_balance': account.normal_balance
            })
            
            total_debits += debit_balance
            total_credits += credit_balance
        
        return {
            'as_of_date': as_of_date,
            'accounts': trial_balance_data,
            'totals': {
                'total_debits': total_debits,
                'total_credits': total_credits,
                'difference': total_debits - total_credits,
                'is_balanced': abs(total_debits - total_credits) < Decimal('0.01')
            },
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def get_account_activity(self, account_id: int, start_date: date, 
                           end_date: date, include_details: bool = True) -> Dict:
        """
        Get detailed account activity for a period
        
        Args:
            account_id: Account ID
            start_date: Period start date
            end_date: Period end date
            include_details: Include transaction details
        
        Returns:
            Dictionary with account activity
        """
        try:
            account = Account.objects.get(id=account_id, tenant=self.tenant)
        except Account.DoesNotExist:
            raise ValidationError(f"Account {account_id} not found")
        
        # Get opening balance
        opening_balance = self.get_account_balance(account_id, start_date - timedelta(days=1))
        
        # Get journal lines for period
        journal_lines = JournalEntryLine.objects.filter(
            tenant=self.tenant,
            account=account,
            journal_entry__status='POSTED',
            journal_entry__entry_date__gte=start_date,
            journal_entry__entry_date__lte=end_date
        ).select_related(
            'journal_entry', 'customer', 'vendor', 'product', 'project'
        ).order_by('journal_entry__entry_date', 'journal_entry__entry_number', 'line_number')
        
        # Calculate period totals
        period_data = journal_lines.aggregate(
            period_debits=Sum('base_currency_debit_amount'),
            period_credits=Sum('base_currency_credit_amount')
        )
        
        period_debits = period_data['period_debits'] or Decimal('0.00')
        period_credits = period_data['period_credits'] or Decimal('0.00')
        
        # Calculate net change
        if account.normal_balance == 'DEBIT':
            net_change = period_debits - period_credits
        else:
            net_change = period_credits - period_debits
        
        closing_balance = opening_balance + net_change
        
        result = {
            'account': {
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'type': account.account_type,
                'normal_balance': account.normal_balance
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'opening_balance': opening_balance,
                'period_debits': period_debits,
                'period_credits': period_credits,
                'net_change': net_change,
                'closing_balance': closing_balance
            },
            'transaction_count': journal_lines.count()
        }
        
        # Add transaction details if requested
        if include_details:
            transactions = []
            running_balance = opening_balance
            
            for line in journal_lines:
                # Calculate running balance
                if account.normal_balance == 'DEBIT':
                    running_balance += line.base_currency_debit_amount - line.base_currency_credit_amount
                else:
                    running_balance += line.base_currency_credit_amount - line.base_currency_debit_amount
                
                transactions.append({
                    'date': line.journal_entry.entry_date,
                    'entry_number': line.journal_entry.entry_number,
                    'entry_type': line.journal_entry.entry_type,
                    'description': line.description,
                    'debit_amount': line.base_currency_debit_amount,
                    'credit_amount': line.base_currency_credit_amount,
                    'running_balance': running_balance,
                    'source_document': line.journal_entry.source_document_number,
                    'reference': line.journal_entry.reference_number,
                    'customer': line.customer.name if line.customer else None,
                    'vendor': line.vendor.company_name if line.vendor else None,
                    'project': line.project.name if line.project else None
                })
            
            result['transactions'] = transactions
        
        return result
    
    # ============================================================================
    # FINANCIAL STATEMENTS
    # ============================================================================
    
    def generate_balance_sheet(self, as_of_date: date = None, 
                             comparative: bool = False, 
                             prior_date: date = None) -> Dict:
        """
        Generate balance sheet
        
        Args:
            as_of_date: Balance sheet date (defaults to today)
            comparative: Include comparative figures
            prior_date: Prior period date for comparison
        
        Returns:
            Balance sheet data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        if comparative and not prior_date:
            prior_date = as_of_date - timedelta(days=365)  # Prior year
        
        # Define balance sheet account types
        asset_types = ['ASSET', 'CURRENT_ASSET', 'FIXED_ASSET', 'OTHER_ASSET']
        liability_types = ['LIABILITY', 'CURRENT_LIABILITY', 'LONG_TERM_LIABILITY']
        equity_types = ['EQUITY', 'RETAINED_EARNINGS']
        
        def get_accounts_by_types(account_types):
            return Account.objects.filter(
                tenant=self.tenant,
                account_type__in=account_types,
                is_active=True
            ).order_by('account_type', 'code')
        
        def build_section(accounts, date_for_balance):
            section_data = []
            section_total = Decimal('0.00')
            
            for account in accounts:
                balance = self.get_account_balance(account.id, date_for_balance)
                
                if balance != Decimal('0.00'):  # Only include non-zero balances
                    account_data = {
                        'account_code': account.code,
                        'account_name': account.name,
                        'account_type': account.account_type,
                        'balance': balance,
                        'level': account.level or 0
                    }
                    
                    if comparative:
                        prior_balance = self.get_account_balance(account.id, prior_date)
                        account_data['prior_balance'] = prior_balance
                        account_data['change'] = balance - prior_balance
                    
                    section_data.append(account_data)
                    section_total += balance
            
            return section_data, section_total
        
        # Build balance sheet sections
        assets, total_assets = build_section(get_accounts_by_types(asset_types), as_of_date)
        liabilities, total_liabilities = build_section(get_accounts_by_types(liability_types), as_of_date)
        equity, total_equity = build_section(get_accounts_by_types(equity_types), as_of_date)
        
        # Add retained earnings calculation if not explicitly tracked
        if not any(acc['account_type'] == 'RETAINED_EARNINGS' for acc in equity):
            retained_earnings = self.calculate_retained_earnings(as_of_date)
            if retained_earnings != Decimal('0.00'):
                re_data = {
                    'account_code': 'RE',
                    'account_name': 'Retained Earnings',
                    'account_type': 'RETAINED_EARNINGS',
                    'balance': retained_earnings,
                    'level': 0
                }
                
                if comparative:
                    prior_re = self.calculate_retained_earnings(prior_date)
                    re_data['prior_balance'] = prior_re
                    re_data['change'] = retained_earnings - prior_re
                
                equity.append(re_data)
                total_equity += retained_earnings
        
        result = {
            'company_name': self.settings.company_name,
            'statement_name': 'Balance Sheet',
            'as_of_date': as_of_date,
            'currency': self.base_currency.code,
            'generated_at': timezone.now(),
            'assets': {
                'accounts': assets,
                'total': total_assets
            },
            'liabilities': {
                'accounts': liabilities,
                'total': total_liabilities
            },
            'equity': {
                'accounts': equity,
                'total': total_equity
            },
            'totals': {
                'total_liabilities_and_equity': total_liabilities + total_equity,
                'balance_check': total_assets - (total_liabilities + total_equity),
                'is_balanced': abs(total_assets - (total_liabilities + total_equity)) < Decimal('0.01')
            }
        }
        
        if comparative:
            result['comparative'] = True
            result['prior_date'] = prior_date
        
        return result
    
    def generate_income_statement(self, start_date: date, end_date: date,
                                comparative: bool = False,
                                prior_start_date: date = None,
                                prior_end_date: date = None) -> Dict:
        """
        Generate income statement (P&L)
        
        Args:
            start_date: Period start date
            end_date: Period end date
            comparative: Include comparative figures
            prior_start_date: Prior period start date
            prior_end_date: Prior period end date
        
        Returns:
            Income statement data
        """
        if comparative and not (prior_start_date and prior_end_date):
            # Default to same period prior year
            days_diff = (end_date - start_date).days
            prior_end_date = end_date - timedelta(days=365)
            prior_start_date = prior_end_date - timedelta(days=days_diff)
        
        # Define income statement account types
        revenue_types = ['REVENUE', 'OTHER_INCOME']
        expense_types = ['EXPENSE', 'OTHER_EXPENSE']
        cogs_types = ['COST_OF_GOODS_SOLD']
        
        def get_period_activity(account_types, start_dt, end_dt):
            accounts = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=account_types,
                is_active=True
            ).order_by('account_type', 'code')
            
            section_data = []
            section_total = Decimal('0.00')
            
            for account in accounts:
                activity = self.get_account_activity(
                    account.id, start_dt, end_dt, include_details=False
                )
                
                # For income statement, we want the net change (activity for period)
                net_change = activity['summary']['net_change']
                
                if net_change != Decimal('0.00'):
                    account_data = {
                        'account_code': account.code,
                        'account_name': account.name,
                        'account_type': account.account_type,
                        'amount': net_change,
                        'level': account.level or 0
                    }
                    
                    section_data.append(account_data)
                    section_total += net_change
            
            return section_data, section_total
        
        # Build income statement sections
        revenue, total_revenue = get_period_activity(revenue_types, start_date, end_date)
        cogs, total_cogs = get_period_activity(cogs_types, start_date, end_date)
        expenses, total_expenses = get_period_activity(expense_types, start_date, end_date)
        
        # Calculate key metrics
        gross_profit = total_revenue - total_cogs
        operating_income = gross_profit - total_expenses
        net_income = operating_income  # Simplified - could include other income/expenses
        
        result = {
            'company_name': self.settings.company_name,
            'statement_name': 'Income Statement',
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'currency': self.base_currency.code,
            'generated_at': timezone.now(),
            'revenue': {
                'accounts': revenue,
                'total': total_revenue
            },
            'cost_of_goods_sold': {
                'accounts': cogs,
                'total': total_cogs
            },
            'expenses': {
                'accounts': expenses,
                'total': total_expenses
            },
            'metrics': {
                'gross_profit': gross_profit,
                'gross_margin_percent': (gross_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00'),
                'operating_income': operating_income,
                'operating_margin_percent': (operating_income / total_revenue * 100) if total_revenue > 0 else Decimal('0.00'),
                'net_income': net_income,
                'net_margin_percent': (net_income / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')
            }
        }
        
        # Add comparative data if requested
        if comparative:
            prior_revenue, prior_total_revenue = get_period_activity(revenue_types, prior_start_date, prior_end_date)
            prior_cogs, prior_total_cogs = get_period_activity(cogs_types, prior_start_date, prior_end_date)
            prior_expenses, prior_total_expenses = get_period_activity(expense_types, prior_start_date, prior_end_date)
            
            prior_gross_profit = prior_total_revenue - prior_total_cogs
            prior_operating_income = prior_gross_profit - prior_total_expenses
            prior_net_income = prior_operating_income
            
            result['comparative'] = {
                'period': {
                    'start_date': prior_start_date,
                    'end_date': prior_end_date
                },
                'revenue': {
                    'accounts': prior_revenue,
                    'total': prior_total_revenue
                },
                'cost_of_goods_sold': {
                    'accounts': prior_cogs,
                    'total': prior_total_cogs
                },
                'expenses': {
                    'accounts': prior_expenses,
                    'total': prior_total_expenses
                },
                'metrics': {
                    'gross_profit': prior_gross_profit,
                    'operating_income': prior_operating_income,
                    'net_income': prior_net_income
                }
            }
            
            # Add variance calculations
            result['variance'] = {
                'revenue_change': total_revenue - prior_total_revenue,
                'revenue_change_percent': ((total_revenue - prior_total_revenue) / prior_total_revenue * 100) if prior_total_revenue > 0 else Decimal('0.00'),
                'gross_profit_change': gross_profit - prior_gross_profit,
                'operating_income_change': operating_income - prior_operating_income,
                'net_income_change': net_income - prior_net_income
            }
        
        return result
    
    def calculate_retained_earnings(self, as_of_date: date = None) -> Decimal:
        """
        Calculate retained earnings (accumulated net income)
        
        Args:
            as_of_date: Date to calculate retained earnings
        
        Returns:
            Retained earnings amount
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all revenue and expense accounts
        revenue_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type__in=['REVENUE', 'OTHER_INCOME'],
            is_active=True
        )
        
        expense_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'],
            is_active=True
        )
        
        total_revenue = Decimal('0.00')
        total_expenses = Decimal('0.00')
        
        # Calculate total revenue (from beginning of time to as_of_date)
        for account in revenue_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_revenue += balance
        
        # Calculate total expenses (from beginning of time to as_of_date)
        for account in expense_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_expenses += balance
        
        return total_revenue - total_expenses
    
    # ============================================================================
    # CURRENCY OPERATIONS
    # ============================================================================
    
    def _get_exchange_rate(self, from_currency: Currency, to_currency: Currency, 
                          rate_date: date = None) -> Decimal:
        """Get exchange rate between currencies"""
        if from_currency.id == to_currency.id:
            return Decimal('1.000000')
        
        if not rate_date:
            rate_date = date.today()
        
        return ExchangeRate.get_rate(
            self.tenant, from_currency, to_currency, rate_date
        )
    
    def convert_currency(self, amount: Decimal, from_currency_code: str, 
                        to_currency_code: str, rate_date: date = None) -> Decimal:
        """
        Convert amount from one currency to another
        
        Args:
            amount: Amount to convert
            from_currency_code: Source currency code
            to_currency_code: Target currency code
            rate_date: Date for exchange rate
        
        Returns:
            Converted amount
        """
        if from_currency_code == to_currency_code:
            return amount
        
        try:
            from_currency = Currency.objects.get(
                tenant=self.tenant,
                code=from_currency_code
            )
            to_currency = Currency.objects.get(
                tenant=self.tenant,
                code=to_currency_code
            )
        except Currency.DoesNotExist as e:
            raise ValidationError(f"Currency not found: {str(e)}")
        
        exchange_rate = self._get_exchange_rate(from_currency, to_currency, rate_date)
        return amount * exchange_rate
    
    # ============================================================================
    # AGING REPORTS
    # ============================================================================
    
    def generate_ar_aging_report(self, as_of_date: date = None, 
                                aging_periods: List[int] = None) -> Dict:
        """
        Generate Accounts Receivable aging report
        
        Args:
            as_of_date: Aging as of date (defaults to today)
            aging_periods: Aging bucket periods [30, 60, 90, 120]
        
        Returns:
            AR aging report data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        if not aging_periods:
            aging_periods = [30, 60, 90, 120]  # Standard aging periods
        
        # Get all open invoices
        open_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=Decimal('0.00')
        ).select_related('customer').order_by('customer__name', 'due_date')
        
        aging_data = []
        customer_totals = {}
        
        for invoice in open_invoices:
            days_outstanding = (as_of_date - invoice.due_date).days
            
            # Determine aging bucket
            if days_outstanding <= 0:
                bucket = 'current'
            elif days_outstanding <= aging_periods[0]:
                bucket = f'1-{aging_periods[0]}'
            elif days_outstanding <= aging_periods[1]:
                bucket = f'{aging_periods[0]+1}-{aging_periods[1]}'
            elif days_outstanding <= aging_periods[2]:
                bucket = f'{aging_periods[1]+1}-{aging_periods[2]}'
            elif days_outstanding <= aging_periods[3]:
                bucket = f'{aging_periods[2]+1}-{aging_periods[3]}'
            else:
                bucket = f'over_{aging_periods[3]}'
            
            customer_key = invoice.customer.id
            if customer_key not in customer_totals:
                customer_totals[customer_key] = {
                    'customer_id': invoice.customer.id,
                    'customer_name': invoice.customer.name,
                    'customer_email': invoice.customer.email,
                    'total_outstanding': Decimal('0.00'),
                    'current': Decimal('0.00'),
                    f'1-{aging_periods[0]}': Decimal('0.00'),
                    f'{aging_periods[0]+1}-{aging_periods[1]}': Decimal('0.00'),
                    f'{aging_periods[1]+1}-{aging_periods[2]}': Decimal('0.00'),
                    f'{aging_periods[2]+1}-{aging_periods[3]}': Decimal('0.00'),
                    f'over_{aging_periods[3]}': Decimal('0.00'),
                    'invoices': []
                }
            
            # Add to customer totals
            customer_totals[customer_key]['total_outstanding'] += invoice.amount_due
            customer_totals[customer_key][bucket] += invoice.amount_due
            
            # Add invoice details
            customer_totals[customer_key]['invoices'].append({
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date,
                'due_date': invoice.due_date,
                'total_amount': invoice.total_amount,
                'amount_due': invoice.amount_due,
                'days_outstanding': days_outstanding,
                'aging_bucket': bucket
            })
        
        # Calculate report totals
        report_totals = {
            'total_outstanding': Decimal('0.00'),
            'current': Decimal('0.00'),
            f'1-{aging_periods[0]}': Decimal('0.00'),
            f'{aging_periods[0]+1}-{aging_periods[1]}': Decimal('0.00'),
            f'{aging_periods[1]+1}-{aging_periods[2]}': Decimal('0.00'),
            f'{aging_periods[2]+1}-{aging_periods[3]}': Decimal('0.00'),
            f'over_{aging_periods[3]}': Decimal('0.00')
        }
        
        for customer_data in customer_totals.values():
            aging_data.append(customer_data)
            for bucket in report_totals.keys():
                report_totals[bucket] += customer_data.get(bucket, Decimal('0.00'))
        
        return {
            'report_name': 'Accounts Receivable Aging',
            'as_of_date': as_of_date,
            'currency': self.base_currency.code,
            'aging_periods': aging_periods,
            'customers': sorted(aging_data, key=lambda x: x['customer_name']),
            'totals': report_totals,
            'summary': {
                'total_customers': len(aging_data),
                'total_invoices': sum(len(customer['invoices']) for customer in aging_data),
                'average_days_outstanding': self._calculate_weighted_average_days_outstanding(aging_data),
                'past_due_amount': sum(
                    report_totals[bucket] for bucket in report_totals.keys() 
                    if bucket != 'current'
                ),
                'past_due_percentage': (
                    sum(report_totals[bucket] for bucket in report_totals.keys() if bucket != 'current') /
                    report_totals['total_outstanding'] * 100
                ) if report_totals['total_outstanding'] > 0 else Decimal('0.00')
            },
            'generated_at': timezone.now()
        }
    
    def generate_ap_aging_report(self, as_of_date: date = None, 
                                aging_periods: List[int] = None) -> Dict:
        """
        Generate Accounts Payable aging report
        
        Args:
            as_of_date: Aging as of date (defaults to today)
            aging_periods: Aging bucket periods [30, 60, 90, 120]
        
        Returns:
            AP aging report data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        if not aging_periods:
            aging_periods = [30, 60, 90, 120]
        
        # Get all open bills
        open_bills = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=Decimal('0.00')
        ).select_related('vendor').order_by('vendor__company_name', 'due_date')
        
        aging_data = []
        vendor_totals = {}
        
        for bill in open_bills:
            days_outstanding = (as_of_date - bill.due_date).days
            
            # Determine aging bucket
            if days_outstanding <= 0:
                bucket = 'current'
            elif days_outstanding <= aging_periods[0]:
                bucket = f'1-{aging_periods[0]}'
            elif days_outstanding <= aging_periods[1]:
                bucket = f'{aging_periods[0]+1}-{aging_periods[1]}'
            elif days_outstanding <= aging_periods[2]:
                bucket = f'{aging_periods[1]+1}-{aging_periods[2]}'
            elif days_outstanding <= aging_periods[3]:
                bucket = f'{aging_periods[2]+1}-{aging_periods[3]}'
            else:
                bucket = f'over_{aging_periods[3]}'
            
            vendor_key = bill.vendor.id
            if vendor_key not in vendor_totals:
                vendor_totals[vendor_key] = {
                    'vendor_id': bill.vendor.id,
                    'vendor_name': bill.vendor.company_name,
                    'vendor_email': bill.vendor.email,
                    'total_outstanding': Decimal('0.00'),
                    'current': Decimal('0.00'),
                    f'1-{aging_periods[0]}': Decimal('0.00'),
                    f'{aging_periods[0]+1}-{aging_periods[1]}': Decimal('0.00'),
                    f'{aging_periods[1]+1}-{aging_periods[2]}': Decimal('0.00'),
                    f'{aging_periods[2]+1}-{aging_periods[3]}': Decimal('0.00'),
                    f'over_{aging_periods[3]}': Decimal('0.00'),
                    'bills': []
                }
            
            # Add to vendor totals
            vendor_totals[vendor_key]['total_outstanding'] += bill.amount_due
            vendor_totals[vendor_key][bucket] += bill.amount_due
            
            # Add bill details
            vendor_totals[vendor_key]['bills'].append({
                'bill_number': bill.bill_number,
                'vendor_invoice_number': bill.vendor_invoice_number,
                'bill_date': bill.bill_date,
                'due_date': bill.due_date,
                'total_amount': bill.total_amount,
                'amount_due': bill.amount_due,
                'days_outstanding': days_outstanding,
                'aging_bucket': bucket
            })
        
        # Calculate report totals
        report_totals = {
            'total_outstanding': Decimal('0.00'),
            'current': Decimal('0.00'),
            f'1-{aging_periods[0]}': Decimal('0.00'),
            f'{aging_periods[0]+1}-{aging_periods[1]}': Decimal('0.00'),
            f'{aging_periods[1]+1}-{aging_periods[2]}': Decimal('0.00'),
            f'{aging_periods[2]+1}-{aging_periods[3]}': Decimal('0.00'),
            f'over_{aging_periods[3]}': Decimal('0.00')
        }
        
        for vendor_data in vendor_totals.values():
            aging_data.append(vendor_data)
            for bucket in report_totals.keys():
                report_totals[bucket] += vendor_data.get(bucket, Decimal('0.00'))
        
        return {
            'report_name': 'Accounts Payable Aging',
            'as_of_date': as_of_date,
            'currency': self.base_currency.code,
            'aging_periods': aging_periods,
            'vendors': sorted(aging_data, key=lambda x: x['vendor_name']),
            'totals': report_totals,
            'summary': {
                'total_vendors': len(aging_data),
                'total_bills': sum(len(vendor['bills']) for vendor in aging_data),
                'average_days_outstanding': self._calculate_weighted_average_days_outstanding(aging_data, 'bills'),
                'past_due_amount': sum(
                    report_totals[bucket] for bucket in report_totals.keys() 
                    if bucket != 'current'
                ),
                'past_due_percentage': (
                    sum(report_totals[bucket] for bucket in report_totals.keys() if bucket != 'current') /
                    report_totals['total_outstanding'] * 100
                ) if report_totals['total_outstanding'] > 0 else Decimal('0.00')
            },
            'generated_at': timezone.now()
        }
    
    def _calculate_weighted_average_days_outstanding(self, aging_data: List[Dict], 
                                                   document_key: str = 'invoices') -> Decimal:
        """Calculate weighted average days outstanding"""
        total_amount = Decimal('0.00')
        weighted_days = Decimal('0.00')
        
        for entity_data in aging_data:
            for document in entity_data.get(document_key, []):
                amount = document['amount_due']
                days = document['days_outstanding']
                total_amount += amount
                weighted_days += amount * days
        
        if total_amount > 0:
            return weighted_days / total_amount
        return Decimal('0.00')
    
    # ============================================================================
    # FINANCIAL RATIOS & ANALYTICS
    # ============================================================================
    
    def calculate_financial_ratios(self, as_of_date: date = None, 
                                 period_start: date = None, 
                                 period_end: date = None) -> Dict:
        """
        Calculate key financial ratios
        
        Args:
            as_of_date: Balance sheet date
            period_start: Income statement period start
            period_end: Income statement period end
        
        Returns:
            Dictionary with financial ratios
        """
        if not as_of_date:
            as_of_date = date.today()
        
        if not period_end:
            period_end = as_of_date
        
        if not period_start:
            period_start = date(as_of_date.year, 1, 1)  # YTD
        
        # Get balance sheet data
        balance_sheet = self.generate_balance_sheet(as_of_date)
        
        # Get income statement data
        income_statement = self.generate_income_statement(period_start, period_end)
        
        # Extract key figures
        total_assets = balance_sheet['assets']['total']
        current_assets = sum(
            acc['balance'] for acc in balance_sheet['assets']['accounts']
            if acc['account_type'] == 'CURRENT_ASSET'
        )
        current_liabilities = sum(
            acc['balance'] for acc in balance_sheet['liabilities']['accounts']
            if acc['account_type'] == 'CURRENT_LIABILITY'
        )
        total_liabilities = balance_sheet['liabilities']['total']
        total_equity = balance_sheet['equity']['total']
        
        total_revenue = income_statement['revenue']['total']
        gross_profit = income_statement['metrics']['gross_profit']
        net_income = income_statement['metrics']['net_income']
        
        # Calculate ratios
        ratios = {}
        
        # Liquidity Ratios
        ratios['liquidity'] = {
            'current_ratio': current_assets / current_liabilities if current_liabilities > 0 else None,
            'quick_ratio': (current_assets - self._get_inventory_value(as_of_date)) / current_liabilities if current_liabilities > 0 else None,
            'cash_ratio': self._get_cash_and_equivalents(as_of_date) / current_liabilities if current_liabilities > 0 else None
        }
        
        # Leverage Ratios
        ratios['leverage'] = {
            'debt_to_equity': total_liabilities / total_equity if total_equity > 0 else None,
            'debt_to_assets': total_liabilities / total_assets if total_assets > 0 else None,
            'equity_ratio': total_equity / total_assets if total_assets > 0 else None
        }
        
        # Profitability Ratios
        ratios['profitability'] = {
            'gross_margin': gross_profit / total_revenue * 100 if total_revenue > 0 else Decimal('0.00'),
            'net_margin': net_income / total_revenue * 100 if total_revenue > 0 else Decimal('0.00'),
            'return_on_assets': net_income / total_assets * 100 if total_assets > 0 else Decimal('0.00'),
            'return_on_equity': net_income / total_equity * 100 if total_equity > 0 else Decimal('0.00')
        }
        
        # Efficiency Ratios
        ar_balance = self._get_accounts_receivable_balance(as_of_date)
        ap_balance = self._get_accounts_payable_balance(as_of_date)
        inventory_value = self._get_inventory_value(as_of_date)
        cogs = abs(income_statement['cost_of_goods_sold']['total'])
        
        days_in_period = (period_end - period_start).days + 1
        
        ratios['efficiency'] = {
            'asset_turnover': total_revenue / total_assets if total_assets > 0 else None,
            'receivables_turnover': total_revenue / ar_balance if ar_balance > 0 else None,
            'days_sales_outstanding': (ar_balance / total_revenue * days_in_period) if total_revenue > 0 else None,
            'inventory_turnover': cogs / inventory_value if inventory_value > 0 else None,
            'days_inventory_outstanding': (inventory_value / cogs * days_in_period) if cogs > 0 else None,
            'payables_turnover': cogs / ap_balance if ap_balance > 0 else None,
            'days_payable_outstanding': (ap_balance / cogs * days_in_period) if cogs > 0 else None
        }
        
        # Cash Conversion Cycle
        dso = ratios['efficiency']['days_sales_outstanding'] or Decimal('0.00')
        dio = ratios['efficiency']['days_inventory_outstanding'] or Decimal('0.00')
        dpo = ratios['efficiency']['days_payable_outstanding'] or Decimal('0.00')
        
        ratios['cash_conversion_cycle'] = dso + dio - dpo
        
        return {
            'as_of_date': as_of_date,
            'period': {
                'start_date': period_start,
                'end_date': period_end
            },
            'ratios': ratios,
            'benchmarks': self._get_industry_benchmarks(),
            'interpretation': self._interpret_ratios(ratios),
            'generated_at': timezone.now()
        }
    
    def _get_inventory_value(self, as_of_date: date) -> Decimal:
        """Get total inventory value"""
        inventory_accounts = Account.objects.filter(
            tenant=self.tenant,
            track_inventory=True,
            is_active=True
        )
        
        total_inventory = Decimal('0.00')
        for account in inventory_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_inventory += balance
        
        return total_inventory
    
    def _get_cash_and_equivalents(self, as_of_date: date) -> Decimal:
        """Get cash and cash equivalents"""
        cash_accounts = Account.objects.filter(
            tenant=self.tenant,
            is_cash_account=True,
            is_active=True
        )
        
        total_cash = Decimal('0.00')
        for account in cash_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_cash += balance
        
        return total_cash
    
    def _get_accounts_receivable_balance(self, as_of_date: date) -> Decimal:
        """Get accounts receivable balance"""
        ar_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type='CURRENT_ASSET',
            name__icontains='Accounts Receivable',
            is_active=True
        )
        
        total_ar = Decimal('0.00')
        for account in ar_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_ar += balance
        
        return total_ar
    
    def _get_accounts_payable_balance(self, as_of_date: date) -> Decimal:
        """Get accounts payable balance"""
        ap_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type='CURRENT_LIABILITY',
            name__icontains='Accounts Payable',
            is_active=True
        )
        
        total_ap = Decimal('0.00')
        for account in ap_accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            total_ap += balance
        
        return total_ap
    
    def _get_industry_benchmarks(self) -> Dict:
        """Get industry benchmark ratios (placeholder - would integrate with external data)"""
        return {
            'current_ratio': {'good': 2.0, 'acceptable': 1.5, 'poor': 1.0},
            'debt_to_equity': {'good': 0.3, 'acceptable': 0.5, 'poor': 1.0},
            'gross_margin': {'good': 40.0, 'acceptable': 25.0, 'poor': 15.0},
            'net_margin': {'good': 10.0, 'acceptable': 5.0, 'poor': 2.0}
        }
    
    def _interpret_ratios(self, ratios: Dict) -> Dict:
        """Provide interpretation of key ratios"""
        interpretations = {}
        benchmarks = self._get_industry_benchmarks()
        
        # Current Ratio interpretation
        current_ratio = ratios['liquidity']['current_ratio']
        if current_ratio:
            if current_ratio >= benchmarks['current_ratio']['good']:
                interpretations['current_ratio'] = 'Excellent liquidity position'
            elif current_ratio >= benchmarks['current_ratio']['acceptable']:
                interpretations['current_ratio'] = 'Adequate liquidity position'
            else:
                interpretations['current_ratio'] = 'Poor liquidity - may have trouble paying short-term obligations'
        
        # Debt to Equity interpretation
        debt_to_equity = ratios['leverage']['debt_to_equity']
        if debt_to_equity:
            if debt_to_equity <= benchmarks['debt_to_equity']['good']:
                interpretations['debt_to_equity'] = 'Conservative debt levels'
            elif debt_to_equity <= benchmarks['debt_to_equity']['acceptable']:
                interpretations['debt_to_equity'] = 'Moderate debt levels'
            else:
                interpretations['debt_to_equity'] = 'High debt levels - may indicate financial risk'
        
        return interpretations
    
    # ============================================================================
    # PERIOD OPERATIONS
    # ============================================================================
    
    def close_accounting_period(self, period_end_date: date, user) -> Dict:
        """
        Close an accounting period
        
        Args:
            period_end_date: End date of period to close
            user: User performing the close
        
        Returns:
            Dictionary with closing results
        """
        try:
            with transaction.atomic():
                # Get or create financial period
                financial_period, created = FinancialPeriod.objects.get_or_create(
                    tenant=self.tenant,
                    end_date=period_end_date,
                    defaults={
                        'name': f"Period ending {period_end_date}",
                        'period_type': 'MONTH',
                        'fiscal_year': self.current_fiscal_year,
                        'start_date': date(period_end_date.year, period_end_date.month, 1)
                    }
                )
                
                if financial_period.status == 'CLOSED':
                    raise ValidationError(f"Period ending {period_end_date} is already closed")
                
                # Run pre-closing validations
                validation_results = self._validate_period_for_closing(period_end_date)
                if not validation_results['is_valid']:
                    raise ValidationError(f"Period validation failed: {validation_results['errors']}")
                
                # Calculate period totals
                income_statement = self.generate_income_statement(
                    financial_period.start_date, 
                    financial_period.end_date
                )
                
                # Update period with actual figures
                financial_period.actual_revenue = income_statement['revenue']['total']
                financial_period.actual_expenses = income_statement['expenses']['total'] + abs(income_statement['cost_of_goods_sold']['total'])
                financial_period.status = 'CLOSED'
                financial_period.closed_by = user
                financial_period.closed_date = timezone.now()
                financial_period.save()
                
                # Create period closing journal entry (if needed)
                closing_entry = self._create_period_closing_entry(financial_period, user)
                
                logger.info(f"Accounting period {financial_period.name} closed by {user}")
                
                return {
                    'success': True,
                    'period': financial_period,
                    'closing_entry': closing_entry,
                    'summary': {
                        'period_revenue': financial_period.actual_revenue,
                        'period_expenses': financial_period.actual_expenses,
                        'net_income': financial_period.actual_revenue - financial_period.actual_expenses
                    }
                }
                
        except Exception as e:
            logger.error(f"Error closing accounting period: {str(e)}")
            raise ValidationError(f"Failed to close period: {str(e)}")
    
    def _validate_period_for_closing(self, period_end_date: date) -> Dict:
        """Validate period is ready for closing"""
        errors = []
        
        # Check for unposted journal entries
        unposted_entries = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__lte=period_end_date,
            status='DRAFT'
        ).count()
        
        if unposted_entries > 0:
            errors.append(f"{unposted_entries} unposted journal entries found")
        
        # Check for unbalanced entries
        unbalanced_entries = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__lte=period_end_date,
            status='POSTED'
        ).exclude(
            total_debit=F('total_credit')
        ).count()
        
        if unbalanced_entries > 0:
            errors.append(f"{unbalanced_entries} unbalanced journal entries found")
        
        # Check for incomplete bank reconciliations
        # This would check bank reconciliation status
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def _create_period_closing_entry(self, financial_period, user):
        """Create period closing journal entry if needed"""
        # This would create any necessary closing entries
        # For now, return None as this is typically done at year-end
        return None
    
    # ============================================================================
    # VALIDATION & UTILITIES
    # ============================================================================
    
    def validate_accounting_equation(self, as_of_date: date = None) -> Dict:
        """
        Validate that Assets = Liabilities + Equity
        
        Args:
            as_of_date: Date to validate (defaults to today)
        
        Returns:
            Validation result
        """
        if not as_of_date:
            as_of_date = date.today()
        
        balance_sheet = self.generate_balance_sheet(as_of_date)
        
        assets = balance_sheet['assets']['total']
        liabilities = balance_sheet['liabilities']['total']
        equity = balance_sheet['equity']['total']
        
        difference = assets - (liabilities + equity)
        is_balanced = abs(difference) < Decimal('0.01')
        
        return {
            'is_balanced': is_balanced,
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'liabilities_plus_equity': liabilities + equity,
            'difference': difference,
            'as_of_date': as_of_date,
            'tolerance': Decimal('0.01')
        }
    
    def get_fiscal_year_summary(self, fiscal_year_id: int = None) -> Dict:
        """Get fiscal year financial summary"""
        if fiscal_year_id:
            fiscal_year = FiscalYear.objects.get(id=fiscal_year_id, tenant=self.tenant)
        else:
            fiscal_year = self.current_fiscal_year
        
        # Generate income statement for the fiscal year
        income_statement = self.generate_income_statement(
            fiscal_year.start_date,
            fiscal_year.end_date
        )
        
        # Generate balance sheet as of fiscal year end
        balance_sheet = self.generate_balance_sheet(fiscal_year.end_date)
        
        return {
            'fiscal_year': {
                'year': fiscal_year.year,
                'start_date': fiscal_year.start_date,
                'end_date': fiscal_year.end_date,
                'status': fiscal_year.status
            },
            'financial_performance': {
                'total_revenue': income_statement['revenue']['total'],
                'total_expenses': income_statement['expenses']['total'] + abs(income_statement['cost_of_goods_sold']['total']),
                'gross_profit': income_statement['metrics']['gross_profit'],
                'net_income': income_statement['metrics']['net_income'],
                'gross_margin': income_statement['metrics']['gross_margin_percent'],
                'net_margin': income_statement['metrics']['net_margin_percent']
            },
            'financial_position': {
                'total_assets': balance_sheet['assets']['total'],
                'total_liabilities': balance_sheet['liabilities']['total'],
                'total_equity': balance_sheet['equity']['total']
            },
            'generated_at': timezone.now()
        }
    
    def get_monthly_trend_analysis(self, months: int = 12) -> Dict:
        """
        Get monthly financial trends
        
        Args:
            months: Number of months to analyze
        
        Returns:
            Monthly trend data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)  # Approximate
        
        monthly_data = []
        current_date = start_date.replace(day=1)  # Start of month
        
        while current_date <= end_date:
            # Calculate month end date
            if current_date.month == 12:
                month_end = date(current_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
            
            # Ensure we don't go beyond the end date
            month_end = min(month_end, end_date)
            
            # Generate income statement for the month
            income_statement = self.generate_income_statement(current_date, month_end)
            
            monthly_data.append({
                'period': f"{current_date.strftime('%Y-%m')}",
                'start_date': current_date,
                'end_date': month_end,
                'revenue': income_statement['revenue']['total'],
                'expenses': income_statement['expenses']['total'] + abs(income_statement['cost_of_goods_sold']['total']),
                'gross_profit': income_statement['metrics']['gross_profit'],
                'net_income': income_statement['metrics']['net_income'],
                'gross_margin': income_statement['metrics']['gross_margin_percent'],
                'net_margin': income_statement['metrics']['net_margin_percent']
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        # Calculate trends
        if len(monthly_data) >= 2:
            revenue_trend = ((monthly_data[-1]['revenue'] - monthly_data[0]['revenue']) / 
                           monthly_data[0]['revenue'] * 100) if monthly_data[0]['revenue'] > 0 else Decimal('0.00')
            
            profit_trend = ((monthly_data[-1]['net_income'] - monthly_data[0]['net_income']) / 
                          abs(monthly_data[0]['net_income']) * 100) if monthly_data[0]['net_income'] != 0 else Decimal('0.00')
        else:
            revenue_trend = Decimal('0.00')
            profit_trend = Decimal('0.00')
        
        return {
            'period_analyzed': {
                'start_date': start_date,
                'end_date': end_date,
                'months': len(monthly_data)
            },
            'monthly_data': monthly_data,
            'trends': {
                'revenue_growth_percent': revenue_trend,
                'profit_growth_percent': profit_trend,
                'average_monthly_revenue': sum(month['revenue'] for month in monthly_data) / len(monthly_data) if monthly_data else Decimal('0.00'),
                'average_monthly_profit': sum(month['net_income'] for month in monthly_data) / len(monthly_data) if monthly_data else Decimal('0.00')
            },
            'generated_at': timezone.now()
        }