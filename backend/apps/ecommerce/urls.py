# apps/ecommerce/urls.py

"""
URL configuration for e-commerce module
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import api

app_name = 'ecommerce'

# API Router for DRF ViewSets
router = DefaultRouter()
router.register('products', api.ProductViewSet, basename='api-products')
router.register('collections', api.CollectionViewSet, basename='api-collections')
router.register('cart', api.CartViewSet, basename='api-cart')
router.register('orders', api.OrderViewSet, basename='api-orders')
router.register('reviews', api.ReviewViewSet, basename='api-reviews')
router.register('discounts', api.DiscountViewSet, basename='api-discounts')
router.register('shipping', api.ShippingViewSet, basename='api-shipping')
router.register('analytics', api.AnalyticsViewSet, basename='api-analytics')

# Main URL patterns
urlpatterns = [
    # Home and storefront
    path('', views.StorefrontHomeView.as_view(), name='home'),
    path('search/', views.ProductSearchView.as_view(), name='search'),
    
    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<slug:slug>/reviews/', views.ProductReviewListView.as_view(), name='product_reviews'),
    path('products/<slug:slug>/reviews/add/', views.AddProductReviewView.as_view(), name='add_review'),
    
    # Collections
    path('collections/', views.CollectionListView.as_view(), name='collection_list'),
    path('collections/<slug:handle>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    
    # Cart and Checkout
    path('cart/', views.CartDetailView.as_view(), name='cart_detail'),
    path('cart/add/', views.AddToCartView.as_view(), name='add_to_cart'),
    path('cart/update/', views.UpdateCartView.as_view(), name='update_cart'),
    path('cart/remove/', views.RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear_cart'),
    
    # Checkout process
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('checkout/shipping/', views.CheckoutShippingView.as_view(), name='checkout_shipping'),
    path('checkout/payment/', views.CheckoutPaymentView.as_view(), name='checkout_payment'),
    path('checkout/review/', views.CheckoutReviewView.as_view(), name='checkout_review'),
    path('checkout/complete/', views.CheckoutCompleteView.as_view(), name='checkout_complete'),
    
    # Orders
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/<str:order_number>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:order_number>/track/', views.OrderTrackingView.as_view(), name='order_tracking'),
    path('orders/<str:order_number>/invoice/', views.OrderInvoiceView.as_view(), name='order_invoice'),
    path('orders/<str:order_number>/cancel/', views.CancelOrderView.as_view(), name='cancel_order'),
    
    # Wishlist
    path('wishlist/', views.WishlistView.as_view(), name='wishlist'),
    path('wishlist/add/', views.AddToWishlistView.as_view(), name='add_to_wishlist'),
    path('wishlist/remove/', views.RemoveFromWishlistView.as_view(), name='remove_from_wishlist'),
    path('wishlists/shared/<uuid:token>/', views.SharedWishlistView.as_view(), name='shared_wishlist'),
    
    # Customer Account
    path('account/', views.CustomerAccountView.as_view(), name='customer_account'),
    path('account/profile/', views.CustomerProfileView.as_view(), name='customer_profile'),
    path('account/addresses/', views.CustomerAddressesView.as_view(), name='customer_addresses'),
    path('account/orders/', views.CustomerOrdersView.as_view(), name='customer_orders'),
    path('account/reviews/', views.CustomerReviewsView.as_view(), name='customer_reviews'),
    path('account/wishlist/', views.CustomerWishlistView.as_view(), name='customer_wishlist'),
    
    # Returns and Refunds
    path('returns/', views.ReturnRequestListView.as_view(), name='return_list'),
    path('returns/create/<str:order_number>/', views.CreateReturnRequestView.as_view(), name='create_return'),
    path('returns/<int:pk>/', views.ReturnRequestDetailView.as_view(), name='return_detail'),
    
    # Gift Cards
    path('gift-cards/', views.GiftCardListView.as_view(), name='gift_card_list'),
    path('gift-cards/check/', views.CheckGiftCardView.as_view(), name='check_gift_card'),
    path('gift-cards/<str:code>/', views.GiftCardDetailView.as_view(), name='gift_card_detail'),
    
    # Subscriptions
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription_list'),
    path('subscriptions/<int:pk>/', views.SubscriptionDetailView.as_view(), name='subscription_detail'),
    path('subscriptions/<int:pk>/pause/', views.PauseSubscriptionView.as_view(), name='pause_subscription'),
    path('subscriptions/<int:pk>/cancel/', views.CancelSubscriptionView.as_view(), name='cancel_subscription'),
    
    # Compare Products
    path('compare/', views.ProductCompareView.as_view(), name='product_compare'),
    path('compare/add/<int:product_id>/', views.AddToCompareView.as_view(), name='add_to_compare'),
    path('compare/remove/<int:product_id>/', views.RemoveFromCompareView.as_view(), name='remove_from_compare'),
    
    # AJAX endpoints
    path('ajax/product-variants/', views.ProductVariantsAjaxView.as_view(), name='ajax_product_variants'),
    path('ajax/shipping-rates/', views.ShippingRatesAjaxView.as_view(), name='ajax_shipping_rates'),
    path('ajax/apply-coupon/', views.ApplyCouponAjaxView.as_view(), name='ajax_apply_coupon'),
    path('ajax/remove-coupon/', views.RemoveCouponAjaxView.as_view(), name='ajax_remove_coupon'),
    path('ajax/update-quantity/', views.UpdateQuantityAjaxView.as_view(), name='ajax_update_quantity'),
    
    # Webhook endpoints
    path('webhooks/payment/', views.PaymentWebhookView.as_view(), name='payment_webhook'),
    path('webhooks/shipping/', views.ShippingWebhookView.as_view(), name='shipping_webhook'),
    path('webhooks/inventory/', views.InventoryWebhookView.as_view(), name='inventory_webhook'),
    
    # Admin and Management
    path('admin/', include([
        path('', views.AdminDashboardView.as_view(), name='admin_dashboard'),
        path('products/', views.AdminProductListView.as_view(), name='admin_product_list'),
        path('products/add/', views.AdminProductCreateView.as_view(), name='admin_product_create'),
        path('products/<int:pk>/', views.AdminProductDetailView.as_view(), name='admin_product_detail'),
        path('products/<int:pk>/edit/', views.AdminProductUpdateView.as_view(), name='admin_product_update'),
        path('products/<int:pk>/delete/', views.AdminProductDeleteView.as_view(), name='admin_product_delete'),
        
        path('collections/', views.AdminCollectionListView.as_view(), name='admin_collection_list'),
        path('collections/add/', views.AdminCollectionCreateView.as_view(), name='admin_collection_create'),
        path('collections/<int:pk>/', views.AdminCollectionDetailView.as_view(), name='admin_collection_detail'),
        path('collections/<int:pk>/edit/', views.AdminCollectionUpdateView.as_view(), name='admin_collection_update'),
        
        path('orders/', views.AdminOrderListView.as_view(), name='admin_order_list'),
        path('orders/<str:order_number>/', views.AdminOrderDetailView.as_view(), name='admin_order_detail'),
        path('orders/<str:order_number>/fulfill/', views.AdminFulfillOrderView.as_view(), name='admin_fulfill_order'),
        path('orders/<str:order_number>/refund/', views.AdminRefundOrderView.as_view(), name='admin_refund_order'),
        
        path('customers/', views.AdminCustomerListView.as_view(), name='admin_customer_list'),
        path('customers/<int:pk>/', views.AdminCustomerDetailView.as_view(), name='admin_customer_detail'),
        
        path('analytics/', views.AdminAnalyticsView.as_view(), name='admin_analytics'),
        path('reports/', views.AdminReportsView.as_view(), name='admin_reports'),
        path('settings/', views.AdminSettingsView.as_view(), name='admin_settings'),
        
        path('discounts/', views.AdminDiscountListView.as_view(), name='admin_discount_list'),
        path('discounts/add/', views.AdminDiscountCreateView.as_view(), name='admin_discount_create'),
        path('discounts/<int:pk>/', views.AdminDiscountDetailView.as_view(), name='admin_discount_detail'),
        
        path('shipping/', views.AdminShippingView.as_view(), name='admin_shipping'),
        path('taxes/', views.AdminTaxesView.as_view(), name='admin_taxes'),
        path('payments/', views.AdminPaymentsView.as_view(), name='admin_payments'),
        
        path('import/', views.AdminImportView.as_view(), name='admin_import'),
        path('export/', views.AdminExportView.as_view(), name='admin_export'),
    ])),
    
    # API endpoints
    path('api/v1/', include([
        path('', include(router.urls)),
        
        # Additional API endpoints not covered by viewsets
        path('settings/', api.EcommerceSettingsAPIView.as_view(), name='api_settings'),
        path('currencies/', api.CurrencyListAPIView.as_view(), name='api_currencies'),
        path('countries/', api.CountryListAPIView.as_view(), name='api_countries'),
        path('states/', api.StateListAPIView.as_view(), name='api_states'),
        
        # Cart specific endpoints
        path('cart/session/', api.SessionCartAPIView.as_view(), name='api_session_cart'),
        path('cart/merge/', api.MergeCartAPIView.as_view(), name='api_merge_cart'),
        path('cart/estimate-shipping/', api.EstimateShippingAPIView.as_view(), name='api_estimate_shipping'),
        path('cart/apply-discount/', api.ApplyDiscountAPIView.as_view(), name='api_apply_discount'),
        
        # Product specific endpoints
        path('products/search/', api.ProductSearchAPIView.as_view(), name='api_product_search'),
        path('products/trending/', api.TrendingProductsAPIView.as_view(), name='api_trending_products'),
        path('products/recommendations/', api.ProductRecommendationsAPIView.as_view(), name='api_recommendations'),
        path('products/<int:pk>/related/', api.RelatedProductsAPIView.as_view(), name='api_related_products'),
        path('products/<int:pk>/variants/', api.ProductVariantsAPIView.as_view(), name='api_product_variants'),
        
        # Order specific endpoints
        path('orders/guest-lookup/', api.GuestOrderLookupAPIView.as_view(), name='api_guest_order_lookup'),
        path('orders/<int:pk>/tracking/', api.OrderTrackingAPIView.as_view(), name='api_order_tracking'),
        path('orders/<int:pk>/cancel/', api.CancelOrderAPIView.as_view(), name='api_cancel_order'),
        
        # Review endpoints
        path('reviews/moderate/', api.ModerateReviewsAPIView.as_view(), name='api_moderate_reviews'),
        path('reviews/<int:pk>/vote/', api.VoteReviewAPIView.as_view(), name='api_vote_review'),
        
        # Analytics endpoints
        path('analytics/dashboard/', api.AnalyticsDashboardAPIView.as_view(), name='api_analytics_dashboard'),
        path('analytics/sales/', api.SalesAnalyticsAPIView.as_view(), name='api_sales_analytics'),
        path('analytics/products/', api.ProductAnalyticsAPIView.as_view(), name='api_product_analytics'),
        path('analytics/customers/', api.CustomerAnalyticsAPIView.as_view(), name='api_customer_analytics'),
        
        # Inventory integration
        path('inventory/sync/', api.InventorySyncAPIView.as_view(), name='api_inventory_sync'),
        path('inventory/check/', api.InventoryCheckAPIView.as_view(), name='api_inventory_check'),
        
        # Notification endpoints
        path('notifications/', api.NotificationListAPIView.as_view(), name='api_notifications'),
        path('notifications/<int:pk>/read/', api.MarkNotificationReadAPIView.as_view(), name='api_mark_notification_read'),
        
        # Wishlist endpoints
        path('wishlists/', api.WishlistAPIView.as_view(), name='api_wishlists'),
        path('wishlists/<int:pk>/share/', api.ShareWishlistAPIView.as_view(), name='api_share_wishlist'),
        
        # Subscription endpoints
        path('subscriptions/plans/', api.SubscriptionPlanListAPIView.as_view(), name='api_subscription_plans'),
        path('subscriptions/<int:pk>/billing/', api.SubscriptionBillingAPIView.as_view(), name='api_subscription_billing'),
        
        # Gift card endpoints
        path('gift-cards/validate/', api.ValidateGiftCardAPIView.as_view(), name='api_validate_gift_card'),
        path('gift-cards/balance/', api.GiftCardBalanceAPIView.as_view(), name='api_gift_card_balance'),
        
        # Return endpoints
        path('returns/reasons/', api.ReturnReasonsAPIView.as_view(), name='api_return_reasons'),
        path('returns/<int:pk>/status/', api.UpdateReturnStatusAPIView.as_view(), name='api_update_return_status'),
        
        # Digital products
        path('digital/downloads/', api.DigitalDownloadsAPIView.as_view(), name='api_digital_downloads'),
        path('digital/licenses/', api.LicenseKeysAPIView.as_view(), name='api_license_keys'),
        
        # Import/Export
        path('import/products/', api.ImportProductsAPIView.as_view(), name='api_import_products'),
        path('export/orders/', api.ExportOrdersAPIView.as_view(), name='api_export_orders'),
        path('export/customers/', api.ExportCustomersAPIView.as_view(), name='api_export_customers'),
        
        # Bulk operations
        path('bulk/products/update/', api.BulkUpdateProductsAPIView.as_view(), name='api_bulk_update_products'),
        path('bulk/orders/fulfill/', api.BulkFulfillOrdersAPIView.as_view(), name='api_bulk_fulfill_orders'),
        
        # Health check
        path('health/', api.HealthCheckAPIView.as_view(), name='api_health_check'),
    ])),
    
    # SEO and Marketing
    path('sitemap.xml', views.SitemapView.as_view(), name='sitemap'),
    path('robots.txt', views.RobotsView.as_view(), name='robots'),
    path('feeds/products.rss', views.ProductFeedView.as_view(), name='product_feed'),
    path('feeds/offers.rss', views.OfferFeedView.as_view(), name='offer_feed'),
    
    # Social Commerce
    path('social/facebook/', views.FacebookCatalogView.as_view(), name='facebook_catalog'),
    path('social/instagram/', views.InstagramShoppingView.as_view(), name='instagram_shopping'),
    path('social/pinterest/', views.PinterestCatalogView.as_view(), name='pinterest_catalog'),
    
    # Progressive Web App
    path('manifest.json', views.WebAppManifestView.as_view(), name='manifest'),
    path('sw.js', views.ServiceWorkerView.as_view(), name='service_worker'),
    
    # Special pages
    path('sale/', views.SaleView.as_view(), name='sale'),
    path('new-arrivals/', views.NewArrivalsView.as_view(), name='new_arrivals'),
    path('best-sellers/', views.BestSellersView.as_view(), name='best_sellers'),
    path('clearance/', views.ClearanceView.as_view(), name='clearance'),
    
    # Legal and Policy pages
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('return-policy/', views.ReturnPolicyView.as_view(), name='return_policy'),
    path('shipping-policy/', views.ShippingPolicyView.as_view(), name='shipping_policy'),
    
    # Contact and Support
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('size-guide/', views.SizeGuideView.as_view(), name='size_guide'),
    path('track-order/', views.TrackOrderView.as_view(), name='track_order'),
    
    # Newsletter and Marketing
    path('newsletter/subscribe/', views.NewsletterSubscribeView.as_view(), name='newsletter_subscribe'),
    path('newsletter/unsubscribe/', views.NewsletterUnsubscribeView.as_view(), name='newsletter_unsubscribe'),
    
    # Error handling
    path('errors/404/', views.Error404View.as_view(), name='error_404'),
    path('errors/500/', views.Error500View.as_view(), name='error_500'),
]

# Add patterns for shared carts
urlpatterns += [
    path('shared/cart/<uuid:token>/', views.SharedCartView.as_view(), name='shared_cart'),
]