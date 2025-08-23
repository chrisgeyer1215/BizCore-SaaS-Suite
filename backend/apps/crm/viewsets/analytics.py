"""
CRM Analytics ViewSets - Complete Business Intelligence Implementation
Provides comprehensive reporting, dashboards, and analytics across all CRM modules
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from ..models import (
    Report, Dashboard, Forecast, PerformanceMetric,
    Lead, Opportunity, Account, Contact, Activity,
    Campaign, Ticket, Product
)
from ..serializers.analytics import (
    ReportSerializer, DashboardSerializer, 
    ForecastSerializer, PerformanceMetricSerializer
)
from ..permissions.analytics import (
    CanViewAnalytics, CanManageReports,
    CanViewDashboards, CanViewForecast
)
from ..services.analytics_service import AnalyticsService
from ..utils.helpers import get_date_range, format_percentage
from ..utils.tenant_utils import get_tenant_context


class ReportViewSet(viewsets.ModelViewSet):
    """
    Advanced Report Management ViewSet
    Handles custom report creation, scheduling, and distribution
    """
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated, CanViewAnalytics]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Report.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('created_by', 'modified_by')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Generate report data based on report configuration"""
        report = self.get_object()
        
        try:
            service = AnalyticsService(tenant=report.tenant)
            data = service.generate_report(
                report=report,
                user=request.user,
                filters=request.data.get('filters', {}),
                date_range=request.data.get('date_range')
            )
            
            return Response({
                'success': True,
                'data': data,
                'metadata': {
                    'report_name': report.name,
                    'generated_at': timezone.now().isoformat(),
                    'record_count': len(data.get('results', [])),
                    'filters_applied': request.data.get('filters', {}),
                    'date_range': request.data.get('date_range')
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Report generation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        """Export report in various formats"""
        report = self.get_object()
        export_format = request.data.get('format', 'csv')
        
        try:
            service = AnalyticsService(tenant=report.tenant)
            export_data = service.export_report(
                report=report,
                format=export_format,
                filters=request.data.get('filters', {}),
                date_range=request.data.get('date_range')
            )
            
            return Response({
                'success': True,
                'download_url': export_data['url'],
                'filename': export_data['filename'],
                'format': export_format,
                'expires_at': export_data['expires_at']
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Export failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Schedule automated report generation"""
        report = self.get_object()
        schedule_config = request.data
        
        try:
            service = AnalyticsService(tenant=report.tenant)
            schedule = service.schedule_report(
                report=report,
                frequency=schedule_config.get('frequency'),
                recipients=schedule_config.get('recipients', []),
                format=schedule_config.get('format', 'pdf'),
                filters=schedule_config.get('filters', {})
            )
            
            return Response({
                'success': True,
                'schedule_id': schedule.id,
                'next_run': schedule.next_run_at,
                'frequency': schedule.frequency,
                'recipients': schedule.recipients
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Scheduling failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get available report templates"""
        tenant = get_tenant_context(request)
        
        templates = [
            {
                'id': 'sales_pipeline',
                'name': 'Sales Pipeline Analysis',
                'description': 'Complete pipeline health and conversion analysis',
                'category': 'Sales',
                'fields': ['opportunity_stage', 'value', 'probability', 'close_date'],
                'charts': ['pipeline_funnel', 'conversion_rates', 'stage_duration']
            },
            {
                'id': 'lead_performance',
                'name': 'Lead Performance Report',
                'description': 'Lead generation, quality, and conversion metrics',
                'category': 'Marketing',
                'fields': ['lead_source', 'score', 'status', 'conversion_date'],
                'charts': ['source_performance', 'scoring_distribution', 'conversion_trends']
            },
            {
                'id': 'customer_satisfaction',
                'name': 'Customer Satisfaction Analysis',
                'description': 'Support ticket satisfaction and resolution metrics',
                'category': 'Support',
                'fields': ['ticket_priority', 'resolution_time', 'satisfaction_rating'],
                'charts': ['satisfaction_trends', 'resolution_times', 'sla_compliance']
            },
            {
                'id': 'revenue_forecast',
                'name': 'Revenue Forecasting Report',
                'description': 'Revenue predictions and pipeline analysis',
                'category': 'Finance',
                'fields': ['expected_revenue', 'quarter', 'probability', 'close_date'],
                'charts': ['revenue_forecast', 'quarterly_trends', 'pipeline_value']
            },
            {
                'id': 'activity_analysis',
                'name': 'Activity & Engagement Report',
                'description': 'User activity patterns and engagement metrics',
                'category': 'Operations',
                'fields': ['activity_type', 'frequency', 'outcome', 'user'],
                'charts': ['activity_distribution', 'engagement_trends', 'user_productivity']
            },
            {
                'id': 'campaign_roi',
                'name': 'Campaign ROI Analysis',
                'description': 'Marketing campaign performance and ROI metrics',
                'category': 'Marketing',
                'fields': ['campaign_name', 'cost', 'leads_generated', 'revenue'],
                'charts': ['roi_comparison', 'cost_per_lead', 'conversion_funnel']
            }
        ]
        
        return Response({
            'success': True,
            'templates': templates,
            'categories': ['Sales', 'Marketing', 'Support', 'Finance', 'Operations']
        })


class DashboardViewSet(viewsets.ModelViewSet):
    """
    Advanced Dashboard Management ViewSet
    Handles interactive dashboards with real-time widgets
    """
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated, CanViewDashboards]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Dashboard.objects.filter(
            tenant=tenant,
            is_active=True
        ).prefetch_related('widgets')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get real-time dashboard data"""
        dashboard = self.get_object()
        date_range = request.query_params.get('date_range', '30')
        
        try:
            service = AnalyticsService(tenant=dashboard.tenant)
            dashboard_data = service.get_dashboard_data(
                dashboard=dashboard,
                date_range=int(date_range),
                user=request.user
            )
            
            return Response({
                'success': True,
                'dashboard_id': dashboard.id,
                'name': dashboard.name,
                'data': dashboard_data,
                'last_updated': timezone.now().isoformat(),
                'refresh_interval': dashboard.refresh_interval
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Dashboard data load failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_widget(self, request, pk=None):
        """Add widget to dashboard"""
        dashboard = self.get_object()
        widget_config = request.data
        
        try:
            service = AnalyticsService(tenant=dashboard.tenant)
            widget = service.add_dashboard_widget(
                dashboard=dashboard,
                widget_type=widget_config.get('type'),
                title=widget_config.get('title'),
                config=widget_config.get('config', {}),
                position=widget_config.get('position', {}),
                size=widget_config.get('size', {})
            )
            
            return Response({
                'success': True,
                'widget': {
                    'id': widget.id,
                    'type': widget.widget_type,
                    'title': widget.title,
                    'position': widget.position,
                    'size': widget.size
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Widget creation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def remove_widget(self, request, pk=None):
        """Remove widget from dashboard"""
        dashboard = self.get_object()
        widget_id = request.data.get('widget_id')
        
        try:
            widget = dashboard.widgets.get(id=widget_id)
            widget.delete()
            
            return Response({
                'success': True,
                'message': 'Widget removed successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Widget removal failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def widget_types(self, request):
        """Get available widget types and configurations"""
        widget_types = [
            {
                'type': 'kpi_card',
                'name': 'KPI Card',
                'description': 'Single metric with trend indicator',
                'config_fields': ['metric', 'comparison_period', 'format'],
                'sizes': ['small', 'medium']
            },
            {
                'type': 'line_chart',
                'name': 'Line Chart',
                'description': 'Time series data visualization',
                'config_fields': ['metrics', 'date_range', 'granularity'],
                'sizes': ['medium', 'large', 'xlarge']
            },
            {
                'type': 'bar_chart',
                'name': 'Bar Chart',
                'description': 'Categorical data comparison',
                'config_fields': ['category', 'metric', 'limit'],
                'sizes': ['medium', 'large']
            },
            {
                'type': 'pie_chart',
                'name': 'Pie Chart',
                'description': 'Distribution visualization',
                'config_fields': ['category', 'metric', 'limit'],
                'sizes': ['small', 'medium']
            },
            {
                'type': 'funnel_chart',
                'name': 'Funnel Chart',
                'description': 'Conversion funnel visualization',
                'config_fields': ['stages', 'metric'],
                'sizes': ['medium', 'large']
            },
            {
                'type': 'table',
                'name': 'Data Table',
                'description': 'Tabular data display',
                'config_fields': ['fields', 'filters', 'limit'],
                'sizes': ['medium', 'large', 'xlarge']
            },
            {
                'type': 'leaderboard',
                'name': 'Leaderboard',
                'description': 'Top performers ranking',
                'config_fields': ['entity', 'metric', 'period', 'limit'],
                'sizes': ['medium', 'large']
            },
            {
                'type': 'activity_feed',
                'name': 'Activity Feed',
                'description': 'Recent activities and updates',
                'config_fields': ['activity_types', 'limit'],
                'sizes': ['medium', 'large']
            }
        ]
        
        return Response({
            'success': True,
            'widget_types': widget_types
        })


class ForecastViewSet(viewsets.ModelViewSet):
    """
    Advanced Sales Forecasting ViewSet
    Provides AI-powered revenue and sales predictions
    """
    serializer_class = ForecastSerializer
    permission_classes = [IsAuthenticated, CanViewForecast]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Forecast.objects.filter(
            tenant=tenant,
            is_active=True
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=False, methods=['post'])
    def generate_revenue_forecast(self, request):
        """Generate AI-powered revenue forecast"""
        tenant = get_tenant_context(request)
        forecast_params = request.data
        
        try:
            service = AnalyticsService(tenant=tenant)
            forecast = service.generate_revenue_forecast(
                period_type=forecast_params.get('period_type', 'quarterly'),
                periods_ahead=forecast_params.get('periods_ahead', 4),
                include_pipeline=forecast_params.get('include_pipeline', True),
                confidence_level=forecast_params.get('confidence_level', 0.85),
                filters=forecast_params.get('filters', {})
            )
            
            return Response({
                'success': True,
                'forecast': forecast,
                'metadata': {
                    'model_accuracy': forecast.get('model_accuracy'),
                    'confidence_level': forecast.get('confidence_level'),
                    'data_points_used': forecast.get('data_points_used'),
                    'generated_at': timezone.now().isoformat()
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Forecast generation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def pipeline_forecast(self, request):
        """Generate pipeline-based forecast"""
        tenant = get_tenant_context(request)
        forecast_params = request.data
        
        try:
            service = AnalyticsService(tenant=tenant)
            forecast = service.generate_pipeline_forecast(
                quarter=forecast_params.get('quarter'),
                year=forecast_params.get('year'),
                probability_threshold=forecast_params.get('probability_threshold', 0.25),
                include_weighted=forecast_params.get('include_weighted', True),
                team_filter=forecast_params.get('team_filter'),
                territory_filter=forecast_params.get('territory_filter')
            )
            
            return Response({
                'success': True,
                'forecast': forecast,
                'summary': {
                    'total_pipeline_value': forecast.get('total_pipeline_value'),
                    'weighted_forecast': forecast.get('weighted_forecast'),
                    'best_case': forecast.get('best_case'),
                    'worst_case': forecast.get('worst_case'),
                    'opportunities_count': forecast.get('opportunities_count')
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Pipeline forecast failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def forecast_accuracy(self, request):
        """Get historical forecast accuracy metrics"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            accuracy_data = service.get_forecast_accuracy(
                periods_back=int(request.query_params.get('periods_back', 8)),
                forecast_type=request.query_params.get('forecast_type', 'all')
            )
            
            return Response({
                'success': True,
                'accuracy_metrics': accuracy_data,
                'summary': {
                    'average_accuracy': accuracy_data.get('average_accuracy'),
                    'trend': accuracy_data.get('trend'),
                    'last_updated': accuracy_data.get('last_updated')
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Accuracy calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class PerformanceMetricViewSet(viewsets.ModelViewSet):
    """
    Performance Metrics Management ViewSet
    Tracks and analyzes KPIs across all CRM modules
    """
    serializer_class = PerformanceMetricSerializer
    permission_classes = [IsAuthenticated, CanViewAnalytics]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return PerformanceMetric.objects.filter(
            tenant=tenant,
            is_active=True
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=False, methods=['get'])
    def kpis(self, request):
        """Get current KPI values across all modules"""
        tenant = get_tenant_context(request)
        date_range = request.query_params.get('date_range', '30')
        
        try:
            service = AnalyticsService(tenant=tenant)
            kpis = service.get_current_kpis(
                date_range=int(date_range),
                modules=request.query_params.getlist('modules[]'),
                user=request.user
            )
            
            return Response({
                'success': True,
                'kpis': kpis,
                'date_range': f"Last {date_range} days",
                'generated_at': timezone.now().isoformat()
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"KPI calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get KPI trends over time"""
        tenant = get_tenant_context(request)
        metric_type = request.query_params.get('metric_type')
        period = request.query_params.get('period', 'daily')
        
        try:
            service = AnalyticsService(tenant=tenant)
            trends = service.get_metric_trends(
                metric_type=metric_type,
                period=period,
                days_back=int(request.query_params.get('days_back', 90))
            )
            
            return Response({
                'success': True,
                'trends': trends,
                'metric_type': metric_type,
                'period': period
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Trend calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def benchmarks(self, request):
        """Get industry benchmarks and comparisons"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            benchmarks = service.get_industry_benchmarks(
                industry=request.query_params.get('industry'),
                company_size=request.query_params.get('company_size'),
                metrics=request.query_params.getlist('metrics[]')
            )
            
            return Response({
                'success': True,
                'benchmarks': benchmarks,
                'comparison_data': service.compare_with_benchmarks(
                    tenant_metrics=service.get_current_kpis(30),
                    benchmarks=benchmarks
                )
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Benchmark comparison failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class AnalyticsViewSet(viewsets.ViewSet):
    """
    General Analytics ViewSet
    Provides cross-module analytics and insights
    """
    permission_classes = [IsAuthenticated, CanViewAnalytics]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get comprehensive analytics overview"""
        tenant = get_tenant_context(request)
        date_range = request.query_params.get('date_range', '30')
        
        try:
            service = AnalyticsService(tenant=tenant)
            overview = service.get_analytics_overview(
                date_range=int(date_range),
                user=request.user
            )
            
            return Response({
                'success': True,
                'overview': overview,
                'date_range': f"Last {date_range} days",
                'modules_analyzed': ['leads', 'opportunities', 'activities', 'campaigns', 'tickets']
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Overview generation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def conversion_funnel(self, request):
        """Get conversion funnel analytics"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            funnel = service.get_conversion_funnel(
                date_range=int(request.query_params.get('date_range', 90)),
                source_filter=request.query_params.get('source_filter'),
                campaign_filter=request.query_params.get('campaign_filter')
            )
            
            return Response({
                'success': True,
                'funnel': funnel,
                'conversion_rates': {
                    'lead_to_opportunity': funnel.get('lead_to_opportunity_rate'),
                    'opportunity_to_deal': funnel.get('opportunity_to_deal_rate'),
                    'overall_conversion': funnel.get('overall_conversion_rate')
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Funnel analysis failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def cohort_analysis(self, request):
        """Get customer cohort analysis"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            cohorts = service.get_cohort_analysis(
                cohort_type=request.query_params.get('cohort_type', 'monthly'),
                metric=request.query_params.get('metric', 'retention'),
                periods=int(request.query_params.get('periods', 12))
            )
            
            return Response({
                'success': True,
                'cohorts': cohorts,
                'cohort_type': request.query_params.get('cohort_type', 'monthly'),
                'metric': request.query_params.get('metric', 'retention')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Cohort analysis failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def predictive_insights(self, request):
        """Get AI-powered predictive insights"""
        tenant = get_tenant_context(request)
        
        try:
            service = AnalyticsService(tenant=tenant)
            insights = service.get_predictive_insights(
                insight_types=request.query_params.getlist('types[]') or ['churn', 'upsell', 'close_probability'],
                confidence_threshold=float(request.query_params.get('confidence_threshold', 0.7))
            )
            
            return Response({
                'success': True,
                'insights': insights,
                'model_info': {
                    'last_trained': insights.get('model_last_trained'),
                    'accuracy_score': insights.get('model_accuracy'),
                    'data_points': insights.get('training_data_points')
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Predictive analysis failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def export_analytics(self, request):
        """Export analytics data in various formats"""
        tenant = get_tenant_context(request)
        export_type = request.query_params.get('export_type', 'comprehensive')
        format_type = request.query_params.get('format', 'excel')
        
        try:
            service = AnalyticsService(tenant=tenant)
            export_data = service.export_analytics(
                export_type=export_type,
                format=format_type,
                date_range=int(request.query_params.get('date_range', 90)),
                modules=request.query_params.getlist('modules[]')
            )
            
            return Response({
                'success': True,
                'download_url': export_data['url'],
                'filename': export_data['filename'],
                'format': format_type,
                'expires_at': export_data['expires_at'],
                'file_size': export_data['file_size']
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Analytics export failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
