"""
Views for the e-commerce module.
Organized by functionality: products, collections, cart, checkout, orders, etc.
"""

# Base views and mixins
from .base import *  # noqa: F401,F403
from .mixins import *  # noqa: F401,F403

# Core functionality views
from .products import *  # noqa: F401,F403
from .collections import *  # noqa: F401,F403
from .cart import *  # noqa: F401,F403

# Note: The following view modules will be implemented:
# - checkout.py - Checkout process views
# - orders.py - Order management views
# - account.py - Customer account views
# - wishlist.py - Wishlist management views
# - reviews.py - Product review views
# - search.py - Product search views
# - payments.py - Payment processing views
# - shipping.py - Shipping and fulfillment views
# - ajax.py - AJAX request handlers
# - webhooks.py - Webhook handlers
# - admin.py - Admin custom views
