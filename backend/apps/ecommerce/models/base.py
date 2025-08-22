# apps/ecommerce/models/base.py

"""
Advanced AI-Powered Base Models and Mixins for E-commerce
Featuring machine learning integration, real-time analytics, and intelligent decision making
"""

from django.db import models
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
from enum import TextChoices
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
    
    # Core pricing fields
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        help_text="Current selling price"
    )
    compare_at_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Original price for comparison (strikethrough price)"
    )
    cost_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost of goods sold"
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # AI-powered pricing optimization
    ai_optimized_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="AI-recommended optimal price"
    )
    price_elasticity = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Price elasticity coefficient (-5.00 to 5.00)"
    )
    demand_sensitivity = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Demand sensitivity to price changes"
    )
    
    # Dynamic pricing controls
    enable_dynamic_pricing = models.BooleanField(default=False)
    min_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Minimum allowed price for dynamic pricing"
    )
    max_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Maximum allowed price for dynamic pricing"
    )
    
    # Market intelligence
    competitor_prices = models.JSONField(default=dict, blank=True)
    market_position = models.CharField(
        max_length=20, 
        choices=[
            ('PREMIUM', 'Premium'),
            ('COMPETITIVE', 'Competitive'),
            ('ECONOMY', 'Economy'),
            ('PENETRATION', 'Market Penetration')
        ],
        default='COMPETITIVE'
    )
    
    # Pricing analytics
    price_history = models.JSONField(default=list, blank=True)
    conversion_rate_by_price = models.JSONField(default=dict, blank=True)
    revenue_optimization_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Revenue optimization score (0-100)"
    )
    
    # Time-based pricing
    seasonal_pricing_rules = models.JSONField(default=dict, blank=True)
    demand_based_multipliers = models.JSONField(default=dict, blank=True)
    
    # Inventory-based pricing
    inventory_price_adjustment = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('1.00'),
        help_text="Price multiplier based on inventory levels"
    )
    
    # Last optimization timestamp
    last_price_optimization = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    @property
    def is_on_sale(self):
        """Check if item is on sale"""
        return self.compare_at_price and self.compare_at_price > self.price
    
    @property
    def discount_amount(self):
        """Calculate discount amount"""
        if self.is_on_sale:
            return self.compare_at_price - self.price
        return Decimal('0.00')
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_on_sale and self.compare_at_price > 0:
            return ((self.compare_at_price - self.price) / self.compare_at_price) * 100
        return Decimal('0.00')
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price and self.price > 0:
            return ((self.price - self.cost_price) / self.price) * 100
        return Decimal('0.00')
    
    @property
    def competitive_advantage(self):
        """Calculate competitive price advantage"""
        if not self.competitor_prices:
            return None
        
        competitor_avg = sum(self.competitor_prices.values()) / len(self.competitor_prices)
        if competitor_avg > 0:
            advantage = ((competitor_avg - float(self.price)) / competitor_avg) * 100
            return round(advantage, 2)
        return None
    
    @property
    def price_optimization_potential(self):
        """Calculate potential revenue increase from price optimization"""
        if not self.ai_optimized_price:
            return None
        
        current_revenue_potential = float(self.price)
        optimized_revenue_potential = float(self.ai_optimized_price)
        
        # Apply elasticity adjustment
        if self.price_elasticity:
            price_change_pct = (optimized_revenue_potential - current_revenue_potential) / current_revenue_potential
            demand_change_pct = float(self.price_elasticity) * price_change_pct
            optimized_revenue_potential *= (1 + demand_change_pct)
        
        potential_increase = ((optimized_revenue_potential - current_revenue_potential) / current_revenue_potential) * 100
        return round(potential_increase, 2)
    
    def record_price_change(self, new_price: Decimal, reason: str = "Manual"):
        """Record price change in history"""
        price_change_record = {
            'timestamp': timezone.now().isoformat(),
            'old_price': float(self.price),
            'new_price': float(new_price),
            'reason': reason,
            'change_percentage': float(((new_price - self.price) / self.price) * 100) if self.price > 0 else 0
        }
        
        if not self.price_history:
            self.price_history = []
        
        self.price_history.append(price_change_record)
        
        # Keep only last 50 price changes
        self.price_history = self.price_history[-50:]
        
        self.price = new_price
        self.save(update_fields=['price', 'price_history'])
    
    def calculate_ai_optimized_price(self) -> Optional[Decimal]:
        """Calculate AI-optimized price based on multiple factors"""
        try:
            base_price = self.price
            optimized_price = base_price
            
            # Market position adjustment
            market_adjustments = {
                'PREMIUM': Decimal('1.15'),    # 15% premium
                'COMPETITIVE': Decimal('1.00'), # No adjustment
                'ECONOMY': Decimal('0.90'),     # 10% discount
                'PENETRATION': Decimal('0.80')  # 20% discount
            }
            
            optimized_price *= market_adjustments.get(self.market_position, Decimal('1.00'))
            
            # Competitor-based adjustment
            if self.competitor_prices:
                competitor_avg = sum(
                    Decimal(str(price)) for price in self.competitor_prices.values()
                ) / len(self.competitor_prices)
                
                # Adjust towards competitive average
                competitive_factor = Decimal('0.95')  # Stay slightly below average
                target_price = competitor_avg * competitive_factor
                
                # Blend with current optimization (70% competitive, 30% other factors)
                optimized_price = (target_price * Decimal('0.7')) + (optimized_price * Decimal('0.3'))
            
            # Inventory-based adjustment
            if hasattr(self, 'available_quantity'):
                if hasattr(self, 'low_stock_threshold'):
                    if self.available_quantity <= self.low_stock_threshold:
                        # Low stock - increase price
                        optimized_price *= Decimal('1.05')
                    elif self.available_quantity > self.low_stock_threshold * 5:
                        # High stock - decrease price
                        optimized_price *= Decimal('0.98')
            
            # Apply inventory price adjustment
            optimized_price *= self.inventory_price_adjustment
            
            # Respect min/max price constraints
            if self.min_price and optimized_price < self.min_price:
                optimized_price = self.min_price
            
            if self.max_price and optimized_price > self.max_price:
                optimized_price = self.max_price
            
            # Ensure profitable pricing
            if self.cost_price and optimized_price < self.cost_price * Decimal('1.1'):
                optimized_price = self.cost_price * Decimal('1.1')  # Minimum 10% markup
            
            return optimized_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
        except Exception as e:
            logger.error(f"Failed to calculate AI-optimized price: {e}")
            return None
    
    def apply_dynamic_pricing(self) -> bool:
        """Apply dynamic pricing if enabled"""
        if not self.enable_dynamic_pricing:
            return False
        
        optimized_price = self.calculate_ai_optimized_price()
        
        if optimized_price and abs(optimized_price - self.price) > Decimal('0.01'):
            # Apply the optimized price
            old_price = self.price
            self.record_price_change(optimized_price, "AI Dynamic Pricing")
            
            self.ai_optimized_price = optimized_price
            self.last_price_optimization = timezone.now()
            self.save(update_fields=['ai_optimized_price', 'last_price_optimization'])
            
            logger.info(f"Dynamic pricing applied: {old_price} -> {optimized_price}")
            return True
        
        return False
    
    def analyze_price_performance(self) -> Dict[str, Any]:
        """Analyze pricing performance and provide insights"""
        performance = {
            'current_price': float(self.price),
            'profit_margin': float(self.profit_margin),
            'competitive_position': self.market_position,
            'optimization_score': float(self.revenue_optimization_score or 0),
        }
        
        # Price trend analysis
        if self.price_history and len(self.price_history) >= 2:
            recent_changes = self.price_history[-5:]  # Last 5 changes
            price_changes = [change['change_percentage'] for change in recent_changes]
            
            performance['price_trend'] = {
                'average_change': sum(price_changes) / len(price_changes),
                'volatility': max(price_changes) - min(price_changes),
                'total_changes': len(self.price_history)
            }
        
        # Competitive analysis
        if self.competitor_prices:
            performance['competitive_analysis'] = {
                'competitor_count': len(self.competitor_prices),
                'price_advantage': self.competitive_advantage,
                'market_position_score': self._calculate_market_position_score()
            }
        
        # Optimization potential
        if self.ai_optimized_price:
            performance['optimization_potential'] = {
                'recommended_price': float(self.ai_optimized_price),
                'potential_improvement': self.price_optimization_potential,
                'confidence_score': self._calculate_pricing_confidence()
            }
        
        return performance
    
    def _calculate_market_position_score(self) -> float:
        """Calculate market position score"""
        if not self.competitor_prices:
            return 50.0  # Neutral score
        
        competitor_prices = list(self.competitor_prices.values())
        competitor_avg = sum(competitor_prices) / len(competitor_prices)
        
        price_ratio = float(self.price) / competitor_avg
        
        # Score based on price position
        if price_ratio <= 0.8:
            return 90.0  # Excellent value position
        elif price_ratio <= 0.9:
            return 75.0  # Good value position
        elif price_ratio <= 1.1:
            return 60.0  # Competitive position
        elif price_ratio <= 1.2:
            return 40.0  # Premium position
        else:
            return 20.0  # High premium position
    
    def _calculate_pricing_confidence(self) -> float:
        """Calculate confidence score for pricing recommendations"""
        confidence = 50.0  # Base confidence
        
        # Data quality factors
        if self.competitor_prices:
            confidence += min(len(self.competitor_prices) * 5, 20)  # Up to 20 points for competitor data
        
        if self.price_history:
            confidence += min(len(self.price_history) * 2, 15)  # Up to 15 points for price history
        
        if self.cost_price:
            confidence += 10  # 10 points for having cost data
        
        if self.price_elasticity:
            confidence += 5  # 5 points for elasticity data
        
        return min(confidence, 95.0)  # Cap at 95%


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