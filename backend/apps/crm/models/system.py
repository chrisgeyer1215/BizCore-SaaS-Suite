class CustomField(TenantBaseModel, SoftDeleteMixin):
    """Enhanced custom field definitions for flexible data collection"""
    
    FIELD_TYPES = [
        ('TEXT', 'Text'),
        ('TEXTAREA', 'Text Area'),
        ('NUMBER', 'Number'),
        ('DECIMAL', 'Decimal'),
        ('DATE', 'Date'),
        ('DATETIME', 'Date Time'),
        ('BOOLEAN', 'Boolean'),
        ('DROPDOWN', 'Dropdown'),
        ('MULTI_SELECT', 'Multi Select'),
        ('EMAIL', 'Email'),
        ('URL', 'URL'),
        ('PHONE', 'Phone'),
        ('CURRENCY', 'Currency'),
        ('PERCENTAGE', 'Percentage'),
        ('FILE', 'File Upload'),
        ('LOOKUP', 'Lookup'),
    ]
    
    ENTITY_TYPES = [
        ('lead', 'Lead'),
        ('account', 'Account'),
        ('contact', 'Contact'),
        ('opportunity', 'Opportunity'),
        ('activity', 'Activity'),
        ('campaign', 'Campaign'),
        ('ticket', 'Ticket'),
        ('product', 'Product'),
    ]
    
    # Field Definition
    field_name = models.CharField(max_length=100)
    field_label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    
    # Field Configuration
    is_required = models.BooleanField(default=False)
    default_value = models.TextField(blank=True)
    placeholder_text = models.CharField(max_length=255, blank=True)
    help_text = models.TextField(blank=True)
    
    # Validation Rules
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    validation_pattern = models.CharField(max_length=500, blank=True)
    validation_message = models.CharField(max_length=255, blank=True)
    
    # Options for Dropdown/Multi-select
    field_options = models.JSONField(default=list)
    
    # Lookup Configuration
    lookup_entity = models.CharField(max_length=50, blank=True)
    lookup_field = models.CharField(max_length=100, blank=True)
    
    # Display Configuration
    display_order = models.IntegerField(default=0)
    column_width = models.IntegerField(default=12)  # Bootstrap column width
    is_searchable = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=False)
    
    # Access Control
    visible_to_roles = models.JSONField(default=list)
    editable_by_roles = models.JSONField(default=list)
    
    # Settings
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['entity_type', 'display_order', 'field_label']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'entity_type', 'field_name'],
                name='unique_tenant_custom_field'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'entity_type', 'is_active']),
        ]
        
    def __str__(self):
        return f'{self.entity_type.title()} - {self.field_label}'
    
    def validate_value(self, value):
        """Validate field value against rules"""
        if self.is_required and not value:
            return False, 'This field is required'
        
        if not value:
            return True, None
        
        # Type-specific validation
        if self.field_type == 'EMAIL':
            from django.core.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                return False, 'Invalid email format'
        
        elif self.field_type == 'NUMBER':
            try:
                num_value = int(value)
                if self.min_value and num_value < self.min_value:
                    return False, f'Value must be at least {self.min_value}'
                if self.max_value and num_value > self.max_value:
                    return False, f'Value must be at most {self.max_value}'
            except ValueError:
                return False, 'Invalid number format'
        
        elif self.field_type in ['TEXT', 'TEXTAREA']:
            if self.min_length and len(str(value)) < self.min_length:
                return False, f'Must be at least {self.min_length} characters'
            if self.max_length and len(str(value)) > self.max_length:
                return False, f'Must be at most {self.max_length} characters'
        
        elif self.field_type == 'DROPDOWN':
            if value not in [opt.get('value') for opt in self.field_options]:
                return False, 'Invalid option selected'
        
        return True, None


class AuditTrail(TenantBaseModel):
    """Enhanced audit trail for compliance and tracking"""
    
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('VIEW', 'Viewed'),
        ('EXPORT', 'Exported'),
        ('IMPORT', 'Imported'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('PERMISSION_CHANGE', 'Permission Changed'),
        ('PASSWORD_CHANGE', 'Password Changed'),
        ('BULK_UPDATE', 'Bulk Update'),
        ('MERGE', 'Merged'),
        ('CONVERT', 'Converted'),
        ('ASSIGN', 'Assigned'),
        ('SHARE', 'Shared'),
        ('ARCHIVE', 'Archived'),
        ('RESTORE', 'Restored'),
    ]
    
    # Action Information
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action_timestamp = models.DateTimeField(auto_now_add=True)
    
    # User Information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions'
    )
    user_email = models.EmailField(blank=True)
    user_ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Object Information
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    
    # Change Details
    field_changes = models.JSONField(default=dict)
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    
    # Additional Context
    session_id = models.CharField(max_length=100, blank=True)
    request_id = models.CharField(max_length=100, blank=True)
    additional_data = models.JSONField(default=dict)
    
    # System Information
    system_version = models.CharField(max_length=50, blank=True)
    module_name = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-action_timestamp']
        indexes = [
            models.Index(fields=['tenant', 'action_type', 'action_timestamp']),
            models.Index(fields=['tenant', 'user', 'action_timestamp']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'action_timestamp']),
        ]
        
    def __str__(self):
        user_str = self.user_email or (self.user.email if self.user else 'System')
        return f'{user_str} {self.action_type} {self.object_repr} at {self.action_timestamp}'
    
    @classmethod
    def log_action(cls, tenant, user, action_type, obj=None, field_changes=None, 
                   request=None, additional_data=None):
        """Log an audit action"""
        audit_data = {
            'tenant': tenant,
            'action_type': action_type,
            'user': user if user and user.is_authenticated else None,
            'additional_data': additional_data or {}
        }
        
        # User information
        if user and user.is_authenticated:
            audit_data['user_email'] = user.email
        
        # Request information
        if request:
            audit_data['user_ip_address'] = cls._get_client_ip(request)
            audit_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
            audit_data['session_id'] = request.session.session_key or ''
        
        # Object information
        if obj:
            audit_data['content_type'] = ContentType.objects.get_for_model(obj)
            audit_data['object_id'] = str(obj.pk)
            audit_data['object_repr'] = str(obj)[:255]
        
        # Field changes
        if field_changes:
            audit_data['field_changes'] = field_changes
            audit_data['old_values'] = {k: v.get('old') for k, v in field_changes.items()}
            audit_data['new_values'] = {k: v.get('new') for k, v in field_changes.items()}
        
        return cls.objects.create(**audit_data)
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DataExportLog(TenantBaseModel):
    """Enhanced data export tracking for compliance"""
    
    EXPORT_TYPES = [
        ('CSV', 'CSV Export'),
        ('EXCEL', 'Excel Export'),
        ('PDF', 'PDF Export'),
        ('JSON', 'JSON Export'),
        ('XML', 'XML Export'),
        ('API', 'API Export'),
        ('BACKUP', 'Data Backup'),
    ]
    
    EXPORT_STATUS = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Export Information
    export_type = models.CharField(max_length=15, choices=EXPORT_TYPES)
    export_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # User Information
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='data_exports'
    )
    requested_date = models.DateTimeField(auto_now_add=True)
    
    # Export Configuration
    entity_types = models.JSONField(default=list)
    filters = models.JSONField(default=dict)
    fields_included = models.JSONField(default=list)
    date_range = models.JSONField(default=dict)
    
    # Processing Information
    status = models.CharField(max_length=15, choices=EXPORT_STATUS, default='PENDING')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time_seconds = models.FloatField(null=True, blank=True)
    
    # Results
    total_records = models.IntegerField(default=0)
    exported_records = models.IntegerField(default=0)
    file_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    download_url = models.URLField(blank=True)
    
    # Security
    is_encrypted = models.BooleanField(default=False)
    password_protected = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    
    # Error Information
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict)
    
    # Compliance
    reason_for_export = models.TextField(blank=True)
    data_retention_period_days = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-requested_date']
        indexes = [
            models.Index(fields=['tenant', 'requested_by', 'status']),
            models.Index(fields=['tenant', 'export_type', 'requested_date']),
            models.Index(fields=['tenant', 'status']),
        ]
        
    def __str__(self):
        return f'{self.export_name} - {self.requested_by.get_full_name()}'
    
    def start_processing(self):
        """Mark export as started"""
        self.status = 'PROCESSING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self, file_path, file_size, total_records, exported_records):
        """Mark export as completed"""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.file_path = file_path
        self.file_size_bytes = file_size
        self.total_records = total_records
        self.exported_records = exported_records
        
        if self.started_at:
            duration = self.completed_at - self.started_at
            self.processing_time_seconds = duration.total_seconds()
        
        self.save()
    
    def mark_failed(self, error_message, error_details=None):
        """Mark export as failed"""
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.error_details = error_details or {}
        
        if self.started_at:
            duration = self.completed_at - self.started_at
            self.processing_time_seconds = duration.total_seconds()
        
        self.save()
    
    def track_download(self):
        """Track file download"""
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    @property
    def is_expired(self):
        """Check if export has expired"""
        return self.expires_at and timezone.now() > self.expires_at


class APIUsageLog(TenantBaseModel):
    """Enhanced API usage tracking for monitoring and billing"""
    
    HTTP_METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('HEAD', 'HEAD'),
        ('OPTIONS', 'OPTIONS'),
    ]
    
    # Request Information
    api_name = models.CharField(max_length=100)
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=HTTP_METHODS)
    request_time = models.DateTimeField(auto_now_add=True)
    
    # User Information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_usage'
    )
    api_key = models.CharField(max_length=100, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Request Details
    request_size_bytes = models.IntegerField(null=True, blank=True)
    request_headers = models.JSONField(default=dict)
    query_parameters = models.JSONField(default=dict)
    
    # Response Information
    response_status_code = models.IntegerField()
    response_size_bytes = models.IntegerField(null=True, blank=True)
    response_time_ms = models.FloatField()
    
    # Performance Metrics
    database_queries = models.IntegerField(default=0)
    cache_hits = models.IntegerField(default=0)
    cache_misses = models.IntegerField(default=0)
    
    # Rate Limiting
    rate_limit_remaining = models.IntegerField(null=True, blank=True)
    rate_limit_reset = models.DateTimeField(null=True, blank=True)
    rate_limited = models.BooleanField(default=False)
    
    # Error Information
    is_error = models.BooleanField(default=False)
    error_type = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    
    # Business Context
    records_returned = models.IntegerField(null=True, blank=True)
    records_modified = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-request_time']
        indexes = [
            models.Index(fields=['tenant', 'api_name', 'request_time']),
            models.Index(fields=['tenant', 'user', 'request_time']),
            models.Index(fields=['tenant', 'is_error', 'request_time']),
            models.Index(fields=['tenant', 'response_status_code']),
        ]
        
    def __str__(self):
        user_str = self.user.email if self.user else 'API Key'
        return f'{self.method} {self.endpoint} - {user_str} ({self.response_status_code})'
    
    @classmethod
    def log_api_call(cls, tenant, request, response, user=None, api_key=None, 
                     performance_data=None):
        """Log an API call"""
        import time
        
        # Calculate response time
        start_time = getattr(request, '_start_time', time.time())
        response_time_ms = (time.time() - start_time) * 1000
        
        log_data = {
            'tenant': tenant,
            'api_name': request.resolver_match.app_name or 'api',
            'endpoint': request.path,
            'method': request.method,
            'user': user,
            'api_key': api_key,
            'client_ip': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'response_status_code': response.status_code,
            'response_time_ms': response_time_ms,
            'is_error': response.status_code >= 400,
        }
        
        # Request details
        if hasattr(request, 'body'):
            log_data['request_size_bytes'] = len(request.body)
        
        # Response details
        if hasattr(response, 'content'):
            log_data['response_size_bytes'] = len(response.content)
        
        # Performance data
        if performance_data:
            log_data.update(performance_data)
        
        return cls.objects.create(**log_data)
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SyncLog(TenantBaseModel):
    """Enhanced data synchronization tracking"""
    
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
        ('COMPLETED_WITH_ERRORS', 'Completed with Errors'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('PAUSED', 'Paused'),
    ]
    
    # Sync Information
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    sync_name = models.CharField(max_length=255)
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    
    # Status & Timing
    status = models.CharField(max_length=25, choices=SYNC_STATUS, default='PENDING')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # User Information
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_syncs'
    )
    
    # Configuration
    sync_configuration = models.JSONField(default=dict)
    filters_applied = models.JSONField(default=dict)
    mapping_rules = models.JSONField(default=dict)
    
    # Progress Tracking
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    
    # Results
    sync_summary = models.JSONField(default=dict)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_deleted = models.IntegerField(default=0)
    
    # Error Tracking
    error_details = models.JSONField(default=list)
    warning_details = models.JSONField(default=list)
    
    # File Information
    source_file_path = models.CharField(max_length=500, blank=True)
    output_file_path = models.CharField(max_length=500, blank=True)
    log_file_path = models.CharField(max_length=500, blank=True)
    
    # Integration Details
    external_system = models.CharField(max_length=100, blank=True)
    external_sync_id = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'sync_type', 'status']),
            models.Index(fields=['tenant', 'initiated_by', 'started_at']),
            models.Index(fields=['tenant', 'external_system']),
        ]
        
    def __str__(self):
        return f'{self.sync_name} ({self.sync_type}): {self.source} → {self.destination}'
    
    def start_sync(self):
        """Mark sync as started"""
        self.status = 'RUNNING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def update_progress(self, processed, successful=None, failed=None, skipped=None):
        """Update sync progress"""
        self.processed_records = processed
        if successful is not None:
            self.successful_records = successful
        if failed is not None:
            self.failed_records = failed
        if skipped is not None:
            self.skipped_records = skipped
        
        self.save(update_fields=[
            'processed_records',
            'successful_records', 
            'failed_records',
            'skipped_records'
        ])
    
    def complete_sync(self, status='COMPLETED', summary=None):
        """Mark sync as completed"""
        self.status = status
        self.completed_at = timezone.now()
        
        if self.started_at:
            duration = self.completed_at - self.started_at
            self.duration_seconds = duration.total_seconds()
        
        if summary:
            self.sync_summary = summary
        
        self.save()
    
    def add_error(self, error_message, record_data=None, line_number=None):
        """Add an error to the sync log"""
        error_entry = {
            'message': error_message,
            'timestamp': timezone.now().isoformat(),
            'record_data': record_data,
            'line_number': line_number
        }
        
        if not self.error_details:
            self.error_details = []
        
        self.error_details.append(error_entry)
        self.save(update_fields=['error_details'])
    
    def add_warning(self, warning_message, record_data=None, line_number=None):
        """Add a warning to the sync log"""
        warning_entry = {
            'message': warning_message,
            'timestamp': timezone.now().isoformat(),
            'record_data': record_data,
            'line_number': line_number
        }
        
        if not self.warning_details:
            self.warning_details = []
        
        self.warning_details.append(warning_entry)
        self.save(update_fields=['warning_details'])
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_records > 0:
            return (self.processed_records / self.total_records) * 100
        return 0
    
    @property
    def success_rate(self):
        """Calculate success rate"""
        if self.processed_records > 0:
            return (self.successful_records / self.processed_records) * 100
        return 0
    
    @property
    def error_rate(self):
        """Calculate error rate"""
        if self.processed_records > 0:
            return (self.failed_records / self.processed_records) * 100
        return 0