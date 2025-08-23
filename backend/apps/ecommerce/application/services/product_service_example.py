from typing import List, Optional, Dict, Any

from ..domain.entities.product import Product
from ..domain.value_objects.sku import ProductSKU
from ..domain.repositories.product_repository import (
    ProductRepository,
    ProductQueryRepository,
    ProductAnalyticsRepository
)


class ProductApplicationService:
    """Example of how repositories are used in application services"""
    
    def __init__(
        self,
        product_repository: ProductRepository,
        product_query_repository: ProductQueryRepository,
        analytics_repository: ProductAnalyticsRepository
    ):
        self.product_repository = product_repository
        self.product_query_repository = product_query_repository
        self.analytics_repository = analytics_repository
    
    def create_product(self, product_data: Dict[str, Any]) -> Product:
        """Create a new product"""
        # Check if SKU already exists
        sku = ProductSKU(product_data['sku'])
        if self.product_repository.exists_by_sku(sku):
            raise ValueError(f"Product with SKU {sku} already exists")
        
        # Create product entity
        product = Product(
            sku=sku,
            title=product_data['title'],
            description=product_data['description'],
            category=product_data.get('category', ''),
            brand=product_data.get('brand', '')
        )
        
        # Save to repository
        return self.product_repository.save(product)
    
    def get_product_by_sku(self, sku_value: str) -> Optional[Product]:
        """Get product by SKU"""
        sku = ProductSKU(sku_value)
        return self.product_repository.find_by_sku(sku)
    
    def search_products(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Search products with faceted navigation"""
        offset = (page - 1) * per_page
        
        # Use specialized query repository for complex search
        return self.product_query_repository.advanced_search(
            search_criteria={'query': query, 'filters': filters or {}},
            facets=['category', 'brand', 'price_range'],
            pagination={'limit': per_page, 'offset': offset}
        )
    
    def get_ai_optimization_candidates(self) -> List[Product]:
        """Get products that need AI optimization"""
        # Find products needing pricing optimization
        pricing_candidates = self.product_repository.find_products_with_pricing_opportunities(
            min_difference_percentage=15.0
        )
        
        # Find products with low engagement
        engagement_candidates = self.product_repository.find_products_with_low_engagement(
            threshold=0.4
        )
        
        # Combine and deduplicate
        all_candidates = pricing_candidates + engagement_candidates
        seen_ids = set()
        unique_candidates = []
        
        for product in all_candidates:
            if product.id not in seen_ids:
                seen_ids.add(product.id)
                unique_candidates.append(product)
        
        return unique_candidates
    
    def get_performance_dashboard(self, time_period: str = "30d") -> Dict[str, Any]:
        """Get performance dashboard data"""
        return self.product_query_repository.get_ai_insights_dashboard(time_period)
    
    def run_ai_analysis_and_save_results(self, product_id: str) -> Dict[str, Any]:
        """Run AI analysis and save results"""
        product = self.product_repository.find_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Run comprehensive AI analysis
        analysis_results = product.run_comprehensive_ai_analysis()
        
        # Save updated product
        self.product_repository.save(product)
        
        # Save analysis results to analytics repository
        self.analytics_repository.save_ai_analysis_result(
            product_id=product_id,
            analysis_type="comprehensive",
            results=analysis_results,
            confidence_scores=product.ai_features.ai_confidence_scores or {}
        )
        
        return analysis_results