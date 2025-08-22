"""
Forms for the e-commerce module.
Split by concern: products, collections, cart, checkout, orders, reviews, admin, etc.
"""

# Core forms for existing models
from .products import *  # noqa: F401,F403
from .collections import *  # noqa: F401,F403
from .cart import *  # noqa: F401,F403
from .admin import *  # noqa: F401,F403
from .utils import *  # noqa: F401,F403

# Enhanced forms for core functionality
from .checkout import *  # noqa: F401,F403
from .orders import *  # noqa: F401,F403
from .reviews import *  # noqa: F401,F403
from .customers import *  # noqa: F401,F403
from .discounts import *  # noqa: F401,F403
from .shipping import *  # noqa: F401,F403

# Placeholder forms for future models
from .stubs import *  # noqa: F401,F403

# Note: The following form modules are placeholders and will be implemented
# when their corresponding models are created:
# - digital, subscriptions, returns

