from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import logging
from datetime import datetime, timedelta

from ..entities.product import Product
from ..repositories.product_repository import ProductRepository, ProductQueryRepository, ProductAnalyticsRepository
from ..events.product_events import ProductAnalyticsUpdatedEvent
from .base import DomainService

logger = logging.getLogger(__name__)


class ProductIntelligenceService(DomainService):
    """
    Domain service for AI-powered product intelligence and insights
    Handles advanced analytics, predictions, and business intelligence
    """
    
    def __init__(
        self,
        product_repository: ProductRepository,
        query_repository: ProductQueryRepository,
        analytics_repository: ProductAnalyticsRepository
    ):
        super().__init__(
            product_repository=product_repository,
            query_repository=query_repository,
            analytics_repository=analytics_repository
        )
    
    # ============================================================================
    # ADVANCED PRODUCT ANALYTICS
    # ============================================================================
    
    def generate_product_intelligence_report(self, product_id: str, report_type: str = "comprehensive") -> Dict[str, Any]:
        """Generate comprehensive intelligence report for product"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            intelligence_report = {
                'product': {
                    'id': product.id,
                    'sku': str(product.sku),
                    'title': product.title,
                    'category': product.category,
                    'brand': product.brand
                },
                'report_type': report_type,
                'generated_at': datetime.utcnow().isoformat(),
                'intelligence_modules': {}
            }
            
            # Market position intelligence
            market_intelligence = self._analyze_market_position(product)
            intelligence_report['intelligence_modules']['market_position'] = market_intelligence
            
            # Customer behavior intelligence
            customer_intelligence = self._analyze_customer_behavior(product)
            intelligence_report['intelligence_modules']['customer_behavior'] = customer_intelligence
            
            # Performance intelligence
            performance_intelligence = self._analyze_performance_trends(product)
            intelligence_report['intelligence_modules']['performance_trends'] = performance_intelligence
            
            # Competitive intelligence
            competitive_intelligence = self._analyze_competitive_landscape(product)
            intelligence_report['intelligence_modules']['competitive_landscape'] = competitive_intelligence
            
            # Opportunity intelligence
            opportunity_intelligence = self._identify_growth_opportunities(product)
            intelligence_report['intelligence_modules']['growth_opportunities'] = opportunity_intelligence
            
            # Risk intelligence
            risk_intelligence = self._assess_business_risks(product)
            intelligence_report['intelligence_modules']['business_risks'] = risk_intelligence
            
            # Generate strategic recommendations
            strategic_recommendations = self._generate_strategic_recommendations(
                intelligence_report['intelligence_modules']
            )
            intelligence_report['strategic_recommendations'] = strategic_recommendations
            
            # Calculate overall intelligence score
            intelligence_score = self._calculate_intelligence_score(intelligence_report)
            intelligence_report['overall_intelligence_score'] = intelligence_score
            
            return intelligence_report
            
        except Exception as e:
            logger.error(f"Intelligence report generation failed: {e}")
            raise
    
    def analyze_portfolio_intelligence(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze intelligence across product portfolio"""
        try:
            # Get products based on filters
            if filters:
                products = self.query_repository.find_by_complex_criteria(filters)
            else:
                products = self.product_repository.find_all_published()
            
            portfolio_intelligence = {
                'portfolio_size': len(products),
                'analysis_date': datetime.utcnow().isoformat(),
                'filters_applied': filters or {},
                'portfolio_metrics': {},
                'segment_analysis': {},
                'performance_distribution': {},
                'intelligence_insights': []
            }
            
            # Portfolio-level metrics
            portfolio_metrics = self._calculate_portfolio_metrics(products)
            portfolio_intelligence['portfolio_metrics'] = portfolio_metrics
            
            # Segment analysis (by category, brand, price range)
            segment_analysis = self._analyze_portfolio_segments(products)
            portfolio_intelligence['segment_analysis'] = segment_analysis
            
            # Performance distribution analysis
            performance_distribution = self._analyze_portfolio_performance_distribution(products)
            portfolio_intelligence['performance_distribution'] = performance_distribution
            
            # Generate portfolio insights
            portfolio_insights = self._generate_portfolio_insights(
                portfolio_metrics, segment_analysis, performance_distribution
            )
            portfolio_intelligence['intelligence_insights'] = portfolio_insights
            
            # Identify portfolio optimization opportunities
            optimization_opportunities = self._identify_portfolio_optimization_opportunities(products)
            portfolio_intelligence['optimization_opportunities'] = optimization_opportunities
            
            return portfolio_intelligence
            
        except Exception as e:
            logger.error(f"Portfolio intelligence analysis failed: {e}")
            raise
    
    def predict_product_lifecycle_stage(self, product_id: str) -> Dict[str, Any]:
        """Predict current and future product lifecycle stage"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            # Get historical performance data
            historical_data = self._get_product_historical_performance(product)
            
            lifecycle_prediction = {
                'product_id': product_id,
                'current_stage': self._determine_current_lifecycle_stage(product, historical_data),
                'predicted_transitions': [],
                'stage_characteristics': {},
                'recommendations': []
            }
            
            # Predict future stage transitions
            stage_transitions = self._predict_lifecycle_transitions(product, historical_data)
            lifecycle_prediction['predicted_transitions'] = stage_transitions
            
            # Analyze stage characteristics
            stage_characteristics = self._analyze_lifecycle_stage_characteristics(product)
            lifecycle_prediction['stage_characteristics'] = stage_characteristics
            
            # Generate stage-specific recommendations
            stage_recommendations = self._generate_lifecycle_stage_recommendations(
                lifecycle_prediction['current_stage'],
                product
            )
            lifecycle_prediction['recommendations'] = stage_recommendations
            
            return lifecycle_prediction
            
        except Exception as e:
            logger.error(f"Product lifecycle prediction failed: {e}")
            raise
    
    # ============================================================================
    # CUSTOMER INTELLIGENCE AND SEGMENTATION
    # ============================================================================
    
    def analyze_customer_product_affinity(self, product_id: str) -> Dict[str, Any]:
        """Analyze customer affinity and behavior patterns for product"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            affinity_analysis = {
                'product_id': product_id,
                'customer_segments': product.ai_features.customer_segments,
                'affinity_insights': {},
                'behavioral_patterns': {},
                'personalization_opportunities': []
            }
            
            # Analyze segment affinity
            for segment in product.ai_features.customer_segments:
                segment_affinity = self._analyze_segment_affinity(product, segment)
                affinity_analysis['affinity_insights'][segment] = segment_affinity
            
            # Behavioral pattern analysis
            behavioral_patterns = self._analyze_customer_behavioral_patterns(product)
            affinity_analysis['behavioral_patterns'] = behavioral_patterns
            
            # Identify personalization opportunities
            personalization_opportunities = self._identify_personalization_opportunities(product)
            affinity_analysis['personalization_opportunities'] = personalization_opportunities
            
            return affinity_analysis
            
        except Exception as e:
            logger.error(f"Customer affinity analysis failed: {e}")
            raise
    
    def generate_demand_intelligence(self, product_id: str, forecast_horizon: int = 90) -> Dict[str, Any]:
        """Generate comprehensive demand intelligence"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            demand_intelligence = {
                'product_id': product_id,
                'forecast_horizon_days': forecast_horizon,
                'current_demand_metrics': {},
                'demand_forecasting': {},
                'demand_drivers': {},
                'seasonality_analysis': {},
                'demand_risks': []
            }
            
            # Current demand metrics
            current_demand = self._analyze_current_demand_metrics(product)
            demand_intelligence['current_demand_metrics'] = current_demand
            
            # Advanced demand forecasting
            demand_forecast = self._generate_advanced_demand_forecast(product, forecast_horizon)
            demand_intelligence['demand_forecasting'] = demand_forecast
            
            # Demand driver analysis
            demand_drivers = self._analyze_demand_drivers(product)
            demand_intelligence['demand_drivers'] = demand_drivers
            
            # Seasonality pattern analysis
            seasonality_analysis = self._analyze_demand_seasonality(product)
            demand_intelligence['seasonality_analysis'] = seasonality_analysis
            
            # Demand risk assessment
            demand_risks = self._assess_demand_risks(product, demand_forecast)
            demand_intelligence['demand_risks'] = demand_risks
            
            return demand_intelligence
            
        except Exception as e:
            logger.error(f"Demand intelligence generation failed: {e}")
            raise
    
    # ============================================================================
    # HELPER METHODS FOR INTELLIGENCE ANALYSIS
    # ============================================================================
    
    def _analyze_market_position(self, product: Product) -> Dict[str, Any]:
        """Analyze product's market position"""
        return {
            'market_share_estimate': self._estimate_market_share(product),
            'competitive_advantage': self._assess_competitive_advantage(product),
            'market_trends_alignment': self._assess_market_trends_alignment(product),
            'positioning_strength': float(product.ai_features.search_relevance_score)
        }
    
    def _analyze_customer_behavior(self, product: Product) -> Dict[str, Any]:
        """Analyze customer behavior patterns"""
        return {
            'customer_segments': product.ai_features.customer_segments,
            'behavioral_analytics': product.ai_features.behavioral_analytics,
            'engagement_patterns': {
                'engagement_score': float(product.ai_features.engagement_prediction),
                'churn_risk': float(product.ai_features.churn_risk_score),
                'loyalty_indicators': self._calculate_loyalty_indicators(product)
            },
            'purchase_behavior': self._analyze_purchase_behavior(product)
        }
    
    def _analyze_performance_trends(self, product: Product) -> Dict[str, Any]:
        """Analyze performance trends"""
        return {
            'sales_performance': {
                'total_sales': product.sales_count,
                'sales_velocity': self._calculate_sales_velocity(product),
                'performance_trend': self._determine_performance_trend(product)
            },
            'conversion_metrics': {
                'conversion_score': float(product.ai_features.conversion_optimization_score),
                'bounce_rate_prediction': float(product.ai_features.bounce_rate_prediction)
            },
            'content_performance': {
                'content_quality': float(product.ai_features.content_completeness_score),
                'search_performance': float(product.ai_features.search_relevance_score)
            }
        }
    
    def _identify_growth_opportunities(self, product: Product) -> List[Dict[str, Any]]:
        """Identify growth opportunities for product"""
        opportunities = []
        
        # Pricing opportunities
        if product.ai_features.ai_recommended_price:
            current_price = float(product.price.amount.amount)
            recommended_price = float(product.ai_features.ai_recommended_price)
            if abs(recommended_price - current_price) / current_price > 0.1:  # 10% difference
                opportunities.append({
                    'type': 'pricing_optimization',
                    'opportunity': 'Price optimization based on AI analysis',
                    'potential_impact': 'medium',
                    'current_value': current_price,
                    'recommended_value': recommended_price
                })
        
        # Cross-sell opportunities
        if float(product.ai_features.cross_sell_potential) > 0.7:
            opportunities.append({
                'type': 'cross_selling',
                'opportunity': 'High cross-sell potential',
                'potential_impact': 'high',
                'cross_sell_score': float(product.ai_features.cross_sell_potential)
            })
        
        # Content improvement opportunities
        if float(product.ai_features.content_completeness_score) < 80:
            opportunities.append({
                'type': 'content_improvement',
                'opportunity': 'Content quality enhancement',
                'potential_impact': 'medium',
                'current_score': float(product.ai_features.content_completeness_score),
                'target_score': 90
            })
        
        return opportunities
    
    def _assess_business_risks(self, product: Product) -> List[Dict[str, Any]]:
        """Assess business risks for product"""
        risks = []
        
        # High churn risk
        if float(product.ai_features.churn_risk_score) > 70:
            risks.append({
                'type': 'customer_churn',
                'risk_level': 'high',
                'description': 'High customer churn risk detected',
                'risk_score': float(product.ai_features.churn_risk_score),
                'mitigation_strategies': ['improve_customer_experience', 'retention_programs']
            })
        
        # Inventory risks
        if float(product.ai_features.stockout_risk_score) > 60:
            risks.append({
                'type': 'inventory_stockout',
                'risk_level': 'medium' if product.ai_features.stockout_risk_score < 80 else 'high',
                'description': 'Stockout risk identified',
                'risk_score': float(product.ai_features.stockout_risk_score),
                'mitigation_strategies': ['inventory_reorder', 'demand_forecasting_improvement']
            })
        
        # Performance risks
        if float(product.ai_features.engagement_prediction) < 0.4:
            risks.append({
                'type': 'low_engagement',
                'risk_level': 'medium',
                'description': 'Low customer engagement predicted',
                'engagement_score': float(product.ai_features.engagement_prediction),
                'mitigation_strategies': ['content_optimization', 'marketing_campaign']
            })
        
        return risks
    
    def _calculate_portfolio_metrics(self, products: List[Product]) -> Dict[str, Any]:
        """Calculate portfolio-level metrics"""
        if not products:
            return {}
        
        total_sales = sum(p.sales_count for p in products)
        total_revenue = sum(float(p.price.amount.amount) * p.sales_count for p in products)
        avg_ai_health = sum(float(p.get_ai_health_score()) for p in products) / len(products)
        
        return {
            'total_products': len(products),
            'total_sales_units': total_sales,
            'total_revenue': total_revenue,
            'average_ai_health_score': avg_ai_health,
            'average_price': sum(float(p.price.amount.amount) for p in products) / len(products),
            'categories_count': len(set(p.category for p in products if p.category)),
            'brands_count': len(set(p.brand for p in products if p.brand))
        }
    
    def _generate_strategic_recommendations(self, intelligence_modules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate strategic recommendations based on intelligence analysis"""
        recommendations = []
        
        # Market position recommendations
        market_position = intelligence_modules.get('market_position', {})
        if market_position.get('positioning_strength', 0) < 50:
            recommendations.append({
                'category': 'market_positioning',
                'priority': 'high',
                'recommendation': 'Improve market positioning through SEO and content optimization',
                'expected_impact': 'Increased visibility and market share'
            })
        
        # Performance recommendations
        performance = intelligence_modules.get('performance_trends', {})
        conversion_score = performance.get('conversion_metrics', {}).get('conversion_score', 0)
        if conversion_score < 60:
            recommendations.append({
                'category': 'conversion_optimization',
                'priority': 'high',
                'recommendation': 'Implement conversion rate optimization strategies',
                'expected_impact': 'Improved sales conversion'
            })
        
        # Growth opportunity recommendations
        opportunities = intelligence_modules.get('growth_opportunities', [])
        for opportunity in opportunities:
            if opportunity.get('potential_impact') == 'high':
                recommendations.append({
                    'category': 'growth_opportunity',
                    'priority': 'medium',
                    'recommendation': f"Capitalize on {opportunity['type']} opportunity",
                    'expected_impact': opportunity.get('opportunity', '')
                })
        
        return recommendations