from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from decimal import Decimal
import json
from ..abstract.base import TenantBaseModel, SoftDeleteMixin
from ..abstract.auditable import AuditableMixin

User = get_user_model()

class ReportTemplate(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Template for inventory reports
    """
    REPORT_TYPES = [
        ('STOCK_SUMMARY', 'Stock Summary'),
        ('STOCK_VALUATION', 'Stock Valuation'),
        ('MOVEMENT_HISTORY', 'Movement History'),
        ('ABC_ANALYSIS', 'ABC Analysis'),
        ('AGING_ANALYSIS', 'Aging Analysis'),
        ('REORDER_REPORT', 'Reorder Report'),
        ('DEAD_STOCK', 'Dead Stock Report'),
        ('FAST_SLOW_MOVING', 'Fast/Slow Moving'),
        ('SUPPLIER_PERFORMANCE', 'Supplier Performance'),
        ('PURCHASE_ANALYSIS', 'Purchase Analysis'),
        ('TRANSFER_REPORT', 'Transfer Report'),
        ('ADJUSTMENT_REPORT', 'Adjustment Report'),
        ('CYCLE_COUNT', 'Cycle Count Report'),
        ('RESERVATION_REPORT', 'Reservation Report'),
        ('ALERT_SUMMARY', 'Alert Summary'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    OUTPUT_FORMATS = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('JSON', 'JSON'),
        ('HTML', 'HTML'),
    ]
    
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Report configuration
    query_config = models.JSONField(default=dict, blank=True)  # SQL/ORM query configuration
    filter_config = models.JSONField(default=dict, blank=True)  # Available filters
    column_config = models.JSONField(default=list, blank=True)  # Column definitions
    chart_config = models.JSONField(default=dict, blank=True)  # Chart configurations
    formatting_config = models.JSONField(default=dict, blank=True)  # Formatting rules
    
    # Default settings
    default_filters = models.JSONField(default=dict, blank=True)
    default_sort_by = models.CharField(max_length=50, blank=True)
    default_sort_order = models.CharField(max_length=4, choices=[('ASC', 'Ascending'), ('DESC', 'Descending')], default='ASC')
    default_output_format = models.CharField(max_length=10, choices=OUTPUT_FORMATS, default='PDF')
    
    # Access control
    is_public = models.BooleanField(default=False)
    allowed_users = models.ManyToManyField(User, blank=True)
    allowed_roles = models.JSONField(default=list, blank=True)
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'report_type', 'is_active']),
            models.Index(fields=['is_public', 'is_active']),
            models.Index(fields=['last_used_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"
    
    def can_access(self, user):
        """Check if user can access this template"""
        if self.is_public:
            return True
        if self.created_by == user:
            return True
        if self.allowed_users.filter(id=user.id).exists():
            return True
        # Check roles if implemented
        return False
    
    def mark_used(self):
        """Mark template as used"""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])

class InventoryReport(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Generated inventory reports
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('GENERATING', 'Generating'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Report parameters
    filters_applied = models.JSONField(default=dict, blank=True)
    date_range_from = models.DateTimeField(null=True, blank=True)
    date_range_to = models.DateTimeField(null=True, blank=True)
    output_format = models.CharField(max_length=10, choices=ReportTemplate.OUTPUT_FORMATS)
    
    # Generation details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_duration = models.DurationField(null=True, blank=True)
    
    # Results
    total_records = models.PositiveIntegerField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)  # SHA256 hash
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Access tracking
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    last_downloaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='downloaded_reports'
    )
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"{self.template.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Set default expiry (30 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=30)
        
        super().save(*args, **kwargs)
    
    def start_generation(self):
        """Mark report generation as started"""
        self.status = 'GENERATING'
        self.generation_started_at = timezone.now()
        self.save(update_fields=['status', 'generation_started_at'])
    
    def mark_completed(self, file_path, file_size, total_records, file_hash=None):
        """Mark report as completed"""
        self.status = 'COMPLETED'
        self.generation_completed_at = timezone.now()
        if self.generation_started_at:
            self.generation_duration = self.generation_completed_at - self.generation_started_at
        self.file_path = file_path
        self.file_size_bytes = file_size
        self.total_records = total_records
        if file_hash:
            self.file_hash = file_hash
        self.save(update_fields=[
            'status', 'generation_completed_at', 'generation_duration',
            'file_path', 'file_size_bytes', 'total_records', 'file_hash'
        ])
    
    def mark_failed(self, error_message):
        """Mark report as failed"""
        self.status = 'FAILED'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])
    
    def can_retry(self):
        """Check if report can be retried"""
        return self.status == 'FAILED' and self.retry_count < self.max_retries
    
    def mark_downloaded(self, user):
        """Mark report as downloaded"""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.last_downloaded_by = user
        self.save(update_fields=['download_count', 'last_downloaded_at', 'last_downloaded_by'])
    
    @property
    def is_expired(self):
        """Check if report has expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return 0

class ReportSchedule(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Scheduled report generation
    """
    FREQUENCY_CHOICES = [
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('CUSTOM', 'Custom Cron'),
    ]
    
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='schedules')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Schedule configuration
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    cron_expression = models.CharField(max_length=100, blank=True)  # For custom frequency
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Report parameters
    filters = models.JSONField(default=dict, blank=True)
    output_format = models.CharField(max_length=10, choices=ReportTemplate.OUTPUT_FORMATS)
    
    # Delivery settings
    auto_send_email = models.BooleanField(default=False)
    email_recipients = models.JSONField(default=list, blank=True)
    email_subject = models.CharField(max_length=200, blank=True)
    email_body = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    
    # Limits
    max_runs = models.PositiveIntegerField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'next_run_at']),
            models.Index(fields=['next_run_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def save(self, *args, **kwargs):
        if not self.next_run_at and self.is_active:
            self.calculate_next_run()
        super().save(*args, **kwargs)
    
    def calculate_next_run(self):
        """Calculate next run time based on frequency"""
        now = timezone.now()
        
        if self.frequency == 'HOURLY':
            self.next_run_at = now + timezone.timedelta(hours=1)
        elif self.frequency == 'DAILY':
            self.next_run_at = now + timezone.timedelta(days=1)
        elif self.frequency == 'WEEKLY':
            self.next_run_at = now + timezone.timedelta(weeks=1)
        elif self.frequency == 'MONTHLY':
            self.next_run_at = now + timezone.timedelta(days=30)
        elif self.frequency == 'QUARTERLY':
            self.next_run_at = now + timezone.timedelta(days=90)
        elif self.frequency == 'YEARLY':
            self.next_run_at = now + timezone.timedelta(days=365)
        elif self.frequency == 'CUSTOM' and self.cron_expression:
            # Implement cron parsing logic here
            pass
    
    def should_run(self):
        """Check if schedule should run now"""
        if not self.is_active or not self.next_run_at:
            return False
        
        if self.end_date and timezone.now() > self.end_date:
            return False
        
        if self.max_runs and self.run_count >= self.max_runs:
            return False
        
        return timezone.now() >= self.next_run_at
    
    def mark_run(self, success=True):
        """Mark schedule as run"""
        self.last_run_at = timezone.now()
        self.run_count += 1
        if not success:
            self.failure_count += 1
        self.calculate_next_run()
        self.save(update_fields=['last_run_at', 'run_count', 'failure_count', 'next_run_at'])

class ReportExecution(TenantBaseModel):
    """
    Log of report executions
    """
    schedule = models.ForeignKey(
        ReportSchedule, on_delete=models.CASCADE, null=True, blank=True,
        related_name='executions'
    )
    report = models.OneToOneField(
        InventoryReport, on_delete=models.CASCADE, null=True, blank=True,
        related_name='execution_log'
    )
    
    execution_type = models.CharField(max_length=20, choices=[
        ('MANUAL', 'Manual'),
        ('SCHEDULED', 'Scheduled'),
        ('API', 'API Triggered'),
    ])
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Resource usage
    memory_usage_mb = models.PositiveIntegerField(null=True, blank=True)
    cpu_time_seconds = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['schedule', 'started_at']),
            models.Index(fields=['success', 'started_at']),
        ]
    
    def __str__(self):
        schedule_name = self.schedule.name if self.schedule else 'Manual'
        return f"{schedule_name} execution at {self.started_at}"
    
    def mark_completed(self, success=True, error_message=None):
        """Mark execution as completed"""
        self.completed_at = timezone.now()
        self.duration = self.completed_at - self.started_at
        self.success = success
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['completed_at', 'duration', 'success', 'error_message'])