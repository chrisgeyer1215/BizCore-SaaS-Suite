# ============================================================================
# backend/apps/crm/models/territory.py - Territory & Team Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()
class Territory(TenantBaseModel, SoftDeleteMixin):
    """Enhanced territory management with geographic and account-based territories"""
    
    TERRITORY_TYPES = [
        ('GEOGRAPHIC', 'Geographic'),
        ('ACCOUNT_BASED', 'Account Based'),
        ('PRODUCT_BASED', 'Product Based'),
        ('INDUSTRY_BASED', 'Industry Based'),
        ('HYBRID', 'Hybrid'),
    ]
    
    # Territory Information
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    territory_type = models.CharField(max_length=20, choices=TERRITORY_TYPES, default='GEOGRAPHIC')
    
    # Hierarchy
    parent_territory = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_territories'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Geographic Configuration
    countries = models.JSONField(default=list)
    states_provinces = models.JSONField(default=list)
    cities = models.JSONField(default=list)
    postal_codes = models.JSONField(default=list)
    geographic_bounds = models.JSONField(default=dict)  # Lat/Lng boundaries
    
    # Account-Based Configuration
    account_criteria = models.JSONField(default=dict)
    revenue_range = models.JSONField(default=dict)
    employee_count_range = models.JSONField(default=dict)
    industries = models.ManyToManyField(
        Industry,
        blank=True,
        related_name='territories'
    )
    
    # Product Configuration
    product_lines = models.JSONField(default=list)
    
    # Assignment Rules
    auto_assignment_enabled = models.BooleanField(default=True)
    assignment_priority = models.IntegerField(default=10)
    
    # Performance Targets
    revenue_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    lead_target = models.IntegerField(null=True, blank=True)
    opportunity_target = models.IntegerField(null=True, blank=True)
    
    # Performance Metrics (Auto-calculated)
    total_accounts = models.IntegerField(default=0)
    total_leads = models.IntegerField(default=0)
    total_opportunities = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['level', 'name']
        verbose_name_plural = 'Territories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_territory_code',
                condition=models.Q(code__isnull=False)
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'territory_type', 'is_active']),
            models.Index(fields=['tenant', 'parent_territory']),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_territory_code()
        
        # Auto-calculate level based on parent
        if self.parent_territory:
            self.level = self.parent_territory.level + 1
        else:
            self.level = 0
        
        super().save(*args, **kwargs)
    
    def generate_territory_code(self):
        """Generate unique territory code"""
        return generate_code('TERR', self.tenant_id)
    
    def get_assigned_users(self):
        """Get all users assigned to this territory"""
        return User.objects.filter(
            crm_profile__territory=self,
            crm_profile__is_active=True
        )
    
    def update_performance_metrics(self):
        """Update territory performance metrics"""
        # This would be called by signals or scheduled tasks
        self.total_accounts = self.accounts.filter(is_active=True).count()
        self.total_leads = self.leads.filter(is_active=True).count()
        self.total_opportunities = self.opportunities.filter(is_active=True).count()
        
        # Calculate total revenue from won opportunities
        won_revenue = self.opportunities.filter(
            is_won=True,
            is_active=True
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.total_revenue = won_revenue
        self.save(update_fields=[
            'total_accounts',
            'total_leads', 
            'total_opportunities',
            'total_revenue'
        ])
    
    @property
    def revenue_achievement_percentage(self):
        """Calculate revenue achievement against target"""
        if self.revenue_target and self.revenue_target > 0:
            return (self.total_revenue / self.revenue_target) * 100
        return 0


class Team(TenantBaseModel, SoftDeleteMixin):
    """Enhanced team management with hierarchy and permissions"""
    
    TEAM_TYPES = [
        ('SALES', 'Sales Team'),
        ('MARKETING', 'Marketing Team'),
        ('SUPPORT', 'Support Team'),
        ('MANAGEMENT', 'Management Team'),
        ('PRODUCT', 'Product Team'),
        ('CUSTOM', 'Custom Team'),
    ]
    
    # Team Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    team_type = models.CharField(max_length=20, choices=TEAM_TYPES, default='SALES')
    
    # Hierarchy
    parent_team = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name    def resolve(self, user, resolution):
        """Resolve ticket"""
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution = resolution
        self.updated_by = user
        
        # Calculate resolution time
        resolution_time = self.resolved_at - self.created_at
        self.resolution_time_minutes = int(resolution_time.total_seconds() / 60)
        
        self.save()
    
    @property
    def is_overdue(self):
        """Check if ticket is overdue"""
        if self.due_date and self.status not in ['RESOLVED', 'CLOSED']:
            return timezone.now() > self.due_date
        return False
    
    @property
    def time_to_resolution(self):
        """Get time to resolution in human readable format"""
        if self.resolution_time_minutes:
            hours, minutes = divmod(self.resolution_time_minutes, 60)
            days, hours = divmod(hours, 24)
            if days > 0:
                return f'{days}d {hours}h {minutes}m'
            elif hours > 0:
                return f'{hours}h {minutes}m'
            else:
                return f'{minutes}m'
        return None


class TicketComment(TenantBaseModel):
    """Enhanced ticket comments with rich formatting"""
    
    COMMENT_TYPES = [
        ('PUBLIC', 'Public Comment'),
        ('INTERNAL', 'Internal Note'),
        ('SYSTEM', 'System Generated'),
        ('EMAIL', 'Email Reply'),
    ]
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    # Comment Content
    comment_type = models.CharField(max_length=15, choices=COMMENT_TYPES, default='PUBLIC')
    content = models.TextField()
    is_html = models.BooleanField(default=False)
    
    # Author Information
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_comments'
    )
    author_name = models.CharField(max_length=100, blank=True)  # For external authors
    author_email = models.EmailField(blank=True)  # For external authors
    
    # Email Integration
    email_message_id = models.CharField(max_length=255, blank=True)
    in_reply_to = models.CharField(max_length=255, blank=True)
    
    # Visibility & Access
    is_public = models.BooleanField(default=True)
    is_customer_visible = models.BooleanField(default=True)
    
    # Attachments
    attachments = models.JSONField(default=list)
    
    # Time Tracking
    time_spent_minutes = models.IntegerField(null=True, blank=True)
    billable_time = models.BooleanField(default=False)
    
    # Status Changes
    status_change_from = models.CharField(max_length=15, blank=True)
    status_change_to = models.CharField(max_length=15, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['tenant', 'ticket', 'comment_type']),
            models.Index(fields=['tenant', 'author']),
            models.Index(fields=['tenant', 'created_at']),
        ]
        
    def __str__(self):
        author = self.author.get_full_name() if self.author else self.author_name
        return f'Comment by {author} on {self.ticket.ticket_number}'
    
    def save(self, *args, **kwargs):
        # Set author name for display
        if self.author and not self.author_name:
            self.author_name = self.author.get_full_name()
        
        super().save(*args, **kwargs)
        
        # Update ticket's last activity
        self.ticket.updated_at = self.created_at
        self.ticket.save(update_fields=['updated_at'])


class KnowledgeBase(TenantBaseModel, SoftDeleteMixin):
    """Enhanced knowledge base for customer self-service"""
    
    CONTENT_TYPES = [
        ('ARTICLE', 'Article'),
        ('FAQ', 'FAQ'),
        ('HOW_TO', 'How-to Guide'),
        ('TROUBLESHOOTING', 'Troubleshooting'),
        ('VIDEO', 'Video Tutorial'),
        ('DOCUMENT', 'Document'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'Under Review'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Content Information
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES, default='ARTICLE')
    
    # Categorization
    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_articles'
    )
    tags = models.JSONField(default=list)
    
    # Status & Publishing
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    published_date = models.DateTimeField(null=True, blank=True)
    
    # Authoring
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_kb_articles'
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_kb_articles'
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    
    # SEO & Search
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    search_keywords = models.JSONField(default=list)
    
    # Usage Analytics
    view_count = models.IntegerField(default=0)
    helpful_votes = models.IntegerField(default=0)
    unhelpful_votes = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    # Related Content
    related_articles = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False
    )
    related_tickets = models.ManyToManyField(
        Ticket,
        blank=True,
        related_name='related_kb_articles'
    )
    
    # External Links
    external_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    customer_visible = models.BooleanField(default=True)
    internal_only = models.BooleanField(default=False)
    
    # Maintenance
    last_reviewed = models.DateTimeField(null=True, blank=True)
    review_required = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Knowledge Base Article'
        verbose_name_plural = 'Knowledge Base Articles'
        indexes = [
            models.Index(fields=['tenant', 'status', 'content_type']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'published_date']),
            models.Index(fields=['tenant', 'view_count']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'slug'],
                name='unique_tenant_kb_slug',
                condition=models.Q(slug__isnull=False)
            ),
        ]
        
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        
        # Set published date when status changes to published
        if self.status == 'PUBLISHED' and not self.published_date:
            self.published_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def helpfulness_ratio(self):
        """Calculate helpfulness ratio"""
        total_votes = self.helpful_votes + self.unhelpful_votes
        if total_votes > 0:
            return (self.helpful_votes / total_votes) * 100
        return 0
    
    def mark_as_viewed(self):
        """Increment view count"""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=['view_count', 'last_viewed'])