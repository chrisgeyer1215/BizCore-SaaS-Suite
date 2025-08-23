# apps/ecommerce/models/base.py

"""
Advanced AI-Powered Base Models and Mixins for E-commerce
Featuring machine learning integration, real-time analytics, and intelligent decision making
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, datetime
import uuid
import json
import logging
from django.db.models import TextChoices
from typing import Dict, List, Any, Optional, Tuple

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()
logger = logging.getLogger(__name__)


class EcommerceBaseModel(TenantBaseModel):
    """
    Advanced AI-powered base model for all e-commerce models
    Features real-time analytics, performance tracking, and intelligent insights
    """
    
    # AI-powered analytics fields
    ai_insights_last_updated = models.DateTimeField(null=True, blank=True)
    performance_metrics = models.JSONField(default=dict, blank=True)
    predictive_analytics = models.JSONField(default=dict, blank=True)
    ai_recommendations = models.JSONField(default=list, blank=True)
    
    # Real-time tracking
    view_count = models.PositiveIntegerField(default=0)
    interaction_count = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Performance optimization
    cache_version = models.PositiveIntegerField(default=1)
    optimization_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI-calculated optimization score (0-100)"
    )
    
    class Meta:
        abstract = True
    
    def update_analytics(self, event_type: str, metadata: Dict = None):
        """Update analytics data for this model instance"""
        try:
            current_time = timezone.now()
            
            # Update activity timestamp
            self.last_activity = current_time
            
            # Increment counters based on event type
            if event_type == 'view':
                self.view_count += 1
            elif event_type == 'interaction':
                self.interaction_count += 1
            
            # Store event metadata
            if metadata:
                if not self.performance_metrics:
                    self.performance_metrics = {}
                
                event_key = f"{event_type}_events"
                if event_key not in self.performance_metrics:
                    self.performance_metrics[event_key] = []
                
                self.performance_metrics[event_key].append({
                    'timestamp': current_time.isoformat(),
                    'metadata': metadata
                })
                
                # Keep only last 100 events per type
                self.performance_metrics[event_key] = self.performance_metrics[event_key][-100:]
            
            # Save without triggering full model validation
            self.save(update_fields=['last_activity', 'view_count', 'interaction_count', 'performance_metrics'])
            
        except Exception as e:
            logger.error(f"Failed to update analytics for {self.__class__.__name__}: {e}")
    
    def get_ai_insights(self) -> Dict[str, Any]:
        """Get AI-powered insights for this instance"""
        cache_key = f"ai_insights_{self.__class__.__name__}_{self.pk}"
        
        # Check cache first
        cached_insights = cache.get(cache_key)
        if cached_insights and self.ai_insights_last_updated:
            cache_age = timezone.now() - self.ai_insights_last_updated
            if cache_age < timedelta(hours=1):  # Cache valid for 1 hour
                return cached_insights
        
        # Generate new insights
        insights = self._calculate_ai_insights()
        
        # Cache the results
        cache.set(cache_key, insights, timeout=3600)  # 1 hour
        
        # Update timestamp
        self.ai_insights_last_updated = timezone.now()
        self.save(update_fields=['ai_insights_last_updated'])
        
        return insights
    
    def _calculate_ai_insights(self) -> Dict[str, Any]:
        """Calculate AI insights - to be overridden by subclasses"""
        return {
            'performance_score': self.calculate_performance_score(),
            'engagement_metrics': self.get_engagement_metrics(),
            'optimization_suggestions': self.get_optimization_suggestions(),
            'trends': self.analyze_trends()
        }
    
    def calculate_performance_score(self) -> float:
        """Calculate performance score based on various metrics"""
        score = 50.0  # Base score
        
        # Activity-based scoring
        if self.view_count > 0:
            activity_score = min(self.view_count / 100 * 20, 30)  # Max 30 points for views
            score += activity_score
        
        if self.interaction_count > 0:
            interaction_score = min(self.interaction_count / 50 * 20, 20)  # Max 20 points for interactions
            score += interaction_score
        
        # Recency bonus
        if self.last_activity:
            days_since_activity = (timezone.now() - self.last_activity).days
            if days_since_activity <= 7:
                score += 10  # Recent activity bonus
            elif days_since_activity <= 30:
                score += 5
        
        return min(score, 100.0)
    
    def get_engagement_metrics(self) -> Dict[str, Any]:
        """Get engagement metrics"""
        total_interactions = self.view_count + self.interaction_count
        
        engagement_rate = 0.0
        if self.view_count > 0:
            engagement_rate = (self.interaction_count / self.view_count) * 100
        
        return {
            'total_views': self.view_count,
            'total_interactions': self.interaction_count,
            'engagement_rate': round(engagement_rate, 2),
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def get_optimization_suggestions(self) -> List[Dict[str, str]]:
        """Get AI-powered optimization suggestions"""
        suggestions = []
        
        # Low engagement suggestions
        if self.view_count > 50 and self.interaction_count < 5:
            suggestions.append({
                'type': 'ENGAGEMENT',
                'priority': 'HIGH',
                'suggestion': 'Low interaction rate detected. Consider improving content quality or call-to-action placement.',
                'expected_impact': 'Increase engagement rate by 15-25%'
            })
        
        # Inactivity suggestions
        if self.last_activity:
            days_inactive = (timezone.now() - self.last_activity).days
            if days_inactive > 30:
                suggestions.append({
                    'type': 'REACTIVATION',
                    'priority': 'MEDIUM',
                    'suggestion': f'No activity for {days_inactive} days. Consider promotional campaigns or content updates.',
                    'expected_impact': 'Restore 20-30% of previous activity levels'
                })
        
        return suggestions
    
    def analyze_trends(self) -> Dict[str, Any]:
        """Analyze performance trends"""
        trends = {
            'view_trend': 'stable',
            'interaction_trend': 'stable',
            'performance_trend': 'stable'
        }
        
        if self.performance_metrics:
            # Simple trend analysis based on recent events
            view_events = self.performance_metrics.get('view_events', [])
            if len(view_events) >= 10:
                recent_views = len([e for e in view_events[-5:] if e])
                older_views = len([e for e in view_events[-10:-5] if e])
                
                if recent_views > older_views * 1.2:
                    trends['view_trend'] = 'increasing'
                elif recent_views < older_views * 0.8:
                    trends['view_trend'] = 'decreasing'
        
        return trends
    
    def invalidate_cache(self):
        """Invalidate cached data for this instance"""
        self.cache_version += 1
        self.save(update_fields=['cache_version'])
        
        # Clear related caches
        cache_keys = [
            f"ai_insights_{self.__class__.__name__}_{self.pk}",
            f"performance_metrics_{self.__class__.__name__}_{self.pk}",
        ]
        
        cache.delete_many(cache_keys)


class TimestampedModel(models.Model):
    """Abstract model with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SEOMixin(models.Model):
    """SEO fields mixin for e-commerce models"""
    
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(max_length=320, blank=True)
    seo_keywords = models.TextField(blank=True)
    canonical_url = models.URLField(blank=True)
    
    # OpenGraph and social media
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.TextField(max_length=300, blank=True)
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)
    
    # Twitter Card
    twitter_title = models.CharField(max_length=255, blank=True)
    twitter_description = models.TextField(max_length=200, blank=True)
    twitter_image = models.ImageField(upload_to='seo/twitter_images/', blank=True, null=True)
    
    # JSON-LD structured data
    structured_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True



class AIOptimizedPricingMixin(models.Model):
    """
    Advanced AI-powered pricing mixin with dynamic optimization, 
    competitor analysis, and intelligent price adjustments
    """
    
    # Core Pricing Fields
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    compare_at_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Additional AI/ML Enhancement Fields
    ml_model_version = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Version of ML model used for price optimization"
    )
    
    prediction_confidence = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI model confidence in price prediction (0-100%)"
    )
    
    # A/B Testing for Pricing
    ab_test_group = models.CharField(
        max_length=20,
        choices=[
            ('CONTROL', 'Control Group'),
            ('VARIANT_A', 'Test Variant A'),
            ('VARIANT_B', 'Test Variant B'),
            ('VARIANT_C', 'Test Variant C'),
        ],
        blank=True,
        null=True,
        help_text="A/B testing group for pricing experiments"
    )
    
    ab_test_start_date = models.DateTimeField(null=True, blank=True)
    ab_test_end_date = models.DateTimeField(null=True, blank=True)
    ab_test_metrics = models.JSONField(default=dict, blank=True)
    
    # Advanced Market Factors
    market_volatility_index = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Market volatility index affecting pricing (0-100)"
    )
    
    customer_segment_pricing = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Pricing by customer segment"
    )
    
    geographic_pricing = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Pricing by geographic region"
    )
    
    # Real-time Pricing Triggers
    auto_price_adjustment_rules = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Rules for automatic price adjustments"
    )
    
    price_alert_thresholds = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Thresholds for price change alerts"
    )
    
    # Your existing methods remain...
    
    # Additional Enhanced Methods:
    
    def get_segment_price(self, customer_segment: str) -> Decimal:
        """Get price for specific customer segment"""
        if not self.customer_segment_pricing or customer_segment not in self.customer_segment_pricing:
            return self.price
        
        segment_data = self.customer_segment_pricing[customer_segment]
        if isinstance(segment_data, dict):
            multiplier = Decimal(str(segment_data.get('multiplier', 1.0)))
            return (self.price * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return Decimal(str(segment_data))
    
    def get_geographic_price(self, region: str, currency: str = None) -> Dict[str, Any]:
        """Get price for specific geographic region"""
        base_price = self.price
        target_currency = currency or self.currency
        
        if self.geographic_pricing and region in self.geographic_pricing:
            region_data = self.geographic_pricing[region]
            
            # Apply regional multiplier
            if 'multiplier' in region_data:
                base_price *= Decimal(str(region_data['multiplier']))
            
            # Apply currency conversion if different
            if 'currency_rate' in region_data and target_currency != self.currency:
                base_price *= Decimal(str(region_data['currency_rate']))
        
        return {
            'price': base_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'currency': target_currency,
            'region': region
        }
    
    def start_ab_test(self, variant: str, duration_days: int = 30) -> bool:
        """Start A/B testing for pricing"""
        if self.ab_test_group:
            logger.warning(f"A/B test already running for {self.ab_test_group}")
            return False
        
        self.ab_test_group = variant
        self.ab_test_start_date = timezone.now()
        self.ab_test_end_date = timezone.now() + timedelta(days=duration_days)
        
        # Initialize metrics tracking
        self.ab_test_metrics = {
            'start_price': float(self.price),
            'impressions': 0,
            'conversions': 0,
            'revenue': 0.0,
            'daily_metrics': []
        }
        
        self.save(update_fields=[
            'ab_test_group', 'ab_test_start_date', 
            'ab_test_end_date', 'ab_test_metrics'
        ])
        
        logger.info(f"Started A/B test {variant} for {duration_days} days")
        return True
    
    def end_ab_test(self) -> Dict[str, Any]:
        """End A/B testing and return results"""
        if not self.ab_test_group:
            return {'error': 'No active A/B test'}
        
        # Calculate final metrics
        metrics = self.ab_test_metrics or {}
        impressions = metrics.get('impressions', 0)
        conversions = metrics.get('conversions', 0)
        revenue = metrics.get('revenue', 0.0)
        
        results = {
            'test_group': self.ab_test_group,
            'duration_days': (timezone.now() - self.ab_test_start_date).days if self.ab_test_start_date else 0,
            'total_impressions': impressions,
            'total_conversions': conversions,
            'conversion_rate': (conversions / impressions * 100) if impressions > 0 else 0,
            'total_revenue': revenue,
            'average_order_value': revenue / conversions if conversions > 0 else 0,
            'daily_metrics': metrics.get('daily_metrics', [])
        }
        
        # Reset A/B test fields
        self.ab_test_group = None
        self.ab_test_start_date = None
        self.ab_test_end_date = None
        
        self.save(update_fields=[
            'ab_test_group', 'ab_test_start_date', 'ab_test_end_date'
        ])
        
        logger.info(f"Ended A/B test with results: {results}")
        return results
    
    def track_ab_test_conversion(self, revenue_amount: Decimal = None):
        """Track conversion for A/B testing"""
        if not self.ab_test_group or not self.ab_test_metrics:
            return
        
        metrics = self.ab_test_metrics.copy()
        metrics['conversions'] += 1
        
        if revenue_amount:
            metrics['revenue'] += float(revenue_amount)
        
        # Track daily metrics
        today = timezone.now().date().isoformat()
        daily_metrics = metrics.get('daily_metrics', [])
        
        # Find today's entry or create new one
        today_metrics = next(
            (day for day in daily_metrics if day['date'] == today), 
            None
        )
        
        if today_metrics:
            today_metrics['conversions'] += 1
            if revenue_amount:
                today_metrics['revenue'] += float(revenue_amount)
        else:
            daily_metrics.append({
                'date': today,
                'conversions': 1,
                'revenue': float(revenue_amount) if revenue_amount else 0.0,
                'impressions': 0
            })
        
        metrics['daily_metrics'] = daily_metrics[-30:]  # Keep last 30 days
        self.ab_test_metrics = metrics
        
        self.save(update_fields=['ab_test_metrics'])
    
    def evaluate_price_rules(self) -> List[Dict[str, Any]]:
        """Evaluate automatic pricing rules and return suggested actions"""
        if not self.auto_price_adjustment_rules:
            return []
        
        suggestions = []
        
        for rule_name, rule_config in self.auto_price_adjustment_rules.items():
            try:
                suggestion = self._evaluate_single_rule(rule_name, rule_config)
                if suggestion:
                    suggestions.append(suggestion)
            except Exception as e:
                logger.error(f"Failed to evaluate rule {rule_name}: {e}")
        
        return suggestions
    
    def _evaluate_single_rule(self, rule_name: str, rule_config: Dict) -> Optional[Dict[str, Any]]:
        """Evaluate a single pricing rule"""
        rule_type = rule_config.get('type')
        
        if rule_type == 'inventory_based':
            return self._evaluate_inventory_rule(rule_name, rule_config)
        elif rule_type == 'competitor_based':
            return self._evaluate_competitor_rule(rule_name, rule_config)
        elif rule_type == 'performance_based':
            return self._evaluate_performance_rule(rule_name, rule_config)
        elif rule_type == 'time_based':
            return self._evaluate_time_rule(rule_name, rule_config)
        
        return None
    
    def _evaluate_inventory_rule(self, rule_name: str, rule_config: Dict) -> Optional[Dict[str, Any]]:
        """Evaluate inventory-based pricing rule"""
        if not hasattr(self, 'available_quantity'):
            return None
        
        low_threshold = rule_config.get('low_inventory_threshold', 10)
        high_threshold = rule_config.get('high_inventory_threshold', 100)
        
        if self.available_quantity <= low_threshold:
            # Low inventory - suggest price increase
            increase_pct = rule_config.get('low_inventory_increase', 5.0)
            new_price = self.price * (1 + Decimal(str(increase_pct)) / 100)
            
            return {
                'rule_name': rule_name,
                'action': 'increase_price',
                'current_price': float(self.price),
                'suggested_price': float(new_price),
                'reason': f'Low inventory ({self.available_quantity} units)',
                'confidence': 0.8
            }
        
        elif self.available_quantity >= high_threshold:
            # High inventory - suggest price decrease
            decrease_pct = rule_config.get('high_inventory_decrease', 3.0)
            new_price = self.price * (1 - Decimal(str(decrease_pct)) / 100)
            
            return {
                'rule_name': rule_name,
                'action': 'decrease_price',
                'current_price': float(self.price),
                'suggested_price': float(new_price),
                'reason': f'High inventory ({self.available_quantity} units)',
                'confidence': 0.7
            }
        
        return None
    
    def get_pricing_insights(self) -> Dict[str, Any]:
        """Get comprehensive pricing insights and recommendations"""
        insights = {
            'current_performance': self.analyze_price_performance(),
            'ai_recommendations': {},
            'market_analysis': {},
            'optimization_opportunities': [],
            'risk_factors': []
        }
        
        # AI recommendations
        if self.ai_optimized_price:
            insights['ai_recommendations'] = {
                'recommended_price': float(self.ai_optimized_price),
                'confidence': float(self.prediction_confidence or 0),
                'potential_lift': self.price_optimization_potential,
                'model_version': self.ml_model_version
            }
        
        # Market analysis
        if self.competitor_prices:
            competitor_analysis = self._analyze_competitor_landscape()
            insights['market_analysis'] = competitor_analysis
        
        # Optimization opportunities
        rule_suggestions = self.evaluate_price_rules()
        insights['optimization_opportunities'] = rule_suggestions
        
        # Risk factors
        risk_factors = self._identify_pricing_risks()
        insights['risk_factors'] = risk_factors
        
        return insights
    
    def _analyze_competitor_landscape(self) -> Dict[str, Any]:
        """Analyze competitive landscape"""
        if not self.competitor_prices:
            return {}
        
        competitor_prices = [float(price) for price in self.competitor_prices.values()]
        current_price = float(self.price)
        
        return {
            'competitor_count': len(competitor_prices),
            'price_range': {
                'min': min(competitor_prices),
                'max': max(competitor_prices),
                'average': sum(competitor_prices) / len(competitor_prices)
            },
            'position': {
                'percentile': sum(1 for p in competitor_prices if current_price <= p) / len(competitor_prices) * 100,
                'rank': sorted(competitor_prices + [current_price]).index(current_price) + 1
            },
            'competitive_gap': self.competitive_advantage
        }
    
    def _identify_pricing_risks(self) -> List[Dict[str, Any]]:
        """Identify potential pricing risks"""
        risks = []
        
        # Margin risk
        if self.cost_price and self.profit_margin < 10:
            risks.append({
                'type': 'low_margin',
                'severity': 'high' if self.profit_margin < 5 else 'medium',
                'message': f'Low profit margin: {self.profit_margin:.1f}%',
                'recommendation': 'Consider increasing price or reducing costs'
            })
        
        # Competitive risk
        if self.competitive_advantage and self.competitive_advantage < -20:
            risks.append({
                'type': 'price_premium',
                'severity': 'medium',
                'message': f'Price {abs(self.competitive_advantage):.1f}% above competitors',
                'recommendation': 'Monitor competitor responses and conversion rates'
            })
        
        # Volatility risk
        if self.market_volatility_index and self.market_volatility_index > 70:
            risks.append({
                'type': 'market_volatility',
                'severity': 'medium',
                'message': f'High market volatility: {self.market_volatility_index}',
                'recommendation': 'Consider more frequent price reviews'
            })
        
        return risks
    
    class Meta:
        abstract = True
        
class InventoryMixin(models.Model):
    """Inventory tracking mixin"""
    
    class InventoryPolicy(TextChoices):
        DENY = 'DENY', 'Deny purchases when out of stock'
        CONTINUE = 'CONTINUE', 'Continue selling when out of stock'
        
    class FulfillmentService(TextChoices):
        MANUAL = 'MANUAL', 'Manual fulfillment'
        AUTOMATIC = 'AUTOMATIC', 'Automatic fulfillment'
        THIRD_PARTY = 'THIRD_PARTY', 'Third party fulfillment'
    
    # Inventory tracking
    track_quantity = models.BooleanField(
        default=True, 
        help_text="Whether to track inventory for this item"
    )
    inventory_policy = models.CharField(
        max_length=20, 
        choices=InventoryPolicy.choices, 
        default=InventoryPolicy.DENY
    )
    fulfillment_service = models.CharField(
        max_length=20, 
        choices=FulfillmentService.choices, 
        default=FulfillmentService.MANUAL
    )
    
    # Stock information
    stock_quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    committed_quantity = models.IntegerField(default=0)
    incoming_quantity = models.IntegerField(default=0)
    
    # Inventory settings
    low_stock_threshold = models.IntegerField(
        default=10, 
        help_text="Alert when stock falls below this level"
    )
    out_of_stock_threshold = models.IntegerField(
        default=0, 
        help_text="Consider out of stock when below this level"
    )
    
    # Weight and dimensions for shipping
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        null=True, 
        blank=True,
        help_text="Weight in grams"
    )
    length = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Length in cm"
    )
    width = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Width in cm"
    )
    height = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Height in cm"
    )
    
    class Meta:
        abstract = True
    
    @property
    def available_quantity(self):
        """Calculate available quantity"""
        if not self.track_quantity:
            return float('inf')  # Unlimited if not tracking
        return max(0, self.stock_quantity - self.reserved_quantity - self.committed_quantity)
    
    @property
    def is_in_stock(self):
        """Check if item is in stock"""
        if self.inventory_policy == self.InventoryPolicy.CONTINUE:
            return True
        return self.available_quantity > self.out_of_stock_threshold
    
    @property
    def is_low_stock(self):
        """Check if item is low in stock"""
        if not self.track_quantity:
            return False
        return self.available_quantity <= self.low_stock_threshold
    
    @property
    def needs_restock(self):
        """Check if item needs restocking"""
        return self.is_low_stock or not self.is_in_stock


class VisibilityMixin(models.Model):
    """Visibility and publishing mixin"""
    
    class PublishStatus(TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'
        HIDDEN = 'HIDDEN', 'Hidden'
    
    status = models.CharField(
        max_length=20, 
        choices=PublishStatus.choices, 
        default=PublishStatus.DRAFT
    )
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Publishing schedule
    published_at = models.DateTimeField(null=True, blank=True)
    publish_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Schedule publication for future date"
    )
    unpublish_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Schedule unpublication for future date"
    )
    
    # Visibility settings
    is_visible_in_search = models.BooleanField(default=True)
    is_visible_in_storefront = models.BooleanField(default=True)
    requires_authentication = models.BooleanField(default=False)
    
    class Meta:
        abstract = True
    
    @property
    def is_visible(self):
        """Check if item is currently visible"""
        now = timezone.now()
        
        # Check basic visibility
        if not self.is_active or not self.is_published:
            return False
            
        # Check publish schedule
        if self.publish_date and now < self.publish_date:
            return False
            
        if self.unpublish_date and now > self.unpublish_date:
            return False
            
        return True
    
    def publish(self):
        """Publish the item"""
        self.is_published = True
        self.status = self.PublishStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save()
    
    def unpublish(self):
        """Unpublish the item"""
        self.is_published = False
        self.status = self.PublishStatus.DRAFT
        self.save()
    
    def archive(self):
        """Archive the item"""
        self.is_published = False
        self.status = self.PublishStatus.ARCHIVED
        self.save()


class SortableMixin(models.Model):
    """Sortable mixin for ordering items"""
    
    sort_order = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True


class TagMixin(models.Model):
    """Tag system mixin"""
    
    tags = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of tags for categorization and search"
    )
    
    class Meta:
        abstract = True
    
    def add_tag(self, tag):
        """Add a tag to the item"""
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.save()
    
    def remove_tag(self, tag):
        """Remove a tag from the item"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.save()
    
    def has_tag(self, tag):
        """Check if item has a specific tag"""
        return tag in self.tags


class AuditMixin(models.Model):
    """Audit trail mixin"""
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_created'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_updated'
    )
    
    class Meta:
        abstract = True


class CommonChoices:
    """Common choice definitions for e-commerce models"""
    
    class Currency(TextChoices):
        USD = 'USD', 'US Dollar'
        EUR = 'EUR', 'Euro'
        GBP = 'GBP', 'British Pound'
        CAD = 'CAD', 'Canadian Dollar'
        AUD = 'AUD', 'Australian Dollar'
        JPY = 'JPY', 'Japanese Yen'
        CNY = 'CNY', 'Chinese Yuan'
        INR = 'INR', 'Indian Rupee'
        BRL = 'BRL', 'Brazilian Real'
        MXN = 'MXN', 'Mexican Peso'
    
    class PaymentMethod(TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
        PAYPAL = 'PAYPAL', 'PayPal'
        APPLE_PAY = 'APPLE_PAY', 'Apple Pay'
        GOOGLE_PAY = 'GOOGLE_PAY', 'Google Pay'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CASH_ON_DELIVERY = 'COD', 'Cash on Delivery'
        CRYPTOCURRENCY = 'CRYPTO', 'Cryptocurrency'
        GIFT_CARD = 'GIFT_CARD', 'Gift Card'
        STORE_CREDIT = 'STORE_CREDIT', 'Store Credit'
    
    class TransactionStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        CAPTURED = 'CAPTURED', 'Captured'
        PARTIALLY_CAPTURED = 'PARTIALLY_CAPTURED', 'Partially Captured'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        DISPUTED = 'DISPUTED', 'Disputed'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
    
    class OrderStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        PARTIALLY_SHIPPED = 'PARTIALLY_SHIPPED', 'Partially Shipped'
        RETURN_REQUESTED = 'RETURN_REQUESTED', 'Return Requested'
        RETURNED = 'RETURNED', 'Returned'
    
    class FulfillmentStatus(TextChoices):
        UNFULFILLED = 'UNFULFILLED', 'Unfulfilled'
        PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED', 'Partially Fulfilled'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        RESTOCKED = 'RESTOCKED', 'Restocked'
        
    class ShippingStatus(TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for Delivery'
        DELIVERED = 'DELIVERED', 'Delivered'
        FAILED_DELIVERY = 'FAILED_DELIVERY', 'Failed Delivery'
        RETURNED_TO_SENDER = 'RETURNED_TO_SENDER', 'Returned to Sender'