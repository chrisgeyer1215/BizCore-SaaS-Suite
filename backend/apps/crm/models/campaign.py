# ============================================================================
# backend/apps/crm/models/campaign.py - Marketing Campaign Models
# ============================================================================

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid
import json

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class CampaignType(TenantBaseModel, SoftDeleteMixin):
    """Campaign type classification for better organization"""
    
    # Type Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    
    # Configuration
    default_duration_days = models.IntegerField(default=30)
    default_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Templates
    email_template = models.TextField(blank=True)
    landing_page_template = models.TextField(blank=True)
    
    # Settings
    requires_approval = models.BooleanField(default=False)
    auto_start = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_campaign_type_code'
            ),
        ]
        
    def __str__(self):
        return self.name


class Campaign(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive marketing campaign management"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PLANNING', 'Planning'),
        ('SCHEDULED', 'Scheduled'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ARCHIVED', 'Archived'),
    ]
    
    CAMPAIGN_TYPES = [
        ('EMAIL', 'Email Marketing'),
        ('SMS', 'SMS Marketing'),
        ('SOCIAL', 'Social Media'),
        ('PPC', 'Pay-Per-Click'),
        ('CONTENT', 'Content Marketing'),
        ('EVENT', 'Event Marketing'),
        ('WEBINAR', 'Webinar'),
        ('DIRECT_MAIL', 'Direct Mail'),
        ('TELEMARKETING', 'Telemarketing'),
        ('REFERRAL', 'Referral Program'),
        ('AFFILIATE', 'Affiliate Marketing'),
        ('RETARGETING', 'Retargeting'),
        ('LEAD_NURTURE', 'Lead Nurturing'),
        ('CUSTOMER_RETENTION', 'Customer Retention'),
        ('PRODUCT_LAUNCH', 'Product Launch'),
        ('BRAND_AWARENESS', 'Brand Awareness'),
        ('SURVEY', 'Survey Campaign'),
        ('MIXED', 'Mixed Media'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    
    # Campaign Type Reference
    type_template = models.ForeignKey(
        CampaignType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )
    
    # Objectives and Goals
    primary_objective = models.CharField(max_length=255, blank=True)
    success_metrics = models.JSONField(default=list, blank=True)
    target_audience_description = models.TextField(blank=True)
    
    # Budget and Financial
    total_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    spent_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    cost_per_lead_target = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    roi_target = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Timeline
    planned_start_date = models.DateTimeField()
    planned_end_date = models.DateTimeField()
    actual_start_date = models.DateTimeField(null=True, blank=True)
    actual_end_date = models.DateTimeField(null=True, blank=True)
    
    # Team and Ownership
    campaign_manager = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='managed_campaigns'
    )
    team_members = models.ManyToManyField(
        User,
        through='CampaignTeamMember',
        related_name='campaign_memberships',
        blank=True
    )
    
    # Content and Creative
    message = models.TextField(blank=True)
    call_to_action = models.CharField(max_length=255, blank=True)
    landing_page_url = models.URLField(blank=True)
    creative_assets = models.JSONField(default=list, blank=True)
    
    # Targeting and Segmentation
    target_demographics = models.JSONField(default=dict, blank=True)
    geographic_targeting = models.JSONField(default=dict, blank=True)
    behavioral_targeting = models.JSONField(default=dict, blank=True)
    
    # Channel Configuration
    email_settings = models.JSONField(default=dict, blank=True)
    sms_settings = models.JSONField(default=dict, blank=True)
    social_settings = models.JSONField(default=dict, blank=True)
    ppc_settings = models.JSONField(default=dict, blank=True)
    
    # Performance Metrics
    impressions = models.BigIntegerField(default=0)
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    leads_generated = models.IntegerField(default=0)
    opportunities_created = models.IntegerField(default=0)
    revenue_generated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Engagement Metrics
    email_opens = models.IntegerField(default=0)
    email_clicks = models.IntegerField(default=0)
    email_bounces = models.IntegerField(default=0)
    email_unsubscribes = models.IntegerField(default=0)
    social_shares = models.IntegerField(default=0)
    social_likes = models.IntegerField(default=0)
    social_comments = models.IntegerField(default=0)
    
    # A/B Testing
    is_ab_test = models.BooleanField(default=False)
    ab_test_config = models.JSONField(default=dict, blank=True)
    winning_variant = models.CharField(max_length=50, blank=True)
    
    # Automation and Workflows
    automation_enabled = models.BooleanField(default=False)
    workflow_rules = models.JSONField(default=list, blank=True)
    trigger_conditions = models.JSONField(default=dict, blank=True)
    
    # Integration Settings
    utm_parameters = models.JSONField(default=dict, blank=True)
    tracking_codes = models.JSONField(default=dict, blank=True)
    external_campaign_ids = models.JSONField(default=dict, blank=True)
    
    # Approval Workflow
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_campaigns'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Compliance and Legal
    compliance_notes = models.TextField(blank=True)
    legal_review_required = models.BooleanField(default=False)
    data_retention_period_days = models.IntegerField(default=365)
    
    # Custom Fields
    custom_fields = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-planned_start_date', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'campaign_type']),
            models.Index(fields=['tenant', 'campaign_manager']),
            models.Index(fields=['tenant', 'planned_start_date', 'planned_end_date']),
            models.Index(fields=['tenant', 'priority']),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-set actual dates based on status
        if self.status == 'ACTIVE' and not self.actual_start_date:
            self.actual_start_date = timezone.now()
        elif self.status in ['COMPLETED', 'CANCELLED'] and not self.actual_end_date:
            self.actual_end_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def duration_days(self):
        """Calculate campaign duration in days"""
        if self.actual_end_date and self.actual_start_date:
            return (self.actual_end_date - self.actual_start_date).days
        elif self.actual_start_date:
            return (timezone.now() - self.actual_start_date).days
        else:
            return (self.planned_end_date - self.planned_start_date).days
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.total_budget and self.total_budget > 0:
            return (self.spent_budget / self.total_budget) * 100
        return Decimal('0.00')
    
    @property
    def click_through_rate(self):
        """Calculate click-through rate"""
        if self.impressions > 0:
            return (self.clicks / self.impressions) * 100
        return Decimal('0.00')
    
    @property
    def conversion_rate(self):
        """Calculate conversion rate"""
        if self.clicks > 0:
            return (self.conversions / self.clicks) * 100
        return Decimal('0.00')
    
    @property
    def cost_per_lead(self):
        """Calculate cost per lead"""
        if self.leads_generated > 0:
            return self.spent_budget / self.leads_generated
        return Decimal('0.00')
    
    @property
    def roi(self):
        """Calculate return on investment"""
        if self.spent_budget > 0:
            profit = self.revenue_generated - self.spent_budget
            return (profit / self.spent_budget) * 100
        return Decimal('0.00')
    
    @property
    def is_active(self):
        """Check if campaign is currently active"""
        now = timezone.now()
        return (
            self.status == 'ACTIVE' and
            self.planned_start_date <= now <= self.planned_end_date
        )
    
    def get_performance_summary(self):
        """Get comprehensive performance summary"""
        return {
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'leads_generated': self.leads_generated,
            'opportunities_created': self.opportunities_created,
            'revenue_generated': float(self.revenue_generated),
            'spent_budget': float(self.spent_budget),
            'click_through_rate': float(self.click_through_rate),
            'conversion_rate': float(self.conversion_rate),
            'cost_per_lead': float(self.cost_per_lead),
            'roi': float(self.roi),
            'budget_utilization': float(self.budget_utilization),
        }
    
    def update_metrics(self, **kwargs):
        """Update campaign metrics"""
        for field, value in kwargs.items():
            if hasattr(self, field):
                setattr(self, field, value)
        self.save()


class CampaignTeamMember(TenantBaseModel):
    """Campaign team member roles and responsibilities"""
    
    ROLE_CHOICES = [
        ('MANAGER', 'Campaign Manager'),
        ('COORDINATOR', 'Campaign Coordinator'),
        ('CREATIVE', 'Creative Lead'),
        ('ANALYST', 'Data Analyst'),
        ('COPYWRITER', 'Copywriter'),
        ('DESIGNER', 'Designer'),
        ('DEVELOPER', 'Developer'),
        ('CONSULTANT', 'Consultant'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='team_assignments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='campaign_assignments'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    responsibilities = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'user', 'role'],
                name='unique_campaign_user_role'
            ),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.user.get_full_name()} ({self.role})'


class CampaignMember(TenantBaseModel, SoftDeleteMixin):
    """Target audience members for campaigns"""
    
    MEMBER_TYPES = [
        ('LEAD', 'Lead'),
        ('CONTACT', 'Contact'),
        ('ACCOUNT', 'Account'),
        ('OPPORTUNITY', 'Opportunity'),
        ('CUSTOMER', 'Customer'),
    ]
    
    MEMBER_STATUS = [
        ('PENDING', 'Pending'),
        ('TARGETED', 'Targeted'),
        ('CONTACTED', 'Contacted'),
        ('ENGAGED', 'Engaged'),
        ('CONVERTED', 'Converted'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('BOUNCED', 'Bounced'),
        ('EXCLUDED', 'Excluded'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Generic relation to CRM entities
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36)
    member = GenericForeignKey('content_type', 'object_id')
    
    # Member Information
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPES)
    status = models.CharField(max_length=15, choices=MEMBER_STATUS, default='PENDING')
    
    # Contact Information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=255, blank=True)
    
    # Targeting Metadata
    source = models.CharField(max_length=100, blank=True)  # How they were added
    segment = models.CharField(max_length=100, blank=True)
    targeting_criteria = models.JSONField(default=dict, blank=True)
    
    # Engagement Tracking
    added_date = models.DateTimeField(auto_now_add=True)
    first_contacted = models.DateTimeField(null=True, blank=True)
    last_engaged = models.DateTimeField(null=True, blank=True)
    engagement_score = models.IntegerField(default=0)
    
    # Response Tracking
    emails_sent = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    emails_bounced = models.IntegerField(default=0)
    sms_sent = models.IntegerField(default=0)
    sms_delivered = models.IntegerField(default=0)
    calls_made = models.IntegerField(default=0)
    calls_answered = models.IntegerField(default=0)
    
    # Conversion Tracking
    converted = models.BooleanField(default=False)
    conversion_date = models.DateTimeField(null=True, blank=True)
    conversion_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Preferences and Compliance
    email_preference = models.BooleanField(default=True)
    sms_preference = models.BooleanField(default=True)
    call_preference = models.BooleanField(default=True)
    unsubscribed_date = models.DateTimeField(null=True, blank=True)
    unsubscribe_reason = models.CharField(max_length=255, blank=True)
    
    # Custom Data
    custom_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['campaign', '-added_date']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'content_type', 'object_id'],
                name='unique_campaign_member'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'status']),
            models.Index(fields=['tenant', 'member_type']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'converted']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.name or self.email}'
    
    @property
    def email_open_rate(self):
        """Calculate email open rate for this member"""
        if self.emails_sent > 0:
            return (self.emails_opened / self.emails_sent) * 100
        return Decimal('0.00')
    
    @property
    def email_click_rate(self):
        """Calculate email click rate for this member"""
        if self.emails_opened > 0:
            return (self.emails_clicked / self.emails_opened) * 100
        return Decimal('0.00')
    
    def update_engagement_score(self):
        """Calculate and update engagement score"""
        score = 0
        
        # Email engagement
        if self.emails_sent > 0:
            score += (self.emails_opened / self.emails_sent) * 30
            score += (self.emails_clicked / self.emails_sent) * 50
        
        # SMS engagement
        if self.sms_sent > 0:
            score += (self.sms_delivered / self.sms_sent) * 20
        
        # Call engagement
        if self.calls_made > 0:
            score += (self.calls_answered / self.calls_made) * 40
        
        # Conversion bonus
        if self.converted:
            score += 100
        
        self.engagement_score = min(int(score), 1000)  # Cap at 1000
        self.save(update_fields=['engagement_score'])


class CampaignEmail(TenantBaseModel, SoftDeleteMixin):
    """Email communications sent as part of campaigns"""
    
    EMAIL_TYPES = [
        ('INVITATION', 'Invitation'),
        ('ANNOUNCEMENT', 'Announcement'),
        ('NEWSLETTER', 'Newsletter'),
        ('PROMOTIONAL', 'Promotional'),
        ('FOLLOW_UP', 'Follow-up'),
        ('REMINDER', 'Reminder'),
        ('WELCOME', 'Welcome'),
        ('THANK_YOU', 'Thank You'),
        ('SURVEY', 'Survey'),
        ('ABANDONED_CART', 'Abandoned Cart'),
        ('NURTURE', 'Lead Nurture'),
        ('REACTIVATION', 'Reactivation'),
    ]
    
    EMAIL_STATUS = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('OPENED', 'Opened'),
        ('CLICKED', 'Clicked'),
        ('BOUNCED', 'Bounced'),
        ('COMPLAINED', 'Spam Complaint'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('FAILED', 'Failed'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='emails'
    )
    member = models.ForeignKey(
        CampaignMember,
        on_delete=models.CASCADE,
        related_name='emails'
    )
    
    # Email Content
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPES)
    subject = models.CharField(max_length=255)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Sender Information
    from_name = models.CharField(max_length=100)
    from_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True)
    
    # Recipient Information
    to_email = models.EmailField()
    to_name = models.CharField(max_length=100, blank=True)
    
    # Status and Tracking
    status = models.CharField(max_length=15, choices=EMAIL_STATUS, default='DRAFT')
    scheduled_time = models.DateTimeField(null=True, blank=True)
    sent_time = models.DateTimeField(null=True, blank=True)
    delivered_time = models.DateTimeField(null=True, blank=True)
    opened_time = models.DateTimeField(null=True, blank=True)
    clicked_time = models.DateTimeField(null=True, blank=True)
    
    # Engagement Metrics
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    last_opened = models.DateTimeField(null=True, blank=True)
    last_clicked = models.DateTimeField(null=True, blank=True)
    
    # Technical Details
    message_id = models.CharField(max_length=255, blank=True)
    esp_message_id = models.CharField(max_length=255, blank=True)  # Email Service Provider ID
    bounce_reason = models.TextField(blank=True)
    complaint_reason = models.TextField(blank=True)
    
    # A/B Testing
    variant = models.CharField(max_length=50, blank=True)
    test_group = models.CharField(max_length=50, blank=True)
    
    # Personalization Data
    personalization_data = models.JSONField(default=dict, blank=True)
    
    # Analytics
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    clicked_links = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-sent_time', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'status']),
            models.Index(fields=['tenant', 'member']),
            models.Index(fields=['tenant', 'to_email']),
            models.Index(fields=['tenant', 'sent_time']),
            models.Index(fields=['message_id']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.subject} to {self.to_email}'
    
    def mark_as_opened(self, ip_address=None, user_agent=None):
        """Mark email as opened"""
        now = timezone.now()
        
        if not self.opened_time:
            self.opened_time = now
            self.status = 'OPENED'
        
        self.open_count += 1
        self.last_opened = now
        
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent
        
        self.save()
        
        # Update member engagement
        self.member.emails_opened += 1
        self.member.last_engaged = now
        if not self.member.first_contacted:
            self.member.first_contacted = now
        self.member.save()
        
        # Update campaign metrics
        self.campaign.email_opens += 1
        self.campaign.save()
    
    def mark_as_clicked(self, clicked_url, ip_address=None, user_agent=None):
        """Mark email as clicked"""
        now = timezone.now()
        
        if not self.clicked_time:
            self.clicked_time = now
            self.status = 'CLICKED'
        
        self.click_count += 1
        self.last_clicked = now
        
        # Track clicked links
        if not isinstance(self.clicked_links, list):
            self.clicked_links = []
        
        self.clicked_links.append({
            'url': clicked_url,
            'timestamp': now.isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent
        })
        
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent
        
        self.save()
        
        # Update member engagement
        self.member.emails_clicked += 1
        self.member.last_engaged = now
        self.member.save()
        
        # Update campaign metrics
        self.campaign.email_clicks += 1
        self.campaign.clicks += 1
        self.campaign.save()
    
    def mark_as_bounced(self, bounce_reason=''):
        """Mark email as bounced"""
        self.status = 'BOUNCED'
        self.bounce_reason = bounce_reason
        self.save()
        
        # Update member metrics
        self.member.emails_bounced += 1
        self.member.save()
        
        # Update campaign metrics
        self.campaign.email_bounces += 1
        self.campaign.save()
    
    def mark_as_unsubscribed(self, reason=''):
        """Mark email as resulting in unsubscribe"""
        self.status = 'UNSUBSCRIBED'
        self.save()
        
        # Update member status
        self.member.status = 'UNSUBSCRIBED'
        self.member.unsubscribed_date = timezone.now()
        self.member.unsubscribe_reason = reason
        self.member.email_preference = False
        self.member.save()
        
        # Update campaign metrics
        self.campaign.email_unsubscribes += 1
        self.campaign.save()


class CampaignAsset(TenantBaseModel, SoftDeleteMixin):
    """Campaign creative assets and resources"""
    
    ASSET_TYPES = [
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
        ('DOCUMENT', 'Document'),
        ('TEMPLATE', 'Template'),
        ('BANNER', 'Banner'),
        ('LOGO', 'Logo'),
        ('BROCHURE', 'Brochure'),
        ('LANDING_PAGE', 'Landing Page'),
        ('EMAIL_TEMPLATE', 'Email Template'),
        ('SOCIAL_POST', 'Social Media Post'),
        ('AD_CREATIVE', 'Ad Creative'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    
    # Asset Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    
    # File Information
    file_url = models.URLField(blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    file_format = models.CharField(max_length=20, blank=True)
    dimensions = models.CharField(max_length=50, blank=True)  # e.g., "1920x1080"
    
    # Usage Tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Approval Status
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_assets'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Version Control
    version = models.CharField(max_length=20, default='1.0')
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versions'
    )
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['campaign', 'asset_type', 'name']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'asset_type']),
            models.Index(fields=['tenant', 'approved']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.name}'


class CampaignNote(TenantBaseModel):
    """Campaign notes and comments"""
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='campaign_notes'
    )
    
    # Note Content
    subject = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    note_type = models.CharField(
        max_length=20,
        choices=[
            ('GENERAL', 'General Note'),
            ('MEETING', 'Meeting Notes'),
            ('DECISION', 'Decision'),
            ('ISSUE', 'Issue/Problem'),
            ('IDEA', 'Idea/Suggestion'),
            ('MILESTONE', 'Milestone'),
            ('APPROVAL', 'Approval Note'),
        ],
        default='GENERAL'
    )
    
    # Visibility
    is_private = models.BooleanField(default=False)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'campaign']),
            models.Index(fields=['tenant', 'author']),
            models.Index(fields=['tenant', 'note_type']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.subject or "Note"}'


class CampaignSegment(TenantBaseModel, SoftDeleteMixin):
    """Campaign audience segments for targeted marketing"""
    
    SEGMENT_TYPES = [
        ('DEMOGRAPHIC', 'Demographic'),
        ('GEOGRAPHIC', 'Geographic'),
        ('BEHAVIORAL', 'Behavioral'),
        ('PSYCHOGRAPHIC', 'Psychographic'),
        ('TECHNOGRAPHIC', 'Technographic'),
        ('CUSTOM', 'Custom Criteria'),
        ('LOOKALIKE', 'Lookalike Audience'),
        ('RETARGETING', 'Retargeting'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='segments'
    )
    
    # Segment Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPES)
    
    # Criteria Definition
    criteria = models.JSONField(default=dict)
    filters = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    
    # Size and Performance
    estimated_size = models.IntegerField(default=0)
    actual_size = models.IntegerField(default=0)
    active_members = models.IntegerField(default=0)
    
    # Performance Metrics
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    engagement_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    cost_per_conversion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_update = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['campaign', 'name']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'is_active']),
            models.Index(fields=['tenant', 'segment_type']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.name}'
    
    def calculate_metrics(self):
        """Calculate segment performance metrics"""
        members = self.campaign.members.filter(segment=self.name)
        
        self.actual_size = members.count()
        self.active_members = members.filter(status__in=['TARGETED', 'CONTACTED', 'ENGAGED']).count()
        
        if self.actual_size > 0:
            conversions = members.filter(converted=True).count()
            self.conversion_rate = (conversions / self.actual_size) * 100
            
            engaged = members.filter(engagement_score__gt=0).count()
            self.engagement_rate = (engaged / self.actual_size) * 100
        
        self.save()


class CampaignEvent(TenantBaseModel):
    """Campaign timeline events and milestones"""
    
    EVENT_TYPES = [
        ('CREATED', 'Campaign Created'),
        ('LAUNCHED', 'Campaign Launched'),
        ('PAUSED', 'Campaign Paused'),
        ('RESUMED', 'Campaign Resumed'),
        ('COMPLETED', 'Campaign Completed'),
        ('CANCELLED', 'Campaign Cancelled'),
        ('MILESTONE', 'Milestone Reached'),
        ('EMAIL_SENT', 'Email Sent'),
        ('SMS_SENT', 'SMS Sent'),
        ('AD_LAUNCHED', 'Ad Launched'),
        ('BUDGET_UPDATED', 'Budget Updated'),
        ('CONTENT_UPDATED', 'Content Updated'),
        ('APPROVAL_REQUESTED', 'Approval Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('MEETING', 'Campaign Meeting'),
        ('REVIEW', 'Campaign Review'),
        ('REPORT_GENERATED', 'Report Generated'),
        ('INTEGRATION_SYNC', 'Integration Sync'),
        ('ERROR', 'Error Occurred'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='events'
    )
    
    # Event Information
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_datetime = models.DateTimeField(auto_now_add=True)
    
    # User Context
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_campaign_events'
    )
    
    # Event Data
    event_data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Impact Metrics
    affected_members = models.IntegerField(default=0)
    budget_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Status
    severity = models.CharField(
        max_length=10,
        choices=[
            ('INFO', 'Information'),
            ('WARNING', 'Warning'),
            ('ERROR', 'Error'),
            ('CRITICAL', 'Critical'),
        ],
        default='INFO'
    )
    
    class Meta:
        ordering = ['-event_datetime']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'event_type']),
            models.Index(fields=['tenant', 'event_datetime']),
            models.Index(fields=['tenant', 'severity']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.title}'


class CampaignIntegration(TenantBaseModel, SoftDeleteMixin):
    """Campaign integrations with external platforms"""
    
    INTEGRATION_TYPES = [
        ('EMAIL_SERVICE', 'Email Service Provider'),
        ('SMS_SERVICE', 'SMS Service Provider'),
        ('SOCIAL_MEDIA', 'Social Media Platform'),
        ('ADVERTISING', 'Advertising Platform'),
        ('ANALYTICS', 'Analytics Platform'),
        ('CRM', 'External CRM'),
        ('MARKETING_AUTOMATION', 'Marketing Automation'),
        ('WEBINAR', 'Webinar Platform'),
        ('SURVEY', 'Survey Platform'),
        ('LANDING_PAGE', 'Landing Page Builder'),
        ('PAYMENT', 'Payment Processor'),
        ('ECOMMERCE', 'E-commerce Platform'),
    ]
    
    INTEGRATION_STATUS = [
        ('INACTIVE', 'Inactive'),
        ('ACTIVE', 'Active'),
        ('ERROR', 'Error'),
        ('SYNCING', 'Syncing'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    
    # Integration Details
    name = models.CharField(max_length=100)
    integration_type = models.CharField(max_length=25, choices=INTEGRATION_TYPES)
    platform_name = models.CharField(max_length=100)
    status = models.CharField(max_length=15, choices=INTEGRATION_STATUS, default='INACTIVE')
    
    # Configuration
    configuration = models.JSONField(default=dict)
    api_credentials = models.JSONField(default=dict)  # Encrypted in production
    webhook_url = models.URLField(blank=True)
    
    # External References
    external_campaign_id = models.CharField(max_length=255, blank=True)
    external_account_id = models.CharField(max_length=255, blank=True)
    
    # Sync Settings
    auto_sync = models.BooleanField(default=True)
    sync_frequency_minutes = models.IntegerField(default=60)
    last_sync = models.DateTimeField(null=True, blank=True)
    next_sync = models.DateTimeField(null=True, blank=True)
    
    # Performance Metrics
    total_syncs = models.IntegerField(default=0)
    successful_syncs = models.IntegerField(default=0)
    failed_syncs = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    # Data Mapping
    field_mappings = models.JSONField(default=dict, blank=True)
    data_filters = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['campaign', 'platform_name']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'platform_name', 'integration_type'],
                name='unique_campaign_platform_integration'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'status']),
            models.Index(fields=['tenant', 'integration_type']),
            models.Index(fields=['tenant', 'last_sync']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.platform_name}'
    
    def sync_data(self):
        """Trigger data synchronization"""
        # Implementation would depend on the specific platform
        pass
    
    def update_sync_status(self, success=True, error_message=None):
        """Update sync status and metrics"""
        self.total_syncs += 1
        self.last_sync = timezone.now()
        
        if success:
            self.successful_syncs += 1
            self.status = 'ACTIVE'
            self.last_error = ''
        else:
            self.failed_syncs += 1
            self.status = 'ERROR'
            if error_message:
                self.last_error = error_message
        
        # Calculate next sync time
        if self.auto_sync:
            self.next_sync = timezone.now() + timezone.timedelta(minutes=self.sync_frequency_minutes)
        
        self.save()


class CampaignReport(TenantBaseModel):
    """Campaign performance reports"""
    
    REPORT_TYPES = [
        ('PERFORMANCE', 'Performance Report'),
        ('ENGAGEMENT', 'Engagement Report'),
        ('CONVERSION', 'Conversion Report'),
        ('ROI', 'ROI Report'),
        ('AUDIENCE', 'Audience Report'),
        ('CHANNEL', 'Channel Performance'),
        ('COMPARATIVE', 'Comparative Analysis'),
        ('EXECUTIVE', 'Executive Summary'),
        ('DETAILED', 'Detailed Analytics'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    REPORT_FORMATS = [
        ('PDF', 'PDF Document'),
        ('EXCEL', 'Excel Spreadsheet'),
        ('CSV', 'CSV File'),
        ('JSON', 'JSON Data'),
        ('HTML', 'HTML Report'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    
    # Report Information
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Generation Details
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_campaign_reports'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # Report Period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Report Configuration
    metrics_included = models.JSONField(default=list)
    filters_applied = models.JSONField(default=dict, blank=True)
    grouping_criteria = models.JSONField(default=list, blank=True)
    
    # Report Data
    report_data = models.JSONField(default=dict)
    summary_metrics = models.JSONField(default=dict, blank=True)
    
    # File Output
    format = models.CharField(max_length=10, choices=REPORT_FORMATS, default='PDF')
    file_url = models.URLField(blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        related_name='shared_campaign_reports',
        blank=True
    )
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
        ],
        blank=True
    )
    next_generation = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'report_type']),
            models.Index(fields=['tenant', 'generated_by']),
            models.Index(fields=['tenant', 'period_start', 'period_end']),
        ]
        
    def __str__(self):
        return f'{self.campaign.name} - {self.name}'
    
    def generate_report_data(self):
        """Generate comprehensive report data"""
        # This method would compile all relevant campaign metrics
        # and generate the report data structure
        pass