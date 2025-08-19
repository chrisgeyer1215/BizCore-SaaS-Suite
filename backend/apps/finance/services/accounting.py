"""
Core Accounting Service
Fundamental accounting operations and calculations
"""

from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from ..models import (
    Account, JournalEntry, JournalEntryLine, Currency, ExchangeRate,
    FinanceSettings, FiscalYear, FinancialPeriod
)


class AccountingService:
    """Core accounting service for financial operations"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
            return None
    
    def get_account_balance(self, account_id: int, as_of_date: date = None, 
                          currency: Currency = None) -> Decimal:
        """
        Get account balance as of specific date with currency conversion
        """
        try:
            account = Account.objects.get(id=account_id, tenant=self.tenant)
        except Account.DoesNotExist:
            return Decimal('0.00')
        
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all journal entry lines for this account up to the date
        journal_lines = JournalEntryLine.objects.filter(
            tenant=self.tenant,
            account=account,
            journal_entry__status='POSTED',
            journal_entry__entry_date__lte=as_of_date
        )
        
        # Calculate balance based on normal balance type
        balance = Decimal('0.00')
        
        for line in journal_lines:
            if account.normal_balance == 'DEBIT':
                balance += line.base_currency_debit_amount - line.base_currency_credit_amount
            else:
                balance += line.base_currency_credit_amount - line.base_currency_debit_amount
        
        # Add opening balance
        if account.opening_balance_date and account.opening_balance_date <= as_of_date:
            if account.normal_balance == 'DEBIT':
                balance += account.opening_balance
            else:
                balance += account.opening_balance
        
        # Convert to requested currency if needed
        if currency and currency != self._get_base_currency():
            exchange_rate = ExchangeRate.get_rate(
                self.tenant, self._get_base_currency(), currency, as_of_date
            )
            balance = balance * exchange_rate
        
        return balance
    
    def get_trial_balance(self, as_of_date: date = None) -> List[Dict]:
        """
        Generate trial balance report
        """
        if not as_of_date:
            as_of_date = date.today()
        
        trial_balance = []
        accounts = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('code')
        
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for account in accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            
            if balance != 0:
                if account.normal_balance == 'DEBIT':
                    debit_balance = balance if balance > 0 else Decimal('0.00')
                    credit_balance = abs(balance) if balance < 0 else Decimal('0.00')
                else:
                    credit_balance = balance if balance > 0 else Decimal('0.00')
                    debit_balance = abs(balance) if balance < 0 else Decimal('0.00')
                
                trial_balance.append({
                    'account': account,
                    'account_code': account.code,
                    'account_name': account.name,
                    'account_type': account.account_type,
                    'debit_balance': debit_balance,
                    'credit_balance': credit_balance,
                })
                
                total_debits += debit_balance
                total_credits += credit_balance
        
        return {
            'trial_balance': trial_balance,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'is_balanced': abs(total_debits - total_credits) < Decimal('0.01'),
            'as_of_date': as_of_date
        }
    
    def get_balance_sheet_data(self, as_of_date: date = None) -> Dict:
        """
        Generate balance sheet data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        balance_sheet = {
            'assets': {
                'current_assets': [],
                'fixed_assets': [],
                'other_assets': [],
                'total_current_assets': Decimal('0.00'),
                'total_fixed_assets': Decimal('0.00'),
                'total_other_assets': Decimal('0.00'),
                'total_assets': Decimal('0.00'),
            },
            'liabilities': {
                'current_liabilities': [],
                'long_term_liabilities': [],
                'total_current_liabilities': Decimal('0.00'),
                'total_long_term_liabilities': Decimal('0.00'),
                'total_liabilities': Decimal('0.00'),
            },
            'equity': {
                'equity_accounts': [],
                'retained_earnings': Decimal('0.00'),
                'total_equity': Decimal('0.00'),
            },
            'as_of_date': as_of_date
        }
        
        # Get all balance sheet accounts
        accounts = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('code')
        
        for account in accounts:
            balance = self.get_account_balance(account.id, as_of_date)
            
            if balance != 0:
                account_data = {
                    'account': account,
                    'balance': balance
                }
                
                # Classify accounts
                if account.account_type == 'CURRENT_ASSET':
                    balance_sheet['assets']['current_assets'].append(account_data)
                    balance_sheet['assets']['total_current_assets'] += balance
                elif account.account_type == 'FIXED_ASSET':
                    balance_sheet['assets']['fixed_assets'].append(account_data)
                    balance_sheet['assets']['total_fixed_assets'] += balance
                elif account.account_type in ['ASSET', 'OTHER_ASSET']:
                    balance_sheet['assets']['other_assets'].append(account_data)
                    balance_sheet['assets']['total_other_assets'] += balance
                elif account.account_type == 'CURRENT_LIABILITY':
                    balance_sheet['liabilities']['current_liabilities'].append(account_data)
                    balance_sheet['liabilities']['total_current_liabilities'] += balance
                elif account.account_type in ['LIABILITY', 'LONG_TERM_LIABILITY']:
                    balance_sheet['liabilities']['long_term_liabilities'].append(account_data)
                    balance_sheet['liabilities']['total_long_term_liabilities'] += balance
                elif account.account_type == 'EQUITY':
                    balance_sheet['equity']['equity_accounts'].append(account_data)
                elif account.account_type == 'RETAINED_EARNINGS':
                    balance_sheet['equity']['retained_earnings'] += balance
        
        # Calculate totals
        balance_sheet['assets']['total_assets'] = (
            balance_sheet['assets']['total_current_assets'] +
            balance_sheet['assets']['total_fixed_assets'] +
            balance_sheet['assets']['total_other_assets']
        )
        
        balance_sheet['liabilities']['total_liabilities'] = (
            balance_sheet['liabilities']['total_current_liabilities'] +
            balance_sheet['liabilities']['total_long_term_liabilities']
        )
        
        # Calculate retained earnings from income statement accounts
        net_income = self.get_net_income(as_of_date)
        balance_sheet['equity']['retained_earnings'] += net_income
        
        balance_sheet['equity']['total_equity'] = (
            sum(item['balance'] for item in balance_sheet['equity']['equity_accounts']) +
            balance_sheet['equity']['retained_earnings']
        )
        
        return balance_sheet
    
    def get_income_statement_data(self, start_date: date, end_date: date) -> Dict:
        """
        Generate income statement data
        """
        income_statement = {
            'revenue': {
                'revenue_accounts': [],
                'other_income': [],
                'total_revenue': Decimal('0.00'),
                'total_other_income': Decimal('0.00'),
                'total_income': Decimal('0.00'),
            },
            'expenses': {
                'cost_of_goods_sold': [],
                'operating_expenses': [],
                'other_expenses': [],
                'total_cogs': Decimal('0.00'),
                'total_operating_expenses': Decimal('0.00'),
                'total_other_expenses': Decimal('0.00'),
                'total_expenses': Decimal('0.00'),
            },
            'start_date': start_date,
            'end_date': end_date,
        }
        
        # Get all income statement accounts
        accounts = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('code')
        
        for account in accounts:
            # Get period activity
            journal_lines = JournalEntryLine.objects.filter(
                tenant=self.tenant,
                account=account,
                journal_entry__status='POSTED',
                journal_entry__entry_date__gte=start_date,
                journal_entry__entry_date__lte=end_date
            )
            
            period_activity = Decimal('0.00')
            for line in journal_lines:
                if account.normal_balance == 'DEBIT':
                    period_activity += line.base_currency_debit_amount - line.base_currency_credit_amount
                else:
                    period_activity += line.base_currency_credit_amount - line.base_currency_debit_amount
            
            if period_activity != 0:
                account_data = {
                    'account': account,
                    'amount': period_activity
                }
                
                # Classify accounts
                if account.account_type == 'REVENUE':
                    income_statement['revenue']['revenue_accounts'].append(account_data)
                    income_statement['revenue']['total_revenue'] += period_activity
                elif account.account_type == 'OTHER_INCOME':
                    income_statement['revenue']['other_income'].append(account_data)
                    income_statement['revenue']['total_other_income'] += period_activity
                elif account.account_type == 'COST_OF_GOODS_SOLD':
                    income_statement['expenses']['cost_of_goods_sold'].append(account_data)
                    income_statement['expenses']['total_cogs'] += abs(period_activity)
                elif account.account_type == 'EXPENSE':
                    income_statement['expenses']['operating_expenses'].append(account_data)
                    income_statement['expenses']['total_operating_expenses'] += abs(period_activity)
                elif account.account_type == 'OTHER_EXPENSE':
                    income_statement['expenses']['other_expenses'].append(account_data)
                    income_statement['expenses']['total_other_expenses'] += abs(period_activity)
        
        # Calculate totals
        income_statement['revenue']['total_income'] = (
            income_statement['revenue']['total_revenue'] +
            income_statement['revenue']['total_other_income']
        )
        
        income_statement['expenses']['total_expenses'] = (
            income_statement['expenses']['total_cogs'] +
            income_statement['expenses']['total_operating_expenses'] +
            income_statement['expenses']['total_other_expenses']
        )
        
        # Calculate financial metrics
        income_statement['gross_profit'] = (
            income_statement['revenue']['total_revenue'] - 
            income_statement['expenses']['total_cogs']
        )
        
        income_statement['operating_income'] = (
            income_statement['gross_profit'] - 
            income_statement['expenses']['total_operating_expenses']
        )
        
        income_statement['net_income'] = (
            income_statement['revenue']['total_income'] - 
            income_statement['expenses']['total_expenses']
        )
        
        # Calculate margins
        if income_statement['revenue']['total_revenue'] > 0:
            income_statement['gross_margin'] = (
                income_statement['gross_profit'] / 
                income_statement['revenue']['total_revenue'] * 100
            )
            income_statement['net_margin'] = (
                income_statement['net_income'] / 
                income_statement['revenue']['total_revenue'] * 100
            )
        else:
            income_statement['gross_margin'] = Decimal('0.00')
            income_statement['net_margin'] = Decimal('0.00')
        
        return income_statement
    
    def get_net_income(self, as_of_date: date = None) -> Decimal:
        """
        Calculate net income for the current fiscal year up to a specific date
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Get current fiscal year
        fiscal_year = self.get_current_fiscal_year(as_of_date)
        if not fiscal_year:
            return Decimal('0.00')
        
        start_date = fiscal_year.start_date
        end_date = min(as_of_date, fiscal_year.end_date)
        
        income_statement = self.get_income_statement_data(start_date, end_date)
        return income_statement['net_income']
    
    def get_current_fiscal_year(self, as_of_date: date = None) -> Optional[FiscalYear]:
        """
        Get the current fiscal year for a given date
        """
        if not as_of_date:
            as_of_date = date.today()
        
        try:
            return FiscalYear.objects.get(
                tenant=self.tenant,
                start_date__lte=as_of_date,
                end_date__gte=as_of_date
            )
        except FiscalYear.DoesNotExist:
            return None
    
    def get_current_period(self, as_of_date: date = None) -> Optional[FinancialPeriod]:
        """
        Get the current financial period for a given date
        """
        if not as_of_date:
            as_of_date = date.today()
        
        try:
            return FinancialPeriod.objects.get(
                tenant=self.tenant,
                start_date__lte=as_of_date,
                end_date__gte=as_of_date,
                status='OPEN'
            )
        except FinancialPeriod.DoesNotExist:
            return None
    
    def _get_base_currency(self) -> Currency:
        """Get the base currency for the tenant"""
        try:
            return Currency.objects.get(tenant=self.tenant, is_base_currency=True)
        except Currency.DoesNotExist:
            # Fallback to USD
            return Currency.objects.get_or_create(
                tenant=self.tenant,
                code='USD',
                defaults={
                    'name': 'US Dollar',
                    'symbol': '$',
                    'is_base_currency': True
                }
            )[0]
    
    def close_accounting_period(self, period: FinancialPeriod, user) -> bool:
        """
        Close an accounting period
        """
        if period.status != 'OPEN':
            raise ValueError('Period is not open')
        
        with transaction.atomic():
            # Calculate actual amounts for the period
            period.calculate_actual_amounts()
            
            # Close the period
            period.close_period(user)
            
            # Create closing entries if it's year-end
            if period.end_date == period.fiscal_year.end_date:
                self._create_year_end_closing_entries(period.fiscal_year, user)
        
        return True
    
    def _create_year_end_closing_entries(self, fiscal_year: FiscalYear, user):
        """
        Create year-end closing entries
        """
        from .journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        service.create_year_end_closing_entries(fiscal_year, user)
    
    def validate_account_structure(self) -> List[Dict]:
        """
        Validate chart of accounts structure and return issues
        """
        issues = []
        
        # Check for required accounts
        required_account_types = [
            'CURRENT_ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE'
        ]
        
        for account_type in required_account_types:
            if not Account.objects.filter(
                tenant=self.tenant,
                account_type=account_type,
                is_active=True
            ).exists():
                issues.append({
                    'type': 'missing_account_type',
                    'severity': 'warning',
                    'message': f'No active accounts found for type: {account_type}'
                })
        
        # Check for accounts without normal balance set
        accounts_without_balance = Account.objects.filter(
            tenant=self.tenant,
            normal_balance__isnull=True,
            is_active=True
        )
        
        for account in accounts_without_balance:
            issues.append({
                'type': 'missing_normal_balance',
                'severity': 'error',
                'account': account,
                'message': f'Account {account.code} has no normal balance set'
            })
        
        # Check for duplicate account codes
        duplicate_codes = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).values('code').annotate(
            count=models.Count('code')
        ).filter(count__gt=1)
        
        for dup in duplicate_codes:
            issues.append({
                'type': 'duplicate_code',
                'severity': 'error',
                'code': dup['code'],
                'message': f'Duplicate account code: {dup["code"]}'
            })
        
        return issues