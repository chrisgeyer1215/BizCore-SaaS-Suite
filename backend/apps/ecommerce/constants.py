from django.db import models


class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    PROCESSING = 'PROCESSING', 'Processing'
    SHIPPED = 'SHIPPED', 'Shipped'
    DELIVERED = 'DELIVERED', 'Delivered'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REFUNDED = 'REFUNDED', 'Refunded'
    FAILED = 'FAILED', 'Failed'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PAID = 'PAID', 'Paid'
    PARTIAL = 'PARTIAL', 'Partially Paid'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ProductStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'
    ARCHIVED = 'ARCHIVED', 'Archived'


class CartStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    ABANDONED = 'ABANDONED', 'Abandoned'
    COMPLETED = 'COMPLETED', 'Completed'
    EXPIRED = 'EXPIRED', 'Expired'


class CouponType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount'
    FREE_SHIPPING = 'FREE_SHIPPING', 'Free Shipping'
    BUY_X_GET_Y = 'BUY_X_GET_Y', 'Buy X Get Y'


class PaymentGateway(models.TextChoices):
    STRIPE = 'STRIPE', 'Stripe'
    PAYPAL = 'PAYPAL', 'PayPal'
    RAZORPAY = 'RAZORPAY', 'Razorpay'
    SQUARE = 'SQUARE', 'Square'


# Cache Keys
CACHE_KEYS = {
    'PRODUCT_DETAIL': 'ecommerce:product:{}',
    'PRODUCT_LIST': 'ecommerce:products:{}:{}',
    'COLLECTION_PRODUCTS': 'ecommerce:collection:{}:products',
    'CART_DETAIL': 'ecommerce:cart:{}',
    'SHIPPING_RATES': 'ecommerce:shipping:{}:{}',
    'COUPON_VALIDATION': 'ecommerce:coupon:{}',
}

# Email Templates
EMAIL_TEMPLATES = {
    'ORDER_CONFIRMATION': 'ecommerce/emails/order_confirmation.html',
    'SHIPPING_NOTIFICATION': 'ecommerce/emails/shipping_notification.html',
    'DELIVERY_NOTIFICATION': 'ecommerce/emails/delivery_notification.html',
    'CART_RECOVERY': 'ecommerce/emails/cart_recovery.html',
    'REVIEW_REQUEST': 'ecommerce/emails/review_request.html',
}

# Default Values
DEFAULTS = {
    'CURRENCY': 'USD',
    'TAX_RATE': 0.0,
    'SHIPPING_RATE': 0.0,
    'LOW_STOCK_THRESHOLD': 10,
    'CART_EXPIRY_DAYS': 30,
    'SESSION_TIMEOUT_HOURS': 24,
    'MAX_CART_ITEMS': 100,
    'MAX_PRODUCT_IMAGES': 10,
}

# Pagination
PAGINATION = {
    'PRODUCTS_PER_PAGE': 20,
    'ORDERS_PER_PAGE': 25,
    'REVIEWS_PER_PAGE': 10,
}

# File Upload Limits
UPLOAD_LIMITS = {
    'MAX_IMAGE_SIZE': 5 * 1024 * 1024,  # 5MB
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_IMAGE_FORMATS': ['jpg', 'jpeg', 'png', 'webp'],
    'ALLOWED_FILE_FORMATS': ['pdf', 'doc', 'docx'],
}
