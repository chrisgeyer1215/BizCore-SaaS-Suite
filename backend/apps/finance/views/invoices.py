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