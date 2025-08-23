from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, timedelta

from ..entities.product import Product
from ..value_objects.money import Money
from ..value_objects.price import Price
from ..repositories.product_repository import ProductRepository, ProductAnalyticsRepository
from ..events.product_events import ProductPriceUpdatedEvent, ProductAnalyticsUpdatedEvent
from .base import DomainService

logger = logging.getLogger(__name__)


class AIPricingService(DomainService):
    """
    Domain service for AI-powered pricing intelligence and optimization
    Handles complex pricing strategies and market analysis
    """
    
    def __init__(
        self,
        product_repository: ProductRepository,
        analytics_repository: ProductAnalyticsRepository
    ):
        super().__init__(
            product_repository=product_repository,
            analytics_repository=analytics_repository
        )
    
    # ============================================================================
    # DYNAMIC PRICING OPTIMIZATION
    # ============================================================================
    
    def optimize_portfolio_pricing(self, strategy: str = "profit_maximization") -> Dict[str, Any]:
        """Optimize pricing across entire product portfolio"""
        try:
            logger.info(f"Starting portfolio pricing optimization with strategy: {strategy}")
            
            products = self.product_repository.find_all_published()
            optimization_results = {
                'strategy': strategy,
                'products_analyzed': len(products),
                'price_changes_recommended': 0,
                'projected_revenue_impact': Decimal('0.00'),
                'optimizations': []
            }
            
            strategy_functions = {
                'profit_maximization': self._optimize_for_profit,
                'market_share': self._optimize_for_market_share,
                'inventory_turnover': self._optimize_for_inventory_turnover,
                'customer_value': self._optimize_for_customer_value
            }
            
            optimize_function = strategy_functions.get(strategy, self._optimize_for_profit)
            
            for product in products:
                try:
                    product_optimization = optimize_function(product)
                    
                    if product_optimization['recommended_change']:
                        optimization_results['price_changes_recommended'] += 1
                        optimization_results['projected_revenue_impact'] += product_optimization['revenue_impact']
                        optimization_results['optimizations'].append(product_optimization)
                
                except Exception as e:
                    logger.warning(f"Failed to optimize pricing for product {product.id}: {e}")
                    continue
            
            # Apply optimizations if beneficial
            if optimization_results['projected_revenue_impact'] > 0:
                applied_optimizations = self._apply_pricing_optimizations(
                    optimization_results['optimizations']
                )
                optimization_results['applied_optimizations'] = applied_optimizations
            
            logger.info(f"Portfolio pricing optimization completed: {optimization_results['price_changes_recommended']} recommendations")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Portfolio pricing optimization failed: {e}")
            raise
    
    def implement_dynamic_pricing(self, product_id: str, pricing_rules: Dict[str, Any]) -> Dict[str, Any]:
        """Implement dynamic pricing for specific product"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            # Enable dynamic pricing
            product.ai_features.dynamic_pricing_enabled = True
            
            dynamic_pricing_result = {
                'product_id': product_id,
                'rules_applied': pricing_rules,
                'price_changes': []
            }
            
            # Market demand-based pricing
            if pricing_rules.get('demand_based', False):
                demand_price_change = self._apply_demand_based_pricing(product, pricing_rules)
                if demand_price_change:
                    dynamic_pricing_result['price_changes'].append(demand_price_change)
            
            # Competitor-based pricing
            if pricing_rules.get('competitor_based', False):
                competitor_price_change = self._apply_competitor_based_pricing(product, pricing_rules)
                if competitor_price_change:
                    dynamic_pricing_result['price_changes'].append(competitor_price_change)
            
            # Inventory-based pricing
            if pricing_rules.get('inventory_based', False):
                inventory_price_change = self._apply_inventory_based_pricing(product, pricing_rules)
                if inventory_price_change:
                    dynamic_pricing_result['price_changes'].append(inventory_price_change)
            
            # Customer segment-based pricing
            if pricing_rules.get('segment_based', False):
                segment_price_changes = self._apply_segment_based_pricing(product, pricing_rules)
                dynamic_pricing_result['price_changes'].extend(segment_price_changes)
            
            # Save updated product
            self.product_repository.save(product)
            
            return dynamic_pricing_result
            
        except Exception as e:
            logger.error(f"Dynamic pricing implementation failed: {e}")
            raise
    
    def analyze_price_elasticity(self, product_id: str, historical_days: int = 90) -> Dict[str, Any]:
        """Analyze price elasticity using historical data and AI"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            # Get historical analytics data
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=historical_days)
            
            price_history = self.analytics_repository.get_analytics_history(
                product_id, 'price', start_date, end_date
            )
            sales_history = self.analytics_repository.get_analytics_history(
                product_id, 'sales_count', start_date, end_date
            )
            
            elasticity_analysis = {
                'product_id': product_id,
                'analysis_period_days': historical_days,
                'current_elasticity_score': float(product.ai_features.price_elasticity_score),
                'elasticity_insights': {}
            }
            
            if len(price_history) >= 5 and len(sales_history) >= 5:
                # Calculate elasticity metrics
                elasticity_metrics = self._calculate_elasticity_metrics(price_history, sales_history)
                elasticity_analysis['elasticity_insights'] = elasticity_metrics
                
                # Update product's elasticity score
                product.ai_features.price_elasticity_score = Decimal(str(elasticity_metrics['elasticity_coefficient']))
                
                # Generate pricing recommendations based on elasticity
                elasticity_recommendations = self._generate_elasticity_recommendations(
                    product, elasticity_metrics
                )
                elasticity_analysis['recommendations'] = elasticity_recommendations
                
                # Save updated product
                self.product_repository.save(product)
            
            else:
                elasticity_analysis['elasticity_insights'] = {
                    'message': 'Insufficient historical data for elasticity analysis',
                    'data_points': len(price_history)
                }
            
            return elasticity_analysis
            
        except Exception as e:
            logger.error(f"Price elasticity analysis failed: {e}")
            raise
    
    # ============================================================================
    # COMPETITIVE PRICING INTELLIGENCE
    # ============================================================================
    
    def analyze_competitive_positioning(self, product_id: str[str, Any]:
        """Analyze competitive pricing position"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            competitive_analysis = {
                'product': {
                    'id': product_id,
                    'current_price': float(product.price.amount.amount),
                    'sku': str(product.sku),
                    'title': product.title
                },
                'competitive_position': {},
                'recommendations': []
            }
            
            # Use provided competitor data or fetch from existing
                competitor_prices = [comp['price'] for comp in competitor_data if 'price' in comp]
            else:
                # Use stored competitive analysis
                stored_analysis = product.ai_features.competitive_price_analysis
                competitor_prices = stored_analysis.get('competitor_prices', []) if stored_analysis else []
            
            if competitor_prices:
                current_price = float(product.price.amount.amount)
                
                competitive_metrics = {
                    'competitor_count': len(competitor_prices),
                    'min_competitor_price': min(competitor_prices),
                    'max_competitor_price': max(competitor_prices),
                    'avg_competitor_price': sum(competitor_prices) / len(competitor_prices),
                    'median_competitor_price': sorted(competitor_prices)[len(competitor_prices) // 2]
                }
                
                # Calculate position metrics
                competitive_metrics['price_rank'] = len([p for p in competitor_prices if p < current_price]) + 1
                competitive_metrics['price_percentile'] = (competitive_metrics['price_rank'] / (len(competitor_prices) + 1)) * 100
                
                # Position analysis
                avg_price = competitive_metrics['avg_competitor_price']
                if current_price > avg_price * 1.2:
                    position = 'premium'
                elif current_price > avg_price * 1.1:
                    position = 'above_average'
                elif current_price < avg_price * 0.8:
                    position = 'budget'
                elif current_price < avg_price * 0.9:
                    position = 'below_average'
                else:
                    position = 'competitive'
                
                competitive_analysis['competitive_position'] = {
                    'position': position,
                    'metrics': competitive_metrics,
                    'price_vs_avg': ((current_price - avg_price) / avg_price) * 100
                }
                
                # Generate positioning recommendations
                positioning_recommendations = self._generate_positioning_recommendations(
                    product, competitive_analysis['competitive_position']
                )
                competitive_analysis['recommendations'] = positioning_recommendations
                
                # Update product's competitive analysis
                product.ai_features.competitive_price_analysis.update(competitive_analysis)
                self.product_repository.save(product)
            
            else:
                competitive_analysis['competitive_position'] = {
                    'message': 'No competitor pricing data available'
                }
            
            return competitive_analysis
            
        except Exception as e:
            logger.error(f"Competitive positioning analysis failed: {e}")
            raise
    
    def monitor_price_wars(self, category: str = None) -> Dict[str, Any]:
        """Monitor for potential price wars in category or across portfolio"""
        try:
            if category:
                products = self.product_repository.find_by_category(category)
                scope = f"category: {category}"
            else:
                products = self.product_repository.find_all_published()
                scope = "entire portfolio"
            
            price_war_analysis = {
                'scope': scope,
                'products_monitored': len(products),
                'potential_price_wars': [],
                'recommendations': []
            }
            
            for product in products:
                # Analyze recent price changes and competitor responses
                price_war_indicators = self._detect_price_war_indicators(product)
                
                if price_war_indicators['risk_level'] in ['HIGH', 'CRITICAL']:
                    price_war_analysis['potential_price_wars'].append({
                        'product_id': product.id,
                        'sku': str(product.sku),
                        'title': product.title,
                        'risk_level': price_war_indicators['risk_level'],
                        'indicators': price_war_indicators['indicators'],
                        'recommended_actions': price_war_indicators['recommended_actions']
                    })
            
            # Generate portfolio-level recommendations
            if price_war_analysis['potential_price_wars']:
                portfolio_recommendations = self._generate_price_war_mitigation_strategies(
                    price_war_analysis['potential_price_wars']
                )
                price_war_analysis['recommendations'] = portfolio_recommendations
            
            return price_war_analysis
            
        except Exception as e:
            logger.error(f"Price war monitoring failed: {e}")
            raise
    
    # ============================================================================
    # PRICING STRATEGY HELPER METHODS
    # ============================================================================
    
    def _optimize_for_profit(self, product: Product) -> Dict[str, Any]:
        """Optimize product price for maximum profit"""
        current_price = product.price.amount.amount
        ai_recommended = product.ai_features.ai_recommended_price or current_price
        
        # Calculate potential profit impact
        cost_estimate = current_price * Decimal('0.6')  # Assume 40% margin
        current_margin = current_price - cost_estimate
        new_margin = ai_recommended - cost_estimate
        
        profit_increase = (new_margin - current_margin) * Decimal(str(max(product.sales_count, 1)))
        
        return {
            'product_id': product.id,
            'current_price': float(current_price),
            'recommended_price': float(ai_recommended),
            'price_change_percent': float(((ai_recommended - current_price) / current_price) * 100),
            'recommended_change': abs(ai_recommended - current_price) > current_price * Decimal('0.05'),  # 5% threshold
            'profit_impact': float(profit_increase),
            'revenue_impact': profit_increase,
            'strategy': 'profit_maximization'
        }
    
    def _optimize_for_market_share(self, product: Product) -> Dict[str, Any]:
        """Optimize product price for market share growth"""
        current_price = product.price.amount.amount
        
        # Analyze competitive position
        competitive_analysis = product.ai_features.competitive_price_analysis
        if competitive_analysis and 'average' in competitive_analysis:
            avg_competitor_price = Decimal(str(competitive_analysis['average']))
            
            # Price slightly below average for market share
            recommended_price = avg_competitor_price * Decimal('0.95')  # 5% below average
            
            # Estimate volume impact
            price_reduction_percent = ((current_price - recommended_price) / current_price)
            estimated_volume_increase = price_reduction_percent * Decimal('2.0')  # Assume 2x elasticity
            
            volume_impact = float(estimated_volume_increase * product.sales_count)
            revenue_impact = float((recommended_price - current_price) * product.sales_count)
            
            return {
                'product_id': product.id,
                'current_price': float(current_price),
                'recommended_price': float(recommended_price),
                'price_change_percent': float(((recommended_price - current_price) / current_price) * 100),
                'recommended_change': abs(recommended_price - current_price) > current_price * Decimal('0.03'),
                'volume_impact': volume_impact,
                'revenue_impact': revenue_impact,
                'strategy': 'market_share'
            }
        
        return {
            'product_id': product.id,
            'recommended_change': False,
            'message': 'Insufficient competitive data',
            'strategy': 'market_share'
        }
    
    def _apply_demand_based_pricing(self, product: Product, rules: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply demand-based dynamic pricing"""
        demand_30d = product.ai_features.demand_forecast_30d
        if demand_30d == 0:
            return None
        
        current_price = product.price.amount.amount
        
        # High demand = increase price, low demand = decrease price
        avg_monthly_demand = max(product.sales_count, 1)  # Avoid division by zero
        demand_ratio = demand_30d / avg_monthly_demand
        
        if demand_ratio > 1.5:  # High demand
            price_multiplier = min(1.15, 1.0 + (demand_ratio - 1.0) * 0.1)  # Cap at 15% increase
        elif demand_ratio < 0.5:  # Low demand
            price_multiplier = max(0.85, 1.0 - (1.0 - demand_ratio) * 0.1)  # Cap at 15% decrease
        else:
            return None  # No change needed
        
        new_price = current_price * Decimal(str(price_multiplier))
        
        # Apply the price change
        product.update_price(
            Price(Money(new_price, product.price.amount.currency)),
            reason="ai_demand_based_dynamic_pricing"
        )
        
        return {
            'type': 'demand_based',
            'old_price': float(current_price),
            'new_price': float(new_price),
            'demand_ratio': demand_ratio,
            'reason': 'high_demand' if demand_ratio > 1.5 else 'low_demand'
        }
    
    def _calculate_elasticity_metrics(self, price_history: List[Dict], sales_history: List[Dict]) -> Dict[str, Any]:
        """Calculate price elasticity metrics from historical data"""
        # Simple elasticity calculation
        # In production, you'd use more sophisticated econometric methods
        
        price_changes = []
        sales_changes = []
        
        for i in range(1, min(len(price_history), len(sales_history))):
            price_change = (price_history[i]['value'] - price_history[i-1]['value']) / price_history[i-1]['value']
            sales_change = (sales_history[i]['value'] - sales_history[i-1]['value']) / max(sales_history[i-1]['value'], 1)
            
            if price_change != 0:  # Avoid division by zero
                price_changes.append(price_change)
                sales_changes.append(sales_change)
        
        if not price_changes:
            return {'elasticity_coefficient': 0, 'message': 'No price changes to analyze'}
        
        # Calculate correlation and elasticity
        if len(price_changes) >= 3:
            # Simple elasticity = average % change in quantity / average % change in price
            avg_price_change = sum(price_changes) / len(price_changes)
            avg_sales_change = sum(sales_changes) / len(sales_changes)
            
            elasticity_coefficient = avg_sales_change / avg_price_change if avg_price_change != 0 else 0
            
            return {
                'elasticity_coefficient': elasticity_coefficient,
                'avg_price_change_percent': avg_price_change * 100,
                'avg_sales_change_percent': avg_sales_change * 100,
                'data_points': len(price_changes),
                'interpretation': self._interpret_elasticity(elasticity_coefficient)
            }
        
        return {'elasticity_coefficient': 0, 'message': 'Insufficient data points for elasticity calculation'}
    
    def _interpret_elasticity(self, coefficient: float) -> str:
        """Interpret elasticity coefficient"""
        abs_coeff = abs(coefficient)
        
        if abs_coeff > 1:
            return 'elastic' if coefficient < 0 else 'elastic_positive'
        elif abs_coeff > 0.5:
            return 'moderately_elastic' if coefficient < 0 else 'moderately_elastic_positive'
        elif abs_coeff > 0.1:
            return 'inelastic' if coefficient < 0 else 'inelastic_positive'
        else:
            return 'perfectly_inelastic'
    
    def _detect_price_war_indicators(self, product: Product) -> Dict[str, Any]:
        """Detect indicators of potential price war"""
        indicators = []
        risk_level = 'LOW'
        
        # Rapid price changes
        if product.ai_features.competitive_price_analysis:
            competitive_data = product.ai_features.competitive_price_analysis
            
            # Check for frequent competitor price changes
            if competitive_data.get('recent_competitor_changes', 0) > 3:
                indicators.append('frequent_competitor_price_changes')
                risk_level = 'MEDIUM'
            
            # Check for below-cost pricing
            current_price = float(product.price.amount.amount)
            if competitive_data.get('minimum', 0) < current_price * 0.7:
                indicators.append('potential_below_cost_pricing')
                risk_level = 'HIGH'
        
        # Check own price volatility
        if product.ai_features.price_elasticity_score > 2:  # High volatility
            indicators.append('high_price_volatility')
            if risk_level == 'LOW':
                risk_level = 'MEDIUM'
        
        # Performance impact indicators
        if float(product.ai_features.churn_risk_score) > 60:
            indicators.append('customer_churn_risk')
            risk_level = 'HIGH'
        
        if len(indicators) >= 3:
            risk_level = 'CRITICAL'
        
        return {
            'risk_level': risk_level,
            'indicators': indicators,
            'recommended_actions': self._get_price_war_actions(risk_level, indicators)
        }
    
    def _get_price_war_actions(self, risk_level: str, indicators: List[str]) -> List[str]:
        """Get recommended actions for price war mitigation"""
        actions = []
        
        if risk_level in ['HIGH', 'CRITICAL']:
            actions.append('Monitor competitor pricing daily')
            actions.append('Consider value-added differentiation')
            actions.append('Evaluate cost structure for pricing flexibility')
        
        if 'customer_churn_risk' in indicators:
            actions.append('Implement customer retention programs')
            actions.append('Focus on service quality improvements')
        
        if 'potential_below_cost_pricing' in indicators:
            actions.append('Investigate competitor cost structures')
            actions.append('Consider reporting predatory pricing if applicable')
        
        return actions