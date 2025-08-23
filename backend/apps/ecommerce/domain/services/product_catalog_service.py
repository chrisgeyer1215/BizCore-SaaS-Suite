from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import logging
from datetime import datetime, timedelta

from ..entities.product import Product
from ..value_objects.sku import ProductSKU
from ..value_objects.money import Money
from ..value_objects.price import Price
from ..repositories.product_repository import ProductRepository, ProductQueryRepository
from ..events.product_events import *
from .base import DomainService

logger = logging.getLogger(__name__)


class ProductCatalogService(DomainService):
    """
    Domain service for complex product catalog operations
    Handles multi-product coordination and catalog-level business logic
    """
    
    def __init__(
        self,
        product_repository: ProductRepository,
        query_repository: ProductQueryRepository
    ):
        super().__init__(
            product_repository=product_repository,
            query_repository=query_repository
        )
    
    # ============================================================================
    # CATALOG ORGANIZATION AND MANAGEMENT
    # ============================================================================
    
    def organize_catalog_by_performance(self) -> Dict[str, Any]:
        """Organize entire catalog based on AI performance insights"""
        try:
            logger.info("Starting catalog organization by performance")
            
            # Get all active products
            products = self.product_repository.find_all_published()
            
            if not products:
                return {'message': 'No products found for organization'}
            
            # Categorize products by performance
            performance_tiers = self._categorize_products_by_performance(products)
            
            # Apply performance-based strategies
            organization_results = {
                'total_products_analyzed': len(products),
                'performance_tiers': {},
                'actions_taken': []
            }
            
            for tier, tier_products in performance_tiers.items():
                tier_results = self._apply_tier_strategies(tier, tier_products)
                organization_results['performance_tiers'][tier] = {
                    'product_count': len(tier_products),
                    'strategies_applied': tier_results
                }
                organization_results['actions_taken'].extend(tier_results.get('actions', []))
            
            logger.info(f"Catalog organization completed: {len(organization_results['actions_taken'])} actions taken")
            return organization_results
            
        except Exception as e:
            logger.error(f"Catalog organization failed: {e}")
            raise
    
    def optimize_category_distribution(self, category: str) -> Dict[str, Any]:
        """Optimize product distribution within a category"""
        try:
            category_products = self.product_repository.find_by_category(category)
            
            if not category_products:
                return {'message': f'No products found in category: {category}'}
            
            optimization_results = {
                'category': category,
                'products_analyzed': len(category_products),
                'optimizations': []
            }
            
            # Analyze pricing distribution
            pricing_analysis = self._analyze_category_pricing(category_products)
            optimization_results['optimizations'].append({
                'type': 'pricing_distribution',
                'analysis': pricing_analysis,
                'recommendations': self._generate_pricing_recommendations(pricing_analysis)
            })
            
            # Analyze feature gaps
            feature_gaps = self._identify_feature_gaps(category_products)
            optimization_results['optimizations'].append({
                'type': 'feature_gaps',
                'gaps_identified': feature_gaps,
                'recommendations': self._generate_gap_filling_recommendations(feature_gaps)
            })
            
            # Optimize product positioning
            positioning_strategy = self._optimize_product_positioning(category_products)
            optimization_results['optimizations'].append({
                'type': 'positioning',
                'strategy': positioning_strategy
            })
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Category optimization failed for {category}: {e}")
            raise
    
    def create_intelligent_collections(self, strategy: str = "ai_driven") -> List[Dict[str, Any]]:
        """Create intelligent product collections based on AI insights"""
        try:
            all_products = self.product_repository.find_all_published()
            collections_created = []
            
            if strategy == "ai_driven":
                # Customer segment-based collections
                segment_collections = self._create_segment_based_collections(all_products)
                collections_created.extend(segment_collections)
                
                # Performance-based collections
                performance_collections = self._create_performance_collections(all_products)
                collections_created.extend(performance_collections)
                
                # AI similarity collections
                similarity_collections = self._create_similarity_collections(all_products)
                collections_created.extend(similarity_collections)
            
            elif strategy == "seasonal":
                seasonal_collections = self._create_seasonal_collections(all_products)
                collections_created.extend(seasonal_collections)
            
            elif strategy == "behavioral":
                behavioral_collections = self._create_behavioral_collections(all_products)
                collections_created.extend(behavioral_collections)
            
            # Apply collections to products
            for collection in collections_created:
                for product_id in collection['product_ids']:
                    product = self.product_repository.find_by_id(product_id)
                    if product:
                        product.add_to_collection(collection['name'])
                        self.product_repository.save(product)
            
            logger.info(f"Created {len(collections_created)} intelligent collections using {strategy} strategy")
            return collections_created
            
        except Exception as e:
            logger.error(f"Intelligent collection creation failed: {e}")
            raise
    
    # ============================================================================
    # PRODUCT RELATIONSHIP ANALYSIS
    # ============================================================================
    
    def analyze_product_relationships(self, product_id: str) -> Dict[str, Any]:
        """Comprehensive analysis of product relationships"""
        try:
            product = self.product_repository.find_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            relationship_analysis = {
                'product': {
                    'id': product.id,
                    'sku': str(product.sku),
                    'title': product.title
                },
                'relationships': {}
            }
            
            # Cross-sell analysis
            cross_sell_products = self.product_repository.find_cross_sell_candidates(product_id, limit=20)
            relationship_analysis['relationships']['cross_sell'] = {
                'candidates': len(cross_sell_products),
                'products': [self._product_summary(p) for p in cross_sell_products[:10]],
                'ai_confidence': float(product.ai_features.cross_sell_potential)
            }
            
            # Upsell analysis
            upsell_products = self.product_repository.find_upsell_candidates(product_id, limit=20)
            relationship_analysis['relationships']['upsell'] = {
                'candidates': len(upsell_products),
                'products': [self._product_summary(p) for p in upsell_products[:10]],
                'opportunities': product.ai_features.upsell_opportunities
            }
            
            # Bundle compatibility
            bundle_candidates = self.product_repository.find_bundle_compatible_products(
                product_id, 
                min_score=0.6
            )
            relationship_analysis['relationships']['bundles'] = {
                'compatible_products': len(bundle_candidates),
                'products': [self._product_summary(p) for p in bundle_candidates[:10]],
                'compatibility_score': float(product.ai_features.bundle_compatibility_score)
            }
            
            # Similarity analysis
            similar_products = self.product_repository.find_similar_products(product_id, limit=15)
            relationship_analysis['relationships']['similar'] = {
                'similar_products': len(similar_products),
                'products': [self._product_summary(p) for p in similar_products[:10]]
            }
            
            # Competitive analysis
            competitive_analysis = self._analyze_competitive_positioning(product)
            relationship_analysis['relationships']['competitive'] = competitive_analysis
            
            return relationship_analysis
            
        except Exception as e:
            logger.error(f"Product relationship analysis failed: {e}")
            raise
    
    def optimize_product_mix(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize product mix based on AI insights and business constraints"""
        try:
            # Get current product portfolio
            all_products = self.product_repository.find_all_published()
            
            mix_optimization = {
                'current_mix': self._analyze_current_mix(all_products),
                'optimization_opportunities': [],
                'recommendations': []
            }
            
            # Analyze performance distribution
            performance_distribution = self._analyze_performance_distribution(all_products)
            mix_optimization['current_mix']['performance_distribution'] = performance_distribution
            
            # Identify mix optimization opportunities
            if performance_distribution['underperformers'] > 0.3:  # More than 30% underperformers
                mix_optimization['optimization_opportunities'].append({
                    'type': 'reduce_underperformers',
                    'impact': 'high',
                    'description': f"{performance_distribution['underperformers']*100:.1f}% of products are underperforming"
                })
            
            # Category balance analysis
            category_balance = self._analyze_category_balance(all_products, constraints)
            mix_optimization['optimization_opportunities'].extend(category_balance['opportunities'])
            
            # Price point analysis
            price_analysis = self._analyze_price_point_coverage(all_products, constraints)
            mix_optimization['optimization_opportunities'].extend(price_analysis['opportunities'])
            
            # Generate specific recommendations
            recommendations = self._generate_mix_recommendations(
                mix_optimization['optimization_opportunities'],
                constraints
            )
            mix_optimization['recommendations'] = recommendations
            
            return mix_optimization
            
        except Exception as e:
            logger.error(f"Product mix optimization failed: {e}")
            raise
    
    # ============================================================================
    # CATALOG QUALITY AND HEALTH
    # ============================================================================
    
    def assess_catalog_health(self) -> Dict[str, Any]:
        """Comprehensive catalog health assessment"""
        try:
            catalog_health = {
                'overall_score': 0.0,
                'health_metrics': {},
                'issues_identified': [],
                'recommendations': []
            }
            
            # Content quality assessment
            content_health = self._assess_content_health()
            catalog_health['health_metrics']['content_quality'] = content_health
            
            # Performance health assessment
            performance_health = self._assess_performance_health()
            catalog_health['health_metrics']['performance'] = performance_health
            
            # AI features health assessment
            ai_health = self._assess_ai_features_health()
            catalog_health['health_metrics']['ai_features'] = ai_health
            
            # Inventory alignment health
            inventory_health = self._assess_inventory_alignment_health()
            catalog_health['health_metrics']['inventory_alignment'] = inventory_health
            
            # Calculate overall health score
            health_scores = [
                content_health['score'],
                performance_health['score'],
                ai_health['score'],
                inventory_health['score']
            ]
            catalog_health['overall_score'] = sum(health_scores) / len(health_scores)
            
            # Identify critical issues
            catalog_health['issues_identified'] = self._identify_critical_issues(catalog_health['health_metrics'])
            
            # Generate health improvement recommendations
            catalog_health['recommendations'] = self._generate_health_recommendations(
                catalog_health['health_metrics'],
                catalog_health['issues_identified']
            )
            
            logger.info(f"Catalog health assessment completed. Overall score: {catalog_health['overall_score']:.1f}")
            return catalog_health
            
        except Exception as e:
            logger.error(f"Catalog health assessment failed: {e}")
            raise
    
    def identify_catalog_gaps(self, market_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Identify gaps in product catalog using AI analysis"""
        try:
            gap_analysis = {
                'gaps_identified': [],
                'market_opportunities': [],
                'competitive_gaps': [],
                'customer_demand_gaps': []
            }
            
            # Analyze current catalog coverage
            current_coverage = self._analyze_catalog_coverage()
            
            # Price point gaps
            price_gaps = self._identify_price_point_gaps()
            gap_analysis['gaps_identified'].extend(price_gaps)
            
            # Feature gaps analysis
            feature_gaps = self._identify_comprehensive_feature_gaps()
            gap_analysis['gaps_identified'].extend(feature_gaps)
            
            # Customer segment gaps
            segment_gaps = self._identify_customer_segment_gaps()
            gap_analysis['customer_demand_gaps'] = segment_gaps
            
            # Market opportunity gaps (if market analysis provided)
            if market_analysis:
                market_gaps = self._identify_market_opportunity_gaps(market_analysis)
                gap_analysis['market_opportunities'] = market_gaps
            
            # Competitive gaps analysis
            competitive_gaps = self._identify_competitive_gaps()
            gap_analysis['competitive_gaps'] = competitive_gaps
            
            # Prioritize gaps by potential impact
            gap_analysis['prioritized_recommendations'] = self._prioritize_gap_recommendations(gap_analysis)
            
            return gap_analysis
            
        except Exception as e:
            logger.error(f"Catalog gap identification failed: {e}")
            raise
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _categorize_products_by_performance(self, products: List[Product]) -> Dict[str, List[Product]]:
        """Categorize products into performance tiers"""
        tiers = {
            'A_tier': [],  # Top performers
            'B_tier': [],  # Good performers
            'C_tier': [],  # Average performers
            'D_tier': []   # Underperformers
        }
        
        for product in products:
            ai_health_score = float(product.get_ai_health_score())
            
            if ai_health_score >= 80:
                tiers['A_tier'].append(product)
            elif ai_health_score >= 60:
                tiers['B_tier'].append(product)
            elif ai_health_score >= 40:
                tiers['C_tier'].append(product)
            else:
                tiers['D_tier'].append(product)
        
        return tiers
    
    def _apply_tier_strategies(self, tier: str, products: List[Product]) -> Dict[str, Any]:
        """Apply performance-based strategies to product tier"""
        strategies = {
            'A_tier': self._apply_top_performer_strategies,
            'B_tier': self._apply_good_performer_strategies,
            'C_tier': self._apply_average_performer_strategies,
            'D_tier': self._apply_underperformer_strategies
        }
        
        strategy_function = strategies.get(tier)
        if strategy_function:
            return strategy_function(products)
        
        return {'actions': []}
    
    def _apply_top_performer_strategies(self, products: List[Product]) -> Dict[str, Any]:
        """Apply strategies for top-performing products"""
        actions = []
        
        for product in products:
            # Feature top performers more prominently
            if not product.is_featured:
                product.feature()
                actions.append({
                    'product_id': product.id,
                    'action': 'featured',
                    'reason': 'top_performer'
                })
            
            # Consider premium pricing for high performers
            current_price = float(product.price.amount.amount)
            ai_recommended = float(product.ai_features.ai_recommended_price or current_price)
            
            if ai_recommended > current_price * 1.1:  # AI recommends 10%+ increase
                actions.append({
                    'product_id': product.id,
                    'action': 'price_increase_opportunity',
                    'current_price': current_price,
                    'recommended_price': ai_recommended,
                    'reason': 'high_performance_premium_opportunity'
                })
        
        return {
            'strategy': 'maximize_top_performers',
            'actions': actions
        }
    
    def _apply_underperformer_strategies(self, products: List[Product]) -> Dict[str, Any]:
        """Apply strategies for underperforming products"""
        actions = []
        
        for product in products:
            # Unfeature underperformers
            if product.is_featured:
                product.unfeature()
                actions.append({
                    'product_id': product.id,
                    'action': 'unfeatured',
                    'reason': 'underperformer'
                })
            
            # Consider discounting or content improvement
            if float(product.ai_features.content_completeness_score) < 50:
                actions.append({
                    'product_id': product.id,
                    'action': 'content_improvement_needed',
                    'current_score': float(product.ai_features.content_completeness_score),
                    'reason': 'low_content_quality'
                })
            
            # High churn risk products need attention
            if float(product.ai_features.churn_risk_score) > 70:
                actions.append({
                    'product_id': product.id,
                    'action': 'churn_risk_mitigation',
                    'churn_risk': float(product.ai_features.churn_risk_score),
                    'reason': 'high_customer_churn_risk'
                })
        
        return {
            'strategy': 'improve_or_discontinue_underperformers',
            'actions': actions
        }
    
    def _analyze_category_pricing(self, products: List[Product]) -> Dict[str, Any]:
        """Analyze pricing distribution within category"""
        prices = [float(p.price.amount.amount) for p in products]
        
        if not prices:
            return {'error': 'No prices to analyze'}
        
        return {
            'count': len(prices),
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': sum(prices) / len(prices),
            'price_spread': max(prices) - min(prices),
            'price_gaps': self._identify_price_gaps_in_range(prices)
        }
    
    def _identify_price_gaps_in_range(self, prices: List[float]) -> List[Dict[str, float]]:
        """Identify significant gaps in price distribution"""
        sorted_prices = sorted(prices)
        gaps = []
        
        for i in range(len(sorted_prices) - 1):
            gap_size = sorted_prices[i + 1] - sorted_prices[i]
            if gap_size > 50:  # Significant gap threshold
                gaps.append({
                    'lower_bound': sorted_prices[i],
                    'upper_bound': sorted_prices[i + 1],
                    'gap_size': gap_size
                })
        
        return gaps
    
    def _create_segment_based_collections(self, products: List[Product]) -> List[Dict[str, Any]]:
        """Create collections based on customer segments"""
        segment_collections = []
        segment_products = {}
        
        # Group products by their target customer segments
        for product in products:
            for segment in product.ai_features.customer_segments:
                if segment not in segment_products:
                    segment_products[segment] = []
                segment_products[segment].append(product.id)
        
        # Create collections for segments with enough products
        for segment, product_ids in segment_products.items():
            if len(product_ids) >= 5:  # Minimum collection size
                segment_collections.append({
                    'name': f"For {segment.replace('_', ' ').title()} Customers",
                    'type': 'customer_segment',
                    'segment': segment,
                    'product_ids': product_ids,
                    'ai_generated': True
                })
        
        return segment_collections
    
    def _create_performance_collections(self, products: List[Product]) -> List[Dict[str, Any]]:
        """Create collections based on performance metrics"""
        performance_collections = []
        
        # Best sellers collection
        best_sellers = [p for p in products if p.sales_count > 10]
        if best_sellers:
            performance_collections.append({
                'name': 'Best Sellers',
                'type': 'performance',
                'criteria': 'high_sales',
                'product_ids': [p.id for p in best_sellers[:20]],
                'ai_generated': True
            })
        
        # Trending products (high engagement)
        trending = [p for p in products if float(p.ai_features.engagement_prediction) > 0.7]
        if trending:
            performance_collections.append({
                'name': 'Trending Now',
                'type': 'performance', 
                'criteria': 'high_engagement',
                'product_ids': [p.id for p in trending[:15]],
                'ai_generated': True
            })
        
        # High-value products
        high_value = [p for p in products if float(p.ai_features.customer_lifetime_value_impact) > 500]
        if high_value:
            performance_collections.append({
                'name': 'Premium Collection',
                'type': 'performance',
                'criteria': 'high_clv_impact',
                'product_ids': [p.id for p in high_value[:12]],
                'ai_generated': True
            })
        
        return performance_collections
    
    def _assess_content_health(self) -> Dict[str, Any]:
        """Assess overall content health across catalog"""
        products = self.product_repository.find_all_published()
        
        if not products:
            return {'score': 0, 'issues': ['No published products']}
        
        # Analyze content completeness scores
        completeness_scores = [
            float(p.ai_features.content_completeness_score) 
            for p in products 
            if p.ai_features.content_completeness_score > 0
        ]
        
        # Analyze image quality scores
        image_quality_scores = [
            float(p.ai_features.image_quality_score)
            for p in products
            if p.ai_features.image_quality_score > 0
        ]
        
        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
        avg_image_quality = sum(image_quality_scores) / len(image_quality_scores) if image_quality_scores else 0
        
        # Identify issues
        issues = []
        if avg_completeness < 60:
            issues.append(f"Low average content completeness: {avg_completeness:.1f}%")
        
        if avg_image_quality < 70:
            issues.append(f"Low average image quality: {avg_image_quality:.1f}%")
        
        # Products with missing content
        missing_descriptions = len([p for p in products if not p.description or len(p.description) < 50])
        if missing_descriptions > 0:
            issues.append(f"{missing_descriptions} products with inadequate descriptions")
        
        missing_images = len([p for p in products if not p.featured_image_url])
        if missing_images > 0:
            issues.append(f"{missing_images} products without featured images")
        
        # Calculate overall content health score
        content_score = (avg_completeness + avg_image_quality) / 2
        
        return {
            'score': content_score,
            'avg_content_completeness': avg_completeness,
            'avg_image_quality': avg_image_quality,
            'products_analyzed': len(products),
            'issues': issues
        }
    
    def _assess_ai_features_health(self) -> Dict[str, Any]:
        """Assess AI features health across catalog"""
        products = self.product_repository.find_all_published()
        
        if not products:
            return {'score': 0, 'issues': ['No products to analyze']}
        
        ai_health_metrics = {
            'products_with_ai_analysis': 0,
            'avg_ai_confidence': 0.0,
            'products_with_recommendations': 0,
            'products_with_pricing_intelligence': 0,
            'products_with_demand_forecasting': 0,
            'recent_ai_analysis_coverage': 0
        }
        
        total_confidence = 0.0
        confidence_count = 0
        recent_analysis_cutoff = datetime.utcnow() - timedelta(days=7)
        
        for product in products:
            # Check if product has recent AI analysis
            if product.ai_features.last_ai_analysis and product.ai_features.last_ai_analysis > recent_analysis_cutoff:
                ai_health_metrics['recent_ai_analysis_coverage'] += 1
            
            # Check AI confidence scores
            if product.ai_features.ai_confidence_scores:
                avg_confidence = sum(product.ai_features.ai_confidence_scores.values()) / len(product.ai_features.ai_confidence_scores)
                total_confidence += avg_confidence
                confidence_count += 1
            
            # Check specific AI features
            if product.ai_features.ai_recommended_price:
                ai_health_metrics['products_with_pricing_intelligence'] += 1
            
            if product.ai_features.cross_sell_potential > 0 or product.ai_features.upsell_opportunities:
                ai_health_metrics['products_with_recommendations'] += 1
            
            if product.ai_features.demand_forecast_30d > 0:
                ai_health_metrics['products_with_demand_forecasting'] += 1
        
        # Calculate averages and percentages
        total_products = len(products)
        ai_health_metrics['avg_ai_confidence'] = total_confidence / confidence_count if confidence_count > 0 else 0
        ai_health_metrics['recent_analysis_coverage_percent'] = (ai_health_metrics['recent_ai_analysis_coverage'] / total_products) * 100
        ai_health_metrics['pricing_intelligence_coverage_percent'] = (ai_health_metrics['products_with_pricing_intelligence'] / total_products) * 100
        ai_health_metrics['recommendations_coverage_percent'] = (ai_health_metrics['products_with_recommendations'] / total_products) * 100
        ai_health_metrics['demand_forecasting_coverage_percent'] = (ai_health_metrics['products_with_demand_forecasting'] / total_products) * 100
        
        # Calculate overall AI health score
        coverage_scores = [
            ai_health_metrics['recent_analysis_coverage_percent'],
            ai_health_metrics['pricing_intelligence_coverage_percent'],
            ai_health_metrics['recommendations_coverage_percent'],
            ai_health_metrics['demand_forecasting_coverage_percent']
        ]
        
        avg_coverage = sum(coverage_scores) / len(coverage_scores)
        confidence_factor = ai_health_metrics['avg_ai_confidence'] * 100
        
        ai_score = (avg_coverage * 0.7 + confidence_factor * 0.3)
        
        # Identify issues
        issues = []
        if ai_health_metrics['recent_analysis_coverage_percent'] < 50:
            issues.append(f"Only {ai_health_metrics['recent_analysis_coverage_percent']:.1f}% of products have recent AI analysis")
        
        if ai_health_metrics['avg_ai_confidence'] < 0.7:
            issues.append(f"Low average AI confidence score: {ai_health_metrics['avg_ai_confidence']:.2f}")
        
        return {
            'score': ai_score,
            'metrics': ai_health_metrics,
            'issues': issues
        }
    
    def _product_summary(self, product: Product) -> Dict[str, Any]:
        """Create product summary for relationship analysis"""
        return {
            'id': product.id,
            'sku': str(product.sku),
            'title': product.title,
            'category': product.category,
            'brand': product.brand,
            'price': float(product.price.amount.amount),
            'sales_count': product.sales_count,
            'ai_health_score': float(product.get_ai_health_score())
        }