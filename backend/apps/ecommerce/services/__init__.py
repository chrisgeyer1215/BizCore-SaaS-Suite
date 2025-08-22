"""
Services for the e-commerce module.
Business logic layer for cart, orders, payments, shipping, etc.
"""

# Base service classes
from .base import *  # noqa: F401,F403

# Core business logic services
from .order import *  # noqa: F401,F403

# Note: The following service modules will be implemented:
# - cart.py - Shopping cart operations
# - payments.py - Payment processing
# - shipping.py - Shipping and fulfillment
# - inventory.py - Inventory management
# - notifications.py - Notification handling
# - analytics.py - Analytics and reporting
# - discounts.py - Discount and coupon logic
# - recommendations.py - Product recommendations
# - search.py - Search functionality
# - emails.py - Email service
# - sms.py - SMS service
# - exports.py - Data export
# - imports.py - Data import
# - digital.py - Digital product handling
# - subscriptions.py - Subscription management
# - gift_cards.py - Gift card operations
# - returns.py - Return and refund processing
