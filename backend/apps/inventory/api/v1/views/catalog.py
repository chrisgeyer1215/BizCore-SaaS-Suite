# apps/inventory/api/v1/views/catalog.py

from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, F, Case, When, DecimalField
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.catalog import (
    ProductSerializer, ProductDetailSerializer, ProductCreateSerializer,
    ProductVariationSerializer, CategorySerializer, CategoryDetailSerializer,
    BulkProductSerializer, ProductImageSerializer, ProductAttributeSerializer
)
from apps.inventory.models.catalog.products import Product
from apps.inventory.models.catalog.variations import ProductVariation
from apps.inventory.models.core.categories import Category
from apps.inventory.models.stock.items import StockItem
from apps.inventory.services.stock.movement_service import StockMovementService
from apps.inventory.services.reports.analytics_service import AnalyticsService
from apps.inventory.utils.exceptions import InventoryError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from drf_spectacular.utils import extend_schema, extend_schema_view
from ..documentation.schemas import *
from ..documentation.serializers import *

@extend_schema_view(
    list=inventory_list_schema(
        summary="List Products",
        description="""
        Retrieve a paginated list of products with advanced filtering and search capabilities.
        
        ## Filtering Options:
        - **category**: Filter by category ID
        - **brand**: Filter by brand ID  
        - **supplier**: Filter by supplier ID
        - **abc_classification**: Filter by ABC class (A, B, C)
        - **is_active**: Filter by active status
        - **has_stock**: Filter products with current stock
        - **low_stock**: Filter products below reorder level
        
        ## Search:
        Search across product name, SKU, description, and barcode fields.
        
        ## Ordering:
        Available ordering fields: name, sku, cost_price, selling_price, 
        total_stock, abc_classification, created_at, updated_at
        
        ## Examples:
        - `/api/v1/products/?category=1&is_active=true&ordering=-total_stock`
        - `/api/v1/products/?search=iPhone&abc_classification=A`
        - `/api/v1/products/?low_stock=true&ordering=reorder_level`
        """,
        serializer_class=DocumentedProductSerializer,
        additional_parameters=[
            OpenApiParameter('category', OpenApiTypes.INT, description='Filter by category ID'),
            OpenApiParameter('brand', OpenApiTypes.INT, description='Filter by brand ID'),
            OpenApiParameter('abc_classification', OpenApiTypes.STR, description='Filter by ABC class'),
            OpenApiParameter('low_stock', OpenApiTypes.BOOL, description='Filter low stock items'),
        ]
    ),
    create=inventory_create_schema(
        summary="Create Product",
        description="""
        Create a new product in the inventory system.
        
        ## Required Fields:
        - **name**: Product name
        - **sku**: Unique stock keeping unit
        - **category**: Category ID
        - **cost_price**: Purchase cost
        - **selling_price**: Sale price
        
        ## Business Rules:
        - SKU must be unique across all products
        - Selling price should be greater than cost price
        - Category must exist and be active
        - Brand and supplier are optional but recommended
        
        ## Automatic Calculations:
        - Profit margin is automatically calculated
        - ABC classification will be assigned during next analysis
        - Stock levels are tracked separately via Stock Items
        """,
        serializer_class=DocumentedProductSerializer
    ),
    retrieve=inventory_detail_schema(
        summary="Get Product Details",
        description="""
        Retrieve detailed information about a specific product including:
        
        - Basic product information
        - Current stock levels across all warehouses  
        - Recent movement history
        - ABC classification and analytics
        - Supplier and pricing information
        - Reorder recommendations
        """,
        serializer_class=DocumentedProductSerializer
    ),
    update=inventory_update_schema(
        summary="Update Product",
        description="""
        Update product information. Supports both full updates (PUT) and partial updates (PATCH).
        
        ## Update Restrictions:
        - SKU changes require administrative approval
        - Price changes are logged for audit purposes
        - Category changes may affect ABC classification
        
        ## Automatic Actions:
        - Price change alerts are generated if thresholds exceeded
        - Reorder levels are recalculated if cost changes significantly
        - ABC classification may be updated if value changes substantially
        """,
        serializer_class=DocumentedProductSerializer
    ),
    destroy=inventory_delete_schema(
        summary="Delete Product",
        description="""
        Delete a product from the system.
        
        ## Deletion Rules:
        - Cannot delete products with current stock
        - Cannot delete products with pending orders
        - Cannot delete products with movement history (archive instead)
        
        ## Alternative: Deactivation
        Consider setting `is_active=false` instead of deletion to maintain audit trail.
        """
    )
)

class CategoryViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing product categories with hierarchical support.
    
    Supports:
    - Hierarchical category trees
    - Bulk category operations
    - Category analytics and metrics
    - Product assignment and management
    """
    serializer_class = CategorySerializer
    detail_serializer_class = CategoryDetailSerializer
    queryset = Category.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific categories with optimized queries."""
        return Category.objects.select_related(
            'parent', 'department'
        ).prefetch_related(
            'children', 'products'
        ).with_product_counts().with_hierarchy_level()
    
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get complete category tree structure."""
        try:
            categories = self.get_queryset().filter(parent__isnull=True)
            tree_data = []
            
            for category in categories:
                tree_data.append(self._build_category_tree(category))
            
            return Response({
                'success': True,
                'data': tree_data,
                'total_categories': self.get_queryset().count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve category tree')
    
    def _build_category_tree(self, category):
        """Recursively build category tree."""
        data = CategoryDetailSerializer(category, context={'request': self.request}).data
        
        children = category.children.all()
        if children.exists():
            data['children'] = [self._build_category_tree(child) for child in children]
        else:
            data['children'] = []
            
        return data
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get category analytics and metrics."""
        try:
            category = self.get_object()
            analytics_service = AnalyticsService(request.user.tenant)
            
            # Get category analytics
            analytics_data = analytics_service.get_category_analytics(category)
            
            return Response({
                'success': True,
                'data': analytics_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve category analytics')
    
    @action(detail=True, methods=['post'])
    def bulk_assign_products(self, request, pk=None):
        """Bulk assign products to category."""
        try:
            category = self.get_object()
            product_ids = request.data.get('product_ids', [])
            
            if not product_ids:
                return Response({
                    'success': False,
                    'errors': ['No product IDs provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                products = Product.objects.filter(
                    id__in=product_ids,
                    tenant=request.user.tenant
                )
                products.update(category=category)
            
            return Response({
                'success': True,
                'message': f'{products.count()} products assigned to category',
                'assigned_count': products.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to assign products to category')


class ProductViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing products with comprehensive features.
    
    Supports:
    - Full product lifecycle management
    - Bulk operations and imports
    - Product analytics and reports
    - Stock integration
    - Variation management
    """
    serializer_class = ProductSerializer
    detail_serializer_class = ProductDetailSerializer
    create_serializer_class = ProductCreateSerializer
    queryset = Product.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific products with optimized queries."""
        return Product.objects.select_related(
            'category', 'brand', 'uom', 'supplier'
        ).prefetch_related(
            'variations', 'stock_items', 'attributes'
        ).with_stock_summary().with_valuation()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return self.create_serializer_class
        elif self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action == 'bulk_create':
            return BulkProductSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced product search with filters."""
        try:
            # Get search parameters
            query = request.query_params.get('q', '')
            category_id = request.query_params.get('category')
            brand_id = request.query_params.get('brand')
            in_stock_only = request.query_params.get('in_stock_only', 'false').lower() == 'true'
            min_price = request.query_params.get('min_price')
            max_price = request.query_params.get('max_price')
            
            # Build query
            queryset = self.get_queryset()
            
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(sku__icontains=query) |
                    Q(barcode__icontains=query) |
                    Q(description__icontains=query)
                )
            
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            if brand_id:
                queryset = queryset.filter(brand_id=brand_id)
            
            if in_stock_only:
                queryset = queryset.filter(stock_items__quantity_on_hand__gt=0)
            
            if min_price:
                queryset = queryset.filter(cost_price__gte=min_price)
            
            if max_price:
                queryset = queryset.filter(cost_price__lte=max_price)
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': queryset.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Product search failed')
    
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get comprehensive stock summary for product."""
        try:
            product = self.get_object()
            
            # Get stock items for all warehouses
            stock_items = StockItem.objects.filter(
                product=product,
                tenant=request.user.tenant
            ).select_related('warehouse', 'location')
            
            summary = {
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'total_quantity': sum(item.quantity_on_hand for item in stock_items),
                'total_reserved': sum(item.quantity_reserved for item in stock_items),
                'total_available': sum(item.quantity_available for item in stock_items),
                'total_value': sum(item.total_value for item in stock_items),
                'warehouses': []
            }
            
            # Group by warehouse
            warehouse_data = {}
            for item in stock_items:
                warehouse_id = item.warehouse.id
                if warehouse_id not in warehouse
                        'warehouse_id': warehouse_id,
                        'warehouse_name': item.warehouse.name,
                        'quantity_on_hand': 0,
                        'quantity_reserved': 0,
                        'quantity_available': 0,
                        'total_value': 0,
                        'locations': []
                    }
                
                warehouse_info = warehouse_data[warehouse_id]
                warehouse_info['quantity_on_hand'] += item.quantity_on_hand
                warehouse_info['quantity_reserved'] += item.quantity_reserved
                warehouse_info['quantity_available'] += item.quantity_available
                warehouse_info['total_value'] += item.total_value
                
                warehouse_info['locations'].append({
                    'location_id': item.location.id if item.location else None,
                    'location_name': item.location.name if item.location else 'Default',
                    'quantity_on_hand': item.quantity_on_hand,
                    'quantity_reserved': item.quantity_reserved,
                    'quantity_available': item.quantity_available,
                    'unit_cost': item.unit_cost,
                    'total_value': item.total_value
                })
            
            summary['warehouses'] = list(warehouse_data.values())
            
            return Response({
                'success': True,
                'data': summary
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve stock summary')
    
    @action(detail=True, methods=['get'])
    def movement_history(self, request, pk=None):
        """Get product movement history."""
        try:
            product = self.get_object()
            days = int(request.query_params.get('days', 30))
            
            movement_service = StockMovementService(request.user.tenant)
            history = movement_service.get_product_movement_history(
                product=product,
                days=days
            )
            
            return Response({
                'success': True,
                'data': history
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve movement history')
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get product analytics and KPIs."""
        try:
            product = self.get_object()
            analytics_service = AnalyticsService(request.user.tenant)
            
            analytics_data = analytics_service.get_product_analytics(product)
            
            return Response({
                'success': True,
                'data': analytics_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve product analytics')
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a product with optional modifications."""
        try:
            source_product = self.get_object()
            
            # Get modification data
            modifications = request.data.get('modifications', {})
            include_variations = request.data.get('include_variations', True)
            include_stock = request.data.get('include_stock', False)
            
            with transaction.atomic():
                # Create new product
                new_product_data = {
                    'name': modifications.get('name', f"{source_product.name} (Copy)"),
                    'sku': modifications.get('sku', f"{source_product.sku}-COPY"),
                    'description': source_product.description,
                    'category': source_product.category,
                    'brand': source_product.brand,
                    'uom': source_product.uom,
                    'cost_price': source_product.cost_price,
                    'selling_price': source_product.selling_price,
                    'reorder_level': source_product.reorder_level,
                    'max_stock_level': source_product.max_stock_level,
                    'is_active': modifications.get('is_active', True),
                    'tenant': request.user.tenant
                }
                
                # Apply any other modifications
                for key, value innew_product_data[key] = value
                
                new_product = Product.objects.create(**new_product_data)
                
                # Copy variations if requested
                if include_variations and source_product.variations.exists():
                    for variation in source_product.variations.all():
                        ProductVariation.objects.create(
                            product=new_product,
                            name=variation.name,
                            sku=f"{new_product.sku}-{variation.name}",
                            additional_cost=variation.additional_cost,
                            is_active=variation.is_active,
                            tenant=request.user.tenant
                        )
                
                # Copy stock if requested
                if include_stock:
                    for stock_item in source_product.stock_items.all():
                        StockItem.objects.create(
                            product=new_product,
                            warehouse=stock_item.warehouse,
                            location=stock_item.location,
                            quantity_on_hand=stock_item.quantity_on_hand,
                            unit_cost=stock_item.unit_cost,
                            tenant=request.user.tenant
                        )
            
            serializer = self.get_serializer(new_product)
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Product duplicated successfully'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.handle_error(e, 'Failed to duplicate product')
    
    @action(detail=False, methods=['post'])
    def bulk_update_prices(self, request):
        """Bulk update product prices."""
        try:
            updates = request.data.get('updates', [])
            
            if not updates:
                return Response({
                    'success': False,
                    'errors': ['No updates provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            updated_count = 0
            errors = []
            
            with transaction.atomic():
                for update in updates:
                    try:
                        product_id = update.get('product_id')
                        cost_price = update.get('cost_price')
                        selling_price = update.get('selling_price')
                        
                        product = Product.objects.get(
                            id=product_id,
                            tenant=request.user.tenant
                        )
                        
                        if cost_price is not None:
                            product.cost_price = cost_price
                        if selling_price is not None:
                            product.selling_price = selling_price
                        
                        product.save()
                        updated_count += 1
                        
                    except Product.DoesNotExist:
                        errors.append(f"Product {product_id} not found")
                    except Exception as e:
                        errors.append(f"Error updating product {product_id}: {str(e)}")
            
            return Response({
                'success': True,
                'updated_count': updated_count,
                'errors': errors,
                'message': f'Updated {updated_count} products'
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to bulk update prices')


class ProductVariationViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing product variations.
    """
    serializer_class = ProductVariationSerializer
    queryset = ProductVariation.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific variations."""
        return ProductVariation.objects.select_related(
            'product', 'product__category'
        ).prefetch_related('stock_items')
    
    @action(detail=False, methods=['get'])
    def by_product(self, request):
        """Get variations by product ID."""
        try:
            product_id = request.query_params.get('product_id')
            if not product_id:
                return Response({
                    'success': False,
                    'errors': ['product_id parameter is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            variations = self.get_queryset().filter(product_id=product_id)
            serializer = self.get_serializer(variations, many=True)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'total': variations.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve product variations')
    
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get stock summary for variation."""
        try:
            variation = self.get_object()
            
            # Get stock items for variation
            stock_items = StockItem.objects.filter(
                variation=variation,
                tenant=request.user.tenant
            ).select_related('warehouse', 'location')
            
            summary = {
                'variation_id': variation.id,
                'variation_name': variation.name,
                'sku': variation.sku,
                'total_quantity': sum(item.quantity_on_hand for item in stock_items),
                'total_reserved': sum(item.quantity_reserved for item in stock_items),
                'total_available': sum(item.quantity_available for item in stock_items),
                'total_value': sum(item.total_value for item in stock_items),
                'locations': []
            }
            
            for item in stock_items:
                summary['locations'].append({
                    'warehouse_id': item.warehouse.id,
                    'warehouse_name': item.warehouse.name,
                    'location_id': item.location.id if item.location else None,
                    'location_name': item.location.name if item.location else 'Default',
                    'quantity_on_hand': item.quantity_on_hand,
                    'quantity_reserved': item.quantity_reserved,
                    'quantity_available': item.quantity_available,
                    'unit_cost': item.unit_cost,
                    'total_value': item.total_value
                })
            
            return Response({
                'success': True,
                'data': summary
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve variation stock summary')