class WorkflowRule(TenantBaseModel, SoftDeleteMixin):
    """Enhanced workflow automation rules"""
    
    TRIGGER_TYPES = [
        ('CREATE', 'Record Created'),
        ('UPDATE', 'Record Updated'),
        ('DELETE', 'Record Deleted'),
        ('FIELD_CHANGE', 'Field Value Changed'),
        ('TIME_BASED', 'Time-based'),
        ('EMAIL_RECEIVED', 'Email Received'),
        ('WEB_FORM', 'Web Form Submitted'),
    ]
    
    ACTION_TYPES = [
        ('SEND_EMAIL', 'Send Email'),
        ('CREATE_TASK', 'Create Task'),
        ('UPDATE_FIELD', 'Update Field'),
        ('ASSIGN_RECORD', 'Assign Record'),
        ('CREATE_RECORD', 'Create Record'),
        ('SEND_SMS', 'Send SMS'),
        ('WEBHOOK', 'Call Webhook'),
        ('SCORE_UPDATE', 'Update Score'),
    ]
    
    # Rule Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Trigger Configuration
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    trigger_object = models.CharField(max_length=100)  # Model name
    trigger_conditions = models.JSONField(default=dict)
    
    # Action Configuration
    actions = models.JSONField(default=list)  # List of actions to execute
    
    # Execution Settings
    is_active = models.BooleanField(default=True)
    execution_order = models.IntegerField(default=10)
    
    # Time-based Settings
    schedule_type = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('DELAYED', 'Delayed'),
            ('SCHEDULED', 'Scheduled'),
            ('RECURRING', 'Recurring'),
        ],
        default='IMMEDIATE'
    )
    delay_minutes = models.IntegerField(null=True, blank=True)
    schedule_datetime = models.DateTimeField(null=True, blank=True)
    recurrence_pattern = models.JSONField(default=dict)
    
    # Performance Tracking
    execution_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    
    # Error Handling
    on_error_action = models.CharField(
        max_length=20,
        choices=[
            ('CONTINUE', 'Continue'),
            ('STOP', 'Stop Workflow'),
            ('RETRY', 'Retry'),
            ('NOTIFY', 'Notify Admin'),
        ],
        default='CONTINUE'
    )
    max_retries = models.IntegerField(default=3)
    
    class Meta:
        ordering = ['execution_order', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'trigger_type']),
            models.Index(fields=['tenant', 'trigger_object']),
        ]
        
    def __str__(self):
        return self.name
    
    def execute(self, trigger_data):
        """Execute the workflow rule"""
        from .services import WorkflowService
        
        service = WorkflowService(self.tenant)
        return service.execute_workflow_rule(self, trigger_data)


class WorkflowExecution(TenantBaseModel):
    """Enhanced workflow execution tracking"""
    
    EXECUTION_STATUS = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('RETRYING', 'Retrying'),
    ]
    
    workflow_rule = models.ForeignKey(
        WorkflowRule,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # Execution Details
    status = models.CharFielclass Campaign(TenantBaseModel, SoftDeleteMixin):
    """Enhanced marketing campaign management with ROI tracking"""
    
    CAMPAIGN_TYPES = [
        ('EMAIL', 'Email Campaign'),
        ('SOCIAL_MEDIA', 'Social Media'),
        ('WEBINAR', 'Webinar'),
        ('TRADE_SHOW', 'Trade Show'),
        ('CONTENT_MARKETING', 'Content Marketing'),
        ('PPC', 'Pay Per Click'),
        ('DIRECT_MAIL', 'Direct Mail'),
        ('TELEMARKETING', 'Telemarketing'),
        ('REFERRAL', 'Referral Program'),
        ('EVENT', 'Event'),
        ('OTHER', 'Other'),
    ]
    
    CAMPAIGN_STATUS = [
        ('PLANNING', 'Planning'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Campaign Information
    name = models.CharField(max_length=255)
    campaign_code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS, default='PLANNING')
    
    # Dates & Duration
    start_date = models.DateField()
    end_date = models.DateField()
    planned_duration_days = models.IntegerField(null=True, blank=True)
    
    # Target & Budget
    target_audience = models.TextField(blank=True)
    budget_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    budget_spent = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Goals & Metrics
    target_leads = models.IntegerField(null=True, blank=True)
    target_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    target_conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Ownership & Team
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_campaigns'
    )
    team_members = models.ManyToManyField(
        User,
        through='CampaignTeamMember',
        related_name='campaign_memberships',
        blank=True
    )
    
    # Performance Tracking
    total_leads = models.IntegerField(default=0)
    qualified_leads = models.IntegerField(default=0)
    converted_leads = models.IntegerField(default=0)
    total_opportunities = models.IntegerField(default=0)
    won_opportunities = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Email Campaign Metrics
    emails_sent = models.IntegerField(default=0)
    emails_delivered = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    emails_bounced = models.IntegerField(default=0)
    emails_unsubscribed = models.IntegerField(default=0)
    
    # Web & Digital Metrics
    website_visits = models.IntegerField(default=0)
    page_views = models.IntegerField(default=0)
    form_submissions = models.IntegerField(default=0)
    downloads = models.IntegerField(default=0)
    registrations = models.IntegerField(default=0)
    
    # Social Media Metrics
    social_impressions = models.IntegerField(default=0)
    social_clicks = models.IntegerField(default=0)
    social_shares = models.IntegerField(default=0)
    social_comments = models.IntegerField(default=0)
    
    # Content & Assets
    landing_page_url = models.URLField(blank=True)
    creative_assets = models.JSONField(default=list)
    
    # Integration & Tracking
    tracking_parameters = models.JSONField(default=dict)
    external_campaign_id = models.CharField(max_length=100, blank=True)
    
    # Tags & Categorization
    tags = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant', 'status', 'campaign_type']),
            models.Index(fields=['tenant', 'owner']),
            models.Index(fields=['tenant', 'start_date', 'end_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'campaign_code'],
                name='unique_tenant_campaign_code',
                condition=models.Q(campaign_code__isnull=False)
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.campaign_code:
            self.campaign_code = self.generate_campaign_code()
        
        # Calculate planned duration
        if self.start_date and self.end_date:
            self.planned_duration_days = (self.end_date - self.start_date).days
        
        super().save(*args, **kwargs)
    
    def generate_campaign_code(self):
        """Generate unique campaign code"""
        return generate_code('CAMP', self.tenant_id)
    
    @property
    def conversion_rate(self):
        """Calculate lead conversion rate"""
        if self.total_leads > 0:
            return (self.converted_leads / self.total_leads) * 100
        return 0
    
    @property
    def roi(self):
        """Calculate return on investment"""
        if self.budget_spent > 0:
            return ((self.total_revenue - self.budget_spent) / self.budget_spent) * 100
        return 0
    
    @property
    def cost_per_lead(self):
        """Calculate cost per lead"""
        if self.total_leads > 0:
            return self.budget_spent / self.total_leads
        return 0
    
    @property
    def email_open_rate(self):
        """Calculate email open rate"""
        if self.emails_delivered > 0:
            return (self.emails_opened / self.emails_delivered) * 100
        return 0
    
    @property
    def email_click_rate(self):
        """Calculate email click-through rate"""
        if self.emails_delivered > 0:
            return (self.emails_clicked / self.emails_delivered) * 100
        return 0


class CampaignTeamMember(TenantBaseModel):
    """Team members assigned to campaigns"""
    
    ROLE_TYPES = [
        ('MANAGER', 'Campaign Manager'),
        ('COORDINATOR', 'Coordinator'),
        ('DESIGNER', 'Designer'),
        ('COPYWRITER', 'Copywriter'),
        ('ANALYST', 'Analyst'),
        ('SPECIALIST', 'Specialist'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='campaign_team_memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_TYPES)
    
    # Permissions
    can_edit = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=True)
    can_manage_content = models.BooleanField(default=False)
    
    # Dates
    assigned_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'user'],
                name='unique_campaign_team_member'
            ),
        ]
        
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.campaign.name} ({self.role})'


class CampaignMember(TenantBaseModel):
    """Enhanced campaign member tracking with engagement metrics"""
    
    MEMBER_STATUS = [
        ('ACTIVE', 'Active'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('BOUNCED', 'Bounced'),
        ('OPTED_OUT', 'Opted Out'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    MEMBER_TYPES = [
        ('LEAD', 'Lead'),
        ('CONTACT', 'Contact'),
        ('CUSTOMER', 'Customer'),
        ('PROSPECT', 'Prospect'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Member Information
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=255, blank=True)
    
    # Member Classification
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPES, default='LEAD')
    status = models.CharField(max_length=20, choices=MEMBER_STATUS, default='ACTIVE')
    
    # CRM Entity References
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_memberships'
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_memberships'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_memberships'
    )
    
    # Engagement Tracking
    emails_sent = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    last_opened_date = models.DateTimeField(null=True, blank=True)
    last_clicked_date = models.DateTimeField(null=True, blank=True)
    
    # Response Tracking
    responded = models.BooleanField(default=False)
    response_date = models.DateTimeField(null=True, blank=True)
    conversion_date = models.DateTimeField(null=True, blank=True)
    
    # Opt-out Information
    unsubscribed_date = models.DateTimeField(null=True, blank=True)
    unsubscribe_reason = models.CharField(max_length=255, blank=True)
    
    # Additional Data
    custom_fields = models.JSONField(default=dict)
    tags = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'status']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'member_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'email'],
                name='unique_campaign_member_email'
            ),
        ]
        
    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip() or self.email
        return f'{name} - {self.campaign.name}'
    
    @property
    def full_name(self):
        """Get full name"""
        return f'{self.first_name} {self.last_name}'.strip() or 'No Name'
    
    @property
    def engagement_score(self):
        """Calculate engagement score"""
        score = 0
        if self.emails_opened > 0:
            score += min(self.emails_opened * 10, 50)  # Max 50 points for opens
        if self.emails_clicked > 0:
            score += min(self.emails_clicked * 20, 50)  # Max 50 points for clicks
        if self.responded:
            score += 30
        return min(score, 100)


class CampaignEmail(TenantBaseModel):
    """Enhanced campaign email tracking"""
    
    EMAIL_STATUS = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('PAUSED', 'Paused'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='emails'
    )
    
    # Email Content
    subject = models.CharField(max_length=255)
    from_name = models.CharField(max_length=100)
    from_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True)
    
    # Content
    html_content = models.TextField(blank=True)
    text_content = models.TextField(blank=True)
    
    # Template
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_emails'
    )
    
    # Scheduling
    status = models.CharField(max_length=15, choices=EMAIL_STATUS, default='DRAFT')
    scheduled_datetime = models.DateTimeField(null=True, blank=True)
    sent_datetime = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    bounced_count = models.IntegerField(default=0)
    unsubscribed_count = models.IntegerField(default=0)
    
    # A/B Testing
    is_ab_test = models.BooleanField(default=False)
    ab_test_percentage = models.IntegerField(null=True, blank=True)
    ab_test_winner = models.BooleanField(null=True, blank=True)
    
    # Provider Information
    provider = models.CharField(max_length=50, blank=True)
    provider_campaign_id = models.CharField(max_length=255, blank=True)
    
    # Analytics
    analytics_data = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'campaign', 'status']),
            models.Index(fields=['tenant', 'scheduled_datetime']),
        ]
        
    def __str__(self):
        return f'{self.subject} - {self.campaign.name}'
    
    @property
    def delivery_rate(self):
        """Calculate delivery rate"""
        if self.sent_count > 0:
            return (self.delivered_count / self.sent_count) * 100
        return 0
    
    @property
    def open_rate(self):
        """Calculate open rate"""
        if self.delivered_count > 0:
            return (self.opened_count / self.delivered_count) * 100
        return 0
    
    @property
    def click_rate(self):
        """Calculate click-through rate"""
        if self.delivered_count > 0:
            return (self.clicked_count / self.delivered_count) * 100
        return 0
    
    @property
    def bounce_rate(self):
        """Calculate bounce rate"""
        if self.sent_count > 0:
            return (self.bounced_count / self.sent_count) * 100
        return 0