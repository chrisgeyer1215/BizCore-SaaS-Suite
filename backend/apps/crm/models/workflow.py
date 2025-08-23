from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()

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
    status = models.CharField(max_length=20, choices=EXECUTION_STATUS, default='PENDING')
    triggered_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    execution_data = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'workflow_rule', 'status']),
            models.Index(fields=['tenant', 'started_at']),
        ]
        
    def __str__(self):
        return f"{self.workflow_rule.name} - {self.status}"


class Integration(TenantBaseModel, SoftDeleteMixin):
    """Third-party system integrations and API connections"""
    
    INTEGRATION_TYPES = [
        ('EMAIL', 'Email Service'),
        ('CRM', 'External CRM'),
        ('ACCOUNTING', 'Accounting System'),
        ('MARKETING', 'Marketing Platform'),
        ('PAYMENT', 'Payment Gateway'),
        ('CALENDAR', 'Calendar Service'),
        ('SOCIAL', 'Social Media'),
        ('ANALYTICS', 'Analytics Platform'),
        ('ERP', 'ERP System'),
        ('HELPDESK', 'Help Desk'),
        ('COMMUNICATION', 'Communication Tool'),
        ('STORAGE', 'Cloud Storage'),
        ('CUSTOM', 'Custom API'),
        ('WEBHOOK', 'Webhook'),
        ('ZAPIER', 'Zapier'),
        ('SALESFORCE', 'Salesforce'),
        ('HUBSPOT', 'HubSpot'),
        ('MAILCHIMP', 'Mailchimp'),
        ('SLACK', 'Slack'),
        ('MICROSOFT', 'Microsoft Office 365'),
        ('GOOGLE', 'Google Workspace'),
    ]
    
    AUTHENTICATION_TYPES = [
        ('API_KEY', 'API Key'),
        ('OAUTH2', 'OAuth 2.0'),
        ('OAUTH1', 'OAuth 1.0'),
        ('BASIC', 'Basic Authentication'),
        ('BEARER', 'Bearer Token'),
        ('JWT', 'JWT Token'),
        ('CUSTOM', 'Custom Authentication'),
    ]
    
    CONNECTION_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ERROR', 'Connection Error'),
        ('TESTING', 'Testing'),
        ('PENDING', 'Pending Setup'),
        ('EXPIRED', 'Credentials Expired'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES)
    provider_name = models.CharField(max_length=100)
    
    # Configuration
    base_url = models.URLField(blank=True)
    api_version = models.CharField(max_length=20, blank=True)
    authentication_type = models.CharField(max_length=20, choices=AUTHENTICATION_TYPES)
    
    # Authentication Data (encrypted)
    api_key = models.CharField(max_length=500, blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    access_token = models.CharField(max_length=1000, blank=True)
    refresh_token = models.CharField(max_length=1000, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Connection Settings
    status = models.CharField(max_length=20, choices=CONNECTION_STATUS, default='PENDING')
    is_active = models.BooleanField(default=True)
    auto_sync = models.BooleanField(default=False)
    sync_frequency = models.IntegerField(default=60)  # minutes
    
    # Rate Limiting
    rate_limit_per_hour = models.IntegerField(default=1000)
    rate_limit_per_day = models.IntegerField(default=10000)
    
    # Sync Configuration
    sync_settings = models.JSONField(default=dict)
    field_mappings = models.JSONField(default=dict)
    filter_conditions = models.JSONField(default=dict)
    
    # Monitoring
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)
    
    # Usage Statistics
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    total_records_synced = models.IntegerField(default=0)
    
    # Webhook Configuration
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    webhook_events = models.JSONField(default=list)
    
    # Advanced Settings
    timeout_seconds = models.IntegerField(default=30)
    max_retries = models.IntegerField(default=3)
    custom_headers = models.JSONField(default=dict)
    custom_parameters = models.JSONField(default=dict)
    
    # Data Transformation
    data_transformation_rules = models.JSONField(default=dict)
    error_handling_rules = models.JSONField(default=dict)
    
    # Security Settings
    ip_whitelist = models.JSONField(default=list)
    requires_encryption = models.BooleanField(default=True)
    log_requests = models.BooleanField(default=True)
    
    # Notification Settings
    notify_on_error = models.BooleanField(default=True)
    notification_email = models.EmailField(blank=True)
    alert_threshold = models.IntegerField(default=5)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'integration_type', 'status']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'last_sync_at']),
            models.Index(fields=['tenant', 'provider_name']),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.provider_name})"
    
    def is_token_expired(self):
        """Check if access token is expired"""
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at
    
    def get_auth_headers(self):
        """Get authentication headers for API requests"""
        headers = {}
        
        if self.authentication_type == 'API_KEY':
            headers['Authorization'] = f'Bearer {self.api_key}'
        elif self.authentication_type == 'BEARER':
            headers['Authorization'] = f'Bearer {self.access_token}'
        elif self.authentication_type == 'BASIC':
            import base64
            credentials = base64.b64encode(f'{self.client_id}:{self.client_secret}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
            
        headers.update(self.custom_headers)
        return headers
    
    def refresh_access_token(self):
        """Refresh OAuth2 access token"""
        if self.authentication_type != 'OAUTH2' or not self.refresh_token:
            return False
            
        # Implementation would depend on the specific OAuth2 provider
        # This is a placeholder for the actual refresh logic
        pass
    
    def test_connection(self):
        """Test the integration connection"""
        try:
            # Implementation would depend on the specific integration
            # This is a placeholder for the actual test logic
            self.status = 'ACTIVE'
            self.last_successful_sync = timezone.now()
            self.save()
            return True
        except Exception as e:
            self.status = 'ERROR'
            self.last_error_at = timezone.now()
            self.last_error_message = str(e)
            self.save()
            return False


class WebhookConfiguration(TenantBaseModel, SoftDeleteMixin):
    """Webhook endpoint configurations for external integrations"""
    
    EVENT_TYPES = [
        ('LEAD_CREATED', 'Lead Created'),
        ('LEAD_UPDATED', 'Lead Updated'),
        ('ACCOUNT_CREATED', 'Account Created'),
        ('ACCOUNT_UPDATED', 'Account Updated'),
        ('OPPORTUNITY_CREATED', 'Opportunity Created'),
        ('OPPORTUNITY_UPDATED', 'Opportunity Updated'),
        ('OPPORTUNITY_WON', 'Opportunity Won'),
        ('OPPORTUNITY_LOST', 'Opportunity Lost'),
        ('CONTACT_CREATED', 'Contact Created'),
        ('CONTACT_UPDATED', 'Contact Updated'),
        ('ACTIVITY_CREATED', 'Activity Created'),
        ('CAMPAIGN_CREATED', 'Campaign Created'),
        ('TICKET_CREATED', 'Ticket Created'),
        ('TICKET_RESOLVED', 'Ticket Resolved'),
        ('CUSTOM_EVENT', 'Custom Event'),
    ]
    
    METHOD_CHOICES = [
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('FAILED', 'Failed'),
        ('TESTING', 'Testing'),
    ]
    
    # Basic Configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    url = models.URLField()
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='POST')
    
    # Event Configuration
    events = models.JSONField(default=list)  # List of EVENT_TYPES
    custom_events = models.JSONField(default=list)  # Custom event names
    
    # Security
    secret_token = models.CharField(max_length=255, blank=True)
    signature_header = models.CharField(max_length=100, default='X-Webhook-Signature')
    
    # Headers and Payload
    custom_headers = models.JSONField(default=dict)
    payload_template = models.TextField(blank=True)  # JSON template
    include_metadata = models.BooleanField(default=True)
    
    # Delivery Settings
    timeout_seconds = models.IntegerField(default=30)
    max_retries = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)
    
    # Status and Monitoring
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_successful_delivery = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_failure_reason = models.TextField(blank=True)
    
    # Statistics
    total_deliveries = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    
    # Filters
    filter_conditions = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'last_triggered_at']),
        ]
        
    def __str__(self):
        return self.name
    
    def get_webhook_signature(self, payload):
        """Generate webhook signature for payload verification"""
        if not self.secret_token:
            return None
            
        import hmac
        import hashlib
        
        signature = hmac.new(
            self.secret_token.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f'sha256={signature}'
    
    def should_trigger_for_event(self, event_type, event_data=None):
        """Check if webhook should trigger for given event"""
        if self.status != 'ACTIVE':
            return False
            
        if event_type not in self.events and event_type not in self.custom_events:
            return False
            
        # Check filter conditions if any
        if self.filter_conditions and event_data:
            # Implementation for filter evaluation would go here
            pass
            
        return True

