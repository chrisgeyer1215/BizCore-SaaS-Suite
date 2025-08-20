# apps/ecommerce/views/base.py

"""
Base views and mixins for e-commerce functionality
"""

from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, 
    UpdateView, DeleteView, FormView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import json

from apps.core.mixins import TenantMixin
from ..models import EcommerceSettings, Cart, Wishlist, EcommerceProduct, Collection
from ..services.cart import CartService
from ..services.recommendations import RecommendationService


class EcommerceBaseMixin(TenantMixin):
    """Base mixin for all e-commerce views"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add e-commerce settings to context
        try:
            context['ecommerce_settings'] = EcommerceSettings.objects.get(tenant=self.tenant)
        except EcommerceSettings.DoesNotExist:
            context['ecommerce_settings'] = None
        
        # Add cart information
        context['cart'] = self.get_cart()
        context['cart_item_count'] = context['cart'].item_count if context['cart'] else 0
        
        # Add wishlist information for authenticated users
        if self.request.user.is_authenticated:
            context['wishlist'] = self.get_wishlist()
            context['wishlist_item_count'] = context['wishlist'].item_count if context['wishlist'] else 0
        
        # Add navigation collections
        context['navigation_collections'] = self.get_navigation_collections()
        
        # Add currency information
        context['current_currency'] = self.get_current_currency()
        
        return context
    
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
                user=self.request.user,
                name='My Wishlist',
                is_default=True
            )
    
    def get_navigation_collections(self):
        """Get collections for navigation menu"""
        return Collection.objects.filter(
            tenant=self.tenant,
            is_visible=True,
            parent__isnull=True
        ).order_by('display_order', 'title')[:10]
    
    def get_current_currency(self):
        """Get current currency for the session"""
        return self.request.session.get('currency', 'USD')


class StorefrontMixin(EcommerceBaseMixin):
    """Mixin for storefront views"""
    
    template_name_suffix = '_storefront'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if store is in maintenance mode
        settings_obj = getattr(self, 'get_ecommerce_settings', lambda: None)()
        if settings_obj and getattr(settings_obj, 'maintenance_mode', False):
            if not request.user.is_staff:
                return self.render_maintenance_page()
        
        return super().dispatch(request, *args, **kwargs)
    
    def render_maintenance_page(self):
        """Render maintenance mode page"""
        return self.render_to_response({
            'maintenance_mode': True,
            'maintenance_message': getattr(
                self.get_ecommerce_settings(), 
                'maintenance_message', 
                'Store is temporarily unavailable.'
            )
        })
    
    def get_ecommerce_settings(self):
        """Get e-commerce settings"""
        try:
            return EcommerceSettings.objects.get(tenant=self.tenant)
        except EcommerceSettings.DoesNotExist:
            return None


class AdminMixin(EcommerceBaseMixin, UserPassesTestMixin):
    """Mixin for admin views"""
    
    template_name_suffix = '_admin'
    
    def test_func(self):
        """Check if user has admin permissions"""
        return (
            self.request.user.is_authenticated and 
            (self.request.user.is_staff or self.request.user.is_superuser)
        )
    
    def handle_no_permission(self):
        """Handle permission denied"""
        if not self.request.user.is_authenticated:
            return redirect('auth:login')
        raise PermissionDenied("You don't have permission to access this page.")


class AjaxMixin:
    """Mixin for AJAX views"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'AJAX request required'}, status=400)
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Handle valid form submission for AJAX"""
        response = super().form_valid(form)
        return JsonResponse({
            'success': True,
            'message': 'Operation completed successfully',
            'redirect': getattr(self, 'success_url', None)
        })
    
    def form_invalid(self, form):
        """Handle invalid form submission for AJAX"""
        return JsonResponse({
            'success': False,
            'errors': form.errors,
            'message': 'Please correct the errors below'
        }, status=400)


class PaginationMixin:
    """Mixin for paginated views"""
    
    paginate_by = 24
    page_kwarg = 'page'
    
    def get_paginate_by(self, queryset):
        """Get items per page from request or settings"""
        per_page = self.request.GET.get('per_page')
        if per_page and per_page.isdigit():
            per_page = int(per_page)
            if per_page in [12, 24, 48, 96]:
                return per_page
        return self.paginate_by
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add pagination info
        paginator = context.get('paginator')
        page_obj = context.get('page_obj')
        
        if paginator and page_obj:
            context.update({
                'pagination_range': self.get_pagination_range(paginator, page_obj),
                'items_per_page_options': [12, 24, 48, 96],
                'current_per_page': self.get_paginate_by(None),
                'total_items': paginator.count,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index(),
            })
        
        return context
    
    def get_pagination_range(self, paginator, page_obj):
        """Get smart pagination range"""
        current_page = page_obj.number
        total_pages = paginator.num_pages
        
        # Show 5 pages around current page
        start_page = max(1, current_page - 2)
        end_page = min(total_pages, current_page + 2)
        
        # Adjust if we're at the beginning or end
        if start_page == 1:
            end_page = min(total_pages, 5)
        elif end_page == total_pages:
            start_page = max(1, total_pages - 4)
        
        return range(start_page, end_page + 1)


class FilterMixin:
    """Mixin for filtered views"""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        queryset = self.apply_search_filter(queryset)
        queryset = self.apply_category_filter(queryset)
        queryset = self.apply_price_filter(queryset)
        queryset = self.apply_availability_filter(queryset)
        queryset = self.apply_rating_filter(queryset)
        queryset = self.apply_brand_filter(queryset)
        
        # Apply sorting
        queryset = self.apply_sorting(queryset)
        
        return queryset
    
    def apply_search_filter(self, queryset):
        """Apply search filter"""
        query = self.request.GET.get('q', '').strip()
        if query:
            return queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(brand__icontains=query) |
                Q(sku__icontains=query) |
                Q(tags__icontains=query)
            )
        return queryset
    
    def apply_category_filter(self, queryset):
        """Apply category/collection filter"""
        collection_id = self.request.GET.get('collection')
        if collection_id and collection_id.isdigit():
            return queryset.filter(collections__id=collection_id)
        return queryset
    
    def apply_price_filter(self, queryset):
        """Apply price range filter"""
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        
        if min_price and min_price.replace('.', '').isdigit():
            queryset = queryset.filter(price__gte=Decimal(min_price))
        
        if max_price and max_price.replace('.', '').isdigit():
            queryset = queryset.filter(price__lte=Decimal(max_price))
        
        return queryset
    
    def apply_availability_filter(self, queryset):
        """Apply availability filter"""
        availability = self.request.GET.get('availability')
        if availability == 'in_stock':
            return queryset.filter(
                Q(track_quantity=False) | Q(stock_quantity__gt=0)
            )
        elif availability == 'out_of_stock':
            return queryset.filter(
                track_quantity=True,
                stock_quantity=0
            )
        return queryset
    
    def apply_rating_filter(self, queryset):
        """Apply rating filter"""
        min_rating = self.request.GET.get('rating')
        if min_rating and min_rating.isdigit():
            return queryset.filter(average_rating__gte=int(min_rating))
        return queryset
    
    def apply_brand_filter(self, queryset):
        """Apply brand filter"""
        brands = self.request.GET.getlist('brand')
        if brands:
            return queryset.filter(brand__in=brands)
        return queryset
    
    def apply_sorting(self, queryset):
        """Apply sorting"""
        sort = self.request.GET.get('sort', 'featured')
        
        sort_options = {
            'featured': ['-is_featured', '-created_at'],
            'newest': ['-created_at'],
            'oldest': ['created_at'],
            'price_asc': ['price'],
            'price_desc': ['-price'],
            'name_asc': ['title'],
            'name_desc': ['-title'],
            'rating': ['-average_rating', '-review_count'],
            'best_selling': ['-sales_count'],
            'most_viewed': ['-view_count'],
        }
        
        if sort in sort_options:
            return queryset.order_by(*sort_options[sort])
        
        return queryset.order_by('-is_featured', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter context
        context.update({
            'current_filters': {
                'q': self.request.GET.get('q', ''),
                'collection': self.request.GET.get('collection', ''),
                'min_price': self.request.GET.get('min_price', ''),
                'max_price': self.request.GET.get('max_price', ''),
                'availability': self.request.GET.get('availability', ''),
                'rating': self.request.GET.get('rating', ''),
                'brands': self.request.GET.getlist('brand'),
                'sort': self.request.GET.get('sort', 'featured'),
            },
            'sort_options': [
                ('featured', 'Featured'),
                ('newest', 'Newest'),
                ('price_asc', 'Price: Low to High'),
                ('price_desc', 'Price: High to Low'),
                ('name_asc', 'Name: A to Z'),
                ('name_desc', 'Name: Z to A'),
                ('rating', 'Highest Rated'),
                ('best_selling', 'Best Selling'),
                ('most_viewed', 'Most Viewed'),
            ],
            'available_brands': self.get_available_brands(),
            'price_range': self.get_price_range(),
        })
        
        return context
    
    def get_available_brands(self):
        """Get available brands for filter"""
        return EcommerceProduct.published.filter(
            tenant=self.tenant
        ).values_list('brand', flat=True).distinct().exclude(
            brand__isnull=True
        ).exclude(brand='')
    
    def get_price_range(self):
        """Get price range for filter"""
        prices = EcommerceProduct.published.filter(
            tenant=self.tenant
        ).aggregate(
            min_price=models.Min('price'),
            max_price=models.Max('price')
        )
        return {
            'min': prices['min_price'] or 0,
            'max': prices['max_price'] or 1000
        }


class BreadcrumbMixin:
    """Mixin for breadcrumb navigation"""
    
    breadcrumb_title = None
    
    def get_breadcrumbs(self):
        """Get breadcrumb navigation"""
        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
        ]
        
        # Add custom breadcrumbs
        custom_breadcrumbs = getattr(self, 'get_custom_breadcrumbs', lambda: [])()
        breadcrumbs.extend(custom_breadcrumbs)
        
        # Add current page
        title = self.get_breadcrumb_title()
        if title:
            breadcrumbs.append({'title': title, 'url': None, 'current': True})
        
        return breadcrumbs
    
    def get_breadcrumb_title(self):
        """Get title for current breadcrumb"""
        if self.breadcrumb_title:
            return self.breadcrumb_title
        
        if hasattr(self, 'object') and self.object:
            return str(self.object)
        
        return getattr(self, 'title', 'Page')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['breadcrumbs'] = self.get_breadcrumbs()
        return context


class SEOMixin:
    """Mixin for SEO meta tags"""
    
    meta_title = None
    meta_description = None
    meta_keywords = None
    meta_image = None
    
    def get_meta_title(self):
        """Get meta title"""
        if self.meta_title:
            return self.meta_title
        
        if hasattr(self, 'object') and self.object:
            if hasattr(self.object, 'seo_title') and self.object.seo_title:
                return self.object.seo_title
            return str(self.object)
        
        return getattr(self, 'title', 'E-commerce Store')
    
    def get_meta_description(self):
        """Get meta description"""
        if self.meta_description:
            return self.meta_description
        
        if hasattr(self, 'object') and self.object:
            if hasattr(self.object, 'seo_description') and self.object.seo_description:
                return self.object.seo_description
            if hasattr(self.object, 'description') and self.object.description:
                return self.object.description[:160]
        
        return 'Premium products and exceptional service'
    
    def get_meta_keywords(self):
        """Get meta keywords"""
        if self.meta_keywords:
            return self.meta_keywords
        
        if hasattr(self, 'object') and self.object:
            if hasattr(self.object, 'seo_keywords') and self.object.seo_keywords:
                return self.object.seo_keywords
            if hasattr(self.object, 'tags') and self.object.tags:
                return ', '.join(self.object.tags)
        
        return ''
    
    def get_meta_image(self):
        """Get meta image"""
        if self.meta_image:
            return self.meta_image
        
        if hasattr(self, 'object') and self.object:
            if hasattr(self.object, 'featured_image') and self.object.featured_image:
                return self.object.featured_image.url
        
        return '/static/ecommerce/images/default-og-image.jpg'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'meta_title': self.get_meta_title(),
            'meta_description': self.get_meta_description(),
            'meta_keywords': self.get_meta_keywords(),
            'meta_image': self.get_meta_image(),
        })
        return context


# Base view classes combining mixins

class EcommerceTemplateView(SEOMixin, BreadcrumbMixin, StorefrontMixin, TemplateView):
    """Base template view for e-commerce"""
    pass


class EcommerceListView(FilterMixin, PaginationMixin, SEOMixin, BreadcrumbMixin, StorefrontMixin, ListView):
    """Base list view for e-commerce"""
    pass


class EcommerceDetailView(SEOMixin, BreadcrumbMixin, StorefrontMixin, DetailView):
    """Base detail view for e-commerce"""
    
    def get_object(self, queryset=None):
        """Get object and increment view count"""
        obj = super().get_object(queryset)
        
        # Increment view count for products
        if hasattr(obj, 'view_count'):
            obj.view_count += 1
            obj.save(update_fields=['view_count'])
        
        return obj


class EcommerceFormView(SEOMixin, BreadcrumbMixin, StorefrontMixin, FormView):
    """Base form view for e-commerce"""
    pass


class AdminTemplateView(AdminMixin, TemplateView):
    """Base admin template view"""
    pass


class AdminListView(AdminMixin, ListView):
    """Base admin list view"""
    pass


class AdminDetailView(AdminMixin, DetailView):
    """Base admin detail view"""
    pass


class AdminCreateView(AdminMixin, CreateView):
    """Base admin create view"""
    pass


class AdminUpdateView(AdminMixin, UpdateView):
    """Base admin update view"""
    pass


class AdminDeleteView(AdminMixin, DeleteView):
    """Base admin delete view"""
    pass


class AjaxView(AjaxMixin, EcommerceBaseMixin, TemplateView):
    """Base AJAX view"""
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests"""
        try:
            data = self.get_ajax_data()
            return JsonResponse({
                'success': True,
                'data': data
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests"""
        try:
            data = self.handle_ajax_post()
            return JsonResponse({
                'success': True,
                'data': data,
                'message': getattr(self, 'success_message', 'Operation completed successfully')
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'message': 'Operation failed'
            }, status=500)
    
    def get_ajax_data(self):
        """Override in subclasses to provide GET data"""
        return {}
    
    def handle_ajax_post(self):
        """Override in subclasses to handle POST data"""
        return {}