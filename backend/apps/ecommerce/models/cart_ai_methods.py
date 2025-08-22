# apps/ecommerce/models/cart_ai_methods.py

"""
AI Methods Extension for Intelligent Cart
This file contains AI-powered methods that extend the IntelligentCart model
"""

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from collections import Counter, defaultdict
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CartAIMixin(models.Model):
    """
    AI-powered methods mixin for Intelligent Cart
    """
    
    class Meta:
        abstract = True
    
    def record_interaction(self, interaction_type: str, metadata: Dict = None):
        """Record user interaction for behavioral analysis"""
        try:
            interaction_data = {
                'type': interaction_type,
                'timestamp': timezone.now().isoformat(),
                'metadata': metadata or {}
            }
            
            if not self.interaction_history:
                self.interaction_history = []
            
            self.interaction_history.append(interaction_data)
            
            # Keep only last 100 interactions
            self.interaction_history = self.interaction_history[-100:]
            
            # Update engagement metrics
            self.update_engagement_metrics()
            
            # Save without triggering full model validation
            self.save(update_fields=['interaction_history', 'engagement_metrics'])
            
        except Exception as e:
            logger.error(f"Failed to record cart interaction: {e}")
    
    def update_engagement_metrics(self):
        """Update real-time engagement metrics"""
        if not self.interaction_history:
            self.engagement_metrics = {}
            return
        
        # Calculate metrics from interaction history
        total_interactions = len(self.interaction_history)
        interaction_types = Counter([i['type'] for i in self.interaction_history])
        
        # Recent activity (last hour)
        recent_threshold = timezone.now() - timedelta(hours=1)
        recent_interactions = [
            i for i in self.interaction_history 
            if timezone.datetime.fromisoformat(i['timestamp'].replace('Z', '+00:00')) > recent_threshold
        ]
        
        # Session duration estimation
        if len(self.interaction_history) >= 2:
            first_interaction = timezone.datetime.fromisoformat(
                self.interaction_history[0]['timestamp'].replace('Z', '+00:00')
            )
            last_interaction = timezone.datetime.fromisoformat(
                self.interaction_history[-1]['timestamp'].replace('Z', '+00:00')
            )
            session_duration = (last_interaction - first_interaction).total_seconds()
        else:
            session_duration = 0
        
        self.engagement_metrics = {
            'total_interactions': total_interactions,
            'interaction_types': dict(interaction_types),
            'recent_activity_count': len(recent_interactions),
            'session_duration_seconds': session_duration,
            'engagement_score': self.calculate_engagement_score(),
            'last_updated': timezone.now().isoformat()
        }
    
    def calculate_engagement_score(self) -> float:
        """Calculate overall engagement score"""
        if not self.interaction_history:
            return 0.0
        
        score = 0.0
        
        # Base score from interaction count
        interaction_count = len(self.interaction_history)
        score += min(interaction_count * 2, 40)  # Max 40 points from interactions
        
        # Diversity bonus (different types of interactions)
        interaction_types = set([i['type'] for i in self.interaction_history])
        score += len(interaction_types) * 5  # 5 points per interaction type
        
        # Recency bonus
        if self.interaction_history:
            last_interaction = timezone.datetime.fromisoformat(
                self.interaction_history[-1]['timestamp'].replace('Z', '+00:00')
            )
            hours_since = (timezone.now() - last_interaction).total_seconds() / 3600
            
            if hours_since <= 1:
                score += 20  # High recency bonus
            elif hours_since <= 24:
                score += 10  # Medium recency bonus
            elif hours_since <= 168:  # 1 week
                score += 5   # Low recency bonus
        
        # Session depth bonus
        session_metrics = self.engagement_metrics.get('session_duration_seconds', 0)
        if session_metrics > 300:  # More than 5 minutes
            score += 15
        elif session_metrics > 60:  # More than 1 minute
            score += 5
        
        return min(score, 100.0)  # Cap at 100
    
    def analyze_cart_with_ai(self):
        """Perform comprehensive AI analysis of cart"""
        try:
            # Calculate conversion probability
            self.conversion_probability = self.calculate_conversion_probability()
            
            # Calculate abandonment risk
            self.abandonment_risk_score = self.calculate_abandonment_risk()
            
            # Calculate personalization effectiveness
            self.personalization_score = self.calculate_personalization_score()
            
            # Predict final cart value
            self.predicted_final_value = self.predict_final_cart_value()
            
            # Determine optimal checkout timing
            self.optimal_checkout_time = self.calculate_optimal_checkout_time()
            
            # Update behavioral segments
            self.behavioral_segments = self.determine_behavioral_segments()
            
            # Cache AI insights
            self.cache_ai_insights()
            
            self.save(update_fields=[
                'conversion_probability', 'abandonment_risk_score', 
                'personalization_score', 'predicted_final_value',
                'optimal_checkout_time', 'behavioral_segments'
            ])
            
        except Exception as e:
            logger.error(f"Failed to analyze cart with AI: {e}")
    
    def calculate_conversion_probability(self) -> Decimal:
        """AI-powered conversion probability calculation"""
        base_probability = Decimal('25.0')  # Base 25% conversion rate
        
        # Engagement factor
        engagement_score = self.engagement_metrics.get('engagement_score', 0)
        engagement_bonus = min(engagement_score / 100 * 30, 30)  # Up to 30% bonus
        
        # Cart value factor
        if self.total_amount:
            if self.total_amount > 100:
                base_probability += Decimal('10.0')  # Higher value carts convert better
            elif self.total_amount > 50:
                base_probability += Decimal('5.0')
        
        # Item count factor
        if self.item_count >= 3:
            base_probability += Decimal('8.0')  # Multiple items indicate intent
        elif self.item_count >= 2:
            base_probability += Decimal('4.0')
        
        # User history factor (if customer exists)
        if hasattr(self, 'customer') and self.customer:
            if self.customer.total_orders > 0:
                base_probability += Decimal('15.0')  # Returning customers convert better
            if self.customer.customer_tier in ['GOLD', 'PLATINUM', 'VIP']:
                base_probability += Decimal('10.0')  # VIP customers convert better
        
        # Time factor
        if self.created_at:
            age_hours = (timezone.now() - self.created_at).total_seconds() / 3600
            if age_hours <= 1:
                base_probability += Decimal('10.0')  # Fresh carts convert better
            elif age_hours > 24:
                base_probability -= Decimal('15.0')  # Old carts convert worse
        
        # Applied discounts factor
        if self.discount_amount > 0:
            base_probability += Decimal('12.0')  # Discounts improve conversion
        
        total_probability = base_probability + Decimal(str(engagement_bonus))
        return min(max(total_probability, Decimal('1.0')), Decimal('95.0'))  # Cap between 1-95%
    
    def calculate_abandonment_risk(self) -> Decimal:
        """Calculate AI-powered abandonment risk score"""
        risk_score = Decimal('20.0')  # Base risk score
        
        # Time-based risk
        if self.created_at:
            age_hours = (timezone.now() - self.created_at).total_seconds() / 3600
            if age_hours > 48:
                risk_score += Decimal('30.0')
            elif age_hours > 24:
                risk_score += Decimal('20.0')
            elif age_hours > 6:
                risk_score += Decimal('10.0')
        
        # Inactivity risk
        if self.last_activity:
            hours_inactive = (timezone.now() - self.last_activity).total_seconds() / 3600
            if hours_inactive > 12:
                risk_score += Decimal('25.0')
            elif hours_inactive > 6:
                risk_score += Decimal('15.0')
            elif hours_inactive > 2:
                risk_score += Decimal('8.0')
        
        # Engagement risk (inverse of engagement)
        engagement_score = self.engagement_metrics.get('engagement_score', 0)
        if engagement_score < 20:
            risk_score += Decimal('20.0')
        elif engagement_score < 40:
            risk_score += Decimal('10.0')
        
        # Cart value risk
        if self.total_amount:
            if self.total_amount > 200:
                risk_score += Decimal('5.0')  # High-value carts sometimes abandoned due to price shock
            elif self.total_amount < 20:
                risk_score += Decimal('10.0')  # Low-value carts often abandoned
        
        # Item complexity risk
        if self.item_count > 10:
            risk_score += Decimal('8.0')  # Too many items can cause decision paralysis
        
        return min(risk_score, Decimal('95.0'))  # Cap at 95%
    
    def calculate_personalization_score(self) -> Decimal:
        """Calculate effectiveness of personalization"""
        score = Decimal('50.0')  # Base score
        
        # Recommendation engagement
        if self.ai_recommendations:
            # Check if user interacted with recommendations
            rec_interactions = [
                i for i in self.interaction_history 
                if i.get('metadata', {}).get('source') == 'ai_recommendation'
            ]
            if rec_interactions:
                score += Decimal('20.0')  # Bonus for engaging with recommendations
        
        # Customer data completeness
        if hasattr(self, 'customer') and self.customer:
            if self.customer.favorite_categories:
                score += Decimal('10.0')
            if self.customer.purchase_history:
                score += Decimal('10.0')
            if self.customer.behavioral_segments:
                score += Decimal('5.0')
        
        # Dynamic pricing effectiveness
        if self.dynamic_pricing_applied:
            score += Decimal('15.0')
        
        return min(score, Decimal('100.0'))
    
    def predict_final_cart_value(self) -> Optional[Decimal]:
        """Predict final cart value using AI"""
        if not self.total_amount:
            return None
        
        current_value = self.total_amount
        predicted_multiplier = Decimal('1.0')
        
        # Engagement-based prediction
        engagement_score = self.engagement_metrics.get('engagement_score', 0)
        if engagement_score > 70:
            predicted_multiplier = Decimal('1.25')  # High engagement = likely to add more
        elif engagement_score > 40:
            predicted_multiplier = Decimal('1.10')
        elif engagement_score < 20:
            predicted_multiplier = Decimal('0.95')  # Low engagement = might remove items
        
        # Behavioral segment adjustments
        if 'high_value_shopper' in self.behavioral_segments:
            predicted_multiplier *= Decimal('1.15')
        elif 'bargain_hunter' in self.behavioral_segments:
            predicted_multiplier *= Decimal('0.95')
        
        # Time-based adjustments
        if self.created_at:
            age_hours = (timezone.now() - self.created_at).total_seconds() / 3600
            if age_hours <= 2:
                predicted_multiplier *= Decimal('1.05')  # Fresh carts likely to grow
        
        predicted_value = current_value * predicted_multiplier
        return predicted_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def calculate_optimal_checkout_time(self) -> Optional[timezone.datetime]:
        """Calculate optimal time for checkout prompting"""
        if not self.created_at:
            return None
        
        # Base optimal time is 2 hours after cart creation
        optimal_time = self.created_at + timedelta(hours=2)
        
        # Adjust based on user behavior
        engagement_score = self.engagement_metrics.get('engagement_score', 0)
        
        if engagement_score > 70:
            # High engagement - prompt sooner
            optimal_time = self.created_at + timedelta(hours=1)
        elif engagement_score < 30:
            # Low engagement - wait longer
            optimal_time = self.created_at + timedelta(hours=4)
        
        # Customer history adjustments
        if hasattr(self, 'customer') and self.customer:
            if self.customer.average_time_to_purchase:
                # Adjust based on customer's historical behavior
                avg_time = self.customer.average_time_to_purchase
                optimal_time = self.created_at + timedelta(hours=avg_time)
        
        return optimal_time
    
    def determine_behavioral_segments(self) -> List[str]:
        """Determine behavioral segments for this cart session"""
        segments = []
        
        # Engagement-based segments
        engagement_score = self.engagement_metrics.get('engagement_score', 0)
        if engagement_score > 70:
            segments.append('highly_engaged')
        elif engagement_score < 30:
            segments.append('low_engagement')
        
        # Value-based segments
        if self.total_amount:
            if self.total_amount > 200:
                segments.append('high_value_shopper')
            elif self.total_amount < 30:
                segments.append('budget_conscious')
        
        # Behavior pattern segments
        interaction_types = self.engagement_metrics.get('interaction_types', {})
        
        if interaction_types.get('price_comparison', 0) > 2:
            segments.append('price_conscious')
        
        if interaction_types.get('view_details', 0) > 5:
            segments.append('detail_oriented')
        
        if interaction_types.get('add_item', 0) > interaction_types.get('remove_item', 0) * 2:
            segments.append('decisive_buyer')
        
        # Time-based segments
        session_duration = self.engagement_metrics.get('session_duration_seconds', 0)
        if session_duration > 1800:  # 30 minutes
            segments.append('thorough_researcher')
        elif session_duration < 300:  # 5 minutes
            segments.append('quick_buyer')
        
        return segments
    
    def generate_recommendations(self):
        """Generate AI-powered product recommendations"""
        try:
            recommendations = []
            
            # Cross-sell recommendations based on current cart items
            cart_products = [item.product for item in self.items.all()]
            cross_sell_recs = self.get_cross_sell_recommendations(cart_products)
            recommendations.extend(cross_sell_recs)
            
            # Upsell recommendations
            upsell_recs = self.get_upsell_recommendations(cart_products)
            recommendations.extend(upsell_recs)
            
            # Personalized recommendations based on customer history
            if hasattr(self, 'customer') and self.customer:
                personal_recs = self.get_personalized_recommendations()
                recommendations.extend(personal_recs)
            
            # Bundle suggestions
            bundle_recs = self.get_bundle_recommendations(cart_products)
            self.bundle_suggestions = bundle_recs
            
            # Store recommendations
            self.ai_recommendations = recommendations[:10]  # Top 10 recommendations
            self.upsell_opportunities = upsell_recs[:5]
            
            self.save(update_fields=['ai_recommendations', 'bundle_suggestions', 'upsell_opportunities'])
            
        except Exception as e:
            logger.error(f"Failed to generate cart recommendations: {e}")
    
    def get_cross_sell_recommendations(self, cart_products) -> List[Dict]:
        """Get cross-sell recommendations based on cart contents"""
        recommendations = []
        
        # This would typically use collaborative filtering or association rules
        # For now, implement basic category-based recommendations
        
        categories = set()
        for product in cart_products:
            if hasattr(product, 'primary_collection') and product.primary_collection:
                categories.add(product.primary_collection.title)
        
        # Find complementary products in related categories
        # This is a simplified implementation
        for category in categories:
            try:
                from .products import EcommerceProduct
                related_products = EcommerceProduct.objects.filter(
                    tenant=self.tenant,
                    is_published=True,
                    primary_collection__title=category
                ).exclude(
                    id__in=[p.id for p in cart_products]
                )[:3]
                
                for product in related_products:
                    recommendations.append({
                        'product_id': str(product.id),
                        'title': product.title,
                        'price': float(product.price),
                        'reason': f'Customers who bought {category} items also bought',
                        'confidence': 0.7,
                        'type': 'cross_sell'
                    })
                    
            except Exception as e:
                logger.error(f"Error in cross-sell recommendations: {e}")
                continue
        
        return recommendations[:5]  # Top 5 cross-sell recommendations
    
    def get_upsell_recommendations(self, cart_products) -> List[Dict]:
        """Get upsell recommendations for higher-value alternatives"""
        recommendations = []
        
        for product in cart_products:
            try:
                # Find higher-priced alternatives in the same category
                if hasattr(product, 'primary_collection') and product.primary_collection:
                    from .products import EcommerceProduct
                    upsell_products = EcommerceProduct.objects.filter(
                        tenant=self.tenant,
                        is_published=True,
                        primary_collection=product.primary_collection,
                        price__gt=product.price * Decimal('1.2')  # At least 20% more expensive
                    ).exclude(id=product.id)[:2]
                    
                    for upsell in upsell_products:
                        recommendations.append({
                            'product_id': str(upsell.id),
                            'title': upsell.title,
                            'price': float(upsell.price),
                            'original_product_id': str(product.id),
                            'price_difference': float(upsell.price - product.price),
                            'reason': f'Upgrade from {product.title}',
                            'confidence': 0.6,
                            'type': 'upsell'
                        })
                        
            except Exception as e:
                logger.error(f"Error in upsell recommendations: {e}")
                continue
        
        return recommendations[:3]  # Top 3 upsell recommendations
    
    def get_personalized_recommendations(self) -> List[Dict]:
        """Get personalized recommendations based on customer data"""
        recommendations = []
        
        if not (hasattr(self, 'customer') and self.customer):
            return recommendations
        
        try:
            # Use customer's favorite categories
            if self.customer.favorite_categories:
                from .products import EcommerceProduct
                
                for category in self.customer.favorite_categories[:2]:
                    category_products = EcommerceProduct.objects.filter(
                        tenant=self.tenant,
                        is_published=True,
                        primary_collection__title=category
                    ).exclude(
                        id__in=[item.product.id for item in self.items.all()]
                    )[:2]
                    
                    for product in category_products:
                        recommendations.append({
                            'product_id': str(product.id),
                            'title': product.title,
                            'price': float(product.price),
                            'reason': f'Based on your interest in {category}',
                            'confidence': 0.8,
                            'type': 'personalized'
                        })
            
            # Use customer's purchase history
            if hasattr(self.customer, 'orders'):
                # Find frequently bought products not in current cart
                order_products = []
                for order in self.customer.orders.filter(status='DELIVERED')[:10]:
                    for item in order.items.all():
                        order_products.append(item.product.id)
                
                from collections import Counter
                popular_products = Counter(order_products).most_common(5)
                
                from .products import EcommerceProduct
                for product_id, count in popular_products:
                    if not self.items.filter(product_id=product_id).exists():
                        try:
                            product = EcommerceProduct.objects.get(id=product_id, tenant=self.tenant)
                            recommendations.append({
                                'product_id': str(product.id),
                                'title': product.title,
                                'price': float(product.price),
                                'reason': f'You bought this {count} times before',
                                'confidence': 0.9,
                                'type': 'repurchase'
                            })
                        except EcommerceProduct.DoesNotExist:
                            continue
                            
        except Exception as e:
            logger.error(f"Error in personalized recommendations: {e}")
        
        return recommendations[:5]
    
    def get_bundle_recommendations(self, cart_products) -> List[Dict]:
        """Get bundle recommendations for cart items"""
        bundles = []
        
        # Simple bundle logic - products frequently bought together
        if len(cart_products) >= 2:
            bundles.append({
                'id': f"bundle_{self.id}",
                'title': 'Complete Your Look',
                'products': [str(p.id) for p in cart_products],
                'discount_percentage': 10,
                'total_savings': float(sum(p.price for p in cart_products) * Decimal('0.1')),
                'confidence': 0.7
            })
        
        return bundles
    
    def cache_ai_insights(self):
        """Cache AI insights for performance"""
        insights = {
            'conversion_probability': float(self.conversion_probability or 0),
            'abandonment_risk': float(self.abandonment_risk_score or 0),
            'personalization_score': float(self.personalization_score or 0),
            'behavioral_segments': self.behavioral_segments,
            'recommendations_count': len(self.ai_recommendations),
            'last_updated': timezone.now().isoformat()
        }
        
        cache_key = f"cart_ai_insights_{self.id}"
        cache.set(cache_key, insights, timeout=1800)  # Cache for 30 minutes
    
    def get_cart_intelligence_summary(self) -> Dict[str, Any]:
        """Get comprehensive AI intelligence summary for this cart"""
        return {
            'performance_metrics': {
                'conversion_probability': float(self.conversion_probability or 0),
                'abandonment_risk': float(self.abandonment_risk_score or 0),
                'personalization_effectiveness': float(self.personalization_score or 0),
                'engagement_score': self.engagement_metrics.get('engagement_score', 0)
            },
            'predictions': {
                'predicted_final_value': float(self.predicted_final_value or self.total_amount),
                'optimal_checkout_time': self.optimal_checkout_time.isoformat() if self.optimal_checkout_time else None,
                'completion_likelihood': float(self.completion_likelihood or 0)
            },
            'behavioral_insights': {
                'segments': self.behavioral_segments,
                'interaction_patterns': self.engagement_metrics.get('interaction_types', {}),
                'session_duration': self.engagement_metrics.get('session_duration_seconds', 0)
            },
            'recommendations': {
                'ai_recommendations': self.ai_recommendations[:5],
                'upsell_opportunities': self.upsell_opportunities[:3],
                'bundle_suggestions': self.bundle_suggestions[:2]
            },
            'optimization': {
                'dynamic_pricing_applied': self.dynamic_pricing_applied,
                'price_optimizations': self.price_optimizations,
                'discount_recommendations': self.discount_recommendations
            }
        }