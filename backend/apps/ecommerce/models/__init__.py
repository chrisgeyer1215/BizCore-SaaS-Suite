# apps/ecommerce/models/__init__.py

"""
E-commerce models for SaaS-AICE platform
Multi-tenant e-commerce functionality with Shopify-like features
"""

# Import only available model modules to avoid runtime ImportError
from .base import *  # noqa: F401,F403
from .settings import *  # noqa: F401,F403
from .products import *  # noqa: F401,F403
from .collections import *  # noqa: F401,F403
from .cart import *  # noqa: F401,F403
from .managers import *  # noqa: F401,F403

# Optional modules (not yet implemented) – ignore if missing
for _module in (
    'orders', 'payments', 'shipping', 'discounts', 'reviews', 'customers',
    'analytics', 'digital', 'subscriptions', 'gift_cards', 'returns', 'channels',
):
    try:
        exec(f"from .{_module} import *")  # noqa: E402,S102
    except Exception:  # Module not available yet
        pass

# Export only symbols that are guaranteed to exist in the current codebase
__all__ = [
    # Settings
    'EcommerceSettings',

    # Products & Collections
    'EcommerceProduct', 'ProductVariant', 'ProductOption', 'ProductOptionValue',
    'ProductImage', 'ProductSEO', 'ProductMetric', 'ProductTag',
    'ProductBundle', 'BundleItem',
    'Collection', 'CollectionProduct', 'CollectionRule', 'CollectionImage',
    'CollectionSEO', 'CollectionMetrics',

    # Cart & Wishlist
    'Cart', 'CartItem', 'Wishlist', 'WishlistItem', 'SavedForLater',
    'CartAbandonmentEvent', 'CartShare',

    # Managers & Querysets
    'PublishedProductManager', 'OrderQuerySet', 'OrderManager', 'CartManager', 'ReviewManager',
]