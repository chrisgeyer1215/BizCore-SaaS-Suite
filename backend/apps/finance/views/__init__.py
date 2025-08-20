# backend/apps/finance/views/__init__.py

"""
Finance Module Views
API ViewSets and endpoints for all finance functionality
"""

from .dashboard import FinanceDashboardViewSet
from .accounts import AccountCategoryViewSet, AccountViewSet
from .journal_entries import JournalEntryViewSet
from .bank_reconciliation import BankAccountViewSet, BankReconciliationViewSet
from .invoices import InvoiceViewSet
from .bills import BillViewSet
from .payments import PaymentViewSet
from .vendors import VendorViewSet
from .customers import CustomerFinancialViewSet
from .reports import FinancialReportsViewSet
from .settings import FinanceSettingsViewSet

__all__ = [
    'FinanceDashboardViewSet',
    'AccountCategoryViewSet',
    'AccountViewSet', 
    'JournalEntryViewSet',
    'BankAccountViewSet',
    'BankReconciliationViewSet',
    'InvoiceViewSet',
    'BillViewSet',
    'PaymentViewSet',
    'VendorViewSet',
    'CustomerFinancialViewSet',
    'FinancialReportsViewSet',
    'FinanceSettingsViewSet',
]


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


# backend/apps/finance/views/accounts.py

"""
Chart of Accounts Management Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterFilter
from django.db.models import Q

from apps.core.permissions import IsTenantUser
from ..models import AccountCategory, Account
from ..serializers.accounts import (
    AccountCategorySerializer, AccountSerializer, AccountTreeSerializer
)
from ..filters import AccountFilter


class AccountCategoryViewSet(viewsets.ModelViewSet):
    """Account category management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    serializer_class = AccountCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'account_type', 'sort_order']
    ordering = ['account_type', 'sort_order', 'name']
    
    def get_queryset(self):
        return AccountCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )


class AccountViewSet(viewsets.ModelViewSet):
    """Chart of accounts management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    serializer_class = AccountSerializer
    filter_backends = [DjangoFilterFilter, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AccountFilter
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'account_type', 'level']
    ordering = ['code']
    
    def get_queryset(self):
        return Account.objects.filter(
            tenant=self.request.tenant
        ).select_related('category', 'parent_account', 'currency')
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get accounts in tree structure"""
        accounts = Account.objects.filter(
            tenant=request.tenant,
            parent_account__isnull=True,
            is_active=True
        ).order_by('code')
        
        serializer = AccountTreeSerializer(accounts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get accounts grouped by type"""
        account_type = request.query_params.get('type')
        if not account_type:
            return Response({'error': 'Account type is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        accounts = Account.objects.filter(
            tenant=request.tenant,
            account_type=account_type,
            is_active=True
        ).order_by('code')
        
        serializer = AccountSerializer(accounts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get account balance"""
        account = self.get_object()
        as_of_date = request.query_params.get('as_of_date')
        
        from ..services.accounting import AccountingService
        service = AccountingService(request.tenant)
        
        balance = service.get_account_balance(
            account.id, 
            as_of_date=as_of_date
        )
        
        return Response({
            'account_id': account.id,
            'account_code': account.code,
            'account_name': account.name,
            'balance': float(balance),
            'as_of_date': as_of_date
        })
    
    @action(detail=False, methods=['post'])
    def import_chart(self, request):
        """Import chart of accounts from template"""
        template_type = request.data.get('template_type', 'standard')
        
        from ..services.accounting import AccountingService
        service = AccountingService(request.tenant)
        
        try:
            result = service.import_chart_of_accounts(template_type)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


# backend/apps/finance/views/journal_entries.py

"""
Journal Entry Management Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterFilter

from apps.core.permissions import IsTenantUser
from ..models import JournalEntry, JournalEntryLine
from ..serializers.journal import (
    JournalEntrySerializer, JournalEntryCreateSerializer
)
from ..filters import JournalEntryFilter


class JournalEntryViewSet(viewsets.ModelViewSet):
    """Journal entry management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    filter_backends = [DjangoFilterFilter, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JournalEntryFilter
    search_fields = ['entry_number', 'description', 'reference_number']
    ordering_fields = ['entry_date', 'entry_number', 'total_debit']
    ordering = ['-entry_date', '-entry_number']
    
    def get_queryset(self):
        return JournalEntry.objects.filter(
            tenant=self.request.tenant
        ).select_related('currency', 'created_by', 'posted_by').prefetch_related('journal_lines')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return JournalEntryCreateSerializer
        return JournalEntrySerializer
    
    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def post(self, request, pk=None):
        """Post a journal entry"""
        journal_entry = self.get_object()
        
        if journal_entry.status == 'POSTED':
            return Response(
                {'error': 'Journal entry is already posted'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            journal_entry.post_entry(request.user)
            return Response({'message': 'Journal entry posted successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """Reverse a journal entry"""
        journal_entry = self.get_object()
        reason = request.data.get('reason', '')
        
        if journal_entry.status != 'POSTED':
            return Response(
                {'error': 'Only posted entries can be reversed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reversal = journal_entry.reverse_entry(request.user, reason)
            serializer = JournalEntrySerializer(reversal, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get journal entry templates"""
        templates = [
            {
                'name': 'Cash Receipt',
                'type': 'RECEIPT',
                'lines': [
                    {'account_type': 'CURRENT_ASSET', 'debit': True},
                    {'account_type': 'REVENUE', 'credit': True}
                ]
            },
            {
                'name': 'Cash Payment',
                'type': 'PAYMENT',
                'lines': [
                    {'account_type': 'EXPENSE', 'debit': True},
                    {'account_type': 'CURRENT_ASSET', 'credit': True}
                ]
            },
            {
                'name': 'Depreciation',
                'type': 'DEPRECIATION',
                'lines': [
                    {'account_type': 'EXPENSE', 'debit': True},
                    {'account_type': 'FIXED_ASSET', 'credit': True}
                ]
            }
        ]
        return Response(templates)


# backend/apps/finance/views/invoices.py

"""
Invoice Management Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterFilter
from django.http import HttpResponse
from django.template.loader import render_to_string

from apps.core.permissions import IsTenantUser
from ..models import Invoice, InvoiceItem
from ..serializers.invoicing import InvoiceSerializer, InvoiceCreateSerializer
from ..filters import InvoiceFilter


class InvoiceViewSet(viewsets.ModelViewSet):
    """Invoice management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    filter_backends = [DjangoFilterFilter, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InvoiceFilter
    search_fields = ['invoice_number', 'customer__name', 'reference_number']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount', 'status']
    ordering = ['-invoice_date', '-invoice_number']
    
    def get_queryset(self):
        return Invoice.objects.filter(
            tenant=self.request.tenant
        ).select_related('customer', 'currency').prefetch_related('invoice_items')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send invoice to customer"""
        invoice = self.get_object()
        send_copy_to = request.data.get('send_copy_to')
        
        from ..services.invoice import InvoiceService
        service = InvoiceService(request.tenant)
        
        result = service.send_invoice(invoice, send_copy_to)
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve invoice"""
        invoice = self.get_object()
        
        try:
            invoice.approve_invoice(request.user)
            return Response({'message': 'Invoice approved successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Generate invoice PDF"""
        invoice = self.get_object()
        
        from ..services.invoice import InvoiceService
        service = InvoiceService(request.tenant)
        
        pdf_content = service.generate_pdf(invoice)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record payment against invoice"""
        invoice = self.get_object()
        
        from ..services.payment import PaymentService
        service = PaymentService(request.tenant)
        
        try:
            payment = service.record_invoice_payment(
                invoice=invoice,
                amount=request.data.get('amount'),
                payment_method=request.data.get('payment_method'),
                payment_date=request.data.get('payment_date'),
                reference_number=request.data.get('reference_number'),
                bank_account_id=request.data.get('bank_account_id')
            )
            
            from ..serializers.payments import PaymentSerializer
            serializer = PaymentSerializer(payment, context={'request': request})
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices"""
        from datetime import date
        
        overdue_invoices = self.get_queryset().filter(
            due_date__lt=date.today(),
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)