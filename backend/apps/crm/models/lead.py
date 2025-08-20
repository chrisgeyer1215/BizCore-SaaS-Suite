# ============================================================================
# backend/apps/crm/models/lead.py - Lead Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import json

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class LeadSource(TenantBaseModel, SoftDeleteMixin):
    """Enhanced lead source tracking with ROI analysis"""
    
    SOURCE_TYPES = [
        ('WEBSITE', 'Website'),
        ('SOCIAL_MEDIA', 'Social Media'),
        ('EMAIL_CAMPAIGN', 'Email Campaign'),
        ('PHONE_CALL', 'Phone Call'),
        ('TRADE_SHOW', 'Trade Show'),
        ('REFERRAL', 'Referral'),
        ('ADVERTISEMENT', 'Advertisement'),
        ('DIRECT_MAIL', 'Direct Mail'),
        ('WEBINAR', 'Webinar'),
        ('CONTENT_MARKETING', 'Content Marketing'),
        ('SEO', 'Search Engine Optimization'),
        ('PPC', 'Pay Per Click'),
        ('PARTNER', 'Partner'),
        ('COLD_OUTREACH', 'Cold Outreach'),
        ('OTHER', 'Other'),
    ]
    
    # Source Information
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    description = models.TextField(blank=True)
    
    # Campaign Association
    campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_sources'
    )
    
    # Performance Metrics
    total_leads = models.IntegerField(default=0)
    converted_leads = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_assignment_enabled = models.BooleanField(default=False)
    default_assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_lead_sources'
    )
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_lead_source'
            ),
        ]
        
    def __str__(self):
        return self.name
    
    @property
    def conversion_rate(self):
        """Calculate conversion rate"""
        if self.total_leads > 0:
            return (self.converted_leads / self.total_leads) * 100
        return 0
    
    @property
    def roi(self):
        """Calculate return on investment"""
        if self.cost > 0:
            return ((self.total_revenue - self.cost) / self.cost) * 100
        return 0
    
    @property
    def cost_per_lead(self):
        """Calculate cost per lead"""
        if self.total_leads > 0:
            return self.cost / self.total_leads
        return 0


class Lead(TenantBaseModel, SoftDeleteMixin):
    """Enhanced lead management with scoring and nurturing"""
    
    LEAD_STATUS = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('QUALIFIED', 'Qualified'),
        ('UNQUALIFIED', 'Unqualified'),
        ('NURTURING', 'Nurturing'),
        ('CONVERTED', 'Converted'),
        ('LOST', 'Lost'),
        ('RECYCLED', 'Recycled'),
    ]
    
    LEAD_RATINGS = [
        ('HOT', 'Hot'),
        ('WARM', 'Warm'),
        ('COLD', 'Cold'),
    ]
    
    COMPANY_SIZES = [
        ('STARTUP', '1-10 employees'),
        ('SMALL', '11-50 employees'),
        ('MEDIUM', '51-200 employees'),
        ('LARGE', '201-1000 employees'),
        ('ENTERPRISE', '1000+ employees'),
    ]
    
    # Lead Identification
    lead_number = models.CharField(max_length=50, blank=True)
    
    # Personal Information
    salutation = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    
    # Company Information
    company = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    industry = models.ForeignKey(
        'Industry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    company_size = models.CharField(max_length=20, choices=COMPANY_SIZES, blank=True)
    annual_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    website = models.URLField(blank=True)
    
    # Lead Management
    status = models.CharField(max_length=20, choices=LEAD_STATUS, default='NEW')
    rating = models.CharField(max_length=10, choices=LEAD_RATINGS, default='COLD')
    source = models.ForeignKey(
        LeadSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    
    # Assignment & Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_leads'
    )
    assigned_date = models.DateTimeField(null=True, blank=True)
    
    # Lead Scoring
    score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    last_score_update = models.DateTimeField(null=True, blank=True)
    score_breakdown = models.JSONField(default=dict)
    
    # Qualification
    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    timeframe = models.CharField(max_length=100, blank=True)
    decision_maker = models.BooleanField(default=False)
    
    # Contact Preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
            ('TEXT', 'Text Message'),
        ],
        default='EMAIL'
    )
    do_not_call = models.BooleanField(default=False)
    do_not_email = models.BooleanField(default=False)
    
    # Address Information
    address = models.JSONField(default=dict)
    
    # Social Media
    linkedin_url = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    
    # Conversion Tracking
    converted_account = models.ForeignKey(
        'Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_leads'
    )
    converted_contact = models.ForeignKey(
        'Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_leads'
    )
    converted_opportunity = models.ForeignKey(
        'Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_leads'
    )
    converted_date = models.DateTimeField(null=True, blank=True)
    
    # Activity Tracking
    last_activity_date = models.DateTimeField(null=True, blank=True)
    next_follow_up_date = models.DateTimeField(null=True, blank=True)
    total_activities = models.IntegerField(default=0)
    
    # Campaign Association
    campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    
    # Additional Information
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    custom_fields = models.JSONField(default=dict)
    
    # Duplicate Detection
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates'
    )
    is_duplicate = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'owner']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'company']),
            models.Index(fields=['tenant', 'score']),
            models.Index(fields=['tenant', 'source']),
            models.Index(fields=['tenant', 'last_activity_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'email'],
                name='unique_tenant_lead_email'
            ),
        ]
        
    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.company or "No Company"})'
    
    def save(self, *args, **kwargs):
        if not self.lead_number:
            self.lead_number = self.generate_lead_number()
        if self.owner and not self.assigned_date:
            self.assigned_date = timezone.now()
        super().save(*args, **kwargs)
    
    def generate_lead_number(self):
        """Generate unique lead number"""
        return generate_code('LEAD', self.tenant_id)
    
    @property
    def full_name(self):
        """Get full name"""
        return f'{self.first_name} {self.last_name}'
    
    @property
    def days_since_created(self):
        """Days since lead was created"""
        return (timezone.now() - self.created_at).days
    
    @property
    def days_since_last_activity(self):
        """Days since last activity"""
        if self.last_activity_date:
            return (timezone.now() - self.last_activity_date).days
        return self.days_since_created
    
    def calculate_score(self):
        """Calculate lead score based on rules"""
        from ..services import LeadScoringService
        
        service = LeadScoringService(self.tenant)
        self.score = service.calculate_lead_score(self)
        self.last_score_update = timezone.now()
        self.save(update_fields=['score', 'last_score_update', 'score_breakdown'])
    
    def convert_to_account(self, user):
        """Convert lead to account, contact, and optionally opportunity"""
        from ..services import LeadConversionService
        
        service = LeadConversionService(self.tenant)
        return service.convert_lead(self, user)


class LeadScoringRule(TenantBaseModel, SoftDeleteMixin):
    """Enhanced lead scoring rules engine"""
    
    RULE_TYPES = [
        ('DEMOGRAPHIC', 'Demographic'),
        ('BEHAVIORAL', 'Behavioral'),
        ('FIRMOGRAPHIC', 'Firmographic'),
        ('ENGAGEMENT', 'Engagement'),
        ('ACTIVITY', 'Activity'),
    ]
    
    CONDITION_OPERATORS = [
        ('EQUALS', 'Equals'),
        ('NOT_EQUALS', 'Not Equals'),
        ('CONTAINS', 'Contains'),
        ('NOT_CONTAINS', 'Does Not Contain'),
        ('STARTS_WITH', 'Starts With'),
        ('ENDS_WITH', 'Ends With'),
        ('GREATER_THAN', 'Greater Than'),
        ('LESS_THAN', 'Less Than'),
        ('GREATER_EQUAL', 'Greater Than or Equal'),
        ('LESS_EQUAL', 'Less Than or Equal'),
        ('IN_LIST', 'In List'),
        ('NOT_IN_LIST', 'Not In List'),
        ('IS_EMPTY', 'Is Empty'),
        ('IS_NOT_EMPTY', 'Is Not Empty'),
    ]
    
    # Rule Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    
    # Rule Configuration
    field_name = models.CharField(max_length=100)
    operator = models.CharField(max_length=20, choices=CONDITION_OPERATORS)
    value = models.TextField()  # Can store multiple values as JSON
    
    # Scoring
    score_change = models.IntegerField(
        validators=[MinValueValidator(-100), MaxValueValidator(100)]
    )
    
    # Rule Settings
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=10)
    
    # Usage Statistics
    times_applied = models.IntegerField(default=0)
    last_applied = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'rule_type']),
            models.Index(fields=['tenant', 'priority']),
        ]
        
    def __str__(self):
        return f'{self.name} ({self.score_change:+d} points)'
    
    def apply_to_lead(self, lead):
        """Apply this rule to a lead and return score change"""
        try:
            field_value = getattr(lead, self.field_name, None)
            rule_values = json.loads(self.value) if self.value.startswith('[') else [self.value]
            
            # Apply operator logic
            if self.operator == 'EQUALS' and str(field_value) == str(rule_values[0]):
                return self.score_change
            elif self.operator == 'NOT_EQUALS' and str(field_value) != str(rule_values[0]):
                return self.score_change
            elif self.operator == 'CONTAINS' and field_value and str(rule_values[0]).lower() in str(field_value).lower():
                return self.score_change
            elif self.operator == 'IN_LIST' and str(field_value) in rule_values:
                return self.score_change
            # Add more operators as needed
            
        except Exception:
            pass  # Rule application failed
        
        return 0