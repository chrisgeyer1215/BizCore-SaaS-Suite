"""
Finance Calculations Utilities
Common financial calculations and formulas used throughout the finance module
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional
from datetime import date, datetime, timedelta
from django.db.models import Sum, Q
from django.utils import timezone

from ..models import Account, JournalEntry, JournalEntryLine


class FinancialCalculations:
    """Utility class for financial calculations"""
    
    @staticmethod
    def calculate_account_balance(
        account: Account,
        as_of_date: Optional[date] = None,
        include_pending: bool = False
    ) -> Decimal:
        """
        Calculate account balance as of a specific date
        
        Args:
            account: Account object
            as_of_date: Date to calculate balance as of (defaults to today)
            include_pending: Whether to include pending journal entries
            
        Returns:
            Decimal: Account balance
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        # Build query for journal entry lines
        query = Q(
            account=account,
            journal_entry__entry_date__lte=as_of_date,
            journal_entry__tenant=account.tenant
        )
        
        if not include_pending:
            query &= Q(journal_entry__status='POSTED')
        
        # Calculate balance
        debits = JournalEntryLine.objects.filter(
            query, debit_amount__gt=0
        ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        
        credits = JournalEntryLine.objects.filter(
            query, credit_amount__gt=0
        ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
        
        # Add opening balance
        opening_balance = account.opening_balance or Decimal('0.00')
        
        # Calculate net balance
        if account.normal_balance == 'DEBIT':
            balance = opening_balance + debits - credits
        else:
            balance = opening_balance + credits - debits
        
        return balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_trial_balance(
        tenant,
        as_of_date: Optional[date] = None,
        include_zero_balances: bool = False
    ) -> Dict:
        """
        Calculate trial balance as of a specific date
        
        Args:
            tenant: Tenant object
            as_of_date: Date to calculate trial balance as of
            include_zero_balances: Whether to include accounts with zero balance
            
        Returns:
            Dict containing trial balance data
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        accounts = Account.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('category', 'currency')
        
        trial_balance = {
            'as_of_date': as_of_date,
            'accounts': [],
            'total_debits': Decimal('0.00'),
            'total_credits': Decimal('0.00'),
            'difference': Decimal('0.00'),
            'is_balanced': False
        }
        
        for account in accounts:
            balance = FinancialCalculations.calculate_account_balance(
                account, as_of_date
            )
            
            if balance == 0 and not include_zero_balances:
                continue
            
            account_data = {
                'account': account,
                'balance': balance,
                'debit_amount': balance if balance > 0 else Decimal('0.00'),
                'credit_amount': abs(balance) if balance < 0 else Decimal('0.00')
            }
            
            trial_balance['accounts'].append(account_data)
            trial_balance['total_debits'] += account_data['debit_amount']
            trial_balance['total_credits'] += account_data['credit_amount']
        
        # Calculate difference
        trial_balance['difference'] = (
            trial_balance['total_debits'] - trial_balance['total_credits']
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Check if balanced
        trial_balance['is_balanced'] = abs(trial_balance['difference']) <= Decimal('0.01')
        
        return trial_balance
    
    @staticmethod
    def calculate_financial_ratios(
        tenant,
        as_of_date: Optional[date] = None
    ) -> Dict:
        """
        Calculate key financial ratios
        
        Args:
            tenant: Tenant object
            as_of_date: Date to calculate ratios as of
            
        Returns:
            Dict containing financial ratios
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        # Get account balances
        assets = FinancialCalculations._get_account_type_balance(
            tenant, 'ASSET', as_of_date
        )
        liabilities = FinancialCalculations._get_account_type_balance(
            tenant, 'LIABILITY', as_of_date
        )
        equity = FinancialCalculations._get_account_type_balance(
            tenant, 'EQUITY', as_of_date
        )
        current_assets = FinancialCalculations._get_current_assets_balance(
            tenant, as_of_date
        )
        current_liabilities = FinancialCalculations._get_current_liabilities_balance(
            tenant, as_of_date
        )
        
        # Calculate ratios
        ratios = {
            'current_ratio': FinancialCalculations._safe_division(
                current_assets, current_liabilities
            ),
            'debt_to_equity_ratio': FinancialCalculations._safe_division(
                liabilities, equity
            ),
            'debt_to_assets_ratio': FinancialCalculations._safe_division(
                liabilities, assets
            ),
            'equity_ratio': FinancialCalculations._safe_division(
                equity, assets
            ),
            'working_capital': current_assets - current_liabilities
        }
        
        return ratios
    
    @staticmethod
    def calculate_account_aging(
        tenant,
        account_type: str,
        as_of_date: Optional[date] = None,
        aging_buckets: Optional[List[int]] = None
    ) -> Dict:
        """
        Calculate account aging analysis
        
        Args:
            tenant: Tenant object
            account_type: Type of accounts ('ASSET' for AR, 'LIABILITY' for AP)
            as_of_date: Date to calculate aging as of
            aging_buckets: List of days for aging buckets (default: [30, 60, 90, 120])
            
        Returns:
            Dict containing aging analysis
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        if aging_buckets is None:
            aging_buckets = [30, 60, 90, 120]
        
        # Get accounts of specified type
        accounts = Account.objects.filter(
            tenant=tenant,
            account_type=account_type,
            is_active=True
        )
        
        aging_data = {
            'as_of_date': as_of_date,
            'aging_buckets': aging_buckets,
            'buckets': {},
            'total_amount': Decimal('0.00'),
            'overdue_amount': Decimal('0.00')
        }
        
        # Initialize buckets
        for days in aging_buckets:
            aging_data['buckets'][days] = {
                'amount': Decimal('0.00'),
                'count': 0,
                'accounts': []
            }
        
        # Add current bucket (0-30 days)
        aging_data['buckets'][0] = {
            'amount': Decimal('0.00'),
            'count': 0,
            'accounts': []
        }
        
        # Calculate aging for each account
        for account in accounts:
            balance = FinancialCalculations.calculate_account_balance(
                account, as_of_date
            )
            
            if balance == 0:
                continue
            
            # Get oldest unpaid transaction
            oldest_transaction = FinancialCalculations._get_oldest_unpaid_transaction(
                account, as_of_date
            )
            
            if oldest_transaction:
                days_old = (as_of_date - oldest_transaction.entry_date).days
                bucket = FinancialCalculations._get_aging_bucket(days_old, aging_buckets)
                
                aging_data['buckets'][bucket]['amount'] += abs(balance)
                aging_data['buckets'][bucket]['count'] += 1
                aging_data['buckets'][bucket]['accounts'].append({
                    'account': account,
                    'balance': balance,
                    'days_old': days_old
                })
                
                aging_data['total_amount'] += abs(balance)
                
                if days_old > 30:
                    aging_data['overdue_amount'] += abs(balance)
        
        return aging_data
    
    @staticmethod
    def calculate_monthly_summary(
        tenant,
        year: int,
        month: Optional[int] = None
    ) -> Dict:
        """
        Calculate monthly financial summary
        
        Args:
            tenant: Tenant object
            year: Year to calculate summary for
            month: Month to calculate summary for (None for entire year)
            
        Returns:
            Dict containing monthly summary
        """
        start_date = date(year, 1, 1) if month is None else date(year, month, 1)
        
        if month is None:
            end_date = date(year, 12, 31)
        else:
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get journal entries for period
        journal_entries = JournalEntry.objects.filter(
            tenant=tenant,
            entry_date__gte=start_date,
            entry_date__lte=end_date,
            status='POSTED'
        )
        
        # Calculate totals by account type
        summary = {
            'period': f"{year}" if month is None else f"{year}-{month:02d}",
            'start_date': start_date,
            'end_date': end_date,
            'total_transactions': journal_entries.count(),
            'account_types': {}
        }
        
        for account_type, _ in Account.AccountType.choices:
            summary['account_types'][account_type] = {
                'debits': Decimal('0.00'),
                'credits': Decimal('0.00'),
                'net_change': Decimal('0.00')
            }
        
        # Calculate changes for each account type
        for entry in journal_entries:
            for line in entry.lines.all():
                account_type = line.account.account_type
                
                if line.debit_amount > 0:
                    summary['account_types'][account_type]['debits'] += line.debit_amount
                if line.credit_amount > 0:
                    summary['account_types'][account_type]['credits'] += line.credit_amount
        
        # Calculate net changes
        for account_type in summary['account_types']:
            debits = summary['account_types'][account_type]['debits']
            credits = summary['account_types'][account_type]['credits']
            
            if account_type in ['ASSET', 'EXPENSE']:
                summary['account_types'][account_type]['net_change'] = debits - credits
            else:
                summary['account_types'][account_type]['net_change'] = credits - debits
        
        return summary
    
    @staticmethod
    def calculate_budget_variance(
        tenant,
        budget_period: str,
        actual_period: str,
        account_codes: Optional[List[str]] = None
    ) -> Dict:
        """
        Calculate budget vs actual variance
        
        Args:
            tenant: Tenant object
            budget_period: Budget period identifier
            actual_period: Actual period identifier
            account_codes: List of account codes to analyze (None for all)
            
        Returns:
            Dict containing budget variance analysis
        """
        # This would integrate with budget models
        # For now, return placeholder structure
        variance_data = {
            'budget_period': budget_period,
            'actual_period': actual_period,
            'accounts': [],
            'total_budget': Decimal('0.00'),
            'total_actual': Decimal('0.00'),
            'total_variance': Decimal('0.00'),
            'variance_percentage': Decimal('0.00')
        }
        
        return variance_data
    
    @staticmethod
    def _get_account_type_balance(
        tenant,
        account_type: str,
        as_of_date: date
    ) -> Decimal:
        """Get total balance for accounts of a specific type"""
        accounts = Account.objects.filter(
            tenant=tenant,
            account_type=account_type,
            is_active=True
        )
        
        total_balance = Decimal('0.00')
        for account in accounts:
            balance = FinancialCalculations.calculate_account_balance(
                account, as_of_date
            )
            total_balance += balance
        
        return total_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def _get_current_assets_balance(tenant, as_of_date: date) -> Decimal:
        """Get total balance for current assets"""
        # This would need logic to identify current vs non-current assets
        # For now, return total assets
        return FinancialCalculations._get_account_type_balance(
            tenant, 'ASSET', as_of_date
        )
    
    @staticmethod
    def _get_current_liabilities_balance(tenant, as_of_date: date) -> Decimal:
        """Get total balance for current liabilities"""
        # This would need logic to identify current vs non-current liabilities
        # For now, return total liabilities
        return FinancialCalculations._get_account_type_balance(
            tenant, 'LIABILITY', as_of_date
        )
    
    @staticmethod
    def _get_oldest_unpaid_transaction(account: Account, as_of_date: date):
        """Get oldest unpaid transaction for an account"""
        return JournalEntryLine.objects.filter(
            account=account,
            journal_entry__entry_date__lte=as_of_date,
            journal_entry__status='POSTED'
        ).order_by('journal_entry__entry_date').first()
    
    @staticmethod
    def _get_aging_bucket(days_old: int, aging_buckets: List[int]) -> int:
        """Get appropriate aging bucket for days old"""
        for bucket in sorted(aging_buckets):
            if days_old <= bucket:
                return bucket
        return aging_buckets[-1] if aging_buckets else 0
    
    @staticmethod
    def _safe_division(numerator: Decimal, denominator: Decimal) -> Decimal:
        """Safely divide two decimals, returning 0 if denominator is 0"""
        if denominator == 0:
            return Decimal('0.00')
        return (numerator / denominator).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )


class TaxCalculations:
    """Utility class for tax calculations"""
    
    @staticmethod
    def calculate_tax_amount(
        base_amount: Decimal,
        tax_rate: Decimal,
        tax_type: str = 'percentage'
    ) -> Decimal:
        """
        Calculate tax amount
        
        Args:
            base_amount: Base amount to calculate tax on
            tax_rate: Tax rate (percentage or fixed amount)
            tax_type: Type of tax ('percentage' or 'fixed')
            
        Returns:
            Decimal: Calculated tax amount
        """
        if tax_type == 'percentage':
            tax_amount = (base_amount * tax_rate / 100)
        else:
            tax_amount = tax_rate
        
        return tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_total_with_tax(
        base_amount: Decimal,
        tax_amount: Decimal
    ) -> Decimal:
        """Calculate total amount including tax"""
        return (base_amount + tax_amount).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )


class CurrencyCalculations:
    """Utility class for currency calculations"""
    
    @staticmethod
    def convert_currency(
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        exchange_rate: Decimal
    ) -> Decimal:
        """
        Convert amount from one currency to another
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            exchange_rate: Exchange rate (from_currency/to_currency)
            
        Returns:
            Decimal: Converted amount
        """
        if from_currency == to_currency:
            return amount
        
        converted_amount = amount * exchange_rate
        return converted_amount.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    
    @staticmethod
    def calculate_exchange_gain_loss(
        original_amount: Decimal,
        original_rate: Decimal,
        current_rate: Decimal
    ) -> Decimal:
        """
        Calculate exchange gain/loss
        
        Args:
            original_amount: Original amount in foreign currency
            original_rate: Original exchange rate
            current_rate: Current exchange rate
            
        Returns:
            Decimal: Exchange gain (positive) or loss (negative)
        """
        original_value = original_amount * original_rate
        current_value = original_amount * current_rate
        gain_loss = current_value - original_value
        
        return gain_loss.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
