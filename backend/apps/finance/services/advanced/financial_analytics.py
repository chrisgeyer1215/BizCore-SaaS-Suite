# apps/finance/services/advanced/financial_analytics.py

"""
Advanced Financial Analytics Service
Provides comprehensive financial analysis and forecasting capabilities
"""

from django.db import models
from django.db.models import Sum, Avg, Count, Q, F, Case, When, Value
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import json
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta

from apps.core.models import TenantBaseModel
from apps.finance.models import (
    Account, JournalEntry, Invoice, Payment, Bill, Vendor,
    Customer, FinanceSettings, FiscalYear, FinancialPeriod,
    Currency, ExchangeRate
)


class FinancialAnalyticsService:
    """Advanced financial analytics and forecasting service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = FinanceSettings.objects.get(tenant=tenant)
        self.base_currency = Currency.objects.get(
            tenant=tenant, 
            code=self.settings.base_currency
        )
    
    # =====================================================================
    # FINANCIAL KPIs & METRICS
    # =====================================================================
    
    def get_financial_kpis(self, start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Get comprehensive financial KPIs for dashboard"""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        # Revenue metrics
        revenue_data = self._get_revenue_metrics(start_date, end_date)
        
        # Expense metrics  
        expense_data = self._get_expense_metrics(start_date, end_date)
        
        # Profitability metrics
        profitability_data = self._get_profitability_metrics(start_date, end_date)
        
        # Cash flow metrics
        cash_flow_data = self._get_cash_flow_metrics(start_date, end_date)
        
        # Receivables metrics
        receivables_data = self._get_receivables_metrics()
        
        # Payables metrics
        payables_data = self._get_payables_metrics()
        
        # Growth metrics
        growth_data = self._get_growth_metrics(start_date, end_date)
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'revenue': revenue_data,
            'expenses': expense_data,
            'profitability': profitability_data,
            'cash_flow': cash_flow_data,
            'receivables': receivables_data,
            'payables': payables_data,
            'growth': growth_data,
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def _get_revenue_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate revenue-related metrics"""
        revenue_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type='REVENUE',
            is_active=True
        )
        
        # Total revenue
        total_revenue = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__range=[start_date, end_date],
            status='POSTED'
        ).filter(
            journal_lines__account__in=revenue_accounts
        ).aggregate(
            total=Sum('journal_lines__base_currency_credit_amount')
        )['total'] or Decimal('0.00')
        
        # Monthly revenue trend
        monthly_revenue = self._get_monthly_trend(
            revenue_accounts, start_date, end_date, 'credit'
        )
        
        # Revenue by account
        revenue_breakdown = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__range=[start_date, end_date],
            status='POSTED'
        ).filter(
            journal_lines__account__in=revenue_accounts
        ).values(
            'journal_lines__account__name'
        ).annotate(
            amount=Sum('journal_lines__base_currency_credit_amount')
        ).order_by('-amount')
        
        # Average invoice value
        avg_invoice_value = Invoice.objects.filter(
            tenant=self.tenant,
            invoice_date__range=[start_date, end_date],
            status__in=['PAID', 'PARTIAL', 'OPEN']
        ).aggregate(
            avg=Avg('base_currency_total')
        )['avg'] or Decimal('0.00')
        
        # Invoice count
        invoice_count = Invoice.objects.filter(
            tenant=self.tenant,
            invoice_date__range=[start_date, end_date],
            status__in=['PAID', 'PARTIAL', 'OPEN']
        ).count()
        
        return {
            'total_revenue': total_revenue,
            'monthly_trend': monthly_revenue,
            'breakdown': list(revenue_breakdown),
            'average_invoice_value': avg_invoice_value,
            'invoice_count': invoice_count,
            'revenue_per_invoice': total_revenue / max(invoice_count, 1)
        }
    
    def _get_expense_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate expense-related metrics"""
        expense_accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD'],
            is_active=True
        )
        
        # Total expenses
        total_expenses = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__range=[start_date, end_date],
            status='POSTED'
        ).filter(
            journal_lines__account__in=expense_accounts
        ).aggregate(
            total=Sum('journal_lines__base_currency_debit_amount')
        )['total'] or Decimal('0.00')
        
        # Monthly expense trend
        monthly_expenses = self._get_monthly_trend(
            expense_accounts, start_date, end_date, 'debit'
        )
        
        # Expense breakdown
        expense_breakdown = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__range=[start_date, end_date],
            status='POSTED'
        ).filter(
            journal_lines__account__in=expense_accounts
        ).values(
            'journal_lines__account__name',
            'journal_lines__account__account_type'
        ).annotate(
            amount=Sum('journal_lines__base_currency_debit_amount')
        ).order_by('-amount')
        
        # Average bill value
        avg_bill_value = Bill.objects.filter(
            tenant=self.tenant,
            bill_date__range=[start_date, end_date],
            status__in=['PAID', 'PARTIAL', 'OPEN']
        ).aggregate(
            avg=Avg('base_currency_total')
        )['avg'] or Decimal('0.00')
        
        return {
            'total_expenses': total_expenses,
            'monthly_trend': monthly_expenses,
            'breakdown': list(expense_breakdown),
            'average_bill_value': avg_bill_value
        }
    
    def _get_profitability_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate profitability metrics"""
        # Get revenue and expense totals
        revenue_total = self._get_account_type_total(
            ['REVENUE'], start_date, end_date, 'credit'
        )
        
        expense_total = self._get_account_type_total(
            ['EXPENSE', 'COST_OF_GOODS_SOLD'], start_date, end_date, 'debit'
        )
        
        cogs_total = self._get_account_type_total(
            ['COST_OF_GOODS_SOLD'], start_date, end_date, 'debit'
        )
        
        operating_expense_total = self._get_account_type_total(
            ['EXPENSE'], start_date, end_date, 'debit'
        )
        
        # Calculate key metrics
        gross_profit = revenue_total - cogs_total
        net_profit = revenue_total - expense_total
        
        # Calculate margins
        gross_margin = (gross_profit / revenue_total * 100) if revenue_total > 0 else 0
        net_margin = (net_profit / revenue_total * 100) if revenue_total > 0 else 0
        
        # Operating margin
        operating_profit = revenue_total - operating_expense_total
        operating_margin = (operating_profit / revenue_total * 100) if revenue_total > 0 else 0
        
        return {
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'operating_profit': operating_profit,
            'gross_margin_percent': round(gross_margin, 2),
            'net_margin_percent': round(net_margin, 2),
            'operating_margin_percent': round(operating_margin, 2),
            'revenue_total': revenue_total,
            'cogs_total': cogs_total,
            'operating_expenses': operating_expense_total
        }
    
    def _get_cash_flow_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate cash flow metrics"""
        cash_accounts = Account.objects.filter(
            tenant=self.tenant,
            is_cash_account=True,
            is_active=True
        )
        
        # Current cash balance
        current_cash = sum(account.current_balance for account in cash_accounts)
        
        # Cash receipts (customer payments)
        cash_receipts = Payment.objects.filter(
            tenant=self.tenant,
            payment_date__range=[start_date, end_date],
            payment_type='RECEIVED',
            status='CLEARED'
        ).aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0.00')
        
        # Cash payments (vendor payments)
        cash_payments = Payment.objects.filter(
            tenant=self.tenant,
            payment_date__range=[start_date, end_date],
            payment_type='MADE',
            status='CLEARED'
        ).aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0.00')
        
        # Net cash flow
        net_cash_flow = cash_receipts - cash_payments
        
        # Cash flow by month
        monthly_cash_flow = self._get_monthly_cash_flow(start_date, end_date)
        
        # Cash burn rate (average monthly cash outflow)
        months = max((end_date - start_date).days / 30, 1)
        cash_burn_rate = cash_payments / Decimal(str(months))
        
        # Cash runway (months of cash remaining at current burn rate)
        cash_runway = (current_cash / cash_burn_rate) if cash_burn_rate > 0 else float('inf')
        
        return {
            'current_cash_balance': current_cash,
            'cash_receipts': cash_receipts,
            'cash_payments': cash_payments,
            'net_cash_flow': net_cash_flow,
            'monthly_cash_flow': monthly_cash_flow,
            'cash_burn_rate': cash_burn_rate,
            'cash_runway_months': min(cash_runway, 999) if cash_runway != float('inf') else None
        }
    
    def _get_receivables_metrics(self) -> Dict[str, Any]:
        """Calculate accounts receivable metrics"""
        outstanding_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'PARTIAL', 'OVERDUE'],
            amount_due__gt=0
        )
        
        total_receivables = outstanding_invoices.aggregate(
            total=Sum('base_currency_amount_due')
        )['total'] or Decimal('0.00')
        
        # Aging analysis
        today = date.today()
        aging_buckets = {
            'current': outstanding_invoices.filter(due_date__gte=today),
            '1_30_days': outstanding_invoices.filter(
                due_date__lt=today,
                due_date__gte=today - timedelta(days=30)
            ),
            '31_60_days': outstanding_invoices.filter(
                due_date__lt=today - timedelta(days=30),
                due_date__gte=today - timedelta(days=60)
            ),
            '61_90_days': outstanding_invoices.filter(
                due_date__lt=today - timedelta(days=60),
                due_date__gte=today - timedelta(days=90)
            ),
            'over_90_days': outstanding_invoices.filter(
                due_date__lt=today - timedelta(days=90)
            )
        }
        
        aging_summary = {}
        for bucket, queryset in aging_buckets.items():
            aging_summary[bucket] = {
                'amount': queryset.aggregate(
                    total=Sum('base_currency_amount_due')
                )['total'] or Decimal('0.00'),
                'count': queryset.count()
            }
        
        # Average collection period
        paid_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status='PAID',
            created_at__gte=timezone.now() - timedelta(days=90)
        ).select_related('customer')
        
        collection_periods = []
        for invoice in paid_invoices:
            last_payment = invoice.applications.order_by('-application_date').first()
            if last_payment:
                collection_period = (last_payment.application_date - invoice.invoice_date).days
                collection_periods.append(collection_period)
        
        avg_collection_period = (
            sum(collection_periods) / len(collection_periods)
            if collection_periods else 0
        )
        
        return {
            'total_receivables': total_receivables,
            'invoice_count': outstanding_invoices.count(),
            'aging_summary': aging_summary,
            'average_collection_period_days': round(avg_collection_period, 1)
        }
    
    def _get_payables_metrics(self) -> Dict[str, Any]:
        """Calculate accounts payable metrics"""
        outstanding_bills = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'PARTIAL', 'OVERDUE'],
            amount_due__gt=0
        )
        
        total_payables = outstanding_bills.aggregate(
            total=Sum('base_currency_amount_due')
        )['total'] or Decimal('0.00')
        
        # Aging analysis
        today = date.today()
        aging_buckets = {
            'current': outstanding_bills.filter(due_date__gte=today),
            '1_30_days': outstanding_bills.filter(
                due_date__lt=today,
                due_date__gte=today - timedelta(days=30)
            ),
            '31_60_days': outstanding_bills.filter(
                due_date__lt=today - timedelta(days=30),
                due_date__gte=today - timedelta(days=60)
            ),
            'over_60_days': outstanding_bills.filter(
                due_date__lt=today - timedelta(days=60)
            )
        }
        
        aging_summary = {}
        for bucket, queryset in aging_buckets.items():
            aging_summary[bucket] = {
                'amount': queryset.aggregate(
                    total=Sum('base_currency_amount_due')
                )['total'] or Decimal('0.00'),
                'count': queryset.count()
            }
        
        return {
            'total_payables': total_payables,
            'bill_count': outstanding_bills.count(),
            'aging_summary': aging_summary
        }
    
    def _get_growth_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate growth metrics comparing to previous period"""
        period_days = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date - timedelta(days=1)
        
        # Current period revenue
        current_revenue = self._get_account_type_total(
            ['REVENUE'], start_date, end_date, 'credit'
        )
        
        # Previous period revenue
        previous_revenue = self._get_account_type_total(
            ['REVENUE'], prev_start, prev_end, 'credit'
        )
        
        # Revenue growth
        revenue_growth = (
            ((current_revenue - previous_revenue) / previous_revenue * 100)
            if previous_revenue > 0 else 0
        )
        
        # Customer growth
        current_customers = Customer.objects.filter(
            tenant=self.tenant,
            created_at__date__lte=end_date
        ).count()
        
        previous_customers = Customer.objects.filter(
            tenant=self.tenant,
            created_at__date__lte=prev_end
        ).count()
        
        customer_growth = (
            ((current_customers - previous_customers) / max(previous_customers, 1) * 100)
            if previous_customers > 0 else 0
        )
        
        return {
            'revenue_growth_percent': round(revenue_growth, 2),
            'customer_growth_percent': round(customer_growth, 2),
            'current_revenue': current_revenue,
            'previous_revenue': previous_revenue,
            'current_customers': current_customers,
            'previous_customers': previous_customers
        }
    
    # =====================================================================
    # CASH FLOW FORECASTING
    # =====================================================================
    
    def generate_cash_flow_forecast(
        self, 
        months_ahead: int = 12,
        include_budget: bool = True
    ) -> Dict[str, Any]:
        """Generate cash flow forecast for specified months ahead"""
        
        forecast_data = []
        start_date = date.today().replace(day=1)  # First day of current month
        
        for month_offset in range(months_ahead):
            month_start = start_date + relativedelta(months=month_offset)
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)
            
            month_forecast = self._forecast_month_cash_flow(
                month_start, month_end, include_budget
            )
            
            forecast_data.append({
                'month': month_start.strftime('%Y-%m'),
                'month_name': month_start.strftime('%B %Y'),
                **month_forecast
            })
        
        # Calculate cumulative cash flow
        cumulative_cash = self._get_current_cash_balance()
        for month_data in forecast_data:
            cumulative_cash += month_data['net_cash_flow']
            month_data['cumulative_cash'] = cumulative_cash
        
        return {
            'forecast_months': months_ahead,
            'base_currency': self.base_currency.code,
            'starting_cash_balance': self._get_current_cash_balance(),
            'forecast_data': forecast_data,
            'generated_at': timezone.now()
        }
    
    def _forecast_month_cash_flow(
        self, 
        month_start: date, 
        month_end: date,
        include_budget: bool
    ) -> Dict[str, Any]:
        """Forecast cash flow for a specific month"""
        
        # Historical analysis for forecasting
        historical_months = 6
        historical_start = month_start - relativedelta(months=historical_months)
        
        # Forecast cash inflows
        projected_inflows = self._forecast_cash_inflows(
            month_start, month_end, historical_start
        )
        
        # Forecast cash outflows
        projected_outflows = self._forecast_cash_outflows(
            month_start, month_end, historical_start
        )
        
        # Known future transactions
        scheduled_inflows = self._get_scheduled_inflows(month_start, month_end)
        scheduled_outflows = self._get_scheduled_outflows(month_start, month_end)
        
        total_inflows = projected_inflows + scheduled_inflows
        total_outflows = projected_outflows + scheduled_outflows
        net_cash_flow = total_inflows - total_outflows
        
        return {
            'projected_inflows': projected_inflows,
            'scheduled_inflows': scheduled_inflows,
            'total_inflows': total_inflows,
            'projected_outflows': projected_outflows,
            'scheduled_outflows': scheduled_outflows,
            'total_outflows': total_outflows,
            'net_cash_flow': net_cash_flow
        }
    
    # =====================================================================
    # FINANCIAL RATIOS & ANALYSIS
    # =====================================================================
    
    def calculate_financial_ratios(self, as_of_date: date = None) -> Dict[str, Any]:
        """Calculate comprehensive financial ratios"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Get balance sheet data
        balance_sheet = self._get_balance_sheet_data(as_of_date)
        
        # Get income statement data (last 12 months)
        year_start = as_of_date - timedelta(days=365)
        income_statement = self._get_income_statement_data(year_start, as_of_date)
        
        ratios = {}
        
        # Liquidity Ratios
        ratios['liquidity'] = self._calculate_liquidity_ratios(balance_sheet)
        
        # Profitability Ratios
        ratios['profitability'] = self._calculate_profitability_ratios(
            balance_sheet, income_statement
        )
        
        # Efficiency Ratios
        ratios['efficiency'] = self._calculate_efficiency_ratios(
            balance_sheet, income_statement
        )
        
        # Leverage Ratios
        ratios['leverage'] = self._calculate_leverage_ratios(balance_sheet)
        
        return {
            'as_of_date': as_of_date,
            'ratios': ratios,
            'balance_sheet_summary': balance_sheet,
            'income_statement_summary': income_statement
        }
    
    # =====================================================================
    # BUDGET VARIANCE ANALYSIS
    # =====================================================================
    
    def generate_budget_variance_analysis(
        self, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """Generate comprehensive budget vs actual analysis"""
        
        # Get actual financial data
        actual_data = self._get_actual_financial_data(start_date, end_date)
        
        # Get budget data (if available)
        budget_data = self._get_budget_data(start_date, end_date)
        
        # Calculate variances
        variance_analysis = self._calculate_budget_variances(
            actual_data, budget_data
        )
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'actual': actual_data,
            'budget': budget_data,
            'variance_analysis': variance_analysis,
            'currency': self.base_currency.code
        }
    
    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    
    def _get_monthly_trend(
        self, 
        accounts, 
        start_date: date, 
        end_date: date, 
        amount_type: str
    ) -> List[Dict[str, Any]]:
        """Get monthly trend data for accounts"""
        monthly_data = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            month_end = current_date + relativedelta(months=1) - timedelta(days=1)
            if month_end > end_date:
                month_end = end_date
            
            amount_field = f'journal_lines__base_currency_{amount_type}_amount'
            
            month_total = JournalEntry.objects.filter(
                tenant=self.tenant,
                entry_date__range=[current_date, month_end],
                status='POSTED'
            ).filter(
                journal_lines__account__in=accounts
            ).aggregate(
                total=Sum(amount_field)
            )['total'] or Decimal('0.00')
            
            monthly_data.append({
                'month': current_date.strftime('%Y-%m'),
                'month_name': current_date.strftime('%B %Y'),
                'amount': month_total
            })
            
            current_date += relativedelta(months=1)
        
        return monthly_data
    
    def _get_account_type_total(
        self, 
        account_types: List[str], 
        start_date: date, 
        end_date: date,
        amount_type: str
    ) -> Decimal:
        """Get total for specific account types"""
        accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type__in=account_types,
            is_active=True
        )
        
        amount_field = f'journal_lines__base_currency_{amount_type}_amount'
        
        total = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__range=[start_date, end_date],
            status='POSTED'
        ).filter(
            journal_lines__account__in=accounts
        ).aggregate(
            total=Sum(amount_field)
        )['total'] or Decimal('0.00')
        
        return total
    
    def _get_current_cash_balance(self) -> Decimal:
        """Get current total cash balance"""
        cash_accounts = Account.objects.filter(
            tenant=self.tenant,
            is_cash_account=True,
            is_active=True
        )
        
        return sum(account.current_balance for account in cash_accounts)
    
    def _get_monthly_cash_flow(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get monthly cash flow data"""
        monthly_data = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            month_end = current_date + relativedelta(months=1) - timedelta(days=1)
            if month_end > end_date:
                month_end = end_date
            
            receipts = Payment.objects.filter(
                tenant=self.tenant,
                payment_date__range=[current_date, month_end],
                payment_type='RECEIVED',
                status='CLEARED'
            ).aggregate(
                total=Sum('base_currency_amount')
            )['total'] or Decimal('0.00')
            
            payments = Payment.objects.filter(
                tenant=self.tenant,
                payment_date__range=[current_date, month_end],
                payment_type='MADE',
                status='CLEARED'
            ).aggregate(
                total=Sum('base_currency_amount')
            )['total'] or Decimal('0.00')
            
            monthly_data.append({
                'month': current_date.strftime('%Y-%m'),
                'month_name': current_date.strftime('%B %Y'),
                'cash_receipts': receipts,
                'cash_payments': payments,
                'net_cash_flow': receipts - payments
            })
            
            current_date += relativedelta(months=1)
        
        return monthly_data