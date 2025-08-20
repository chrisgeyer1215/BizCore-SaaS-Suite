# ============================================================================
# backend/apps/crm/models/account.py - Account and Contact Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import EmailValidator
from django.utils import timezone
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class Industry(TenantBaseModel, SoftDeleteMixin):
    """Industry classification for accounts and leads"""
    
    # Industry Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent_industry = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_industries'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # Analytics
    total_accounts = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Industries'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_industry_code'
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-calculate level based on parent
        if self.parent_industry:
            self.level = self.parent_industry.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)


class Account(TenantBaseModel, SoftDeleteMixin):
    """Enhanced customer/company accounts with finance integration"""
    
    ACCOUNT_TYPES = [
        ('PROSPECT', 'Prospect'),
        ('CUSTOMER', 'Customer'),
        ('PARTNER', 'Partner'),
        ('VENDOR', 'Vendor'),
        ('COMPETITOR', 'Competitor'),
        ('RESELLER', 'Reseller'),
        ('INVESTOR', 'Investor'),
    ]
    
    ACCOUNT_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PROSPECT', 'Prospect'),
        ('CUSTOMER', 'Customer'),
        ('CLOSED', 'Closed'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    COMPANY_SIZES = [
        ('STARTUP', '1-10 employees'),
        ('SMALL', '11-50 employees'),
        ('MEDIUM', '51-200 employees'),
        ('LARGE', '201-1000 employees'),
        ('ENTERPRISE', '1000+ employees'),
    ]
    
    # Basic Information
    account_number = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='PROSPECT')
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS, default='PROSPECT')
    
    # Company Details
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts'
    )
    website = models.URLField(blank=True)
    company_size = models.CharField(max_length=20, choices=COMPANY_SIZES, blank=True)
    annual_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    employee_count = models.IntegerField(null=True, blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Address Information
    billing_address = models.JSONField(default=dict)
    shipping_address = models.JSONField(default=dict)
    
    # Social Media
    linkedin_url = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    facebook_url = models.URLField(blank=True)
    
    # Business Information
    tax_id = models.CharField(max_length=50, blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    duns_number = models.CharField(max_length=20, blank=True)
    
    # Ownership & Management
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_accounts'
    )
    parent_account = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_accounts'
    )
    
    # Relationship Information
    customer_since = models.DateField(null=True, blank=True)
    last_activity_date = models.DateTimeField(null=True, blank=True)
    relationship_strength = models.CharField(
        max_length=20,
        choices=[
            ('COLD', 'Cold'),
            ('WARM', 'Warm'),
            ('HOT', 'Hot'),
            ('CHAMPION', 'Champion'),
        ],
        default='COLD'
    )
    
    # Financial Integration (linking to finance module)
    finance_customer_id = models.IntegerField(null=True, blank=True)
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    payment_terms = models.CharField(max_length=50, blank=True)
    
    # Sales Performance
    total_opportunities = models.IntegerField(default=0)
    total_won_opportunities = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_deal_size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    last_purchase_date = models.DateField(null=True, blank=True)
    
    # Territory & Team
    territory = models.ForeignKey(
        'Territory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts'
    )
    
    # Preferences & Settings
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
            ('TEXT', 'Text Message'),
            ('MAIL', 'Postal Mail'),
        ],
        default='EMAIL'
    )
    do_not_call = models.BooleanField(default=False)
    do_not_email = models.BooleanField(default=False)
    
    # Additional Information
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    custom_fields = models.JSONField(default=dict)
    
    # System Fields
    lead_source = models.CharField(max_length=100, blank=True)
    original_lead_id = models.CharField(max_length=36, blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'account_type', 'status']),
            models.Index(fields=['tenant', 'owner']),
            models.Index(fields=['tenant', 'industry']),
            models.Index(fields=['tenant', 'territory']),
            models.Index(fields=['tenant', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'account_number'],
                name='unique_tenant_account_number',
                condition=models.Q(account_number__isnull=False)
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)
    
    def generate_account_number(self):
        """Generate unique account number"""
        return generate_code('ACC', self.tenant_id)
    
    @property
    def primary_contact(self):
        """Get primary contact for this account"""
        return self.contacts.filter(is_primary=True).first()
    
    @property
    def win_rate(self):
        """Calculate opportunity win rate"""
        if self.total_opportunities > 0:
            return (self.total_won_opportunities / self.total_opportunities) * 100
        return 0
    
    def update_revenue_metrics(self):
        """Update revenue metrics from opportunities"""
        from .opportunity import Opportunity
        
        won_opportunities = self.opportunities.filter(is_won=True)
        self.total_won_opportunities = won_opportunities.count()
        self.total_revenue = won_opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        if self.total_won_opportunities > 0:
            self.average_deal_size = self.total_revenue / self.total_won_opportunities
        
        self.save(update_fields=[
            'total_won_opportunities',
            'total_revenue',
            'average_deal_size'
        ])


class Contact(TenantBaseModel, SoftDeleteMixin):
    """Enhanced contact management with relationship tracking"""
    
    SALUTATION_CHOICES = [
        ('Mr.', 'Mr.'),
        ('Ms.', 'Ms.'),
        ('Mrs.', 'Mrs.'),
        ('Dr.', 'Dr.'),
        ('Prof.', 'Prof.'),
    ]
    
    CONTACT_TYPES = [
        ('PRIMARY', 'Primary Contact'),
        ('DECISION_MAKER', 'Decision Maker'),
        ('INFLUENCER', 'Influencer'),
        ('USER', 'End User'),
        ('TECHNICAL', 'Technical Contact'),
        ('BILLING', 'Billing Contact'),
        ('SUPPORT', 'Support Contact'),
    ]
    
    # Account Association
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    
    # Personal Information
    salutation = models.CharField(max_length=10, choices=SALUTATION_CHOICES, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    
    # Contact Details
    email = models.EmailField()
    secondary_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    
    # Professional Information
    job_title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports'
    )
    
    # Contact Classification
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES, default='PRIMARY')
    is_primary = models.BooleanField(default=False)
    is_decision_maker = models.BooleanField(default=False)
    
    # Address Information (if different from account)
    mailing_address = models.JSONField(default=dict)
    
    # Preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
            ('MOBILE', 'Mobile'),
            ('TEXT', 'Text Message'),
        ],
        default='EMAIL'
    )
    do_not_call = models.BooleanField(default=False)
    do_not_email = models.BooleanField(default=False)
    do_not_text = models.BooleanField(default=False)
    
    # Social Media
    linkedin_url = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    
    # Personal Details
    birthday = models.DateField(null=True, blank=True)
    anniversary = models.DateField(null=True, blank=True)
    interests = models.TextField(blank=True)
    
    # Relationship Information
    relationship_strength = models.CharField(
        max_length=20,
        choices=[
            ('COLD', 'Cold'),
            ('WARM', 'Warm'),
            ('HOT', 'Hot'),
            ('CHAMPION', 'Champion'),
        ],
        default='COLD'
    )
    last_contact_date = models.DateTimeField(null=True, blank=True)
    next_contact_date = models.DateTimeField(null=True, blank=True)
    
    # Performance Tracking
    total_activities = models.IntegerField(default=0)
    total_opportunities = models.IntegerField(default=0)
    total_revenue_influenced = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Additional Information
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    custom_fields = models.JSONField(default=dict)
    
    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_contacts'
    )
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['tenant', 'account', 'is_primary']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'last_name', 'first_name']),
            models.Index(fields=['tenant', 'owner']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'account', 'is_primary'],
                name='unique_primary_contact_per_account',
                condition=models.Q(is_primary=True)
            ),
        ]
        
    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.account.name})'
    
    @property
    def full_name(self):
        """Get full name with salutation"""
        parts = [self.salutation, self.first_name, self.last_name]
        return ' '.join(filter(None, parts))
    
    @property
    def display_name(self):
        """Get display name for UI"""
        return f'{self.first_name} {self.last_name}'
    
    def save(self, *args, **kwargs):
        # Ensure only one primary contact per account
        if self.is_primary:
            Contact.objects.filter(
                tenant=self.tenant,
                account=self.account,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)