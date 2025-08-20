# ============================================================================
# backend/apps/crm/models/opportunity.py - Opportunity Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class Pipeline(TenantBaseModel, SoftDeleteMixin):
    """Enhanced sales pipeline management"""
    
    PIPELINE_TYPES = [
        ('SALES', 'Sales Pipeline'),
        ('MARKETING', 'Marketing Pipeline'),
        ('SUPPORT', 'Support Pipeline'),
        ('CUSTOM', 'Custom Pipeline'),
    ]
    
    # Pipeline Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    pipeline_type = models.CharField(max_length=20, choices=PIPELINE_TYPES, default='SALES')
    
    # Settings
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Performance Metrics
    total_opportunities = models.IntegerField(default=0)
    total_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_deal_size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_sales_cycle = models.IntegerField(default=0)  # in days
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Owner
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_pipelines'
    )
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'is_default'],
                name='unique_default_pipeline',
                condition=models.Q(is_default=True)
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one default pipeline
        if self.is_default:
            Pipeline.objects.filter(
                tenant=self.tenant,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PipelineStage(TenantBaseModel, SoftDeleteMixin):
    """Enhanced pipeline stages with probability and actions"""
    
    STAGE_TYPES = [
        ('OPEN', 'Open'),
        ('WON', 'Won'),
        ('LOST', 'Lost'),
    ]
    
    # Stage Information
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='stages'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    stage_type = models.CharField(max_length=10, choices=STAGE_TYPES, default='OPEN')
    
    # Stage Configuration
    sort_order = models.IntegerField(default=0)
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Stage Behavior
    is_closed = models.BooleanField(default=False)
    is_won = models.BooleanField(default=False)
    
    # Required Actions
    required_fields = models.JSONField(default=list)
    required_activities = models.JSONField(default=list)
    
    # Automation
    auto_actions = models.JSONField(default=list)
    
    # Performance Metrics
    total_opportunities = models.IntegerField(default=0)
    average_time_in_stage = models.IntegerField(default=0)  # in days
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        ordering = ['pipeline', 'sort_order']
        constraints = [
            models.UniqueConstraint(
                fields=['pipeline', 'name'],
                name='unique_stage_per_pipeline'
            ),
        ]
        
    def __str__(self):
        return f'{self.pipeline.name} - {self.name}'


class Opportunity(TenantBaseModel, SoftDeleteMixin):
    """Enhanced opportunity management with forecasting and collaboration"""
    
    OPPORTUNITY_TYPES = [
        ('NEW_BUSINESS', 'New Business'),
        ('EXISTING_BUSINESS', 'Existing Business'),
        ('RENEWAL', 'Renewal'),
        ('UPSELL', 'Upsell'),
        ('CROSS_SELL', 'Cross Sell'),
    ]
    
    LEAD_SOURCES = [
        ('WEBSITE', 'Website'),
        ('REFERRAL', 'Referral'),
        ('MARKETING', 'Marketing Campaign'),
        ('COLD_CALL', 'Cold Call'),
        ('TRADE_SHOW', 'Trade Show'),
        ('PARTNER', 'Partner'),
        ('OTHER', 'Other'),
    ]
    
    # Opportunity Identification
    opportunity_number = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    opportunity_type = models.CharField(
        max_length=20,
        choices=OPPORTUNITY_TYPES,
        default='NEW_BUSINESS'
    )
    
    # Account & Contact Association
    account = models.ForeignKey(
        'Account',
        on_delete=models.CASCADE,
        related_name='opportunities'
    )
    primary_contact = models.ForeignKey(
        'Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opportunities'
    )
    
    # Pipeline & Stage
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.PROTECT,
        related_name='opportunities'
    )
    stage = models.ForeignKey(
        PipelineStage,
        on_delete=models.PROTECT,
        related_name='opportunities'
    )
    
    # Financial Information
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    expected_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Dates
    close_date = models.DateField()
    created_date = models.DateField(auto_now_add=True)
    stage_changed_date = models.DateTimeField(null=True, blank=True)
    
    # Ownership & Assignment
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_opportunities'
    )
    team_members = models.ManyToManyField(
        User,
        through='OpportunityTeamMember',
        related_name='team_opportunities',
        blank=True
    )
    
    # Source & Campaign
    lead_source = models.CharField(max_length=50, choices=LEAD_SOURCES, blank=True)
    campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opportunities'
    )
    original_lead = models.ForeignKey(
        'Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_opportunities'
    )
    
    # Competition & Analysis
    competitors = models.JSONField(default=list)
    competitive_analysis = models.TextField(blank=True)
    
    # Status Tracking
    is_closed = models.BooleanField(default=False)
    is_won = models.BooleanField(default=False)
    closed_date = models.DateTimeField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    
    # Sales Cycle Analysis
    days_in_pipeline = models.IntegerField(default=0)
    stage_history = models.JSONField(default=list)
    
    # Territory
    territory = models.ForeignKey(
        'Territory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opportunities'
    )
    
    # Next Steps & Planning
    next_step = models.CharField(max_length=255, blank=True)
    next_step_date = models.DateField(null=True, blank=True)
    
    # Integration with Finance Module
    finance_quote_id = models.IntegerField(null=True, blank=True)
    finance_invoice_id = models.IntegerField(null=True, blank=True)
    
    # Additional Information
    tags = models.JSONField(default=list)
    custom_fields = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Opportunities'
        indexes = [
            models.Index(fields=['tenant', 'account', 'stage']),
            models.Index(fields=['tenant', 'owner', 'is_closed']),
            models.Index(fields=['tenant', 'close_date']),
            models.Index(fields=['tenant', 'probability']),
            models.Index(fields=['tenant', 'amount']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'opportunity_number'],
                name='unique_tenant_opportunity_number',
                condition=models.Q(opportunity_number__isnull=False)
            ),
        ]
        
    def __str__(self):
        return f'{self.name} - {self.account.name}'
    
    def save(self, *args, **kwargs):
        if not self.opportunity_number:
            self.opportunity_number = self.generate_opportunity_number()
        
        # Calculate expected revenue
        self.expected_revenue = (self.amount * self.probability) / 100
        
        # Update stage change tracking
        if self.pk:
            old_opportunity = Opportunity.objects.get(pk=self.pk)
            if old_opportunity.stage != self.stage:
                self.stage_changed_date = timezone.now()
                self.update_stage_history(old_opportunity.stage, self.stage)
        
        # Calculate days in pipeline
        self.days_in_pipeline = (timezone.now().date() - self.created_date).days
        
        super().save(*args, **kwargs)
    
    def generate_opportunity_number(self):
        """Generate unique opportunity number"""
        return generate_code('OPP', self.tenant_id)
    
    def update_stage_history(self, old_stage, new_stage):
        """Update stage change history"""
        if not self.stage_history:
            self.stage_history = []
        
        self.stage_history.append({
            'from_stage': old_stage.name if old_stage else None,
            'to_stage': new_stage.name,
            'changed_date': timezone.now().isoformat(),
            'changed_by': self.updated_by.id if self.updated_by else None,
        })
    
    def close_as_won(self, user, close_date=None):
        """Close opportunity as won"""
        self.is_closed = True
        self.is_won = True
        self.closed_date = close_date or timezone.now()
        self.updated_by = user
        
        # Move to won stage
        won_stage = self.pipeline.stages.filter(is_won=True).first()
        if won_stage:
            self.stage = won_stage
            self.probability = won_stage.probability
        
        self.save()
    
    def close_as_lost(self, user, reason, close_date=None):
        """Close opportunity as lost"""
        self.is_closed = True
        self.is_won = False
        self.lost_reason = reason
        self.closed_date = close_date or timezone.now()
        self.updated_by = user
        
        # Move to lost stage
        lost_stage = self.pipeline.stages.filter(stage_type='LOST').first()
        if lost_stage:
            self.stage = lost_stage
            self.probability = lost_stage.probability
        
        self.save()


class OpportunityTeamMember(TenantBaseModel):
    """Team members assigned to opportunities"""
    
    ROLE_TYPES = [
        ('OWNER', 'Owner'),
        ('COLLABORATOR', 'Collaborator'),
        ('TECHNICAL', 'Technical Contact'),
        ('SALES_SUPPORT', 'Sales Support'),
        ('MANAGER', 'Manager'),
    ]
    
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='opportunity_memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_TYPES, default='COLLABORATOR')
    
    # Permissions
    can_edit = models.BooleanField(default=False)
    can_view_financials = models.BooleanField(default=False)
    
    # Dates
    assigned_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['opportunity', 'user'],
                name='unique_opportunity_team_member'
            ),
        ]
        
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.opportunity.name} ({self.role})'


class OpportunityProduct(TenantBaseModel, SoftDeleteMixin):
    """Enhanced products/services associated with opportunities"""
    
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name='products'
    )
    
    # Product Information (linking to inventory module)
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, blank=True)
    product_id = models.IntegerField(null=True, blank=True)  # Reference to inventory module
    
    # Pricing & Quantity
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(0)]
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Product Details
    description = models.TextField(blank=True)
    product_category = models.CharField(max_length=100, blank=True)
    
    # Revenue Recognition
    revenue_type = models.CharField(
        max_length=20,
        choices=[
            ('ONE_TIME', 'One Time'),
            ('RECURRING', 'Recurring'),
            ('USAGE_BASED', 'Usage Based'),
        ],
        default='ONE_TIME'
    )
    recurring_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
        ],
        blank=True
    )
    
    # Delivery Information
    delivery_date = models.DateField(null=True, blank=True)
    service_start_date = models.DateField(null=True, blank=True)
    service_end_date = models.DateField(null=True, blank=True)
    
    # Line Item Position
    line_number = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['opportunity', 'line_number']
        verbose_name = 'Opportunity Product'
        verbose_name_plural = 'Opportunity Products'
        
    def __str__(self):
        return f'{self.product_name} - {self.opportunity.name}'
    
    def save(self, *args, **kwargs):
        # Calculate discount amount if percentage is provided
        if self.discount_percent > 0:
            gross_amount = self.quantity * self.unit_price
            self.discount_amount = gross_amount * (self.discount_percent / 100)
        
        # Calculate total price
        gross_amount = self.quantity * self.unit_price
        self.total_price = gross_amount - self.discount_amount
        
        super().save(*args, **kwargs)
    
    @property
    def net_unit_price(self):
        """Calculate net unit price after discount"""
        if self.quantity > 0:
            return self.total_price / self.quantity
        return self.unit_price