from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

from .....domain.entities.product import Product, AIFeatureState
from .....domain.value_objects.sku import ProductSKU
from .....domain.value_objects.money import Money
from .....domain.value_objects.price import Price
from .....models.products import EcommerceProduct

import logging

logger = logging.getLogger(__name__)


class ProductMapper:
    """
    Maps between Django models and Domain entities
    Preserves all your AI features during conversion
    """
    
    def django_model_to_entity(self, django_product: EcommerceProduct) -> Product:
        """Convert Django model to Domain entity"""
        try:
            # Create Money and Price value objects
            money = Money(django_product.price, django_product.currency)
            compare_at_money = Money(django_product.compare_at_price, django_product.currency) if django_product.compare_at_price else None
            price = Price(money, list_price=compare_at_money, cost_price=Money(django_product.cost_price or 0, django_product.currency))
            
            # Create Product entity
            product = Product(
                sku=ProductSKU(django_product.sku),
                title=django_product.title,
                description=django_product.description,
                category=django_product.category or "",
                brand=django_product.brand or "",
                price=price,
                product_type=django_product.product_type,
                product_id=str(django_product.id)
            )
            
            # Map basic fields
            product.short_description = django_product.short_description or ""
            product.manufacturer = django_product.manufacturer or ""
            product.model_number = django_product.model_number or ""
            product.barcode = django_product.barcode or ""
            product.product_code = django_product.product_code or ""
            
            # Map status fields
            product.is_active = django_product.is_active
            product.is_published = django_product.is_published
            product.is_featured = django_product.is_featured
            product.visibility = django_product.visibility
            
            # Map collections and tags
            product.collections = list(django_product.collections.values_list('name', flat=True))
            product.tags = django_product.tags or []
            
            # Map media
            product.featured_image_url = django_product.featured_image.url if django_product.featured_image else None
            product.gallery_images = django_product.gallery_images or []
            product.product_videos = django_product.product_videos or []
            
            # Map specifications and attributes
            product.specifications = django_product.specifications or {}
            product.attributes = django_product.attributes or {}
            product.custom_fields = django_product.custom_fields or {}
            
            # Map performance metrics
            product.sales_count = django_product.sales_count
            product.view_count = django_product.view_count
            product.wishlist_count = django_product.wishlist_count
            product.review_count = django_product.review_count
            product.average_rating = django_product.average_rating
            
            # Map inventory reference
            product.inventory_reference = str(django_product.sku)
            product.track_inventory = django_product.track_quantity
            product.current_stock_quantity = django_product.stock_quantity or 0
            
            # Map shipping and tax
            product.requires_shipping = django_product.requires_shipping
            product.is_taxable = django_product.is_taxable
            product.tax_code = django_product.tax_code or ""
            
            # Map SEO fields
            product.seo_title = django_product.seo_title or ""
            product.seo_description = django_product.seo_description or ""
            product.meta_keywords = django_product.seo_keywords.split(',') if django_product.seo_keywords else []
            
            # ============================================================================
            # MAP ALL AI FEATURES (Your complete AI arsenal!)
            # ============================================================================
            
            ai_features = AIFeatureState()
            
            # AI Content Generation
            ai_features.ai_generated_description = django_product.ai_generated_description or ""
            ai_features.ai_suggested_tags = django_product.ai_suggested_tags or []
            ai_features.ai_seo_suggestions = django_product.ai_seo_suggestions or {}
            ai_features.ai_content_quality_score = django_product.ai_content_quality_score or Decimal('0')
            
            # Intelligent Pricing and Revenue Optimization
            ai_features.ai_recommended_price = django_product.ai_recommended_price
            ai_features.dynamic_pricing_enabled = django_product.dynamic_pricing_enabled
            ai_features.price_elasticity_score = django_product.price_elasticity_score or Decimal('0')
            ai_features.competitive_price_analysis = django_product.competitive_price_analysis or {}
            ai_features.revenue_optimization_score = django_product.revenue_optimization_score or Decimal('0')
            
            # AI-Powered Demand Forecasting
            ai_features.demand_forecast_30d = django_product.demand_forecast_30d
            ai_features.demand_forecast_90d = django_product.demand_forecast_90d
            ai_features.seasonal_demand_pattern = django_product.seasonal_demand_pattern or {}
            ai_features.trend_analysis = django_product.trend_analysis or {}
            ai_features.demand_volatility_score = django_product.demand_volatility_score or Decimal('0')
            
            # Intelligent Customer Insights and Personalization
            ai_features.customer_segments = django_product.customer_segments or []
            ai_features.personalization_data = django_product.personalization_data or {}
            ai_features.behavioral_analytics = django_product.behavioral_analytics or {}
            ai_features.customer_lifetime_value_impact = django_product.customer_lifetime_value_impact or Decimal('0')
            
            # AI-Powered Product Recommendations
            ai_features.cross_sell_potential = django_product.cross_sell_potential or Decimal('0')
            ai_features.upsell_opportunities = django_product.upsell_opportunities or []
            ai_features.bundle_compatibility_score = django_product.bundle_compatibility_score or Decimal('0')
            
            # Intelligent Search and Discoverability
            ai_features.search_relevance_score = django_product.search_relevance_score or Decimal('0')
            ai_features.ai_keywords = django_product.ai_keywords or []
            ai_features.search_performance_metrics = django_product.search_performance_metrics or {}
            ai_features.discoverability_score = django_product.discoverability_score or Decimal('0')
            
            # Advanced Analytics and Performance Intelligence
            ai_features.conversion_optimization_score = django_product.conversion_optimization_score or Decimal('0')
            ai_features.bounce_rate_prediction = django_product.bounce_rate_prediction or Decimal('0')
            ai_features.engagement_prediction = django_product.engagement_prediction or Decimal('0')
            ai_features.churn_risk_score = django_product.churn_risk_score or Decimal('0')
            
            # AI Quality and Content Analysis
            ai_features.image_quality_score = django_product.image_quality_score or Decimal('0')
            ai_features.content_completeness_score = django_product.content_completeness_score or Decimal('0')
            ai_features.ai_quality_recommendations = django_product.ai_quality_recommendations or []
            ai_features.content_optimization_suggestions = django_product.content_optimization_suggestions or []
            
            # Intelligent Inventory and Supply Chain
            ai_features.reorder_point_ai = django_product.reorder_point_ai
            ai_features.stockout_risk_score = django_product.stockout_risk_score or Decimal('0')
            ai_features.inventory_turnover_prediction = django_product.inventory_turnover_prediction or Decimal('0')
            ai_features.supply_chain_risk_analysis = django_product.supply_chain_risk_analysis or {}
            
            # Real-time AI Insights
            ai_features.real_time_performance = django_product.real_time_performance or {}
            ai_features.ai_alerts = django_product.ai_alerts or []
            ai_features.automated_optimizations = django_product.automated_optimizations or {}
            ai_features.ml_model_predictions = django_product.ml_model_predictions or {}
            
            # AI Learning and Adaptation
            ai_features.learning_data = django_product.learning_data or {}
            ai_features.model_performance_metrics = django_product.model_performance_metrics or {}
            ai_features.ai_confidence_scores = django_product.ai_confidence_scores or {}
            ai_features.last_ai_analysis = django_product.last_ai_analysis
            
            # Assign AI features to product
            product.ai_features = ai_features
            
            # Set timestamps and version
            product.created_at = django_product.created_at
            product.updated_at = django_product.updated_at
            product._version = getattr(django_product, 'version', 0)
            
            return product
            
        except Exception as e:
            logger.error(f"Failed to convert Django model to entity: {e}")
            raise
    
    def entity_to_django_model(self, product: Product, tenant) -> EcommerceProduct:
        """Convert Domain entity to new Django model"""
        try:
            django_product = EcommerceProduct(
                tenant=tenant,
                id=product.id if product.id != 'new' else None
            )
            
            return self.update_django_model_from_entity(django_product, product)
            
        except Exception as e:
            logger.error(f"Failed to convert entity to Django model: {e}")
            raise
    
    def update_django_model_from_entity(self, django_product: EcommerceProduct, product: Product) -> EcommerceProduct:
        """Update existing Django model from Domain entity"""
        try:
            # Basic product information
            django_product.sku = str(product.sku)
            django_product.title = product.title
            django_product.description = product.description
            django_product.short_description = product.short_description
            django_product.category = product.category
            django_product.brand = product.brand
            django_product.manufacturer = product.manufacturer
            django_product.model_number = product.model_number
            django_product.barcode = product.barcode
            django_product.product_code = product.product_code
            django_product.product_type = product.product_type
            
            # Pricing information
            django_product.price = product.price.amount.amount
            django_product.currency = product.price.amount.currency
            if product.price.list_price:
                django_product.compare_at_price = product.price.list_price.amount
            if product.price.cost_price:
                django_product.cost_price = product.price.cost_price.amount
            
            # Status fields
            django_product.is_active = product.is_active
            django_product.is_published = product.is_published
            django_product.is_featured = product.is_featured
            django_product.visibility = product.visibility
            
            # Product details
            django_product.tags = product.tags
            django_product.specifications = product.specifications
            django_product.attributes = product.attributes
            django_product.custom_fields = product.custom_fields
            
            # Media
            django_product.gallery_images = product.gallery_images
            django_product.product_videos = product.product_videos
            
            # Performance metrics
            django_product.sales_count = product.sales_count
            django_product.view_count = product.view_count
            django_product.wishlist_count = product.wishlist_count
            django_product.review_count = product.review_count
            django_product.average_rating = product.average_rating
            
            # Inventory
            django_product.track_quantity = product.track_inventory
            django_product.stock_quantity = product.current_stock_quantity
            
            # Shipping and tax
            django_product.requires_shipping = product.requires_shipping
            django_product.is_taxable = product.is_taxable
            django_product.tax_code = product.tax_code
            
            # SEO
            django_product.seo_title = product.seo_title
            django_product.seo_description = product.seo_description
            django_product.seo_keywords = ','.join(product.meta_keywords)
            
            # ============================================================================
            # MAP ALL AI FEATURES BACK TO DJANGO MODEL
            # ============================================================================
            
            ai_features = product.ai_features
            
            # AI Content Generation
            django_product.ai_generated_description = ai_features.ai_generated_description
            django_product.ai_suggested_tags = ai_features.ai_suggested_tags
            django_product.ai_seo_suggestions = ai_features.ai_seo_suggestions
            django_product.ai_content_quality_score = ai_features.ai_content_quality_score
            
            # Intelligent Pricing and Revenue Optimization
            django_product.ai_recommended_price = ai_features.ai_recommended_price
            django_product.dynamic_pricing_enabled = ai_features.dynamic_pricing_enabled
            django_product.price_elasticity_score = ai_features.price_elasticity_score
            django_product.competitive_price_analysis = ai_features.competitive_price_analysis
            django_product.revenue_optimization_score = ai_features.revenue_optimization_score
            
            # AI-Powered Demand Forecasting
            django_product.demand_forecast_30d = ai_features.demand_forecast_30d
            django_product.demand_forecast_90d = ai_features.demand_forecast_90d
            django_product.seasonal_demand_pattern = ai_features.seasonal_demand_pattern
            django_product.trend_analysis = ai_features.trend_analysis
            django_product.demand_volatility_score = ai_features.demand_volatility_score
            
            # Intelligent Customer Insights and Personalization
            django_product.customer_segments = ai_features.customer_segments
            django_product.personalization_data = ai_features.personalization_data
            django_product.behavioral_analytics = ai_features.behavioral_analytics
            django_product.customer_lifetime_value_impact = ai_features.customer_lifetime_value_impact
            
            # AI-Powered Product Recommendations
            django_product.cross_sell_potential = ai_features.cross_sell_potential
            django_product.upsell_opportunities = ai_features.upsell_opportunities
            django_product.bundle_compatibility_score = ai_features.bundle_compatibility_score
            
            # Intelligent Search and Discoverability
            django_product.search_relevance_score = ai_features.search_relevance_score
            django_product.ai_keywords = ai_features.ai_keywords
            django_product.search_performance_metrics = ai_features.search_performance_metrics
            django_product.discoverability_score = ai_features.discoverability_score
            
            # Advanced Analytics and Performance Intelligence
            django_product.conversion_optimization_score = ai_features.conversion_optimization_score
            django_product.bounce_rate_prediction = ai_features.bounce_rate_prediction
            django_product.engagement_prediction = ai_features.engagement_prediction
            django_product.churn_risk_score = ai_features.churn_risk_score
            
            # AI Quality and Content Analysis
            django_product.image_quality_score = ai_features.image_quality_score
            django_product.content_completeness_score = ai_features.content_completeness_score
            django_product.ai_quality_recommendations = ai_features.ai_quality_recommendations
            django_product.content_optimization_suggestions = ai_features.content_optimization_suggestions
            
            # Intelligent Inventory and Supply Chain
            django_product.reorder_point_ai = ai_features.reorder_point_ai
            django_product.stockout_risk_score = ai_features.stockout_risk_score
            django_product.inventory_turnover_prediction = ai_features.inventory_turnover_prediction
            django_product.supply_chain_risk_analysis = ai_features.supply_chain_risk_analysis
            
            # Real-time AI Insights
            django_product.real_time_performance = ai_features.real_time_performance
            django_product.ai_alerts = ai_features.ai_alerts
            django_product.automated_optimizations = ai_features.automated_optimizations
            django_product.ml_model_predictions = ai_features.ml_model_predictions
            
            # AI Learning and Adaptation
            django_product.learning_data = ai_features.learning_data
            django_product.model_performance_metrics = ai_features.model_performance_metrics
            django_product.ai_confidence_scores = ai_features.ai_confidence_scores
            django_product.last_ai_analysis = ai_features.last_ai_analysis
            
            return django_product
            
        except Exception as e:
            logger.error(f"Failed to update Django model from entity: {e}")
            raise