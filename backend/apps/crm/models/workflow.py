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

