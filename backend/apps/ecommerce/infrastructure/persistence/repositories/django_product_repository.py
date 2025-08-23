from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import models, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, F, Count, Avg, Sum, Max, Min
from django.utils import timezone

from ....domain.entities.product import Product, AIFeatureState
from ....domain.value_objects.sku import ProductSKU
from ....domain.value_objects.money import Money
from ....domain.value_objects.price import Price
from ....domain.repositories.product_repository import ProductRepository
from ....models.products import EcommerceProduct  # Your existing Django model
from .mappers.product_mapper import ProductMapper

import logging

logger = logging.getLogger(__name__)


class DjangoProductRepository(ProductRepository):
    """
    Django ORM implementation of ProductRepository
    Maps between your rich Django models and clean domain entities
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.mapper = ProductMapper()
    
    # ============================================================================
    # BASIC CRUD OPERATIONS
    # ============================================================================
    
    def save(self, product: Product) -> Product:
        """Save or update product entity"""
        try:
            with transaction.atomic():
                # Check if product exists
                try:
                    django_product = EcommerceProduct.objects.get(
                        tenant=self.tenant,
                        id=product.id
                    )
                    # Update existing
                    django_product = self.mapper.update_django_model_from_entity(django_product, product)
                except EcommerceProduct.DoesNotExist:
                    # Create new
                    django_product = self.mapper.entity_to_django_model(product, self.tenant)
                
                django_product.save()
                
                # Handle domain events (publish them)
                self._publish_domain_events(product)
                
                # Return updated entity
                return self.mapper.django_model_to_entity(django_product)
                
        except Exception as e:
            logger.error(f"Failed to save product {product.id}: {e}")
            raise
    
    def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find product by ID"""
        try:
            django_product = EcommerceProduct.objects.select_related(
                'primary_collection'
            ).prefetch_related(
                'collections', 'variants', 'images'
            ).get(
                tenant=self.tenant,
                id=product_id
            )
            
            return self.mapper.django_model_to_entity(django_product)
            
        except EcommerceProduct.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to find product by ID {product_id}: {e}")
            raise
    
    def find_by_sku(self, sku: ProductSKU) -> Optional[Product]:
        """Find product by SKU"""
        try:
            django_product = EcommerceProduct.objects.select_related(
                'primary_collection'
            ).prefetch_related(
                'collections', 'variants', 'images'
            ).get(
                tenant=self.tenant,
                sku=str(sku)
            )
            
            return self.mapper.django_model_to_entity(django_product)
            
        except EcommerceProduct.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to find product by SKU {sku}: {e}")
            raise
    
    def find_by_url_handle(self, url_handle: str) -> Optional[Product]:
        """Find product by URL handle"""
        try:
            django_product = EcommerceProduct.published.select_related(
                'primary_collection'
            ).prefetch_related(
                'collections', 'variants', 'images'
            ).get(
                tenant=self.tenant,
                url_handle=url_handle
            )
            
            return self.mapper.django_model_to_entity(django_product)
            
        except EcommerceProduct.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to find product by URL handle {url_handle}: {e}")
            raise
    
    def delete(self, product_id: str) -> bool:
        """Delete product"""
        try:
            deleted_count, _ = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                id=product_id
            ).delete()
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
            raise
    
    def exists_by_sku(self, sku: ProductSKU) -> bool:
        """Check if product exists by SKU"""
        return EcommerceProduct.objects.filter(
            tenant=self.tenant,
            sku=str(sku)
        ).exists()
    
    def exists_by_url_handle(self, url_handle: str) -> bool:
        """Check if URL handle is already taken"""
        return EcommerceProduct.objects.filter(
            tenant=self.tenant,
            url_handle=url_handle
        ).exists()
    
    # ============================================================================
    # FINDING AND FILTERING
    # ============================================================================
    
    def find_all_active(self, limit: Optional[int] = None, offset: int = 0) -> List[Product]:
        """Find all active products"""
        try:
            queryset = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).select_related('primary_collection').order_by('-created_at')
            
            if limit:
                queryset = queryset[offset:offset + limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find active products: {e}")
            raise
    
    def find_all_published(self, limit: Optional[int] = None, offset: int = 0) -> List[Product]:
        """Find all published products"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).select_related('primary_collection').order_by('-created_at')
            
            if limit:
                queryset = queryset[offset:offset + limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find published products: {e}")
            raise
    
    def find_by_category(self, category: str, limit: Optional[int] = None) -> List[Product]:
        """Find products by category"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                category=category
            ).order_by('-sales_count', '-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find products by category {category}: {e}")
            raise
    
    def find_by_brand(self, brand: str, limit: Optional[int] = None) -> List[Product]:
        """Find products by brand"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                brand__iexact=brand
            ).order_by('-sales_count', '-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find products by brand {brand}: {e}")
            raise
    
    def find_by_price_range(
        self, 
        min_price: Money, 
        max_price: Money, 
        limit: Optional[int] = None
    ) -> List[Product]:
        """Find products within price range"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                price__gte=min_price.amount,
                price__lte=max_price.amount,
                currency=min_price.currency
            ).order_by('price')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find products by price range: {e}")
            raise
    
    def find_featured(self, limit: Optional[int] = None) -> List[Product]:
        """Find featured products"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                is_featured=True
            ).order_by('-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find featured products: {e}")
            raise
    
    def find_new_arrivals(self, days: int = 30, limit: Optional[int] = None) -> List[Product]:
        """Find new arrivals within specified days"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                created_at__gte=cutoff_date
            ).order_by('-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find new arrivals: {e}")
            raise
    
    def find_best_sellers(self, limit: Optional[int] = None) -> List[Product]:
        """Find best selling products"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                sales_count__gt=0
            ).order_by('-sales_count', '-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find best sellers: {e}")
            raise
    
    def find_on_sale(self, limit: Optional[int] = None) -> List[Product]:
        """Find products on sale"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                compare_at_price__isnull=False,
                compare_at_price__gt=F('price')
            ).order_by('-created_at')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find sale products: {e}")
            raise
    
    # ============================================================================
    # SEARCH OPERATIONS
    # ============================================================================
    
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Product], int]:
        """Full-text search products"""
        try:
            # Start with base published queryset
            queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Apply search query
            if query.strip():
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(brand__icontains=query) |
                    Q(sku__icontains=query) |
                    Q(tags__icontains=query)
                )
            
            # Apply filters
            if filters:
                if 'category' in filters:
                    queryset = queryset.filter(category=filters['category'])
                
                if 'brand' in filters:
                    queryset = queryset.filter(brand__in=filters['brand'])
                
                if 'price_min' in filters:
                    queryset = queryset.filter(price__gte=filters['price_min'])
                
                if 'price_max' in filters:
                    queryset = queryset.filter(price__lte=filters['price_max'])
                
                if 'in_stock' in filters and filters['in_stock']:
                    queryset = queryset.filter(stock_quantity__gt=0)
                
                if 'featured' in filters and filters['featured']:
                    queryset = queryset.filter(is_featured=True)
            
            # Apply sorting
            sort_mapping = {
                'relevance': ['-sales_count', '-view_count', '-created_at'],
                'price_low': ['price'],
                'price_high': ['-price'],
                'newest': ['-created_at'],
                'popularity': ['-sales_count', '-view_count'],
                'rating': ['-average_rating', '-review_count'],
                'name': ['title']
            }
            
            sort_fields = sort_mapping.get(sort_by, ['-created_at'])
            queryset = queryset.order_by(*sort_fields)
            
            # Get total count before pagination
            total_count = queryset.count()
            
            # Apply pagination
            if limit:
                queryset = queryset[offset:offset + limit]
            
            # Convert to entities
            products = [self.mapper.django_model_to_entity(p) for p in queryset]
            
            return products, total_count
            
        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            raise
    
    def search_by_keywords(self, keywords: List[str], limit: Optional[int] = None) -> List[Product]:
        """Search products by AI keywords"""
        try:
            if not keywords:
                return []
            
            # Search in AI keywords field
            queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Build query for AI keywords
            keyword_queries = Q()
            for keyword in keywords:
                keyword_queries |= Q(ai_keywords__icontains=keyword)
            
            queryset = queryset.filter(keyword_queries).distinct()
            
            # Also search in regular fields as fallback
            fallback_queries = Q()
            for keyword in keywords:
                fallback_queries |= (
                    Q(title__icontains=keyword) |
                    Q(description__icontains=keyword) |
                    Q(tags__icontains=keyword)
                )
            
            fallback_queryset = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).filter(fallback_queries).distinct()
            
            # Combine results (AI keywords first, then fallback)
            combined_ids = list(queryset.values_list('id', flat=True)) + \
                          list(fallback_queryset.exclude(id__in=queryset).values_list('id', flat=True))
            
            if limit:
                combined_ids = combined_ids[:limit]
            
            # Get products in order
            products_dict = {
                str(p.id): p for p in EcommerceProduct.objects.filter(id__in=combined_ids)
            }
            
            ordered_products = [products_dict[str(pid)] for pid in combined_ids if str(pid) in products_dict]
            
            return [self.mapper.django_model_to_entity(p) for p in ordered_products]
            
        except Exception as e:
            logger.error(f"Failed to search by keywords: {e}")
            raise
    
    # ============================================================================
    # AI-POWERED QUERIES (Your existing AI features!)
    # ============================================================================
    
    def find_products_needing_ai_analysis(self, analysis_type: str, limit: int = 100) -> List[Product]:
        """Find products that need AI analysis"""
        try:
            cutoff_date = timezone.now() - timedelta(days=7)  # Need analysis if older than 7 days
            
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).filter(
                Q(last_ai_analysis__isnull=True) |
                Q(last_ai_analysis__lt=cutoff_date)
            )
            
            # Filter by specific analysis type needs
            if analysis_type == 'pricing':
                queryset = queryset.filter(
                    Q(ai_recommended_price__isnull=True) |
                    Q(price_elasticity_score=0)
                )
            elif analysis_type == 'content':
                queryset = queryset.filter(
                    Q(ai_content_quality_score__lt=60) |
                    Q(content_completeness_score__lt=70)
                )
            elif analysis_type == 'demand':
                queryset = queryset.filter(
                    Q(demand_forecast_30d=0) |
                    Q(demand_forecast_90d=0)
                )
            elif analysis_type == 'recommendations':
                queryset = queryset.filter(
                    Q(cross_sell_potential=0) |
                    Q(bundle_compatibility_score=0)
                )
            
            queryset = queryset.order_by('last_ai_analysis', '-sales_count')[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find products needing AI analysis: {e}")
            raise
    
    def find_products_with_high_churn_risk(self, threshold: float = 70.0, limit: Optional[int] = None) -> List[Product]:
        """Find products with high customer churn risk"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                churn_risk_score__gte=threshold
            ).order_by('-churn_risk_score')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find high churn risk products: {e}")
            raise
    
    def find_products_with_low_engagement(self, threshold: float = 0.5, limit: Optional[int] = None) -> List[Product]:
        """Find products with low engagement prediction"""
        try:
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                engagement_prediction__lt=threshold
            ).order_by('engagement_prediction')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find low engagement products: {e}")
            raise
    
    def find_products_with_pricing_opportunities(self, min_difference_percentage: float = 10.0) -> List[Product]:
        """Find products where AI recommended price differs significantly from current price"""
        try:
            # Find products where AI recommended price differs by more than threshold
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                ai_recommended_price__isnull=False
            ).extra(
                where=[
                    "ABS(ai_recommended_price - price) / price * 100 >= %s"
                ],
                params=[min_difference_percentage]
            ).order_by('-ai_recommended_price')
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find pricing opportunities: {e}")
            raise
    
    def find_products_with_inventory_alerts(self, alert_types: List[str], limit: Optional[int] = None) -> List[Product]:
        """Find products with specific inventory alert types"""
        try:
            # Search in AI alerts for inventory-related alerts
            queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Filter by alert types in ai_alerts JSON field
            alert_conditions = Q()
            for alert_type in alert_types:
                alert_conditions |= Q(ai_alerts__icontains=alert_type)
            
            queryset = queryset.filter(alert_conditions)
            
            # Also check specific inventory risk scores
            if 'HIGH_STOCKOUT_RISK' in alert_types:
                queryset = queryset.filter(stockout_risk_score__gte=70)
            
            queryset = queryset.order_by('-stockout_risk_score')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find products with inventory alerts: {e}")
            raise
    
    def find_underperforming_products(self, criteria: Dict[str, Any], limit: Optional[int] = None) -> List[Product]:
        """Find underperforming products based on AI criteria"""
        try:
            queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Apply performance criteria
            if 'min_sales' in criteria:
                queryset = queryset.filter(sales_count__lt=criteria['min_sales'])
            
            if 'max_engagement' in criteria:
                queryset = queryset.filter(engagement_prediction__lt=criteria['max_engagement'])
            
            if 'max_conversion' in criteria:
                queryset = queryset.filter(conversion_optimization_score__lt=criteria['max_conversion'])
            
            if 'min_churn_risk' in criteria:
                queryset = queryset.filter(churn_risk_score__gte=criteria['min_churn_risk'])
            
            if 'max_content_quality' in criteria:
                queryset = queryset.filter(content_completeness_score__lt=criteria['max_content_quality'])
            
            # Order by worst performing first
            queryset = queryset.order_by('engagement_prediction', 'conversion_optimization_score', '-churn_risk_score')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find underperforming products: {e}")
            raise
    
    def find_trending_products(self, time_period: str = "7d", limit: Optional[int] = None) -> List[Product]:
        """Find trending products based on AI analysis"""
        try:
            # Parse time period
            if time_period == "7d":
                cutoff_date = timezone.now() - timedelta(days=7)
            elif time_period == "30d":
                cutoff_date = timezone.now() - timedelta(days=30)
            else:
                cutoff_date = timezone.now() - timedelta(days=7)
            
            # Find products with high engagement and recent activity
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                engagement_prediction__gte=0.6,  # High engagement
                updated_at__gte=cutoff_date  # Recent activity
            ).order_by('-engagement_prediction', '-view_count', '-sales_count')
            
            if limit:
                queryset = queryset[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except Exception as e:
            logger.error(f"Failed to find trending products: {e}")
            raise
    
    # ============================================================================
    # RECOMMENDATIONS AND RELATIONSHIPS
    # ============================================================================
    
    def find_cross_sell_candidates(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find cross-sell candidates for a product"""
        try:
            # Get the source product
            source_product = EcommerceProduct.objects.get(tenant=self.tenant, id=product_id)
            
            # Find products with high cross-sell potential in same/related categories
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                cross_sell_potential__gte=0.5
            ).exclude(id=product_id)
            
            # Prefer same category first
            same_category = queryset.filter(category=source_product.category)[:limit//2]
            other_category = queryset.exclude(category=source_product.category)[:limit//2]
            
            combined_queryset = list(same_category) + list(other_category)
            
            return [self.mapper.django_model_to_entity(p) for p in combined_queryset[:limit]]
            
        except EcommerceProduct.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Failed to find cross-sell candidates: {e}")
            raise
    
    def find_upsell_candidates(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find upsell candidates for a product"""
        try:
            source_product = EcommerceProduct.objects.get(tenant=self.tenant, id=product_id)
            
            # Find products in same category with higher price and good performance
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                category=source_product.category,
                price__gt=source_product.price,
                engagement_prediction__gte=0.5
            ).exclude(id=product_id).order_by('price', '-engagement_prediction')[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except EcommerceProduct.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Failed to find upsell candidates: {e}")
            raise
    
    def find_bundle_compatible_products(self, product_id: str, min_score: float = 0.7) -> List[Product]:
        """Find products compatible for bundling"""
        try:
            source_product = EcommerceProduct.objects.get(tenant=self.tenant, id=product_id)
            
            # Find products with high bundle compatibility score
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                bundle_compatibility_score__gte=min_score
            ).exclude(id=product_id).order_by('-bundle_compatibility_score')
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except EcommerceProduct.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Failed to find bundle compatible products: {e}")
            raise
    
    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================
    
    def save_batch(self, products: List[Product]) -> List[Product]:
        """Save multiple products in batch"""
        try:
            saved_products = []
            
            with transaction.atomic():
                for product in products:
                    saved_product = self.save(product)
                    saved_products.append(saved_product)
            
            return saved_products
            
        except Exception as e:
            logger.error(f"Failed to save products batch: {e}")
            raise
    
    def update_prices_batch(self, price_updates: List[Dict[str, Any]]) -> int:
        """Bulk update product prices"""
        try:
            updated_count = 0
            
            with transaction.atomic():
                for update in price_updates:
                    product_id = update['product_id']
                    new_price = update['price']
                    reason = update.get('reason', 'bulk_update')
                    
                    updated = EcommerceProduct.objects.filter(
                        tenant=self.tenant,
                        id=product_id
                    ).update(
                        price=new_price,
                        updated_at=timezone.now()
                    )
                    
                    updated_count += updated
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to update prices in batch: {e}")
            raise
    
    def bulk_publish(self, product_ids: List[str]) -> int:
        """Bulk publish products"""
        try:
            updated_count = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                id__in=product_ids
            ).update(
                is_published=True,
                is_active=True,
                updated_at=timezone.now()
            )
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk publish products: {e}")
            raise
    
    def bulk_unpublish(self, product_ids: List[str], reason: str = "") -> int:
        """Bulk unpublish products"""
        try:
            updated_count = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                id__in=product_ids
            ).update(
                is_published=False,
                updated_at=timezone.now()
            )
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk unpublish products: {e}")
            raise
    
    # ============================================================================
    # STATISTICS AND AGGREGATIONS
    # ============================================================================
    
    def count_all(self) -> int:
        """Count all products"""
        return EcommerceProduct.objects.filter(tenant=self.tenant).count()
    
    def count_published(self) -> int:
        """Count published products"""
        return EcommerceProduct.published.filter(tenant=self.tenant).count()
    
    def count_by_category(self) -> Dict[str, int]:
        """Count products by category"""
        try:
            counts = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).values('category').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {item['category']: item['count'] for item in counts if item['category']}
            
        except Exception as e:
            logger.error(f"Failed to count by category: {e}")
            raise
    
    def count_by_brand(self) -> Dict[str, int]:
        """Count products by brand"""
        try:
            counts = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).values('brand').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {item['brand']: item['count'] for item in counts if item['brand']}
            
        except Exception as e:
            logger.error(f"Failed to count by brand: {e}")
            raise
    
    def get_price_statistics(self) -> Dict[str, Decimal]:
        """Get price statistics"""
        try:
            stats = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).aggregate(
                min_price=Min('price'),
                max_price=Max('price'),
                avg_price=Avg('price'),
                total_products=Count('id')
            )
            
            return {
                'min_price': stats['min_price'] or Decimal('0'),
                'max_price': stats['max_price'] or Decimal('0'),
                'avg_price': stats['avg_price'] or Decimal('0'),
                'total_products': stats['total_products']
            }
            
        except Exception as e:
            logger.error(f"Failed to get price statistics: {e}")
            raise
    
    def get_ai_health_statistics(self) -> Dict[str, Any]:
        """Get AI health score statistics across all products"""
        try:
            # Calculate AI health statistics from your AI fields
            stats = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).aggregate(
                avg_content_quality=Avg('ai_content_quality_score'),
                avg_engagement_prediction=Avg('engagement_prediction'),
                avg_conversion_score=Avg('conversion_optimization_score'),
                products_with_ai_analysis=Count('id', filter=Q(last_ai_analysis__isnull=False)),
                total_products=Count('id')
            )
            
            # Calculate additional AI metrics
            ai_coverage_percentage = (stats['products_with_ai_analysis'] / max(stats['total_products'], 1)) * 100
            
            return {
                'avg_content_quality_score': float(stats['avg_content_quality'] or 0),
                'avg_engagement_prediction': float(stats['avg_engagement_prediction'] or 0),
                'avg_conversion_optimization_score': float(stats['avg_conversion_score'] or 0),
                'ai_analysis_coverage_percentage': ai_coverage_percentage,
                'products_with_ai_analysis': stats['products_with_ai_analysis'],
                'total_products': stats['total_products']
            }
            
        except Exception as e:
            logger.error(f"Failed to get AI health statistics: {e}")
            raise
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _publish_domain_events(self, product: Product):
        """Publish domain events from entity"""
        # In a real implementation, you'd publish these to an event bus
        # For now, we'll just log them
        events = product.get_domain_events()
        
        for event in events:
            logger.info(f"Domain event: {event.event_type} for product {event.aggregate_id}")
            # TODO: Publish to event bus (Redis, RabbitMQ, etc.)
        
        # Clear events after publishing
        product.clear_domain_events()
    
    def find_similar_products(self, product_id: str, limit: int = 10) -> List[Product]:
        """Find similar products based on attributes"""
        try:
            source_product = EcommerceProduct.objects.get(tenant=self.tenant, id=product_id)
            
            # Find similar products by category, price range, and brand
            price_range_min = source_product.price * Decimal('0.8')
            price_range_max = source_product.price * Decimal('1.2')
            
            queryset = EcommerceProduct.published.filter(
                tenant=self.tenant,
                category=source_product.category,
                price__gte=price_range_min,
                price__lte=price_range_max
            ).exclude(id=product_id).order_by('-sales_count', '-average_rating')[:limit]
            
            return [self.mapper.django_model_to_entity(p) for p in queryset]
            
        except EcommerceProduct.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Failed to find similar products: {e}")
            raise