# apps/ecommerce/constants.py

"""
Constants for the e-commerce module
"""

# Product status choices
PRODUCT_STATUS_CHOICES = [
    ('DRAFT', 'Draft'),
    ('PUBLISHED', 'Published'),
    ('ARCHIVED', 'Archived'),
    ('HIDDEN', 'Hidden'),
]

# Product type choices
PRODUCT_TYPE_CHOICES = [
    ('PHYSICAL', 'Physical Product'),
    ('DIGITAL', 'Digital Product'),
    ('SERVICE', 'Service'),
    ('SUBSCRIPTION', 'Subscription'),
    ('GIFT_CARD', 'Gift Card'),
    ('BUNDLE', 'Product Bundle'),
    ('VARIABLE', 'Variable Product'),
]

# Order status choices
ORDER_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('CONFIRMED', 'Confirmed'),
    ('PROCESSING', 'Processing'),
    ('SHIPPED', 'Shipped'),
    ('DELIVERED', 'Delivered'),
    ('CANCELLED', 'Cancelled'),
    ('REFUNDED', 'Refunded'),
    ('ON_HOLD', 'On Hold'),
    ('PARTIALLY_SHIPPED', 'Partially Shipped'),
    ('RETURN_REQUESTED', 'Return Requested'),
    ('RETURNED', 'Returned'),
]

# Payment status choices
PAYMENT_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('PAID', 'Paid'),
    ('PARTIALLY_PAID', 'Partially Paid'),
    ('FAILED', 'Failed'),
    ('CANCELLED', 'Cancelled'),
    ('REFUNDED', 'Refunded'),
    ('AUTHORIZED', 'Authorized'),
]

# Fulfillment status choices
FULFILLMENT_STATUS_CHOICES = [
    ('UNFULFILLED', 'Unfulfilled'),
    ('PARTIALLY_FULFILLED', 'Partially Fulfilled'),
    ('FULFILLED', 'Fulfilled'),
    ('RESTOCKED', 'Restocked'),
]

# Currency choices
CURRENCY_CHOICES = [
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    ('CAD', 'Canadian Dollar'),
    ('AUD', 'Australian Dollar'),
    ('JPY', 'Japanese Yen'),
    ('CNY', 'Chinese Yuan'),
    ('INR', 'Indian Rupee'),
    ('BRL', 'Brazilian Real'),
    ('MXN', 'Mexican Peso'),
]

# Payment method choices
PAYMENT_METHOD_CHOICES = [
    ('CREDIT_CARD', 'Credit Card'),
    ('DEBIT_CARD', 'Debit Card'),
    ('PAYPAL', 'PayPal'),
    ('APPLE_PAY', 'Apple Pay'),
    ('GOOGLE_PAY', 'Google Pay'),
    ('BANK_TRANSFER', 'Bank Transfer'),
    ('COD', 'Cash on Delivery'),
    ('CRYPTO', 'Cryptocurrency'),
    ('GIFT_CARD', 'Gift Card'),
    ('STORE_CREDIT', 'Store Credit'),
]

# Discount type choices
DISCOUNT_TYPE_CHOICES = [
    ('PERCENTAGE', 'Percentage'),
    ('FIXED_AMOUNT', 'Fixed Amount'),
    ('FREE_SHIPPING', 'Free Shipping'),
    ('BUY_X_GET_Y', 'Buy X Get Y'),
    ('BOGO', 'Buy One Get One'),
]

# Cart status choices
CART_STATUS_CHOICES = [
    ('ACTIVE', 'Active'),
    ('ABANDONED', 'Abandoned'),
    ('COMPLETED', 'Completed'),
    ('EXPIRED', 'Expired'),
    ('MERGED', 'Merged'),
]

# Collection type choices
COLLECTION_TYPE_CHOICES = [
    ('MANUAL', 'Manual Collection'),
    ('AUTOMATIC', 'Automatic Collection'),
    ('SMART', 'Smart Collection'),
    ('CATEGORY', 'Category'),
    ('BRAND', 'Brand Collection'),
    ('SEASONAL', 'Seasonal Collection'),
    ('FEATURED', 'Featured Collection'),
    ('SALE', 'Sale Collection'),
]

# Review status choices
REVIEW_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]

# Shipping status choices
SHIPPING_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('PROCESSING', 'Processing'),
    ('SHIPPED', 'Shipped'),
    ('IN_TRANSIT', 'In Transit'),
    ('OUT_FOR_DELIVERY', 'Out for Delivery'),
    ('DELIVERED', 'Delivered'),
    ('FAILED_DELIVERY', 'Failed Delivery'),
    ('RETURNED_TO_SENDER', 'Returned to Sender'),
]

# Return status choices
RETURN_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
    ('RECEIVED', 'Received'),
    ('PROCESSING', 'Processing'),
    ('COMPLETED', 'Completed'),
    ('CANCELLED', 'Cancelled'),
]

# Subscription status choices
SUBSCRIPTION_STATUS_CHOICES = [
    ('ACTIVE', 'Active'),
    ('PAUSED', 'Paused'),
    ('CANCELLED', 'Cancelled'),
    ('EXPIRED', 'Expired'),
    ('PENDING', 'Pending'),
]

# Email template types
EMAIL_TEMPLATE_TYPES = [
    ('ORDER_CONFIRMATION', 'Order Confirmation'),
    ('ORDER_SHIPPED', 'Order Shipped'),
    ('ORDER_DELIVERED', 'Order Delivered'),
    ('ORDER_CANCELLED', 'Order Cancelled'),
    ('PAYMENT_RECEIVED', 'Payment Received'),
    ('REFUND_PROCESSED', 'Refund Processed'),
    ('PASSWORD_RESET', 'Password Reset'),
    ('ACCOUNT_WELCOME', 'Account Welcome'),
    ('ABANDONED_CART', 'Abandoned Cart'),
    ('BACK_IN_STOCK', 'Back in Stock'),
    ('NEWSLETTER', 'Newsletter'),
    ('PROMOTIONAL', 'Promotional'),
]

# Default settings
DEFAULT_CURRENCY = 'USD'
DEFAULT_TAX_RATE = 0.08
DEFAULT_SHIPPING_COST = 10.00
DEFAULT_FREE_SHIPPING_THRESHOLD = 50.00
DEFAULT_CART_ABANDONMENT_HOURS = 24
DEFAULT_CART_EXPIRY_DAYS = 30
DEFAULT_PRODUCTS_PER_PAGE = 24
DEFAULT_REVIEWS_PER_PAGE = 10
DEFAULT_ORDERS_PER_PAGE = 20

# File upload settings
MAX_PRODUCT_IMAGES = 10
MAX_IMAGE_SIZE_MB = 5
ALLOWED_IMAGE_FORMATS = ['JPEG', 'JPG', 'PNG', 'WEBP']
THUMBNAIL_SIZES = {
    'small': (150, 150),
    'medium': (300, 300),
    'large': (600, 600),
    'xlarge': (1200, 1200),
}

# Search settings
SEARCH_RESULTS_PER_PAGE = 20
MAX_SEARCH_QUERY_LENGTH = 100
SEARCH_MIN_QUERY_LENGTH = 2

# Cache settings
CACHE_TIMEOUT_PRODUCTS = 3600  # 1 hour
CACHE_TIMEOUT_COLLECTIONS = 1800  # 30 minutes
CACHE_TIMEOUT_CART = 300  # 5 minutes
CACHE_TIMEOUT_SETTINGS = 7200  # 2 hours

# Rate limiting
API_RATE_LIMIT_PER_HOUR = 1000
CART_UPDATE_RATE_LIMIT = 60  # per minute
REVIEW_SUBMISSION_RATE_LIMIT = 5  # per hour

# Inventory policies
INVENTORY_POLICIES = [
    ('DENY', 'Deny purchases when out of stock'),
    ('CONTINUE', 'Continue selling when out of stock'),
]

# Fulfillment services
FULFILLMENT_SERVICES = [
    ('MANUAL', 'Manual fulfillment'),
    ('AUTOMATIC', 'Automatic fulfillment'),
    ('THIRD_PARTY', 'Third party fulfillment'),
]

# Tax calculation methods
TAX_CALCULATION_METHODS = [
    ('FLAT_RATE', 'Flat Rate'),
    ('LOCATION_BASED', 'Location Based'),
    ('PRODUCT_BASED', 'Product Based'),
    ('AVALARA', 'Avalara Tax Service'),
    ('TAXJAR', 'TaxJar Service'),
]

# Shipping calculation methods
SHIPPING_CALCULATION_METHODS = [
    ('FLAT_RATE', 'Flat Rate'),
    ('WEIGHT_BASED', 'Weight Based'),
    ('DIMENSION_BASED', 'Dimension Based'),
    ('LOCATION_BASED', 'Location Based'),
    ('CARRIER_CALCULATED', 'Carrier Calculated'),
    ('FREE_SHIPPING', 'Free Shipping'),
]

# Weight units
WEIGHT_UNITS = [
    ('g', 'Grams'),
    ('kg', 'Kilograms'),
    ('oz', 'Ounces'),
    ('lb', 'Pounds'),
]

# Dimension units
DIMENSION_UNITS = [
    ('mm', 'Millimeters'),
    ('cm', 'Centimeters'),
    ('m', 'Meters'),
    ('in', 'Inches'),
    ('ft', 'Feet'),
]

# Analytics periods
ANALYTICS_PERIODS = [
    ('TODAY', 'Today'),
    ('YESTERDAY', 'Yesterday'),
    ('LAST_7_DAYS', 'Last 7 Days'),
    ('LAST_30_DAYS', 'Last 30 Days'),
    ('THIS_MONTH', 'This Month'),
    ('LAST_MONTH', 'Last Month'),
    ('THIS_QUARTER', 'This Quarter'),
    ('LAST_QUARTER', 'Last Quarter'),
    ('THIS_YEAR', 'This Year'),
    ('LAST_YEAR', 'Last Year'),
    ('CUSTOM', 'Custom Range'),
]

# Social media platforms
SOCIAL_PLATFORMS = [
    ('FACEBOOK', 'Facebook'),
    ('INSTAGRAM', 'Instagram'),
    ('TWITTER', 'Twitter'),
    ('LINKEDIN', 'LinkedIn'),
    ('PINTEREST', 'Pinterest'),
    ('YOUTUBE', 'YouTube'),
    ('TIKTOK', 'TikTok'),
]

# Gift card statuses
GIFT_CARD_STATUSES = [
    ('ACTIVE', 'Active'),
    ('USED', 'Used'),
    ('EXPIRED', 'Expired'),
    ('CANCELLED', 'Cancelled'),
]

# Customer group assignment types
CUSTOMER_GROUP_ASSIGNMENT_TYPES = [
    ('MANUAL', 'Manual Assignment'),
    ('AUTOMATIC', 'Automatic Assignment'),
]

# Wishlist visibility options
WISHLIST_VISIBILITY_OPTIONS = [
    ('PRIVATE', 'Private'),
    ('PUBLIC', 'Public'),
    ('SHARED', 'Shared with Link'),
]

# Bundle pricing strategies
BUNDLE_PRICING_STRATEGIES = [
    ('FIXED_PRICE', 'Fixed Bundle Price'),
    ('PERCENTAGE_DISCOUNT', 'Percentage Discount'),
    ('FIXED_DISCOUNT', 'Fixed Amount Discount'),
    ('SUM_OF_PARTS', 'Sum of Individual Prices'),
]

# Notification types
NOTIFICATION_TYPES = [
    ('ORDER_PLACED', 'Order Placed'),
    ('ORDER_UPDATED', 'Order Updated'),
    ('PAYMENT_RECEIVED', 'Payment Received'),
    ('INVENTORY_LOW', 'Low Inventory'),
    ('PRODUCT_REVIEW', 'Product Review'),
    ('CUSTOMER_INQUIRY', 'Customer Inquiry'),
]

# Export formats
EXPORT_FORMATS = [
    ('CSV', 'CSV'),
    ('XLSX', 'Excel'),
    ('JSON', 'JSON'),
    ('XML', 'XML'),
]

# Import sources
IMPORT_SOURCES = [
    ('CSV', 'CSV File'),
    ('XLSX', 'Excel File'),
    ('SHOPIFY', 'Shopify'),
    ('WOOCOMMERCE', 'WooCommerce'),
    ('MAGENTO', 'Magento'),
    ('API', 'API'),
]

# Marketing campaign types
CAMPAIGN_TYPES = [
    ('EMAIL', 'Email Campaign'),
    ('SMS', 'SMS Campaign'),
    ('SOCIAL', 'Social Media'),
    ('PAID_ADS', 'Paid Advertising'),
    ('AFFILIATE', 'Affiliate Marketing'),
]

# SEO priorities
SEO_PRIORITIES = [
    ('HIGH', 'High Priority'),
    ('MEDIUM', 'Medium Priority'),
    ('LOW', 'Low Priority'),
]

# Page types for SEO
PAGE_TYPES = [
    ('PRODUCT', 'Product Page'),
    ('COLLECTION', 'Collection Page'),
    ('HOMEPAGE', 'Homepage'),
    ('BLOG', 'Blog Page'),
    ('STATIC', 'Static Page'),
]