# apps/ecommerce/views/products.py

"""
Product-related views for the e-commerce module
"""

from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q, Prefetch, Count, Avg
from django.core.paginator import Paginator

from .base import (
    EcommerceListView, EcommerceDetailView, EcommerceTemplateView,
    AjaxView, FilterMixin, PaginationMixin
)
from ..models import (
    EcommerceProduct, ProductVariant, Collection, ProductReview,
    ProductTag, ProductAnalytics
)
from ..services.recommendations import RecommendationService
from ..services.cart import CartService
from ..services.analytics import AnalyticsService


class StorefrontHomeView(EcommerceTemplateView):
    """Storefront homepage"""
    
    template_name = 'ecommerce/storefront/home.html'
    meta_title = 'Welcome to Our Store'
    meta_description = 'Discover amazing products with exceptional quality and service'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Featured products
        context['featured_products'] = EcommerceProduct.published.filter(
            tenant=self.tenant,
            is_featured=True
        ).order_by('-created_at')[:8]
        
        # New arrivals
        context['new_arrivals'] = EcommerceProduct.published.filter(
            tenant=self.tenant
        ).order_by('-created_at')[:8]
        
        # Best sellers
        context['best_sellers'] = EcommerceProduct.published.filter(
            tenant=self.tenant,
            sales_count__gt=0
        ).order_by('-sales_count')[:8]
        
        # Featured collections
        context['featured_collections'] = Collection.objects.filter(
            tenant=self.tenant,
            is_visible=True,
            is_featured=True
        ).order_by('display_order')[:6]
        
        # Hero banners (would be configured in admin)
        context['hero_banners'] = self.get_hero_banners()
        
        # Store statistics
        context['store_stats'] = self.get_store_stats()
        
        return context
    
    def get_hero_banners(self):
        """Get hero banners for homepage"""
        # This would typically come from a Banner model
        # For now, return sample data
        return [
            {
                'title': 'Summer Sale',
                'subtitle': 'Up to 50% off on selected items',
                'image': '/static/ecommerce/images/banner1.jpg',
                'link': '/collections/sale/',
                'button_text': 'Shop Now'
            },
            {
                'title': 'New Collection',
                'subtitle': 'Discover our latest arrivals',
                'image': '/static/ecommerce/images/banner2.jpg',
                'link': '/collections/new-arrivals/',
                'button_text': 'Explore'
            }
        ]
    
    def get_store_stats(self):
        """Get store statistics for homepage"""
        return {
            'total_products': EcommerceProduct.published.filter(tenant=self.tenant).count(),
            'total_reviews': ProductReview.objects.filter(
                tenant=self.tenant,
                status='APPROVED'
            ).count(),
            'happy_customers': 1000,  # This would come from actual data
            'years_experience': 5
        }


class ProductListView(EcommerceListView):
    """Product catalog listing"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/product_list.html'
    context_object_name = 'products'
    paginate_by = 24
    breadcrumb_title = 'All Products'
    meta_title = 'Our Products'
    meta_description = 'Browse our complete collection of premium products'
    
    def get_queryset(self):
        queryset = EcommerceProduct.published.filter(
            tenant=self.tenant
        ).select_related('primary_collection').prefetch_related(
            'collections', 'images'
        )
        
        # Apply filters from FilterMixin
        return super().get_queryset()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter sidebar data
        context.update({
            'collections': Collection.objects.filter(
                tenant=self.tenant,
                is_visible=True,
                products__isnull=False
            ).annotate(product_count=Count('products')).distinct(),
            'price_ranges': self.get_price_ranges(),
            'popular_tags': self.get_popular_tags(),
        })
        
        return context
    
    def get_price_ranges(self):
        """Get predefined price ranges"""
        return [
            {'label': 'Under $25', 'min': 0, 'max': 25},
            {'label': '$25 - $50', 'min': 25, 'max': 50},
            {'label': '$50 - $100', 'min': 50, 'max': 100},
            {'label': '$100 - $200', 'min': 100, 'max': 200},
            {'label': 'Over $200', 'min': 200, 'max': None},
        ]
    
    def get_popular_tags(self):
        """Get popular product tags"""
        # This would aggregate tags from products
        return ['electronics', 'fashion', 'home', 'sports', 'books']


class ProductDetailView(EcommerceDetailView):
    """Product detail page"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/product_detail.html'
    context_object_name = 'product'
    slug_field = 'url_handle'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return EcommerceProduct.published.filter(
            tenant=self.tenant
        ).select_related('primary_collection').prefetch_related(
            'variants__option_values__option',
            'images',
            'collections',
            Prefetch(
                'reviews',
                queryset=ProductReview.objects.filter(
                    status='APPROVED'
                ).select_related('customer').order_by('-created_at')
            )
        )
    
    def get_object(self, queryset=None):
        """Get product and track analytics"""
        obj = super().get_object(queryset)
        
        # Track product view
        analytics_service = AnalyticsService(self.tenant)
        analytics_service.track_product_view(
            product=obj,
            user=self.request.user if self.request.user.is_authenticated else None,
            session_key=self.request.session.session_key,
            ip_address=self.get_client_ip()
        )
        
        return obj
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = context['product']
        
        # Product variants and options
        if product.has_variants:
            context['variants'] = product.variants.filter(is_active=True)
            context['variant_options'] = product.get_variant_options()
        
        # Product images
        context['product_images'] = product.images.filter(is_active=True).order_by('position')
        
        # Product reviews
        reviews_queryset = product.reviews.filter(status='APPROVED')
        context['reviews'] = reviews_queryset[:5]  # First 5 reviews
        context['total_reviews'] = reviews_queryset.count()
        context['review_stats'] = self.get_review_stats(reviews_queryset)
        
        # Related products
        recommendation_service = RecommendationService(self.tenant)
        context['related_products'] = recommendation_service.get_related_products(
            product, limit=8
        )
        
        # Recently viewed products
        context['recently_viewed'] = self.get_recently_viewed_products(product)
        
        # Product in wishlist check
        if self.request.user.is_authenticated:
            wishlist = self.get_wishlist()
            context['in_wishlist'] = wishlist.has_product(product) if wishlist else False
        
        # Breadcrumbs
        context['breadcrumbs'] = self.get_product_breadcrumbs(product)
        
        # SEO data
        context['structured_data'] = self.get_product_structured_data(product)
        
        return context
    
    def get_review_stats(self, reviews_queryset):
        """Get review statistics"""
        if not reviews_queryset.exists():
            return None
        
        stats = reviews_queryset.aggregate(
            average_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        # Rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            rating_distribution[i] = reviews_queryset.filter(rating=i).count()
        
        stats['rating_distribution'] = rating_distribution
        return stats
    
    def get_recently_viewed_products(self, current_product):
        """Get recently viewed products from session"""
        viewed_products = self.request.session.get('recently_viewed', [])
        
        # Add current product to recently viewed
        product_id = current_product.id
        if product_id in viewed_products:
            viewed_products.remove(product_id)
        viewed_products.insert(0, product_id)
        
        # Keep only last 10 products
        viewed_products = viewed_products[:10]
        self.request.session['recently_viewed'] = viewed_products
        
        # Return products except current one
        if len(viewed_products) > 1:
            return EcommerceProduct.published.filter(
                tenant=self.tenant,
                id__in=viewed_products[1:6]  # Next 5 products
            )
        return EcommerceProduct.objects.none()
    
    def get_product_breadcrumbs(self, product):
        """Get breadcrumbs for product"""
        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
            {'title': 'Products', 'url': '/products/'},
        ]
        
        # Add primary collection if exists
        if product.primary_collection:
            breadcrumbs.append({
                'title': product.primary_collection.title,
                'url': product.primary_collection.get_absolute_url()
            })
        
        # Add current product
        breadcrumbs.append({
            'title': product.title,
            'url': None,
            'current': True
        })
        
        return breadcrumbs
    
    def get_product_structured_data(self, product):
        """Get structured data for SEO"""
        structured_data = {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": product.title,
            "description": product.description,
            "sku": product.sku,
            "url": self.request.build_absolute_uri(),
            "offers": {
                "@type": "Offer",
                "price": str(product.price),
                "priceCurrency": product.currency,
                "availability": "https://schema.org/InStock" if product.is_in_stock else "https://schema.org/OutOfStock",
                "seller": {
                    "@type": "Organization",
                    "name": "Our Store"
                }
            }
        }
        
        # Add images
        if product.featured_image:
            structured_data["image"] = [
                self.request.build_absolute_uri(product.featured_image.url)
            ]
        
        # Add brand
        if product.brand:
            structured_data["brand"] = {
                "@type": "Brand",
                "name": product.brand
            }
        
        # Add review data
        if product.review_count > 0:
            structured_data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(product.average_rating),
                "reviewCount": product.review_count,
                "bestRating": "5",
                "worstRating": "1"
            }
        
        return structured_data


class ProductSearchView(EcommerceListView):
    """Product search results"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/search_results.html'
    context_object_name = 'products'
    paginate_by = 24
    
    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        
        if not query:
            return EcommerceProduct.objects.none()
        
        # Store search query for analytics
        self.search_query = query
        
        queryset = EcommerceProduct.published.filter(
            tenant=self.tenant
        ).filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__icontains=query) |
            Q(sku__icontains=query) |
            Q(tags__icontains=query)
        ).select_related('primary_collection').prefetch_related('images')
        
        # Apply additional filters
        return super().get_queryset()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        query = self.request.GET.get('q', '')
        context.update({
            'search_query': query,
            'search_results_count': self.get_queryset().count(),
            'meta_title': f'Search results for "{query}"',
            'breadcrumb_title': f'Search: "{query}"',
        })
        
        # Track search for analytics
        if query and hasattr(self, 'search_query'):
            analytics_service = AnalyticsService(self.tenant)
            analytics_service.track_search(
                query=query,
                results_count=context['search_results_count'],
                user=self.request.user if self.request.user.is_authenticated else None,
                session_key=self.request.session.session_key
            )
        
        return context


class ProductCompareView(EcommerceTemplateView):
    """Product comparison page"""
    
    template_name = 'ecommerce/products/compare.html'
    breadcrumb_title = 'Compare Products'
    meta_title = 'Compare Products'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get products to compare from session
        compare_list = self.request.session.get('compare_products', [])
        
        if compare_list:
            products = EcommerceProduct.published.filter(
                tenant=self.tenant,
                id__in=compare_list
            ).prefetch_related('variants', 'images')
            context['products'] = products
            context['comparison_attributes'] = self.get_comparison_attributes(products)
        else:
            context['products'] = []
            context['comparison_attributes'] = []
        
        return context
    
    def get_comparison_attributes(self, products):
        """Get attributes for comparison table"""
        if not products:
            return []
        
        # Basic attributes
        attributes = [
            {'name': 'Price', 'key': 'price'},
            {'name': 'Brand', 'key': 'brand'},
            {'name': 'SKU', 'key': 'sku'},
            {'name': 'Rating', 'key': 'average_rating'},
            {'name': 'Reviews', 'key': 'review_count'},
        ]
        
        # Collect all specification keys
        all_specs = set()
        for product in products:
            if product.specifications:
                all_specs.update(product.specifications.keys())
        
        # Add specification attributes
        for spec in sorted(all_specs):
            attributes.append({
                'name': spec.replace('_', ' ').title(),
                'key': f'spec_{spec}',
                'is_specification': True
            })
        
        return attributes


class ProductVariantsAjaxView(AjaxView):
    """AJAX view for product variant information"""
    
    def get_ajax_data(self):
        product_id = self.request.GET.get('product_id')
        if not product_id:
            raise ValidationError('Product ID is required')
        
        product = get_object_or_404(
            EcommerceProduct.published,
            tenant=self.tenant,
            id=product_id
        )
        
        variants_data = []
        for variant in product.variants.filter(is_active=True):
            variants_data.append({
                'id': variant.id,
                'title': variant.title,
                'sku': variant.sku,
                'price': str(variant.effective_price),
                'compare_at_price': str(variant.effective_compare_at_price) if variant.effective_compare_at_price else None,
                'available': variant.is_in_stock,
                'quantity': variant.available_quantity if variant.track_quantity else None,
                'image': variant.image.url if variant.image else None,
                'option_values': [
                    {
                        'option': ov.option.name,
                        'value': ov.value
                    }
                    for ov in variant.option_values.all()
                ]
            })
        
        return {
            'variants': variants_data,
            'has_variants': product.has_variants,
            'options': product.get_variant_options()
        }


class AddToCompareView(AjaxView):
    """AJAX view to add product to comparison"""
    
    def handle_ajax_post(self):
        product_id = self.request.POST.get('product_id')
        if not product_id:
            raise ValidationError('Product ID is required')
        
        # Verify product exists
        product = get_object_or_404(
            EcommerceProduct.published,
            tenant=self.tenant,
            id=product_id
        )
        
        # Get current compare list
        compare_list = self.request.session.get('compare_products', [])
        
        # Check if already in compare list
        if int(product_id) in compare_list:
            return {
                'message': 'Product is already in comparison list',
                'in_compare': True,
                'compare_count': len(compare_list)
            }
        
        # Add to compare list (max 4 products)
        if len(compare_list) >= 4:
            compare_list.pop(0)  # Remove oldest
        
        compare_list.append(int(product_id))
        self.request.session['compare_products'] = compare_list
        
        return {
            'message': f'{product.title} added to comparison',
            'in_compare': True,
            'compare_count': len(compare_list),
            'product': {
                'id': product.id,
                'title': product.title,
                'image': product.featured_image.url if product.featured_image else None
            }
        }


class RemoveFromCompareView(AjaxView):
    """AJAX view to remove product from comparison"""
    
    def handle_ajax_post(self):
        product_id = self.request.POST.get('product_id')
        if not product_id:
            raise ValidationError('Product ID is required')
        
        # Get current compare list
        compare_list = self.request.session.get('compare_products', [])
        
        # Remove from compare list
        if int(product_id) in compare_list:
            compare_list.remove(int(product_id))
            self.request.session['compare_products'] = compare_list
        
        return {
            'message': 'Product removed from comparison',
            'in_compare': False,
            'compare_count': len(compare_list)
        }


class ProductReviewListView(EcommerceListView):
    """Product reviews listing"""
    
    model = ProductReview
    template_name = 'ecommerce/products/reviews.html'
    context_object_name = 'reviews'
    paginate_by = 10
    
    def get_queryset(self):
        self.product = get_object_or_404(
            EcommerceProduct.published,
            tenant=self.tenant,
            url_handle=self.kwargs['slug']
        )
        
        queryset = ProductReview.objects.filter(
            tenant=self.tenant,
            product=self.product,
            status='APPROVED'
        ).select_related('customer').order_by('-created_at')
        
        # Apply rating filter
        rating_filter = self.request.GET.get('rating')
        if rating_filter and rating_filter.isdigit():
            queryset = queryset.filter(rating=int(rating_filter))
        
        # Apply sorting
        sort = self.request.GET.get('sort', 'newest')
        if sort == 'oldest':
            queryset = queryset.order_by('created_at')
        elif sort == 'highest_rating':
            queryset = queryset.order_by('-rating', '-created_at')
        elif sort == 'lowest_rating':
            queryset = queryset.order_by('rating', '-created_at')
        elif sort == 'most_helpful':
            queryset = queryset.order_by('-helpful_votes', '-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'product': self.product,
            'review_stats': self.get_review_stats(),
            'rating_filter': self.request.GET.get('rating', ''),
            'sort_filter': self.request.GET.get('sort', 'newest'),
            'breadcrumb_title': f'Reviews for {self.product.title}',
        })
        
        return context
    
    def get_review_stats(self):
        """Get review statistics"""
        reviews = ProductReview.objects.filter(
            tenant=self.tenant,
            product=self.product,
            status='APPROVED'
        )
        
        if not reviews.exists():
            return None
        
        stats = reviews.aggregate(
            average_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        # Rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            count = reviews.filter(rating=i).count()
            percentage = (count / stats['total_reviews'] * 100) if stats['total_reviews'] > 0 else 0
            rating_distribution[i] = {
                'count': count,
                'percentage': round(percentage, 1)
            }
        
        stats['rating_distribution'] = rating_distribution
        return stats


@method_decorator(cache_page(60 * 15), name='dispatch')  # Cache for 15 minutes
class ProductSitemapView(EcommerceTemplateView):
    """Product sitemap for SEO"""
    
    template_name = 'ecommerce/sitemaps/products.xml'
    content_type = 'application/xml'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['products'] = EcommerceProduct.published.filter(
            tenant=self.tenant
        ).only('url_handle', 'updated_at').order_by('-updated_at')
        
        return context


class NewArrivalsView(EcommerceListView):
    """New arrivals page"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/new_arrivals.html'
    context_object_name = 'products'
    paginate_by = 24
    breadcrumb_title = 'New Arrivals'
    meta_title = 'New Arrivals - Latest Products'
    
    def get_queryset(self):
        from datetime import datetime, timedelta
        
        # Products from last 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        
        return EcommerceProduct.published.filter(
            tenant=self.tenant,
            created_at__gte=cutoff_date
        ).order_by('-created_at')


class BestSellersView(EcommerceListView):
    """Best sellers page"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/best_sellers.html'
    context_object_name = 'products'
    paginate_by = 24
    breadcrumb_title = 'Best Sellers'
    meta_title = 'Best Sellers - Most Popular Products'
    
    def get_queryset(self):
        return EcommerceProduct.published.filter(
            tenant=self.tenant,
            sales_count__gt=0
        ).order_by('-sales_count', '-created_at')


class SaleView(EcommerceListView):
    """Sale/discounted products page"""
    
    model = EcommerceProduct
    template_name = 'ecommerce/products/sale.html'
    context_object_name = 'products'
    paginate_by = 24
    breadcrumb_title = 'Sale'
    meta_title = 'Sale - Discounted Products'
    
    def get_queryset(self):
        return EcommerceProduct.published.filter(
            tenant=self.tenant,
            compare_at_price__isnull=False,
            compare_at_price__gt=models.F('price')
        ).order_by('-created_at')