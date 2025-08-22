"""
View mixins for e-commerce functionality
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q, Count, Avg, Sum, Prefetch
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework import status
from rest_framework.response import Response
from decimal import Decimal
import json

from apps.core.mixins import TenantMixin
from ..models import Cart, Wishlist, EcommerceProduct, Collection, EcommerceSettings
from ..services.cart import CartService


class CartMixin(TenantMixin):
    """Mixin for cart-related functionality"""
    
    def get_cart(self):
        """Get or create cart for current user/session"""
        cart_service = CartService(self.tenant)
        
        if self.request.user.is_authenticated:
            return cart_service.get_or_create_user_cart(self.request.user)
        else:
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
            return cart_service.get_or_create_session_cart(session_key)
    
    def get_cart_context(self):
        """Get cart context data"""
        cart = self.get_cart()
        return {
            'cart': cart,
            'cart_item_count': cart.item_count if cart else 0,
            'cart_total': cart.total_amount if cart else Decimal('0.00'),
            'cart_subtotal': cart.subtotal if cart else Decimal('0.00'),
            'cart_tax': cart.tax_amount if cart else Decimal('0.00'),
            'cart_shipping': cart.shipping_amount if cart else Decimal('0.00'),
        }


class WishlistMixin(TenantMixin):
    """Mixin for wishlist functionality"""
    
    def get_wishlist(self):
        """Get default wishlist for authenticated user"""
        if not self.request.user.is_authenticated:
            return None
        
        try:
            return Wishlist.objects.get(
                tenant=self.tenant,
                user=self.request.user,
                is_default=True
            )
        except Wishlist.DoesNotExist:
            return Wishlist.objects.create(
                tenant=self.tenant,
                user=self.tenant,
                name='My Wishlist',
                is_default=True
            )
    
    def get_wishlist_context(self):
        """Get wishlist context data"""
        wishlist = self.get_wishlist()
        return {
            'wishlist': wishlist,
            'wishlist_item_count': wishlist.item_count if wishlist else 0,
        }


class SearchMixin(TenantMixin):
    """Mixin for search functionality"""
    
    def get_search_query(self):
        """Get search query from request"""
        return self.request.GET.get('q', '').strip()
    
    def get_search_filters(self):
        """Get search filters from request"""
        filters = {}
        
        # Price filters
        price_min = self.request.GET.get('price_min')
        price_max = self.request.GET.get('price_max')
        if price_min:
            filters['price__gte'] = Decimal(price_min)
        if price_max:
            filters['price__lte'] = Decimal(price_max)
        
        # Category filters
        category = self.request.GET.get('category')
        if category:
            filters['collections__handle'] = category
        
        # Brand filters
        brand = self.request.GET.get('brand')
        if brand:
            filters['brand__iexact'] = brand
        
        # Availability filters
        in_stock = self.request.GET.get('in_stock')
        if in_stock == 'true':
            filters['stock_quantity__gt'] = 0
        
        # Rating filters
        min_rating = self.request.GET.get('min_rating')
        if min_rating:
            filters['average_rating__gte'] = float(min_rating)
        
        return filters
    
    def get_search_ordering(self):
        """Get search ordering from request"""
        ordering = self.request.GET.get('ordering', 'relevance')
        
        order_mapping = {
            'relevance': '-relevance_score',
            'price_low': 'price',
            'price_high': '-price',
            'newest': '-created_at',
            'oldest': 'created_at',
            'rating': '-average_rating',
            'popularity': '-view_count',
            'name': 'title',
        }
        
        return order_mapping.get(ordering, '-relevance_score')
    
    def perform_search(self, queryset, query, filters=None, ordering=None):
        """Perform search on queryset"""
        if query:
            # Basic text search
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(short_description__icontains=query) |
                Q(sku__icontains=query) |
                Q(brand__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()
        
        # Apply filters
        if filters:
            queryset = queryset.filter(**filters)
        
        # Apply ordering
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset


class PaginationMixin:
    """Mixin for pagination functionality"""
    
    def get_paginated_response(self, queryset, page_size=20):
        """Get paginated response"""
        paginator = Paginator(queryset, page_size)
        page = self.request.GET.get('page')
        
        try:
            objects = paginator.page(page)
        except PageNotAnInteger:
            objects = paginator.page(1)
        except EmptyPage:
            objects = paginator.page(paginator.num_pages)
        
        return {
            'objects': objects,
            'paginator': paginator,
            'page_obj': objects,
            'is_paginated': paginator.num_pages > 1,
            'page_range': paginator.get_elided_page_range(
                objects.number, 
                on_each_side=2, 
                on_ends=1
            ),
        }


class CacheMixin:
    """Mixin for caching functionality"""
    
    def get_cache_key(self, prefix='view'):
        """Generate cache key for view"""
        return f"{prefix}_{self.tenant}_{self.request.path}_{self.request.GET.urlencode()}"
    
    def get_cache_timeout(self):
        """Get cache timeout in seconds"""
        return getattr(settings, 'ECOMMERCE_CACHE_TIMEOUT', 300)
    
    @method_decorator(cache_page(300))
    @method_decorator(vary_on_cookie)
    def dispatch(self, request, *args, **kwargs):
        """Dispatch with caching"""
        return super().dispatch(request, *args, **kwargs)


class PermissionMixin(UserPassesTestMixin):
    """Mixin for permission checking"""
    
    def test_func(self):
        """Test if user has required permissions"""
        if not self.request.user.is_authenticated:
            return False
        
        # Check if user is staff/admin
        if self.request.user.is_staff:
            return True
        
        # Check specific permissions
        required_permissions = getattr(self, 'required_permissions', [])
        if required_permissions:
            return self.request.user.has_perms(required_permissions)
        
        return True
    
    def handle_no_permission(self):
        """Handle when user doesn't have permission"""
        if self.request.user.is_authenticated:
            messages.error(self.request, "You don't have permission to access this page.")
            return redirect('ecommerce:home')
        else:
            return redirect('login')


class ProductAccessMixin(TenantMixin):
    """Mixin for product access control"""
    
    def check_product_access(self, product):
        """Check if user can access product"""
        # Check if product is published
        if not product.is_published:
            if not self.request.user.is_staff:
                raise Http404("Product not found")
        
        # Check if product requires authentication
        if product.requires_authentication and not self.request.user.is_authenticated:
            return redirect('login')
        
        # Check if product is visible in search
        if not product.is_visible_in_search and self.request.path.endswith('/search/'):
            return None
        
        return product
    
    def get_visible_products(self, queryset):
        """Filter products based on visibility and permissions"""
        if self.request.user.is_staff:
            return queryset
        
        return queryset.filter(
            is_published=True,
            is_active=True,
            is_visible_in_search=True
        )


class CurrencyMixin(TenantMixin):
    """Mixin for currency handling"""
    
    def get_current_currency(self):
        """Get current currency for the session"""
        return self.request.session.get('currency', 'USD')
    
    def set_currency(self, currency):
        """Set currency for the session"""
        self.request.session['currency'] = currency
    
    def get_currency_context(self):
        """Get currency context data"""
        return {
            'current_currency': self.get_current_currency(),
            'available_currencies': self.get_available_currencies(),
        }
    
    def get_available_currencies(self):
        """Get available currencies for tenant"""
        try:
            settings = EcommerceSettings.objects.get(tenant=self.tenant)
            return settings.available_currencies or ['USD']
        except EcommerceSettings.DoesNotExist:
            return ['USD']


class AnalyticsMixin(TenantMixin):
    """Mixin for analytics tracking"""
    
    def track_page_view(self, page_type, object_id=None, metadata=None):
        """Track page view for analytics"""
        # TODO: Implement analytics tracking
        pass
    
    def track_event(self, event_type, object_id=None, metadata=None):
        """Track custom event for analytics"""
        # TODO: Implement event tracking
        pass
    
    def get_analytics_context(self):
        """Get analytics context data"""
        return {
            'page_type': self.get_page_type(),
            'object_id': self.get_object_id(),
            'user_id': self.request.user.id if self.request.user.is_authenticated else None,
        }
    
    def get_page_type(self):
        """Get current page type for analytics"""
        if 'product' in self.request.path:
            return 'product'
        elif 'category' in self.request.path:
            return 'category'
        elif 'search' in self.request.path:
            return 'search'
        elif 'cart' in self.request.path:
            return 'cart'
        elif 'checkout' in self.request.path:
            return 'checkout'
        else:
            return 'page'
    
    def get_object_id(self):
        """Get current object ID for analytics"""
        if hasattr(self, 'object') and self.object:
            return str(self.object.id)
        return None


class AJAXMixin:
    """Mixin for AJAX request handling"""
    
    def is_ajax(self):
        """Check if request is AJAX"""
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    def json_response(self, data, status_code=200):
        """Return JSON response"""
        return JsonResponse(data, status=status_code)
    
    def json_error(self, message, status_code=400, details=None):
        """Return JSON error response"""
        response_data = {
            'error': message,
            'status': 'error'
        }
        if details:
            response_data['details'] = details
        
        return self.json_response(response_data, status_code)
    
    def json_success(self, message, data=None, status_code=200):
        """Return JSON success response"""
        response_data = {
            'message': message,
            'status': 'success'
        }
        if data:
            response_data['data'] = data
        
        return self.json_response(response_data, status_code)


class NotificationMixin:
    """Mixin for notification handling"""
    
    def add_success_message(self, message):
        """Add success message"""
        messages.success(self.request, message)
    
    def add_error_message(self, message):
        """Add error message"""
        messages.error(self.request, message)
    
    def add_warning_message(self, message):
        """Add warning message"""
        messages.warning(self.request, message)
    
    def add_info_message(self, message):
        """Add info message"""
        messages.info(self.request, message)
    
    def get_messages_context(self):
        """Get messages context data"""
        return {
            'messages': messages.get_messages(self.request),
        }


class SEOmixin(TenantMixin):
    """Mixin for SEO functionality"""
    
    def get_seo_context(self, object=None):
        """Get SEO context data"""
        if object and hasattr(object, 'seo_title'):
            return {
                'seo_title': object.seo_title or object.title,
                'seo_description': object.seo_description or getattr(object, 'short_description', ''),
                'seo_keywords': object.seo_keywords or '',
                'canonical_url': object.canonical_url or self.request.build_absolute_uri(),
                'og_title': getattr(object, 'og_title', object.title),
                'og_description': getattr(object, 'og_description', getattr(object, 'short_description', '')),
                'og_image': getattr(object, 'og_image', getattr(object, 'featured_image', '')),
            }
        
        # Default SEO context
        return {
            'seo_title': 'E-commerce Store',
            'seo_description': 'Welcome to our online store',
            'seo_keywords': 'ecommerce, online shopping, products',
            'canonical_url': self.request.build_absolute_uri(),
        }
