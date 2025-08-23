"""
CRM Dashboard ViewSets - Comprehensive Dashboard Management
Provides unified dashboard views across all CRM modules
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import (
    Lead, Opportunity, Account, Activity, Campaign,
    Ticket, Product, Territory, Team
)
from ..permissions.base import CanViewDashboards
from ..services.analytics_service import AnalyticsService
from ..utils.tenant_utils import get_tenant_context
from ..utils.helpers import get_date_range, format_currency


class DashboardViewSet(viewsets.ViewSet):
    """
    Unified Dashboard ViewSet
    Provides comprehensive dashboard data across all CRM modules
    """
    permission_classes = [IsAuthenticated, CanViewDashboards]
    
    @action(detail=False, methods=['get'])
    def executive_summary(self, request):
        """Get executive-level dashboard summary"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 30))
        
        try:
            service = AnalyticsService(tenant=tenant)
            summary = service.get_executive_summary(
                date_range=date_range,
                user=request.user
            )
            
            return Response({
                'success': True,
                'summary': summary,
                'generated_at': timezone.now().isoformat(),
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Executive summary failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def sales_dashboard(self, request):
        """Get sales-focused dashboard data"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 30))
        
        try:
            service = AnalyticsService(tenant=tenant)
            sales_data = service.get_sales_dashboard_data(
                date_range=date_range,
                territory_id=request.query_params.get('territory_id'),
                team_id=request.query_params.get('team_id'),
                user=request.user
            )
            
            return Response({
                'success': True,
                'sales_dashboard': sales_data,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Sales dashboard failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def marketing_dashboard(self, request):
        """Get marketing-focused dashboard data"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 30))
        
        try:
            service = AnalyticsService(tenant=tenant)
            marketing_data = service.get_marketing_dashboard_data(
                date_range=date_range,
                campaign_id=request.query_params.get('campaign_id'),
                user=request.user
            )
            
            return Response({
                'success': True,
                'marketing_dashboard': marketing_data,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Marketing dashboard failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def support_dashboard(self, request):
        """Get customer support dashboard data"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 30))
        
        try:
            service = AnalyticsService(tenant=tenant)
            support_data = service.get_support_dashboard_data(
                date_range=date_range,
                priority_filter=request.query_params.get('priority'),
                user=request.user
            )
            
            return Response({
                'success': True,
                'support_dashboard': support_data,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Support dashboard failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def personal_dashboard(self, request):
        """Get personal dashboard for individual users"""
        tenant = get_tenant_context(request)
        user = request.user
        
        try:
            service = AnalyticsService(tenant=tenant)
            personal_data = service.get_personal_dashboard_data(
                user=user,
                date_range=int(request.query_params.get('date_range', 30))
            )
            
            return Response({
                'success': True,
                'personal_dashboard': personal_data,
                'user': {
                    'id': user.id,
                    'name': user.get_full_name(),
                    'role': getattr(user, 'role', 'User')
                }
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Personal dashboard failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def real_time_metrics(self, request):
        """Get real-time metrics for live dashboard updates"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            real_time_data = service.get_real_time_metrics(
                user=request.user,
                metrics=request.query_params.getlist('metrics[]')
            )
            
            return Response({
                'success': True,
                'real_time_metrics': real_time_data,
                'timestamp': timezone.now().isoformat(),
                'refresh_interval': 30  # seconds
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Real-time metrics failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)