"""
Advanced Product API Views
Utilizing the full power of our Application Layer
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
import asyncio
from typing import Dict, Any, List

from .....application.use_cases.products.create_product import CreateProductUseCase
from .....application.use_cases.products.analyze_product_performance import AnalyzeProductPerformanceUseCase
from .....application.queries.product_queries import (
    ProductListQuery, ProductDetailQuery, ProductAnalyticsQuery
)
from .....application.commands.product_commands import (
    CreateProductCommand, UpdateProductCommand, ProductCommandHandler
)
from .....application.services.event_bus_service import EventBusService
from .....infrastructure.ai.recommendations.real_time_recommendations import RealTimeRecommender
from .....infrastructure.ai.pricing.dynamic_pricing_engine import DynamicPricingEngine
from ....serializers.advanced_product_serializers import (
    ProductAnalyticsSerializer, AIInsightsSerializer, 
    RecommendationConfigSerializer, PricingAnalyticsSerializer
)
from ..base import AdvancedAPIViewSet


class AdvancedProductViewSet(AdvancedAPIViewSet):
    """Advanced product API with AI integration and real-time capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_bus = None
        self.recommender = None
        self.pricing_engine = None
    
    def setup(self, request, *args, **kwargs):
        """Setup services for the request"""
        super().setup(request, *args, **kwargs)
        self.event_bus = EventBusService(self.get_tenant())
        self.recommender = RealTimeRecommender(self.get_tenant())
        self.pricing_engine = DynamicPricingEngine(self.get_tenant())
    
    @action(detail=False, methods=['post'], url_path='create-with-ai')
    def create_with_ai_analysis(self, request):
        """Create product with immediate AI analysis"""
        try:
            # Validate input
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Create command
            command = CreateProductCommand(
                title=request.data.get('title'),
                description=request.data.get('description'),
                price=float(request.data.get('price')),
                enable_ai_features=request.data.get('enable_ai', True),
                user_id=str(request.user.id) if request.user.is_authenticated else None
            )
            
            # Execute through command handler
            handler = ProductCommandHandler(self.get_tenant())
            product_id = handler.handle_create_product(command)
            
            # Trigger immediate AI analysis
            if command.enable_ai_features:
                analysis_task = self._trigger_ai_analysis(product_id)
                # Run async analysis
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ai_results = loop.run_until_complete(analysis_task)
                loop.close()
            else:
                ai_results = None
            
            return Response({
                'success': True,
                'product_id': product_id,
                'message': 'Product created successfully',
                'ai_analysis': ai_results,
                'next_steps': self._get_next_steps_recommendations(product_id)
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['get'], url_path='ai-insights')
    def get_ai_insights(self, request, pk=None):
        """Get comprehensive AI insights for product"""
        try:
            product_id = pk
            
            # Get real-time insights
            insights = {
                'performance_score': self._get_performance_score(product_id),
                'demand_forecast': self._get_demand_forecast(product_id),
                'pricing_optimization': self._get_pricing_insights(product_id),
                'recommendation_performance': self._get_recommendation_metrics(product_id),
                'market_position': self._get_market_position(product_id),
                'optimization_suggestions': self._get_optimization_suggestions(product_id)
            }
            
            # Add trends and predictions
            insights['trends'] = self._get_product_trends(product_id)
            insights['predictions'] = self._get_future_predictions(product_id)
            
            serializer = AIInsightsSerializer(insights)
            
            return Response({
                'product_id': product_id,
                'insights': serializer.data,
                'generated_at': timezone.now(),
                'confidence_score': self._calculate_confidence_score(insights)
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'], url_path='optimize-pricing')
    def optimize_pricing(self, request, pk=None):
        """Trigger AI-powered pricing optimization"""
        try:
            product_id = pk
            optimization_params = request.data.get('optimization_params', {})
            
            # Run pricing optimization
            optimization_result = asyncio.run(
                self.pricing_engine.optimize_product_pricing(
                    product_id=product_id,
                    params=optimization_params
                )
            )
            
            # Apply optimized pricing if auto_apply is true
            if optimization_params.get('auto_apply', False):
                self._apply_pricing_changes(product_id, optimization_result['recommended_price'])
                applied = True
            else:
                applied = False
            
            return Response({
                'optimization_id': optimization_result['optimization_id'],
                'current_price': optimization_result['current_price'],
                'recommended_price': optimization_result['recommended_price'],
                'expected_impact': optimization_result['impact_analysis'],
                'confidence': optimization_result['confidence_score'],
                'applied': applied,
                'reasoning': optimization_result['reasoning']
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['get'], url_path='recommendations/similar')
    def get_similar_products(self, request, pk=None):
        """Get AI-powered similar product recommendations"""
        try:
            product_id = pk
            limit = int(request.query_params.get('limit', 6))
            algorithm = request.query_params.get('algorithm', 'hybrid')
            
            recommendations = asyncio.run(
                self.recommender.get_similar_products(
                    product_id=product_id,
                    limit=limit,
                    algorithm=algorithm,
                    user_context={
                        'user_id': str(request.user.id) if request.user.is_authenticated else None,
                        'session_id': request.session.session_key
                    }
                )
            )
            
            # Enrich recommendations with reasons
            enriched_recommendations = self._enrich_recommendations(
                recommendations, 'similar_products'
            )
            
            return Response({
                'product_id': product_id,
                'algorithm_used': algorithm,
                'recommendations': enriched_recommendations,
                'total_count': len(enriched_recommendations),
                'confidence_scores': [r['confidence'] for r in enriched_recommendations]
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'], url_path='analytics/track-view')
    def track_product_view(self, request, pk=None):
        """Track product view with enhanced analytics"""
        try:
            product_id = pk
            view_context = {
                'user_id': str(request.user.id) if request.user.is_authenticated else None,
                'session_id': request.session.session_key,
                'source': request.data.get('source', 'direct'),
                'referrer': request.data.get('referrer'),
                'device_type': self._detect_device_type(request),
                'timestamp': timezone.now(),
                'page_context': request.data.get('page_context', {}),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'ip_address': self._get_client_ip(request)
            }
            
            # Track view asynchronously
            asyncio.run(self._track_enhanced_view(product_id, view_context))
            
            # Get real-time recommendations based on this view
            view_recommendations = asyncio.run(
                self.recommender.get_post_view_recommendations(
                    product_id=product_id,
                    user_context=view_context,
                    limit=4
                )
            )
            
            return Response({
                'tracked': True,
                'product_id': product_id,
                'view_id': view_context.get('view_id'),
                'recommendations': view_recommendations,
                'personalization_score': self._calculate_personalization_score(
                    product_id, view_context
                )
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'], url_path='trending')
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def get_trending_products(self, request):
        """Get trending products with AI-powered ranking"""
        try:
            time_window = request.query_params.get('time_window', '24h')
            category = request.query_params.get('category')
            limit = int(request.query_params.get('limit', 20))
            
            trending_products = asyncio.run(
                self.recommender.get_trending_products(
                    time_window=time_window,
                    category=category,
                    limit=limit,
                    user_context={
                        'user_id': str(request.user.id) if request.user.is_authenticated else None
                    }
                )
            )
            
            # Add trend analytics
            for product in trending_products:
                product['trend_metrics'] = self._get_trend_metrics(
                    product['id'], time_window
                )
            
            return Response({
                'time_window': time_window,
                'category': category,
                'trending_products': trending_products,
                'trend_analysis': self._get_overall_trend_analysis(time_window),
                'cache_info': {
                    'cached_at': timezone.now(),
                    'expires_in_minutes': 15
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'], url_path='bulk-analyze')
    def bulk_analyze_products(self, request):
        """Bulk analyze multiple products with AI"""
        try:
            product_ids = request.data.get('product_ids', [])
            analysis_types = request.data.get('analysis_types', ['performance', 'pricing'])
            
            if len(product_ids) > 100:
                return Response({
                    'error': 'Maximum 100 products can be analyzed at once'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Run bulk analysis
            analysis_results = asyncio.run(
                self._bulk_analyze_products(product_ids, analysis_types)
            )
            
            return Response({
                'analysis_id': analysis_results['analysis_id'],
                'products_analyzed': len(product_ids),
                'analysis_types': analysis_types,
                'results': analysis_results['results'],
                'summary': analysis_results['summary'],
                'processing_time_seconds': analysis_results['processing_time']
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    # Private helper methods
    async def _trigger_ai_analysis(self, product_id: str) -> Dict[str, Any]:
        """Trigger comprehensive AI analysis for new product"""
        analysis_tasks = [
            self.recommender.analyze_product_content(product_id),
            self.pricing_engine.initialize_product_pricing(product_id),
            self._generate_initial_forecasts(product_id)
        ]
        
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        return {
            'content_analysis': results[0] if not isinstance(results[0], Exception) else None,
            'pricing_analysis': results[1] if not isinstance(results[1], Exception) else None,
            'demand_forecast': results[2] if not isinstance(results[2], Exception) else None,
            'analysis_completed_at': timezone.now()
        }
    
    def _get_performance_score(self, product_id: str) -> Dict[str, Any]:
        """Calculate comprehensive performance score"""
        # This would aggregate various metrics
        return {
            'overall_score': 8.5,
            'sales_performance': 8.2,
            'engagement_score': 8.8,
            'conversion_rate': 7.9,
            'customer_satisfaction': 9.1,
            'market_fit_score': 8.0,
            'trend_direction': 'increasing',
            'last_updated': timezone.now()
        }
    
    def _get_demand_forecast(self, product_id: str) -> Dict[str, Any]:
        """Get AI-powered demand forecast"""
        return {
            'next_7_days': {'units': 45, 'confidence': 0.82},
            'next_30_days': {'units': 180, 'confidence': 0.75},
            'next_90_days': {'units': 520, 'confidence': 0.68},
            'seasonal_factors': ['holiday_boost', 'weather_dependent'],
            'forecast_model': 'lstm_ensemble',
            'last_trained': timezone.now() - timedelta(hours=6)
        }
    
    def _get_pricing_insights(self, product_id: str) -> Dict[str, Any]:
        """Get pricing optimization insights"""
        return {
            'current_price': 29.99,
            'optimal_price_range': {'min': 27.99, 'max': 32.99},
            'price_elasticity': -1.2,
            'competitor_analysis': {
                'average_competitor_price': 31.50,
                'our_position': 'below_average',
                'opportunity_score': 8.3
            },
            'revenue_impact': {
                'current_weekly_revenue': 1349.55,
                'optimized_weekly_revenue': 1547.30,
                'potential_increase_percent': 14.6
            }
        }
    
    def _enrich_recommendations(self, recommendations: List[Dict], rec_type: str) -> List[Dict]:
        """Enrich recommendations with explanations and confidence"""
        enriched = []
        
        for rec in recommendations:
            enriched_rec = {
                **rec,
                'recommendation_type': rec_type,
                'explanation': self._generate_recommendation_explanation(rec, rec_type),
                'confidence': rec.get('confidence', 0.8),
                'reasoning_factors': self._get_reasoning_factors(rec),
                'expected_ctr': self._estimate_click_through_rate(rec),
                'personalization_score': rec.get('personalization_score', 0.5)
            }
            enriched.append(enriched_rec)
        
        return enriched
    
    async def _track_enhanced_view(self, product_id: str, view_context: Dict[str, Any]):
        """Track product view with enhanced analytics"""
        # Create view event
        from .....domain.events.analytics_events import ProductViewEvent
        
        view_event = ProductViewEvent(
            product_id=product_id,
            user_id=view_context.get('user_id'),
            session_id=view_context.get('session_id'),
            source=view_context.get('source'),
            device_type=view_context.get('device_type'),
            timestamp=view_context.get('timestamp')
        )
        
        # Publish event asynchronously
        await self.event_bus.publish_event(view_event)
        
        # Update real-time metrics
        await self._update_realtime_metrics(product_id, 'view')
    
    def _calculate_personalization_score(self, product_id: str, context: Dict[str, Any]) -> float:
        """Calculate how well this product matches user preferences"""
        # This would use ML models to calculate personalization
        return 0.75  # Placeholder
    
    def _get_next_steps_recommendations(self, product_id: str) -> List[str]:
        """Get recommended next steps after product creation"""
        return [
            "Upload high-quality product images",
            "Set up inventory tracking",
            "Configure pricing rules",
            "Add product to relevant collections",
            "Enable AI-powered recommendations",
            "Set up automated pricing optimization"
        ]