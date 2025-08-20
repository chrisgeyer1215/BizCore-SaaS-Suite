# backend/apps/finance/viewsets/vendors.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from ..models import Vendor, VendorContact, Bill
from ..serializers import (
    VendorSerializer, VendorListSerializer, VendorContactSerializer,
    BillSerializer, BillListSerializer
)
from ..services.vendor import VendorService
from .base import BaseFinanceViewSet

class VendorViewSet(BaseFinanceViewSet):
    """ViewSet for Vendors"""
    
    queryset = Vendor.objects.select_related('currency').prefetch_related('contacts')
    filterset_fields = [
        'vendor_type', 'status', 'currency', 'is_inventory_supplier',
        'is_tax_exempt', 'is_1099_vendor'
    ]
    search_fields = [
        'vendor_number', 'company_name', 'display_name', 'email',
        'primary_contact', 'supplier_code'
    ]
    ordering_fields = [
        'company_name', 'vendor_number', 'current_balance', 'created_at'
    ]
    ordering = ['company_name']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return VendorListSerializer
        return VendorSerializer
    
    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """Get vendor financial summary"""
        vendor = self.get_object()
        
        service = VendorService(request.tenant)
        summary = service.get_vendor_financial_summary(vendor.id)
        
        return Response(summary)
    
    @action(detail=True, methods=['get'])
    def bills(self, request, pk=None):
        """Get vendor bills"""
        vendor = self.get_object()
        bills = Bill.objects.filter(vendor=vendor, tenant=request.tenant)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            bills = bills.filter(status=status_filter)
        
        serializer = BillListSerializer(bills, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_performance_metrics(self, request, pk=None):
        """Update vendor performance metrics"""
        vendor = self.get_object()
        
        try:
            vendor.update_performance_metrics()
            serializer = self.get_serializer(vendor)
            return Response({
                'message': 'Performance metrics updated successfully',
                'vendor': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def top_by_purchases(self, request):
        """Get top vendors by purchase amount"""
        limit = int(request.query_params.get('limit', 10))
        
        # Get vendors ordered by YTD purchases
        vendors = self.get_queryset().order_by('-current_balance')[:limit]
        
        vendor_data = []
        for vendor in vendors:
            vendor_data.append({
                'vendor': VendorListSerializer(vendor).data,
                'ytd_purchases': vendor.get_ytd_purchases(),
                'outstanding_balance': vendor.get_outstanding_balance()
            })
        
        return Response(vendor_data)


class BillViewSet(BaseFinanceViewSet):
    """ViewSet for Bills"""
    
    queryset = Bill.objects.select_related(
        'vendor', 'currency', 'approved_by'
    ).prefetch_related('bill_items__product')
    
    filterset_fields = [
        'status', 'bill_type', 'vendor', 'currency',
        'bill_date', 'due_date', 'is_recurring'
    ]
    search_fields = [
        'bill_number', 'vendor_invoice_number', 'reference_number',
        'vendor__company_name', 'description'
    ]
    ordering_fields = [
        'bill_date', 'due_date', 'bill_number', 'total_amount', 'created_at'
    ]
    ordering = ['-bill_date', '-bill_number']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BillListSerializer
        return BillSerializer
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a bill"""
        bill = self.get_object()
        
        try:
            bill.approve_bill(request.user)
            serializer = self.get_serializer(bill)
            return Response({
                'message': 'Bill approved successfully',
                'bill': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue bills"""
        from datetime import date
        
        overdue_bills = self.get_queryset().filter(
            status__in=['OPEN', 'APPROVED'],
            due_date__lt=date.today()
        )
        
        serializer = BillListSerializer(overdue_bills, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get bills pending approval"""
        pending_bills = self.get_queryset().filter(status='PENDING_APPROVAL')
        
        serializer = BillListSerializer(pending_bills, many=True)
        return Response(serializer.data)