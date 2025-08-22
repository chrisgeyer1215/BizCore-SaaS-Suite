# apps/ecommerce/models/orders.py

"""
Comprehensive Order Management System with AI-powered features
Advanced business logic with predictive analytics and intelligent automation
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid
from datetime import timedelta
from enum import TextChoices

from .base import EcommerceBaseModel, CommonChoices, AuditMixin, SEOMixin
from .managers import OrderManager, OrderQuerySet

User = get_user_model()


class Order(EcommerceBaseModel, AuditMixin):
    """
    Comprehensive Order model with AI-powered insights and predictive analytics
    """
    
    class OrderStatus(models.TextChoices):
        # Pre-fulfillment
        PENDING = 'PENDING', 'Pending Payment'
        PAYMENT_PENDING = 'PAYMENT_PENDING', 'Payment Processing'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PROCESSING = 'PROCESSING', 'Processing'
        
        # Fulfillment
        PICKING = 'PICKING', 'Picking Items'
        PACKED = 'PACKED', 'Packed'
        SHIPPED = 'SHIPPED', 'Shipped'
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for Delivery'
        DELIVERED = 'DELIVERED', 'Delivered'
        
        # Exceptions
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        RETURNED = 'RETURNED', 'Returned'
        DISPUTED = 'DISPUTED', 'Disputed'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        
        # AI-driven statuses
        RISK_REVIEW = 'RISK_REVIEW', 'Risk Review Required'
        AI_FLAGGED = 'AI_FLAGGED', 'AI Flagged'
        AUTO_CANCELLED = 'AUTO_CANCELLED', 'Auto-Cancelled by AI'
    
    class OrderType(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard Order'
        EXPRESS = 'EXPRESS', 'Express Order'
        SUBSCRIPTION = 'SUBSCRIPTION', 'Subscription Order'
        BULK = 'BULK', 'Bulk Order'
        B2B = 'B2B', 'B2B Order'
        DROPSHIP = 'DROPSHIP', 'Dropship Order'
        DIGITAL = 'DIGITAL', 'Digital Order'
        MIXED = 'MIXED', 'Mixed Order'
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Payment Pending'
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        CAPTURED = 'CAPTURED', 'Captured'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        PAID = 'PAID', 'Fully Paid'
        FAILED = 'FAILED', 'Payment Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        DISPUTED = 'DISPUTED', 'Disputed'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
    
    class FulfillmentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED', 'Partially Fulfilled'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'
        RETURNED = 'RETURNED', 'Returned'
    
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low Risk'
        MEDIUM = 'MEDIUM', 'Medium Risk'
        HIGH = 'HIGH', 'High Risk'
        CRITICAL = 'CRITICAL', 'Critical Risk'
        BLOCKED = 'BLOCKED', 'Blocked'
    
    # Basic Order Information
    order_number = models.CharField(max_length=100, unique=True, blank=True)
    order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Order Classification
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.STANDARD)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    fulfillment_status = models.CharField(max_length=20, choices=FulfillmentStatus.choices, default=FulfillmentStatus.PENDING)
    
    # Customer Information
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.PROTECT,
        related_name='orders',
        null=True, blank=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='orders',
        null=True, blank=True
    )
    guest_email = models.EmailField(blank=True)
    is_guest_order = models.BooleanField(default=False)
    
    # Shopping Cart Reference
    cart = models.OneToOneField(
        'Cart',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='order'
    )
    
    # Financial Information
    currency = models.CharField(max_length=3, choices=CommonChoices.Currency.choices, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))
    
    # Order Totals
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Discounts and Promotions
    applied_coupons = models.JSONField(default=list, blank=True)
    discount_codes = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    loyalty_points_used = models.PositiveIntegerField(default=0)
    loyalty_points_earned = models.PositiveIntegerField(default=0)
    
    # Addresses
    billing_address = models.JSONField(default=dict, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_url = models.URLField(blank=True)
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Timing Information
    placed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Order Attributes
    priority_level = models.CharField(max_length=10, default='NORMAL')
    is_gift = models.BooleanField(default=False)
    gift_message = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # AI-Powered Risk Management
    risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated risk score (0-100)"
    )
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.LOW)
    risk_factors = models.JSONField(default=list, blank=True, help_text="AI-identified risk factors")
    fraud_probability = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # AI Insights and Predictions
    predicted_delivery_date = models.DateTimeField(null=True, blank=True)
    predicted_fulfillment_time_hours = models.PositiveIntegerField(null=True, blank=True)
    customer_satisfaction_prediction = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    return_probability = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Marketing Attribution
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_term = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    referrer_url = models.URLField(blank=True)
    affiliate_id = models.CharField(max_length=100, blank=True)
    
    # Device and Location Information
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    geolocation = models.JSONField(default=dict, blank=True)
    
    # Customer Behavior Analytics
    session_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    page_views_before_order = models.PositiveIntegerField(null=True, blank=True)
    cart_abandonment_count = models.PositiveIntegerField(default=0)
    days_since_last_order = models.PositiveIntegerField(null=True, blank=True)
    customer_lifetime_orders = models.PositiveIntegerField(default=1)
    
    # Automation Flags
    auto_fulfill = models.BooleanField(default=False)
    auto_ship = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)
    ai_processing_enabled = models.BooleanField(default=True)
    
    # Integration References
    external_order_id = models.CharField(max_length=100, blank=True)
    erp_sync_status = models.CharField(max_length=20, default='PENDING')
    warehouse_system_id = models.CharField(max_length=100, blank=True)
    
    # Performance Metrics
    processing_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    fulfillment_accuracy_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Custom manager
    objects = OrderManager()
    
    class Meta:
        db_table = 'ecommerce_orders'
        ordering = ['-placed_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'placed_at']),
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['tenant', 'order_number']),
            models.Index(fields=['tenant', 'risk_level', 'status']),
            models.Index(fields=['tenant', 'payment_status']),
            models.Index(fields=['tenant', 'fulfillment_status']),
            models.Index(fields=['tenant', 'placed_at', 'total_amount']),
            models.Index(fields=['tenant', 'tracking_number']),
            models.Index(fields=['tenant', 'predicted_delivery_date']),
            models.Index(fields=['tenant', 'auto_fulfill', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(risk_score__gte=0) & models.Q(risk_score__lte=100),
                name='valid_risk_score'
            ),
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='positive_total_amount'
            ),
            models.CheckConstraint(
                check=models.Q(paid_amount__gte=0),
                name='positive_paid_amount'
            ),
        ]
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.get_customer_display()} - ${self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Calculate totals before saving
        self.calculate_totals()
        
        # Set guest order flag
        self.is_guest_order = bool(self.guest_email and not self.user)
        
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number with tenant prefix"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        prefix = f"ORD-{self.tenant.slug.upper() if self.tenant else 'DEF'}-{today}"
        
        last_order = Order.objects.filter(
            tenant=self.tenant,
            order_number__startswith=prefix
        ).order_by('-order_number').first()
        
        if last_order:
            try:
                last_seq = int(last_order.order_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:06d}"
    
    def get_customer_display(self):
        """Get customer display name"""
        if self.customer:
            return self.customer.get_full_name()
        elif self.user:
            return self.user.get_full_name() or self.user.email
        elif self.guest_email:
            return f"Guest ({self.guest_email})"
        return "Unknown Customer"
    
    def calculate_totals(self):
        """Calculate order totals from line items"""
        items = self.items.all() if self.pk else []
        
        self.subtotal = sum(item.total_amount for item in items)
        
        # Apply discounts
        if self.discount_amount:
            self.subtotal -= self.discount_amount
        
        # Calculate total
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
    
    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total_amount - self.paid_amount
    
    @property
    def is_paid(self):
        """Check if order is fully paid"""
        return self.paid_amount >= self.total_amount
    
    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.payment_status in ['PENDING', 'FAILED'] and self.placed_at:
            return timezone.now() > self.placed_at + timedelta(hours=24)
        return False
    
    @property
    def days_since_placed(self):
        """Calculate days since order was placed"""
        return (timezone.now() - self.placed_at).days
    
    @property
    def is_high_risk(self):
        """Check if order is high risk"""
        return self.risk_level in ['HIGH', 'CRITICAL'] or self.risk_score >= 70
    
    @property
    def is_rush_order(self):
        """Check if this is a rush order"""
        return self.priority_level == 'HIGH' or self.order_type == 'EXPRESS'
    
    @property
    def estimated_profit_margin(self):
        """Calculate estimated profit margin"""
        if self.total_amount == 0:
            return Decimal('0.00')
        
        cost_price = sum(item.cost_price * item.quantity for item in self.items.all())
        profit = self.total_amount - cost_price - self.shipping_cost
        return (profit / self.total_amount * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def can_cancel(self):
        """Check if order can be cancelled"""
        cancellable_statuses = ['PENDING', 'CONFIRMED', 'PROCESSING']
        return self.status in cancellable_statuses
    
    def can_refund(self):
        """Check if order can be refunded"""
        refundable_statuses = ['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED']
        return (self.status in refundable_statuses and 
                self.payment_status in ['CAPTURED', 'PAID'] and
                self.paid_amount > self.refunded_amount)
    
    def update_risk_assessment(self, risk_factors=None):
        """Update AI risk assessment"""
        # This would integrate with your AI risk assessment service
        if risk_factors:
            self.risk_factors = risk_factors
        
        # Calculate risk score based on various factors
        score = Decimal('0.00')
        
        # Customer history risk
        if self.is_guest_order:
            score += Decimal('10.00')
        elif self.customer and self.customer.orders.count() == 1:
            score += Decimal('5.00')
        
        # Order value risk
        if self.total_amount > 1000:
            score += Decimal('15.00')
        elif self.total_amount > 500:
            score += Decimal('10.00')
        
        # Geographic risk (simplified)
        if self.geolocation.get('country_code') not in ['US', 'CA', 'GB', 'AU']:
            score += Decimal('20.00')
        
        # Payment method risk
        # This would check payment method from associated transactions
        
        # Behavioral risk
        if self.cart_abandonment_count > 3:
            score += Decimal('15.00')
        
        self.risk_score = min(score, Decimal('100.00'))
        
        # Set risk level based on score
        if self.risk_score < 20:
            self.risk_level = self.RiskLevel.LOW
        elif self.risk_score < 50:
            self.risk_level = self.RiskLevel.MEDIUM
        elif self.risk_score < 80:
            self.risk_level = self.RiskLevel.HIGH
        else:
            self.risk_level = self.RiskLevel.CRITICAL
        
        self.save(update_fields=['risk_score', 'risk_level', 'risk_factors'])
    
    def predict_delivery_date(self):
        """AI-powered delivery date prediction"""
        # Base prediction on shipping method and location
        base_days = {
            'STANDARD': 5,
            'EXPRESS': 2,
            'OVERNIGHT': 1,
        }.get(self.shipping_method, 3)
        
        # Adjust based on location, inventory, etc.
        if self.shipping_address.get('country') != 'US':
            base_days += 3
        
        # AI adjustments based on historical data
        # This would use ML models trained on delivery performance
        
        predicted_date = timezone.now() + timedelta(days=base_days)
        self.predicted_delivery_date = predicted_date
        self.save(update_fields=['predicted_delivery_date'])
        
        return predicted_date
    
    def calculate_customer_satisfaction_prediction(self):
        """Predict customer satisfaction using AI"""
        score = Decimal('8.0')  # Base score
        
        # Adjust based on various factors
        if self.is_rush_order:
            score -= Decimal('0.5')
        
        if self.total_amount > 200:
            score += Decimal('0.3')
        
        if self.customer and self.customer.orders.filter(status='RETURNED').count() > 0:
            score -= Decimal('0.8')
        
        # This would use ML models for more accurate prediction
        self.customer_satisfaction_prediction = max(Decimal('1.0'), min(score, Decimal('10.0')))
        self.save(update_fields=['customer_satisfaction_prediction'])
    
    def get_ai_insights(self):
        """Get AI-generated insights about the order"""
        insights = {
            'risk_assessment': {
                'score': float(self.risk_score),
                'level': self.risk_level,
                'factors': self.risk_factors,
                'recommendation': self.get_risk_recommendation()
            },
            'fulfillment': {
                'predicted_time': self.predicted_fulfillment_time_hours,
                'auto_fulfill_eligible': self.auto_fulfill,
                'priority_recommendation': self.get_priority_recommendation()
            },
            'customer': {
                'satisfaction_prediction': float(self.customer_satisfaction_prediction or 0),
                'return_probability': float(self.return_probability),
                'lifetime_value_impact': self.calculate_ltv_impact()
            },
            'business': {
                'profit_margin': float(self.estimated_profit_margin),
                'inventory_impact': self.get_inventory_impact(),
                'demand_pattern': self.analyze_demand_pattern()
            }
        }
        return insights
    
    def get_risk_recommendation(self):
        """Get AI recommendation based on risk level"""
        if self.risk_level == 'CRITICAL':
            return "Block order and require manual verification"
        elif self.risk_level == 'HIGH':
            return "Require additional verification before fulfillment"
        elif self.risk_level == 'MEDIUM':
            return "Monitor closely and verify payment method"
        else:
            return "Process normally"
    
    def get_priority_recommendation(self):
        """Get AI-powered priority recommendation"""
        if self.customer and self.customer.customer_tier == 'VIP':
            return 'HIGH'
        elif self.total_amount > 500:
            return 'HIGH'
        elif self.is_rush_order:
            return 'URGENT'
        else:
            return 'NORMAL'
    
    def calculate_ltv_impact(self):
        """Calculate impact on customer lifetime value"""
        if not self.customer:
            return 0
        
        # This would use ML models to predict LTV impact
        base_impact = float(self.total_amount)
        
        # First-time customer bonus
        if self.customer.orders.count() == 1:
            base_impact *= 1.5
        
        return round(base_impact, 2)
    
    def get_inventory_impact(self):
        """Analyze inventory impact of this order"""
        impact = {
            'total_units': sum(item.quantity for item in self.items.all()),
            'high_velocity_items': [],
            'low_stock_alerts': [],
            'reorder_recommendations': []
        }
        
        for item in self.items.all():
            # This would integrate with inventory system
            if hasattr(item.product, 'inventory_product'):
                inventory = item.product.inventory_product
                if inventory and inventory.quantity_on_hand < inventory.reorder_point:
                    impact['low_stock_alerts'].append(item.product.title)
        
        return impact
    
    def analyze_demand_pattern(self):
        """Analyze demand patterns from this order"""
        # This would use time series analysis and ML
        return {
            'seasonal_factor': 1.0,
            'trending_products': [],
            'demand_forecast_accuracy': 85.5
        }


class OrderItem(EcommerceBaseModel):
    """
    Order line item with AI-powered analytics and automation
    """
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('EcommerceProduct', on_delete=models.PROTECT, related_name='order_items')
    variant = models.ForeignKey('ProductVariant', on_delete=models.PROTECT, null=True, blank=True, related_name='order_items')
    
    # Item Details
    sku = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=255)
    variant_title = models.CharField(max_length=255, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Quantity and Fulfillment
    quantity = models.PositiveIntegerField(default=1)
    quantity_fulfilled = models.PositiveIntegerField(default=0)
    quantity_returned = models.PositiveIntegerField(default=0)
    quantity_cancelled = models.PositiveIntegerField(default=0)
    
    # Totals
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Product Attributes (snapshot at time of order)
    product_type = models.CharField(max_length=20, blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    requires_shipping = models.BooleanField(default=True)
    is_digital = models.BooleanField(default=False)
    
    # Personalization and Customization
    personalization = models.JSONField(default=dict, blank=True)
    custom_options = models.JSONField(default=dict, blank=True)
    
    # AI-Powered Insights
    demand_rank = models.PositiveIntegerField(null=True, blank=True, help_text="AI-calculated demand ranking")
    velocity_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Product velocity score"
    )
    cross_sell_opportunities = models.JSONField(default=list, blank=True)
    upsell_recommendations = models.JSONField(default=list, blank=True)
    
    # Fulfillment Intelligence
    pick_priority = models.PositiveIntegerField(default=50, help_text="AI-determined pick priority (1-100)")
    estimated_pick_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    warehouse_location = models.CharField(max_length=100, blank=True)
    
    # Quality and Satisfaction Predictors
    return_risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    satisfaction_impact = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Impact on overall order satisfaction (0-10)"
    )
    
    # Inventory Integration
    inventory_reserved = models.BooleanField(default=False)
    inventory_reservation_id = models.CharField(max_length=100, blank=True)
    stock_location = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'ecommerce_order_items'
        ordering = ['order', 'pk']
        indexes = [
            models.Index(fields=['tenant', 'order', 'product']),
            models.Index(fields=['tenant', 'product', 'created_at']),
            models.Index(fields=['tenant', 'sku']),
            models.Index(fields=['tenant', 'pick_priority']),
            models.Index(fields=['tenant', 'inventory_reserved']),
        ]
    
    def __str__(self):
        return f"{self.title} x{self.quantity} - Order #{self.order.order_number}"
    
    def save(self, *args, **kwargs):
        # Calculate totals
        self.subtotal = self.price * self.quantity
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        
        # Copy product information
        if self.product and not self.title:
            self.title = self.product.title
            self.sku = self.product.sku
            self.product_type = self.product.product_type
            self.requires_shipping = self.product.requires_shipping
            self.is_digital = self.product.is_digital_product
        
        super().save(*args, **kwargs)
    
    @property
    def quantity_pending(self):
        """Quantity still pending fulfillment"""
        return self.quantity - self.quantity_fulfilled - self.quantity_cancelled
    
    @property
    def fulfillment_percentage(self):
        """Percentage of item fulfilled"""
        if self.quantity == 0:
            return 0
        return (self.quantity_fulfilled / self.quantity * 100)
    
    @property
    def profit_margin(self):
        """Calculate profit margin for this item"""
        if not self.cost_price or self.price == 0:
            return Decimal('0.00')
        
        profit = self.price - self.cost_price
        return (profit / self.price * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def is_high_value(self):
        """Check if this is a high-value item"""
        return self.total_amount >= 100
    
    def calculate_ai_insights(self):
        """Calculate AI-powered insights for this order item"""
        # Update demand rank based on recent sales
        recent_sales = OrderItem.objects.filter(
            tenant=self.tenant,
            product=self.product,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # This would use more sophisticated ML models
        self.demand_rank = min(recent_sales * 10, 100)
        
        # Calculate return risk based on product history
        total_sold = OrderItem.objects.filter(
            tenant=self.tenant,
            product=self.product
        ).aggregate(total=models.Sum('quantity'))['total'] or 1
        
        total_returned = OrderItem.objects.filter(
            tenant=self.tenant,
            product=self.product
        ).aggregate(total=models.Sum('quantity_returned'))['total'] or 0
        
        self.return_risk_score = Decimal(str((total_returned / total_sold) * 100))
        
        # Calculate cross-sell opportunities
        self.calculate_cross_sell_opportunities()
        
        self.save(update_fields=[
            'demand_rank', 'return_risk_score', 'cross_sell_opportunities'
        ])
    
    def calculate_cross_sell_opportunities(self):
        """Calculate cross-sell opportunities using AI"""
        # This would use collaborative filtering and association rules
        frequently_bought_together = OrderItem.objects.filter(
            order__in=Order.objects.filter(
                items__product=self.product
            ).exclude(id=self.order_id)
        ).values('product__title', 'product__id').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        self.cross_sell_opportunities = [
            {
                'product_id': item['product__id'],
                'product_title': item['product__title'],
                'frequency': item['count'],
                'confidence_score': min(item['count'] * 10, 100)
            }
            for item in frequently_bought_together
        ]
    
    def reserve_inventory(self):
        """Reserve inventory for this order item"""
        if self.inventory_reserved:
            return True, "Already reserved"
        
        if not self.product.inventory_product:
            return False, "No inventory integration"
        
        # This would integrate with the inventory reservation system
        try:
            # Create reservation in inventory system
            from apps.inventory.models import StockReservation
            
            reservation = StockReservation.objects.create(
                tenant=self.tenant,
                reservation_type='SALES_ORDER',
                priority_level='NORMAL',
                expires_at=timezone.now() + timedelta(days=7),
                reference_type='ORDER',
                reference_id=str(self.order.id),
                notes=f"Order #{self.order.order_number} - {self.product.title}"
            )
            
            # Add reservation item
            from apps.inventory.models import StockReservationItem
            
            reservation_item = StockReservationItem.objects.create(
                tenant=self.tenant,
                reservation=reservation,
                stock_item=self.product.inventory_product.stock_items.first(),
                quantity_requested=self.quantity,
                unit_price=self.price,
                notes=f"Order item for {self.product.title}"
            )
            
            self.inventory_reserved = True
            self.inventory_reservation_id = str(reservation.id)
            self.save(update_fields=['inventory_reserved', 'inventory_reservation_id'])
            
            return True, "Inventory reserved successfully"
            
        except Exception as e:
            return False, f"Failed to reserve inventory: {str(e)}"
    
    def get_fulfillment_recommendation(self):
        """Get AI-powered fulfillment recommendation"""
        recommendation = {
            'priority': self.pick_priority,
            'estimated_time': self.estimated_pick_time_minutes,
            'special_handling': [],
            'quality_checks': []
        }
        
        # High-value items need extra care
        if self.is_high_value:
            recommendation['special_handling'].append('HIGH_VALUE_ITEM')
            recommendation['quality_checks'].append('DAMAGE_INSPECTION')
        
        # High return risk items need quality checks
        if self.return_risk_score > 10:
            recommendation['quality_checks'].append('QUALITY_ASSURANCE')
        
        # Digital items have different fulfillment
        if self.is_digital:
            recommendation['fulfillment_type'] = 'DIGITAL_DELIVERY'
        
        return recommendation


class OrderHistory(EcommerceBaseModel):
    """
    Comprehensive order history tracking with AI insights
    """
    
    class ActionType(models.TextChoices):
        CREATED = 'CREATED', 'Order Created'
        UPDATED = 'UPDATED', 'Order Updated'
        CONFIRMED = 'CONFIRMED', 'Order Confirmed'
        PAYMENT_RECEIVED = 'PAYMENT_RECEIVED', 'Payment Received'
        PAYMENT_FAILED = 'PAYMENT_FAILED', 'Payment Failed'
        SHIPPED = 'SHIPPED', 'Order Shipped'
        DELIVERED = 'DELIVERED', 'Order Delivered'
        CANCELLED = 'CANCELLED', 'Order Cancelled'
        REFUNDED = 'REFUNDED', 'Order Refunded'
        RETURNED = 'RETURNED', 'Order Returned'
        
        # AI-driven actions
        AI_FLAGGED = 'AI_FLAGGED', 'AI Flagged for Review'
        AUTO_APPROVED = 'AUTO_APPROVED', 'Auto-Approved by AI'
        RISK_ASSESSED = 'RISK_ASSESSED', 'Risk Assessment Updated'
        AUTO_FULFILLED = 'AUTO_FULFILLED', 'Auto-Fulfilled'
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ActionType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Actor information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    system_actor = models.CharField(max_length=100, blank=True, help_text="System/AI that performed action")
    is_automated = models.BooleanField(default=False)
    
    # Change details
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    
    # Context and metadata
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # AI insights
    confidence_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI confidence in automated decision"
    )
    risk_factors_at_time = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'ecommerce_order_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'order', '-timestamp']),
            models.Index(fields=['tenant', 'action', '-timestamp']),
            models.Index(fields=['tenant', 'user', '-timestamp']),
            models.Index(fields=['tenant', 'is_automated']),
        ]
    
    def __str__(self):
        return f"Order #{self.order.order_number} - {self.get_action_display()} at {self.timestamp}"
    
    @classmethod
    def log_action(cls, order, action, user=None, system_actor=None, description='', 
                   previous_status=None, new_status=None, changes=None, metadata=None,
                   confidence_score=None):
        """Log an order action with comprehensive details"""
        return cls.objects.create(
            tenant=order.tenant,
            order=order,
            action=action,
            user=user,
            system_actor=system_actor or 'SYSTEM',
            is_automated=bool(system_actor and not user),
            previous_status=previous_status or '',
            new_status=new_status or '',
            changes=changes or {},
            description=description,
            metadata=metadata or {},
            confidence_score=confidence_score,
            risk_factors_at_time=order.risk_factors if hasattr(order, 'risk_factors') else []
        )


class OrderAnalytics(EcommerceBaseModel):
    """
    AI-powered order analytics and insights
    """
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='analytics')
    
    # Customer Analytics
    customer_segment = models.CharField(max_length=50, blank=True)
    customer_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    customer_acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    customer_retention_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Order Performance Metrics
    order_processing_efficiency = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fulfillment_accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    delivery_performance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Financial Analytics
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contribution_margin = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    marketing_attribution = models.JSONField(default=dict, blank=True)
    
    # Predictive Analytics
    churn_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    upsell_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    next_purchase_prediction_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Seasonal and Trend Analysis
    seasonal_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    trend_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    demand_volatility = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Competitive Intelligence
    price_competitiveness_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    market_share_impact = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # ML Model Scores
    model_predictions = models.JSONField(default=dict, blank=True)
    feature_importance = models.JSONField(default=dict, blank=True)
    model_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Real-time Updates
    last_calculated_at = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=20, default='1.0')
    
    class Meta:
        db_table = 'ecommerce_order_analytics'
        indexes = [
            models.Index(fields=['tenant', 'customer_segment']),
            models.Index(fields=['tenant', 'last_calculated_at']),
            models.Index(fields=['tenant', 'churn_probability']),
            models.Index(fields=['tenant', 'profit_margin']),
        ]
    
    def __str__(self):
        return f"Analytics for Order #{self.order.order_number}"
    
    def calculate_all_metrics(self):
        """Calculate all analytics metrics using AI/ML models"""
        self.calculate_customer_metrics()
        self.calculate_performance_metrics()
        self.calculate_financial_metrics()
        self.calculate_predictive_metrics()
        self.save()
    
    def calculate_customer_metrics(self):
        """Calculate customer-related analytics"""
        if self.order.customer:
            # Customer segment classification
            self.customer_segment = self.classify_customer_segment()
            
            # Customer lifetime value calculation
            self.customer_lifetime_value = self.calculate_clv()
            
            # Retention probability
            self.customer_retention_probability = self.predict_retention()
    
    def calculate_performance_metrics(self):
        """Calculate operational performance metrics"""
        # Order processing efficiency
        if self.order.processing_time_minutes:
            # Compare against benchmark
            benchmark_time = 60  # minutes
            self.order_processing_efficiency = min(
                (benchmark_time / self.order.processing_time_minutes) * 100,
                100
            )
        
        # Fulfillment accuracy
        self.fulfillment_accuracy = self.order.fulfillment_accuracy_score or Decimal('95.0')
        
        # Delivery performance
        if self.order.predicted_delivery_date and self.order.actual_delivery_date:
            predicted = self.order.predicted_delivery_date
            actual = self.order.actual_delivery_date
            diff_hours = abs((actual - predicted).total_seconds() / 3600)
            
            # Score based on accuracy (100% if within 24 hours)
            self.delivery_performance = max(0, 100 - (diff_hours / 24) * 50)
    
    def calculate_financial_metrics(self):
        """Calculate financial analytics"""
        self.profit_margin = self.order.estimated_profit_margin
        
        # Contribution margin
        if self.order.total_amount > 0:
            variable_costs = sum(
                item.cost_price * item.quantity 
                for item in self.order.items.all() 
                if item.cost_price
            )
            self.contribution_margin = self.order.total_amount - variable_costs
    
    def calculate_predictive_metrics(self):
        """Calculate predictive analytics using ML"""
        # Churn probability (simplified)
        if self.order.customer:
            last_order_days = self.order.days_since_last_order or 0
            if last_order_days > 180:
                self.churn_probability = Decimal('75.0')
            elif last_order_days > 90:
                self.churn_probability = Decimal('45.0')
            else:
                self.churn_probability = Decimal('15.0')
        
        # Next purchase prediction
        if self.order.customer:
            avg_days_between_orders = self.calculate_avg_purchase_interval()
            self.next_purchase_prediction_days = int(avg_days_between_orders * 1.1)
    
    def classify_customer_segment(self):
        """Classify customer into segments using AI"""
        if not self.order.customer:
            return 'GUEST'
        
        customer = self.order.customer
        order_count = customer.orders.count()
        total_spent = customer.orders.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0')
        
        if order_count >= 10 and total_spent >= 1000:
            return 'VIP'
        elif order_count >= 5 or total_spent >= 500:
            return 'LOYAL'
        elif order_count >= 2:
            return 'REPEAT'
        else:
            return 'NEW'
    
    def calculate_clv(self):
        """Calculate Customer Lifetime Value"""
        if not self.order.customer:
            return None
        
        # Simplified CLV calculation
        avg_order_value = self.order.customer.orders.aggregate(
            avg=models.Avg('total_amount')
        )['avg'] or Decimal('0')
        
        order_frequency = self.calculate_purchase_frequency()
        customer_lifespan = 2.0  # years, would be calculated based on data
        
        return avg_order_value * order_frequency * customer_lifespan * 12
    
    def calculate_purchase_frequency(self):
        """Calculate customer purchase frequency"""
        if not self.order.customer:
            return 0
        
        orders = self.order.customer.orders.order_by('placed_at')
        if orders.count() < 2:
            return 1
        
        first_order = orders.first()
        last_order = orders.last()
        days_diff = (last_order.placed_at - first_order.placed_at).days
        
        if days_diff == 0:
            return 1
        
        return orders.count() / (days_diff / 30.0)  # orders per month
    
    def calculate_avg_purchase_interval(self):
        """Calculate average days between purchases"""
        if not self.order.customer:
            return 90  # default
        
        orders = list(self.order.customer.orders.order_by('placed_at'))
        if len(orders) < 2:
            return 90
        
        intervals = [
            (orders[i].placed_at - orders[i-1].placed_at).days
            for i in range(1, len(orders))
        ]
        
        return sum(intervals) / len(intervals) if intervals else 90
    
    def predict_retention(self):
        """Predict customer retention probability"""
        if not self.order.customer:
            return None
        
        # Simplified retention model
        base_retention = Decimal('80.0')
        
        # Adjust based on order frequency
        frequency = self.calculate_purchase_frequency()
        if frequency > 2:
            base_retention += Decimal('10.0')
        elif frequency < 0.5:
            base_retention -= Decimal('20.0')
        
        # Adjust based on order value
        if self.order.total_amount > 200:
            base_retention += Decimal('5.0')
        
        # Adjust based on customer satisfaction prediction
        if self.order.customer_satisfaction_prediction:
            if self.order.customer_satisfaction_prediction > 8:
                base_retention += Decimal('10.0')
            elif self.order.customer_satisfaction_prediction < 6:
                base_retention -= Decimal('15.0')
        
        return min(max(base_retention, Decimal('10.0')), Decimal('95.0'))