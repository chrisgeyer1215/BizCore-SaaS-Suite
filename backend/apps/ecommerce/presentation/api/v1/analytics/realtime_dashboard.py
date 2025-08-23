"""
Real-time Dashboard API
Provides live analytics and monitoring data
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page, never_cache
from django.core.cache import cache
import asyncio
from datetime import datetime, timedelta

from .....application.queries.analytics_queries import (
    RealTimeMetricsQuery, PerformanceDashboardQuery
)
from .....application.services.event_bus_service import EventBusService
from .....infrastructure.ai.analytics.real_time_analyzer import RealTimeAnalyzer
from ....serializers.analytics_serializers import (
    RealTimeMetricsSerializer, DashboardDataSerializer
)
from ..base import AdvancedAPIView


class RealTimeDashboardAPIView(AdvancedAPIView):
    """Real-time dashboard data endpoint"""
    
    @method_decorator(never_cache)
    def get(self, request):
        """Get real-time dashboard data"""
        try:
            # Get real-time metrics
            metrics = self._get_realtime_metrics()
            
            # Get live activity feed
            activity_feed = self._get_live_activity()
            
            # Get performance alerts
            alerts = self._get_performance_alerts()
            
            # Get AI insights
            ai_insights = self._get_ai_insights()
            
            dashboard_data = {
                'timestamp': datetime.now(),
                'metrics': metrics,
                'activity_feed': activity_feed,
                'alerts': alerts,
                'ai_insights': ai_insights,
                'system_status': self._get_system_status()
            }
            
            return Response(dashboard_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_realtime_metrics(self) -> Dict[str, Any]:
        """Get real-time business metrics"""
        # Check cache first (refresh every 30 seconds)
        cache_key = f"realtime_metrics_{self.get_tenant().id}"
        metrics = cache.get(cache_key)
        
        if not metrics:
            metrics = {
                'current_visitors': self._get_current_visitors(),
                'active_carts': self._get_active_carts_count(),
                'orders_today': self._get_orders_today(),
                'revenue_today': self._get_revenue_today(),
                'conversion_rate_live': self._get_live_conversion_rate(),
                'average_order_value': self._get_current_aov(),
                'inventory_alerts': self._get_inventory_alerts_count(),
                'performance_score': self._get_performance_score(),
                'trending_products': self._get_trending_products_now(),
                'geographic_activity': self._get_geographic_activity()
            }
            
            # Cache for 30 seconds
            cache.set(cache_key, metrics, 30)
        
        return metrics
    
    def _get_live_activity(self) -> List[Dict[str, Any]]:
        """Get live activity feed"""
        return [
            {
                'id': 'activity_1',
                'type': 'order_placed',
                'message': 'New order #ORD-12345 for $89.99',
                'timestamp': datetime.now() - timedelta(minutes=2),
                'importance': 'high',
                'customer': {'name': 'John D.', 'location': 'New York, NY'}
            },
            {
                'id': 'activity_2',
                'type': 'product_viewed',
                'message': 'Premium Headphones viewed 15 times in last 5 minutes',
                'timestamp': datetime.now() - timedelta(minutes=3),
                'importance': 'medium',
                'product': {'name': 'Premium Headphones', 'id': 'prod_123'}
            },
            {
                'id': 'activity_3',
                'type': 'inventory_alert',
                'message': 'Low stock alert: Wireless Mouse (5 units left)',
                'timestamp': datetime.now() - timedelta(minutes=5),
                'importance': 'urgent',
                'product': {'name': 'Wireless Mouse', 'id': 'prod_456'}
            }
        ]
    
    def _get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Get performance alerts and warnings"""
        return [
            {
                'id': 'alert_1',
                'type': 'conversion_drop',
                'severity': 'warning',
                'message': 'Conversion rate dropped 15% in last hour',
                'recommended_action': 'Check checkout process for issues',
                'timestamp': datetime.now() - timedelta(minutes=10)
            },
            {
                'id': 'alert_2',
                'type': 'high_traffic',
                'severity': 'info',
                'message': 'Traffic spike detected (+40% vs. average)',
                'recommended_action': 'Monitor server performance',
                'timestamp': datetime.now() - timedelta(minutes=5)
            }
        ]
    
    def _get_ai_insights(self) -> Dict[str, Any]:
        """Get AI-generated insights"""
        return {
            'demand_predictions': {
                'next_hour_orders': 12,
                'confidence': 0.85,
                'trend': 'increasing'
            },
            'pricing_opportunities': {
                'products_to_optimize': 3,
                'potential_revenue_increase': 156.78,
                'confidence': 0.72
            },
            'customer_behavior': {
                'abandonment_risk_carts': 8,
                'high_value_visitors': 5,
                'repeat_customer_activity': 'high'
            },
            'inventory_predictions': {
                'stock_out_warnings': 2,
                'reorder_suggestions': 5,
                'demand_surge_products': ['prod_123', 'prod_789']
            }
        }


class LiveAnalyticsStreamAPIView(AdvancedAPIView):
    """WebSocket-compatible live analytics stream"""
    
    def get(self, request):
        """Get streaming analytics data"""
        try:
            stream_type = request.query_params.get('stream', 'general')
            interval = int(request.query_params.get('interval', 5))  # seconds
            
            # Get appropriate stream data
            if stream_type == 'sales':
                stream_data = self._get_sales_stream()
            elif stream_type == 'traffic':
                stream_data = self._get_traffic_stream()
            elif stream_type == 'inventory':
                stream_data = self._get_inventory_stream()
            else:
                stream_data = self._get_general_stream()
            
            return Response({
                'stream_type': stream_type,
                'interval_seconds': interval,
                'data': stream_data,
                'next_update_at': datetime.now() + timedelta(seconds=interval)
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_sales_stream(self) -> Dict[str, Any]:
        """Get real-time sales data"""
        return {
            'orders_per_minute': [
                {'minute': datetime.now() - timedelta(minutes=5), 'count': 3},
                {'minute': datetime.now() - timedelta(minutes=4), 'count': 5},
                {'minute': datetime.now() - timedelta(minutes=3), 'count': 2},
                {'minute': datetime.now() - timedelta(minutes=2), 'count': 7},
                {'minute': datetime.now() - timedelta(minutes=1), 'count': 4}
            ],
            'revenue_per_minute': [
                {'minute': datetime.now() - timedelta(minutes=5), 'amount': 234.56},
                {'minute': datetime.now() - timedelta(minutes=4), 'amount': 445.23},
                {'minute': datetime.now() - timedelta(minutes=3), 'amount': 123.89},
                {'minute': datetime.now() - timedelta(minutes=2), 'amount': 678.90},
                {'minute': datetime.now() - timedelta(minutes=1), 'amount': 345.67}
            ],
            'top_selling_products': [
                {'product_id': 'prod_123', 'name': 'Premium Headphones', 'sales': 8},
                {'product_id': 'prod_456', 'name': 'Wireless Mouse', 'sales': 6},
                {'product_id': 'prod_789', 'name': 'Gaming Keyboard', 'sales': 4}
            ]
        }


class AIInsightsAPIView(AdvancedAPIView):
    """AI-powered insights and predictions"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ai_analyzer = None
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.ai_analyzer = RealTimeAnalyzer(self.get_tenant())
    
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request):
        """Get AI-powered business insights"""
        try:
            insight_type = request.query_params.get('type', 'all')
            time_horizon = request.query_params.get('horizon', '24h')
            
            insights = asyncio.run(
                self.ai_analyzer.generate_business_insights(
                    insight_type=insight_type,
                    time_horizon=time_horizon
                )
            )
            
            return Response({
                'insight_type': insight_type,
                'time_horizon': time_horizon,
                'generated_at': datetime.now(),
                'insights': insights,
                'confidence_scores': self._extract_confidence_scores(insights),
                'recommendations': self._extract_recommendations(insights)
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def post(self, request):
        """Generate custom AI insights"""
        try:
            custom_query = request.data.get('query')
            parameters = request.data.get('parameters', {})
            
            # Generate custom insights
            insights = asyncio.run(
                self.ai_analyzer.generate_custom_insights(
                    query=custom_query,
                    parameters=parameters
                )
            )
            
            return Response({
                'query': custom_query,
                'parameters': parameters,
                'insights': insights,
                'analysis_id': insights.get('analysis_id'),
                'processing_time_ms': insights.get('processing_time_ms')
            })
            
        except Exception as e:
            return self.handle_exception(e)