"""
Finance Reporting Utilities
Financial report generation utilities
"""

from decimal import Decimal
from typing import Dict, List, Any
from datetime import date, datetime, timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone


class ReportGenerator:
    """Financial report generation utilities"""
    
    @staticmethod
    def generate_summary_report(tenant, start_date: date, end_date: date) -> Dict:
        """Generate financial summary report"""
        from ..models import Account, JournalEntry
        
        # Get account balances
        accounts = Account.objects.filter(tenant=tenant, is_active=True)
        
        # Calculate period activity
        period_activity = JournalEntry.objects.filter(
            tenant=tenant,
            entry_date__gte=start_date,
            entry_date__lte=end_date,
            status='POSTED'
        ).aggregate(
            total_debits=Sum('total_debit'),
            total_credits=Sum('total_credit'),
            entry_count=Count('id')
        )
        
        # Get account type summaries
        account_summaries = {}
        for account_type, _ in Account.AccountType.choices:
            type_accounts = accounts.filter(account_type=account_type)
            total_balance = sum(acc.current_balance or Decimal('0.00') for acc in type_accounts)
            account_summaries[account_type] = {
                'count': type_accounts.count(),
                'total_balance': total_balance
            }
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'activity_summary': {
                'total_debits': period_activity['total_debits'] or Decimal('0.00'),
                'total_credits': period_activity['total_credits'] or Decimal('0.00'),
                'entry_count': period_activity['entry_count'] or 0
            },
            'account_summaries': account_summaries,
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def generate_cash_flow_summary(tenant, start_date: date, end_date: date) -> Dict:
        """Generate cash flow summary"""
        from ..models import Account, JournalEntry
        
        # Get cash accounts
        cash_accounts = Account.objects.filter(
            tenant=tenant,
            is_cash_account=True,
            is_active=True
        )
        
        cash_flow_data = {
            'period': {'start_date': start_date, 'end_date': end_date},
            'cash_accounts': [],
            'total_cash_flow': Decimal('0.00')
        }
        
        for account in cash_accounts:
            # Get opening balance
            opening_balance = account.get_balance_as_of(start_date - timedelta(days=1))
            
            # Get period activity
            period_activity = JournalEntry.objects.filter(
                tenant=tenant,
                lines__account=account,
                entry_date__gte=start_date,
                entry_date__lte=end_date,
                status='POSTED'
            ).aggregate(
                total_debits=Sum('lines__debit_amount'),
                total_credits=Sum('lines__credit_amount')
            )
            
            total_debits = period_activity['total_debits'] or Decimal('0.00')
            total_credits = period_activity['total_credits'] or Decimal('0.00')
            net_change = total_credits - total_debits
            ending_balance = opening_balance + net_change
            
            cash_flow_data['cash_accounts'].append({
                'account_code': account.code,
                'account_name': account.name,
                'opening_balance': opening_balance,
                'total_debits': total_debits,
                'total_credits': total_credits,
                'net_change': net_change,
                'ending_balance': ending_balance
            })
            
            cash_flow_data['total_cash_flow'] += net_change
        
        return cash_flow_data
    
    @staticmethod
    def generate_aging_report(tenant, as_of_date: date = None) -> Dict:
        """Generate accounts receivable/payable aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        from ..models import Invoice, Bill
        
        # Accounts Receivable Aging
        ar_invoices = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        ar_aging = ReportGenerator._calculate_aging_buckets(ar_invoices, as_of_date, 'due_date', 'amount_due')
        
        # Accounts Payable Aging
        ap_bills = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        ap_aging = ReportGenerator._calculate_aging_buckets(ap_bills, as_of_date, 'due_date', 'amount_due')
        
        return {
            'as_of_date': as_of_date,
            'accounts_receivable': ar_aging,
            'accounts_payable': ap_aging,
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def _calculate_aging_buckets(documents, as_of_date: date, date_field: str, amount_field: str) -> Dict:
        """Calculate aging buckets for documents"""
        aging_buckets = {
            'current': {'amount': Decimal('0.00'), 'count': 0, 'days': '0-30'},
            'days_31_60': {'amount': Decimal('0.00'), 'count': 0, 'days': '31-60'},
            'days_61_90': {'amount': Decimal('0.00'), 'count': 0, 'days': '61-90'},
            'days_91_120': {'amount': Decimal('0.00'), 'count': 0, 'days': '91-120'},
            'over_120': {'amount': Decimal('0.00'), 'count': 0, 'days': '120+'}
        }
        
        total_amount = Decimal('0.00')
        total_count = 0
        
        for document in documents:
            due_date = getattr(document, date_field)
            amount = getattr(document, amount_field)
            
            if due_date:
                days_overdue = (as_of_date - due_date).days
                
                # Categorize into aging buckets
                if days_overdue <= 30:
                    bucket = 'current'
                elif days_overdue <= 60:
                    bucket = 'days_31_60'
                elif days_overdue <= 90:
                    bucket = 'days_61_90'
                elif days_overdue <= 120:
                    bucket = 'days_91_120'
                else:
                    bucket = 'over_120'
                
                aging_buckets[bucket]['amount'] += amount
                aging_buckets[bucket]['count'] += 1
                total_amount += amount
                total_count += 1
        
        # Calculate percentages
        for bucket_data in aging_buckets.values():
            if total_amount > 0:
                bucket_data['percentage'] = (bucket_data['amount'] / total_amount * 100).quantize(Decimal('0.01'))
            else:
                bucket_data['percentage'] = Decimal('0.00')
        
        return {
            'aging_buckets': aging_buckets,
            'summary': {
                'total_amount': total_amount,
                'total_count': total_count,
                'average_amount': total_amount / total_count if total_count > 0 else Decimal('0.00')
            }
        }


class ReportFormatter:
    """Report formatting utilities"""
    
    @staticmethod
    def format_currency_amount(amount: Decimal, currency_code: str = 'USD') -> str:
        """Format currency amount for display"""
        if amount is None:
            return '-'
        
        # Basic currency formatting
        if currency_code == 'USD':
            return f"${amount:,.2f}"
        elif currency_code == 'EUR':
            return f"€{amount:,.2f}"
        elif currency_code == 'GBP':
            return f"£{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency_code}"
    
    @staticmethod
    def format_percentage(value: Decimal, decimal_places: int = 1) -> str:
        """Format percentage value"""
        if value is None:
            return '-'
        
        return f"{value:.{decimal_places}f}%"
    
    @staticmethod
    def format_date(date_obj: date, format_type: str = 'short') -> str:
        """Format date for display"""
        if not date_obj:
            return '-'
        
        if format_type == 'short':
            return date_obj.strftime('%m/%d/%Y')
        elif format_type == 'long':
            return date_obj.strftime('%B %d, %Y')
        else:
            return date_obj.strftime('%Y-%m-%d')
    
    @staticmethod
    def format_number(number, decimal_places: int = 0) -> str:
        """Format number with commas"""
        if number is None:
            return '-'
        
        if decimal_places == 0:
            return f"{int(number):,}"
        else:
            return f"{float(number):,.{decimal_places}f}"


class ReportScheduler:
    """Report scheduling utilities"""
    
    @staticmethod
    def get_next_run_date(frequency: str, last_run: datetime = None) -> datetime:
        """Calculate next run date based on frequency"""
        if not last_run:
            last_run = timezone.now()
        
        if frequency == 'DAILY':
            return last_run + timedelta(days=1)
        elif frequency == 'WEEKLY':
            return last_run + timedelta(weeks=1)
        elif frequency == 'MONTHLY':
            # Simple monthly calculation
            if last_run.month == 12:
                return last_run.replace(year=last_run.year + 1, month=1)
            else:
                return last_run.replace(month=last_run.month + 1)
        elif frequency == 'QUARTERLY':
            # Simple quarterly calculation
            quarter = (last_run.month - 1) // 3
            next_quarter_month = quarter * 3 + 4
            if next_quarter_month > 12:
                return last_run.replace(year=last_run.year + 1, month=1)
            else:
                return last_run.replace(month=next_quarter_month)
        elif frequency == 'YEARLY':
            return last_run.replace(year=last_run.year + 1)
        else:
            return last_run + timedelta(days=1)
    
    @staticmethod
    def is_report_due(schedule) -> bool:
        """Check if report is due to run"""
        if not schedule.is_active:
            return False
        
        if not schedule.last_run:
            return True
        
        next_run = ReportScheduler.get_next_run_date(schedule.frequency, schedule.last_run)
        return timezone.now() >= next_run
