# apps/ecommerce/models/customers.py

"""
Advanced Customer Management System with AI-powered insights, behavioral analysis, and predictive intelligence
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid
from datetime import timedelta, date
from enum import TextChoices

from .base import EcommerceBaseModel, CommonChoices, AuditMixin, SEOMixin
from .managers import CustomerManager

User = get_user_model()


class Customer(EcommerceBaseModel, AuditMixin):
    """
    Comprehensive customer model with AI-powered insights and behavioral analysis
    """
    
    class CustomerStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        BLOCKED = 'BLOCKED', 'Blocked'
        DELETED = 'DELETED', 'Deleted'
        POTENTIAL = 'POTENTIAL', 'Potential Customer'
        PROSPECT = 'PROSPECT', 'Prospect'
        VIP = 'VIP', 'VIP Customer'
    
    class CustomerTier(models.TextChoices):
        BRONZE = 'BRONZE', 'Bronze'
        SILVER = 'SILVER', 'Silver'
        GOLD = 'GOLD', 'Gold'
        PLATINUM = 'PLATINUM', 'Platinum'
        DIAMOND = 'DIAMOND', 'Diamond'
        VIP = 'VIP', 'VIP'
    
    class LifecycleStage(models.TextChoices):
        VISITOR = 'VISITOR', 'Website Visitor'
        LEAD = 'LEAD', 'Marketing Lead'
        PROSPECT = 'PROSPECT', 'Sales Prospect'
        FIRST_TIME = 'FIRST_TIME', 'First-time Customer'
        REPEAT = 'REPEAT', 'Repeat Customer'
        LOYAL = 'LOYAL', 'Loyal Customer'
        ADVOCATE = 'ADVOCATE', 'Brand Advocate'
        AT_RISK = 'AT_RISK', 'At Risk'
        CHURNED = 'CHURNED', 'Churned'
        REACTIVATED = 'REACTIVATED', 'Reactivated'
    
    class AcquisitionChannel(models.TextChoices):
        ORGANIC_SEARCH = 'ORGANIC_SEARCH', 'Organic Search'
        PAID_SEARCH = 'PAID_SEARCH', 'Paid Search'
        SOCIAL_MEDIA = 'SOCIAL_MEDIA', 'Social Media'
        EMAIL_MARKETING = 'EMAIL_MARKETING', 'Email Marketing'
        REFERRAL = 'REFERRAL', 'Referral'
        DIRECT = 'DIRECT', 'Direct'
        AFFILIATE = 'AFFILIATE', 'Affiliate'
        CONTENT_MARKETING = 'CONTENT_MARKETING', 'Content Marketing'
        INFLUENCER = 'INFLUENCER', 'Influencer'
        OFFLINE = 'OFFLINE', 'Offline'
        OTHER = 'OTHER', 'Other'
    
    # Customer identification
    customer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # User association
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='customer_profile',
        null=True, blank=True
    )
    
    # Basic information
    email = models.EmailField(validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=200, blank=True)
    
    # Customer classification
    status = models.CharField(max_length=15, choices=CustomerStatus.choices, default=CustomerStatus.ACTIVE)
    customer_tier = models.CharField(max_length=10, choices=CustomerTier.choices, default=CustomerTier.BRONZE)
    lifecycle_stage = models.CharField(max_length=15, choices=LifecycleStage.choices, default=LifecycleStage.VISITOR)
    
    # Demographics
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    income_range = models.CharField(max_length=20, blank=True)
    education_level = models.CharField(max_length=50, blank=True)
    
    # Geographic information
    country = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    
    # Customer acquisition
    acquisition_date = models.DateTimeField(auto_now_add=True)
    acquisition_channel = models.CharField(max_length=20, choices=AcquisitionChannel.choices, blank=True)
    acquisition_source = models.CharField(max_length=100, blank=True)
    acquisition_campaign = models.CharField(max_length=100, blank=True)
    acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    referral_code = models.CharField(max_length=50, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    
    # Financial metrics
    total_spent = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_orders = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    predicted_lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Purchase behavior
    first_purchase_date = models.DateTimeField(null=True, blank=True)
    last_purchase_date = models.DateTimeField(null=True, blank=True)
    days_since_last_purchase = models.PositiveIntegerField(null=True, blank=True)
    purchase_frequency = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    favorite_categories = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    preferred_brands = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    
    # AI-powered insights
    churn_probability = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-predicted churn probability (0-100%)"
    )
    next_purchase_prediction = models.DateField(null=True, blank=True)
    recommended_products = models.JSONField(default=list, blank=True)
    customer_segment = models.CharField(max_length=50, blank=True)
    
    # Behavioral analytics
    website_visits = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    session_duration_avg = models.PositiveIntegerField(null=True, blank=True, help_text="Average session duration in seconds")
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Engagement metrics
    email_open_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    email_click_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    social_media_engagement = models.JSONField(default=dict, blank=True)
    loyalty_points_balance = models.PositiveIntegerField(default=0)
    loyalty_points_lifetime = models.PositiveIntegerField(default=0)
    
    # Preferences and interests
    communication_preferences = models.JSONField(default=dict, blank=True)
    product_interests = models.JSONField(default=list, blank=True)
    price_sensitivity = models.CharField(max_length=20, blank=True)
    preferred_contact_method = models.CharField(max_length=20, blank=True)
    marketing_consent = models.BooleanField(default=False)
    
    # Satisfaction and feedback
    satisfaction_score = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    net_promoter_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    feedback_count = models.PositiveIntegerField(default=0)
    complaint_count = models.PositiveIntegerField(default=0)
    
    # Risk assessment
    credit_score = models.PositiveIntegerField(null=True, blank=True)
    payment_reliability = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Payment reliability score (0-100%)"
    )
    fraud_risk_level = models.CharField(max_length=10, default='LOW')
    blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.TextField(blank=True)
    
    # Device and technology preferences
    preferred_devices = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    browser_preferences = models.JSONField(default=dict, blank=True)
    mobile_app_user = models.BooleanField(default=False)
    technology_adoption_score = models.PositiveIntegerField(null=True, blank=True)
    
    # Social influence
    social_influence_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Social media influence score"
    )
    referral_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    average_review_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    
    # Predictive analytics
    predicted_next_order_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    seasonal_buying_pattern = models.JSONField(default=dict, blank=True)
    product_affinity_scores = models.JSONField(default=dict, blank=True)
    price_elasticity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Marketing automation
    lead_score = models.PositiveIntegerField(default=0)
    marketing_qualified = models.BooleanField(default=False)
    sales_qualified = models.BooleanField(default=False)
    nurture_stage = models.CharField(max_length=20, blank=True)
    last_marketing_touch = models.DateTimeField(null=True, blank=True)
    
    # Custom attributes and tags
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    custom_attributes = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    
    # System fields
    is_test_customer = models.BooleanField(default=False)
    gdpr_consent = models.BooleanField(default=False)
    gdpr_consent_date = models.DateTimeField(null=True, blank=True)
    data_processing_consent = models.BooleanField(default=False)
    
    objects = CustomerManager()
    
    class Meta:
        db_table = 'ecommerce_customers'
        ordering = ['-acquisition_date']
        indexes = [
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'status', 'customer_tier']),
            models.Index(fields=['tenant', 'lifecycle_stage']),
            models.Index(fields=['tenant', 'churn_probability']),
            models.Index(fields=['tenant', 'customer_segment']),
            models.Index(fields=['tenant', 'acquisition_channel']),
            models.Index(fields=['tenant', 'last_purchase_date']),
            models.Index(fields=['tenant', 'total_spent']),
            models.Index(fields=['tenant', '-lifetime_value']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'email'],
                name='unique_customer_email_per_tenant'
            ),
            models.CheckConstraint(
                check=models.Q(total_spent__gte=0),
                name='positive_total_spent'
            ),
            models.CheckConstraint(
                check=models.Q(lifetime_value__gte=0),
                name='positive_lifetime_value'
            ),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def save(self, *args, **kwargs):
        if not self.customer_number:
            self.customer_number = self.generate_customer_number()
        
        # Update days since last purchase
        if self.last_purchase_date:
            self.days_since_last_purchase = (timezone.now().date() - self.last_purchase_date.date()).days
        
        # Calculate average order value
        if self.total_orders > 0:
            self.average_order_value = (self.total_spent / self.total_orders).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        super().save(*args, **kwargs)
    
    def generate_customer_number(self):
        """Generate unique customer number"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        prefix = f"CUST-{today}"
        
        last_customer = Customer.objects.filter(
            tenant=self.tenant,
            customer_number__startswith=prefix
        ).order_by('-customer_number').first()
        
        if last_customer:
            try:
                last_seq = int(last_customer.customer_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:06d}"
    
    def get_full_name(self):
        """Get customer's full name"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        elif self.user:
            return self.user.get_full_name() or self.user.username
        return self.email.split('@')[0]
    
    @property
    def age(self):
        """Calculate customer's age"""
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    @property
    def is_new_customer(self):
        """Check if this is a new customer (first 90 days)"""
        return (timezone.now() - self.acquisition_date).days <= 90
    
    @property
    def is_repeat_customer(self):
        """Check if customer has made repeat purchases"""
        return self.total_orders > 1
    
    @property
    def is_vip(self):
        """Check if customer is VIP"""
        return self.customer_tier in ['PLATINUM', 'DIAMOND', 'VIP'] or self.status == 'VIP'
    
    @property
    def is_at_risk(self):
        """Check if customer is at risk of churning"""
        return (self.churn_probability and self.churn_probability > 70) or self.lifecycle_stage == 'AT_RISK'
    
    @property
    def customer_value_segment(self):
        """Get customer value segment based on spending"""
        if self.total_spent >= 5000:
            return 'High Value'
        elif self.total_spent >= 1000:
            return 'Medium Value'
        elif self.total_spent > 0:
            return 'Low Value'
        else:
            return 'No Purchase'
    
    def update_purchase_metrics(self):
        """Update customer purchase metrics from orders"""
        orders = self.orders.filter(status__in=['DELIVERED', 'COMPLETED'])
        
        if orders.exists():
            # Update order counts and spending
            self.total_orders = orders.count()
            self.total_spent = orders.aggregate(
                total=models.Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            # Update dates
            first_order = orders.order_by('placed_at').first()
            last_order = orders.order_by('-placed_at').first()
            
            self.first_purchase_date = first_order.placed_at
            self.last_purchase_date = last_order.placed_at
            
            # Calculate purchase frequency (orders per month)
            if self.first_purchase_date and self.last_purchase_date:
                days_active = (self.last_purchase_date - self.first_purchase_date).days
                if days_active > 0:
                    self.purchase_frequency = (self.total_orders / (days_active / 30.0)).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
            
            # Update favorite categories and brands
            self.update_preferences_from_orders(orders)
        
        self.save(update_fields=[
            'total_orders', 'total_spent', 'first_purchase_date', 
            'last_purchase_date', 'purchase_frequency', 'favorite_categories', 'preferred_brands'
        ])
    
    def update_preferences_from_orders(self, orders):
        """Update customer preferences based on order history"""
        from collections import Counter
        
        # Collect categories and brands from orders
        categories = []
        brands = []
        
        for order in orders:
            for item in order.items.all():
                if hasattr(item.product, 'primary_collection') and item.product.primary_collection:
                    categories.append(item.product.primary_collection.title)
                if item.product.brand:
                    brands.append(item.product.brand)
        
        # Get top 5 categories and brands
        category_counts = Counter(categories)
        brand_counts = Counter(brands)
        
        self.favorite_categories = [cat for cat, count in category_counts.most_common(5)]
        self.preferred_brands = [brand for brand, count in brand_counts.most_common(5)]
    
    def calculate_lifetime_value(self):
        """Calculate customer lifetime value using AI prediction"""
        if self.total_orders == 0:
            self.lifetime_value = Decimal('0.00')
            self.predicted_lifetime_value = Decimal('0.00')
            return
        
        # Historical LTV
        self.lifetime_value = self.total_spent
        
        # Predictive LTV calculation
        if self.purchase_frequency and self.average_order_value:
            # Simple predictive model (can be enhanced with ML)
            monthly_frequency = self.purchase_frequency
            monthly_value = monthly_frequency * self.average_order_value
            
            # Adjust for customer lifecycle stage
            lifecycle_multiplier = {
                'FIRST_TIME': 6,  # 6 months
                'REPEAT': 12,     # 1 year
                'LOYAL': 24,      # 2 years
                'ADVOCATE': 36,   # 3 years
                'AT_RISK': 3,     # 3 months
                'CHURNED': 0,     # 0 months
            }.get(self.lifecycle_stage, 12)
            
            # Adjust for customer tier
            tier_multiplier = {
                'BRONZE': 1.0,
                'SILVER': 1.2,
                'GOLD': 1.5,
                'PLATINUM': 2.0,
                'DIAMOND': 2.5,
                'VIP': 3.0,
            }.get(self.customer_tier, 1.0)
            
            predicted_ltv = monthly_value * lifecycle_multiplier * tier_multiplier
            self.predicted_lifetime_value = predicted_ltv.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        self.save(update_fields=['lifetime_value', 'predicted_lifetime_value'])
    
    def calculate_churn_probability(self):
        """Calculate churn probability using AI/ML algorithms"""
        score = Decimal('0.00')
        
        # Days since last purchase factor
        if self.days_since_last_purchase:
            if self.days_since_last_purchase > 365:
                score += Decimal('40.00')
            elif self.days_since_last_purchase > 180:
                score += Decimal('30.00')
            elif self.days_since_last_purchase > 90:
                score += Decimal('20.00')
            elif self.days_since_last_purchase > 30:
                score += Decimal('10.00')
        
        # Purchase frequency factor
        if self.purchase_frequency:
            if self.purchase_frequency < 0.5:  # Less than once every 2 months
                score += Decimal('25.00')
            elif self.purchase_frequency < 1.0:  # Less than once per month
                score += Decimal('15.00')
        
        # Order count factor
        if self.total_orders == 1:
            score += Decimal('20.00')  # One-time customers have higher churn risk
        elif self.total_orders < 3:
            score += Decimal('10.00')
        
        # Engagement factors
        if self.email_open_rate and self.email_open_rate < 10:
            score += Decimal('15.00')
        
        if self.website_visits == 0:
            score += Decimal('20.00')
        
        # Satisfaction factors
        if self.satisfaction_score and self.satisfaction_score < 6:
            score += Decimal('25.00')
        
        if self.complaint_count > 2:
            score += Decimal('20.00')
        
        # Demographic factors
        if self.age and self.age < 25:
            score += Decimal('5.00')  # Younger customers tend to have higher churn
        
        self.churn_probability = min(score, Decimal('95.00'))
        
        # Update lifecycle stage based on churn probability
        if self.churn_probability > 70:
            self.lifecycle_stage = self.LifecycleStage.AT_RISK
        elif self.churn_probability > 85:
            self.lifecycle_stage = self.LifecycleStage.CHURNED
        
        self.save(update_fields=['churn_probability', 'lifecycle_stage'])
    
    def predict_next_purchase(self):
        """Predict when customer will make next purchase"""
        if not self.purchase_frequency or self.purchase_frequency == 0:
            self.next_purchase_prediction = None
            return
        
        # Calculate average days between purchases
        days_between_purchases = 30 / self.purchase_frequency  # Convert from monthly frequency
        
        # Adjust based on current lifecycle stage
        stage_adjustments = {
            'FIRST_TIME': 0.8,  # Faster next purchase
            'REPEAT': 1.0,
            'LOYAL': 0.9,       # Slightly faster
            'AT_RISK': 1.5,     # Slower
            'CHURNED': 3.0,     # Much slower
        }
        
        adjustment = stage_adjustments.get(self.lifecycle_stage, 1.0)
        predicted_days = days_between_purchases * adjustment
        
        if self.last_purchase_date:
            base_date = self.last_purchase_date.date()
        else:
            base_date = timezone.now().date()
        
        self.next_purchase_prediction = base_date + timedelta(days=int(predicted_days))
        self.save(update_fields=['next_purchase_prediction'])
    
    def generate_product_recommendations(self, limit=10):
        """Generate AI-powered product recommendations"""
        recommendations = []
        
        # Collaborative filtering based on similar customers
        similar_customers = Customer.objects.filter(
            tenant=self.tenant,
            customer_segment=self.customer_segment
        ).exclude(id=self.id)[:100]
        
        # Get products bought by similar customers
        from collections import Counter
        product_scores = Counter()
        
        for customer in similar_customers:
            customer_orders = customer.orders.filter(status__in=['DELIVERED', 'COMPLETED'])
            for order in customer_orders:
                for item in order.items.all():
                    # Skip products already purchased by this customer
                    if not self.orders.filter(items__product=item.product).exists():
                        product_scores[item.product.id] += 1
        
        # Get top recommended products
        from apps.ecommerce.models import EcommerceProduct
        
        for product_id, score in product_scores.most_common(limit):
            try:
                product = EcommerceProduct.objects.get(id=product_id)
                recommendations.append({
                    'product_id': product.id,
                    'title': product.title,
                    'price': float(product.price),
                    'score': score,
                    'reason': 'Customers like you also bought'
                })
            except EcommerceProduct.DoesNotExist:
                continue
        
        # Add category-based recommendations
        if self.favorite_categories:
            category_products = EcommerceProduct.objects.filter(
                tenant=self.tenant,
                primary_collection__title__in=self.favorite_categories,
                is_published=True
            ).exclude(
                id__in=self.orders.values_list('items__product_id', flat=True)
            )[:5]
            
            for product in category_products:
                recommendations.append({
                    'product_id': product.id,
                    'title': product.title,
                    'price': float(product.price),
                    'score': 50,  # Base score for category match
                    'reason': f'Based on your interest in {product.primary_collection.title}'
                })
        
        self.recommended_products = recommendations[:limit]
        self.save(update_fields=['recommended_products'])
        
        return recommendations
    
    def update_customer_segment(self):
        """Update customer segment using AI clustering"""
        # Simple rule-based segmentation (can be enhanced with ML clustering)
        
        if self.total_spent >= 5000 and self.total_orders >= 10:
            segment = 'VIP_HIGH_VALUE'
        elif self.total_spent >= 2000 and self.total_orders >= 5:
            segment = 'HIGH_VALUE'
        elif self.total_spent >= 500 and self.purchase_frequency and self.purchase_frequency > 1:
            segment = 'FREQUENT_BUYER'
        elif self.total_orders == 1 and self.total_spent > 100:
            segment = 'HIGH_POTENTIAL'
        elif self.total_orders == 1:
            segment = 'ONE_TIME_BUYER'
        elif self.days_since_last_purchase and self.days_since_last_purchase > 365:
            segment = 'DORMANT'
        elif self.churn_probability and self.churn_probability > 70:
            segment = 'AT_RISK'
        else:
            segment = 'REGULAR'
        
        self.customer_segment = segment
        self.save(update_fields=['customer_segment'])
    
    def calculate_lead_score(self):
        """Calculate marketing lead score"""
        score = 0
        
        # Demographics scoring
        if self.age:
            if 25 <= self.age <= 54:  # Prime buying age
                score += 10
        
        if self.income_range:
            income_scores = {
                'HIGH': 15,
                'MEDIUM_HIGH': 10,
                'MEDIUM': 5
            }
            score += income_scores.get(self.income_range, 0)
        
        # Engagement scoring
        if self.email_open_rate:
            if self.email_open_rate > 25:
                score += 20
            elif self.email_open_rate > 15:
                score += 10
        
        if self.website_visits > 10:
            score += 15
        elif self.website_visits > 5:
            score += 10
        
        # Behavioral scoring
        if self.page_views > 20:
            score += 10
        
        if self.session_duration_avg and self.session_duration_avg > 300:  # 5 minutes
            score += 15
        
        # Purchase intent scoring
        if self.total_orders > 0:
            score += 50  # Existing customer
        
        if 'abandoned_cart' in self.tags:
            score += 25  # Showed purchase intent
        
        self.lead_score = min(score, 100)
        
        # Update qualification flags
        if self.lead_score >= 70:
            self.marketing_qualified = True
            self.sales_qualified = True
        elif self.lead_score >= 50:
            self.marketing_qualified = True
        
        self.save(update_fields=['lead_score', 'marketing_qualified', 'sales_qualified'])
    
    def get_customer_insights(self):
        """Get comprehensive AI-powered customer insights"""
        insights = {
            'value_segment': self.customer_value_segment,
            'lifecycle_stage': self.lifecycle_stage,
            'churn_risk': {
                'probability': float(self.churn_probability or 0),
                'level': 'High' if self.is_at_risk else 'Low',
                'factors': self.get_churn_risk_factors()
            },
            'purchase_behavior': {
                'frequency': float(self.purchase_frequency or 0),
                'average_order_value': float(self.average_order_value),
                'preferred_categories': self.favorite_categories,
                'next_purchase_prediction': self.next_purchase_prediction.isoformat() if self.next_purchase_prediction else None
            },
            'engagement': {
                'email_engagement': float(self.email_open_rate or 0),
                'website_activity': self.website_visits,
                'satisfaction_score': float(self.satisfaction_score or 0)
            },
            'recommendations': {
                'products': self.recommended_products[:5],
                'marketing_actions': self.get_marketing_recommendations(),
                'retention_strategies': self.get_retention_strategies()
            },
            'financial': {
                'lifetime_value': float(self.lifetime_value),
                'predicted_ltv': float(self.predicted_lifetime_value or 0),
                'acquisition_cost': float(self.acquisition_cost or 0),
                'roi': self.calculate_customer_roi()
            }
        }
        
        return insights
    
    def get_churn_risk_factors(self):
        """Get factors contributing to churn risk"""
        factors = []
        
        if self.days_since_last_purchase and self.days_since_last_purchase > 90:
            factors.append(f"No purchase in {self.days_since_last_purchase} days")
        
        if self.email_open_rate and self.email_open_rate < 10:
            factors.append("Low email engagement")
        
        if self.complaint_count > 0:
            factors.append(f"{self.complaint_count} complaints on record")
        
        if self.satisfaction_score and self.satisfaction_score < 6:
            factors.append("Low satisfaction score")
        
        if self.total_orders == 1:
            factors.append("One-time customer")
        
        return factors
    
    def get_marketing_recommendations(self):
        """Get AI-powered marketing recommendations"""
        recommendations = []
        
        if self.is_at_risk:
            recommendations.append({
                'action': 'RETENTION_CAMPAIGN',
                'message': 'Send targeted retention email with discount',
                'priority': 'HIGH'
            })
        
        if self.churn_probability and self.churn_probability > 50:
            recommendations.append({
                'action': 'WINBACK_CAMPAIGN',
                'message': 'Launch win-back campaign with personalized offers',
                'priority': 'MEDIUM'
            })
        
        if self.lead_score > 70 and self.total_orders == 0:
            recommendations.append({
                'action': 'NURTURE_SEQUENCE',
                'message': 'Enroll in purchase conversion sequence',
                'priority': 'HIGH'
            })
        
        if self.is_vip:
            recommendations.append({
                'action': 'VIP_ENGAGEMENT',
                'message': 'Send VIP exclusive offers and early access',
                'priority': 'MEDIUM'
            })
        
        return recommendations
    
    def get_retention_strategies(self):
        """Get personalized retention strategies"""
        strategies = []
        
        if self.price_sensitivity == 'HIGH':
            strategies.append('Offer price-based incentives and discounts')
        
        if self.favorite_categories:
            strategies.append(f'Target with {", ".join(self.favorite_categories[:2])} products')
        
        if self.loyalty_points_balance > 0:
            strategies.append('Remind about unused loyalty points')
        
        if self.email_open_rate and self.email_open_rate > 20:
            strategies.append('Increase email marketing frequency')
        
        return strategies
    
    def calculate_customer_roi(self):
        """Calculate return on investment for this customer"""
        if not self.acquisition_cost or self.acquisition_cost == 0:
            return None
        
        roi = ((self.lifetime_value - self.acquisition_cost) / self.acquisition_cost * 100)
        return float(roi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


class CustomerAddress(EcommerceBaseModel, AuditMixin):
    """
    Customer address management with AI-powered validation and insights
    """
    
    class AddressType(models.TextChoices):
        BILLING = 'BILLING', 'Billing Address'
        SHIPPING = 'SHIPPING', 'Shipping Address'
        BOTH = 'BOTH', 'Billing & Shipping'
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=AddressType.choices, default=AddressType.BOTH)
    
    # Address fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=200, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    
    # Address validation and metadata
    is_validated = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)
    is_default_shipping = models.BooleanField(default=False)
    
    # Geolocation data
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    
    # Delivery insights
    delivery_difficulty_score = models.PositiveIntegerField(null=True, blank=True, help_text="1-10 scale")
    average_delivery_time_hours = models.PositiveIntegerField(null=True, blank=True)
    delivery_success_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Usage statistics
    order_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_customer_addresses'
        ordering = ['-is_default_billing', '-is_default_shipping', '-last_used']
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'is_default_billing']),
            models.Index(fields=['tenant', 'is_default_shipping']),
            models.Index(fields=['tenant', 'postal_code']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.city}, {self.state_province}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default billing address per customer
        if self.is_default_billing:
            CustomerAddress.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default_billing=True
            ).exclude(pk=self.pk).update(is_default_billing=False)
        
        # Ensure only one default shipping address per customer
        if self.is_default_shipping:
            CustomerAddress.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default_shipping=True
            ).exclude(pk=self.pk).update(is_default_shipping=False)
        
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        """Get full name for address"""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def formatted_address(self):
        """Get formatted address string"""
        parts = [
            self.address_line_1,
            self.address_line_2,
            f"{self.city}, {self.state_province} {self.postal_code}",
            self.country
        ]
        return "\n".join(part for part in parts if part)
    
    def validate_address(self):
        """Validate address using external service (placeholder)"""
        # This would integrate with address validation services like Google, UPS, etc.
        self.is_validated = True
        self.save(update_fields=['is_validated'])
        return True
    
    def update_delivery_insights(self):
        """Update delivery performance insights for this address"""
        # This would be called after each delivery to this address
        orders_to_address = self.customer.orders.filter(
            shipping_address__icontains=self.postal_code
        )
        
        if orders_to_address.exists():
            self.order_count = orders_to_address.count()
            
            # Calculate delivery success rate
            delivered_orders = orders_to_address.filter(status='DELIVERED')
            if orders_to_address.count() > 0:
                self.delivery_success_rate = (
                    delivered_orders.count() / orders_to_address.count() * 100
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Calculate average delivery time
            delivery_times = []
            for order in delivered_orders:
                if order.shipped_at and order.delivered_at:
                    delivery_time = (order.delivered_at - order.shipped_at).total_seconds() / 3600
                    delivery_times.append(delivery_time)
            
            if delivery_times:
                self.average_delivery_time_hours = int(sum(delivery_times) / len(delivery_times))
            
            self.last_used = orders_to_address.order_by('-placed_at').first().placed_at
            
            self.save(update_fields=[
                'order_count', 'delivery_success_rate', 
                'average_delivery_time_hours', 'last_used'
            ])