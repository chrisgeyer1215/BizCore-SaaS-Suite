# ============================================================================
# backend/apps/crm/models/system.py - System & Configuration Models
# ============================================================================

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid
import json

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class CustomField(TenantBaseModel, SoftDeleteMixin):
    """Dynamic custom fields for extending CRM entities"""
    
    FIELD_TYPES = [
        ('TEXT', 'Text Field'),
        ('TEXTAREA', 'Text Area'),
        ('NUMBER', 'Number'),
        ('DECIMAL', 'Decimal'),
        ('DATE', 'Date'),
        ('DATETIME', 'Date Time'),
        ('BOOLEAN', 'Yes/No'),
        ('EMAIL', 'Email'),
        ('URL', 'URL'),
        ('PHONE', 'Phone Number'),
        ('CURRENCY', 'Currency'),
        ('PERCENTAGE', 'Percentage'),
        ('PICKLIST', 'Pick List'),
        ('MULTI_PICKLIST', 'Multi-Select Pick List'),
        ('LOOKUP', 'Lookup'),
        ('FILE', 'File Upload'),
        ('IMAGE', 'Image'),
        ('JSON', 'JSON Data'),
    ]
    
    ENTITY_TYPES = [
        ('LEAD', 'Lead'),
        ('ACCOUNT', 'Account'),
        ('CONTACT', 'Contact'),
        ('OPPORTUNITY', 'Opportunity'),
        ('ACTIVITY', 'Activity'),
        ('CAMPAIGN', 'Campaign'),
        ('TICKET', 'Ticket'),
        ('PRODUCT', 'Product'),
    ]
    
    # Field Definition
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    
    # Field Properties
    description = models.TextField(blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    placeholder = models.CharField(max_length=100, blank=True)
    default_value = models.TextField(blank=True)
    
    # Validation Rules
    is_required = models.BooleanField(default=False)
    is_unique = models.BooleanField(default=False)
    max_length = models.IntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    max_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    regex_pattern = models.CharField(max_length=500, blank=True)
    regex_message = models.CharField(max_length=255, blank=True)
    
    # Picklist Options (JSON for flexibility)
    picklist_options = models.JSONField(default=list, blank=True)
    
    # Display Settings
    order_index = models.IntegerField(default=0)
    is_visible_in_list = models.BooleanField(default=True)
    is_visible_in_detail = models.BooleanField(default=True)
    is_visible_in_form = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=True)
    
    # Lookup Configuration
    lookup_entity = models.CharField(max_length=20, blank=True)
    lookup_field = models.CharField(max_length=100, blank=True)
    
    # Dependencies and Conditional Logic
    dependent_field = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_fields'
    )
    conditional_logic = models.JSONField(default=dict, blank=True)
    
    # API Settings
    api_name = models.CharField(max_length=100, blank=True)
    is_api_accessible = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['entity_type', 'order_index', 'display_name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'entity_type', 'name'],
                name='unique_tenant_custom_field'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'entity_type', 'api_name'],
                name='unique_tenant_custom_field_api'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'entity_type', 'is_active']),
            models.Index(fields=['tenant', 'field_type']),
        ]
        
    def __str__(self):
        return f'{self.entity_type} - {self.display_name}'
    
    def save(self, *args, **kwargs):
        if not self.api_name:
            self.api_name = self.name.lower().replace(' ', '_')
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate field configuration"""
        super().clean()
        
        # Validate picklist options for picklist fields
        if self.field_type in ['PICKLIST', 'MULTI_PICKLIST'] and not self.picklist_options:
            raise ValidationError('Picklist fields must have options defined')
        
        # Validate lookup configuration
        if self.field_type == 'LOOKUP' and not (self.lookup_entity and self.lookup_field):
            raise ValidationError('Lookup fields must have entity and field specified')
        
        # Validate number ranges
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValidationError('Min value cannot be greater than max value')
    
    def get_validation_rules(self):
        """Get validation rules for frontend"""
        rules = {
            'required': self.is_required,
            'unique': self.is_unique,
        }
        
        if self.max_length:
            rules['maxLength'] = self.max_length
        
        if self.min_value is not None:
            rules['min'] = float(self.min_value)
        
        if self.max_value is not None:
            rules['max'] = float(self.max_value)
        
        if self.regex_pattern:
            rules['pattern'] = self.regex_pattern
            rules['patternMessage'] = self.regex_message
        
        return rules


class CustomFieldValue(TenantBaseModel):
    """Stores values for custom fields"""
    
    custom_field = models.ForeignKey(
        CustomField,
        on_delete=models.CASCADE,
        related_name='values'
    )
    
    # Generic relation to any CRM entity
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Value storage (uses JSON for flexibility)
    value = models.JSONField(null=True, blank=True)
    text_value = models.TextField(blank=True)  # For search indexing
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'custom_field', 'content_type', 'object_id'],
                name='unique_custom_field_value'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'custom_field']),
            models.Index(fields=['tenant', 'text_value']),
        ]
        
    def __str__(self):
        return f'{self.custom_field.display_name}: {self.text_value[:50]}'
    
    def save(self, *args, **kwargs):
        # Update text_value for search indexing
        if self.value is not None:
            if isinstance(self.value, (str, int, float)):
                self.text_value = str(self.value)
            elif isinstance(self.value, bool):
                self.text_value = 'Yes' if self.value else 'No'
            elif isinstance(self.value, list):
                self.text_value = ', '.join(str(v) for v in self.value)
            else:
                self.text_value = json.dumps(self.value)
        
        super().save(*args, **kwargs)


class AuditTrail(TenantBaseModel):
    """Comprehensive audit trail for all CRM activities"""
    
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('RESTORE', 'Restored'),
        ('VIEW', 'Viewed'),
        ('EXPORT', 'Exported'),
        ('IMPORT', 'Imported'),
        ('ASSIGN', 'Assigned'),
        ('UNASSIGN', 'Unassigned'),
        ('CONVERT', 'Converted'),
        ('DUPLICATE', 'Duplicated'),
        ('MERGE', 'Merged'),
        ('SPLIT', 'Split'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
        ('SEND', 'Sent'),
        ('RECEIVE', 'Received'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('PERMISSION_CHANGE', 'Permission Changed'),
        ('STATUS_CHANGE', 'Status Changed'),
    ]
    
    # Action Details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action_datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions'
    )
    
    # Entity Information
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36)
    object_name = models.CharField(max_length=255)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Change Details
    field_name = models.CharField(max_length=100, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    change_summary = models.TextField(blank=True)
    
    # Context Information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_url = models.URLField(blank=True)
    
    # Additional Metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Risk Assessment
    risk_level = models.CharField(
        max_length=10,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
        default='LOW'
    )
    
    class Meta:
        ordering = ['-action_datetime']
        indexes = [
            models.Index(fields=['tenant', 'action_datetime']),
            models.Index(fields=['tenant', 'action_type']),
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'ip_address']),
            models.Index(fields=['tenant', 'risk_level']),
        ]
        
    def __str__(self):
        user_name = self.user.get_full_name() if self.user else 'System'
        return f'{user_name} {self.get_action_type_display()} {self.object_name}'
    
    @classmethod
    def log_action(cls, tenant, action_type, user, obj, field_name=None, 
                   old_value=None, new_value=None, ip_address=None, 
                   user_agent=None, metadata=None):
        """Helper method to log audit actions"""
        return cls.objects.create(
            tenant=tenant,
            action_type=action_type,
            user=user,
            content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk),
            object_name=str(obj),
            field_name=field_name or '',
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent or '',
            metadata=metadata or {}
        )


class DataExportLog(TenantBaseModel):
    """Track data exports for compliance and security"""
    
    EXPORT_TYPES = [
        ('CSV', 'CSV Export'),
        ('EXCEL', 'Excel Export'),
        ('PDF', 'PDF Export'),
        ('JSON', 'JSON Export'),
        ('XML', 'XML Export'),
        ('API', 'API Export'),
        ('BACKUP', 'Backup Export'),
        ('MIGRATION', 'Migration Export'),
    ]
    
    EXPORT_STATUS = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    # Export Details
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    entity_type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    
    # Request Information
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_requests'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    
    # Export Configuration
    filters = models.JSONField(default=dict, blank=True)
    fields = models.JSONField(default=list, blank=True)
    format_options = models.JSONField(default=dict, blank=True)
    
    # Processing Status
    status = models.CharField(max_length=15, choices=EXPORT_STATUS, default='PENDING')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    total_records = models.IntegerField(default=0)
    exported_records = models.IntegerField(default=0)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.BigIntegerField(default=0)  # Size in bytes
    download_url = models.URLField(blank=True)
    
    # Security & Compliance
    contains_pii = models.BooleanField(default=False)
    security_classification = models.CharField(
        max_length=20,
        choices=[
            ('PUBLIC', 'Public'),
            ('INTERNAL', 'Internal'),
            ('CONFIDENTIAL', 'Confidential'),
            ('RESTRICTED', 'Restricted'),
        ],
        default='INTERNAL'
    )
    
    # Access Control
    download_count = models.IntegerField(default=0)
    last_downloaded = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_key = models.UUIDField(default=uuid.uuid4, unique=True)
    
    # Error Handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'requested_by']),
            models.Index(fields=['tenant', 'export_type']),
            models.Index(fields=['tenant', 'entity_type']),
            models.Index(fields=['access_key']),
        ]
        
    def __str__(self):
        return f'{self.export_type} - {self.entity_type} ({self.status})'
    
    def save(self, *args, **kwargs):
        # Set expiration date if not set
        if not self.expires_at and self.status == 'COMPLETED':
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if export has expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    def generate_download_url(self):
        """Generate secure download URL"""
        if self.status == 'COMPLETED' and not self.is_expired():
            base_url = '/api/crm/exports/download/'
            return f'{base_url}{self.access_key}/'
        return None


class APIUsageLog(TenantBaseModel):
    """Track API usage for monitoring and billing"""
    
    HTTP_METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
        ('HEAD', 'HEAD'),
    ]
    
    # Request Information
    method = models.CharField(max_length=10, choices=HTTP_METHODS)
    endpoint = models.CharField(max_length=500)
    api_version = models.CharField(max_length=10, default='v1')
    request_time = models.DateTimeField(auto_now_add=True)
    
    # User Context
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_requests'
    )
    api_key = models.CharField(max_length=100, blank=True)
    
    # Request Details
    query_params = models.JSONField(default=dict, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body_size = models.IntegerField(default=0)
    
    # Response Information
    status_code = models.IntegerField()
    response_time_ms = models.IntegerField()
    response_size = models.IntegerField(default=0)
    
    # Network Information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    referer = models.URLField(blank=True)
    
    # Rate Limiting
    rate_limit_key = models.CharField(max_length=100, blank=True)
    rate_limit_remaining = models.IntegerField(null=True, blank=True)
    
    # Error Information
    is_error = models.BooleanField(default=False)
    error_type = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    
    # Business Context
    affected_resources = models.JSONField(default=list, blank=True)
    operation_type = models.CharField(
        max_length=20,
        choices=[
            ('READ', 'Read'),
            ('WRITE', 'Write'),
            ('DELETE', 'Delete'),
            ('SEARCH', 'Search'),
            ('BULK', 'Bulk Operation'),
            ('EXPORT', 'Export'),
            ('IMPORT', 'Import'),
        ],
        blank=True
    )
    
    class Meta:
        ordering = ['-request_time']
        indexes = [
            models.Index(fields=['tenant', 'request_time']),
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'endpoint']),
            models.Index(fields=['tenant', 'status_code']),
            models.Index(fields=['tenant', 'is_error']),
            models.Index(fields=['tenant', 'api_key']),
        ]
        
    def __str__(self):
        return f'{self.method} {self.endpoint} - {self.status_code}'
    
    @property
    def is_successful(self):
        """Check if request was successful"""
        return 200 <= self.status_code < 300
    
    @classmethod
    def log_request(cls, tenant, request, response, user=None, api_key=None, 
                   operation_type=None, affected_resources=None):
        """Helper method to log API requests"""
        import time
        
        # Calculate response time if available
        response_time = 0
        if hasattr(request, '_request_start_time'):
            response_time = int((time.time() - request._request_start_time) * 1000)
        
        return cls.objects.create(
            tenant=tenant,
            method=request.method,
            endpoint=request.path,
            user=user,
            api_key=api_key or '',
            query_params=dict(request.GET),
            status_code=response.status_code,
            response_time_ms=response_time,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referer=request.META.get('HTTP_REFERER', ''),
            is_error=response.status_code >= 400,
            operation_type=operation_type or '',
            affected_resources=affected_resources or []
        )


class SyncLog(TenantBaseModel):
    """Track data synchronization with external systems"""
    
    SYNC_TYPES = [
        ('IMPORT', 'Data Import'),
        ('EXPORT', 'Data Export'),
        ('INTEGRATION', 'Third-party Integration'),
        ('BACKUP', 'Backup'),
        ('MIGRATION', 'Data Migration'),
        ('CLEANUP', 'Data Cleanup'),
        ('VALIDATION', 'Data Validation'),
    ]
    
    SYNC_STATUS = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('PARTIAL', 'Partially Completed'),
    ]
    
    # Sync Identification
    sync_id = models.UUIDField(default=uuid.uuid4, unique=True)
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Source and Destination
    source_system = models.CharField(max_length=100)
    destination_system = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50, blank=True)
    
    # Trigger Information
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_syncs'
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=[
            ('MANUAL', 'Manual'),
            ('SCHEDULED', 'Scheduled'),
            ('WEBHOOK', 'Webhook'),
            ('API', 'API Call'),
            ('EVENT', 'Event Triggered'),
        ],
        default='MANUAL'
    )
    
    # Status and Timing
    status = models.CharField(max_length=15, choices=SYNC_STATUS, default='PENDING')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Progress Tracking
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    
    # Configuration
    sync_config = models.JSONField(default=dict, blank=True)
    field_mappings = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Results and Errors
    sync_summary = models.JSONField(default=dict, blank=True)
    error_details = models.JSONField(default=list, blank=True)
    success_details = models.JSONField(default=list, blank=True)
    
    # Performance Metrics
    average_record_time_ms = models.IntegerField(default=0)
    peak_memory_usage_mb = models.IntegerField(default=0)
    data_volume_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Retry Logic
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'sync_type']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'source_system']),
            models.Index(fields=['tenant', 'destination_system']),
            models.Index(fields=['tenant', 'entity_type']),
            models.Index(fields=['sync_id']),
        ]
        
    def __str__(self):
        return f'{self.name} ({self.sync_type}) - {self.status}'
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_records > 0:
            return (self.processed_records / self.total_records) * 100
        return 0
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.processed_records > 0:
            return (self.successful_records / self.processed_records) * 100
        return 0
    
    @property
    def duration_seconds(self):
        """Calculate sync duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return 0
    
    def update_progress(self, processed=None, successful=None, failed=None, skipped=None):
        """Update sync progress"""
        if processed is not None:
            self.processed_records = processed
        if successful is not None:
            self.successful_records = successful
        if failed is not None:
            self.failed_records = failed
        if skipped is not None:
            self.skipped_records = skipped
        
        # Update status based on progress
        if self.processed_records >= self.total_records:
            if self.failed_records == 0:
                self.status = 'COMPLETED'
            elif self.successful_records > 0:
                self.status = 'PARTIAL'
            else:
                self.status = 'FAILED'
        
        self.save()
    
    def add_error(self, record_id, error_message, error_details=None):
        """Add error details for a specific record"""
        error_entry = {
            'record_id': record_id,
            'error_message': error_message,
            'error_details': error_details or {},
            'timestamp': timezone.now().isoformat()
        }
        
        if not isinstance(self.error_details, list):
            self.error_details = []
        
        self.error_details.append(error_entry)
        self.save()
    
    def add_success(self, record_id, details=None):
        """Add success details for a specific record"""
        success_entry = {
            'record_id': record_id,
            'details': details or {},
            'timestamp': timezone.now().isoformat()
        }
        
        if not isinstance(self.success_details, list):
            self.success_details = []
        
        self.success_details.append(success_entry)
        self.save()


class SystemConfiguration(TenantBaseModel):
    """Global system configuration settings"""
    
    CONFIG_TYPES = [
        ('GENERAL', 'General Settings'),
        ('EMAIL', 'Email Configuration'),
        ('SECURITY', 'Security Settings'),
        ('API', 'API Configuration'),
        ('INTEGRATION', 'Integration Settings'),
        ('NOTIFICATION', 'Notification Settings'),
        ('WORKFLOW', 'Workflow Settings'),
        ('REPORTING', 'Reporting Configuration'),
    ]
    
    # Configuration Identity
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES)
    key = models.CharField(max_length=100)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Value Storage
    value = models.JSONField()
    default_value = models.JSONField(null=True, blank=True)
    
    # Metadata
    is_encrypted = models.BooleanField(default=False)
    is_read_only = models.BooleanField(default=False)
    is_system_default = models.BooleanField(default=False)