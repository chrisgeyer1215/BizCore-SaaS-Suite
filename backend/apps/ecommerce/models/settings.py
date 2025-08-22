# apps/ecommerce/models/settings.py

"""
E-commerce settings and configuration models
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal

from .base import EcommerceBaseModel, CommonChoices


class EcommerceSettings(EcommerceBaseModel):
    """Enhanced e-commerce configuration per tenant"""
    
    class TaxCalculationMethod(models.TextChoices):
        FLAT_RATE = 'FLAT_RATE', 'Flat Rate'
        LOCATION_BASED = 'LOCATION_BASED', 'Location Based'
        PRODUCT_BASED = 'PRODUCT_BASED', 'Product Based'
        AVALARA = 'AVALARA', 'Avalara Tax Service'
        TAXJAR = 'TAXJAR', 'TaxJar Service'
        
    class ShippingCalculationMethod(models.TextChoices):
        FLAT_RATE = 'FLAT_RATE', 'Flat Rate'
        WEIGHT_BASED = 'WEIGHT_BASED', 'Weight Based'
        DIMENSION_BASED = 'DIMENSION_BASED', 'Dimension Based'
        LOCATION_BASED = 'LOCATION_BASED', 'Location Based'
        CARRIER_CALCULATED = 'CARRIER_CALCULATED', 'Carrier Calculated'
        FREE_SHIPPING = 'FREE_SHIPPING', 'Free Shipping'
        
    class InventoryDeductionMethod(models.TextChoices):
        ON_ORDER = 'ON_ORDER', 'When Order is Placed'
        ON_PAYMENT = 'ON_PAYMENT', 'When Payment is Received'
        ON_FULFILLMENT = 'ON_FULFILLMENT', 'When Order is Fulfilled'
    
    # Store Information
    store_name = models.CharField(max_length=255)
    store_description = models.TextField(blank=True)
    store_email = models.EmailField()
    store_phone = models.CharField(max_length=20, blank=True)
    store_address = models.JSONField(default=dict)
    
    # Store URLs and Social
    store_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Currency Settings
    default_currency = models.CharField(
        max_length=3, 
        choices=CommonChoices.Currency.choices, 
        default=CommonChoices.Currency.USD
    )
    enable_multi_currency = models.BooleanField(default=False)
    supported_currencies = models.JSONField(default=list)
    currency_display_format = models.CharField(
        max_length=20,
        choices=[
            ('SYMBOL_BEFORE', '$10.00'),
            ('SYMBOL_AFTER', '10.00$'),
            ('CODE_BEFORE', 'USD 10.00'),
            ('CODE_AFTER', '10.00 USD'),
        ],
        default='SYMBOL_BEFORE'
    )
    
    # Payment Settings
    primary_payment_gateway = models.CharField(
        max_length=50,
        choices=[
            ('STRIPE', 'Stripe'),
            ('PAYPAL', 'PayPal'),
            ('SQUARE', 'Square'),
            ('AUTHORIZE_NET', 'Authorize.Net'),
            ('SHOPIFY_PAYMENTS', 'Shopify Payments'),
            ('MOLLIE', 'Mollie'),
            ('RAZORPAY', 'Razorpay'),
        ],
        default='STRIPE'
    )
    accepted_payment_methods = models.JSONField(
        default=list,
        help_text="List of accepted payment methods"
    )
    enable_express_checkout = models.BooleanField(default=True)
    enable_guest_checkout = models.BooleanField(default=True)
    require_billing_address = models.BooleanField(default=True)
    
    # Tax Settings
    tax_calculation_method = models.CharField(
        max_length=20,
        choices=TaxCalculationMethod.choices,
        default=TaxCalculationMethod.FLAT_RATE
    )
    default_tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=Decimal('0.0000'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tax_included_in_prices = models.BooleanField(default=False)
    charge_tax_on_shipping = models.BooleanField(default=False)
    
    # Shipping Settings
    shipping_calculation_method = models.CharField(
        max_length=20,
        choices=ShippingCalculationMethod.choices,
        default=ShippingCalculationMethod.FLAT_RATE
    )
    default_shipping_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('10.00')
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    enable_shipping_calculator = models.BooleanField(default=True)
    require_shipping_address = models.BooleanField(default=True)
    
    # Inventory Settings
    track_inventory_by_default = models.BooleanField(default=True)
    allow_overselling = models.BooleanField(default=False)
    inventory_deduction_method = models.CharField(
        max_length=20,
        choices=InventoryDeductionMethod.choices,
        default=InventoryDeductionMethod.ON_PAYMENT
    )
    low_stock_threshold = models.IntegerField(default=10)
    enable_low_stock_alerts = models.BooleanField(default=True)
    
    # Product Settings
    enable_product_reviews = models.BooleanField(default=True)
    require_review_approval = models.BooleanField(default=True)
    enable_product_ratings = models.BooleanField(default=True)
    enable_wishlist = models.BooleanField(default=True)
    enable_product_compare = models.BooleanField(default=True)
    enable_product_recommendations = models.BooleanField(default=True)
    
    # SEO Settings
    enable_seo_friendly_urls = models.BooleanField(default=True)
    auto_generate_meta_descriptions = models.BooleanField(default=True)
    enable_structured_data = models.BooleanField(default=True)
    enable_sitemap_generation = models.BooleanField(default=True)
    
    # Cart & Checkout Settings
    cart_abandonment_threshold_minutes = models.IntegerField(default=60)
    enable_abandoned_cart_recovery = models.BooleanField(default=True)
    persistent_cart_days = models.IntegerField(default=30)
    enable_cart_notifications = models.BooleanField(default=True)
    
    # Order Settings
    order_number_prefix = models.CharField(max_length=10, default='ORD')
    order_number_start = models.PositiveIntegerField(default=1000)
    enable_order_status_emails = models.BooleanField(default=True)
    enable_order_tracking = models.BooleanField(default=True)
    auto_fulfill_digital_orders = models.BooleanField(default=True)
    
    # Customer Settings
    enable_customer_accounts = models.BooleanField(default=True)
    require_account_verification = models.BooleanField(default=False)
    enable_customer_groups = models.BooleanField(default=False)
    enable_loyalty_program = models.BooleanField(default=False)
    
    # Discount & Coupon Settings
    enable_coupons = models.BooleanField(default=True)
    enable_automatic_discounts = models.BooleanField(default=True)
    enable_bulk_discounts = models.BooleanField(default=False)
    enable_loyalty_discounts = models.BooleanField(default=False)
    
    # Analytics Settings
    enable_analytics = models.BooleanField(default=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    enable_conversion_tracking = models.BooleanField(default=True)
    
    # Email Marketing Settings
    enable_email_marketing = models.BooleanField(default=False)
    mailchimp_api_key = models.CharField(max_length=255, blank=True)
    klaviyo_api_key = models.CharField(max_length=255, blank=True)
    
    # Advanced Features
    enable_subscriptions = models.BooleanField(default=False)
    enable_digital_products = models.BooleanField(default=False)
    enable_gift_cards = models.BooleanField(default=False)
    enable_multi_vendor = models.BooleanField(default=False)
    enable_marketplace = models.BooleanField(default=False)
    
    # API & Integration Settings
    enable_rest_api = models.BooleanField(default=True)
    enable_webhooks = models.BooleanField(default=True)
    api_rate_limit = models.IntegerField(default=1000)  # requests per hour
    
    # Security Settings
    enable_ssl_enforcement = models.BooleanField(default=True)
    enable_fraud_protection = models.BooleanField(default=True)
    max_login_attempts = models.IntegerField(default=5)
    session_timeout_minutes = models.IntegerField(default=60)
    
    # Notification Settings
    admin_notification_email = models.EmailField(blank=True)
    enable_new_order_notifications = models.BooleanField(default=True)
    enable_low_stock_notifications = models.BooleanField(default=True)
    enable_customer_notifications = models.BooleanField(default=True)
    
    # Backup & Maintenance
    auto_backup_enabled = models.BooleanField(default=False)
    backup_frequency_days = models.IntegerField(default=7)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    # Legal & Compliance
    privacy_policy_url = models.URLField(blank=True)
    terms_of_service_url = models.URLField(blank=True)
    return_policy_url = models.URLField(blank=True)
    cookie_consent_enabled = models.BooleanField(default=True)
    gdpr_compliance_enabled = models.BooleanField(default=False)
    
    # Localization
    default_language = models.CharField(max_length=10, default='en')
    supported_languages = models.JSONField(default=list)
    default_timezone = models.CharField(max_length=50, default='UTC')
    date_format = models.CharField(max_length=20, default='Y-m-d')
    time_format = models.CharField(max_length=20, default='H:i:s')
    
    # Custom Fields
    custom_settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ecommerce_settings'
        verbose_name = 'E-commerce Settings'
        verbose_name_plural = 'E-commerce Settings'
    
    def __str__(self):
        return f'E-commerce Settings - {self.store_name}'
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Validate tax rate
        if self.default_tax_rate < 0 or self.default_tax_rate > 100:
            raise ValidationError({
                'default_tax_rate': 'Tax rate must be between 0 and 100 percent'
            })
        
        # Validate shipping threshold
        if self.free_shipping_threshold and self.free_shipping_threshold < 0:
            raise ValidationError({
                'free_shipping_threshold': 'Free shipping threshold cannot be negative'
            })
    
    @property
    def formatted_currency_symbol(self):
        """Get formatted currency symbol"""
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CAD': '$',
            'AUD': '$',
            'CNY': '¥',
            'INR': '₹',
            'BRL': 'R$',
            'MXN': '$',
        }
        return currency_symbols.get(self.default_currency, self.default_currency)
    
    def format_price(self, amount):
        """Format price according to settings"""
        symbol = self.formatted_currency_symbol
        
        if self.currency_display_format == 'SYMBOL_BEFORE':
            return f'{symbol}{amount:.2f}'
        elif self.currency_display_format == 'SYMBOL_AFTER':
            return f'{amount:.2f}{symbol}'
        elif self.currency_display_format == 'CODE_BEFORE':
            return f'{self.default_currency} {amount:.2f}'
        elif self.currency_display_format == 'CODE_AFTER':
            return f'{amount:.2f} {self.default_currency}'
        
        return f'{symbol}{amount:.2f}'  # Default format
    
    def is_payment_method_enabled(self, method):
        """Check if payment method is enabled"""
        return method in self.accepted_payment_methods
    
    def is_currency_supported(self, currency):
        """Check if currency is supported"""
        if not self.enable_multi_currency:
            return currency == self.default_currency
        return currency in self.supported_currencies or currency == self.default_currency


class StoreTheme(EcommerceBaseModel):
    """Store theme and appearance settings"""
    
    class ThemeType(models.TextChoices):
        CUSTOM = 'CUSTOM', 'Custom Theme'
        MINIMAL = 'MINIMAL', 'Minimal'
        MODERN = 'MODERN', 'Modern'
        CLASSIC = 'CLASSIC', 'Classic'
        FASHION = 'FASHION', 'Fashion'
        ELECTRONICS = 'ELECTRONICS', 'Electronics'
        FOOD = 'FOOD', 'Food & Beverage'
    
    name = models.CharField(max_length=100)
    theme_type = models.CharField(max_length=20, choices=ThemeType.choices, default=ThemeType.MODERN)
    is_active = models.BooleanField(default=False)
    
    # Colors
    primary_color = models.CharField(max_length=7, default='#007bff')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    accent_color = models.CharField(max_length=7, default='#28a745')
    background_color = models.CharField(max_length=7, default='#ffffff')
    text_color = models.CharField(max_length=7, default='#333333')
    
    # Typography
    primary_font = models.CharField(max_length=100, default='Arial, sans-serif')
    heading_font = models.CharField(max_length=100, default='Arial, sans-serif')
    font_size_base = models.IntegerField(default=16)  # px
    
    # Layout
    container_width = models.IntegerField(default=1200)  # px
    header_style = models.CharField(
        max_length=20,
        choices=[
            ('CLASSIC', 'Classic'),
            ('MINIMAL', 'Minimal'),
            ('CENTERED', 'Centered'),
            ('SIDEBAR', 'Sidebar'),
        ],
        default='CLASSIC'
    )
    
    # Logo and Branding
    logo_image = models.ImageField(upload_to='themes/logos/', blank=True, null=True)
    logo_width = models.IntegerField(default=200)  # px
    favicon = models.ImageField(upload_to='themes/favicons/', blank=True, null=True)
    
    # Custom CSS/JS
    custom_css = models.TextField(blank=True)
    custom_javascript = models.TextField(blank=True)
    custom_head_html = models.TextField(blank=True)
    
    # Theme Settings
    theme_settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ecommerce_store_theme'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'],
                condition=models.Q(is_active=True),
                name='unique_active_theme_per_tenant'
            )
        ]
    
    def __str__(self):
        return f'{self.name} - {self.theme_type}'
    
    def activate(self):
        """Activate this theme and deactivate others"""
        # Deactivate all other themes for this tenant
        StoreTheme.objects.filter(tenant=self.tenant).update(is_active=False)
        # Activate this theme
        self.is_active = True
        self.save()


class EmailTemplate(EcommerceBaseModel):
    """Email template management"""
    
    class TemplateType(models.TextChoices):
        ORDER_CONFIRMATION = 'ORDER_CONFIRMATION', 'Order Confirmation'
        ORDER_SHIPPED = 'ORDER_SHIPPED', 'Order Shipped'
        ORDER_DELIVERED = 'ORDER_DELIVERED', 'Order Delivered'
        ORDER_CANCELLED = 'ORDER_CANCELLED', 'Order Cancelled'
        PAYMENT_RECEIVED = 'PAYMENT_RECEIVED', 'Payment Received'
        REFUND_PROCESSED = 'REFUND_PROCESSED', 'Refund Processed'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
        ACCOUNT_WELCOME = 'ACCOUNT_WELCOME', 'Account Welcome'
        ABANDONED_CART = 'ABANDONED_CART', 'Abandoned Cart'
        BACK_IN_STOCK = 'BACK_IN_STOCK', 'Back in Stock'
        NEWSLETTER = 'NEWSLETTER', 'Newsletter'
        PROMOTIONAL = 'PROMOTIONAL', 'Promotional'
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TemplateType.choices)
    subject = models.CharField(max_length=255)
    
    # Template Content
    html_content = models.TextField()
    text_content = models.TextField(blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=100, blank=True)
    
    # Template Variables
    available_variables = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'ecommerce_email_template'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'template_type'],
                name='unique_template_type_per_tenant'
            )
        ]
    
    def __str__(self):
        return f'{self.name} ({self.template_type})'
    
    def render(self, context):
        """Render template with context variables"""
        from django.template import Template, Context
        
        html_template = Template(self.html_content)
        text_template = Template(self.text_content) if self.text_content else None
        
        django_context = Context(context)
        
        rendered_html = html_template.render(django_context)
        rendered_text = text_template.render(django_context) if text_template else None
        
        return {
            'subject': self.subject,
            'html_content': rendered_html,
            'text_content': rendered_text,
            'from_email': self.from_email,
            'from_name': self.from_name
        }