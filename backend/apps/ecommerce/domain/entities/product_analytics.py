from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal


class ProductAnalytics:
    """Product analytics and performance tracking"""
    
    def __init__(self):
        # Performance metrics
        self.view_count: int = 0
        self.click_through_rate: float = 0.0
        self.conversion_rate: float = 0.0
        self.bounce_rate: float = 0.0
        self.average_time_on_page: int = 0  # seconds
        
        # Sales metrics
        self.units_sold: int = 0
        self.total_revenue: Decimal = Decimal('0')
        self.average_order_value: Decimal = Decimal('0')
        self.return_rate: float = 0.0
        
        # Customer metrics
        self.unique_visitors: int = 0
        self.repeat_customers: int = 0
        self.customer_satisfaction_score: float = 0.0
        self.review_count: int = 0
        self.average_rating: float = 0.0
        
        # Inventory metrics
        self.stock_turnover_rate: float = 0.0
        self.days_of_inventory: int = 0
        self.stockout_frequency: int = 0
        
        # Marketing metrics
        self.organic_traffic_percentage: float = 0.0
        self.paid_traffic_percentage: float = 0.0
        self.social_media_mentions: int = 0
        self.email_campaign_performance: Dict[str, Any] = {}
        
        # Time-based data
        self.performance_history: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
    
    def update_from_ai_analysis(self, analysis: Dict[str, Any]) -> None:
        """Update analytics from AI analysis results"""
        if 'engagement_prediction' in analysis:
            self.click_through_rate = analysis['engagement_prediction'] * 0.1  # Example conversion
        
        if 'behavioral_insights' in analysis:
            insights = analysis['behavioral_insights']
            if 'avg_session_duration' in insights:
                self.average_time_on_page = insights['avg_session_duration']
            if 'bounce_rate' in insights:
                self.bounce_rate = insights['bounce_rate']
        
        self.last_updated = datetime.utcnow()
    
    def analyze_performance(
        self, 
        product_id: str, 
        sku: str, 
        time_period: str = "30d",
        ai_features: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Comprehensive performance analysis"""
        
        performance_analysis = {
            'product_id': product_id,
            'sku': sku,
            'time_period': time_period,
            'analysis_timestamp': datetime.utcnow().isoformat(),
            
            # Traffic analysis
            'traffic_analysis': {
                'total_views': self.view_count,
                'unique_visitors': self.unique_visitors,
                'bounce_rate': self.bounce_rate,
                'avg_time_on_page': self.average_time_on_page,
                'traffic_sources': self._analyze_traffic_sources()
            },
            
            # Conversion analysis
            'conversion_analysis': {
                'conversion_rate': self.conversion_rate,
                'click_through_rate': self.click_through_rate,
                'cart_abandonment_rate': self._calculate_cart_abandonment(),
                'conversion_funnel': self._analyze_conversion_funnel()
            },
            
            # Sales analysis
            'sales_analysis': {
                'units_sold': self.units_sold,
                'total_revenue': float(self.total_revenue),
                'average_order_value': float(self.average_order_value),
                'revenue_trend': self._calculate_revenue_trend(),
                'sales_velocity': self._calculate_sales_velocity()
            },
            
            # Customer analysis
            'customer_analysis': {
                'customer_satisfaction': self.customer_satisfaction_score,
                'review_metrics': {
                    'count': self.review_count,
                    'average_rating': self.average_rating,
                    'sentiment_score': self._calculate_sentiment_score()
                },
                'customer_retention': self._analyze_customer_retention(),
                'repeat_purchase_rate': self._calculate_repeat_purchase_rate()
            },
            
            # Inventory analysis
            'inventory_analysis': {
                'stock_turnover': self.stock_turnover_rate,
                'inventory_days': self.days_of_inventory,
                'stockout_incidents': self.stockout_frequency,
                'inventory_health_score': self._calculate_inventory_health_score()
            },
            
            # AI-enhanced insights
            'ai_insights': self._generate_ai_insights(ai_features or {}),
            
            # Performance score
            'overall_performance_score': self._calculate_performance_score(),
            
            # Recommendations
            'improvement_recommendations': self._generate_improvement_recommendations()
        }
        
        # Store in history
        self._add_to_performance_history(performance_analysis)
        
        return performance_analysis
    
    def get_historical_data(self) -> Dict[str, Any]:
        """Get historical performance data"""
        return {
            'performance_history': self.performance_history,
            'data_points': len(self.performance_history),
            'date_range': self._get_historical_date_range(),
            'trends': self._calculate_historical_trends()
        }
    
    def _analyze_traffic_sources(self) -> Dict[str, float]:
        """Analyze traffic source distribution"""
        return {
            'organic': self.organic_traffic_percentage,
            'paid': self.paid_traffic_percentage,
            'social': max(0, 100 - self.organic_traffic_percentage - self.paid_traffic_percentage - 20),
            'direct': 20.0,  # Default assumption
            'referral': max(0, 100 - self.organic_traffic_percentage - self.paid_traffic_percentage - 40)
        }
    
    def _calculate_cart_abandonment(self) -> float:
        """Calculate cart abandonment rate"""
        if self.view_count == 0:
            return 0.0
        
        # Estimate cart abandonment (industry average ~70%)
        estimated_adds_to_cart = self.view_count * self.click_through_rate
        if estimated_adds_to_cart == 0:
            return 0.0
        
        completed_purchases = self.units_sold
        return max(0.0, (estimated_adds_to_cart - completed_purchases) / estimated_adds_to_cart)
    
    def _analyze_conversion_funnel(self) -> Dict[str, Any]:
        """Analyze conversion funnel metrics"""
        return {
            'views_to_clicks': self.click_through_rate,
            'clicks_to_cart': 0.3,  # Estimated
            'cart_to_purchase': 1 - self._calculate_cart_abandonment(),
            'overall_conversion': self.conversion_rate,
            'funnel_dropoff_points': self._identify_funnel_dropoffs()
        }
    
    def _calculate_revenue_trend(self) -> str:
        """Calculate revenue trend direction"""
        if len(self.performance_history) < 2:
            return "insufficient_data"
        
        recent_revenue = self.total_revenue
        previous_revenue = Decimal(str(self.performance_history[-2].get('sales_analysis', {}).get('total_revenue', 0)))
        
        if recent_revenue > previous_revenue * Decimal('1.1'):
            return "increasing"
        elif recent_revenue < previous_revenue * Decimal('0.9'):
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_sales_velocity(self) -> float:
        """Calculate sales velocity (units per day)"""
        if len(self.performance_history) == 0:
            return 0.0
        
        # Calculate based on last 30 days
        return float(self.units_sold / 30)
    
    def _calculate_sentiment_score(self) -> float:
        """Calculate sentiment score from reviews"""
        if self.review_count == 0:
            return 0.0
        
        # Simple sentiment based on rating (1-5 scale to 0-1 scale)
        return (self.average_rating - 1) / 4
    
    def _analyze_customer_retention(self) -> Dict[str, Any]:
        """Analyze customer retention metrics"""
        return {
            'repeat_customer_percentage': self._calculate_repeat_customer_percentage(),
            'customer_lifetime_value': self._estimate_clv(),
            'retention_rate': self._calculate_retention_rate()
        }
    
    def _calculate_repeat_purchase_rate(self) -> float:
        """Calculate repeat purchase rate"""
        if self.unique_visitors == 0:
            return 0.0
        
        return self.repeat_customers / self.unique_visitors
    
    def _calculate_inventory_health_score(self) -> float:
        """Calculate inventory health score (0-1)"""
        factors = {
            'turnover_health': min(1.0, self.stock_turnover_rate / 12),  # Assume 12/year is good
            'days_health': max(0.0, 1.0 - (self.days_of_inventory / 90)),  # 90+ days is concerning
            'stockout_health': max(0.0, 1.0 - (self.stockout_frequency / 10))  # 10+ stockouts is bad
        }
        
        return sum(factors.values()) / len(factors)
    
    def _generate_ai_insights(self, ai_features: Dict[str, Any]) -> List[str]:
        """Generate AI-powered insights"""
        insights = []
        
        # Performance insights
        if self.conversion_rate < 0.02:  # Less than 2%
            insights.append("Conversion rate is below industry average. Consider A/B testing product page.")
        
        if self.bounce_rate > 0.6:  # More than 60%
            insights.append("High bounce rate detected. Review page load time and content relevance.")
        
        if self.return_rate > 0.15:  # More than 15%
            insights.append("High return rate indicates potential quality or expectation issues.")
        
        # AI-specific insights
        if ai_features.get('engagement_prediction', 0) < 0.5:
            insights.append("AI predicts low engagement. Consider updating product imagery and description.")
        
        if ai_features.get('churn_risk_score', 0) > 0.7:
            insights.append("High churn risk detected. Implement retention strategies.")
        
        return insights
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-1)"""
        scores = {
            'conversion': min(1.0, self.conversion_rate / 0.05),  # 5% is excellent
            'customer_satisfaction': self.customer_satisfaction_score,
            'inventory_health': self._calculate_inventory_health_score(),
            'traffic_quality': max(0.0, 1.0 - self.bounce_rate),
            'revenue_performance': min(1.0, float(self.total_revenue) / 10000)  # $10k benchmark
        }
        
        return sum(scores.values()) / len(scores)
    
    def _generate_improvement_recommendations(self) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        if self.conversion_rate < 0.02:
            recommendations.append("Optimize product page for higher conversion")
        
        if self.bounce_rate > 0.5:
            recommendations.append("Improve page loading speed and content quality")
        
        if self.average_rating < 4.0:
            recommendations.append("Address product quality issues based on customer feedback")
        
        if self.stock_turnover_rate < 6:
            recommendations.append("Consider inventory reduction or demand generation activities")
        
        return recommendations
    
    def _add_to_performance_history(self, analysis: Dict[str, Any]) -> None:
        """Add analysis to performance history"""
        # Keep only last 12 months of history
        max_history_items = 12
        
        self.performance_history.append({
            'timestamp': analysis['analysis_timestamp'],
            'performance_score': analysis['overall_performance_score'],
            'sales_analysis': analysis['sales_analysis'],
            'conversion_rate': analysis['conversion_analysis']['conversion_rate'],
            'customer_satisfaction': analysis['customer_analysis']['customer_satisfaction']
        })
        
        if len(self.performance_history) > max_history_items:
            self.performance_history = self.performance_history[-max_history_items:]
    
    def _get_historical_date_range(self) -> Dict[str, str]:
        """Get date range of historical data"""
        if not self.performance_history:
            return {'start': None, 'end': None}
        
        return {
            'start': self.performance_history[0]['timestamp'],
            'end': self.performance_history[-1]['timestamp']
        }
    
    def _calculate_historical_trends(self) -> Dict[str, str]:
        """Calculate trends from historical data"""
        if len(self.performance_history) < 2:
            return {}
        
        recent = self.performance_history[-1]
        previous = self.performance_history[-2]
        
        def trend_direction(current: float, prev: float) -> str:
            if current > prev * 1.05:
                return "increasing"
            elif current < prev * 0.95:
                return "decreasing"
            return "stable"
        
        return {
            'performance_score': trend_direction(
                recent['performance_score'], 
                previous['performance_score']
            ),
            'conversion_rate': trend_direction(
                recent['conversion_rate'], 
                previous['conversion_rate']
            ),
            'revenue': trend_direction(
                recent['sales_analysis']['total_revenue'], 
                previous['sales_analysis']['total_revenue']
            )
        }
    
    # Helper methods
    def _identify_funnel_dropoffs(self) -> List[str]:
        return []  # Implement funnel dropoff identification
    
    def _calculate_repeat_customer_percentage(self) -> float:
        if self.unique_visitors == 0:
            return 0.0
        return (self.repeat_customers / self.unique_visitors) * 100
    
    def _estimate_clv(self) -> float:
        return float(self.average_order_value * Decimal('3'))  # Simple 3x AOV estimate
    
    def _calculate_retention_rate(self) -> float:
        return self._calculate_repeat_customer_percentage() / 100  # Convert to 0-1 scale
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analytics to dictionary"""
        return {
            # Performance metrics
            'view_count': self.view_count,
            'click_through_rate': self.click_through_rate,
            'conversion_rate': self.conversion_rate,
            'bounce_rate': self.bounce_rate,
            'average_time_on_page': self.average_time_on_page,
            
            # Sales metrics
            'units_sold': self.units_sold,
            'total_revenue': float(self.total_revenue),
            'average_order_value': float(self.average_order_value),
            'return_rate': self.return_rate,
            
            # Customer metrics
            'unique_visitors': self.unique_visitors,
            'repeat_customers': self.repeat_customers,
            'customer_satisfaction_score': self.customer_satisfaction_score,
            'review_count': self.review_count,
            'average_rating': self.average_rating,
            
            # Inventory metrics
            'stock_turnover_rate': self.stock_turnover_rate,
            'days_of_inventory': self.days_of_inventory,
            'stockout_frequency': self.stockout_frequency,
            
            # Marketing metrics
            'organic_traffic_percentage': self.organic_traffic_percentage,
            'paid_traffic_percentage': self.paid_traffic_percentage,
            'social_media_mentions': self.social_media_mentions,
            
            # Metadata
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'performance_history_count': len(self.performance_history)
        }