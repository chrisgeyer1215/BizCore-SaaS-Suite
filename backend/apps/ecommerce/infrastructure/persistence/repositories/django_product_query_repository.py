from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Q, Count, Avg, Sum, Max, Min, F, Case, When, Value
from django.utils import timezone
from django.core.paginator import Paginator

from ....domain.repositories.product_repository import ProductQueryRepository
from ....models.products import EcommerceProduct
from .mappers.product_mapper import ProductMapper

import logging

logger = logging.getLogger(__name__)


class DjangoProductQueryRepository(ProductQueryRepository):
    """
    Optimized query repository for complex product queries
    Handles analytics, dashboards, and reporting efficiently
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.mapper = ProductMapper()
    
    # ============================================================================
    # ADVANCED SEARCH AND FILTERING
    # ============================================================================
    
    def advanced_search(
        self,
        search_criteria: Dict[str, Any],
        facets: Optional[List[str]] = None,
        sort_options: Optional[List[Dict[str, str]]] = None,
        pagination: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """Advanced search with faceted navigation"""
        try:
            base_queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Apply search criteria
            query = search_criteria.get('query', '')
            filters = search_criteria.get('filters', {})
            
            if query:
                base_queryset = base_queryset.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(brand__icontains=query) |
                    Q(sku__icontains=query) |
                    Q(ai_keywords__icontains=query)
                )
            
            # Apply filters
            if filters.get('category'):
                base_queryset = base_queryset.filter(category__in=filters['category'])
            
            if filters.get('brand'):
                base_queryset = base_queryset.filter(brand__in=filters['brand'])
            
            if filters.get('price_min'):
                base_queryset = base_queryset.filter(price__gte=filters['price_min'])
            
            if filters.get('price_max'):
                base_queryset = base_queryset.filter(price__lte=filters['price_max'])
            
            if filters.get('rating_min'):
                base_queryset = base_queryset.filter(average_rating__gte=filters['rating_min'])
            
            if filters.get('in_stock'):
                base_queryset = base_queryset.filter(stock_quantity__gt=0)
            
            # Generate facets
            facet_data = {}
            if facets:
                facet_data = self._generate_facets(base_queryset, facets)
            
            # Apply sorting
            if sort_options:
                base_queryset = self._apply_sorting(base_queryset, sort_options)
            else:
                base_queryset = base_queryset.order_by('-sales_count', '-created_at')
            
            # Get total count
            total_count = base_queryset.count()
            
            # Apply pagination
            products = []
            if pagination:
                limit = pagination.get('limit', 20)
                offset = pagination.get('offset', 0)
                paginated_queryset = base_queryset[offset:offset + limit]
                products = [self.mapper.django_model_to_entity(p) for p in paginated_queryset]
            else:
                products = [self.mapper.django_model_to_entity(p) for p in base_queryset[:100]]  # Limit to 100 for safety
            
            return {
                'products': products,
                'total_count': total_count,
                'facets': facet_data,
                'applied_filters': filters,
                'search_query': query
            }
            
        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            raise
    
    def get_product_suggestions(
        self,
        partial_query: str,
        limit: int = 10,
        include_categories: bool = True
    ) -> List[Dict[str, Any]]:
        """Get autocomplete suggestions"""
        try:
            suggestions = []
            
            # Product title suggestions
            products = EcommerceProduct.published.filter(
                tenant=self.tenant,
                title__icontains=partial_query
            )[:limit//2]
            
            for product in products:
                suggestions.append({
                    'type': 'product',
                    'text': product.title,
                    'url': f'/products/{product.url_handle}',
                    'image': product.featured_image.url if product.featured_image else None,
                    'price': float(product.price)
                })
            
            # Category suggestions
            if include_categories:
                categories = EcommerceProduct.published.filter(
                    tenant=self.tenant,
                    category__icontains=partial_query
                ).values_list('category', flat=True).distinct()[:limit//2]
                
                for category in categories:
                    suggestions.append({
                        'type': 'category',
                        'text': category,
                        'url': f'/products?category={category}'
                    })
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Product suggestions failed: {e}")
            raise
    
    # ============================================================================
    # AI-POWERED QUERIES AND INSIGHTS
    # ============================================================================
    
    def get_ai_insights_dashboard(self, time_period: str = "30d") -> Dict[str, Any]:
        """Get comprehensive AI insights for dashboard"""
        try:
            # Parse time period
            if time_period == "7d":
                cutoff_date = timezone.now() - timedelta(days=7)
            elif time_period == "30d":
                cutoff_date = timezone.now() - timedelta(days=30)
            elif time_period == "90d":
                cutoff_date = timezone.now() - timedelta(days=90)
            else:
                cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get base metrics
            total_products = EcommerceProduct.published.filter(tenant=self.tenant).count()
            
            # AI Analysis Coverage
            ai_coverage = EcommerceProduct.published.filter(
                tenant=self.tenant,
                last_ai_analysis__gte=cutoff_date
            ).count()
            
            ai_coverage_percentage = (ai_coverage / max(total_products, 1)) * 100
            
            # AI Performance Metrics
            ai_metrics = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).aggregate(
                avg_ai_health=Avg(
                    Case(
                        When(engagement_prediction__gt=0, then='engagement_prediction'),
                        default=Value(0),
                        output_field=models.DecimalField()
                    )
                ),
                avg_content_quality=Avg('ai_content_quality_score'),
                avg_conversion_score=Avg('conversion_optimization_score'),
                products_needing_analysis=Count(
                    'id', 
                    filter=Q(last_ai_analysis__isnull=True) | Q(last_ai_analysis__lt=cutoff_date)
                ),
                high_churn_risk_products=Count('id', filter=Q(churn_risk_score__gte=70)),
                pricing_opportunities=Count(
                    'id', 
                    filter=Q(ai_recommended_price__isnull=False) & 
                           Q(ai_recommended_price__gt=F('price') * 1.1)
                )
            )
            
            # Top Performing Products (AI-driven)
            top_performers = EcommerceProduct.published.filter(
                tenant=self.tenant,
                engagement_prediction__gte=0.7
            ).order_by('-engagement_prediction', '-sales_count')[:5]
            
            # Products Needing Attention
            needs_attention = EcommerceProduct.published.filter(
                tenant=self.tenant
            ).filter(
                Q(churn_risk_score__gte=60) |
                Q(engagement_prediction__lt=0.4) |
                Q(content_completeness_score__lt=50)
            ).order_by('-churn_risk_score')[:5]
            
            # AI Insights Summary
            insights = []
            
            if ai_coverage_percentage < 50:
                insights.append({
                    'type': 'coverage',
                    'severity': 'medium',
                    'message': f"Only {ai_coverage_percentage:.1f}% of products have recent AI analysis",
                    'action': 'Run AI analysis on more products'
                })
            
            if ai_metrics['high_churn_risk_products'] > 0:
                insights.append({
                    'type': 'churn_risk',
                    'severity': 'high',
                    'message': f"{ai_metrics['high_churn_risk_products']} products have high churn risk",
                    'action': 'Implement retention strategies'
                })
            
            if ai_metrics['pricing_opportunities'] > 0:
                insights.append({
                    'type': 'pricing',
                    'severity': 'low',
                    'message': f"{ai_metrics['pricing_opportunities']} products have pricing optimization opportunities",
                    'action': 'Review AI pricing recommendations'
                })
            
            return {
                'time_period': time_period,
                'total_products': total_products,
                'ai_coverage': {
                    'products_analyzed': ai_coverage,
                    'coverage_percentage': ai_coverage_percentage,
                    'products_needing_analysis': ai_metrics['products_needing_analysis']
                },
                'ai_performance': {
                    'avg_ai_health_score': float(ai_metrics['avg_ai_health'] or 0) * 100,
                    'avg_content_quality': float(ai_metrics['avg_content_quality'] or 0),
                    'avg_conversion_score': float(ai_metrics['avg_conversion_score'] or 0)
                },
                'opportunities': {
                    'pricing_opportunities': ai_metrics['pricing_opportunities'],
                    'high_churn_risk': ai_metrics['high_churn_risk_products']
                },
                'top_performers': [
                    {
                        'id': str(p.id),
                        'title': p.title,
                        'sku': p.sku,
                        'engagement_score': float(p.engagement_prediction),
                        'sales_count': p.sales_count
                    } for p in top_performers
                ],
                'needs_attention': [
                    {
                        'id': str(p.id),
                        'title': p.title,
                        'sku': p.sku,
                        'churn_risk': float(p.churn_risk_score),
                        'engagement': float(p.engagement_prediction),
                        'content_quality': float(p.content_completeness_score)
                    } for p in needs_attention
                ],
                'insights': insights
            }
            
        except Exception as e:
            logger.error(f"AI insights dashboard failed: {e}")
            raise
    
    def get_performance_analytics(
        self,
        product_ids: Optional[List[str]] = None,
        time_period: str = "30d"
    ) -> Dict[str, Any]:
        """Get detailed performance analytics"""
        try:
            # Base queryset
            if product_ids:
                queryset = EcommerceProduct.published.filter(
                    tenant=self.tenant,
                    id__in=product_ids
                )
            else:
                queryset = EcommerceProduct.published.filter(tenant=self.tenant)
            
            # Performance aggregations
            performance_data = queryset.aggregate(
                total_revenue=Sum(F('price') * F('sales_count')),
                total_sales=Sum('sales_count'),
                avg_price=Avg('price'),
                avg_rating=Avg('average_rating'),
                total_reviews=Sum('review_count'),
                total_views=Sum('view_count'),
                
                # AI Performance Metrics
                avg_engagement=Avg('engagement_prediction'),
                avg_conversion=Avg('conversion_optimization_score'),
                avg_content_quality=Avg('content_completeness_score'),
                
                # Performance Distribution
                high_performers=Count('id', filter=Q(engagement_prediction__gte=0.7)),
                medium_performers=Count('id', filter=Q(engagement_prediction__gte=0.4, engagement_prediction__lt=0.7)),
                low_performers=Count('id', filter=Q(engagement_prediction__lt=0.4))
            )
            
            # Category Performance
            category_performance = queryset.values('category').annotate(
                products_count=Count('id'),
                avg_sales=Avg('sales_count'),
                avg_price=Avg('price'),
                avg_engagement=Avg('engagement_prediction'),
                total_revenue=Sum(F('price') * F('sales_count'))
            ).order_by('-total_revenue')
            
            # Brand Performance
            brand_performance = queryset.exclude(brand='').values('brand').annotate(
                products_count=Count('id'),
                avg_sales=Avg('sales_count'),
                avg_price=Avg('price'),
                avg_engagement=Avg('engagement_prediction'),
                total_revenue=Sum(F('price') * F('sales_count'))
            ).order_by('-total_revenue')[:10]
            
            return {
                'time_period': time_period,
                'overall_metrics': {
                    'total_products': queryset.count(),
                    'total_revenue': float(performance_data['total_revenue'] or 0),
                    'total_sales_units': performance_data['total_sales'] or 0,
                    'average_price': float(performance_data['avg_price'] or 0),
                    'average_rating': float(performance_data['avg_rating'] or 0),
                    'total_reviews': performance_data['total_reviews'] or 0,
                    'total_views': performance_data['total_views'] or 0
                },
                'ai_metrics': {
                    'avg_engagement_score': float(performance_data['avg_engagement'] or 0),
                    'avg_conversion_score': float(performance_data['avg_conversion'] or 0),
                    'avg_content_quality': float(performance_data['avg_content_quality'] or 0)
                },
                'performance_distribution': {
                    'high_performers': performance_data['high_performers'],
                    'medium_performers': performance_data['medium_performers'],
                    'low_performers': performance_data['low_performers']
                },
                'category_performance': list(category_performance),
                'brand_performance': list(brand_performance)
            }
            
        except Exception as e:
            logger.error(f"Performance analytics failed: {e}")
            raise
    
    def get_pricing_optimization_opportunities(self) -> List[Dict[str, Any]]:
        """Get pricing optimization opportunities"""
        try:
            opportunities = []
            
            # Products where AI recommends significant price changes
            price_opportunities = EcommerceProduct.published.filter(
                tenant=self.tenant,
                ai_recommended_price__isnull=False
            ).extra(
                where=["ABS(ai_recommended_price - price) / price * 100 >= 10"]
            ).order_by('-ai_recommended_price')
            
            for product in price_opportunities:
                current_price = float(product.price)
                recommended_price = float(product.ai_recommended_price)
                price_difference_pct = ((recommended_price - current_price) / current_price) * 100
                
                opportunities.append({
                    'product_id': str(product.id),
                    'sku': product.sku,
                    'title': product.title,
                    'current_price': current_price,
                    'recommended_price': recommended_price,
                    'price_difference_percentage': round(price_difference_pct, 2),
                    'revenue_impact_estimate': (recommended_price - current_price) * product.sales_count,
                    'confidence_score': float(product.price_elasticity_score or 0),
                    'recommendation_type': 'increase' if recommended_price > current_price else 'decrease'
                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Pricing optimization opportunities failed: {e}")
            raise
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_facets(self, queryset, facet_fields: List[str]) -> Dict[str, List[Dict]]:
        """Generate facet data for advanced search"""
        facets = {}
        
        try:
            for field in facet_fields:
                if field == 'category':
                    facets['category'] = list(
                        queryset.exclude(category='').values('category').annotate(
                            count=Count('id')
                        ).order_by('-count')[:20]
                    )
                
                elif field == 'brand':
                    facets['brand'] = list(
                        queryset.exclude(brand='').values('brand').annotate(
                            count=Count('id')
                        ).order_by('-count')[:20]
                    )
                
                elif field == 'price_range':
                    # Create price range buckets
                    price_stats = queryset.aggregate(
                        min_price=Min('price'),
                        max_price=Max('price')
                    )
                    
                    if price_stats['min_price'] and price_stats['max_price']:
                        price_ranges = self._create_price_ranges(
                            price_stats['min_price'], 
                            price_stats['max_price']
                        )
                        
                        facets['price_range'] = []
                        for price_range in price_ranges:
                            count = queryset.filter(
                                price__gte=price_range['min'],
                                price__lt=price_range['max']
                            ).count()
                            
                            if count > 0:
                                facets['price_range'].append({
                                    'range': f"${price_range['min']:.0f} - ${price_range['max']:.0f}",
                                    'min': price_range['min'],
                                    'max': price_range['max'],
                                    'count': count
                                })
                
                elif field == 'rating':
                    facets['rating'] = [
                        {
                            'rating': 5,
                            'label': '5 stars',
                            'count': queryset.filter(average_rating__gte=4.5).count()
                        },
                        {
                            'rating': 4,
                            'label': '4+ stars',
                            'count': queryset.filter(average_rating__gte=4.0).count()
                        },
                        {
                            'rating': 3,
                            'label': '3+ stars', 
                            'count': queryset.filter(average_rating__gte=3.0).count()
                        }
                    ]
            
            return facets
            
        except Exception as e:
            logger.error(f"Facet generation failed: {e}")
            return {}
    
    def _create_price_ranges(self, min_price: Decimal, max_price: Decimal) -> List[Dict]:
        """Create price range buckets"""
        price_diff = max_price - min_price
        
        if price_diff <= 100:
            # Small ranges for low-priced items
            bucket_size = 25
        elif price_diff <= 500:
            # Medium ranges
            bucket_size = 50
        else:
            # Large ranges for expensive items
            bucket_size = 100
        
        ranges = []
        current = min_price
        
        while current < max_price:
            next_price = min(current + bucket_size, max_price)
            ranges.append({
                'min': float(current),
                'max': float(next_price)
            })
            current = next_price
        
        return ranges
    
    def _apply_sorting(self, queryset, sort_options: List[Dict[str, str]]):
        """Apply sorting options to queryset"""
        order_fields = []
        
        for sort_option in sort_options:
            field = sort_option.get('field')
            direction = sort_option.get('direction', 'asc')
            
            if field == 'relevance':
                # Custom relevance scoring
                order_fields.extend(['-sales_count', '-view_count', '-average_rating'])
            elif field == 'price':
                order_fields.append('price' if direction == 'asc' else '-price')
            elif field == 'popularity':
                order_fields.extend(['-sales_count', '-view_count'])
            elif field == 'rating':
                order_fields.append('-average_rating' if direction == 'desc' else 'average_rating')
            elif field == 'newest':
                order_fields.append('-created_at')
            elif field == 'engagement':
                order_fields.append('-engagement_prediction' if direction == 'desc' else 'engagement_prediction')
        
        if order_fields:
            return queryset.order_by(*order_fields)
        
        return queryset.order_by('-created_at')  # Default sorting
    