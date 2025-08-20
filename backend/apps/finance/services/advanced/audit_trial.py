# apps/finance/services/advanced/audit_trail.py

"""
Comprehensive Audit Trail Service
Provides complete audit logging and change tracking for financial data
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from typing import Dict, List, Optional, Any, Union
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from apps.core.models import TenantBaseModel

User = get_user_model()


class AuditEvent(TenantBaseModel):
    """Individual audit event record"""
    
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'), 
        ('DELETE', 'Deleted'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
        ('POST', 'Posted'),
        ('REVERSE', 'Reversed'),
        ('SEND', 'Sent'),
        ('RECEIVE', 'Received'),
        ('RECONCILE', 'Reconciled'),
        ('CLOSE', 'Closed'),
        ('REOPEN', 'Reopened'),
        ('EXPORT', 'Exported'),
        ('IMPORT', 'Imported'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'Viewed'),
        ('DOWNLOAD', 'Downloaded'),
        ('PRINT', 'Printed'),
        ('EMAIL', 'Emailed'),
        ('BACKUP', 'Backed Up'),
        ('RESTORE', 'Restored'),
        ('PURGE', 'Purged'),
        ('CALCULATE', 'Calculated'),
        ('SYNC', 'Synchronized'),
        ('CONFIGURE', 'Configured'),
        ('BULK_UPDATE', 'Bulk Updated'),
        ('BULK_DELETE', 'Bulk Deleted'),
        ('SYSTEM', 'System Action'),
        ('ERROR', 'Error Occurred'),
        ('WARNING', 'Warning Generated')
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical')
    ]
    
    # Event Identification
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Event Details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='NORMAL')
    event_timestamp = models.DateTimeField(auto_now_add=True)
    
    # User & Session Info
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_events'
    )
    user_email = models.EmailField(blank=True)
    user_full_name = models.CharField(max_length=200, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Object Information
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    
    # Event Description
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    # Change Tracking
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    
    # Financial Impact
    financial_impact = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monetary impact of this action"
    )
    currency_code = models.CharField(max_length=3, blank=True)
    
    # Business Context
    business_process = models.CharField(max_length=100, blank=True)
    workflow_step = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Compliance & Risk
    compliance_flag = models.BooleanField(default=False)
    risk_level = models.CharField(
        max_length=10,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
        default='LOW'
    )
    requires_review = models.BooleanField(default=False)
    
    # Integration Info
    source_system = models.CharField(max_length=100, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    api_endpoint = models.CharField(max_length=200, blank=True)
    
    # Status
    is_processed = models.BooleanField(default=True)
    processing_error = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-event_timestamp']
        indexes = [
            models.Index(fields=['tenant', 'action_type', 'event_timestamp']),
            models.Index(fields=['tenant', 'user', 'event_timestamp']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'business_process']),
            models.Index(fields=['tenant', 'compliance_flag']),
            models.Index(fields=['tenant', 'risk_level']),
        ]
        
    def __str__(self):
        return f"{self.action_type} - {self.description} ({self.event_timestamp})"


class AuditTrailService:
    """Service for managing audit trails and change tracking"""
    
    def __init__(self, tenant, user=None, request=None):
        self.tenant = tenant
        self.user = user
        self.request = request
        
        # Extract request information if available
        self.ip_address = None
        self.user_agent = None
        self.session_key = None
        
        if request:
            self.ip_address = self._get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
            self.session_key = request.session.session_key
    
    # =====================================================================
    # AUDIT EVENT CREATION
    # =====================================================================
    
    def log_event(
        self,
        action_type: str,
        description: str,
        obj: models.Model = None,
        old_values: Dict = None,
        new_values: Dict = None,
        financial_impact: Decimal = None,
        currency_code: str = None,
        business_process: str = None,
        workflow_step: str = None,
        reference_number: str = None,
        severity: str = 'NORMAL',
        compliance_flag: bool = False,
        risk_level: str = 'LOW',
        details: Dict = None,
        source_system: str = None,
        external_reference: str = None
    ) -> AuditEvent:
        """Create a comprehensive audit log entry"""
        
        # Prepare object information
        content_type = None
        object_id = None
        object_repr = ""
        
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = obj.pk
            object_repr = str(obj)
        
        # Determine changed fields
        changed_fields = []
        if old_values and new_values:
            changed_fields = [
                field for field in new_values.keys()
                if field in old_values and old_values[field] != new_values[field]
            ]
        
        # User information
        user_email = ""
        user_full_name = ""
        if self.user:
            user_email = self.user.email
            user_full_name = self.user.get_full_name() or self.user.username
        
        # Create audit event
        audit_event = AuditEvent.objects.create(
            tenant=self.tenant,
            action_type=action_type,
            severity=severity,
            user=self.user,
            user_email=user_email,
            user_full_name=user_full_name,
            session_key=self.session_key,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            details=details or {},
            old_values=self._sanitize_values(old_values or {}),
            new_values=self._sanitize_values(new_values or {}),
            changed_fields=changed_fields,
            financial_impact=financial_impact,
            currency_code=currency_code,
            business_process=business_process,
            workflow_step=workflow_step,
            reference_number=reference_number,
            compliance_flag=compliance_flag,
            risk_level=risk_level,
            source_system=source_system,
            external_reference=external_reference,
            api_endpoint=self._get_api_endpoint() if self.request else None
        )
        
        # Process compliance and risk flags
        self._process_compliance_flags(audit_event)
        
        return audit_event
    
    def log_model_change(
        self,
        action_type: str,
        obj: models.Model,
        old_instance: models.Model = None,
        business_process: str = None,
        financial_impact: Decimal = None
    ) -> AuditEvent:
        """Log changes to a model instance with automatic field comparison"""
        
        old_values = {}
        new_values = {}
        
        if old_instance:
            old_values = self._model_to_dict(old_instance)
        
        if action_type != 'DELETE':
            new_values = self._model_to_dict(obj)
        
        # Calculate financial impact if not provided
        if not financial_impact:
            financial_impact = self._calculate_financial_impact(
                obj, action_type, old_values, new_values
            )
        
        description = self._generate_change_description(
            action_type, obj, old_values, new_values
        )
        
        return self.log_event(
            action_type=action_type,
            description=description,
            obj=obj,
            old_values=old_values,
            new_values=new_values,
            financial_impact=financial_impact,
            business_process=business_process,
            reference_number=getattr(obj, 'number', None) or 
                           getattr(obj, 'invoice_number', None) or
                           getattr(obj, 'bill_number', None) or
                           getattr(obj, 'payment_number', None) or
                           getattr(obj, 'entry_number', None)
        )
    
    def log_bulk_operation(
        self,
        action_type: str,
        model_class: type,
        affected_count: int,
        filter_criteria: Dict,
        business_process: str = None,
        financial_impact: Decimal = None
    ) -> AuditEvent:
        """Log bulk operations on multiple records"""
        
        description = f"Bulk {action_type.lower()} operation on {affected_count} {model_class.__name__} records"
        
        details = {
            'model': model_class.__name__,
            'affected_count': affected_count,
            'filter_criteria': filter_criteria
        }
        
        return self.log_event(
            action_type=f'BULK_{action_type}',
            description=description,
            financial_impact=financial_impact,
            business_process=business_process,
            details=details,
            severity='HIGH' if affected_count > 100 else 'NORMAL'
        )
    
    def log_financial_transaction(
        self,
        action_type: str,
        transaction_obj: models.Model,
        amount: Decimal,
        currency_code: str,
        business_process: str,
        workflow_step: str = None
    ) -> AuditEvent:
        """Log financial transactions with enhanced tracking"""
        
        # Determine risk level based on amount
        risk_level = 'LOW'
        if amount > Decimal('10000'):
            risk_level = 'HIGH'
        elif amount > Decimal('1000'):
            risk_level = 'MEDIUM'
        
        # Check for compliance requirements
        compliance_flag = amount > Decimal('10000')  # Example threshold
        
        description = f"{action_type} financial transaction: {amount} {currency_code}"
        
        return self.log_event(
            action_type=action_type,
            description=description,
            obj=transaction_obj,
            financial_impact=amount,
            currency_code=currency_code,
            business_process=business_process,
            workflow_step=workflow_step,
            compliance_flag=compliance_flag,
            risk_level=risk_level,
            severity='HIGH' if compliance_flag else 'NORMAL'
        )
    
    def log_user_activity(
        self,
        action_type: str,
        description: str,
        details: Dict = None
    ) -> AuditEvent:
        """Log user activity events"""
        
        return self.log_event(
            action_type=action_type,
            description=description,
            details=details,
            business_process='USER_ACTIVITY'
        )
    
    def log_system_event(
        self,
        action_type: str,
        description: str,
        details: Dict = None,
        severity: str = 'NORMAL',
        source_system: str = None
    ) -> AuditEvent:
        """Log system-generated events"""
        
        return self.log_event(
            action_type=action_type,
            description=description,
            details=details,
            severity=severity,
            business_process='SYSTEM_PROCESS',
            source_system=source_system
        )
    
    def log_integration_event(
        self,
        action_type: str,
        description: str,
        source_system: str,
        external_reference: str = None,
        details: Dict = None,
        success: bool = True
    ) -> AuditEvent:
        """Log integration and API events"""
        
        severity = 'NORMAL' if success else 'HIGH'
        
        return self.log_event(
            action_type=action_type,
            description=description,
            details=details,
            severity=severity,
            business_process='INTEGRATION',
            source_system=source_system,
            external_reference=external_reference
        )
    
    # =====================================================================
    # AUDIT TRAIL QUERIES
    # =====================================================================
    
    def get_object_audit_trail(
        self,
        obj: models.Model,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get complete audit trail for a specific object"""
        
        content_type = ContentType.objects.get_for_model(obj)
        
        return AuditEvent.objects.filter(
            tenant=self.tenant,
            content_type=content_type,
            object_id=obj.pk
        ).order_by('-event_timestamp')[:limit]
    
    def get_user_audit_trail(
        self,
        user: User,
        start_date: date = None,
        end_date: date = None,
        action_types: List[str] = None
    ) -> List[AuditEvent]:
        """Get audit trail for a specific user"""
        
        queryset = AuditEvent.objects.filter(
            tenant=self.tenant,
            user=user
        )
        
        if start_date:
            queryset = queryset.filter(event_timestamp__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(event_timestamp__date__lte=end_date)
        
        if action_types:
            queryset = queryset.filter(action_type__in=action_types)
        
        return queryset.order_by('-event_timestamp')
    
    def get_financial_audit_trail(
        self,
        start_date: date = None,
        end_date: date = None,
        min_amount: Decimal = None,
        compliance_only: bool = False
    ) -> List[AuditEvent]:
        """Get audit trail for financial transactions"""
        
        queryset = AuditEvent.objects.filter(
            tenant=self.tenant,
            financial_impact__isnull=False
        )
        
        if start_date:
            queryset = queryset.filter(event_timestamp__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(event_timestamp__date__lte=end_date)
        
        if min_amount:
            queryset = queryset.filter(financial_impact__gte=min_amount)
        
        if compliance_only:
            queryset = queryset.filter(compliance_flag=True)
        
        return queryset.order_by('-event_timestamp')
    
    def get_compliance_audit_trail(
        self,
        start_date: date = None,
        end_date: date = None,
        risk_levels: List[str] = None
    ) -> List[AuditEvent]:
        """Get compliance-related audit events"""
        
        queryset = AuditEvent.objects.filter(
            tenant=self.tenant,
            compliance_flag=True
        )
        
        if start_date:
            queryset = queryset.filter(event_timestamp__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(event_timestamp__date__lte=end_date)
        
        if risk_levels:
            queryset = queryset.filter(risk_level__in=risk_levels)
        
        return queryset.order_by('-event_timestamp')
    
    def get_business_process_audit_trail(
        self,
        business_process: str,
        start_date: date = None,
        end_date: date = None
    ) -> List[AuditEvent]:
        """Get audit trail for a specific business process"""
        
        queryset = AuditEvent.objects.filter(
            tenant=self.tenant,
            business_process=business_process
        )
        
        if start_date:
            queryset = queryset.filter(event_timestamp__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(event_timestamp__date__lte=end_date)
        
        return queryset.order_by('-event_timestamp')
    
    # =====================================================================
    # AUDIT ANALYTICS & REPORTING
    # =====================================================================
    
    def generate_audit_summary(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate comprehensive audit summary report"""
        
        queryset = AuditEvent.objects.filter(
            tenant=self.tenant,
            event_timestamp__date__range=[start_date, end_date]
        )
        
        # Activity summary
        activity_summary = queryset.values('action_type').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        # User activity
        user_activity = queryset.values(
            'user__username', 'user__email'
        ).annotate(
            event_count=models.Count('id')
        ).order_by('-event_count')
        
        # Financial impact summary
        financial_summary = queryset.filter(
            financial_impact__isnull=False
        ).aggregate(
            total_impact=models.Sum('financial_impact'),
            max_impact=models.Max('financial_impact'),
            avg_impact=models.Avg('financial_impact'),
            transaction_count=models.Count('id')
        )
        
        # Compliance events
        compliance_events = queryset.filter(compliance_flag=True).count()
        
        # Risk distribution
        risk_distribution = queryset.values('risk_level').annotate(
            count=models.Count('id')
        )
        
        # Business process activity
        process_activity = queryset.filter(
            business_process__isnull=False
        ).values('business_process').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        # Error events
        error_events = queryset.filter(
            action_type='ERROR'
        ).values('description').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_events': queryset.count()
            },
            'activity_summary': list(activity_summary),
            'user_activity': list(user_activity),
            'financial_summary': financial_summary,
            'compliance_events': compliance_events,
            'risk_distribution': list(risk_distribution),
            'process_activity': list(process_activity),
            'error_events': list(error_events),
            'generated_at': timezone.now()
        }
    
    def detect_suspicious_activity(
        self,
        start_date: date = None,
        end_date: date = None
    ) -> List[Dict[str, Any]]:
        """Detect potentially suspicious activity patterns"""
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        suspicious_patterns = []
        
        # High-value transactions outside business hours
        after_hours_transactions = AuditEvent.objects.filter(
            tenant=self.tenant,
            event_timestamp__date__range=[start_date, end_date],
            financial_impact__gt=Decimal('10000'),
            event_timestamp__time__lt='08:00'
        ) | AuditEvent.objects.filter(
            tenant=self.tenant,
            event_timestamp__date__range=[start_date, end_date],
            financial_impact__gt=Decimal('10000'),
            event_timestamp__time__gt='18:00'
        )
        
        for event in after_hours_transactions:
            suspicious_patterns.append({
                'type': 'AFTER_HOURS_TRANSACTION',
                'event_id': event.event_id,
                'description': f"High-value transaction outside business hours: {event.financial_impact}",
                'severity': 'HIGH',
                'event': event
            })
        
        # Multiple failed login attempts
        failed_logins = AuditEvent.objects.filter(
            tenant=self.tenant,
            event_timestamp__date__range=[start_date, end_date],
            action_type='ERROR',
            description__icontains='login'
        ).values('user', 'ip_address').annotate(
            attempt_count=models.Count('id')
        ).filter(attempt_count__gte=5)
        
        for login_data in failed_logins:
            suspicious_patterns.append({
                'type': 'MULTIPLE_FAILED_LOGINS',
                'description': f"Multiple failed login attempts: {login_data['attempt_count']}",
                'severity': 'MEDIUM',
                'user_id': login_data['user'],
                'ip_address': login_data['ip_address']
            })
        
        # Bulk operations on financial data
        bulk_operations = AuditEvent.objects.filter(
            tenant=self.tenant,
            event_timestamp__date__range=[start_date, end_date],
            action_type__startswith='BULK_',
            financial_impact__gt=Decimal('50000')
        )
        
        for event in bulk_operations:
            suspicious_patterns.append({
                'type': 'LARGE_BULK_OPERATION',
                'event_id': event.event_id,
                'description': f"Large bulk financial operation: {event.financial_impact}",
                'severity': 'HIGH',
                'event': event
            })
        
        return suspicious_patterns
    
    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    
    def _get_client_ip(self, request) -> str:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_api_endpoint(self) -> str:
        """Get API endpoint from request"""
        if not self.request:
            return ""
        
        return f"{self.request.method} {self.request.path}"
    
    def _sanitize_values(self, values: Dict) -> Dict:
        """Sanitize sensitive values for audit logging"""
        sanitized = {}
        
        sensitive_fields = [
            'password', 'token', 'key', 'secret', 'credit_card', 
            'ssn', 'bank_account', 'routing_number'
        ]
        
        for key, value in values.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = '***REDACTED***'
            else:
                # Convert Decimal and other types to JSON-serializable format
                if isinstance(value, Decimal):
                    sanitized[key] = float(value)
                elif isinstance(value, (date, datetime)):
                    sanitized[key] = value.isoformat()
                else:
                    sanitized[key] = value
        
        return sanitized
    
    def _model_to_dict(self, instance: models.Model) -> Dict:
        """Convert model instance to dictionary"""
        data = {}
        
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if isinstance(value, Decimal):
                data[field.name] = float(value)
            elif isinstance(value, (date, datetime)):
                data[field.name] = value.isoformat() if value else None
            else:
                data[field.name] = value
        
        return data
    
    def _calculate_financial_impact(
        self,
        obj: models.Model,
        action_type: str,
        old_values: Dict,
        new_values: Dict
    ) -> Optional[Decimal]:
        """Calculate financial impact of a change"""
        
        # Define financial fields by model type
        financial_fields = {
            'Invoice': ['total_amount', 'base_currency_total'],
            'Bill': ['total_amount', 'base_currency_total'],
            'Payment': ['amount', 'base_currency_amount'],
            'JournalEntry': ['total_debit', 'total_credit']
        }
        
        model_name = obj.__class__.__name__
        if model_name not in financial_fields:
            return None
        
        fields = financial_fields[model_name]
        
        for field in fields:
            if field in new_values:
                if action_type == 'CREATE':
                    return Decimal(str(new_values[field]))
                elif action_type == 'UPDATE' and field in old_values:
                    old_val = Decimal(str(old_values[field]))
                    new_val = Decimal(str(new_values[field]))
                    return abs(new_val - old_val)
                elif action_type == 'DELETE' and field in old_values:
                    return Decimal(str(old_values[field]))
        
        return None
    
    def _generate_change_description(
        self,
        action_type: str,
        obj: models.Model,
        old_values: Dict,
        new_values: Dict
    ) -> str:
        """Generate human-readable change description"""
        
        model_name = obj.__class__.__name__
        
        if action_type == 'CREATE':
            return f"Created {model_name}: {str(obj)}"
        elif action_type == 'DELETE':
            return f"Deleted {model_name}: {str(obj)}"
        elif action_type == 'UPDATE':
            changed_fields = [
                field for field in new_values.keys()
                if field in old_values and old_values[field] != new_values[field]
            ]
            
            if changed_fields:
                return f"Updated {model_name} {str(obj)} - Changed: {', '.join(changed_fields)}"
            else:
                return f"Updated {model_name}: {str(obj)}"
        else:
            return f"{action_type} {model_name}: {str(obj)}"
    
    def _process_compliance_flags(self, audit_event: AuditEvent):
        """Process compliance and risk assessment for audit events"""
        
        # Additional compliance processing can be added here
        # For example, flagging events that require management review
        
        if audit_event.financial_impact and audit_event.financial_impact > Decimal('25000'):
            audit_event.requires_review = True
            audit_event.save(update_fields=['requires_review'])


# Context manager for automatic audit logging
class AuditContext:
    """Context manager for automatic audit logging of model changes"""
    
    def __init__(self, audit_service: AuditTrailService, business_process: str = None):
        self.audit_service = audit_service
        self.business_process = business_process
        self.original_states = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Log error if exception occurred
            self.audit_service.log_event(
                action_type='ERROR',
                description=f"Error in {self.business_process}: {str(exc_val)}",
                business_process=self.business_process,
                severity='HIGH',
                details={'error_type': exc_type.__name__, 'error_message': str(exc_val)}
            )
    
    def track_model(self, instance: models.Model):
        """Track a model instance for changes"""
        self.original_states[instance.pk] = self.audit_service._model_to_dict(instance)
    
    def log_changes(self, instance: models.Model, action_type: str = 'UPDATE'):
        """Log changes to tracked model"""
        original_state = self.original_states.get(instance.pk, {})
        current_state = self.audit_service._model_to_dict(instance)
        
        self.audit_service.log_model_change(
            action_type=action_type,
            obj=instance,
            old_instance=None,  # We have the dict instead
            business_process=self.business_process
        )