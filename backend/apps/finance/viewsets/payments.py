# backend/apps/finance/viewsets/payments.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from ..models import Payment, PaymentApplication
from ..serializers import (
    PaymentSerializer, PaymentListSerializer, PaymentCreateSerializer
)
from ..services.payment import PaymentService
from .base import BaseFinanceViewSet

class PaymentViewSet(BaseFinanceViewSet):
    """ViewSet for Payments"""
    
    queryset = Payment.objects.select_related(
        'customer', 'vendor', 'currency', 'bank_account'
    ).prefetch_related('applications__invoice', 'applications__bill')
    
    filterset_fields = [
        'payment_type', 'payment_method', 'status', 'customer',
        'vendor', 'currency', 'payment_date'
    ]
    search_fields = [
        'payment_number', 'reference_number', 'external_transaction_id',
        'customer__name', 'vendor__company_name', 'description'
    ]
    ordering_fields = [
        'payment_date', 'payment_number', 'amount', 'created_at'
    ]
    ordering = ['-payment_date', '-payment_number']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PaymentListSerializer
        elif self.action in ['create_payment', 'create']:
            return PaymentCreateSerializer
        return PaymentSerializer
    
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def create_payment(self, request):
        """Create a new payment"""
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = PaymentService(request.tenant)
        try:
            payment = service.create_payment(
                payment_type=serializer.validated_data['payment_type'],
                payment_method=serializer.validated_data['payment_method'],
                payment_date=serializer.validated_data['payment_date'],
                amount=serializer.validated_data['amount'],
                currency=serializer.validated_data['currency'],
                bank_account_id=serializer.validated_data['bank_account'],
                customer_id=serializer.validated_data.get('customer'),
                vendor_id=serializer.validated_data.get('vendor'),
                reference_number=serializer.validated_data.get('reference_number'),
                description=serializer.validated_data.get('description'),
                check_number=serializer.validated_data.get('check_number'),
                check_date=serializer.validated_data.get('check_date'),
                user=request.user
            )
            
            response_serializer = PaymentSerializer(payment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def apply_to_invoices(self, request, pk=None):
        """Apply payment to invoices"""
        payment = self.get_object()
        applications = request.data.get('applications', [])
        
        if payment.payment_type != 'RECEIVED':
            return Response(
                {'error': 'Only received payments can be applied to invoices'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment.apply_to_invoices(applications)
            serializer = self.get_serializer(payment)
            return Response({
                'message': 'Payment applied to invoices successfully',
                'payment': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def apply_to_bills(self, request, pk=None):
        """Apply payment to bills"""
        payment = self.get_object()
        applications = request.data.get('applications', [])
        
        if payment.payment_type != 'MADE':
            return Response(
                {'error': 'Only made payments can be applied to bills'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment.apply_to_bills(applications)
            serializer = self.get_serializer(payment)
            return Response({
                'message': 'Payment applied to bills successfully',
                'payment': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def process_refund(self, request, pk=None):
        """Process a refund for payment"""
        payment = self.get_object()
        refund_amount = request.data.get('refund_amount')
        
        try:
            refund_payment = payment.process_refund(refund_amount)
            serializer = self.get_serializer(refund_payment)
            return Response({
                'message': 'Refund processed successfully',
                'refund_payment': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def unallocated(self, request):
        """Get unallocated payments"""
        # Get payments with remaining amount to allocate
        unallocated_payments = []
        
        for payment in self.get_queryset().filter(status='CLEARED'):
            applications_total = sum(
                app.amount_applied for app in payment.applications.all()
            )
            if payment.amount > applications_total:
                unallocated_payments.append(payment)
        
        serializer = PaymentListSerializer(unallocated_payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get payment summary statistics"""
        queryset = self.get_queryset()
        
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        
        from django.db.models import Sum, Count, Avg
        
        summary = queryset.aggregate(
            total_payments=Count('id'),
            total_amount=Sum('amount'),
            average_amount=Avg('amount'),
            
            # By type
            received_count=Count('id', filter=Q(payment_type='RECEIVED')),
            received_amount=Sum('amount', filter=Q(payment_type='RECEIVED')),
            made_count=Count('id', filter=Q(payment_type='MADE')),
            made_amount=Sum('amount', filter=Q(payment_type='MADE')),
            
            # By status
            pending_count=Count('id', filter=Q(status='PENDING')),
            cleared_count=Count('id', filter=Q(status='CLEARED')),
            bounced_count=Count('id', filter=Q(status='BOUNCED')),
        )
        
        return Response(summary)