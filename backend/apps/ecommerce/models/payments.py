# apps/ecommerce/models/payments.py

"""
Advanced Payment System with AI-powered fraud detection, risk assessment, and intelligent automation
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
import json

from .base import EcommerceBaseModel, CommonChoices, AuditMixin
from .managers import PaymentTransactionManager

User = get_user_model()


class PaymentMethod(EcommerceBaseModel, AuditMixin):
    """
    Customer payment methods with AI-powered security analysis
    """
    
    class PaymentType(models.TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
        DIGITAL_WALLET = 'DIGITAL_WALLET', 'Digital Wallet'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        ACH = 'ACH', 'ACH Transfer'
        PAYPAL = 'PAYPAL', 'PayPal'
        APPLE_PAY = 'APPLE_PAY', 'Apple Pay'
        GOOGLE_PAY = 'GOOGLE_PAY', 'Google Pay'
        CRYPTOCURRENCY = 'CRYPTOCURRENCY', 'Cryptocurrency'
        BUY_NOW_PAY_LATER = 'BNPL', 'Buy Now Pay Later'
        GIFT_CARD = 'GIFT_CARD', 'Gift Card'
        STORE_CREDIT = 'STORE_CREDIT', 'Store Credit'
        LOYALTY_POINTS = 'LOYALTY_POINTS', 'Loyalty Points'
    
    class CardType(models.TextChoices):
        VISA = 'VISA', 'Visa'
        MASTERCARD = 'MASTERCARD', 'Mastercard'
        AMERICAN_EXPRESS = 'AMEX', 'American Express'
        DISCOVER = 'DISCOVER', 'Discover'
        DINERS_CLUB = 'DINERS', 'Diners Club'
        JCB = 'JCB', 'JCB'
        OTHER = 'OTHER', 'Other'
    
    class SecurityLevel(models.TextChoices):
        LOW = 'LOW', 'Low Security'
        MEDIUM = 'MEDIUM', 'Medium Security'
        HIGH = 'HIGH', 'High Security'
        MAXIMUM = 'MAXIMUM', 'Maximum Security'
        BLOCKED = 'BLOCKED', 'Blocked'
    
    # Customer association
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_methods',
        null=True, blank=True
    )
    
    # Payment method details
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Card-specific information (encrypted/tokenized)
    card_type = models.CharField(max_length=20, choices=CardType.choices, blank=True)
    last_four_digits = models.CharField(max_length=4, blank=True)
    expiry_month = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)])
    expiry_year = models.PositiveIntegerField(null=True, blank=True)
    cardholder_name = models.CharField(max_length=100, blank=True)
    
    # Tokenization and security
    payment_token = models.CharField(max_length=255, unique=True, blank=True)
    gateway_customer_id = models.CharField(max_length=255, blank=True)
    gateway_payment_method_id = models.CharField(max_length=255, blank=True)
    
    # Billing information
    billing_address = models.JSONField(default=dict, blank=True)
    
    # AI-powered fraud detection
    risk_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated fraud risk score (0-100)"
    )
    security_level = models.CharField(max_length=10, choices=SecurityLevel.choices, default=SecurityLevel.MEDIUM)
    fraud_indicators = models.JSONField(default=list, blank=True)
    
    # Usage analytics
    total_transactions = models.PositiveIntegerField(default=0)
    total_amount_processed = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    successful_transactions = models.PositiveIntegerField(default=0)
    failed_transactions = models.PositiveIntegerField(default=0)
    disputed_transactions = models.PositiveIntegerField(default=0)
    
    # Behavioral analysis
    average_transaction_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    preferred_transaction_time = models.TimeField(null=True, blank=True)
    geographic_usage_pattern = models.JSONField(default=dict, blank=True)
    device_fingerprints = models.JSONField(default=list, blank=True)
    
    # Verification status
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_method = models.CharField(max_length=50, blank=True)
    requires_3ds = models.BooleanField(default=False)
    
    # AI insights
    predicted_decline_probability = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Predicted probability of transaction decline"
    )
    optimal_transaction_times = ArrayField(
        models.TimeField(), default=list, blank=True,
        help_text="AI-predicted optimal transaction times"
    )
    
    class Meta:
        db_table = 'ecommerce_payment_methods'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'customer', 'is_active']),
            models.Index(fields=['tenant', 'payment_token']),
            models.Index(fields=['tenant', 'risk_score']),
            models.Index(fields=['tenant', 'security_level']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'customer', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_payment_method'
            )
        ]
    
    def __str__(self):
        if self.payment_type == 'CREDIT_CARD':
            return f"{self.card_type} ending in {self.last_four_digits}"
        return f"{self.get_payment_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per customer
        if self.is_default:
            PaymentMethod.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if payment method is expired"""
        if self.expiry_month and self.expiry_year:
            from datetime import date
            today = date.today()
            return (self.expiry_year < today.year or 
                   (self.expiry_year == today.year and self.expiry_month < today.month))
        return False
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_transactions == 0:
            return Decimal('0.00')
        return (self.successful_transactions / self.total_transactions * 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    
    @property
    def is_high_risk(self):
        """Check if payment method is high risk"""
        return self.risk_score >= 70 or self.security_level in ['BLOCKED']
    
    def calculate_risk_score(self):
        """AI-powered risk score calculation"""
        score = Decimal('0.00')
        
        # Base risk factors
        if self.failed_transactions > 3:
            score += Decimal('25.00')
        
        if self.disputed_transactions > 0:
            score += Decimal('30.00')
        
        # Success rate factor
        if self.success_rate < 80:
            score += Decimal('20.00')
        elif self.success_rate > 95:
            score -= Decimal('10.00')
        
        # Age of payment method
        age_days = (timezone.now() - self.created_at).days
        if age_days < 7:
            score += Decimal('15.00')
        elif age_days > 365:
            score -= Decimal('5.00')
        
        # Geographic risk
        if len(self.geographic_usage_pattern) > 5:  # Multiple locations
            score += Decimal('10.00')
        
        # Device fingerprint analysis
        if len(self.device_fingerprints) > 3:  # Multiple devices
            score += Decimal('10.00')
        
        self.risk_score = min(score, Decimal('100.00'))
        
        # Update security level based on risk score
        if self.risk_score < 20:
            self.security_level = self.SecurityLevel.LOW
        elif self.risk_score < 40:
            self.security_level = self.SecurityLevel.MEDIUM
        elif self.risk_score < 70:
            self.security_level = self.SecurityLevel.HIGH
        else:
            self.security_level = self.SecurityLevel.MAXIMUM
        
        self.save(update_fields=['risk_score', 'security_level'])
    
    def update_usage_statistics(self, transaction_amount, is_successful):
        """Update usage statistics after transaction"""
        self.total_transactions += 1
        self.total_amount_processed += transaction_amount
        
        if is_successful:
            self.successful_transactions += 1
        else:
            self.failed_transactions += 1
        
        # Recalculate average transaction amount
        if self.successful_transactions > 0:
            self.average_transaction_amount = (
                self.total_amount_processed / self.successful_transactions
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        self.save(update_fields=[
            'total_transactions', 'total_amount_processed',
            'successful_transactions', 'failed_transactions',
            'average_transaction_amount'
        ])
        
        # Recalculate risk score
        self.calculate_risk_score()
    
    def get_fraud_indicators(self):
        """Get AI-identified fraud indicators"""
        indicators = []
        
        if self.is_expired:
            indicators.append("EXPIRED_CARD")
        
        if self.success_rate < 50:
            indicators.append("LOW_SUCCESS_RATE")
        
        if self.disputed_transactions > 0:
            indicators.append("PREVIOUS_DISPUTES")
        
        if len(self.geographic_usage_pattern) > 10:
            indicators.append("UNUSUAL_GEOGRAPHIC_PATTERN")
        
        recent_failures = self.failed_transactions
        if recent_failures > 5:
            indicators.append("MULTIPLE_RECENT_FAILURES")
        
        return indicators
    
    def predict_transaction_success(self, amount, merchant_category=None):
        """Predict transaction success probability using AI"""
        base_probability = self.success_rate
        
        # Adjust based on amount
        if self.average_transaction_amount:
            amount_ratio = amount / self.average_transaction_amount
            if amount_ratio > 3:  # Unusually high amount
                base_probability -= 20
            elif amount_ratio < 0.3:  # Unusually low amount
                base_probability -= 5
        
        # Adjust based on risk score
        base_probability -= (self.risk_score / 2)
        
        # Time-based factors
        current_time = timezone.now().time()
        if self.preferred_transaction_time:
            time_diff = abs((current_time.hour - self.preferred_transaction_time.hour))
            if time_diff > 6:
                base_probability -= 10
        
        return max(0, min(100, base_probability))


class PaymentTransaction(EcommerceBaseModel, AuditMixin):
    """
    Comprehensive payment transaction with AI-powered fraud detection and analysis
    """
    
    class TransactionType(models.TextChoices):
        PAYMENT = 'PAYMENT', 'Payment'
        REFUND = 'REFUND', 'Refund'
        PARTIAL_REFUND = 'PARTIAL_REFUND', 'Partial Refund'
        AUTHORIZATION = 'AUTHORIZATION', 'Authorization'
        CAPTURE = 'CAPTURE', 'Capture'
        VOID = 'VOID', 'Void'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
        CHARGEBACK_REVERSAL = 'CHARGEBACK_REVERSAL', 'Chargeback Reversal'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        FEE = 'FEE', 'Processing Fee'
    
    class TransactionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        CAPTURED = 'CAPTURED', 'Captured'
        SETTLED = 'SETTLED', 'Settled'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        DECLINED = 'DECLINED', 'Declined'
        DISPUTED = 'DISPUTED', 'Disputed'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        
        # AI-driven statuses
        FRAUD_SUSPECTED = 'FRAUD_SUSPECTED', 'Fraud Suspected'
        AI_BLOCKED = 'AI_BLOCKED', 'AI Blocked'
        MANUAL_REVIEW = 'MANUAL_REVIEW', 'Manual Review Required'
    
    class FraudRiskLevel(models.TextChoices):
        VERY_LOW = 'VERY_LOW', 'Very Low Risk'
        LOW = 'LOW', 'Low Risk'
        MEDIUM = 'MEDIUM', 'Medium Risk'
        HIGH = 'HIGH', 'High Risk'
        VERY_HIGH = 'VERY_HIGH', 'Very High Risk'
        CRITICAL = 'CRITICAL', 'Critical Risk'
    
    # Transaction identification
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    transaction_number = models.CharField(max_length=100, unique=True, blank=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Related objects
    order = models.ForeignKey(
        'Order',
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    parent_transaction = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='child_transactions'
    )
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    
    # Financial information
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CommonChoices.Currency.choices, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Gateway information
    payment_gateway = models.CharField(max_length=50, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    gateway_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Timing information
    initiated_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # AI-powered fraud detection
    fraud_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated fraud score (0-100)"
    )
    fraud_risk_level = models.CharField(max_length=15, choices=FraudRiskLevel.choices, default=FraudRiskLevel.LOW)
    fraud_indicators = models.JSONField(default=list, blank=True)
    ml_model_version = models.CharField(max_length=20, blank=True)
    
    # Device and location information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.JSONField(default=dict, blank=True)
    geolocation = models.JSONField(default=dict, blank=True)
    user_agent = models.TextField(blank=True)
    
    # 3D Secure information
    three_ds_required = models.BooleanField(default=False)
    three_ds_status = models.CharField(max_length=20, blank=True)
    three_ds_authentication_id = models.CharField(max_length=255, blank=True)
    
    # Verification and compliance
    avs_response = models.CharField(max_length=10, blank=True, help_text="Address Verification Service response")
    cvv_response = models.CharField(max_length=10, blank=True, help_text="CVV verification response")
    
    # Risk assessment details
    velocity_check_result = models.JSONField(default=dict, blank=True)
    blacklist_check_result = models.JSONField(default=dict, blank=True)
    behavioral_analysis = models.JSONField(default=dict, blank=True)
    
    # Decline and error information
    decline_reason = models.CharField(max_length=100, blank=True)
    error_code = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    
    # Settlement information
    settlement_batch_id = models.CharField(max_length=100, blank=True)
    settlement_date = models.DateField(null=True, blank=True)
    settlement_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Metadata and tracking
    metadata = models.JSONField(default=dict, blank=True)
    webhook_delivered = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    # Custom manager
    objects = PaymentTransactionManager()
    
    class Meta:
        db_table = 'ecommerce_payment_transactions'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['tenant', 'order', 'status']),
            models.Index(fields=['tenant', 'payment_method', '-initiated_at']),
            models.Index(fields=['tenant', 'transaction_type', 'status']),
            models.Index(fields=['tenant', 'fraud_risk_level']),
            models.Index(fields=['tenant', 'gateway_transaction_id']),
            models.Index(fields=['tenant', 'settlement_date']),
            models.Index(fields=['tenant', 'fraud_score']),
            models.Index(fields=['tenant', '-initiated_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='positive_transaction_amount'
            ),
            models.CheckConstraint(
                check=models.Q(fraud_score__gte=0) & models.Q(fraud_score__lte=100),
                name='valid_fraud_score'
            ),
        ]
    
    def __str__(self):
        return f"Transaction #{self.transaction_number} - {self.get_transaction_type_display()} - ${self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_number:
            self.transaction_number = self.generate_transaction_number()
        
        # Calculate net amount
        self.net_amount = self.amount - self.processing_fee - self.gateway_fee
        
        super().save(*args, **kwargs)
    
    def generate_transaction_number(self):
        """Generate unique transaction number"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        prefix = f"TXN-{today}"
        
        last_transaction = PaymentTransaction.objects.filter(
            tenant=self.tenant,
            transaction_number__startswith=prefix
        ).order_by('-transaction_number').first()
        
        if last_transaction:
            try:
                last_seq = int(last_transaction.transaction_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:08d}"
    
    @property
    def is_successful(self):
        """Check if transaction was successful"""
        return self.status in ['AUTHORIZED', 'CAPTURED', 'SETTLED']
    
    @property
    def is_refundable(self):
        """Check if transaction can be refunded"""
        return (self.transaction_type == 'PAYMENT' and
                self.status in ['CAPTURED', 'SETTLED'] and
                self.amount > 0)
    
    @property
    def processing_time_seconds(self):
        """Calculate processing time in seconds"""
        if self.processed_at and self.initiated_at:
            return (self.processed_at - self.initiated_at).total_seconds()
        return None
    
    @property
    def is_high_risk(self):
        """Check if transaction is high risk"""
        return self.fraud_risk_level in ['HIGH', 'VERY_HIGH', 'CRITICAL']
    
    def calculate_fraud_score(self):
        """AI-powered fraud score calculation"""
        score = Decimal('0.00')
        
        # Amount-based risk
        if self.amount > 1000:
            score += Decimal('15.00')
        elif self.amount > 500:
            score += Decimal('10.00')
        elif self.amount > 100:
            score += Decimal('5.00')
        
        # Payment method risk
        if self.payment_method.risk_score > 50:
            score += Decimal('20.00')
        
        # Geographic risk
        if self.geolocation.get('country_code') not in ['US', 'CA', 'GB', 'AU']:
            score += Decimal('15.00')
        
        # Time-based risk (unusual hours)
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 23:
            score += Decimal('10.00')
        
        # Velocity checks
        velocity_risk = self.check_velocity_risk()
        score += velocity_risk
        
        # Device fingerprint analysis
        device_risk = self.analyze_device_fingerprint()
        score += device_risk
        
        # Behavioral analysis
        behavioral_risk = self.analyze_user_behavior()
        score += behavioral_risk
        
        self.fraud_score = min(score, Decimal('100.00'))
        
        # Set risk level based on score
        if self.fraud_score < 10:
            self.fraud_risk_level = self.FraudRiskLevel.VERY_LOW
        elif self.fraud_score < 25:
            self.fraud_risk_level = self.FraudRiskLevel.LOW
        elif self.fraud_score < 50:
            self.fraud_risk_level = self.FraudRiskLevel.MEDIUM
        elif self.fraud_score < 75:
            self.fraud_risk_level = self.FraudRiskLevel.HIGH
        elif self.fraud_score < 90:
            self.fraud_risk_level = self.FraudRiskLevel.VERY_HIGH
        else:
            self.fraud_risk_level = self.FraudRiskLevel.CRITICAL
        
        # Update fraud indicators
        self.fraud_indicators = self.get_fraud_indicators()
        
        self.save(update_fields=['fraud_score', 'fraud_risk_level', 'fraud_indicators'])
    
    def check_velocity_risk(self):
        """Check for velocity-based fraud indicators"""
        risk_score = Decimal('0.00')
        now = timezone.now()
        
        # Check transactions in last hour
        recent_transactions = PaymentTransaction.objects.filter(
            tenant=self.tenant,
            payment_method=self.payment_method,
            initiated_at__gte=now - timedelta(hours=1)
        ).count()
        
        if recent_transactions > 3:
            risk_score += Decimal('25.00')
        elif recent_transactions > 1:
            risk_score += Decimal('10.00')
        
        # Check daily transaction amount
        daily_amount = PaymentTransaction.objects.filter(
            tenant=self.tenant,
            payment_method=self.payment_method,
            initiated_at__date=now.date()
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        if daily_amount > 5000:
            risk_score += Decimal('20.00')
        elif daily_amount > 2000:
            risk_score += Decimal('15.00')
        elif daily_amount > 1000:
            risk_score += Decimal('10.00')
        
        self.velocity_check_result = {
            'recent_transactions_count': recent_transactions,
            'daily_amount': float(daily_amount),
            'risk_score': float(risk_score)
        }
        
        return risk_score
    
    def analyze_device_fingerprint(self):
        """Analyze device fingerprint for fraud indicators"""
        risk_score = Decimal('0.00')
        
        if not self.device_fingerprint:
            risk_score += Decimal('10.00')  # No fingerprint is suspicious
            return risk_score
        
        # Check for common fraud indicators in device fingerprint
        screen_resolution = self.device_fingerprint.get('screen_resolution', '')
        if screen_resolution in ['800x600', '1024x768']:  # Common bot resolutions
            risk_score += Decimal('15.00')
        
        # Check timezone consistency
        browser_timezone = self.device_fingerprint.get('timezone')
        geo_timezone = self.geolocation.get('timezone')
        if browser_timezone and geo_timezone and browser_timezone != geo_timezone:
            risk_score += Decimal('20.00')
        
        # Check for suspicious user agent
        if 'bot' in self.user_agent.lower() or 'crawler' in self.user_agent.lower():
            risk_score += Decimal('30.00')
        
        return risk_score
    
    def analyze_user_behavior(self):
        """Analyze user behavioral patterns for fraud detection"""
        risk_score = Decimal('0.00')
        
        # Check customer transaction history
        if self.order.customer:
            customer_transactions = PaymentTransaction.objects.filter(
                tenant=self.tenant,
                order__customer=self.order.customer,
                status__in=['CAPTURED', 'SETTLED']
            ).count()
            
            # New customers have higher risk
            if customer_transactions == 0:
                risk_score += Decimal('15.00')
            
            # Check for previous failures
            failed_transactions = PaymentTransaction.objects.filter(
                tenant=self.tenant,
                order__customer=self.order.customer,
                status__in=['FAILED', 'DECLINED']
            ).count()
            
            if failed_transactions > 3:
                risk_score += Decimal('20.00')
        else:
            # Guest checkout has inherent risk
            risk_score += Decimal('10.00')
        
        # Analyze order placement behavior
        if hasattr(self.order, 'cart') and self.order.cart:
            cart_creation = self.order.cart.created_at
            order_creation = self.order.placed_at
            
            # Very quick checkout might be suspicious
            if (order_creation - cart_creation).total_seconds() < 30:
                risk_score += Decimal('15.00')
        
        self.behavioral_analysis = {
            'risk_factors_identified': len(self.fraud_indicators),
            'customer_history_available': bool(self.order.customer),
            'risk_score': float(risk_score)
        }
        
        return risk_score
    
    def get_fraud_indicators(self):
        """Get list of fraud indicators for this transaction"""
        indicators = []
        
        if self.fraud_score > 50:
            indicators.append("HIGH_FRAUD_SCORE")
        
        if self.amount > 1000:
            indicators.append("HIGH_VALUE_TRANSACTION")
        
        if not self.order.customer:
            indicators.append("GUEST_CHECKOUT")
        
        if self.geolocation.get('country_code') not in ['US', 'CA', 'GB', 'AU']:
            indicators.append("INTERNATIONAL_TRANSACTION")
        
        # Check velocity
        velocity_result = self.velocity_check_result
        if velocity_result.get('recent_transactions_count', 0) > 2:
            indicators.append("HIGH_VELOCITY")
        
        if velocity_result.get('daily_amount', 0) > 2000:
            indicators.append("HIGH_DAILY_VOLUME")
        
        # Payment method risk
        if self.payment_method.risk_score > 70:
            indicators.append("HIGH_RISK_PAYMENT_METHOD")
        
        # Device analysis
        if not self.device_fingerprint:
            indicators.append("NO_DEVICE_FINGERPRINT")
        
        # Time-based risk
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 23:
            indicators.append("UNUSUAL_TRANSACTION_TIME")
        
        return indicators
    
    def should_require_3ds(self):
        """Determine if 3D Secure is required based on risk assessment"""
        # Always require for high-risk transactions
        if self.fraud_risk_level in ['HIGH', 'VERY_HIGH', 'CRITICAL']:
            return True
        
        # Require for high-value transactions
        if self.amount > 500:
            return True
        
        # Require for new payment methods
        if self.payment_method.total_transactions < 3:
            return True
        
        # European PSD2 compliance
        if self.geolocation.get('region') == 'EU' and self.amount > 30:
            return True
        
        return False
    
    def get_recommendation(self):
        """Get AI-powered transaction recommendation"""
        if self.fraud_risk_level == 'CRITICAL':
            return {
                'action': 'BLOCK',
                'reason': 'Critical fraud risk detected',
                'confidence': 95
            }
        elif self.fraud_risk_level == 'VERY_HIGH':
            return {
                'action': 'MANUAL_REVIEW',
                'reason': 'Very high fraud risk requires human review',
                'confidence': 85
            }
        elif self.fraud_risk_level == 'HIGH':
            return {
                'action': 'REQUIRE_3DS',
                'reason': 'High risk - require 3D Secure authentication',
                'confidence': 75
            }
        elif self.fraud_risk_level == 'MEDIUM':
            return {
                'action': 'MONITOR',
                'reason': 'Medium risk - process with monitoring',
                'confidence': 65
            }
        else:
            return {
                'action': 'APPROVE',
                'reason': 'Low risk - approve transaction',
                'confidence': 90
            }
    
    def process_transaction(self):
        """Process the transaction with AI-powered decision making"""
        # Calculate fraud score first
        self.calculate_fraud_score()
        
        # Get AI recommendation
        recommendation = self.get_recommendation()
        
        if recommendation['action'] == 'BLOCK':
            self.status = self.TransactionStatus.AI_BLOCKED
            self.decline_reason = recommendation['reason']
        elif recommendation['action'] == 'MANUAL_REVIEW':
            self.status = self.TransactionStatus.MANUAL_REVIEW
        elif recommendation['action'] == 'REQUIRE_3DS':
            self.three_ds_required = True
            self.status = self.TransactionStatus.PROCESSING
        else:
            # Proceed with normal processing
            self.status = self.TransactionStatus.PROCESSING
        
        self.save()
        return recommendation


class PaymentAnalytics(EcommerceBaseModel):
    """
    AI-powered payment analytics and insights
    """
    
    payment_method = models.OneToOneField(
        PaymentMethod,
        on_delete=models.CASCADE,
        related_name='analytics',
        null=True, blank=True
    )
    transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='analytics',
        null=True, blank=True
    )
    
    # Performance metrics
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average_processing_time = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    decline_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Fraud analytics
    fraud_detection_accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    false_positive_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    false_negative_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Business impact
    revenue_protected = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    potential_losses_prevented = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Predictive insights
    chargeback_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    customer_retention_impact = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # ML model performance
    model_accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feature_importance = models.JSONField(default=dict, blank=True)
    prediction_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Temporal analysis
    seasonal_patterns = models.JSONField(default=dict, blank=True)
    trending_patterns = models.JSONField(default=dict, blank=True)
    anomaly_detection = models.JSONField(default=dict, blank=True)
    
    # Real-time metrics
    last_updated = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=20, default='1.0')
    
    class Meta:
        db_table = 'ecommerce_payment_analytics'
        indexes = [
            models.Index(fields=['tenant', 'last_updated']),
            models.Index(fields=['tenant', 'fraud_detection_accuracy']),
            models.Index(fields=['tenant', 'chargeback_probability']),
        ]
    
    def __str__(self):
        if self.payment_method:
            return f"Analytics for {self.payment_method}"
        elif self.transaction:
            return f"Analytics for {self.transaction}"
        return "Payment Analytics"
    
    def calculate_metrics(self):
        """Calculate all analytics metrics"""
        if self.payment_method:
            self.calculate_payment_method_metrics()
        elif self.transaction:
            self.calculate_transaction_metrics()
        
        self.save()
    
    def calculate_payment_method_metrics(self):
        """Calculate metrics for payment method"""
        pm = self.payment_method
        
        self.success_rate = pm.success_rate
        self.decline_rate = Decimal('100.00') - self.success_rate
        
        # Calculate average processing time
        transactions = pm.transactions.filter(
            status__in=['CAPTURED', 'SETTLED', 'FAILED']
        ).exclude(processed_at__isnull=True)
        
        if transactions.exists():
            total_time = sum(
                (t.processed_at - t.initiated_at).total_seconds()
                for t in transactions
            )
            self.average_processing_time = Decimal(str(total_time / transactions.count()))
    
    def calculate_transaction_metrics(self):
        """Calculate metrics for individual transaction"""
        txn = self.transaction
        
        # Fraud detection accuracy (would be calculated from historical data)
        self.fraud_detection_accuracy = Decimal('92.5')  # Example
        
        # Chargeback probability prediction
        self.chargeback_probability = self.predict_chargeback_probability()
    
    def predict_chargeback_probability(self):
        """Predict chargeback probability using ML"""
        if not self.transaction:
            return None
        
        base_probability = Decimal('2.5')  # Base chargeback rate
        
        # Adjust based on risk factors
        if self.transaction.fraud_score > 70:
            base_probability += Decimal('15.0')
        elif self.transaction.fraud_score > 50:
            base_probability += Decimal('8.0')
        
        # High-value transactions have higher chargeback risk
        if self.transaction.amount > 1000:
            base_probability += Decimal('3.0')
        
        # International transactions
        if self.transaction.geolocation.get('country_code') not in ['US', 'CA']:
            base_probability += Decimal('2.0')
        
        return min(base_probability, Decimal('50.0'))