"""
CRM Product ViewSets - Product and Pricing Management
Handles product catalog, pricing models, and bundles for sales teams
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum, Avg
from decimal import Decimal

from ..models import ProductCategory, Product, PricingModel, ProductBundle
from ..serializers.product import (
    ProductCategorySerializer, ProductSerializer,
    PricingModelSerializer, ProductBundleSerializer
)
from ..permissions.product import (
    CanViewProducts, CanManageProducts, CanManagePricing
)
from ..services.product_service import ProductService
from ..utils.tenant_utils import get_tenant_context


class ProductCategoryViewSet(viewsets.ModelViewSet):
    """
    Product Category Management ViewSet
    Handles product categorization and organization
    """
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated, CanManageProducts]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return ProductCategory.objects.filter(
            tenant=tenant,
            is_active=True
        ).annotate(
            product_count=Count('products')
        ).order_by('name')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in this category"""
        category = self.get_object()
        
        products = Product.objects.filter(
            category=category,
            is_active=True
        ).select_related('category')
        
        serializer = ProductSerializer(products, many=True)
        
        return Response({
            'success': True,
            'products': serializer.data,
            'category': category.name,
            'total_count': products.count()
        })


class ProductViewSet(viewsets.ModelViewSet):
    """
    Product Management ViewSet
    Handles product creation, management, and sales integration
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, CanViewProducts]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        queryset = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('category').prefetch_related('pricing_models')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(sku__icontains=search)
            )
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=Decimal(min_price))
        if max_price:
            queryset = queryset.filter(base_price__lte=Decimal(max_price))
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, CanManageProducts]
        else:
            permission_classes = [IsAuthenticated, CanViewProducts]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'])
    def pricing(self, request, pk=None):
        """Get product pricing information"""
        product = self.get_object()
        
        try:
            service = ProductService(tenant=product.tenant)
            pricing_info = service.get_product_pricing(
                product=product,
                quantity=int(request.query_params.get('quantity', 1)),
                customer_tier=request.query_params.get('customer_tier'),
                region=request.query_params.get('region')
            )
            
            return Response({
                'success': True,
                'product_id': product.id,
                'pricing': pricing_info,
                'base_price': product.base_price,
                'available_pricing_models': product.pricing_models.count()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Pricing calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def sales_history(self, request, pk=None):
        """Get product sales history and analytics"""
        product = self.get_object()
        date_range = int(request.query_params.get('date_range', 90))
        
        try:
            service = ProductService(tenant=product.tenant)
            sales_data = service.get_product_sales_history(
                product=product,
                date_range=date_range
            )
            
            return Response({
                'success': True,
                'product_id': product.id,
                'sales_history': sales_data,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Sales history retrieval failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """Get top-selling products"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 90))
        limit = int(request.query_params.get('limit', 10))
        
        try:
            service = ProductService(tenant=tenant)
            top_products = service.get_top_selling_products(
                date_range=date_range,
                limit=limit,
                metric=request.query_params.get('metric', 'revenue')  # revenue, quantity, deals
            )
            
            return Response({
                'success': True,
                'top_products': top_products,
                'metric': request.query_params.get('metric', 'revenue'),
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Top products calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class PricingModelViewSet(viewsets.ModelViewSet):
    """
    Pricing Model Management ViewSet
    Handles different pricing strategies and models
    """
    serializer_class = PricingModelSerializer
    permission_classes = [IsAuthenticated, CanManagePricing]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return PricingModel.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('product')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def calculate_price(self, request, pk=None):
        """Calculate price based on pricing model"""
        pricing_model = self.get_object()
        
        try:
            service = ProductService(tenant=pricing_model.tenant)
            calculated_price = service.calculate_price_with_model(
                pricing_model=pricing_model,
                quantity=int(request.data.get('quantity', 1)),
                customer_data=request.data.get('customer_data', {}),
                context_data=request.data.get('context_data', {})
            )
            
            return Response({
                'success': True,
                'pricing_model': pricing_model.name,
                'calculated_price': calculated_price,
                'base_price': pricing_model.product.base_price,
                'calculation_details': calculated_price.get('details', {})
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Price calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductBundleViewSet(viewsets.ModelViewSet):
    """
    Product Bundle Management ViewSet
    Handles product bundles and package deals
    """
    serializer_class = ProductBundleSerializer
    permission_classes = [IsAuthenticated, CanManageProducts]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return ProductBundle.objects.filter(
            tenant=tenant,
            is_active=True
        ).prefetch_related('products')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def pricing(self, request, pk=None):
        """Get bundle pricing vs individual product pricing"""
        bundle = self.get_object()
        
        try:
            service = ProductService(tenant=bundle.tenant)
            pricing_comparison = service.get_bundle_pricing_comparison(
                bundle=bundle,
                quantity=int(request.query_params.get('quantity', 1)),
                customer_tier=request.query_params.get('customer_tier')
            )
            
            return Response({
                'success': True,
                'bundle': {
                    'id': bundle.id,
                    'name': bundle.name,
                    'bundle_price': bundle.bundle_price
                },
                'pricing_comparison': pricing_comparison,
                'savings': pricing_comparison.get('total_savings'),
                'savings_percentage': pricing_comparison.get('savings_percentage')
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Bundle pricing calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get bundle sales performance"""
        bundle = self.get_object()
        date_range = int(request.query_params.get('date_range', 90))
        
        try:
            service = ProductService(tenant=bundle.tenant)
            performance_data = service.get_bundle_performance(
                bundle=bundle,
                date_range=date_range
            )
            
            return Response({
                'success': True,
                'bundle_id': bundle.id,
                'performance': performance_data,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Bundle performance calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)