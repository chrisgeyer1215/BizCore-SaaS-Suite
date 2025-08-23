from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from decimal import Decimal

from ..entities.product import Product
from ..value_objects.sku import ProductSKU
from ..value_objects.money import Money
from ..value_objects.price import Price
from .base import Repository, QueryRepository


class ProductRepository(Repository):
    """
    Repository interface for Product aggregate
    Defines all data access operations for products
    """
    
    # ============================================================================
    # BASIC CRUD OPERATIONS
    # ============================================================================
    
    @abstractmethod
    def save(self, product: Product) -> Product:
        """Save or update product"""
        pass
    
    @abstractmethod
    def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find product by ID"""
        pass
    
    @abstractmethod
    def find_by_sku(self, sku: ProductSKU) -> Optional[Product]:
        """Find product by SKU"""
        pass
    
    @abstractmethod
    def find_by_url_handle(self, url_handle: str) -> Optional[Product]:
        """Find product by URL handle/slug"""
        pass
    
    @abstractmethod
    def delete(self, product_id: str) -> bool:
        """Delete product"""
        pass
    
    @abstractmethod
    def exists_by_sku(self, sku: ProductSKU) -> bool:
        """Check if product exists by SKU"""
        pass
    
    @abstractmethod
    def exists_by_url_handle(self, url_handle: str) -> bool:
        """Check if URL handle is already taken"""
        pass
    
    # ============================================================================
    # FINDING AND FILTERING
    # ============================================================================
    
    @abstractmethod
    def find_all_active(self, limit: Optional[int] = None, offset: int = 0) -> List[Product]:
        """Find all active products"""
        pass
    
    @abstractmethod
    def find_all_published(self, limit: Optional[int] = None, offset: int = 0) -> List[Product]:
        """Find all published products"""
        pass
    
    @abstractmethod
    def find_by_category(self, category: str, limit: Optional[int] = None) -> List[Product]:
        """Find products by category"""
        pass
    
    @abstractmethod
    def find_by_brand(self, brand: str, limit: Optional[int] = None) -> List[Product]:
        """Find products by brand"""
        pass
    
    @abstractmethod
    def find_by_collection(self, collection_name: str, limit: Optional[int] = None) -> List[Product]:
        """Find products in a collection"""
        pass
    
    @abstractmethod
    def find_by_tags(self, tags: List[str], match_all: bool = False, limit: Optional[int] = None) -> List[Product]:
        """Find products by tags"""
        pass
    
    @abstractmethod
    def find_by_price_range(
        self, 
        min_price: Money, 
        max_price: Money, 
        limit: Optional[int] = None
    ) -> List[Product]:
        """Find products within price range"""
        pass
    
    @abstractmethod
    def find_featured(self, limit: Optional[int] = None) -> List[Product]:
        """Find featured products"""
        pass
    
    @abstractmethod
    def find_new_arrivals(self, days: int = 30, limit: Optional[int] = None) -> List[Product]:
        """Find new arrivals within specified days"""
        pass
    
    @abstractmethod
    def find_best_sellers(self, limit: Optional[int] = None) -> List[Product]:
        """Find best selling products"""
        pass
    
    @abstractmethod
    def find_on_sale(self, limit: Optional[int] = None) -> List[Product]:
        """Find products on sale (with compare_at_price)"""
        pass
    
    # ============================================================================
    # SEARCH OPERATIONS
    # ============================================================================
    
    @abstractmethod
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Product], int]:
        """
        Full-text search products
        Returns (products, total_count)
        """
        pass
    
    @abstractmethod
    def search_by_keywords(self, keywords: List[str], limit: Optional[int] = None) -> List[Product]:
        """Search products by AI keywords"""
        pass
    
    @abstractmethod
    def find_similar_products(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find similar products based on attributes"""
        pass
    
    # ============================================================================
    # AI-POWERED QUERIES
    # ============================================================================
    
    @abstractmethod
    def find_products_needing_ai_analysis(self, analysis_type: str, limit: int = 100) -> List[Product]:
        """Find products that need AI analysis"""
        pass
    
    @abstractmethod
    def find_products_with_high_churn_risk(self, threshold: float = 70.0, limit: Optional[int] = None) -> List[Product]:
        """Find products with high customer churn risk"""
        pass
    
    @abstractmethod
    def find_products_with_low_engagement(self, threshold: float = 0.5, limit: Optional[int] = None) -> List[Product]:
        """Find products with low engagement prediction"""
        pass
    
    @abstractmethod
    def find_products_with_pricing_opportunities(self, min_difference_percentage: float = 10.0) -> List[Product]:
        """Find products where AI recommended price differs significantly from current price"""
        pass
    
    @abstractmethod
    def find_products_with_inventory_alerts(self, alert_types: List[str], limit: Optional[int] = None) -> List[Product]:
        """Find products with specific inventory alert types"""
        pass
    
    @abstractmethod
    def find_underperforming_products(self, criteria: Dict[str, Any], limit: Optional[int] = None) -> List[Product]:
        """Find underperforming products based on AI criteria"""
        pass
    
    @abstractmethod
    def find_trending_products(self, time_period: str = "7d", limit: Optional[int] = None) -> List[Product]:
        """Find trending products based on AI analysis"""
        pass
    
    # ============================================================================
    # RECOMMENDATIONS AND RELATIONSHIPS
    # ============================================================================
    
    @abstractmethod
    def find_cross_sell_candidates(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find cross-sell candidates for a product"""
        pass
    
    @abstractmethod
    def find_upsell_candidates(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find upsell candidates for a product"""
        pass
    
    @abstractmethod
    def find_bundle_compatible_products(self, product_id: str, min_score: float = 0.7) -> List[Product]:
        """Find products compatible for bundling"""
        pass
    
    @abstractmethod
    def find_frequently_bought_together(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find products frequently bought together"""
        pass
    
    @abstractmethod
    def find_recommended_for_customer_segment(self, segment: str, limit: int = 20) -> List[Product]:
        """Find products recommended for specific customer segment"""
        pass
    
    # ============================================================================
    # ANALYTICS AND PERFORMANCE
    # ============================================================================
    
    @abstractmethod
    def find_top_performers(self, metric: str, time_period: str = "30d", limit: int = 10) -> List[Product]:
        """
        Find top performing products by metric
        Metrics: sales_count, revenue, view_count, conversion_rate, etc.
        """
        pass
    
    @abstractmethod
    def find_products_by_performance_tier(self, tier: str, limit: Optional[int] = None) -> List[Product]:
        """Find products by performance tier (A, B, C)"""
        pass
    
    @abstractmethod
    def find_products_with_low_ratings(self, threshold: float = 3.0, limit: Optional[int] = None) -> List[Product]:
        """Find products with ratings below threshold"""
        pass
    
    @abstractmethod
    def find_products_needing_content_improvement(self, quality_threshold: float = 60.0) -> List[Product]:
        """Find products with content quality score below threshold"""
        pass
    
    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================
    
    @abstractmethod
    def save_batch(self, products: List[Product]) -> List[Product]:
        """Save multiple products in batch"""
        pass
    
    @abstractmethod
    def update_prices_batch(self, price_updates: List[Dict[str, Any]]) -> int:
        """Bulk update product prices"""
        pass
    
    @abstractmethod
    def update_inventory_references_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update inventory references"""
        pass
    
    @abstractmethod
    def bulk_publish(self, product_ids: List[str]) -> int:
        """Bulk publish products"""
        pass
    
    @abstractmethod
    def bulk_unpublish(self, product_ids: List[str], reason: str = "") -> int:
        """Bulk unpublish products"""
        pass
    
    # ============================================================================
    # STATISTICS AND AGGREGATIONS
    # ============================================================================
    
    @abstractmethod
    def count_all(self) -> int:
        """Count all products"""
        pass
    
    @abstractmethod
    def count_published(self) -> int:
        """Count published products"""
        pass
    
    @abstractmethod
    def count_by_category(self) -> Dict[str, int]:
        """Count products by category"""
        pass
    
    @abstractmethod
    def count_by_brand(self) -> Dict[str, int]:
        """Count products by brand"""
        pass
    
    @abstractmethod
    def get_price_statistics(self) -> Dict[str, Decimal]:
        """Get price statistics (min, max, avg)"""
        pass
    
    @abstractmethod
    def get_ai_health_statistics(self) -> Dict[str, Any]:
        """Get AI health score statistics across all products"""
        pass


class ProductQueryRepository(QueryRepository):
    """
    Specialized query repository for complex product queries
    Optimized for read-heavy operations and analytics
    """
    
    # ============================================================================
    # ADVANCED SEARCH AND FILTERING
    # ============================================================================
    
    @abstractmethod
    def advanced_search(
        self,
        search_criteria: Dict[str, Any],
        facets: Optional[List[str]] = None,
        sort_options: Optional[List[Dict[str, str]]] = None,
        pagination: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Advanced search with faceted navigation
        Returns: {
            'products': List[Product],
            'total_count': int,
            'facets': Dict[str, List[Dict]],
            'applied_filters': Dict[str, Any]
        }
        """
        pass
    
    @abstractmethod
    def find_by_complex_criteria(self, criteria: Dict[str, Any]) -> List[Product]:
        """Find products by complex criteria including AI metrics"""
        pass
    
    @abstractmethod
    def get_product_suggestions(
        self,
        partial_query: str,
        limit: int = 10,
        include_categories: bool = True
    ) -> List[Dict[str, Any]]:
        """Get autocomplete suggestions for product search"""
        pass
    
    # ============================================================================
    # AI-POWERED QUERIES AND INSIGHTS
    # ============================================================================
    
    @abstractmethod
    def get_ai_insights_dashboard(self, time_period: str = "30d") -> Dict[str, Any]:
        """Get comprehensive AI insights for dashboard"""
        pass
    
    @abstractmethod
    def get_performance_analytics(
        self,
        product_ids: Optional[List[str]] = None,
        time_period: str = "30d"
    ) -> Dict[str, Any]:
        """Get detailed performance analytics"""
        pass
    
    @abstractmethod
    def get_customer_intelligence_summary(self) -> Dict[str, Any]:
        """Get customer intelligence summary across all products"""
        pass
    
    @abstractmethod
    def get_pricing_optimization_opportunities(self) -> List[Dict[str, Any]]:
        """Get pricing optimization opportunities based on AI analysis"""
        pass
    
    @abstractmethod
    def get_inventory_intelligence_alerts(self, severity_levels: List[str]) -> List[Dict[str, Any]]:
        """Get inventory intelligence alerts"""
        pass
    
    @abstractmethod
    def get_demand_forecasting_summary(self, horizon_days: int = 30) -> Dict[str, Any]:
        """Get demand forecasting summary"""
        pass
    
    # ============================================================================
    # RECOMMENDATION QUERIES
    # ============================================================================
    
    @abstractmethod
    def get_personalized_recommendations(
        self,
        customer_context: Dict[str, Any],
        recommendation_types: List[str],
        limit: int = 20
    ) -> Dict[str, List[Product]]:
        """Get personalized product recommendations"""
        pass
    
    @abstractmethod
    def get_trending_recommendations(self, categories: Optional[List[str]] = None) -> List[Product]:
        """Get trending product recommendations"""
        pass
    
    @abstractmethod
    def get_seasonal_recommendations(self, season: Optional[str] = None) -> List[Product]:
        """Get seasonal product recommendations"""
        pass
    
    # ============================================================================
    # CATALOG MANAGEMENT QUERIES
    # ============================================================================
    
    @abstractmethod
    def get_catalog_health_report(self) -> Dict[str, Any]:
        """Get comprehensive catalog health report"""
        pass
    
    @abstractmethod
    def get_content_quality_report(self) -> Dict[str, Any]:
        """Get content quality report across all products"""
        pass
    
    @abstractmethod
    def get_category_performance(self, time_period: str = "30d") -> List[Dict[str, Any]]:
        """Get performance metrics by category"""
        pass
    
    @abstractmethod
    def get_brand_performance(self, time_period: str = "30d") -> List[Dict[str, Any]]:
        """Get performance metrics by brand"""
        pass
    
    # ============================================================================
    # EXPORT AND REPORTING
    # ============================================================================
    
    @abstractmethod
    def export_products(
        self,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        format: str = "csv"
    ) -> str:
        """Export products to specified format"""
        pass
    
    @abstractmethod
    def generate_product_report(
        self,
        report_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate various product reports"""
        pass
    
    # ============================================================================
    # REAL-TIME QUERIES
    # ============================================================================
    
    @abstractmethod
    def get_real_time_metrics(self, product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get real-time metrics for specified products"""
        pass
    
    @abstractmethod
    def get_live_inventory_status(self, skus: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get live inventory status for products"""
        pass


class ProductAnalyticsRepository(ABC):
    """
    Repository for product analytics and time-series data
    Specialized for handling performance metrics and AI insights
    """
    
    @abstractmethod
    def save_analytics_snapshot(
        self,
        product_id: str,
        analytics_data: Dict[str, Any],
        timestamp: datetime
    ) -> None:
        """Save analytics snapshot for a product"""
        pass
    
    @abstractmethod
    def get_analytics_history(
        self,
        product_id: str,
        metric_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get analytics history for specific metric"""
        pass
    
    @abstractmethod
    def get_performance_trends(
        self,
        product_ids: List[str],
        metrics: List[str],
        time_period: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get performance trends for multiple products and metrics"""
        pass
    
    @abstractmethod
    def save_ai_analysis_result(
        self,
        product_id: str,
        analysis_type: str,
        results: Dict[str, Any],
        confidence_scores: Dict[str, float]
    ) -> None:
        """Save AI analysis results"""
        pass
    
    @abstractmethod
    def get_latest_ai_analysis(
        self,
        product_id: str,
        analysis_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get latest AI analysis for product"""
        pass
    
    @abstractmethod
    def get_ai_confidence_trends(
        self,
        product_id: str,
        analysis_types: List[str],
        days: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get AI confidence score trends"""
        pass
    
    @abstractmethod
    def aggregate_metrics(
        self,
        metric_name: str,
        aggregation_type: str,  # sum, avg, min, max
        time_period: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Aggregate metrics across products"""
        pass


class ProductCacheRepository(ABC):
    """
    Repository for cached product data
    High-performance read operations for frequently accessed data
    """
    
    @abstractmethod
    def cache_product(self, product: Product, ttl: int = 3600) -> None:
        """Cache product data"""
        pass
    
    @abstractmethod
    def get_cached_product(self, product_id: str) -> Optional[Product]:
        """Get product from cache"""
        pass
    
    @abstractmethod
    def invalidate_product_cache(self, product_id: str) -> None:
        """Invalidate product cache"""
        pass
    
    @abstractmethod
    def cache_search_results(
        self,
        search_key: str,
        results: List[Product],
        total_count: int,
        ttl: int = 1800
    ) -> None:
        """Cache search results"""
        pass
    
    @abstractmethod
    def get_cached_search_results(
        self,
        search_key: str
    ) -> Optional[Tuple[List[Product], int]]:
        """Get cached search results"""
        pass
    
    @abstractmethod
    def cache_recommendations(
        self,
        cache_key: str,
        recommendations: List[Product],
        ttl: int = 3600
    ) -> None:
        """Cache product recommendations"""
        pass
    
    @abstractmethod
    def get_cached_recommendations(self, cache_key: str) -> Optional[List[Product]]:
        """Get cached recommendations"""
        pass
    
    @abstractmethod
    def warm_cache(self, strategies: List[str]) -> None:
        """Warm cache with frequently accessed data"""
        pass