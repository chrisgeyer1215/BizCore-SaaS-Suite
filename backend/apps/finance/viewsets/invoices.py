# backend/apps/finance/viewsets/invoices.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from ..models import Invoice, InvoiceItem
from ..serializers import (
    InvoiceSerializer, InvoiceListSerializer, InvoiceCreateSerializer,
    InvoiceSendSerializer
)
from ..services.invoice import InvoiceService
from .base import BaseFinanceViewSet

class InvoiceViewSet(BaseFinanceViewSet):
    """ViewSet for Invoices"""
    
    queryset = Invoice.objects.select_related(
        'customer', 'currency', 'approved_by'
    ).prefetch_related('invoice_items__product')
    
    filterset_fields = [
        'status', 'invoice_type', 'customer', 'currency',
        'invoice_date', 'due_date', 'is_recurring'
    ]
    search_fields = [
        'invoice_number', 'reference_number', 'customer__name',
        'description', 'customer_email'
    ]
    ordering_fields = [
        'invoice_date', 'due_date', 'invoice_number', 'total_amount',
        'created_at'
    ]
    ordering = ['-invoice_date', '-invoice_number']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return InvoiceListSerializer
        elif self.action == 'create_invoice':
            return InvoiceCreateSerializer
        elif self.action == 'send_invoices':
            return InvoiceSendSerializer
        return InvoiceSerializer
    
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def create_invoice(self, request):
        """Create a new invoice with items"""
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = InvoiceService(request.tenant)
        try:
            invoice = service.create_invoice(
                customer_id=serializer.validated_data['customer'],
                invoice_date=serializer.validated_data['invoice_date'],
                due_date=serializer.validated_data['due_date'],
                currency=serializer.validated_data['currency'],
                items_data=serializer.validated_data['items'],
                description=serializer.validated_data.get('description'),
                notes=serializer.validated_data.get('notes'),
                user=request.user
            )
            
            response_serializer = InvoiceSerializer(invoice)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an invoice"""
        invoice = self.get_object()
        
        try:
            invoice.approve_invoice(request.user)
            serializer = self.get_serializer(invoice)
            return Response({
                'message': 'Invoice approved successfully',
                'invoice': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send invoice to customer"""
        invoice = self.get_object()
        send_copy_to = request.data.get('send_copy_to')
        
        try:
            result = invoice.send_invoice(send_copy_to)
            if result['success']:
                serializer = self.get_serializer(invoice)
                return Response({
                    'message': 'Invoice sent successfully',
                    'invoice': serializer.data
                })
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def send_invoices(self, request):
        """Send multiple invoices"""
        serializer = InvoiceSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invoice_ids = serializer.validated_data['invoice_ids']
        send_copy_to = serializer.validated_data.get('send_copy_to')
        
        sent_invoices = []
        errors = []
        
        for invoice_id in invoice_ids:
            try:
                invoice = get_object_or_404(self.get_queryset(), id=invoice_id)
                result = invoice.send_invoice(send_copy_to)
                if result['success']:
                    sent_invoices.append(invoice_id)
                else:
                    errors.append({
                        'invoice_id': invoice_id,
                        'error': result['error']
                    })
            except Exception as e:
                errors.append({
                    'invoice_id': invoice_id,
                    'error': str(e)
                })
        
        return Response({
            'sent_invoices': sent_invoices,
            'errors': errors,
            'message': f'Sent {len(sent_invoices)} invoices'
        })
    
    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void an invoice"""
        invoice = self.get_object()
        reason = request.data.get('reason', 'Invoice voided')
        
        try:
            invoice.void_invoice(request.user, reason)
            serializer = self.get_serializer(invoice)
            return Response({
                'message': 'Invoice voided successfully',
                'invoice': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        """Send payment reminder"""
        invoice = self.get_object()
        reminder_type = request.data.get('reminder_type', 'OVERDUE')
        
        try:
            result = invoice.send_reminder(reminder_type)
            if result['success']:
                return Response({
                    'message': 'Reminder sent successfully'
                })
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices"""
        overdue_invoices = self.get_queryset().filter(
            status__in=['OPEN', 'SENT', 'VIEWED'],
            due_date__lt=timezone.now().date()
        )
        
        serializer = InvoiceListSerializer(overdue_invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get invoice summary statistics"""
        queryset = self.get_queryset()
        
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)
        
        from django.db.models import Sum, Count, Avg
        from datetime import date
        
        summary = queryset.aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('total_amount'),
            total_paid=Sum('amount_paid'),
            total_outstanding=Sum('amount_due'),
            average_amount=Avg('total_amount'),
            
            # Status breakdown
            draft_count=Count('id', filter=Q(status='DRAFT')),
            sent_count=Count('id', filter=Q(status__in=['SENT', 'VIEWED'])),
            open_count=Count('id', filter=Q(status='OPEN')),
            paid_count=Count('id', filter=Q(status='PAID')),
            overdue_count=Count('id', filter=Q(
                status__in=['OPEN', 'SENT', 'VIEWED'],
                due_date__lt=date.today()
            ))
        )
        
        return Response(summary)