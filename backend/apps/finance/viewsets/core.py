backend/apps/finance/viewsets/core.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import FinanceSettings, FiscalYear, FinancialPeriod
from ..serializers import (
    FinanceSettingsSerializer, FiscalYearSerializer, FinancialPeriodSerializer
)
from .base import BaseFinanceViewSet

class FinanceSettingsViewSet(BaseFinanceViewSet):
    """ViewSet for Finance Settings"""
    
    queryset = FinanceSettings.objects.all()
    serializer_class = FinanceSettingsSerializer
    
    def get_object(self):
        """Get or create finance settings for tenant"""
        obj, created = FinanceSettings.objects.get_or_create(
            tenant=self.request.tenant,
            defaults={'company_name': 'My Company'}
        )
        return obj
    
    def list(self, request, *args, **kwargs):
        """Return single settings object"""
        settings = self.get_object()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Update existing settings instead of creating new"""
        settings = self.get_object()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """Reset settings to default values"""
        settings = self.get_object()
        
        # Reset to default values
        settings.accounting_method = 'ACCRUAL'
        settings.base_currency = 'USD'
        settings.enable_multi_currency = True
        settings.inventory_valuation_method = 'FIFO'
        settings.tax_calculation_method = 'EXCLUSIVE'
        settings.save()
        
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


class FiscalYearViewSet(BaseFinanceViewSet):
    """ViewSet for Fiscal Years"""
    
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    filterset_fields = ['year', 'status']
    search_fields = ['year']
    ordering_fields = ['year', 'start_date', 'end_date']
    ordering = ['-year']
    
    @action(detail=True, methods=['post'])
    def close_year(self, request, pk=None):
        """Close fiscal year"""
        fiscal_year = self.get_object()
        
        if fiscal_year.status == 'CLOSED':
            return Response(
                {'error': 'Fiscal year is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            fiscal_year.close_fiscal_year(request.user)
            return Response({'message': 'Fiscal year closed successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current fiscal year"""
        try:
            current_year = self.get_queryset().filter(status='OPEN').first()
            if not current_year:
                return Response(
                    {'error': 'No open fiscal year found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = self.get_serializer(current_year)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class FinancialPeriodViewSet(BaseFinanceViewSet):
    """ViewSet for Financial Periods"""
    
    queryset = FinancialPeriod.objects.all()
    serializer_class = FinancialPeriodSerializer
    filterset_fields = ['period_type', 'status', 'fiscal_year']
    search_fields = ['name']
    ordering_fields = ['start_date', 'end_date', 'name']
    ordering = ['-start_date']
    
    @action(detail=True, methods=['post'])
    def close_period(self, request, pk=None):
        """Close financial period"""
        period = self.get_object()
        
        if period.status == 'CLOSED':
            return Response(
                {'error': 'Period is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        period.status = 'CLOSED'
        period.closed_by = request.user
        period.closed_date = timezone.now()
        period.save()
        
        return Response({'message': 'Period closed successfully'})