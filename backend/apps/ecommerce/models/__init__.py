# apps/ecommerce/models/__init__.py

"""
E-commerce models for SaaS-AICE platform
Multi-tenant e-commerce functionality with Shopify-like features
"""

# Import all models to make them available when importing from models
from .base import *
from .settings import *
from .products import *
from .collections import *
from .cart import *
from .orders import *
from .payments import *
from .shipping import *
from .discounts import *
from .reviews import *
from .customers import *
from .analytics import *
from .digital import *
from .subscriptions import *
from .gift_cards import *
from .returns import *
from .channels import *
from .managers import *

# Define what gets imported with "from models import *"
__all__ = [
    # Settings
    'EcommerceSettings',
    
    # Products & Collections
    'EcommerceProduct', 'ProductVariant', 'ProductOption', 'ProductOptionValue',
    'Collection', 'CollectionProduct', 'ProductImage', 'ProductSEO',
    'ProductTag', 'ProductBundle', 'BundleItem',
    
    # Cart & Wishlist
    'Cart', 'CartItem', 'Wishlist', 'WishlistItem', 'SavedForLater',
    
    # Orders
    'Order', 'OrderItem', 'OrderStatusHistory', 'OrderNote',
    'OrderShipping', 'OrderFulfillment', 'FulfillmentItem',
    
    # Payments
    'PaymentSession', 'PaymentTransaction', 'PaymentMethod',
    'RefundTransaction', 'PaymentGatewayConfig',
    
    # Shipping
    'ShippingZone', 'ShippingMethod', 'ShippingRate',
    'ShippingProfile', 'ShippingRestriction',
    
    # Discounts & Coupons
    'Discount', 'CouponCode', 'CouponUsage', 'DiscountProduct',
    'DiscountCollection', 'CustomerDiscountUsage',
    
    # Reviews & Ratings
    'ProductReview', 'ProductQuestion', 'ReviewResponse',
    'ReviewVote', 'ReviewMedia',
    
    # Customer Management
    'CustomerAddress', 'CustomerGroup', 'CustomerGroupMembership',
    'CustomerNote', 'CustomerTag', 'StorefrontCustomer',
    
    # Analytics
    'ProductAnalytics', 'AbandonedCart', 'SalesReport',
    'CustomerAnalytics', 'SearchQuery', 'ProductView',
    
    # Digital Products
    'DigitalProduct', 'DigitalDownload', 'DownloadAttempt',
    'LicenseKey', 'DigitalAsset',
    
    # Subscriptions
    'SubscriptionPlan', 'Subscription', 'SubscriptionItem',
    'SubscriptionCycle', 'SubscriptionPause', 'SubscriptionChange',
    
    # Gift Cards
    'GiftCard', 'GiftCardTransaction', 'GiftCardDesign',
    
    # Returns & Refunds
    'ReturnRequest', 'ReturnRequestItem', 'RefundRequest',
    'ReturnReason', 'ReturnPolicy',
    
    # Multi-channel
    'SalesChannel', 'ChannelProduct', 'ChannelSync',
    'MarketplaceIntegration', 'ExternalListing',
    
    # Managers & Querysets
    'PublishedProductManager', 'OrderQuerySet', 'OrderManager',
    'CartManager', 'ReviewManager',
]