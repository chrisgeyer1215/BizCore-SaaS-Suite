# backend/apps/finance/viewsets/dashboard.py

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import date, datetime, timedelta
from ..services.dashboard import FinanceDashboardService
from ..services.reporting import FinancialReportingService
from ..serializers import FinanceDashboardSerializer, KPISerializer
from apps.core.permissions import TenantPermission

class FinanceDashboardViewSet(viewsets.GenericViewSet):
    """ViewSet for Finance Dashboard"""
    
    permission_classes = [permissions.IsAuthenticated, TenantPermission]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get finance dashboard overview"""
        period = request.query_params.get('period', 'current_month')
        
        service = FinanceDashboardService(request.tenant)
        dashboard_data = service.get_dashboard_data(period)
        
        serializer = FinanceDashboardSerializer(dashboard_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def kpis(self, request):
        """Get key performance indicators"""
        period = request.query_params.get('period', 'current_month')
        
        service = FinanceDashboardService(request.tenant)
        kpis = service.get_financial_kpis(period)
        
        return Response(kpis)
    
    @action(detail=False, methods=['get'])
    def cash_flow(self, request):
        """Get cash flow data"""
        days = int(request.query_params.get('days', 30))
        
        service = FinanceDashboardService(request.tenant)
        cash_flow_data = service.get_cash_flow_forecast(days)
        
        return Response(cash_flow_data)
    
    @action(detail=False, methods=['get'])
    def aging_summary(self, request):
        """Get aging summary"""
        as_of_date = request.query_params.get('as_of_date')
        if not as_of_date:
            as_of_date = date.today()
        
        service = FinanceDashboardService(request.tenant)
        aging_data = service.get_aging_summary(as_of_date)
        
        return Response(aging_data)
    
    @action(detail=False, methods=['get'])
    def revenue_trend(self, request):
        """Get revenue trend data"""
        months = int(request.query_params.get('months', 12))
        
        service = FinanceDashboardService(request.tenant)
        trend_data = service.get_revenue_trend(months)
        
        return Response(trend_data)
    
    @action(detail=False, methods=['get'])
    def expense_breakdown(self, request):
        """Get expense breakdown by category"""
        period = request.query_params.get('period', 'current_month')
        
        service = FinanceDashboardService(request.tenant)
        expense_data = service.get_expense_breakdown(period)
        
        return Response(expense_data)
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get financial alerts"""
        service = FinanceDashboardService(request.tenant)
        alerts = service.get_financial_alerts()
        
        return Response(alerts)