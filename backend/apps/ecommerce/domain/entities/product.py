from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
from dataclasses import dataclass
from django.utils import timezone

from .base import AggregateRoot
from ..value_objects.sku import ProductSKU
from ..value_objects.money import Money
from ..value_objects.price import Price
from ..events.product_events import (
    ProductCreatedEvent,
    ProductPriceUpdatedEvent,
    ProductAnalyticsUpdatedEvent,
    ProductAIAnalysisCompletedEvent,
    ProductRecommendationUpdatedEvent,
    ProductInventoryAlertEvent
)

logger = logging.getLogger(__name__)


@dataclass
class AIFeatureState:
    """Encapsulates all AI-powered features state"""
    
    # AI Content Generation
    ai_generated_description: str = ""
    ai_suggested_tags: List[str] = None
    ai_seo_suggestions: Dict[str, Any] = None
    ai_content_quality_score: Decimal = Decimal('0')
    
    # Intelligent Pricing and Revenue Optimization
    ai_recommended_price: Optional[Decimal] = None
    dynamic_pricing_enabled: bool = False
    price_elasticity_score: Decimal = Decimal('0')
    competitive_price_analysis: Dict[str, Any] = None
    revenue_optimization_score: Decimal = Decimal('0')
    
    # AI-Powered Demand Forecasting
    demand_forecast_30d: int = 0
    demand_forecast_90d: int = 0
    seasonal_demand_pattern: Dict[str, Any] = None
    trend_analysis: Dict[str, Any] = None
    demand_volatility_score: Decimal = Decimal('0')
    
    # Intelligent Customer Insights and Personalization
    customer_segments: List[str] = None
    person None
    behavioral_analytics: Dict[str, Any] = None
    customer_lifetime_value_impact: Decimal = Decimal('0')
    
    # AI-Powered Product Recommendations
    cross_sell_potential: Decimal = Decimal('0')
    upsell_opportunities: List[Dict] = None
    bundle_compatibility_score: Decimal = Decimal('0')
    
    # Intelligent Search and Discoverability
    search_relevance_score: Decimal = Decimal('0')
    ai_keywords: List[str] = None
    search_performance_metrics: Dict[str, Any] = None
    discoverability_score: Decimal = Decimal('0')
    
    # Advanced Analytics and Performance Intelligence
    conversion_optimization_score: Decimal = Decimal('0')
    bounce_rate_prediction: Decimal = Decimal('0')
    engagement_prediction: Decimal = Decimal('0')
    churn_risk_score: Decimal = Decimal('0')
    
    # AI Quality and Content Analysis
    image_quality_score: Decimal = Decimal('0')
    content_completeness_score: Decimal = Decimal('0')
    ai_quality_recommendations: List[Dict] = None
    content_optimization_suggestions: List[Dict] = None
    
    # Intelligent Inventory and Supply Chain
    reorder_point_ai: Optional[int] = None
    stockout_risk_score: Decimal = Decimal('0')
    inventory_turnover_prediction: Decimal = Decimal('0')
    supply_chain_risk_analysis: Dict[str, Any] = None
    
    # Real-time AI Insights
    real_time_performance: Dict[str, Any] = None
    ai_alerts: List[Dict] = None
    automated_optimizations: Dict[str, Any] = None
    ml_model_predictions: Dict[str, Any] = None
    
    # AI Learning and Adaptation
    learning None
    model_performance_metrics: Dict[str, Any] = None
    ai_confidence_scores: Dict[str, Any] = None
    last_ai_analysis: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize default values"""
        if self.ai_suggested_tags is None:
            self.ai_suggested_tags = []
        if self.ai_seo_suggestions is None:
            self.ai_seo_suggestions = {}
        if self.competitive_price_analysis is None:
            self.competitive_price_analysis = {}
        if self.seasonal_demand_pattern is None:
            self.seasonal_demand_pattern = {}
        if self.trend_analysis is None:
            self.trend_analysis = {}
        if self.customer_segments is None:
            self.customer_segments = []
        if self.personalization_data is None:
            self.personalization_data = {}
        if self.behavioral_analytics is None:
            self.behavioral_analytics = {}
        if self.upsell_opportunities is None:
            self.upsell_opportunities = []
        if self.ai_keywords is None:
            self.ai_keywords = []
        if self.search_performance_metrics is None:
            self.search_performance_metrics = {}
        if self.ai_quality_recommendations is None:
            self.ai_quality_recommendations = []
        if self.content_optimization_suggestions is None:
            self.content_optimization_suggestions = []
        if self.supply_chain_risk_analysis is None:
            self.supply_chain_risk_analysis = {}
        if self.real_time_performance is None:
            self.real_time_performance = {}
        if self.ai_alerts is None:
            self.ai_alerts = []
        if self.automated_optimizations is None:
            self.automated_optimizations = {}
        if self.ml_model_predictions is None:
            self.ml_model_predictions = {}
        if self.learning_data is None:
            self.learning_data = {}
        if self.model_performance_metrics is None:
            self.model_performance_metrics = {}
        if self.ai_confidence_scores is None:
            self.ai_confidence_scores = {}


class Product(AggregateRoot):
    """
    AI-Powered Product Domain Entity
    Preserves all your existing AI features while providing clean domain boundaries
    """
    
    def __init__(
        self,
        sku: ProductSKU,
        title: str,
        description: str,
        category: str = "",
        brand: str = "",
        price: Optional[Price] = None,
        product_type: str = "PHYSICAL",
        product_id: Optional[str] = None
    ):
        super().__init__(product_id)
        
        # Core product information (from your model)
        self.sku = sku
        self.title = title
        self.description = description
        self.category = category
        self.brand = brand
        self.price = price or Price(Money.zero())
        self.product_type = product_type
        
        # Product status and metadata
        self.is_active = True
        self.is_published = True
        self.is_featured = False
        self.visibility = "public"
        
        # Additional product details
        self.short_description = ""
        self.manufacturer = ""
        self.model_number = ""
        self.barcode = ""
        self.product_code = ""
        
        # Product variants
        self.has_variants = False
        
        # Categorization and collections
        self.collections: List[str] = []
        self.tags: List[str] = []
        
        # Media
        self.featured_image_url: Optional[str] = None
        self.gallery_images: List[str] = []
        self.product_videos: List[str] = []
        
        # Product specifications and attributes (from your model)
        self.specifications: Dict[str, Any] = {}
        self.attributes: Dict[str, Any] = {}
        self.custom_fields: Dict[str, Any] = {}
        
        # Sales and performance data (from your model)
        self.sales_count = 0
        self.view_count = 0
        self.wishlist_count = 0
        self.review_count = 0
        self.average_rating = Decimal('0.00')
        
        # Inventory reference (loose coupling with inventory domain)
        self.inventory_reference = str(self.sku)
        self.track_inventory = True
        self.current_stock_quantity = 0
        
        # Shipping and tax
        self.requires_shipping = product_type == "PHYSICAL"
        self.is_taxable = True
        self.tax_code = ""
        
        # SEO fields
        self.seo_title = ""
        self.seo_description = ""
        self.meta_keywords: List[str] = []
        seo_metadata: Optional[SEOMetadata] = None,
                 url_slug: Optional[URLSlug] = None,
                 **kwargs):
        super().__init__(**kwargs)
        # ... existing initialization
        self._seo_metadata = seo_metadata
        self._url_slug = url_slug or URLSlug(self._generate_slug_from_title(title))
    
    @property
    def seo_metadata(self) -> Optional[SEOMetadata]:
        """Get SEO metadata"""
        return self._seo_metadata
    
    @property
    def url_slug(self) -> URLSlug:
        """Get URL slug"""
        return self._url_slug
    
    def updateadata):
        """Update SEO metadata"""
        self._seo_metadata = seo_metadata
        self._record_event(ProductSEOUpdatedEvent(
            product_id=self.id,
            seo_title=seo_metadata.title,
            seo_description=seo_metadata.description,
            timestamp=timezone.now()
        ))
    
    def update_url_slug(self, new_slug: str):
        """Update URL slug"""
        old_slug = str(self._url_slug)
        self._url_slug = URLSlug(new_slug)
        
        self._record_event(ProductSlugChangedEvent(
            product_id=self.id,
            old_slug=old_slug,
            new_slug=new_slug,
            timestamp=timezone.now()
        ))
    
    def get_absolute_url(self) -> str:
        """Get product absolute URL"""
        return f"/products/{self.url_slug}/"
    
    def _generate_slug_from_title(self, title: str) -> str:
        """Generate URL slug from title"""
        import re
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars
        slug = re.sub(r'[\s_-]+', '-', slug)  # Replace spaces/underscores with hyphens
        slug = slug.strip('-')  # Remove leading/trailing hyphens
        return slug[:100]  # L
        # ============================================================================
        # AI-POWERED FEATURES - Your complete AI arsenal preserved!
        # ============================================================================
        self.ai_features = AIFeatureState()
        
        # Publish creation event
        self.add_domain_event(ProductCreatedEvent(
            aggregate_id=self.id,
            sku=str(self.sku),
            title=self.title,
            category=self.category,
            product_type=self.product_type,
            initial_price=self.price.amount.amount
        ))
    
    # ============================================================================
    # CORE BUSINESS METHODS
    # ============================================================================
    
    def update_basic_info(
        self, 
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None
    ) -> None:
        """Update basic product information"""
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if category is not None:
            self.category = category
        if brand is not None:
            self.brand = brand
        
        self.increment_version()
    
    def update_price(self, new_price: Price, reason: str = "manual_update") -> None:
        """Update product price with event tracking"""
        old_price = self.price
        self.price = new_price
        self.increment_version()
        
        self.add_domain_event(ProductPriceUpdatedEvent(
            aggregate_id=self.id,
            sku=str(self.sku),
            old_price=old_price.amount.amount,
            new_price=new_price.amount.amount,
            currency=new_price.amount.currency,
            reason=reason,
            ai_recommended=reason.startswith("ai_")
        ))
    
    def publish(self) -> None:
        """Publish product for sale"""
        self.is_published = True
        self.is_active = True
        self.increment_version()
    
    def unpublish(self, reason: str = "") -> None:
        """Unpublish product from sale"""
        self.is_published = False
        self.increment_version()
    
    def feature(self) -> None:
        """Mark product as featured"""
        self.is_featured = True
        self.increment_version()
    
    def unfeature(self) -> None:
        """Remove product from featured"""
        self.is_featured = False
        self.increment_version()
    
    def add_to_collection(self, collection_name: str) -> None:
        """Add product to collection"""
        if collection_name not in self.collections:
            self.collections.append(collection_name)
            self.increment_version()
    
    def remove_from_collection(self, collection_name: str) -> None:
        """Remove product from collection"""
        if collection_name in self.collections:
            self.collections.remove(collection_name)
            self.increment_version()
    
    def add_tag(self, tag: str) -> None:
        """Add tag to product"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.increment_version()
    
    def remove_tag(self, tag: str) -> None:
        """Remove tag from product"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.increment_version()
    
    def update_sales_metrics(self, quantity_sold: int = 1) -> None:
        """Update sales count and related metrics"""
        self.sales_count += quantity_sold
        self.increment_version()
    
    def update_view_count(self, views: int = 1) -> None:
        """Update view count"""
        self.view_count += views
        self.increment_version()
    
    def update_rating(self, new_rating: Decimal, review_count: int) -> None:
        """Update average rating and review count"""
        self.average_rating = new_rating
        self.review_count = review_count
        self.increment_version()
    
    # ============================================================================
    # AI-POWERED METHODS - Your existing AI functionality preserved!
    # ============================================================================
    
    def generate_ai_content(self, content_type: str = 'description') -> Dict[str, Any]:
        """AI-powered content generation (your existing method enhanced)"""
        try:
            logger.info(f"Generating AI content for product {self.id}, type: {content_type}")
            
            # Your existing AI content generation logic here
            ai_content = self._execute_ai_content_generation(content_type)
            
            # Update AI features state
            if content_type == 'description':
                self.ai_features.ai_generated_description = ai_content.get('description', '')
                self.ai_features.ai_suggested_tags = ai_content.get('tags', [])
                self.ai_features.ai_content_quality_score = Decimal(str(ai_content.get('quality_score', 0)))
            
            if content_type == 'seo':
                self.ai_features.ai_seo_suggestions = ai_content.get('seo_suggestions', {})
            
            self.increment_version()
            
            return ai_content
            
        except Exception as e:
            logger.error(f"AI content generation failed for product {self.id}: {e}")
            return {'error': str(e)}
    
    def analyze_pricing_intelligence(self) -> Dict[str, Any]:
        """AI-powered pricing analysis (your existing method preserved)"""
        try:
            logger.info(f"Running pricing intelligence analysis for product {self.id}")
            
            # Your existing pricing intelligence logic
            pricing_analysis = self._execute_pricing_intelligence_analysis()
            
            # Update AI pricing features
            self.ai_features.ai_recommended_price = pricing_analysis.get('recommended_price')
            self.ai_features.price_elasticity_score = Decimal(str(pricing_analysis.get('elasticity_score', 0)))
            self.ai_features.competitive_price_analysis = pricing_analysis.get('competitive_analysis', {})
            self.ai_features.revenue_optimization_score = Decimal(str(pricing_analysis.get('revenue_score', 0)))
            
            self.increment_version()
            
            # Trigger pricing event if significant change
            if (self.ai_features.ai_recommended_price and 
                self.ai_features.ai_recommended_price != self.price.amount.amount):
                
                self.add_domain_event(ProductPriceUpdatedEvent(
                    aggregate_id=self.id,
                    sku=str(self.sku),
                    old_price=self.price.amount.amount,
                    new_price=self.ai_features.ai_recommended_price,
                    currency=self.price.amount.currency,
                    reason="ai_pricing_analysis",
                    ai_recommended=True
                ))
            
            return pricing_analysis
            
        except Exception as e:
            logger.error(f"Pricing intelligence analysis failed: {e}")
            return {'error': str(e)}
    
    def forecast_demand_ai(self, days: int = 30) -> Dict[str, Any]:
        """AI-powered demand forecasting (your existing method)"""
        try:
            logger.info(f"Running demand forecasting for product {self.id}, {days} days")
            
            # Your existing demand forecasting logic
            demand_forecast = self._execute_demand_forecasting(days)
            
            # Update demand forecasting features
            if days == 30:
                self.ai_features.demand_forecast_30d = demand_forecast.get('predicted_demand', 0)
            elif days == 90:
                self.ai_features.demand_forecast_90d = demand_forecast.get('predicted_demand', 0)
            
            self.ai_features.seasonal_demand_pattern = demand_forecast.get('seasonal_patterns', {})
            self.ai_features.trend_analysis = demand_forecast.get('trend_analysis', {})
            self.ai_features.demand_volatility_score = Decimal(str(demand_forecast.get('volatility_score', 0)))
            
            self.increment_version()
            
            return demand_forecast
            
        except Exception as e:
            logger.error(f"Demand forecasting failed: {e}")
            return {'error': str(e)}
    
    def analyze_customer_intelligence(self) -> Dict[str, Any]:
        """AI-powered customer behavior analysis (your existing method)"""
        try:
            logger.info(f"Running customer intelligence analysis for product {self.id}")
            
            # Your existing customer intelligence logic
            customer_analysis = self._execute_customer_intelligence_analysis()
            
            # Update customer intelligence features
            self.ai_features.customer_segments = customer_analysis.get('segments', [])
            self.ai_features.behavioral_analytics = customer_analysis.get('behavioral_data', {})
            self.ai_features.personalization_data = customer_analysis.get('personalization_insights', {})
            self.ai_features.customer_lifetime_value_impact = Decimal(str(customer_analysis.get('clv_impact', 0)))
            
            self.increment_version()
            
            return customer_analysis
            
        except Exception as e:
            logger.error(f"Customer intelligence analysis failed: {e}")
            return {'error': str(e)}
    
    def generate_ai_recommendations(self) -> Dict[str, Any]:
        """AI-powered product recommendation generation (your existing method)"""
        try:
            logger.info(f"Generating AI recommendations for product {self.id}")
            
            # Your existing recommendation generation logic
            recommendations = self._execute_recommendation_generation()
            
            # Update recommendation features
            self.ai_features.cross_sell_potential = Decimal(str(recommendations.get('cross_sell_score', 0)))
            self.ai_features.upsell_opportunities = recommendations.get('upsell_opportunities', [])
            self.ai_features.bundle_compatibility_score = Decimal(str(recommendations.get('bundle_score', 0)))
            
            self.increment_version()
            
            # Publish recommendation event
            self.add_domain_event(ProductRecommendationUpdatedEvent(
                aggregate_id=self.id,
                sku=str(self.sku),
                recommendation_count=len(recommendations.get('related_products', [])),
                cross_sell_score=float(self.ai_features.cross_sell_potential),
                upsell_count=len(self.ai_features.upsell_opportunities)
            ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"AI recommendation generation failed: {e}")
            return {'error': str(e)}
    
    def optimize_search_intelligence(self) -> Dict[str, Any]:
        """AI-powered search optimization (your existing method)"""
        try:
            logger.info(f"Running search optimization for product {self.id}")
            
            # Your existing search optimization logic
            search_optimization = self._execute_search_optimization()
            
            # Update search features
            self.ai_features.ai_keywords = search_optimization.get('keywords', [])
            self.ai_features.search_performance_metrics = search_optimization.get('performance_metrics', {})
            self.ai_features.search_relevance_score = Decimal(str(search_optimization.get('relevance_score', 0)))
            self.ai_features.discoverability_score = Decimal(str(search_optimization.get('discoverability_score', 0)))
            
            self.increment_version()
            
            return search_optimization
            
        except Exception as e:
            logger.error(f"Search optimization failed: {e}")
            return {'error': str(e)}
    
    def analyze_performance_intelligence(self) -> Dict[str, Any]:
        """Advanced AI-powered performance analytics (your existing method)"""
        try:
            logger.info(f"Running performance intelligence analysis for product {self.id}")
            
            # Your existing performance analytics logic
            performance_analysis = self._execute_performance_intelligence_analysis()
            
            # Update performance features
            self.ai_features.conversion_optimization_score = Decimal(str(performance_analysis.get('conversion_score', 0)))
            self.ai_features.bounce_rate_prediction = Decimal(str(performance_analysis.get('bounce_rate_prediction', 0)))
            self.ai_features.engagement_prediction = Decimal(str(performance_analysis.get('engagement_prediction', 0)))
            self.ai_features.churn_risk_score = Decimal(str(performance_analysis.get('churn_risk_score', 0)))
            
            self.increment_version()
            
            return performance_analysis
            
        except Exception as e:
            logger.error(f"Performance intelligence analysis failed: {e}")
            return {'error': str(e)}
    
    def assess_content_quality_ai(self) -> Dict[str, Any]:
        """AI-powered content quality assessment (your existing method)"""
        try:
            logger.info(f"Assessing content quality for product {self.id}")
            
            # Your existing content quality assessment logic
            quality_assessment = self._execute_content_quality_assessment()
            
            # Update quality features
            self.ai_features.image_quality_score = Decimal(str(quality_assessment.get('image_quality_score', 0)))
            self.ai_features.content_completeness_score = Decimal(str(quality_assessment.get('completeness_score', 0)))
            self.ai_features.ai_quality_recommendations = quality_assessment.get('quality_recommendations', [])
            self.ai_features.content_optimization_suggestions = quality_assessment.get('optimization_suggestions', [])
            
            self.increment_version()
            
            return quality_assessment
            
        except Exception as e:
            logger.error(f"Content quality assessment failed: {e}")
            return {'error': str(e)}
    
    def intelligent_inventory_analysis(self) -> Dict[str, Any]:
        """AI-powered inventory and supply chain analysis (your existing method)"""
        try:
            logger.info(f"Running inventory intelligence analysis for product {self.id}")
            
            # Your existing inventory intelligence logic
            inventory_analysis = self._execute_inventory_intelligence_analysis()
            
            # Update inventory intelligence features
            self.ai_features.reorder_point_ai = inventory_analysis.get('ai_reorder_point')
            self.ai_features.stockout_risk_score = Decimal(str(inventory_analysis.get('stockout_risk_score', 0)))
            self.ai_features.inventory_turnover_prediction = Decimal(str(inventory_analysis.get('turnover_prediction', 0)))
            self.ai_features.supply_chain_risk_analysis = inventory_analysis.get('supply_chain_risks', {})
            
            self.increment_version()
            
            # Publish inventory alert if needed
            if self.ai_features.stockout_risk_score > 70:
                self.add_domain_event(ProductInventoryAlertEvent(
                    aggregate_id=self.id,
                    sku=str(self.sku),
                    alert_type="HIGH_STOCKOUT_RISK",
                    risk_score=float(self.ai_features.stockout_risk_score),
                    recommended_reorder_quantity=inventory_analysis.get('recommended_reorder_quantity', 0)
                ))
            
            return inventory_analysis
            
        except Exception as e:
            logger.error(f"Inventory intelligence analysis failed: {e}")
            return {'error': str(e)}
    
    def run_comprehensive_ai_analysis(self) -> Dict[str, Any]:
        """
        Execute comprehensive AI analysis across all product dimensions 
        (your existing master method enhanced)
        """
        try:
            logger.info(f"Starting comprehensive AI analysis for product {self.id}")
            
            analysis_results = {
                'started_at': datetime.utcnow().isoformat(),
                'product_id': self.id,
                'sku': str(self.sku)
            }
            
            # Run all AI analysis methods (your existing logic preserved)
            try:
                analysis_results['content_generation'] = self.generate_ai_content('comprehensive')
            except Exception as e:
                logger.warning(f"Content generation failed: {e}")
                analysis_results['content_generation'] = {'error': str(e)}
            
            try:
                analysis_results['pricing_intelligence'] = self.analyze_pricing_intelligence()
            except Exception as e:
                logger.warning(f"Pricing intelligence failed: {e}")
                analysis_results['pricing_intelligence'] = {'error': str(e)}
            
            try:
                analysis_results['demand_forecasting_30d'] = self.forecast_demand_ai(30)
                analysis_results['demand_forecasting_90d'] = self.forecast_demand_ai(90)
            except Exception as e:
                logger.warning(f"Demand forecasting failed: {e}")
                analysis_results['demand_forecasting_30d'] = {'error': str(e)}
                analysis_results['demand_forecasting_90d'] = {'error': str(e)}
            
            try:
                analysis_results['customer_intelligence'] = self.analyze_customer_intelligence()
            except Exception as e:
                logger.warning(f"Customer intelligence failed: {e}")
                analysis_results['customer_intelligence'] = {'error': str(e)}
            
            try:
                analysis_results['ai_recommendations'] = self.generate_ai_recommendations()
            except Exception as e:
                logger.warning(f"AI recommendations failed: {e}")
                analysis_results['ai_recommendations'] = {'error': str(e)}
            
            try:
                analysis_results['search_optimization'] = self.optimize_search_intelligence()
            except Exception as e:
                logger.warning(f"Search optimization failed: {e}")
                analysis_results['search_optimization'] = {'error': str(e)}
            
            try:
                analysis_results['performance_analytics'] = self.analyze_performance_intelligence()
            except Exception as e:
                logger.warning(f"Performance analytics failed: {e}")
                analysis_results['performance_analytics'] = {'error': str(e)}
            
            try:
                analysis_results['content_quality'] = self.assess_content_quality_ai()
            except Exception as e:
                logger.warning(f"Content quality assessment failed: {e}")
                analysis_results['content_quality'] = {'error': str(e)}
            
            try:
                analysis_results['inventory_intelligence'] = self.intelligent_inventory_analysis()
            except Exception as e:
                logger.warning(f"Inventory intelligence failed: {e}")
                analysis_results['inventory_intelligence'] = {'error': str(e)}
            
            # Update comprehensive AI state
            self.ai_features.last_ai_analysis = datetime.utcnow()
            self.ai_features.real_time_performance = {
                'last_comprehensive_analysis': datetime.utcnow().isoformat(),
                'analysis_modules_successful': len([r for r in analysis_results.values() 
                                                  if isinstance(r, dict) and 'error' not in r]),
                'overall_ai_health_score': self._calculate_overall_ai_score(analysis_results)
            }
            
            # Generate AI alerts based on analysis
            self.ai_features.ai_alerts = self._generate_ai_alerts_from_analysis(analysis_results)
            
            # Update confidence scores
            self.ai_features.ai_confidence_scores = self._calculate_ai_confidence_scores(analysis_results)
            
            analysis_results['completed_at'] = datetime.utcnow().isoformat()
            analysis_results['overall_success'] = 'error' not in str(analysis_results)
            
            self.increment_version()
            
            # Publish comprehensive analysis event
            self.add_domain_event(ProductAIAnalysisCompletedEvent(
                aggregate_id=self.id,
                sku=str(self.sku),
                analysis_type="comprehensive",
                modules_analyzed=list(analysis_results.keys()),
                success_count=len([r for r in analysis_results.values() 
                                 if isinstance(r, dict) and 'error' not in r]),
                ai_confidence_score=self._get_average_confidence_score(),
                alerts_generated=len(self.ai_features.ai_alerts)
            ))
            
            logger.info(f"Comprehensive AI analysis completed for product {self.id}")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Comprehensive AI analysis failed for product {self.id}: {e}")
            return {
                'error': str(e),
                'completed_at': datetime.utcnow().isoformat(),
                'overall_success': False
            }
    
    # ============================================================================
    # BUSINESS RULE METHODS
    # ============================================================================
    
    def can_be_purchased(self) -> bool:
        """Check if product can be purchased"""
        return (
            self.is_active and 
            self.is_published and 
            self.price.amount.is_positive() and
            self._has_sufficient_inventory()
        )
    
    def is_eligible_for_promotion(self, promotion_type: str) -> bool:
        """Check promotion eligibility"""
        if not self.is_active or not self.is_published:
            return False
        
        promotion_rules = {
            'discount': self.price.amount.amount >= Decimal('10'),
            'featured': self.average_rating >= Decimal('4.0'),
            'clearance': self.ai_features.inventory_turnover_prediction < Decimal('2.0'),
            'bundle': self.ai_features.bundle_compatibility_score >= Decimal('0.7')
        }
        
        return promotion_rules.get(promotion_type, False)
    
    def calculate_profit_margin(self, cost_price: Optional[Money] = None) -> Optional[Decimal]:
        """Calculate profit margin"""
        if cost_price and self.price:
            margin = self.price.amount - cost_price
            if self.price.amount.amount > 0:
                return (margin.amount / self.price.amount.amount) * 100
        return None
    
    def get_ai_health_score(self) -> Decimal:
        """Get overall AI health score"""
        if not self.ai_features.last_ai_analysis:
            return Decimal('0')
        
        scores = []
        
        # Content quality
        if self.ai_features.content_completeness_score > 0:
            scores.append(self.ai_features.content_completeness_score)
        
        # Performance predictions
        if self.ai_features.engagement_prediction > 0:
            scores.append(self.ai_features.engagement_prediction * 100)
        
        # Search optimization
        if self.ai_features.search_relevance_score > 0:
            scores.append(self.ai_features.search_relevance_score)
        
        # Conversion optimization
        if self.ai_features.conversion_optimization_score > 0:
            scores.append(self.ai_features.conversion_optimization_score)
        
        if scores:
            return sum(scores) / len(scores)
        return Decimal('50')  # Default neutral score
    
    def get_ai_recommendations_summary(self) -> Dict[str, Any]:
        """Get summary of all AI recommendations"""
        return {
            'pricing_recommendations': {
                'ai_recommended_price': float(self.ai_features.ai_recommended_price or 0),
                'current_price': float(self.price.amount.amount),
                'price_adjustment_needed': (
                    abs(float(self.ai_features.ai_recommended_price or 0) - float(self.price.amount.amount)) > 1.0
                    if self.ai_features.ai_recommended_price else False
                )
            },
            'inventory_recommendations': {
                'ai_reorder_point': self.ai_features.reorder_point_ai,
                'stockout_risk': float(self.ai_features.stockout_risk_score),
                'reorder_needed': self.ai_features.stockout_risk_score > Decimal('50')
            },
            'content_recommendations': self.ai_features.ai_quality_recommendations,
            'optimization_suggestions': self.ai_features.content_optimization_suggestions,
            'marketing_insights': {
                'cross_sell_potential': float(self.ai_features.cross_sell_potential),
                'upsell_opportunities': len(self.ai_features.upsell_opportunities),
                'target_segments': self.ai_features.customer_segments
            }
        }
    
    # ============================================================================
    # INVENTORY COORDINATION METHODS (Domain Events)
    # ============================================================================
    
    def check_inventory_availability(self) -> Dict[str, Any]:
        """Check inventory availability (coordinates with inventory domain via events)"""
        # This triggers inventory domain to provide stock information
        return {
            'sku': str(self.sku),
            'requested_at': datetime.utcnow().isoformat(),
            'current_known_quantity': self.current_stock_quantity,
            'tracks_inventory': self.track_inventory
        }
    
    def update_inventory_reference(self, new_quantity: int, location: str = "default") -> None:
        """Update inventory information from inventory domain"""
        self.current_stock_quantity = new_quantity
        self.increment_version()
        
        # Trigger inventory-related AI analysis if significant change
        if abs(new_quantity - self.current_stock_quantity) > 10:
            # Schedule AI inventory analysis
            pass
    
    def _has_sufficient_inventory(self) -> bool:
        """Check if product has sufficient inventory"""
        if not self.track_inventory:
            return True
        return self.current_stock_quantity > 0
    
    # ============================================================================
    # AI HELPER METHODS (Your existing implementation logic goes here)
    # ============================================================================
    
    def _execute_ai_content_generation(self, content_type: str) -> Dict[str, Any]:
        """Execute AI content generation (implement your existing logic)"""
        # Your existing implementation from generate_ai_content() method
        return {
            'description': f"AI-enhanced description for {self.title}",
            'tags': ['ai-optimized', 'high-quality', 'trending'],
            'quality_score': 85.5,
            'seo_suggestions': {
                'title_optimization': f"SEO-optimized: {self.title}",
                'meta_description': f"Discover {self.title} with premium features"
            }
        }
    
    def _execute_pricing_intelligence_analysis(self) -> Dict[str, Any]:
        """Execute pricing intelligence analysis (implement your existing logic)"""
        # Your existing implementation from analyze_pricing_intelligence() method
        current_price = float(self.price.amount.amount)
        return {
            'recommended_price': Decimal(str(current_price * 1.05)),  # 5% increase example
            'elasticity_score': 0.85,
            'competitive_analysis': {
                'market_position': 'competitive',
                'price_vs_market_avg': 0.95
            },
            'revenue_score': current_price * 1.1
        }
    
    def _execute_demand_forecasting(self, days: int) -> Dict[str, Any]:
        """Execute demand forecasting (implement your existing logic)"""
        # Your existing implementation from forecast_demand_ai() method
        base_demand = max(1, self.sales_count // 10)  # Simplified calculation
        return {
            'predicted_demand': base_demand * days,
            'seasonal_patterns': {
                'current_season_multiplier': 1.1,
                'peak_months': [11, 12, 1]
            },
            'trend_analysis': {
                'direction': 'upward',
                'strength': 'moderate'
            },
            'volatility_score': 25.0
        }
    
    def _execute_customer_intelligence_analysis(self) -> Dict[str, Any]:
        """Execute customer intelligence analysis (implement your existing logic)"""
        # Your existing implementation from analyze_customer_intelligence() method
        return {
            'segments': ['premium_buyers', 'price_conscious', 'frequent_buyers'],
            'behavioral_data': {
                'avg_session_duration': 180,
                'conversion_rate': 0.035,
                'return_rate': 0.12
            },
            'personalization_insights': {
                'recommended_messaging': 'quality-focused',
                'optimal_price_point': float(self.price.amount.amount)
            },
            'clv_impact': float(self.price.amount.amount) * 2.5
        }
    
    def _execute_recommendation_generation(self) -> Dict[str, Any]:
        """Execute recommendation generation (implement your existing logic)"""
        # Your existing implementation from generate_ai_recommendations() method
        return {
            'cross_sell_score': 0.75,
            'upsell_opportunities': [
                {'type': 'premium_version', 'uplift_potential': 0.25},
                {'type': 'accessories', 'uplift_potential': 0.15}
            ],
            'bundle_score': 0.80,
            'related_products': []  # Would contain actual product recommendations
        }
    
    def _execute_search_optimization(self) -> Dict[str, Any]:
        """Execute search optimization (implement your existing logic)"""
        # Your existing implementation from optimize_search_intelligence() method
        keywords = self.title.lower().split() + [self.category.lower(), self.brand.lower()]
        return {
            'keywords': list(set(keywords)),
            'performance_metrics': {
                'search_volume': 1250,
                'click_through_rate': 0.045,
                'conversion_rate': 0.028
            },
            'relevance_score': 75.5,
            'discoverability_score': 68.2
        }
    
    def _execute_performance_intelligence_analysis(self) -> Dict[str, Any]:
        """Execute performance intelligence analysis (implement your existing logic)"""
        # Your existing implementation from analyze_performance_intelligence() method
        return {
            'conversion_score': 65.5,
            'bounce_rate_prediction': 0.35,
            'engagement_prediction': 0.72,
            'churn_risk_score': 0.28
        }
    
    def _execute_content_quality_assessment(self) -> Dict[str, Any]:
        """Execute content quality assessment (implement your existing logic)"""
        # Your existing implementation from assess_content_quality_ai() method
        return {
            'image_quality_score': 80.0 if self.featured_image_url else 20.0,
            'completeness_score': self._calculate_content_completeness(),
            'quality_recommendations': [
                {'type': 'add_more_images', 'priority': 'medium'},
                {'type': 'expand_description', 'priority': 'low'}
            ],
            'optimization_suggestions': [
                {'type': 'seo_optimization', 'impact': 'high'},
                {'type': 'mobile_optimization', 'impact': 'medium'}
            ]
        }
    
    def _execute_inventory_intelligence_analysis(self) -> Dict[str, Any]:
        """Execute inventory intelligence analysis (implement your existing logic)"""
        # Your existing implementation from intelligent_inventory_analysis() method
        daily_sales = max(1, self.sales_count // 30)  # Approximate daily sales
        return {
            'ai_reorder_point': daily_sales * 7 + 10,  # 7 days + safety stock
            'stockout_risk_score': 25.0 if self.current_stock_quantity > 10 else 75.0,
            'turnover_prediction': daily_sales * 365 / max(1, self.current_stock_quantity),
            'supply_chain_risks': {
                'supplier_risk': 'low',
                'lead_time_risk': 'medium'
            },
            'recommended_reorder_quantity': max(50, daily_sales * 30)
        }
    
    def _calculate_content_completeness(self) -> float:
        """Calculate content completeness score"""
        score = 0
        if self.title: score += 20
        if self.description and len(self.description) > 50: score += 25
        if self.featured_image_url: score += 20
        if self.specifications: score += 15
        if self.brand: score += 10
        if self.tags: score += 10
        return score
    
    def _calculate_overall_ai_score(self, analysis_results: Dict) -> float:
        """Calculate overall AI health score from analysis results"""
        successful_analyses = len([r for r in analysis_results.values() 
                                 if isinstance(r, dict) and 'error' not in r])
        total_analyses = len([r for r in analysis_results.values() 
                            if isinstance(r, dict)])
        
        if total_analyses == 0:
            return 0.0
        
        return (successful_analyses / total_analyses) * 100
    
    def _generate_ai_alerts_from_analysis(self, analysis_results: Dict) -> List[Dict]:
        """Generate AI alerts based on analysis results"""
        alerts = []
        
        # Check for high stockout risk
        inventory_analysis = analysis_results.get('inventory_intelligence', {})
        if isinstance(inventory_analysis, dict) and inventory_analysis.get('stockout_risk_score', 0) > 70:
            alerts.append({
                'type': 'HIGH_STOCKOUT_RISK',
                'severity': 'high',
                'message': 'Product has high stockout risk',
                'recommended_action': 'reorder_inventory',
                'created_at': datetime.utcnow().isoformat()
            })
        
        # Check for pricing optimization opportunity
        pricing_analysis = analysis_results.get('pricing_intelligence', {})
        if isinstance(pricing_analysis, dict):
            recommended_price = pricing_analysis.get('recommended_price', 0)
            current_price = float(self.price.amount.amount)
            if abs(float(recommended_price) - current_price) > current_price * 0.1:  # 10% difference
                alerts.append({
                    'type': 'PRICING_OPTIMIZATION',
                    'severity': 'medium',
                    'message': f'AI recommends price adjustment from ${current_price:.2f} to ${float(recommended_price):.2f}',
                    'recommended_action': 'review_pricing',
                    'created_at': datetime.utcnow().isoformat()
                })
        
        # Check for low engagement prediction
        performance_analysis = analysis_results.get('performance_analytics', {})
        if isinstance(performance_analysis, dict) and performance_analysis.get('engagement_prediction', 1) < 0.5:
            alerts.append({
                'type': 'LOW_ENGAGEMENT_PREDICTION',
                'severity': 'medium',
                'message': 'Product predicted to have low customer engagement',
                'recommended_action': 'improve_content_quality',
                'created_at': datetime.utcnow().isoformat()
            })
        
        return alerts
    
    def _calculate_ai_confidence_scores(self, analysis_results: Dict) -> Dict[str, float]:
        """Calculate confidence scores for different AI analyses"""
        confidence_scores = {}
        
        # Base confidence on data completeness and historical accuracy
        base_confidence = 0.75
        
        # Adjust based on data quality
        data_quality_factor = self._calculate_content_completeness() / 100.0
        
        # Adjust based on sales history
        history_factor = min(1.0, self.sales_count / 100.0)  # More sales = higher confidence
        
        overall_confidence = base_confidence * (0.5 + data_quality_factor * 0.3 + history_factor * 0.2)
        
        confidence_scores = {
            'pricing_intelligence': min(0.95, overall_confidence * 1.1),
            'demand_forecasting': min(0.90, overall_confidence * 0.9),
            'customer_intelligence': min(0.85, overall_confidence * 0.95),
            'recommendations': min(0.88, overall_confidence),
            'search_optimization': min(0.92, overall_confidence * 1.05),
            'performance_analytics': min(0.87, overall_confidence * 0.98),
            'content_quality': min(0.90, overall_confidence * 1.0),
            'inventory_intelligence': min(0.83, overall_confidence * 0.85)
        }
        
        return confidence_scores
    
    def _get_average_confidence_score(self) -> float:
        """Get average confidence score across all AI features"""
        if not self.ai_features.ai_confidence_scores:
            return 0.0
        
        scores = list(self.ai_features.ai_confidence_scores.values())
        return sum(scores) / len(scores) if scores else 0.0
    
    # ============================================================================
    # SERIALIZATION AND REPRESENTATION
    # ============================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert product entity to dictionary representation"""
        return {
            'id': self.id,
            'sku': str(self.sku),
            'title': self.title,
            'description': self.description,
            'short_description': self.short_description,
            'category': self.category,
            'brand': self.brand,
            'manufacturer': self.manufacturer,
            'model_number': self.model_number,
            'product_type': self.product_type,
            
            # Status
            'is_active': self.is_active,
            'is_published': self.is_published,
            'is_featured': self.is_featured,
            'visibility': self.visibility,
            
            # Pricing
            'price': {
                'amount': float(self.price.amount.amount),
                'currency': self.price.amount.currency,
                'list_price': float(self.price.list_price.amount) if self.price.list_price else None,
            },
            
            # Collections and categorization
            'collections': self.collections,
            'tags': self.tags,
            
            # Media
            'featured_image_url': self.featured_image_url,
            'gallery_images': self.gallery_images,
            
            # Product details
            'specifications': self.specifications,
            'attributes': self.attributes,
            'custom_fields': self.custom_fields,
            
            # Performance metrics
            'sales_count': self.sales_count,
            'view_count': self.view_count,
            'review_count': self.review_count,
            'average_rating': float(self.average_rating),
            
            # Inventory
            'inventory_reference': self.inventory_reference,
            'track_inventory': self.track_inventory,
            'current_stock_quantity': self.current_stock_quantity,
            
            # AI Features (all your AI fields preserved)
            'ai_features': {
                'content_generation': {
                    'ai_generated_description': self.ai_features.ai_generated_description,
                    'ai_suggested_tags': self.ai_features.ai_suggested_tags,
                    'ai_content_quality_score': float(self.ai_features.ai_content_quality_score),
                    'ai_seo_suggestions': self.ai_features.ai_seo_suggestions,
                },
                'pricing_intelligence': {
                    'ai_recommended_price': float(self.ai_features.ai_recommended_price) if self.ai_features.ai_recommended_price else None,
                    'dynamic_pricing_enabled': self.ai_features.dynamic_pricing_enabled,
                    'price_elasticity_score': float(self.ai_features.price_elasticity_score),
                    'competitive_price_analysis': self.ai_features.competitive_price_analysis,
                    'revenue_optimization_score': float(self.ai_features.revenue_optimization_score),
                },
                'demand_forecasting': {
                    'demand_forecast_30d': self.ai_features.demand_forecast_30d,
                    'demand_forecast_90d': self.ai_features.demand_forecast_90d,
                    'seasonal_demand_pattern': self.ai_features.seasonal_demand_pattern,
                    'trend_analysis': self.ai_features.trend_analysis,
                    'demand_volatility_score': float(self.ai_features.demand_volatility_score),
                },
                'customer_intelligence': {
                    'customer_segments': self.ai_features.customer_segments,
                    'personalization_data': self.ai_features.personalization_data,
                    'behavioral_analytics': self.ai_features.behavioral_analytics,
                    'customer_lifetime_value_impact': float(self.ai_features.customer_lifetime_value_impact),
                },
                'recommendations': {
                    'cross_sell_potential': float(self.ai_features.cross_sell_potential),
                    'upsell_opportunities': self.ai_features.upsell_opportunities,
                    'bundle_compatibility_score': float(self.ai_features.bundle_compatibility_score),
                },
                'search_optimization': {
                    'search_relevance_score': float(self.ai_features.search_relevance_score),
                    'ai_keywords': self.ai_features.ai_keywords,
                    'search_performance_metrics': self.ai_features.search_performance_metrics,
                    'discoverability_score': float(self.ai_features.discoverability_score),
                },
                'performance_analytics': {
                    'conversion_optimization_score': float(self.ai_features.conversion_optimization_score),
                    'bounce_rate_prediction': float(self.ai_features.bounce_rate_prediction),
                    'engagement_prediction': float(self.ai_features.engagement_prediction),
                    'churn_risk_score': float(self.ai_features.churn_risk_score),
                },
                'content_quality': {
                    'image_quality_score': float(self.ai_features.image_quality_score),
                    'content_completeness_score': float(self.ai_features.content_completeness_score),
                    'ai_quality_recommendations': self.ai_features.ai_quality_recommendations,
                    'content_optimization_suggestions': self.ai_features.content_optimization_suggestions,
                },
                'inventory_intelligence': {
                    'reorder_point_ai': self.ai_features.reorder_point_ai,
                    'stockout_risk_score': float(self.ai_features.stockout_risk_score),
                    'inventory_turnover_prediction': float(self.ai_features.inventory_turnover_prediction),
                    'supply_chain_risk_analysis': self.ai_features.supply_chain_risk_analysis,
                },
                'real_time_insights': {
                    'real_time_performance': self.ai_features.real_time_performance,
                    'ai_alerts': self.ai_features.ai_alerts,
                    'automated_optimizations': self.ai_features.automated_optimizations,
                    'ml_model_predictions': self.ai_features.ml_model_predictions,
                },
                'ai_learning': {
                    'learning_data': self.ai_features.learning_data,
                    'model_performance_metrics': self.ai_features.model_performance_metrics,
                    'ai_confidence_scores': self.ai_features.ai_confidence_scores,
                    'last_ai_analysis': self.ai_features.last_ai_analysis.isoformat() if self.ai_features.last_ai_analysis else None,
                }
            },
            
            # Metadata
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version,
            'ai_health_score': float(self.get_ai_health_score())
        }
    
    def __repr__(self) -> str:
        return f"Product(id='{self.id}', sku='{self.sku}', title='{self.title}')"
    
    def __str__(self) -> str:
        return f"{self.title} ({self.sku})"