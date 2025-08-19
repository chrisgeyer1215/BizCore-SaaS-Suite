from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.core.cache import cache
from django.template.loader import render_to_string
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
import csv
import json

from apps.core.views import TenantViewMixin
from apps.core.pagination import StandardResultsSetPagination
from .models import (
    EcommerceProduct, Collection, Cart, CartItem, Order, OrderItem,
    Coupon, ProductReview, CustomerAddress, ShippingZone, ShippingMethod,
    ReturnRequest, ProductQuestion, ProductAnalytics
)
from .serializers import (
    EcommerceProductListSerializer, EcommerceProductDetailSerializer,
    CollectionSerializer, CartSerializer, CartItemSerializer,
    OrderListSerializer, OrderDetailSerializer, CouponSerializer,
    ProductReviewSerializer, CustomerAddressSerializer,
    ShippingZoneSerializer, ShippingMethodSerializer, ShippingRateSerializer,
    ReturnRequestSerializer, ProductQuestionSerializer,
    CheckoutSerializer, ApplyCouponSerializer, ProductSearchSerializer
)
from .filters import (
    ProductFilter, OrderFilter, CouponFilter, ReviewFilter
)
from .permissions import (
    ProductPermission, OrderPermission, CartPermission, 
    CouponPermission, ReviewPermission
)
from .services import (
    ProductService, CartService, OrderService, PaymentService, AnalyticsService
)


# =============================================================================
# PRODUCT VIEWSETS & VIEWS
# =============================================================================

class ProductViewSet(TenantViewMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for products"""
    
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['title', 'description', 'short_description', 'tags']
    ordering_fields = ['created_at', 'regular_price', 'average_rating', 'sales_count']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return EcommerceProduct.objects.filter(
            tenant=self.request.tenant,
            is_published=True,
            status='ACTIVE'
        ).select_related('primary_collection').prefetch_related('collections', 'variants')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EcommerceProductDetailSerializer
        return EcommerceProductListSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get product detail with view tracking"""
        instance = self.get_object()
        
        # Track product view
        cache_key = f"product_view_{instance.id}_{request.META.get('REMOTE_ADDR')}"
        if not cache.get(cache_key):
            instance.view_count = F('view_count') + 1
            instance.save(update_fields=['view_count'])
            cache.set(cache_key, True, timeout=3600)  # 1 hour
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """Get related products"""
        product = self.get_object()
        related_products = ProductService.get_product_recommendations(product, limit=8)
        
        serializer = EcommerceProductListSerializer(
            related_products, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get product reviews"""
        product = self.get_object()
        reviews = ProductReview.objects.filter(
            product=product,
            status='APPROVED'
        ).select_related('customer').order_by('-created_at')
        
        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = ProductReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get product questions"""
        product = self.get_object()
        questions = ProductQuestion.objects.filter(
            product=product,
            is_public=True
        ).select_related('customer').order_by('-created_at')
        
        serializer = ProductQuestionSerializer(questions, many=True)
        return Response(serializer.data)


class ProductListView(TenantViewMixin, ListAPIView):
    """List view for products"""
    
    serializer_class = EcommerceProductListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return EcommerceProduct.objects.filter(
            tenant=self.request.tenant,
            is_published=True,
            status='ACTIVE'
        ).select_related('primary_collection')


class ProductDetailView(TenantViewMixin, RetrieveAPIView):
    """Detail view for products"""
    
    serializer_class = EcommerceProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return EcommerceProduct.objects.filter(
            tenant=self.request.tenant,
            is_published=True,
            status='ACTIVE'
        ).select_related('primary_collection').prefetch_related('variants', 'collections')


class ProductSearchView(TenantViewMixin, APIView):
    """Product search view"""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        serializer = ProductSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        queryset = EcommerceProduct.objects.filter(
            tenant=request.tenant,
            is_published=True,
            status='ACTIVE'
        )
        
        # Apply search filters
        if data.get('query'):
            queryset = queryset.filter(
                Q(title__icontains=data['query']) |
                Q(description__icontains=data['query']) |
                Q(tags__icontains=data['query'])
            )
        
        if data.get('collections'):
            queryset = queryset.filter(collections__id__in=data['collections'])
        
        if data.get('price_min'):
            queryset = queryset.filter(regular_price__gte=data['price_min'])
        
        if data.get('price_max'):
            queryset = queryset.filter(regular_price__lte=data['price_max'])
        
        if data.get('in_stock'):
            queryset = queryset.filter(
                Q(track_quantity=False) | 
                Q(stock_quantity__gt=0) | 
                Q(continue_selling_when_out_of_stock=True)
            )
        
        if data.get('rating_min'):
            queryset = queryset.filter(average_rating__gte=data['rating_min'])
        
        # Apply sorting
        sort_by = data.get('sort_by', 'relevance')
        if sort_by == 'price_asc':
            queryset = queryset.order_by('regular_price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-regular_price')
        elif sort_by == 'rating_desc':
            queryset = queryset.order_by('-average_rating')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'best_selling':
            queryset = queryset.order_by('-sales_count')
        
        # Paginate results
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        serializer = EcommerceProductListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


# =============================================================================
# COLLECTION VIEWSETS & VIEWS
# =============================================================================

class CollectionViewSet(TenantViewMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for collections"""
    
    serializer_class = CollectionSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Collection.objects.filter(
            tenant=self.request.tenant,
            is_visible=True
        ).prefetch_related('products')
    
    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        """Get products in collection"""
        collection = self.get_object()
        products = collection.products.filter(
            is_published=True,
            status='ACTIVE'
        )
        
        # Apply filters
        filter_backend = ProductFilter(request.GET, queryset=products)
        products = filter_backend.qs
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = EcommerceProductListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = EcommerceProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


# =============================================================================
# CART VIEWSETS & VIEWS
# =============================================================================

class CartViewSet(TenantViewMixin, viewsets.ModelViewSet):
    """ViewSet for cart operations"""
    
    serializer_class = CartSerializer
    permission_classes = [CartPermission]
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Cart.objects.filter(
                tenant=self.request.tenant,
                customer=self.request.user.customer,
                status='active'
            )
        else:
            session_key = self.request.session.session_key
            if session_key:
                return Cart.objects.filter(
                    tenant=self.request.tenant,
                    session_key=session_key,
                    status='active'
                )
        return Cart.objects.none()
    
    def get_object(self):
        """Get or create cart for current user/session"""
        customer = None
        session_key = None
        
        if self.request.user.is_authenticated:
            customer = getattr(self.request.user, 'customer', None)
        else:
            if not self.request.session.session_key:
                self.request.session.create()
            session_key = self.request.session.session_key
        
        cart = CartService.get_or_create_cart(customer=customer, session_key=session_key)
        return cart
    
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Add item to cart"""
        serializer = CartItemSerializer(data=request.data)
        if serializer.is_valid():
            cart = self.get_object()
            
            try:
                cart_item, created = CartService.add_to_cart(
                    cart=cart,
                    product=serializer.validated_data['product'],
                    quantity=serializer.validated_data['quantity'],
                    variant=serializer.validated_data.get('variant'),
                    custom_attributes=serializer.validated_data.get('custom_attributes', {})
                )
                
                return Response({
                    'success': True,
                    'message': 'Item added to cart',
                    'cart': CartSerializer(cart).data
                })
                
            except ValueError as e:
                return Response({
                    'success': False,
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def update_item(self, request):
        """Update cart item quantity"""
        item_id = request.data.get('item_id')
        quantity = request.data.get('quantity', 1)
        
        cart = self.get_object()
        
        try:
            success = CartService.update_cart_item(cart, item_id, quantity)
            if success:
                return Response({
                    'success': True,
                    'message': 'Cart updated',
                    'cart': CartSerializer(cart).data
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Item not found'
                }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        """Remove item from cart"""
        item_id = request.data.get('item_id')
        
        cart = self.get_object()
        success = CartService.remove_from_cart(cart, item_id)
        
        if success:
            return Response({
                'success': True,
                'message': 'Item removed from cart',
                'cart': CartSerializer(cart).data
            })
        else:
            return Response({
                'success': False,
                'message': 'Item not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        """Apply coupon to cart"""
        serializer = ApplyCouponSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            cart = self.get_object()
            coupon_code = serializer.validated_data['coupon_code']
            
            success, message = CartService.apply_coupon(cart, coupon_code)
            
            return Response({
                'success': success,
                'message': message,
                'cart': CartSerializer(cart).data if success else None
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def remove_coupon(self, request):
        """Remove coupon from cart"""
        coupon_code = request.data.get('coupon_code')
        
        cart = self.get_object()
        success = CartService.remove_coupon(cart, coupon_code)
        
        return Response({
            'success': success,
            'message': 'Coupon removed' if success else 'Coupon not found',
            'cart': CartSerializer(cart).data
        })
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Clear cart"""
        cart = self.get_object()
        cart.items.all().delete()
        CartService.calculate_totals(cart)
        
        return Response({
            'success': True,
            'message': 'Cart cleared',
            'cart': CartSerializer(cart).data
        })


# =============================================================================
# ORDER VIEWSETS & VIEWS
# =============================================================================

class OrderViewSet(TenantViewMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for orders"""
    
    permission_classes = [OrderPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = OrderFilter
    ordering = ['-order_date']
    pagination_class = StandardResultsSetPagination
    lookup_field = 'order_number'
    
    def get_queryset(self):
        queryset = Order.objects.filter(tenant=self.request.tenant)
        
        if not self.request.user.is_staff:
            # Customers can only see their own orders
            queryset = queryset.filter(customer=self.request.user.customer)
        
        return queryset.select_related('customer').prefetch_related('items', 'payment_transactions')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderListSerializer
    
    @action(detail=True, methods=['get'])
    def invoice(self, request, order_number=None):
        """Get order invoice"""
        order = self.get_object()
        
        # Generate invoice HTML
        html_content = render_to_string('ecommerce/order_invoice.html', {
            'order': order,
            'items': order.items.all(),
        })
        
        return HttpResponse(html_content, content_type='text/html')
    
    @action(detail=True, methods=['get'])
    def tracking(self, request, order_number=None):
        """Get order tracking information"""
        order = self.get_object()
        
        tracking_info = {
            'order_number': order.order_number,
            'status': order.status,
            'tracking_number': order.tracking_number,
            'tracking_url': order.tracking_url,
            'shipped_date': order.shipped_date,
            'delivered_date': order.delivered_date,
            'milestones': []
        }
        
        # Add status milestones
        if order.order_date:
            tracking_info['milestones'].append({
                'status': 'Order Placed',
                'date': order.order_date,
                'completed': True
            })
        
        if order.confirmed_at:
            tracking_info['milestones'].append({
                'status': 'Order Confirmed',
                'date': order.confirmed_at,
                'completed': True
            })
        
        if order.shipped_date:
            tracking_info['milestones'].append({
                'status': 'Shipped',
                'date': order.shipped_date,
                'completed': True
            })
        
        if order.delivered_date:
            tracking_info['milestones'].append({
                'status': 'Delivered',
                'date': order.delivered_date,
                'completed': True
            })
        
        return Response(tracking_info)


class CheckoutView(TenantViewMixin, APIView):
    """Checkout process view"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Process checkout"""
        serializer = CheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get user's cart
        customer = request.user.customer
        cart = Cart.objects.filter(
            tenant=request.tenant,
            customer=customer,
            status='active'
        ).first()
        
        if not cart or cart.items.count() == 0:
            return Response({
                'success': False,
                'message': 'Cart is empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create order from cart
            order = OrderService.create_order_from_cart(
                cart=cart,
                customer_info=data['billing_address'],
                shipping_info=data['shipping_address'],
                payment_info={
                    'method': data['payment_method'],
                    'shipping_method_id': data['shipping_method_id']
                }
            )
            
            return Response({
                'success': True,
                'message': 'Order created successfully',
                'order': OrderDetailSerializer(order).data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShippingRatesView(TenantViewMixin, APIView):
    """Calculate shipping rates"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Calculate shipping rates for cart"""
        shipping_address = request.data.get('shipping_address')
        if not shipping_address:
            return Response({
                'error': 'Shipping address required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get cart
        if request.user.is_authenticated:
            cart = Cart.objects.filter(
                tenant=request.tenant,
                customer=request.user.customer,
                status='active'
            ).first()
        else:
            session_key = request.session.session_key
            cart = Cart.objects.filter(
                tenant=request.tenant,
                session_key=session_key,
                status='active'
            ).first() if session_key else None
        
        if not cart:
            return Response({
                'error': 'Cart not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        shipping_rates = OrderService.calculate_shipping_rates(cart, shipping_address)
        
        return Response({
            'shipping_rates': shipping_rates
        })


# =============================================================================
# ADMIN VIEWS
# =============================================================================

class AdminDashboardView(TenantViewMixin, APIView):
    """Admin dashboard with key metrics"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard metrics"""
        # Sales metrics for last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        sales_summary = AnalyticsService.get_sales_summary(
            tenant=request.tenant,
            date_from=thirty_days_ago
        )
        
        # Top products
        top_products = AnalyticsService.get_top_products(
            tenant=request.tenant,
            limit=5,
            date_from=thirty_days_ago
        )
        
        # Recent orders
        recent_orders = Order.objects.filter(
            tenant=request.tenant
        ).order_by('-order_date')[:10]
        
        # Low stock products
        low_stock_products = EcommerceProduct.objects.filter(
            tenant=request.tenant,
            track_quantity=True,
            stock_quantity__lte=F('low_stock_threshold')
        )[:10]
        
        # Abandoned cart stats
        abandoned_stats = AnalyticsService.get_abandoned_cart_recovery_stats(request.tenant)
        
        return Response({
            'sales_summary': sales_summary,
            'top_products': top_products,
            'recent_orders': OrderListSerializer(recent_orders, many=True).data,
            'low_stock_products': EcommerceProductListSerializer(low_stock_products, many=True).data,
            'abandoned_cart_stats': abandoned_stats,
        })


# =============================================================================
# UTILITY VIEWS
# =============================================================================

class ValidateCouponView(TenantViewMixin, APIView):
    """Validate coupon code"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Validate coupon"""
        coupon_code = request.data.get('coupon_code')
        if not coupon_code:
            return Response({
                'valid': False,
                'message': 'Coupon code required'
            })
        
        try:
            coupon = Coupon.objects.get(
                tenant=request.tenant,
                code=coupon_code
            )
            
            is_valid, message = coupon.is_valid()
            
            return Response({
                'valid': is_valid,
                'message': message,
                'coupon': CouponSerializer(coupon).data if is_valid else None
            })
            
        except Coupon.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'Invalid coupon code'
            })


# =============================================================================
# EXPORT VIEWS
# =============================================================================

class ExportProductsView(TenantViewMixin, APIView):
    """Export products to CSV"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Export products"""
        products = EcommerceProduct.objects.filter(tenant=request.tenant)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'SKU', 'Regular Price', 'Sale Price',
            'Stock Quantity', 'Status', 'Created At'
        ])
        
        for product in products:
            writer.writerow([
                product.id,
                product.title,
                product.sku,
                product.regular_price,
                product.sale_price or '',
                product.stock_quantity,
                product.status,
                product.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response


class ExportOrdersView(TenantViewMixin, APIView):
    """Export orders to CSV"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Export orders"""
        orders = Order.objects.filter(tenant=request.tenant)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Customer Email', 'Status', 'Total Amount',
            'Currency', 'Order Date', 'Payment Status'
        ])
        
        for order in orders:
            writer.writerow([
                order.order_number,
                order.customer_email,
                order.status,
                order.total_amount,
                order.currency,
                order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                order.payment_status
            ])
        
        return response


# Additional ViewSets for remaining models
class CouponViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    permission_classes = [CouponPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = CouponFilter

class ProductReviewViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    permission_classes = [ReviewPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ReviewFilter

class ProductQuestionViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = ProductQuestionSerializer
    permission_classes = [IsAuthenticated]

class ReturnRequestViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = ReturnRequestSerializer
    permission_classes = [IsAuthenticated]

class ShippingZoneViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = ShippingZoneSerializer
    permission_classes = [IsAuthenticated]

class CustomerAddressViewSet(TenantViewMixin, viewsets.ModelViewSet):
    serializer_class = CustomerAddressSerializer
    permission_classes = [IsAuthenticated]
