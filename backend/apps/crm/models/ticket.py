# ============================================================================
# backend/apps/crm/models/ticket.py - Ticket Management Models  
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class TicketCategory(TenantBaseModel, SoftDeleteMixin):
    """Ticket category management"""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    icon = models.CharField(max_length=50, blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Ticket Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_ticket_category'
            ),
        ]
        
    def __str__(self):
        return self.name


class SLA(TenantBaseModel, SoftDeleteMixin):
    """Service Level Agreement management"""
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Response times (in minutes)
    first_response_time = models.IntegerField()  # Minutes to first response
    resolution_time = models.IntegerField()     # Minutes to resolution
    
    # Escalation
    escalation_enabled = models.BooleanField(default=True)
    escalation_time = models.IntegerField(null=True, blank=True)  # Minutes before escalation
    
    # Business hours
    business_hours_only = models.BooleanField(default=True)
    business_start_hour = models.IntegerField(default=9)
    business_end_hour = models.IntegerField(default=17)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['priority', 'name']
        verbose_name = 'SLA'
        verbose_name_plural = 'SLAs'
        
    def __str__(self):
        return f"{self.name} ({self.get_priority_display()})"


class Ticket(TenantBaseModel, SoftDeleteMixin):
    """Support ticket management"""
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING', 'Pending Customer'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Basic Information
    ticket_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Categorization
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_tickets')
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    
    # SLA
    sla = models.ForeignKey(SLA, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    first_response_due = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    opened_at = models.DateTimeField(auto_now_add=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Related objects (generic foreign key)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'assigned_to']),
            models.Index(fields=['tenant', 'priority']),
            models.Index(fields=['ticket_number']),
        ]
        
    def __str__(self):
        return f"{self.ticket_number}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Auto-generate ticket number
            from datetime import datetime
            today = datetime.now().strftime('%Y%m%d')
            
            last_ticket = Ticket.objects.filter(
                tenant=self.tenant,
                ticket_number__startswith=f'TK-{today}'
            ).order_by('-ticket_number').first()
            
            if last_ticket:
                try:
                    last_seq = int(last_ticket.ticket_number.split('-')[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = 1
            else:
                next_seq = 1
            
            self.ticket_number = f"TK-{today}-{next_seq:04d}"
        
        super().save(*args, **kwargs)


class TicketComment(TenantBaseModel):
    """Ticket comment/response tracking"""
    
    COMMENT_TYPES = [
        ('COMMENT', 'Comment'),
        ('INTERNAL_NOTE', 'Internal Note'),
        ('STATUS_CHANGE', 'Status Change'),
        ('ASSIGNMENT', 'Assignment Change'),
        ('RESOLUTION', 'Resolution'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    comment_type = models.CharField(max_length=15, choices=COMMENT_TYPES, default='COMMENT')
    content = models.TextField()
    
    # Author
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Visibility
    is_internal = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    
    # Metadata
    time_spent = models.DurationField(null=True, blank=True)  # Time spent on this update
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['author']),
        ]
        
    def __str__(self):
        return f"Comment on {self.ticket.ticket_number} by {self.author}"


class KnowledgeBase(TenantBaseModel, SoftDeleteMixin):
    """Knowledge base articles for self-service"""
    
    ARTICLE_TYPES = [
        ('FAQ', 'FAQ'),
        ('HOWTO', 'How-to Guide'),
        ('TROUBLESHOOTING', 'Troubleshooting'),
        ('POLICY', 'Policy'),
        ('FEATURE', 'Feature Guide'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'Under Review'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Content
    title = models.CharField(max_length=255)
    content = models.TextField()
    summary = models.TextField(blank=True)
    
    # Categorization
    article_type = models.CharField(max_length=20, choices=ARTICLE_TYPES, default='FAQ')
    categories = models.ManyToManyField(TicketCategory, blank=True, related_name='kb_articles')
    tags = models.JSONField(default=list, blank=True)
    
    # Publishing
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Author and review
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='authored_articles')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_articles')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    view_count = models.PositiveIntegerField(default=0)
    helpful_votes = models.PositiveIntegerField(default=0)
    unhelpful_votes = models.PositiveIntegerField(default=0)
    
    # SEO
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['article_type']),
            models.Index(fields=['published_at']),
        ]
        
    def __str__(self):
        return self.title
    
    def publish(self, user=None):
        """Publish the article"""
        self.status = 'PUBLISHED'
        self.published_at = timezone.now()
        if user:
            self.reviewed_by = user
            self.reviewed_at = timezone.now()
        self.save()
    
    def archive(self):
        """Archive the article"""
        self.status = 'ARCHIVED'
        self.save()
    
    @property
    def helpfulness_ratio(self):
        """Calculate helpfulness ratio"""
        total_votes = self.helpful_votes + self.unhelpful_votes
        if total_votes == 0:
            return 0
        return (self.helpful_votes / total_votes) * 100