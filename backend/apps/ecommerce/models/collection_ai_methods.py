# apps/ecommerce/models/collection_ai_methods.py

"""
AI Methods Extension for Intelligent Collections
Advanced machine learning curation, predictive analytics, and automated optimization
"""

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Avg, Count, Sum, Q
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from collections import Counter, defaultdict
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CollectionAIMixin(models.Model):
    """
    AI-powered methods mixin for Intelligent Collections
    """
    
    class Meta:
        abstract = True
    
    def enable_ai_curation(self, model_type='collaborative_filtering'):
        """Enable AI curation for this collection"""
        self.ai_curation_enabled = True
        self.machine_learning_model = model_type
        self.collection_type = self.CollectionType.AI_CURATED
        
        # Initialize AI optimization
        self.initialize_ai_optimization()
        
        self.save(update_fields=[
            'ai_curation_enabled', 'machine_learning_model', 'collection_type'
        ])
    
    def initialize_ai_optimization(self):
        """Initialize AI optimization settings"""
        self.predicted_performance = {
            'expected_conversion_rate': 0.0,
            'predicted_revenue': 0.0,
            'engagement_forecast': 0.0,
            'confidence_score': 0.0
        }
        
        self.conversion_optimization = {
            'enabled': True,
            'target_metrics': ['conversion_rate', 'revenue', 'engagement'],
            'optimization_strategy': 'maximize_revenue',
            'testing_enabled': True
        }
        
        self.performance_metrics = {
            'current_conversion_rate': 0.0,
            'revenue_per_visitor': 0.0,
            'average_time_on_collection': 0.0,
            'bounce_rate': 0.0,
            'product_click_rate': 0.0
        }
    
    def run_ai_curation(self) -> Dict[str, Any]:
        """Run AI curation process to optimize product selection"""
        try:
            if not self.ai_curation_enabled:
                return {'error': 'AI curation not enabled'}
            
            # Analyze current performance
            current_performance = self.analyze_current_performance()
            
            # Get AI-curated product recommendations
            curated_products = self.get_ai_curated_products()
            
            # Apply curation if significant improvement expected
            improvement_threshold = 0.15  # 15% improvement threshold
            if curated_products.get('expected_improvement', 0) > improvement_threshold:
                self.apply_ai_curation(curated_products['products'])
            
            # Update optimization metrics
            self.update_ai_optimization_metrics(curated_products)
            
            return {
                'status': 'success',
                'current_performance': current_performance,
                'curated_products': len(curated_products.get('products', [])),
                'expected_improvement': curated_products.get('expected_improvement', 0),
                'confidence_score': curated_products.get('confidence_score', 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to run AI curation for collection {self.id}: {e}")
            return {'error': str(e)}
    
    def get_ai_curated_products(self) -> Dict[str, Any]:
        """Get AI-curated product recommendations using machine learning"""
        try:
            from .products import EcommerceProduct
            
            # Get all available products for curation
            available_products = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                is_published=True,
                is_active=True,
                stock_quantity__gt=0
            )
            
            # Apply ML model based on type
            if self.machine_learning_model == 'collaborative_filtering':
                return self.collaborative_filtering_curation(available_products)
            elif self.machine_learning_model == 'content_based':
                return self.content_based_curation(available_products)
            elif self.machine_learning_model == 'hybrid':
                return self.hybrid_curation(available_products)
            elif self.machine_learning_model == 'deep_learning':
                return self.deep_learning_curation(available_products)
            else:
                return self.default_curation(available_products)
                
        except Exception as e:
            logger.error(f"Error in AI product curation: {e}")
            return {'products': [], 'confidence_score': 0.0}
    
    def collaborative_filtering_curation(self, available_products) -> Dict[str, Any]:
        """Collaborative filtering based product curation"""
        try:
            # Analyze customer behavior patterns
            customer_interactions = self.analyze_customer_interactions()
            
            # Find similar collections and their successful products
            similar_collections = self.find_similar_collections()
            
            # Score products based on collaborative patterns
            product_scores = {}
            
            for product in available_products:
                score = 0.0
                confidence_factors = []
                
                # Score based on similar customer preferences
                if product.id in customer_interactions.get('highly_viewed', []):
                    score += 30
                    confidence_factors.append('high_customer_interest')
                
                if product.id in customer_interactions.get('frequently_purchased', []):
                    score += 40
                    confidence_factors.append('strong_purchase_history')
                
                # Score based on similar collection performance
                for similar_collection in similar_collections:
                    if self.product_performs_well_in_collection(product, similar_collection):
                        score += 20
                        confidence_factors.append('similar_collection_success')
                
                # Score based on cross-selling patterns
                cross_sell_score = self.calculate_cross_sell_potential(product)
                score += cross_sell_score
                
                if score > 0:
                    product_scores[product.id] = {
                        'score': score,
                        'confidence_factors': confidence_factors,
                        'product': product
                    }\n            \n            # Sort by score and select top products\n            sorted_products = sorted(\n                product_scores.items(), \n                key=lambda x: x[1]['score'], \n                reverse=True\n            )[:50]  # Top 50 products\n            \n            selected_products = [\n                {\n                    'product_id': product_id,\n                    'title': data['product'].title,\n                    'score': data['score'],\n                    'confidence_factors': data['confidence_factors'],\n                    'price': float(data['product'].price)\n                }\n                for product_id, data in sorted_products if data['score'] > 20\n            ]\n            \n            # Calculate expected improvement\n            current_avg_score = self.calculate_current_collection_score()\n            new_avg_score = sum(p['score'] for p in selected_products) / len(selected_products) if selected_products else 0\n            expected_improvement = (new_avg_score - current_avg_score) / current_avg_score if current_avg_score > 0 else 0\n            \n            return {\n                'products': selected_products,\n                'expected_improvement': expected_improvement,\n                'confidence_score': self.calculate_curation_confidence(selected_products),\n                'method': 'collaborative_filtering'\n            }\n            \n        except Exception as e:\n            logger.error(f\"Error in collaborative filtering curation: {e}\")\n            return {'products': [], 'confidence_score': 0.0}
    
    def content_based_curation(self, available_products) -> Dict[str, Any]:
        """Content-based filtering for product curation"""
        try:
            # Analyze current collection characteristics
            collection_profile = self.analyze_collection_content_profile()
            
            product_scores = {}
            
            for product in available_products:
                score = 0.0
                
                # Score based on category alignment
                if hasattr(product, 'primary_collection'):
                    if product.primary_collection and product.primary_collection.title in collection_profile.get('top_categories', []):
                        score += 25
                
                # Score based on price range alignment
                price_range_score = self.calculate_price_alignment_score(product, collection_profile)
                score += price_range_score
                
                # Score based on brand alignment
                if product.brand in collection_profile.get('top_brands', []):
                    score += 15
                
                # Score based on attributes alignment
                attribute_score = self.calculate_attribute_alignment_score(product, collection_profile)
                score += attribute_score
                
                # Score based on quality metrics
                quality_score = self.calculate_product_quality_score(product)
                score += quality_score
                
                if score > 15:  # Minimum threshold
                    product_scores[product.id] = {\n                        'score': score,\n                        'product': product\n                    }\n            \n            # Select top products\n            sorted_products = sorted(\n                product_scores.items(), \n                key=lambda x: x[1]['score'], \n                reverse=True\n            )[:40]\n            \n            selected_products = [\n                {\n                    'product_id': product_id,\n                    'title': data['product'].title,\n                    'score': data['score'],\n                    'price': float(data['product'].price),\n                    'relevance_factors': self.get_relevance_factors(data['product'], collection_profile)\n                }\n                for product_id, data in sorted_products\n            ]\n            \n            return {\n                'products': selected_products,\n                'expected_improvement': 0.12,  # Estimated improvement\n                'confidence_score': 0.75,\n                'method': 'content_based'\n            }\n            \n        except Exception as e:\n            logger.error(f\"Error in content-based curation: {e}\")\n            return {'products': [], 'confidence_score': 0.0}
    
    def analyze_customer_interactions(self) -> Dict[str, Any]:
        \"\"\"Analyze customer interaction patterns for this collection\"\"\"\n        try:\n            # This would integrate with analytics data\n            # For now, return simulated analysis\n            \n            cache_key = f\"customer_interactions_{self.id}\"\n            cached_data = cache.get(cache_key)\n            \n            if cached_data:\n                return cached_data\n            \n            # Simulate customer interaction analysis\n            interactions = {\n                'highly_viewed': [],  # Products with high view rates\n                'frequently_purchased': [],  # Products with high purchase rates\n                'high_engagement': [],  # Products with high engagement\n                'trending_products': [],  # Currently trending products\n                'seasonal_favorites': []  # Seasonally popular products\n            }\n            \n            # Cache for 1 hour\n            cache.set(cache_key, interactions, timeout=3600)\n            \n            return interactions\n            \n        except Exception as e:\n            logger.error(f\"Error analyzing customer interactions: {e}\")\n            return {}\n    \n    def find_similar_collections(self) -> List['IntelligentCollection']:\n        \"\"\"Find collections similar to this one\"\"\"\n        try:\n            # Find collections with similar characteristics\n            similar_collections = IntelligentCollection.objects.filter(\n                tenant=self.tenant,\n                collection_type=self.collection_type\n            ).exclude(id=self.id)\n            \n            # Filter by performance metrics\n            high_performing = similar_collections.filter(\n                ai_optimization_score__gte=70.0\n            )[:10]\n            \n            return list(high_performing)\n            \n        except Exception as e:\n            logger.error(f\"Error finding similar collections: {e}\")\n            return []\n    \n    def product_performs_well_in_collection(self, product, collection) -> bool:\n        \"\"\"Check if product performs well in a similar collection\"\"\"\n        try:\n            # This would check actual performance metrics\n            # For now, return True for demonstration\n            return True\n            \n        except Exception as e:\n            logger.error(f\"Error checking product performance: {e}\")\n            return False\n    \n    def calculate_cross_sell_potential(self, product) -> float:\n        \"\"\"Calculate cross-selling potential score for a product\"\"\"\n        try:\n            # Analyze how often this product is bought with current collection products\n            score = 0.0\n            \n            # This would use actual purchase data analysis\n            # For now, return a base score\n            score = 10.0  # Base cross-sell score\n            \n            return score\n            \n        except Exception as e:\n            logger.error(f\"Error calculating cross-sell potential: {e}\")\n            return 0.0\n    \n    def calculate_current_collection_score(self) -> float:\n        \"\"\"Calculate current collection performance score\"\"\"\n        try:\n            current_products = self.get_products()\n            if not current_products:\n                return 0.0\n            \n            # Calculate based on performance metrics\n            scores = []\n            for product in current_products:\n                # This would use actual performance data\n                score = 50.0  # Base score\n                scores.append(score)\n            \n            return sum(scores) / len(scores) if scores else 0.0\n            \n        except Exception as e:\n            logger.error(f\"Error calculating current collection score: {e}\")\n            return 0.0\n    \n    def calculate_curation_confidence(self, selected_products: List[Dict]) -> float:\n        \"\"\"Calculate confidence score for AI curation\"\"\"\n        if not selected_products:\n            return 0.0\n        \n        # Base confidence factors\n        confidence = 0.6  # Base confidence\n        \n        # Increase confidence based on data quality\n        if len(selected_products) >= 20:\n            confidence += 0.1  # Good selection size\n        \n        # Increase confidence based on score distribution\n        scores = [p['score'] for p in selected_products]\n        if scores:\n            avg_score = sum(scores) / len(scores)\n            if avg_score > 40:\n                confidence += 0.15  # High average scores\n        \n        # Cap confidence at 95%\n        return min(confidence, 0.95)\n    \n    def apply_ai_curation(self, curated_products: List[Dict]):\n        \"\"\"Apply AI curation by updating collection products\"\"\"\n        try:\n            # Clear existing auto-curated products if needed\n            if self.collection_type in ['AI_CURATED', 'PREDICTIVE']:\n                self.clear_ai_curated_products()\n            \n            # Add new AI-curated products\n            for i, product_data in enumerate(curated_products[:30]):  # Top 30 products\n                try:\n                    from .products import EcommerceProduct\n                    product = EcommerceProduct.objects.get(\n                        id=product_data['product_id'],\n                        tenant=self.tenant\n                    )\n                    \n                    # Add product with AI-determined position\n                    self.add_ai_curated_product(\n                        product=product,\n                        position=i + 1,\n                        ai_score=product_data['score'],\n                        confidence_factors=product_data.get('confidence_factors', [])\n                    )\n                    \n                except Exception as e:\n                    logger.error(f\"Error adding curated product {product_data['product_id']}: {e}\")\n                    continue\n            \n            # Update collection metadata\n            self.ai_curated_count = len(curated_products)\n            self.last_ai_optimization = timezone.now()\n            \n            self.save(update_fields=['ai_curated_count', 'last_ai_optimization'])\n            \n        except Exception as e:\n            logger.error(f\"Error applying AI curation: {e}\")\n    \n    def add_ai_curated_product(self, product, position: int, ai_score: float, confidence_factors: List[str]):\n        \"\"\"Add AI-curated product to collection\"\"\"\n        try:\n            from . import IntelligentCollectionProduct\n            \n            collection_product, created = IntelligentCollectionProduct.objects.get_or_create(\n                tenant=self.tenant,\n                collection=self,\n                product=product,\n                defaults={\n                    'position': position,\n                    'is_ai_curated': True,\n                    'ai_curation_score': Decimal(str(ai_score)),\n                    'confidence_factors': confidence_factors\n                }\n            )\n            \n            if not created:\n                # Update existing product\n                collection_product.position = position\n                collection_product.is_ai_curated = True\n                collection_product.ai_curation_score = Decimal(str(ai_score))\n                collection_product.confidence_factors = confidence_factors\n                collection_product.save()\n            \n            return collection_product\n            \n        except Exception as e:\n            logger.error(f\"Error adding AI curated product: {e}\")\n            return None\n    \n    def clear_ai_curated_products(self):\n        \"\"\"Remove existing AI-curated products\"\"\"\n        try:\n            self.collection_products.filter(is_ai_curated=True).delete()\n        except Exception as e:\n            logger.error(f\"Error clearing AI curated products: {e}\")\n    \n    def analyze_collection_performance(self) -> Dict[str, Any]:\n        \"\"\"Comprehensive performance analysis using AI\"\"\"\n        try:\n            performance_data = {\n                'conversion_metrics': self.calculate_conversion_metrics(),\n                'engagement_metrics': self.calculate_engagement_metrics(),\n                'revenue_metrics': self.calculate_revenue_metrics(),\n                'trend_analysis': self.analyze_performance_trends(),\n                'customer_segments': self.analyze_customer_segments(),\n                'product_performance': self.analyze_product_performance(),\n                'optimization_opportunities': self.identify_optimization_opportunities()\n            }\n            \n            # Update cached performance metrics\n            self.performance_metrics = performance_data\n            self.save(update_fields=['performance_metrics'])\n            \n            return performance_data\n            \n        except Exception as e:\n            logger.error(f\"Error analyzing collection performance: {e}\")\n            return {}\n    \n    def generate_ai_recommendations(self) -> List[Dict[str, Any]]:\n        \"\"\"Generate AI-powered recommendations for collection optimization\"\"\"\n        try:\n            recommendations = []\n            \n            # Analyze current performance\n            performance = self.analyze_collection_performance()\n            \n            # Generate recommendations based on AI analysis\n            if performance.get('conversion_metrics', {}).get('rate', 0) < 2.0:\n                recommendations.append({\n                    'type': 'CONVERSION_OPTIMIZATION',\n                    'priority': 'HIGH',\n                    'title': 'Optimize Product Selection for Higher Conversion',\n                    'description': 'AI analysis suggests replacing low-performing products with high-conversion alternatives.',\n                    'expected_impact': 'Increase conversion rate by 25-40%',\n                    'confidence': 0.85,\n                    'actions': [\n                        'Run AI curation to identify better products',\n                        'Remove products with conversion rate < 1%',\n                        'Add trending products in this category'\n                    ]\n                })\n            \n            # Add more AI-generated recommendations\n            pricing_rec = self.generate_pricing_recommendations()\n            if pricing_rec:\n                recommendations.extend(pricing_rec)\n            \n            layout_rec = self.generate_layout_recommendations()\n            if layout_rec:\n                recommendations.extend(layout_rec)\n            \n            # Store recommendations\n            self.ai_recommendations = recommendations\n            self.save(update_fields=['ai_recommendations'])\n            \n            return recommendations\n            \n        except Exception as e:\n            logger.error(f\"Error generating AI recommendations: {e}\")\n            return []\n    \n    def generate_pricing_recommendations(self) -> List[Dict]:\n        \"\"\"Generate AI-powered pricing recommendations\"\"\"\n        recommendations = []\n        \n        try:\n            # Analyze pricing performance\n            products = self.get_products()\n            \n            overpriced_products = []\n            underpriced_products = []\n            \n            for product in products:\n                if hasattr(product, 'ai_optimized_price') and product.ai_optimized_price:\n                    price_diff = product.ai_optimized_price - product.price\n                    if abs(price_diff) > product.price * Decimal('0.05'):  # 5% difference\n                        if price_diff > 0:\n                            underpriced_products.append(product)\n                        else:\n                            overpriced_products.append(product)\n            \n            if overpriced_products or underpriced_products:\n                recommendations.append({\n                    'type': 'PRICING_OPTIMIZATION',\n                    'priority': 'MEDIUM',\n                    'title': 'Optimize Product Pricing',\n                    'description': f'AI suggests adjusting prices for {len(overpriced_products + underpriced_products)} products.',\n                    'expected_impact': 'Increase revenue by 8-15%',\n                    'confidence': 0.78,\n                    'details': {\n                        'overpriced_count': len(overpriced_products),\n                        'underpriced_count': len(underpriced_products)\n                    }\n                })\n            \n        except Exception as e:\n            logger.error(f\"Error generating pricing recommendations: {e}\")\n        \n        return recommendations\n    \n    def predict_collection_performance(self, time_horizon_days: int = 30) -> Dict[str, Any]:\n        \"\"\"Predict collection performance using AI\"\"\"\n        try:\n            current_performance = self.analyze_current_performance()\n            \n            # Simple prediction model (would be enhanced with actual ML)\n            base_metrics = {\n                'views': current_performance.get('daily_views', 100),\n                'conversion_rate': current_performance.get('conversion_rate', 2.5),\n                'revenue': current_performance.get('daily_revenue', 500)\n            }\n            \n            # Apply growth/decline factors based on trends\n            trend_multiplier = 1.0\n            \n            if self.trending_score:\n                if self.trending_score > 80:\n                    trend_multiplier = 1.15  # Growing trend\n                elif self.trending_score < 40:\n                    trend_multiplier = 0.95  # Declining trend\n            \n            # Seasonal adjustments\n            seasonal_multiplier = self.get_seasonal_multiplier()\n            \n            # Predict metrics\n            predictions = {\n                'predicted_views': int(base_metrics['views'] * trend_multiplier * seasonal_multiplier * time_horizon_days),\n                'predicted_conversion_rate': base_metrics['conversion_rate'] * trend_multiplier,\n                'predicted_revenue': base_metrics['revenue'] * trend_multiplier * seasonal_multiplier * time_horizon_days,\n                'confidence_score': self.calculate_prediction_confidence(),\n                'time_horizon_days': time_horizon_days,\n                'factors': {\n                    'trend_impact': trend_multiplier - 1.0,\n                    'seasonal_impact': seasonal_multiplier - 1.0,\n                    'ai_optimization_impact': 0.05 if self.ai_curation_enabled else 0.0\n                }\n            }\n            \n            # Store predictions\n            self.predicted_performance = predictions\n            self.save(update_fields=['predicted_performance'])\n            \n            return predictions\n            \n        except Exception as e:\n            logger.error(f\"Error predicting collection performance: {e}\")\n            return {}\n    \n    def get_seasonal_multiplier(self) -> float:\n        \"\"\"Get seasonal multiplier for predictions\"\"\"\n        current_month = timezone.now().month\n        \n        # Simple seasonal patterns (would be enhanced with historical data)\n        seasonal_patterns = {\n            11: 1.3,  # November (Black Friday)\n            12: 1.4,  # December (Christmas)\n            1: 0.8,   # January (post-holiday)\n            2: 0.9,   # February\n            3: 1.1,   # March (Spring)\n            4: 1.0,   # April\n            5: 1.1,   # May (Mother's Day)\n            6: 1.0,   # June\n            7: 1.0,   # July\n            8: 1.0,   # August\n            9: 1.0,   # September\n            10: 1.0,  # October\n        }\n        \n        return seasonal_patterns.get(current_month, 1.0)\n    \n    def calculate_prediction_confidence(self) -> float:\n        \"\"\"Calculate confidence in performance predictions\"\"\"\n        confidence = 0.5  # Base confidence\n        \n        # Increase confidence based on data availability\n        if self.performance_metrics:\n            confidence += 0.2\n        \n        if self.ai_curation_enabled:\n            confidence += 0.15\n        \n        if self.trending_score:\n            confidence += 0.1\n        \n        # Historical data factor (simulated)\n        confidence += 0.05  # Assume some historical data\n        \n        return min(confidence, 0.95)\n    \n    def optimize_collection_automatically(self) -> Dict[str, Any]:\n        \"\"\"Run automated collection optimization\"\"\"\n        try:\n            optimization_results = {\n                'actions_taken': [],\n                'performance_improvements': {},\n                'timestamp': timezone.now().isoformat()\n            }\n            \n            # Run AI curation if enabled\n            if self.ai_curation_enabled:\n                curation_result = self.run_ai_curation()\n                if curation_result.get('status') == 'success':\n                    optimization_results['actions_taken'].append('ai_curation')\n            \n            # Apply dynamic pricing if enabled\n            if self.auto_pricing_enabled:\n                pricing_result = self.apply_dynamic_pricing()\n                if pricing_result:\n                    optimization_results['actions_taken'].append('dynamic_pricing')\n            \n            # Reorder products if enabled\n            if self.auto_reorder_enabled:\n                reorder_result = self.optimize_product_order()\n                if reorder_result:\n                    optimization_results['actions_taken'].append('product_reordering')\n            \n            # Update optimization score\n            new_score = self.calculate_optimization_score()\n            old_score = self.ai_optimization_score or Decimal('0.0')\n            \n            optimization_results['performance_improvements'] = {\n                'optimization_score_change': float(new_score - old_score),\n                'new_optimization_score': float(new_score)\n            }\n            \n            self.ai_optimization_score = new_score\n            self.last_ai_optimization = timezone.now()\n            self.save(update_fields=['ai_optimization_score', 'last_ai_optimization'])\n            \n            return optimization_results\n            \n        except Exception as e:\n            logger.error(f\"Error in automated optimization: {e}\")\n            return {'error': str(e)}\n    \n    def calculate_optimization_score(self) -> Decimal:\n        \"\"\"Calculate overall optimization effectiveness score\"\"\"\n        score = Decimal('50.0')  # Base score\n        \n        # AI curation impact\n        if self.ai_curation_enabled:\n            score += Decimal('15.0')\n        \n        # Performance metrics impact\n        if self.performance_metrics:\n            conv_rate = self.performance_metrics.get('conversion_rate', 0)\n            if conv_rate > 3.0:\n                score += Decimal('10.0')\n            elif conv_rate > 2.0:\n                score += Decimal('5.0')\n        \n        # Product count optimization\n        if 20 <= self.products_count <= 50:\n            score += Decimal('5.0')  # Optimal product count\n        \n        # Trending factor\n        if self.trending_score and self.trending_score > 70:\n            score += Decimal('10.0')\n        \n        # Recent optimization bonus\n        if self.last_ai_optimization:\n            days_since_opt = (timezone.now() - self.last_ai_optimization).days\n            if days_since_opt <= 7:\n                score += Decimal('5.0')\n        \n        return min(score, Decimal('100.0'))\n    \n    def get_ai_insights_summary(self) -> Dict[str, Any]:\n        \"\"\"Get comprehensive AI insights summary\"\"\"\n        return {\n            'optimization_status': {\n                'ai_curation_enabled': self.ai_curation_enabled,\n                'optimization_score': float(self.ai_optimization_score or 0),\n                'last_optimization': self.last_ai_optimization.isoformat() if self.last_ai_optimization else None,\n                'ml_model': self.machine_learning_model\n            },\n            'performance_predictions': self.predicted_performance,\n            'current_performance': self.performance_metrics,\n            'ai_recommendations': self.ai_recommendations[:5],  # Top 5 recommendations\n            'market_insights': self.market_insights,\n            'customer_segments': self.customer_segments,\n            'optimization_opportunities': len(self.optimization_suggestions)\n        }