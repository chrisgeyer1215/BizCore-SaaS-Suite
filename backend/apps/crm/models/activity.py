# ============================================================================
# models/activity.py - 8 Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class ActivityType(TenantBaseModel, SoftDeleteMixin):
    """Enhanced activity types with automation and scoring"""
    
    ACTIVITY_CATEGORIES = [
        ('COMMUNICATION', 'Communication'),
        ('MEETING', 'Meeting'),
        ('TASK', 'Task'),
        ('SALES', 'Sales Activity'),
        ('MARKETING', 'Marketing Activity'),
        ('SUPPORT', 'Support Activity'),
    ]
    
    # Type Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=ACTIVITY_CATEGORIES)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    
    # Behavior Settings
    requires_duration = models.BooleanField(default=False)
    requires_outcome = models.BooleanField(default=False)
    auto_complete = models.BooleanField(default=False)
    
    # Scoring Impact
    score_impact = models.IntegerField(default=0)
    
    # Default Settings
    default_duration_minutes = models.IntegerField(default=30)
    default_reminder_minutes = models.IntegerField(default=15)
    
    # Performance Tracking
    total_activities = models.IntegerField(default=0)
    average_duration = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name_plural = 'Activity Types'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_activity_type'
            ),
        ]
        
    def __str__(self):
        return self.name


class Activity(TenantBaseModel, SoftDeleteMixin):
    """Enhanced activity tracking with rich metadata"""
    
    ACTIVITY_STATUS = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('OVERDUE', 'Overdue'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    # Activity Identification
    activity_number = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Activity Classification
    activity_type = models.ForeignKey(
        ActivityType,
        on_delete=models.PROTECT,
        related_name='activities'
    )
    status = models.CharField(max_length=20, choices=ACTIVITY_STATUS, default='PLANNED')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    
    # Scheduling
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.IntegerField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_activities'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_activities'
    )
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Location & Meeting Details
    location = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    meeting_password = models.CharField(max_length=100, blank=True)
    
    # Outcome & Results
    outcome = models.TextField(blank=True)
    result = models.CharField(
        max_length=20,
        choices=[
            ('SUCCESSFUL', 'Successful'),
            ('UNSUCCESSFUL', 'Unsuccessful'),
            ('RESCHEDULED', 'Rescheduled'),
            ('NO_SHOW', 'No Show'),
        ],
        blank=True
    )
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_activity = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_activity'
    )
    
    # Reminders
    reminder_set = models.BooleanField(default=False)
    reminder_minutes = models.IntegerField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    
    # Completion Tracking
    completed_date = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_activities'
    )
    
    # Additional Information
    tags = models.JSONField(default=list)
    attachments = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-start_datetime']
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=['tenant', 'assigned_to', 'status']),
            models.Index(fields=['tenant', 'start_datetime']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'activity_type']),
        ]
        
    def __str__(self):
        return f'{self.subject} - {self.assigned_to.get_full_name()}'
    
    def save(self, *args, **kwargs):
        if not self.activity_number:
            self.activity_number = self.generate_activity_number()
        
        # Calculate duration
        if self.start_datetime and self.end_datetime:
            duration = self.end_datetime - self.start_datetime
            self.duration_minutes = int(duration.total_seconds() / 60)
        
        # Auto-complete if end time has passed
        if self.status == 'PLANNED' and self.end_datetime < timezone.now():
            self.status = 'OVERDUE'
        
        super().save(*args, **kwargs)
    
    def generate_activity_number(self):
        """Generate unique activity number"""
        return generate_code('ACT', self.tenant_id)
    
    def mark_completed(self, user, outcome=None):
        """Mark activity as completed"""
        self.status = 'COMPLETED'
        self.completed_date = timezone.now()
        self.completed_by = user
        if outcome:
            self.outcome = outcome
        self.save()


class ActivityParticipant(TenantBaseModel):
    """Enhanced participants in activities with response tracking"""
    
    PARTICIPANT_TYPES = [
        ('REQUIRED', 'Required'),
        ('OPTIONAL', 'Optional'),
        ('ORGANIZER', 'Organizer'),
        ('RESOURCE', 'Resource'),
    ]
    
    RESPONSE_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
        ('TENTATIVE', 'Tentative'),
        ('NO_RESPONSE', 'No Response'),
    ]
    
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_participations'
    )
    
    # Participation Details
    participant_type = models.CharField(max_length=20, choices=PARTICIPANT_TYPES, default='REQUIRED')
    response = models.CharField(max_length=15, choices=RESPONSE_CHOICES, default='PENDING')
    response_datetime = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True)
    
    # Contact Information (for external participants)
    external_email = models.EmailField(blank=True)
    external_name = models.CharField(max_length=100, blank=True)
    
    # Attendance Tracking
    attended = models.BooleanField(null=True, blank=True)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Activity Participant'
        verbose_name_plural = 'Activity Participants'
        constraints = [
            models.UniqueConstraint(
                fields=['activity', 'user'],
                name='unique_activity_user_participant'
            ),
        ]
        
    def __str__(self):
        name = self.user.get_full_name() if self.user else self.external_name
        return f'{name} - {self.activity.subject}'


class Note(TenantBaseModel, SoftDeleteMixin):
    """Enhanced notes with rich formatting and collaboration"""
    
    NOTE_TYPES = [
        ('GENERAL', 'General Note'),
        ('MEETING', 'Meeting Notes'),
        ('CALL', 'Call Notes'),
        ('TASK', 'Task Notes'),
        ('FOLLOW_UP', 'Follow-up Notes'),
    ]
    
    # Note Content
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='GENERAL')
    
    # Formatting
    is_html = models.BooleanField(default=False)
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Privacy & Sharing
    is_private = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        related_name='shared_notes',
        blank=True
    )
    
    # Activity Association
    activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes'
    )
    
    # Tagging & Organization
    tags = models.JSONField(default=list)
    
    # Collaboration
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='last_edited_notes'
    )
    edit_history = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'created_by']),
            models.Index(fields=['tenant', 'note_type']),
        ]
        
    def __str__(self):
        return self.title or f'Note - {self.created_at.strftime("%Y-%m-%d")}'


class EmailTemplate(TenantBaseModel, SoftDeleteMixin):
    """Enhanced email templates with dynamic content"""
    
    TEMPLATE_TYPES = [
        ('MARKETING', 'Marketing Email'),
        ('SALES', 'Sales Email'),
        ('FOLLOW_UP', 'Follow-up Email'),
        ('WELCOME', 'Welcome Email'),
        ('REMINDER', 'Reminder Email'),
        ('PROPOSAL', 'Proposal Email'),
        ('THANK_YOU', 'Thank You Email'),
        ('MEETING_INVITE', 'Meeting Invitation'),
    ]
    
    # Template Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    
    # Email Content
    subject = models.CharField(max_length=255)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Template Variables
    available_variables = models.JSONField(default=list)
    merge_tags = models.JSONField(default=dict)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_system_template = models.BooleanField(default=False)
    
    # Usage Tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Personalization
    sender_name = models.CharField(max_length=100, blank=True)
    sender_email = models.EmailField(blank=True)
    reply_to_email = models.EmailField(blank=True)
    
    # Attachments
    default_attachments = models.JSONField(default=list)
    
    class Meta:
        ordering = ['template_type', 'name']
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        
    def __str__(self):
        return self.name
    
    def render_content(self, context_data):
        """Render template with context data"""
        from django.template import Context, Template
        
        # Render subject
        subject_template = Template(self.subject)
        rendered_subject = subject_template.render(Context(context_data))
        
        # Render body
        if self.body_html:
            body_template = Template(self.body_html)
            rendered_body = body_template.render(Context(context_data))
        else:
            body_template = Template(self.body_text)
            rendered_body = body_template.render(Context(context_data))
        
        return {
            'subject': rendered_subject,
            'body': rendered_body,
            'is_html': bool(self.body_html)
        }


class EmailLog(TenantBaseModel):
    """Enhanced email interaction tracking with analytics"""
    
    EMAIL_STATUS = [
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('OPENED', 'Opened'),
        ('CLICKED', 'Clicked'),
        ('REPLIED', 'Replied'),
        ('BOUNCED', 'Bounced'),
        ('UNSUBSCRIBED', 'Unsubscribed'),
        ('SPAM', 'Marked as Spam'),
        ('FAILED', 'Failed'),
    ]
    
    # Email Details
    subject = models.CharField(max_length=255)
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=100, blank=True)
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=100, blank=True)
    
    # Additional Recipients
    cc_emails = models.JSONField(default=list)
    bcc_emails = models.JSONField(default=list)
    
    # Content
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Template Association
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    
    # Status & Tracking
    status = models.CharField(max_length=15, choices=EMAIL_STATUS, default='SENT')
    sent_datetime = models.DateTimeField()
    delivered_datetime = models.DateTimeField(null=True, blank=True)
    opened_datetime = models.DateTimeField(null=True, blank=True)
    clicked_datetime = models.DateTimeField(null=True, blank=True)
    replied_datetime = models.DateTimeField(null=True, blank=True)
    
    # Engagement Metrics
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Campaign Association
    campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    
    # Technical Details
    message_id = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    
    # Error Information
    error_message = models.TextField(blank=True)
    bounce_reason = models.CharField(max_length=255, blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-sent_datetime']
        indexes = [
            models.Index(fields=['tenant', 'recipient_email', 'status']),
            models.Index(fields=['tenant', 'sent_datetime']),
            models.Index(fields=['tenant', 'campaign']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
        ]
        
    def __str__(self):
        return f'{self.subject} - {self.recipient_email}'


class CallLog(TenantBaseModel, SoftDeleteMixin):
    """Enhanced call logging with outcome tracking"""
    
    CALL_TYPES = [
        ('INBOUND', 'Inbound'),
        ('OUTBOUND', 'Outbound'),
        ('INTERNAL', 'Internal'),
    ]
    
    CALL_STATUS = [
        ('PLANNED', 'Planned'),
        ('CONNECTED', 'Connected'),
        ('NO_ANSWER', 'No Answer'),
        ('BUSY', 'Busy'),
        ('VOICEMAIL', 'Voicemail'),
        ('FAILED', 'Failed'),
    ]
    
    CALL_OUTCOMES = [
        ('SUCCESSFUL', 'Successful'),
        ('APPOINTMENT_SET', 'Appointment Set'),
        ('FOLLOW_UP_REQUIRED', 'Follow-up Required'),
        ('NOT_INTERESTED', 'Not Interested'),
        ('WRONG_NUMBER', 'Wrong Number'),
        ('CALLBACK_REQUESTED', 'Callback Requested'),
    ]
    
    # Call Details
    call_type = models.CharField(max_length=15, choices=CALL_TYPES)
    phone_number = models.CharField(max_length=20)
    caller_name = models.CharField(max_length=100, blank=True)
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Participants
    caller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='made_calls'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_calls'
    )
    
    # Call Status & Outcome
    status = models.CharField(max_length=15, choices=CALL_STATUS, default='PLANNED')
    outcome = models.CharField(max_length=25, choices=CALL_OUTCOMES, blank=True)
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Call Notes
    notes = models.TextField(blank=True)
    agenda = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    
    # Recording & Transcription
    recording_url = models.URLField(blank=True)
    transcription = models.TextField(blank=True)
    
    # Integration Details
    phone_system_id = models.CharField(max_length=100, blank=True)
    external_call_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['tenant', 'caller', 'start_time']),
            models.Index(fields=['tenant', 'phone_number']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
        ]
        
    def __str__(self):
        return f'{self.call_type} Call - {self.phone_number} ({self.start_time})'
    
    def save(self, *args, **kwargs):
        # Calculate duration
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            self.duration_seconds = int(duration.total_seconds())
        super().save(*args, **kwargs)


class SMSLog(TenantBaseModel):
    """Enhanced SMS/text message logging"""
    
    SMS_TYPES = [
        ('INBOUND', 'Inbound'),
        ('OUTBOUND', 'Outbound'),
    ]
    
    SMS_STATUS = [
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('RECEIVED', 'Received'),
    ]
    
    # Message Details
    sms_type = models.CharField(max_length=15, choices=SMS_TYPES)
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    
    # Sender/Recipient
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_sms'
    )
    recipient_name = models.CharField(max_length=100, blank=True)
    
    # Status & Timing
    status = models.CharField(max_length=15, choices=SMS_STATUS, default='SENT')
    sent_datetime = models.DateTimeField()
    delivered_datetime = models.DateTimeField(null=True, blank=True)
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Provider Details
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Error Information
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-sent_datetime']
        verbose_name = 'SMS Log'
        verbose_name_plural = 'SMS Logs'
        indexes = [
            models.Index(fields=['tenant', 'phone_number', 'sms_type']),
            models.Index(fields=['tenant', 'sent_datetime']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
        ]
        
    def __str__(self):
        return f'{self.sms_type} SMS - {self.phone_number}'