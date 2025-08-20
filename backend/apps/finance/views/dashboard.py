# backend/apps/finance/views/dashboard.py

"""
Finance Dashboard Views
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from apps.core.permissions import IsTenantUser
from ..models import (
    Invoice, Bill, Payment, Account, JournalEntry,
    BankAccount, Currency, FinanceSettings
)
from ..serializers.reporting import (
    FinanceDashboardSerializer, CashFlowSummarySerializer,
    ARAgingSummarySerializer, APAgingSummarySerializer
)


class FinanceDashboardViewSet(viewsets.GenericViewSet):
    """Finance dashboard data and analytics"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get finance dashboard overview data"""
        tenant = request.tenant
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        
        # Key metrics
        total_ar = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        total_ap = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        overdue_ar = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__lt=today,
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        overdue_ap = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__lt=today,
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        # Cash position
        cash_accounts = Account.objects.filter(
            tenant=tenant,
            is_cash_account=True,
            is_active=True
        )
        total_cash = sum(account.current_balance for account in cash_accounts)
        
        # Recent activity (last 30 days)
        recent_invoices = Invoice.objects.filter(
            tenant=tenant,
            invoice_date__gte=thirty_days_ago
        ).count()
        
        recent_bills = Bill.objects.filter(
            tenant=tenant,
            bill_date__gte=thirty_days_ago
        ).count()
        
        recent_payments = Payment.objects.filter(
            tenant=tenant,
            payment_date__gte=thirty_days_ago
        ).count()
        
        # Revenue and expenses (current month)
        current_month_start = today.replace(day=1)
        
        monthly_revenue = Invoice.objects.filter(
            tenant=tenant,
            invoice_date__gte=current_month_start,
            status__in=['PAID', 'PARTIAL']
        ).aggregate(total=Sum('base_currency_amount_paid'))['total'] or Decimal('0.00')
        
        monthly_expenses = Bill.objects.filter(
            tenant=tenant,
            bill_date__gte=current_month_start,
            status__in=['PAID', 'PARTIAL']
        ).aggregate(total=Sum('base_currency_amount_paid'))['total'] or Decimal('0.00')
        
        data = {
            'total_ar': float(total_ar),
            'total_ap': float(total_ap),
            'overdue_ar': float(overdue_ar),
            'overdue_ap': float(overdue_ap),
            'total_cash': float(total_cash),
            'net_position': float(total_cash + total_ar - total_ap),
            'recent_invoices': recent_invoices,
            'recent_bills': recent_bills,
            'recent_payments': recent_payments,
            'monthly_revenue': float(monthly_revenue),
            'monthly_expenses': float(monthly_expenses),
            'monthly_profit': float(monthly_revenue - monthly_expenses),
        }
        
        serializer = FinanceDashboardSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def cash_flow(self, request):
        """Get cash flow summary for the last 12 months"""
        tenant = request.tenant
        today = date.today()
        twelve_months_ago = today - timedelta(days=365)
        
        # Monthly cash flow data
        cash_flow_data = []
        for i in range(12):
            month_start = (today.replace(day=1) - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            inflows = Payment.objects.filter(
                tenant=tenant,
                payment_type='RECEIVED',
                payment_date__range=[month_start, month_end],
                status='CLEARED'
            ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
            
            outflows = Payment.objects.filter(
                tenant=tenant,
                payment_type='MADE',
                payment_date__range=[month_start, month_end],
                status='CLEARED'
            ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
            
            cash_flow_data.append({
                'month': month_start.strftime('%Y-%m'),
                'inflows': float(inflows),
                'outflows': float(outflows),
                'net_flow': float(inflows - outflows)
            })
        
        return Response({'cash_flow': list(reversed(cash_flow_data))})
    
    @action(detail=False, methods=['get'])
    def ar_aging(self, request):
        """Get accounts receivable aging report"""
        tenant = request.tenant
        today = date.today()
        
        # AR Aging buckets
        current = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__gte=today,
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_1_30 = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=30), today - timedelta(days=1)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_31_60 = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=60), today - timedelta(days=31)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_61_90 = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=90), today - timedelta(days=61)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        over_90 = Invoice.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__lt=today - timedelta(days=90),
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        data = {
            'current': float(current),
            'days_1_30': float(days_1_30),
            'days_31_60': float(days_31_60),
            'days_61_90': float(days_61_90),
            'over_90': float(over_90),
            'total': float(current + days_1_30 + days_31_60 + days_61_90 + over_90)
        }
        
        serializer = ARAgingSummarySerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def ap_aging(self, request):
        """Get accounts payable aging report"""
        tenant = request.tenant
        today = date.today()
        
        # AP Aging buckets
        current = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__gte=today,
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_1_30 = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=30), today - timedelta(days=1)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_31_60 = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=60), today - timedelta(days=31)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        days_61_90 = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__range=[today - timedelta(days=90), today - timedelta(days=61)],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        over_90 = Bill.objects.filter(
            tenant=tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__lt=today - timedelta(days=90),
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        data = {
            'current': float(current),
            'days_1_30': float(days_1_30),
            'days_31_60': float(days_31_60),
            'days_61_90': float(days_61_90),
            'over_90': float(over_90),
            'total': float(current + days_1_30 + days_31_60 + days_61_90 + over_90)
        }
        
        serializer = APAgingSummarySerializer(data)
        return Response(serializer.data)