from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .webhooks import stripe, paypal

app_name = 'ecommerce'

# API Router
router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'collections', views.CollectionViewSet, basename='collection')
router.register(r'carts', views.CartViewSet, basename='cart')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'coupons', views.CouponViewSet, basename='coupon')
router.register(r'reviews', views.ProductReviewViewSet, basename='review')
router.register(r'questions', views.ProductQuestionViewSet, basename='question')
router.register(r'return-requests', views.ReturnRequestViewSet, basename='return-request')
router.register(r'shipping-zones', views.ShippingZoneViewSet, basename='shipping-zone')
router.register(r'customer-addresses', views.CustomerAddressViewSet, basename='customer-address')

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Product URLs
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:product_id>/reviews/', views.ProductReviewListView.as_view(), name='product-reviews'),
    path('products/<int:product_id>/questions/', views.ProductQuestionListView.as_view(), name='product-questions'),
    path('products/<int:product_id>/related/', views.RelatedProductsView.as_view(), name='related-products'),
    
    # Collection URLs
    path('collections/', views.CollectionListView.as_view(), name='collection-list'),
    path('collections/<slug:slug>/', views.CollectionDetailView.as_view(), name='collection-detail'),
    path('collections/<slug:slug>/products/', views.CollectionProductsView.as_view(), name='collection-products'),
    
    # Cart URLs
    path('cart/', views.CartDetailView.as_view(), name='cart-detail'),
    path('cart/add/', views.AddToCartView.as_view(), name='add-to-cart'),
    path('cart/update/', views.UpdateCartView.as_view(), name='update-cart'),
    path('cart/remove/', views.RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear-cart'),
    path('cart/apply-coupon/', views.ApplyCouponView.as_view(), name='apply-coupon'),
    path('cart/remove-coupon/', views.RemoveCouponView.as_view(), name='remove-coupon'),
    
    # Checkout URLs
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('checkout/shipping-rates/', views.ShippingRatesView.as_view(), name='shipping-rates'),
    path('checkout/payment/', views.PaymentView.as_view(), name='payment'),
    path('checkout/complete/', views.CheckoutCompleteView.as_view(), name='checkout-complete'),
    
    # Order URLs
    path('orders/', views.OrderListView.as_view(), name='order-list'),
    path('orders/<str:order_number>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:order_id>/invoice/', views.OrderInvoiceView.as_view(), name='order-invoice'),
    path('orders/<int:order_id>/track/', views.OrderTrackingView.as_view(), name='order-tracking'),
    path('orders/<int:order_id>/return/', views.CreateReturnRequestView.as_view(), name='create-return'),
    
    # Search URLs
    path('search/', views.ProductSearchView.as_view(), name='product-search'),
    path('search/suggestions/', views.SearchSuggestionsView.as_view(), name='search-suggestions'),
    
    # Review URLs
    path('reviews/', views.ReviewListView.as_view(), name='review-list'),
    path('reviews/<int:review_id>/', views.ReviewDetailView.as_view(), name='review-detail'),
    path('reviews/<int:review_id>/helpful/', views.MarkReviewHelpfulView.as_view(), name='mark-review-helpful'),
    
    # Customer URLs
    path('customer/orders/', views.CustomerOrdersView.as_view(), name='customer-orders'),
    path('customer/addresses/', views.CustomerAddressListView.as_view(), name='customer-addresses'),
    path('customer/wishlist/', views.WishlistView.as_view(), name='wishlist'),
    path('customer/reviews/', views.CustomerReviewsView.as_view(), name='customer-reviews'),
    path('customer/return-requests/', views.CustomerReturnRequestsView.as_view(), name='customer-returns'),
    
    # Admin URLs
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/products/', views.AdminProductListView.as_view(), name='admin-products'),
    path('admin/orders/', views.AdminOrderListView.as_view(), name='admin-orders'),
    path('admin/customers/', views.AdminCustomerListView.as_view(), name='admin-customers'),
    path('admin/analytics/', views.AdminAnalyticsView.as_view(), name='admin-analytics'),
    path('admin/coupons/', views.AdminCouponListView.as_view(), name='admin-coupons'),
    path('admin/returns/', views.AdminReturnRequestListView.as_view(), name='admin-returns'),
    
    # Webhook URLs
    path('webhooks/stripe/', stripe.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('webhooks/paypal/', paypal.PayPalWebhookView.as_view(), name='paypal-webhook'),
    
    # Utility URLs
    path('validate-coupon/', views.ValidateCouponView.as_view(), name='validate-coupon'),
    path('shipping-rates/', views.CalculateShippingRatesView.as_view(), name='calculate-shipping-rates'),
    path('tax-calculation/', views.CalculateTaxView.as_view(), name='calculate-tax'),
    
    # Export URLs
    path('export/products/', views.ExportProductsView.as_view(), name='export-products'),
    path('export/orders/', views.ExportOrdersView.as_view(), name='export-orders'),
    path('export/customers/', views.ExportCustomersView.as_view(), name='export-customers'),
]
