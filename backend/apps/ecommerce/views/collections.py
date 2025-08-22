"""
Collection views for e-commerce functionality
"""

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Prefetch, Count, Q
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.utils import timezone

from .base import EcommerceBaseMixin
from .mixins import (
    CartMixin, WishlistMixin, SearchMixin, PaginationMixin, 
    CacheMixin, PermissionMixin, ProductAccessMixin, SEOmixin
)
from ..models import Collection, EcommerceProduct, CollectionProduct
from ..forms import CollectionForm, CollectionProductForm


class CollectionListView(EcommerceBaseMixin, CartMixin, WishlistMixin, ListView):
    """View for listing all collections"""
    
    model = Collection
    template_name = 'ecommerce/collections/collection_list.html'
    context_object_name = 'collections'
    paginate_by = 20
    
    def get_queryset(self):
        """Get collections with product counts"""
        queryset = Collection.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_published=True,
            is_visible_in_search=True
        ).annotate(
            product_count=Count('collectionproduct', distinct=True)
        ).prefetch_related(
            Prefetch(
                'collectionproduct_set',
                queryset=CollectionProduct.objects.filter(
                    product__is_active=True,
                    product__is_published=True
                ).select_related('product'),
                to_attr='visible_products'
            )
        ).order_by('display_order', 'title')
        
        # Apply search if query parameter exists
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(handle__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        context.update(self.get_wishlist_context())
        
        # Add featured collections
        context['featured_collections'] = Collection.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_published=True,
            is_featured=True
        ).order_by('display_order', 'title')[:6]
        
        # Add collection types for filtering
        context['collection_types'] = Collection.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).values_list('collection_type', flat=True).distinct()
        
        return context


class CollectionDetailView(EcommerceBaseMixin, CartMixin, WishlistMixin, DetailView):
    """View for displaying collection details with products"""
    
    model = Collection
    template_name = 'ecommerce/collections/collection_detail.html'
    context_object_name = 'collection'
    
    def get_queryset(self):
        """Get collection with related data"""
        return Collection.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_published=True
        ).prefetch_related(
            'collectionproduct_set__product__variants',
            'collectionproduct_set__product__images',
            'collectionproduct_set__product__tags',
            'collectionproduct_set__product__collections'
        ).annotate(
            product_count=Count('collectionproduct', distinct=True)
        )
    
    def get_object(self, queryset=None):
        """Get collection by handle or ID"""
        if 'handle' in self.kwargs:
            obj = get_object_or_404(
                self.get_queryset(),
                handle=self.kwargs['handle']
            )
        else:
            obj = super().get_object(queryset)
        
        # Check access permissions
        if not obj.is_visible_in_storefront and not self.request.user.is_staff:
            raise Http404("Collection not found")
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        context.update(self.get_wishlist_context())
        
        collection = self.object
        
        # Get products in collection
        products = EcommerceProduct.objects.filter(
            collectionproduct__collection=collection,
            is_active=True,
            is_published=True
        ).select_related(
            'primary_collection'
        ).prefetch_related(
            'variants',
            'images',
            'tags',
            'collections'
        ).order_by(
            'collectionproduct__position',
            'title'
        )
        
        # Apply search and filters
        search_query = self.request.GET.get('q')
        if search_query:
            products = products.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sku__icontains=search_query)
            )
        
        # Apply price filters
        price_min = self.request.GET.get('price_min')
        price_max = self.request.GET.get('price_max')
        if price_min:
            products = products.filter(price__gte=price_min)
        if price_max:
            products = products.filter(price__lte=price_max)
        
        # Apply availability filter
        in_stock = self.request.GET.get('in_stock')
        if in_stock == 'true':
            products = products.filter(stock_quantity__gt=0)
        
        # Apply sorting
        ordering = self.request.GET.get('ordering', 'position')
        order_mapping = {
            'position': 'collectionproduct__position',
            'name': 'title',
            'price_low': 'price',
            'price_high': '-price',
            'newest': '-created_at',
            'oldest': 'created_at',
            'popularity': '-view_count',
        }
        products = products.order_by(order_mapping.get(ordering, 'collectionproduct__position'))
        
        # Paginate products
        paginator = Paginator(products, 24)  # 24 products per page
        page = self.request.GET.get('page')
        try:
            products_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            products_page = paginator.page(1)
        
        context.update({
            'products': products_page,
            'paginator': paginator,
            'is_paginated': paginator.num_pages > 1,
            'page_obj': products_page,
            'search_query': search_query,
            'price_min': price_min,
            'price_max': price_max,
            'in_stock': in_stock,
            'ordering': ordering,
        })
        
        return context


class CollectionCreateView(EcommerceBaseMixin, PermissionMixin, CreateView):
    """View for creating new collections (admin only)"""
    
    model = Collection
    form_class = CollectionForm
    template_name = 'ecommerce/collections/collection_form.html'
    success_url = reverse_lazy('ecommerce:collection_list')
    
    required_permissions = ['ecommerce.add_collection']
    
    def form_valid(self, form):
        """Set tenant and user on form save"""
        form.instance.tenant = self.tenant
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        messages.success(self.request, f"Collection '{form.instance.title}' created successfully.")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Collection'
        context['submit_text'] = 'Create Collection'
        return context


class CollectionUpdateView(EcommerceBaseMixin, PermissionMixin, UpdateView):
    """View for updating collections (admin only)"""
    
    model = Collection
    form_class = CollectionForm
    template_name = 'ecommerce/collections/collection_form.html'
    
    required_permissions = ['ecommerce.change_collection']
    
    def get_queryset(self):
        """Filter by tenant"""
        return Collection.objects.filter(tenant=self.tenant)
    
    def form_valid(self, form):
        """Set updated by user"""
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        messages.success(self.request, f"Collection '{form.instance.title}' updated successfully.")
        return response
    
    def get_success_url(self):
        """Redirect to collection detail"""
        return reverse_lazy('ecommerce:collection_detail', kwargs={'handle': self.object.handle})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Collection: {self.object.title}'
        context['submit_text'] = 'Update Collection'
        return context


class CollectionDeleteView(EcommerceBaseMixin, PermissionMixin, DeleteView):
    """View for deleting collections (admin only)"""
    
    model = Collection
    template_name = 'ecommerce/collections/collection_confirm_delete.html'
    success_url = reverse_lazy('ecommerce:collection_list')
    
    required_permissions = ['ecommerce.delete_collection']
    
    def get_queryset(self):
        """Filter by tenant"""
        return Collection.objects.filter(tenant=self.tenant)
    
    def delete(self, request, *args, **kwargs):
        """Show success message on delete"""
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f"Collection '{self.object.title}' deleted successfully.")
        return response


class CollectionProductManageView(EcommerceBaseMixin, PermissionMixin, ListView):
    """View for managing products in a collection (admin only)"""
    
    model = CollectionProduct
    template_name = 'ecommerce/collections/collection_products.html'
    context_object_name = 'collection_products'
    
    required_permissions = ['ecommerce.change_collection']
    
    def get_queryset(self):
        """Get products in specific collection"""
        self.collection = get_object_or_404(
            Collection.objects.filter(tenant=self.tenant),
            pk=self.kwargs['pk']
        )
        
        return CollectionProduct.objects.filter(
            collection=self.collection
        ).select_related(
            'product'
        ).order_by('position')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collection'] = self.collection
        
        # Get available products to add
        existing_product_ids = self.collection.collectionproduct_set.values_list('product_id', flat=True)
        available_products = EcommerceProduct.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).exclude(
            id__in=existing_product_ids
        ).order_by('title')
        
        context['available_products'] = available_products
        return context


class CollectionProductAddView(EcommerceBaseMixin, PermissionMixin, CreateView):
    """View for adding products to collection (admin only)"""
    
    model = CollectionProduct
    form_class = CollectionProductForm
    template_name = 'ecommerce/collections/collection_product_form.html'
    
    required_permissions = ['ecommerce.change_collection']
    
    def dispatch(self, request, *args, **kwargs):
        """Get collection before dispatch"""
        self.collection = get_object_or_404(
            Collection.objects.filter(tenant=self.tenant),
            pk=self.kwargs['collection_pk']
        )
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Set collection and position"""
        form.instance.collection = self.collection
        form.instance.added_by = self.request.user
        
        # Set position to end of collection
        last_position = CollectionProduct.objects.filter(
            collection=self.collection
        ).aggregate(
            last_pos=Count('id')
        )['last_pos'] or 0
        form.instance.position = last_position + 1
        
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f"Product '{form.instance.product.title}' added to collection '{self.collection.title}'."
        )
        return response
    
    def get_success_url(self):
        """Redirect to collection products management"""
        return reverse_lazy(
            'ecommerce:collection_products', 
            kwargs={'pk': self.collection.pk}
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collection'] = self.collection
        context['title'] = f'Add Product to {self.collection.title}'
        return context


class CollectionProductUpdateView(EcommerceBaseMixin, PermissionMixin, UpdateView):
    """View for updating collection product (admin only)"""
    
    model = CollectionProduct
    form_class = CollectionProductForm
    template_name = 'ecommerce/collections/collection_product_form.html'
    
    required_permissions = ['ecommerce.change_collection']
    
    def get_queryset(self):
        """Filter by tenant"""
        return CollectionProduct.objects.filter(
            collection__tenant=self.tenant
        ).select_related('collection', 'product')
    
    def form_valid(self, form):
        """Set updated by user"""
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f"Product '{form.instance.product.title}' updated in collection '{form.instance.collection.title}'."
        )
        return response
    
    def get_success_url(self):
        """Redirect to collection products management"""
        return reverse_lazy(
            'ecommerce:collection_products', 
            kwargs={'pk': self.object.collection.pk}
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collection'] = self.object.collection
        context['title'] = f'Edit Product in {self.object.collection.title}'
        return context


class CollectionProductDeleteView(EcommerceBaseMixin, PermissionMixin, DeleteView):
    """View for removing products from collection (admin only)"""
    
    model = CollectionProduct
    template_name = 'ecommerce/collections/collection_product_confirm_delete.html'
    
    required_permissions = ['ecommerce.change_collection']
    
    def get_queryset(self):
        """Filter by tenant"""
        return CollectionProduct.objects.filter(
            collection__tenant=self.tenant
        ).select_related('collection', 'product')
    
    def get_success_url(self):
        """Redirect to collection products management"""
        return reverse_lazy(
            'ecommerce:collection_products', 
            kwargs={'pk': self.object.collection.pk}
        )
    
    def delete(self, request, *args, **kwargs):
        """Show success message on delete"""
        response = super().delete(request, *args, **kwargs)
        messages.success(
            request, 
            f"Product '{self.object.product.title}' removed from collection '{self.object.collection.title}'."
        )
        return response


class CollectionAJAXView(EcommerceBaseMixin, CartMixin, AJAXMixin):
    """AJAX view for collection operations"""
    
    def post(self, request, *args, **kwargs):
        """Handle AJAX POST requests"""
        action = request.POST.get('action')
        
        if action == 'reorder_products':
            return self.reorder_products(request)
        elif action == 'update_product_position':
            return self.update_product_position(request)
        else:
            return self.json_error('Invalid action')
    
    def reorder_products(self, request):
        """Reorder products in collection"""
        try:
            product_ids = request.POST.getlist('product_ids[]')
            collection_id = request.POST.get('collection_id')
            
            collection = get_object_or_404(
                Collection.objects.filter(tenant=self.tenant),
                pk=collection_id
            )
            
            # Update positions
            for position, product_id in enumerate(product_ids, 1):
                CollectionProduct.objects.filter(
                    collection=collection,
                    product_id=product_id
                ).update(position=position)
            
            return self.json_success('Products reordered successfully')
            
        except Exception as e:
            return self.json_error(f'Error reordering products: {str(e)}')
    
    def update_product_position(self, request):
        """Update individual product position"""
        try:
            product_id = request.POST.get('product_id')
            collection_id = request.POST.get('collection_id')
            new_position = int(request.POST.get('position'))
            
            collection = get_object_or_404(
                Collection.objects.filter(tenant=self.tenant),
                pk=collection_id
            )
            
            # Update position
            CollectionProduct.objects.filter(
                collection=collection,
                product_id=product_id
            ).update(position=new_position)
            
            return self.json_success('Product position updated')
            
        except (ValueError, TypeError):
            return self.json_error('Invalid position value')
        except Exception as e:
            return self.json_error(f'Error updating position: {str(e)}')
