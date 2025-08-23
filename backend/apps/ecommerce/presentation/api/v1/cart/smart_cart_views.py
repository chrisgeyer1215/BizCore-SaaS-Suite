"""
Smart Cart API with AI-powered features
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
import asyncio
from datetime import datetime, timedelta

from .....application.use_cases.cart.add_to_cart import AddToCartUseCase
from .....application.use_cases.cart.optimize_cart import OptimizeCartUseCase
from .....application.queries.cart_queries import CartDetailQuery, AbandonedCartsQuery
from .....application.commands.cart_commands import AddToCartCommand, CartCommandHandler
from .....infrastructure.ai.recommendations.cross_sell_engine import CrossSellEngine
from .....infrastructure.ai.pricing.dynamic_pricing_engine import DynamicPricingEngine
from ....serializers.smart_cart_serializers import (
    SmartCartSerializer, CartOptimizationSerializer, 
    AbandonmentRecoverySerializer
)
from ..base import AdvancedAPIViewSet


class SmartCartViewSet(AdvancedAPIViewSet):
    """Smart cart management with AI-powered optimizations"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cross_sell_engine = None
        self.pricing_engine = None
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.cross_sell_engine = CrossSellEngine(self.get_tenant())
        self.pricing_engine = DynamicPricingEngine(self.get_tenant())
    
    @action(detail=False, methods=['post'], url_path='add-with-recommendations')
    def add_with_smart_recommendations(self, request):
        """Add item to cart with intelligent cross-sell recommendations"""
        try:
            # Add item to cart
            command = AddToCartCommand(
                product_id=request.data.get('product_id'),
                quantity=int(request.data.get('quantity', 1)),
                variant_id=request.data.get('variant_id'),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_key=request.session.session_key
            )
            
            handler = CartCommandHandler(self.get_tenant())
            cart_result = handler.handle_add_to_cart(command)
            
            # Get intelligent recommendations
            recommendations = asyncio.run(
                self.cross_sell_engine.get_cart_recommendations(
                    cart_id=cart_result['cart_id'],
                    newly_added_product=command.product_id,
                    user_context={
                        'user_id': command.user_id,
                        'session_id': command.session_key,
                        'current_cart_value': cart_result['total']
                    }
                )
            )
            
            # Calculate cart optimization suggestions
            optimizations = self._get_cart_optimizations(cart_result['cart_id'])
            
            return Response({
                'cart_updated': True,
                'cart_summary': cart_result,
                'smart_recommendations': {
                    'cross_sell_items': recommendations['cross_sell'],
                    'upsell_items': recommendations['upsell'],
                    'bundle_opportunities': recommendations['bundles'],
                    'personalized_picks': recommendations['personalized']
                },
                'optimization_suggestions': optimizations,
                'next_actions': self._get_next_action_suggestions(cart_result)
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'], url_path='optimize')
    def optimize_cart(self, request, pk=None):
        """AI-powered cart optimization"""
        try:
            cart_id = pk
            optimization_goals = request.data.get('goals', ['maximize_value', 'improve_satisfaction'])
            
            # Run cart optimization
            optimization_result = asyncio.run(
                self._run_cart_optimization(cart_id, optimization_goals)
            )
            
            # Apply optimizations if requested
            if request.data.get('auto_apply', False):
                applied_changes = self._apply_cart_optimizations(
                    cart_id, optimization_result['recommendations']
                )
                optimization_result['applied_changes'] = applied_changes
            
            return Response({
                'cart_id': cart_id,
                'optimization_goals': optimization_goals,
                'current_metrics': optimization_result['current_metrics'],
                'recommendations': optimization_result['recommendations'],
                'projected_improvements': optimization_result['projected_improvements'],
                'confidence_score': optimization_result['confidence'],
                'applied_changes': optimization_result.get('applied_changes', [])
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['get'], url_path='abandonment-risk')
    def get_abandonment_risk(self, request, pk=None):
        """Calculate cart abandonment risk and prevention strategies"""
        try:
            cart_id = pk
            
            # Calculate abandonment risk
            risk_analysis = asyncio.run(
                self._analyze_abandonment_risk(cart_id)
            )
            
            # Get prevention strategies
            prevention_strategies = self._get_abandonment_prevention_strategies(
                cart_id, risk_analysis['risk_score']
            )
            
            return Response({
                'cart_id': cart_id,
                'abandonment_risk': {
                    'risk_score': risk_analysis['risk_score'],
                    'risk_level': risk_analysis['risk_level'],
                    'key_factors': risk_analysis['risk_factors'],
                    'time_since_last_activity': risk_analysis['inactive_minutes'],
                    'historical_patterns': risk_analysis['user_patterns']
                },
                'prevention_strategies': prevention_strategies,
                'recovery_recommendations': risk_analysis['recovery_suggestions']
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'], url_path='abandoned/recovery')
    def get_abandonment_recovery_data(self, request):
        """Get abandoned carts with recovery recommendations"""
        try:
            hours_since = int(request.query_params.get('hours', 24))
            min_value = float(request.query_params.get('min_value', 0))
            
            query = AbandonedCartsQuery(
                hours_since_update=hours_since,
                min_cart_value=min_value,
                page=int(request.query_params.get('page', 1)),
                include_guest_carts=request.query_params.get('include_guests', 'true').lower() == 'true'
            )
            
            from .....application.queries.cart_queries import CartQueryHandler
            handler = CartQueryHandler(self.get_tenant())
            
            abandoned_carts = handler.handle_abandoned_carts(query)
            
            # Enrich with recovery strategies
            for cart in abandoned_carts['abandoned_carts']:
                cart['recovery_strategy'] = self._generate_recovery_strategy(cart)
                cart['optimal_contact_time'] = self._calculate_optimal_contact_time(cart)
                cart['discount_recommendation'] = self._recommend_recovery_discount(cart)
            
            return Response({
                'abandoned_carts': abandoned_carts['abandoned_carts'],
                'summary': abandoned_carts['summary'],
                'recovery_opportunities': {
                    'high_value_carts': len([c for c in abandoned_carts['abandoned_carts'] if c['total'] > 100]),
                    'recent_abandoners': len([c for c in abandoned_carts['abandoned_carts'] if c['abandonment_info']['hours_abandoned'] < 6]),
                    'recoverable_value': sum(c['total'] for c in abandoned_carts['abandoned_carts']),
                    'estimated_recovery_rate': 0.15  # 15% typical recovery rate
                },
                'pagination': {
                    'page': query.page,
                    'has_next': abandoned_carts['has_next'],
                    'total_count': abandoned_carts['total_count']
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'], url_path='price-check')
    def check_price_changes(self, request, pk=None):
        """Check for price changes and optimization opportunities"""
        try:
            cart_id = pk
            
            price_analysis = asyncio.run(
                self._analyze_cart_pricing(cart_id)
            )
            
            return Response({
                'cart_id': cart_id,
                'price_analysis': {
                    'items_with_changes': price_analysis['changed_items'],
                    'total_savings_available': price_analysis['potential_savings'],
                    'price_alerts': price_analysis['alerts'],
                    'optimization_opportunities': price_analysis['opportunities']
                },
                'recommendations': {
                    'price_adjustments': price_analysis['recommended_adjustments'],
                    'alternative_products': price_analysis['alternative_suggestions'],
                    'timing_suggestions': price_analysis['timing_recommendations']
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    # Private helper methods
    async def _run_cart_optimization(self, cart_id: str, goals: List[str]) -> Dict[str, Any]:
        """Run comprehensive cart optimization analysis"""
        
        # Analyze current cart
        current_analysis = await self._analyze_current_cart(cart_id)
        
        # Generate optimization recommendations
        recommendations = []
        
        for goal in goals:
            if goal == 'maximize_value':
                recs = await self._get_value_maximization_recommendations(cart_id, current_analysis)
                recommendations.extend(recs)
            elif goal == 'improve_satisfaction':
                recs = await self._get_satisfaction_improvement_recommendations(cart_id, current_analysis)
                recommendations.extend(recs)
            elif goal == 'reduce_shipping_cost':
                recs = await self._get_shipping_optimization_recommendations(cart_id, current_analysis)
                recommendations.extend(recs)
        
        # Calculate projected improvements
        projected_improvements = await self._calculate_projected_improvements(
            current_analysis, recommendations
        )
        
        return {
            'current_metrics': current_analysis['metrics'],
            'recommendations': recommendations,
            'projected_improvements': projected_improvements,
            'confidence': self._calculate_optimization_confidence(recommendations)
        }
    
    async def _analyze_abandonment_risk(self, cart_id: str) -> Dict[str, Any]:
        """Analyze cart abandonment risk using ML models"""
        
        # Get cart data
        from .....application.queries.cart_queries import CartDetailQuery, CartQueryHandler
        
        query = CartDetailQuery(cart_id=cart_id, include_product_details=True)
        handler = CartQueryHandler(self.get_tenant())
        cart_data = handler.handle_cart_detail(query)
        
        if ValueError("Cart not found")
        
        # Calculate risk factors
        risk_factors = {
            'cart_value': self._calculate_value_risk(cart_data.total),
            'item_count': self._calculate_item_count_risk(cart_data.item_count),
            'time_in_cart': self._calculate_time_risk(cart_data.updated_at),
            'pricing_competitiveness': await self._calculate_pricing_risk(cart_data.items),
            'stock_availability': self._calculate_availability_risk(cart_data.items),
            'user_behavior': await self._calculate_behavior_risk(cart_data.user_id) if cart_data.user_id else 0.5
        }
        
        # Calculate overall risk score (0-1, higher = more likely to abandon)
        risk_score = self._calculate_overall_risk_score(risk_factors)
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = 'low'
        elif risk_score < 0.6:
            risk_level = 'medium'
        elif risk_score < 0.8:
            risk_level = 'high'
        else:
            risk_level = 'critical'
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'inactive_minutes': (datetime.now() - cart_data.updated_at).total_seconds() / 60,
            'user_patterns': await self._get_user_abandonment_patterns(cart_data.user_id) if cart_data.user_id else {},
            'recovery_suggestions': self._get_risk_specific_recovery_suggestions(risk_score, risk_factors)
        }
    
    def _get_cart_optimizations(self, cart_id: str) -> List[Dict[str, Any]]:
        """Get cart optimization suggestions"""
        return [
            {
                'type': 'bundle_opportunity',
                'title': 'Save with Bundle',
                'description': 'Add complementary item and save 15%',
                'potential_savings': 12.50,
                'confidence': 0.85
            },
            {
                'type': 'shipping_optimization',
                'title': 'Free Shipping Available',
                'description': 'Add $8.50 more for free shipping',
                'potential_savings': 5.99,
                'confidence': 1.0
            }
        ]
    
    def _generate_recovery_strategy(self, cart
        """Generate personalized recovery strategy"""
        recovery_probability = cart_data['abandonment_info']['recovery_probability']
        cart_value = cart_data['total']
        
        if recovery_probability > 0.7:
            strategy = 'gentle_reminder'
            discount_needed = 0
        elif recovery_probability > 0.4:
            strategy = 'small_incentive'
            discount_needed = 5 if cart_value < 50 else 10
        else:
            strategy = 'strong_incentive'
            discount_needed = 15 if cart_value < 100 else 20
        
        return {
            'strategy_type': strategy,
            'recommended_discount_percent': discount_needed,
            'optimal_message_tone': self._get_message_tone(strategy),
            'recommended_channels': self._get_contact_channels(cart_data),
            'urgency_level': self._calculate_urgency_level(cart_data)
        }