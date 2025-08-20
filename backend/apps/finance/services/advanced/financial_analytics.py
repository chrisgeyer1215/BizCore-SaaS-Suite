# backend/apps/finance/services/advanced/financial_analytics.py
"""
Advanced Financial Analytics Service
Provides sophisticated financial analysis, forecasting, and business intelligence
"""

from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import transaction, models
from django.db.models import Sum, Avg, Count, Q, F, Case, When, Value
from django.utils import timezone
import calendar
import statistics
import logging

from ..base import FinanceBaseService, ServiceResult
from ...models import (
    Invoice, Bill, Payment, Account, Customer, Vendor,
    JournalEntry, JournalEntryLine, FiscalYear, FinancialPeriod
)

logger = logging.getLogger(__name__)


class FinancialAnalyticsService(FinanceBaseService):
    """
    Advanced financial analytics and business intelligence service
    """
    
    def get_service_name(self) -> str:
        return "FinancialAnalyticsService"
    
    def generate_financial_dashboard(self, period: str = 'current_month',
                                   include_forecasts: bool = True) -> ServiceResult:
        """
        Generate comprehensive financial dashboard data
        
        Args:
            period: Time period for analysis ('current_month', 'current_quarter', 'current_year', 'ytd')
            include_forecasts: Whether to include forecast data
            
        Returns:
            ServiceResult with dashboard data
        """
        def _generate_dashboard():
            # Determine date range
            date_range = self._get_date_range(period)
            start_date, end_date = date_range['start_date'], date_range['end_date']
            
            dashboard_data = {
                'period': period,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'key_metrics': self._calculate_key_metrics(start_date, end_date),
                'cash_flow': self._analyze_cash_flow(start_date, end_date),
                'revenue_analysis': self._analyze_revenue(start_date, end_date),
                'expense_analysis': self._analyze_expenses(start_date, end_date),
                'profitability': self._calculate_profitability_metrics(start_date, end_date),
                'receivables_analysis': self._analyze_receivables(),
                'payables_analysis': self._analyze_payables(),
                'trends': self._calculate_financial_trends(period),
                'alerts': self._generate_financial_alerts()
            }
            
            if include_forecasts:
                dashboard_data['forecasts'] = self._generate_forecasts(period)
            
            return dashboard_data
        
        return self.safe_execute("generate_financial_dashboard", _generate_dashboard)
    
    def _get_date_range(self, period: str) -> Dict[str, date]:
        """Get start and end dates for specified period"""
        today = timezone.now().date()
        
        if period == 'current_month':
            start_date = today.replace(day=1)
            end_date = today.replace(
                day=calendar.monthrange(today.year, today.month)[1]
            )
        
        elif period == 'current_quarter':
            quarter = (today.month - 1) // 3 + 1
            quarter_start_month = (quarter - 1) * 3 + 1
            start_date = today.replace(month=quarter_start_month, day=1)
            
            quarter_end_month = quarter * 3
            end_date = today.replace(
                month=quarter_end_month,
                day=calendar.monthrange(today.year, quarter_end_month)[1]
            )
        
        elif period == 'current_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        
        elif period == 'ytd':
            start_date = today.replace(month=1, day=1)
            end_date = today
        
        else:  # Default to current month
            start_date = today.replace(day=1)
            end_date = today.replace(
                day=calendar.monthrange(today.year, today.month)[1]
            )
        
        return {'start_date': start_date, 'end_date': end_date}
    
    def _calculate_key_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate key financial metrics"""
        
        # Revenue metrics
        total_revenue = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice_date__range=[start_date, end_date]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        # Expense metrics
        total_expenses = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            bill_date__range=[start_date, end_date]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        # Cash metrics
        cash_receipts = Payment.objects.filter(
            tenant=self.tenant,
            payment_type='RECEIVED',
            status__in=['CLEARED', 'RECONCILED'],
            payment_date__range=[start_date, end_date]
        ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
        
        cash_payments = Payment.objects.filter(
            tenant=self.tenant,
            payment_type='MADE',
            status__in=['CLEARED', 'RECONCILED'],
            payment_date__range=[start_date, end_date]
        ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
        
        # Outstanding balances
        outstanding_receivables = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        outstanding_payables = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL']
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        # Calculate derived metrics
        gross_profit = total_revenue - total_expenses
        net_cash_flow = cash_receipts - cash_payments
        working_capital = outstanding_receivables - outstanding_payables
        
        return {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'gross_profit': gross_profit,
            'gross_margin': (gross_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00'),
            'cash_receipts': cash_receipts,
            'cash_payments': cash_payments,
            'net_cash_flow': net_cash_flow,
            'outstanding_receivables': outstanding_receivables,
            'outstanding_payables': outstanding_payables,
            'working_capital': working_capital,
            'currency': self.base_currency.code
        }
    
    def _analyze_cash_flow(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze cash flow patterns"""
        
        # Daily cash flow analysis
        daily_flows = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_receipts = Payment.objects.filter(
                tenant=self.tenant,
                payment_type='RECEIVED',
                status__in=['CLEARED', 'RECONCILED'],
                payment_date=current_date
            ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
            
            daily_payments = Payment.objects.filter(
                tenant=self.tenant,
                payment_type='MADE',
                status__in=['CLEARED', 'RECONCILED'],
                payment_date=current_date
            ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
            
            daily_flows.append({
                'date': current_date.isoformat(),
                'receipts': daily_receipts,
                'payments': daily_payments,
                'net_flow': daily_receipts - daily_payments
            })
            
            current_date += timedelta(days=1)
        
        # Calculate cash flow statistics
        net_flows = [flow['net_flow'] for flow in daily_flows]
        positive_days = len([flow for flow in net_flows if flow > 0])
        negative_days = len([flow for flow in net_flows if flow < 0])
        
        return {
            'daily_flows': daily_flows,
            'summary': {
                'total_days': len(daily_flows),
                'positive_days': positive_days,
                'negative_days': negative_days,
                'average_daily_flow': statistics.mean([float(flow) for flow in net_flows]) if net_flows else 0,
                'total_receipts': sum(flow['receipts'] for flow in daily_flows),
                'total_payments': sum(flow['payments'] for flow in daily_flows),
                'net_cash_flow': sum(flow['net_flow'] for flow in daily_flows)
            }
        }
    
    def _analyze_revenue(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze revenue patterns and trends"""
        
        # Revenue by customer
        customer_revenue = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice_date__range=[start_date, end_date]
        ).values('customer__name').annotate(
            total_revenue=Sum('base_currency_total'),
            invoice_count=Count('id'),
            avg_invoice_amount=Avg('base_currency_total')
        ).order_by('-total_revenue')[:10]
        
        # Revenue by month (for trend analysis)
        monthly_revenue = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            month_end = current_date.replace(
                day=calendar.monthrange(current_date.year, current_date.month)[1]
            )
            
            monthly_total = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['PAID', 'PARTIAL', 'OPEN'],
                invoice_date__range=[current_date, min(month_end, end_date)]
            ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
            
            monthly_revenue.append({
                'month': current_date.strftime('%Y-%m'),
                'revenue': monthly_total
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Revenue by product category (if available)
        category_revenue = []
        try:
            # This would require integration with inventory/product models
            from apps.inventory.models import Product, ProductCategory
            
            category_revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['PAID', 'PARTIAL', 'OPEN'],
                invoice_date__range=[start_date, end_date]
            ).values(
                'invoice_items__product__category__name'
            ).annotate(
                total_revenue=Sum('base_currency_total')
            ).order_by('-total_revenue')
            
        except ImportError:
            pass  # Inventory module not available
        
        return {
            'top_customers': list(customer_revenue),
            'monthly_trends': monthly_revenue,
            'category_breakdown': list(category_revenue),
            'total_customers': Invoice.objects.filter(
                tenant=self.tenant,
                invoice_date__range=[start_date, end_date]
            ).values('customer').distinct().count()
        }
    
    def _analyze_expenses(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze expense patterns and trends"""
        
        # Expenses by vendor
        vendor_expenses = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            bill_date__range=[start_date, end_date]
        ).values('vendor__company_name').annotate(
            total_expenses=Sum('base_currency_total'),
            bill_count=Count('id'),
            avg_bill_amount=Avg('base_currency_total')
        ).order_by('-total_expenses')[:10]
        
        # Expenses by account type
        account_expenses = JournalEntryLine.objects.filter(
            tenant=self.tenant,
            journal_entry__status='POSTED',
            journal_entry__entry_date__range=[start_date, end_date],
            account__account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'],
            debit_amount__gt=0
        ).values('account__account_type', 'account__name').annotate(
            total_expenses=Sum('base_currency_debit_amount')
        ).order_by('-total_expenses')
        
        # Monthly expense trends
        monthly_expenses = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            month_end = current_date.replace(
                day=calendar.monthrange(current_date.year, current_date.month)[1]
            )
            
            monthly_total = Bill.objects.filter(
                tenant=self.tenant,
                status__in=['PAID', 'PARTIAL', 'OPEN'],
                bill_date__range=[current_date, min(month_end, end_date)]
            ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
            
            monthly_expenses.append({
                'month': current_date.strftime('%Y-%m'),
                'expenses': monthly_total
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return {
            'top_vendors': list(vendor_expenses),
            'expense_categories': list(account_expenses),
            'monthly_trends': monthly_expenses,
            'total_vendors': Bill.objects.filter(
                tenant=self.tenant,
                bill_date__range=[start_date, end_date]
            ).values('vendor').distinct().count()
        }
    
    def _calculate_profitability_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate various profitability metrics"""
        
        # Get revenue and expense data
        revenue_data = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice_date__range=[start_date, end_date]
        ).aggregate(
            total_revenue=Sum('base_currency_total'),
            count=Count('id')
        )
        
        expense_data = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            bill_date__range=[start_date, end_date]
        ).aggregate(
            total_expenses=Sum('base_currency_total'),
            count=Count('id')
        )
        
        # Calculate COGS
        cogs_data = JournalEntryLine.objects.filter(
            tenant=self.tenant,
            journal_entry__status='POSTED',
            journal_entry__entry_date__range=[start_date, end_date],
            account__account_type='COST_OF_GOODS_SOLD',
            debit_amount__gt=0
        ).aggregate(total_cogs=Sum('base_currency_debit_amount'))
        
        total_revenue = revenue_data['total_revenue'] or Decimal('0.00')
        total_expenses = expense_data['total_expenses'] or Decimal('0.00')
        total_cogs = cogs_data['total_cogs'] or Decimal('0.00')
        
        # Calculate profitability metrics
        gross_profit = total_revenue - total_cogs
        operating_profit = gross_profit - total_expenses
        
        # Calculate margins
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')
        operating_margin = (operating_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')
        
        # Calculate average transaction values
        avg_invoice_amount = total_revenue / revenue_data['count'] if revenue_data['count'] > 0 else Decimal('0.00')
        avg_expense_amount = total_expenses / expense_data['count'] if expense_data['count'] > 0 else Decimal('0.00')
        
        return {
            'total_revenue': total_revenue,
            'total_cogs': total_cogs,
            'total_expenses': total_expenses,
            'gross_profit': gross_profit,
            'operating_profit': operating_profit,
            'gross_margin': gross_margin,
            'operating_margin': operating_margin,
            'avg_invoice_amount': avg_invoice_amount,
            'avg_expense_amount': avg_expense_amount,
            'invoice_count': revenue_data['count'],
            'expense_count': expense_data['count']
        }
    
    def _analyze_receivables(self) -> Dict[str, Any]:
        """Analyze accounts receivable patterns"""
        
        # Outstanding invoices by age
        today = timezone.now().date()
        aging_buckets = {
            'current': Decimal('0.00'),
            '1_30_days': Decimal('0.00'),
            '31_60_days': Decimal('0.00'),
            '61_90_days': Decimal('0.00'),
            'over_90_days': Decimal('0.00')
        }
        
        outstanding_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
        )
        
        total_outstanding = Decimal('0.00')
        invoice_count = 0
        
        for invoice in outstanding_invoices:
            days_overdue = (today - invoice.due_date).days
            amount_due = invoice.base_currency_amount_due
            total_outstanding += amount_due
            invoice_count += 1
            
            if days_overdue <= 0:
                aging_buckets['current'] += amount_due
            elif days_overdue <= 30:
                aging_buckets['1_30_days'] += amount_due
            elif days_overdue <= 60:
                aging_buckets['31_60_days'] += amount_due
            elif days_overdue <= 90:
                aging_buckets['61_90_days'] += amount_due
            else:
                aging_buckets['over_90_days'] += amount_due
        
        # Calculate collection metrics
        avg_collection_period = self._calculate_avg_collection_period()
        
        return {
            'total_outstanding': total_outstanding,
            'invoice_count': invoice_count,
            'aging_buckets': aging_buckets,
            'avg_collection_period': avg_collection_period,
            'overdue_amount': aging_buckets['1_30_days'] + aging_buckets['31_60_days'] + 
                            aging_buckets['61_90_days'] + aging_buckets['over_90_days'],
            'overdue_percentage': (
                (aging_buckets['1_30_days'] + aging_buckets['31_60_days'] + 
                 aging_buckets['61_90_days'] + aging_buckets['over_90_days']) / 
                total_outstanding * 100
            ) if total_outstanding > 0 else Decimal('0.00')
        }
    
    def _analyze_payables(self) -> Dict[str, Any]:
        """Analyze accounts payable patterns"""
        
        # Outstanding bills by age
        today = timezone.now().date()
        aging_buckets = {
            'current': Decimal('0.00'),
            '1_30_days': Decimal('0.00'),
            '31_60_days': Decimal('0.00'),
            '61_90_days': Decimal('0.00'),
            'over_90_days': Decimal('0.00')
        }
        
        outstanding_bills = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL']
        )
        
        total_outstanding = Decimal('0.00')
        bill_count = 0
        
        for bill in outstanding_bills:
            days_overdue = (today - bill.due_date).days
            amount_due = bill.base_currency_amount_due
            total_outstanding += amount_due
            bill_count += 1
            
            if days_overdue <= 0:
                aging_buckets['current'] += amount_due
            elif days_overdue <= 30:
                aging_buckets['1_30_days'] += amount_due
            elif days_overdue <= 60:
                aging_buckets['31_60_days'] += amount_due
            elif days_overdue <= 90:
                aging_buckets['61_90_days'] += amount_due
            else:
                aging_buckets['over_90_days'] += amount_due
        
        # Calculate payment metrics
        avg_payment_period = self._calculate_avg_payment_period()
        
        return {
            'total_outstanding': total_outstanding,
            'bill_count': bill_count,
            'aging_buckets': aging_buckets,
            'avg_payment_period': avg_payment_period,
            'overdue_amount': aging_buckets['1_30_days'] + aging_buckets['31_60_days'] + 
                            aging_buckets['61_90_days'] + aging_buckets['over_90_days'],
            'overdue_percentage': (
                (aging_buckets['1_30_days'] + aging_buckets['31_60_days'] + 
                 aging_buckets['61_90_days'] + aging_buckets['over_90_days']) / 
                total_outstanding * 100
            ) if total_outstanding > 0 else Decimal('0.00')
        }
    
    def _calculate_avg_collection_period(self) -> float:
        """Calculate average collection period for receivables"""
        
        # Get paid invoices from last 90 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)
        
        paid_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status='PAID',
            invoice_date__range=[start_date, end_date]
        )
        
        collection_periods = []
        for invoice in paid_invoices:
            # Get the last payment date for this invoice
            last_payment = Payment.objects.filter(
                tenant=self.tenant,
                applications__invoice=invoice
            ).order_by('-payment_date').first()
            
            if last_payment:
                collection_period = (last_payment.payment_date - invoice.invoice_date).days
                collection_periods.append(collection_period)
        
        return statistics.mean(collection_periods) if collection_periods else 0.0
    
    def _calculate_avg_payment_period(self) -> float:
        """Calculate average payment period for payables"""
        
        # Get paid bills from last 90 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)
        
        paid_bills = Bill.objects.filter(
            tenant=self.tenant,
            status='PAID',
            bill_date__range=[start_date, end_date]
        )
        
        payment_periods = []
        for bill in paid_bills:
            # Get the last payment date for this bill
            last_payment = Payment.objects.filter(
                tenant=self.tenant,
                applications__bill=bill
            ).order_by('-payment_date').first()
            
            if last_payment:
                payment_period = (last_payment.payment_date - bill.bill_date).days
                payment_periods.append(payment_period)
        
        return statistics.mean(payment_periods) if payment_periods else 0.0
    
    def _calculate_financial_trends(self, period: str) -> Dict[str, Any]:
        """Calculate financial trends and growth rates"""
        
        # Get current period data
        current_range = self._get_date_range(period)
        
        # Calculate previous period range
        period_length = (current_range['end_date'] - current_range['start_date']).days
        previous_end = current_range['start_date'] - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_length)
        
        # Current period metrics
        current_revenue = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice_date__range=[current_range['start_date'], current_range['end_date']]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        current_expenses = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            bill_date__range=[current_range['start_date'], current_range['end_date']]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        # Previous period metrics
        previous_revenue = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice_date__range=[previous_start, previous_end]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        previous_expenses = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN'],
            bill_date__range=[previous_start, previous_end]
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        # Calculate growth rates
        revenue_growth = self._calculate_growth_rate(previous_revenue, current_revenue)
        expense_growth = self._calculate_growth_rate(previous_expenses, current_expenses)
        profit_growth = self._calculate_growth_rate(
            previous_revenue - previous_expenses,
            current_revenue - current_expenses
        )
        
        return {
            'revenue_growth': revenue_growth,
            'expense_growth': expense_growth,
            'profit_growth': profit_growth,
            'current_period': {
                'revenue': current_revenue,
                'expenses': current_expenses,
                'profit': current_revenue - current_expenses
            },
            'previous_period': {
                'revenue': previous_revenue,
                'expenses': previous_expenses,
                'profit': previous_revenue - previous_expenses
            }
        }
    
    def _calculate_growth_rate(self, previous: Decimal, current: Decimal) -> float:
        """Calculate growth rate between two periods"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return float((current - previous) / previous * 100)
    
    def _generate_financial_alerts(self) -> List[Dict[str, Any]]:
        """Generate financial alerts and warnings"""
        alerts = []
        
        # Check for overdue invoices
        overdue_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__lt=timezone.now().date()
        ).count()
        
        if overdue_invoices > 0:
            alerts.append({
                'type': 'warning',
                'category': 'receivables',
                'title': 'Overdue Invoices',
                'message': f'{overdue_invoices} invoices are overdue',
                'action': 'review_overdue_invoices'
            })
        
        # Check for large outstanding balances
        large_receivables = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            base_currency_amount_due__gte=10000
        ).count()
        
        if large_receivables > 0:
            alerts.append({
                'type': 'info',
                'category': 'receivables',
                'title': 'Large Outstanding Balances',
                'message': f'{large_receivables} invoices have balances over {self.format_currency(Decimal("10000"))}',
                'action': 'review_large_balances'
            })
        
        # Check cash flow
        today = timezone.now().date()
        week_start = today - timedelta(days=7)
        
        week_receipts = Payment.objects.filter(
            tenant=self.tenant,
            payment_type='RECEIVED',
            payment_date__range=[week_start, today]
        ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
        
        week_payments = Payment.objects.filter(
            tenant=self.tenant,
            payment_type='MADE',
            payment_date__range=[week_start, today]
        ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
        
        if week_payments > week_receipts * Decimal('1.5'):
            alerts.append({
                'type': 'warning',
                'category': 'cash_flow',
                'title': 'Negative Cash Flow Trend',
                'message': 'Payments exceeded receipts by 50% this week',
                'action': 'review_cash_flow'
            })
        
        return alerts
    
    def _generate_forecasts(self, period: str) -> Dict[str, Any]:
        """Generate financial forecasts based on historical data"""
        
        # Simple linear trend forecasting
        # In a real implementation, you might use more sophisticated methods
        
        # Get historical data for trend analysis
        months_data = []
        for i in range(12, 0, -1):  # Last 12 months
            month_date = timezone.now().date().replace(day=1) - timedelta(days=30 * i)
            month_end = month_date.replace(
                day=calendar.monthrange(month_date.year, month_date.month)[1]
            )
            
            revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['PAID', 'PARTIAL', 'OPEN'],
                invoice_date__range=[month_date, month_end]
            ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
            
            months_data.append(float(revenue))
        
        # Calculate simple trend
        if len(months_data) >= 3:
            # Linear regression for trend
            x = list(range(len(months_data)))
            y = months_data
            
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)
            
            # Linear regression: y = mx + b
            m = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            b = (sum_y - m * sum_x) / n
            
            # Forecast next 3 months
            forecasts = []
            for i in range(1, 4):
                forecast_value = m * (len(months_data) + i) + b
                forecasts.append(max(0, forecast_value))  # Don't forecast negative values
            
            return {
                'method': 'linear_trend',
                'historical_data': months_data,
                'trend_slope': m,
                'next_3_months': forecasts,
                'confidence': 'medium' if abs(m) > 1000 else 'low'
            }
        
        return {
            'method': 'insufficient_data',
            'message': 'Need at least 3 months of data for forecasting'
        }