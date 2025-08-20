"""
Inventory alerts and notifications system with intelligent monitoring
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import uuid

from ..abstract.base import TenantBaseModel
from ...managers.base import InventoryManager

User = get_user_model()


class InventoryAlert(TenantBaseModel):
    """
    Comprehensive inventory alerts and notifications system with intelligent monitoring
    """
    
    ALERT_TYPES = [
        # Stock Level Alerts
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('REORDER_POINT', 'Reorder Point Reached'),
        ('SAFETY_STOCK_BREACH', 'Safety Stock Breach'),
        ('MAX_STOCK_EXCEEDED', 'Maximum Stock Exceeded'),
        
        # Expiry & Quality Alerts
        ('EXPIRY_WARNING', 'Expiry Warning'),
        ('EXPIRED_STOCK', 'Expired Stock'),
        ('NEAR_EXPIRY', 'Near Expiry'),
        ('QUALITY_ISSUE', 'Quality Issue'),
        ('BATCH_RECALL', 'Batch Recall'),
        ('QUARANTINE_ALERT', 'Quarantine Alert'),
        
        # Operational Alerts
        ('NEGATIVE_STOCK', 'Negative Stock'),
        ('VARIANCE_ALERT', 'Stock Variance'),
        ('CYCLE_COUNT_DUE', 'Cycle Count Due'),
        ('CYCLE_COUNT_OVERDUE', 'Cycle Count Overdue'),
        ('MOVEMENT_ANOMALY', 'Movement Anomaly'),
        ('LOCATION_CAPACITY', 'Location Capacity Alert'),
        
        # Performance Alerts
        ('SLOW_MOVING', 'Slow Moving Stock'),
        ('DEAD_STOCK', 'Dead Stock'),
        ('FAST_MOVING', 'Fast Moving Stock'),
        ('STOCKOUT_FREQUENCY', 'Frequent Stockouts'),
        ('HIGH_SHRINKAGE', 'High Shrinkage'),
        ('TURNOVER_ALERT', 'Turnover Rate Alert'),
        
        # Order & Fulfillment Alerts
        ('PO_OVERDUE', 'Purchase Order Overdue'),
        ('RECEIPT_OVERDUE', 'Receipt Overdue'),
        ('TRANSFER_OVERDUE', 'Transfer Overdue'),
        ('RESERVATION_EXPIRY', 'Reservation Expiring'),
        ('BACKORDER_ALERT', 'Backorder Alert'),
        ('SUPPLIER_DELAY', 'Supplier Delay'),
        
        # Financial Alerts
        ('PRICE_CHANGE', 'Price Change'),
        ('COST_VARIANCE', 'Cost Variance'),
        ('HIGH_VALUE_MOVEMENT', 'High Value Movement'),
        ('INVENTORY_VALUE_CHANGE', 'Inventory Value Change'),
        ('WRITE_OFF_THRESHOLD', 'Write-off Threshold'),
        ('LANDED_COST_VARIANCE', 'Landed Cost Variance'),
        
        # System & Integration Alerts
        ('SYSTEM_ERROR', 'System Error'),
        ('INTEGRATION_FAILURE', 'Integration Failure'),
        ('DATA_SYNC_ISSUE', 'Data Sync Issue'),
        ('API_LIMIT_REACHED', 'API Limit Reached'),
        ('BACKUP_FAILURE', 'Backup Failure'),
        
        # Compliance & Regulatory
        ('COMPLIANCE_ISSUE', 'Compliance Issue'),
        ('AUDIT_DUE', 'Audit Due'),
        ('CERTIFICATION_EXPIRY', 'Certification Expiry'),
        ('REGULATORY_CHANGE', 'Regulatory Change'),
        
        # Custom & Other
        ('CUSTOM_RULE', 'Custom Rule Triggered'),
        ('THRESHOLD_BREACH', 'Threshold Breach'),
        ('PATTERN_DETECTION', 'Pattern Detection'),
        ('FORECASTING_ALERT', 'Forecasting Alert'),
        ('OTHER', 'Other'),
    ]
    
    ALERT_SEVERITY = [
        ('INFO', 'Information'),
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    ALERT_STATUS = [
        ('ACTIVE', 'Active'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
        ('SNOOZED', 'Snoozed'),
        ('ESCALATED', 'Escalated'),
        ('AUTO_RESOLVED', 'Auto Resolved'),
    ]
    
    ALERT_CHANNELS = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PUSH', 'Push Notification'),
        ('SLACK', 'Slack'),
        ('TEAMS', 'Microsoft Teams'),
        ('WEBHOOK', 'Webhook'),
        ('IN_APP', 'In-App Notification'),
        ('DASHBOARD', 'Dashboard Alert'),
    ]
    
    # Unique Identifiers
    alert_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alert_number = models.CharField(max_length=50, blank=True)
    
    # Alert Classification
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=ALERT_SEVERITY, default='MEDIUM')
    category = models.CharField(max_length=50, blank=True)
    
    # Alert Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    description = models.TextField(blank=True)
    
    # Alert Context & Data
    alert_data = models.JSONField(default=dict, blank=True)
    threshold_data = models.JSONField(default=dict, blank=True)
    current_values = models.JSONField(default=dict, blank=True)
    historical_data = models.JSONField(default=dict, blank=True)
    
    # Source References (Generic Foreign Key for flexibility)
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('content_type', 'object_id')
    
    # Direct References (alternative to generic FK)
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='alerts'
    )
    
    # Additional References
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Status & Workflow
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    
    # Personnel & Assignment
    created_by_system = models.BooleanField(default=True)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acknowledged_alerts'
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_alerts'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_alerts'
    )
    assigned_to_role = models.CharField(max_length=50, blank=True)
    
    # Alert Rule & Configuration
    alert_rule = models.ForeignKey(
        'alerts.AlertRule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_alerts'
    )
    rule_version = models.CharField(max_length=20, blank=True)
    
    # Notification Management
    notification_channels = models.JSONField(default=list, blank=True)
    notification_status = models.JSONField(default=dict, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    notification_frequency_minutes = models.IntegerField(default=0)
    
    # Escalation Management
    escalation_level = models.IntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='escalated_alerts'
    )
    auto_escalate_after_hours = models.IntegerField(default=24)
    
    # Business Impact
    business_impact_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Business impact score (0-100)"
    )
    estimated_financial_impact = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    operational_impact = models.CharField(max_length=20, blank=True)
    
    # Auto-Resolution
    auto_resolve_enabled = models.BooleanField(default=False)
    auto_resolve_conditions = models.JSONField(default=dict, blank=True)
    resolution_actions = models.JSONField(default=list, blank=True)
    
    # Pattern Recognition & Learning
    pattern_signature = models.CharField(max_length=255, blank=True)
    similar_alerts_count = models.IntegerField(default=0)
    recurrence_frequency = models.CharField(max_length=20, blank=True)
    
    # Geolocation (for location-based alerts)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Additional Information
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Integration & External Systems
    external_alert_id = models.CharField(max_length=100, blank=True)
    external_system = models.CharField(max_length=50, blank=True)
    webhook_url = models.URLField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_alerts'
        ordering = ['-created_at', '-severity']
        indexes = [
            models.Index(fields=['tenant_id', 'status', '-created_at']),
            models.Index(fields=['tenant_id', 'alert_type', 'status']),
            models.Index(fields=['tenant_id', 'severity', 'status']),
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
            models.Index(fields=['tenant_id', 'assigned_to', 'status']),
            models.Index(fields=['tenant_id', 'expires_at']),
            models.Index(fields=['tenant_id', 'pattern_signature']),
            models.Index(fields=['alert_id']),  # For API lookups
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.title}"
    
    def clean(self):
        if not self.alert_number:
            # Auto-generate alert number
            today = timezone.now().strftime('%Y%m%d')
            last_alert = InventoryAlert.objects.filter(
                tenant_id=self.tenant_id,
                alert_number__startswith=f'ALT-{today}'
            ).order_by('-alert_number').first()
            
            if last_alert:
                try:
                    last_seq = int(last_alert.alert_number.split('-')[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = 1
            else:
                next_seq = 1
            
            self.alert_number = f"ALT-{today}-{next_seq:06d}"
    
    def acknowledge(self, user, notes=''):
        """Acknowledge the alert"""
        if self.status not in ['ACTIVE', 'ESCALATED']:
            return False, f"Cannot acknowledge alert with status {self.status}"
        
        self.status = 'ACKNOWLEDGED'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        
        if notes:
            self.notes = f"Acknowledged: {notes}\n{self.notes}" if self.notes else f"Acknowledged: {notes}"
        
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at', 'notes'])
        
        # Send acknowledgment notification
        self._send_notification('acknowledged', user)
        
        return True, "Alert acknowledged successfully"
    
    def resolve(self, user, resolution_notes='', auto_resolved=False):
        """Resolve the alert"""
        if self.status in ['RESOLVED', 'DISMISSED']:
            return False, f"Alert already {self.status.lower()}"
        
        self.status = 'AUTO_RESOLVED' if auto_resolved else 'RESOLVED'
        self.resolved_by = user if not auto_resolved else None
        self.resolved_at = timezone.now()
        self.resolution_notes = resolution_notes
        
        self.save(update_fields=[
            'status', 'resolved_by', 'resolved_at', 'resolution_notes'
        ])
        
        # Execute resolution actions if configured
        if self.resolution_actions:
            self._execute_resolution_actions()
        
        # Send resolution notification
        if not auto_resolved:
            self._send_notification('resolved', user)
        
        return True, "Alert resolved successfully"
    
    def snooze(self, until_datetime, user, reason=''):
        """Snooze the alert until specified time"""
        if self.status not in ['ACTIVE', 'ACKNOWLEDGED']:
            return False, f"Cannot snooze alert with status {self.status}"
        
        self.status = 'SNOOZED'
        self.snoozed_until = until_datetime
        
        snooze_note = f"Snoozed until {until_datetime} by {user.get_full_name()}"
        if reason:
            snooze_note += f": {reason}"
        
        self.notes = f"{snooze_note}\n{self.notes}" if self.notes else snooze_note
        
        self.save(update_fields=['status', 'snoozed_until', 'notes'])
        
        return True, f"Alert snoozed until {until_datetime}"
    
    def escalate(self, escalate_to_user, user, reason=''):
        """Escalate the alert to higher level"""
        if self.status in ['RESOLVED', 'DISMISSED']:
            return False, "Cannot escalate resolved/dismissed alert"
        
        self.status = 'ESCALATED'
        self.escalation_level += 1
        self.escalated_at = timezone.now()
        self.escalated_to = escalate_to_user
        self.assigned_to = escalate_to_user
        
        escalation_note = f"Escalated to {escalate_to_user.get_full_name()} by {user.get_full_name()}"
        if reason:
            escalation_note += f": {reason}"
        
        self.notes = f"{escalation_note}\n{self.notes}" if self.notes else escalation_note
        
        self.save(update_fields=[
            'status', 'escalation_level', 'escalated_at', 
            'escalated_to', 'assigned_to', 'notes'
        ])
        
        # Send escalation notification
        self._send_notification('escalated', escalate_to_user)
        
        return True, f"Alert escalated to {escalate_to_user.get_full_name()}"
    
    def dismiss(self, user, reason=''):
        """Dismiss the alert without resolution"""
        if self.status in ['RESOLVED', 'DISMISSED']:
            return False, f"Alert already {self.status.lower()}"
        
        self.status = 'DISMISSED'
        dismiss_note = f"Dismissed by {user.get_full_name()}"
        if reason:
            dismiss_note += f": {reason}"
        
        self.notes = f"{dismiss_note}\n{self.notes}" if self.notes else dismiss_note
        
        self.save(update_fields=['status', 'notes'])
        
        return True, "Alert dismissed"
    
    def check_auto_escalation(self):
        """Check if alert should be auto-escalated"""
        if (self.status in ['ACTIVE', 'ACKNOWLEDGED'] and 
            self.auto_escalate_after_hours > 0 and
            not self.escalated_at):
            
            hours_since_creation = (timezone.now() - self.created_at).total_seconds() / 3600
            
            if hours_since_creation >= self.auto_escalate_after_hours:
                # Find escalation target (would be configurable)
                escalation_target = self._find_escalation_target()
                if escalation_target:
                    return self.escalate(
                        escalation_target, 
                        None, 
                        f"Auto-escalated after {self.auto_escalate_after_hours} hours"
                    )
        
        return False, "No auto-escalation needed"
    
    def check_auto_resolution(self):
        """Check if alert can be auto-resolved"""
        if not self.auto_resolve_enabled or not self.auto_resolve_conditions:
            return False, "Auto-resolution not enabled"
        
        if self.status not in ['ACTIVE', 'ACKNOWLEDGED']:
            return False, "Alert not in resolvable status"
        
        # Check resolution conditions
        conditions_met = self._evaluate_auto_resolve_conditions()
        
        if conditions_met:
            return self.resolve(None, "Auto-resolved based on system conditions", auto_resolved=True)
        
        return False, "Auto-resolution conditions not met"
    
    def check_expiry(self):
        """Check if alert has expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            if self.status not in ['RESOLVED', 'DISMISSED']:
                return self.resolve(None, "Auto-resolved due to expiry", auto_resolved=True)
        
        return False, "Alert not expired"
    
    def check_snooze_expiry(self):
        """Check if snoozed alert should be reactivated"""
        if (self.status == 'SNOOZED' and 
            self.snoozed_until and 
            timezone.now() >= self.snoozed_until):
            
            self.status = 'ACTIVE'
            self.snoozed_until = None
            self.notes = f"Reactivated after snooze period\n{self.notes}" if self.notes else "Reactivated after snooze period"
            
            self.save(update_fields=['status', 'snoozed_until', 'notes'])
            
            return True, "Alert reactivated after snooze"
        
        return False, "Alert not snoozed or snooze not expired"
    
    def send_notification(self, channel='EMAIL', force=False):
        """Send notification through specified channel"""
        if not force and not self._should_send_notification():
            return False, "Notification not due or rate limited"
        
        success = self._send_notification('created', None, channel)
        
        if success:
            self.notification_count += 1
            self.last_notification_sent = timezone.now()
            self._update_notification_status(channel, 'sent')
            
            self.save(update_fields=[
                'notification_count', 'last_notification_sent', 'notification_status'
            ])
        
        return success, "Notification sent" if success else "Notification failed"
    
    def calculate_business_impact(self):
        """Calculate business impact score based on various factors"""
        impact_score = 0
        
        # Severity impact (0-40 points)
        severity_scores = {
            'EMERGENCY': 40,
            'CRITICAL': 35,
            'HIGH': 25,
            'MEDIUM': 15,
            'LOW': 5,
            'INFO': 0,
        }
        impact_score += severity_scores.get(self.severity, 0)
        
        # Financial impact (0-30 points)
        if self.estimated_financial_impact:
            if self.estimated_financial_impact >= 10000:
                impact_score += 30
            elif self.estimated_financial_impact >= 5000:
                impact_score += 20
            elif self.estimated_financial_impact >= 1000:
                impact_score += 10
            else:
                impact_score += 5
        
        # Frequency/Pattern impact (0-20 points)
        if self.similar_alerts_count >= 10:
            impact_score += 20
        elif self.similar_alerts_count >= 5:
            impact_score += 15
        elif self.similar_alerts_count >= 2:
            impact_score += 10
        
        # Time sensitivity (0-10 points)
        if self.alert_type in ['OUT_OF_STOCK', 'EXPIRED_STOCK', 'SYSTEM_ERROR']:
            impact_score += 10
        elif self.alert_type in ['LOW_STOCK', 'EXPIRY_WARNING']:
            impact_score += 5
        
        self.business_impact_score = min(Decimal('100'), Decimal(str(impact_score)))
        self.save(update_fields=['business_impact_score'])
        
        return self.business_impact_score
    
    def _send_notification(self, event_type, user, channel='EMAIL'):
        """Send notification through specified channel"""
        # Implementation would depend on notification service
        # Could integrate with email service, SMS provider, Slack, etc.
        return True  # Placeholder
    
    def _should_send_notification(self):
        """Check if notification should be sent based on frequency rules"""
        if not self.last_notification_sent:
            return True
        
        if self.notification_frequency_minutes == 0:
            return False  # No repeat notifications
        
        time_since_last = (timezone.now() - self.last_notification_sent).total_seconds() / 60
        return time_since_last >= self.notification_frequency_minutes
    
    def _update_notification_status(self, channel, status):
        """Update notification status for specific channel"""
        if not self.notification_status:
            self.notification_status = {}
        
        self.notification_status[channel] = {
            'status': status,
            'timestamp': timezone.now().isoformat(),
            'attempts': self.notification_status.get(channel, {}).get('attempts', 0) + 1
        }
    
    def _find_escalation_target(self):
        """Find appropriate user for escalation"""
        # Business logic to find escalation target
        # Could be based on role, department, on-call schedule, etc.
        return None  # Placeholder
    
    def _evaluate_auto_resolve_conditions(self):
        """Evaluate auto-resolution conditions"""
        # Implementation would evaluate conditions from auto_resolve_conditions JSON
        return False  # Placeholder
    
    def _execute_resolution_actions(self):
        """Execute configured resolution actions"""
        # Implementation would execute actions from resolution_actions JSON
        pass  # Placeholder
    
    @property
    def is_active(self):
        """Check if alert is currently active"""
        if self.status == 'SNOOZED' and self.snoozed_until:
            if timezone.now() >= self.snoozed_until:
                self.check_snooze_expiry()
        
        return self.status == 'ACTIVE'
    
    @property
    def is_overdue(self):
        """Check if alert is overdue for attention"""
        if self.status not in ['ACTIVE', 'ACKNOWLEDGED']:
            return False
        
        # Define overdue thresholds based on severity
        overdue_hours = {
            'EMERGENCY': 1,
            'CRITICAL': 4,
            'HIGH': 8,
            'MEDIUM': 24,
            'LOW': 48,
            'INFO': 96,
        }
        
        threshold = overdue_hours.get(self.severity, 24)
        hours_since_creation = (timezone.now() - self.created_at).total_seconds() / 3600
        
        return hours_since_creation > threshold
    
    @property
    def age_in_hours(self):
        """Age of alert in hours"""
        return int((timezone.now() - self.created_at).total_seconds() / 3600)
    
    @property
    def priority_score(self):
        """Calculate priority score for sorting"""
        base_score = self.business_impact_score or 0
        
        # Add urgency multiplier based on age and severity
        urgency_multiplier = 1
        if self.is_overdue:
            urgency_multiplier = 2
        
        if self.severity in ['EMERGENCY', 'CRITICAL']:
            urgency_multiplier *= 2
        
        return float(base_score) * urgency_multiplier


class AlertRule(TenantBaseModel):
    """
    Configurable alert rules for automated alert generation
    """
    
    RULE_TYPES = [
        ('THRESHOLD', 'Threshold-based'),
        ('PATTERN', 'Pattern Detection'),
        ('ANOMALY', 'Anomaly Detection'),
        ('SCHEDULE', 'Scheduled Check'),
        ('EVENT', 'Event-driven'),
        ('COMPOSITE', 'Composite Rule'),
    ]
    
    EVALUATION_FREQUENCY = [
        ('REAL_TIME', 'Real-time'),
        ('EVERY_MINUTE', 'Every Minute'),
        ('EVERY_5_MINUTES', 'Every 5 Minutes'),
        ('EVERY_15_MINUTES', 'Every 15 Minutes'),
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
    ]
    
    # Basic Information
    rule_name = models.CharField(max_length=200)
    rule_code = models.CharField(max_length=50, blank=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    description = models.TextField(blank=True)
    
    # Rule Configuration
    alert_type = models.CharField(max_length=30, choices=InventoryAlert.ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=InventoryAlert.ALERT_SEVERITY)
    
    # Scope & Filters
    applies_to_warehouses = models.ManyToManyField(
        'warehouse.Warehouse',
        blank=True,
        related_name='alert_rules'
    )
    applies_to_categories = models.ManyToManyField(
        'core.Category',
        blank=True,
        related_name='alert_rules'
    )
    applies_to_products = models.ManyToManyField(
        'catalog.Product',
        blank=True,
        related_name='alert_rules'
    )
    
    # Rule Conditions
    conditions = models.JSONField(default=dict, blank=True)
    thresholds = models.JSONField(default=dict, blank=True)
    
    # Evaluation Settings
    evaluation_frequency = models.CharField(
        max_length=20, 
        choices=EVALUATION_FREQUENCY, 
        default='HOURLY'
    )
    evaluation_window_hours = models.IntegerField(default=24)
    
    # Status & Control
    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    pause_until = models.DateTimeField(null=True, blank=True)
    
    # Notification Configuration
    notification_channels = models.JSONField(default=list, blank=True)
    notification_template = models.TextField(blank=True)
    suppress_duplicates_minutes = models.IntegerField(default=60)
    
    # Assignment & Escalation
    auto_assign_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='auto_assigned_alert_rules'
    )
    auto_assign_to_role = models.CharField(max_length=50, blank=True)
    escalation_rules = models.JSONField(default=dict, blank=True)
    
    # Performance & Statistics
    total_triggers = models.PositiveIntegerField(default=0)
    false_positives = models.PositiveIntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_evaluated = models.DateTimeField(null=True, blank=True)
    average_resolution_time_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    
    # Version Control
    version = models.CharField(max_length=20, default='1.0')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_alert_rules'
    )
    
    # Additional Configuration
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_alert_rules'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'rule_code'], 
                name='unique_tenant_alert_rule_code'
            ),
        ]
        ordering = ['rule_name']
        indexes = [
            models.Index(fields=['tenant_id', 'is_active', 'rule_type']),
            models.Index(fields=['tenant_id', 'alert_type', 'is_active']),
            models.Index(fields=['tenant_id', 'evaluation_frequency']),
            models.Index(fields=['tenant_id', 'last_evaluated']),
        ]
    
    def __str__(self):
        return f"{self.rule_name} ({self.get_rule_type_display()})"
    
    def clean(self):
        if not self.rule_code:
            # Auto-generate rule code
            rule_type_prefix = self.rule_type[:3].upper()
            last_rule = AlertRule.objects.filter(
                tenant_id=self.tenant_id,
                rule_code__startswith=rule_type_prefix
            ).order_by('-rule_code').first()
            
            if last_rule:
                try:
                    last_num = int(last_rule.rule_code.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.rule_code = f"{rule_type_prefix}-{next_num:04d}"
    
    def evaluate_rule(self):
        """Evaluate the alert rule and trigger alerts if conditions met"""
        if not self.is_active or self.is_paused:
            return False, "Rule not active or paused"
        
        if self.pause_until and timezone.now() < self.pause_until:
            return False, "Rule is paused until specified time"
        
        try:
            # Update last evaluated timestamp
            self.last_evaluated = timezone.now()
            
            # Get objects to evaluate based on scope
            objects_to_check = self._get_evaluation_scope()
            
            alerts_created = 0
            for obj in objects_to_check:
                if self._evaluate_conditions(obj):
                    # Check for duplicate suppression
                    if not self._is_duplicate_alert(obj):
                        alert = self._create_alert(obj)
                        if alert:
                            alerts_created += 1
            
            # Update statistics
            if alerts_created > 0:
                self.total_triggers += alerts_created
                self.last_triggered = timezone.now()
            
            self.save(update_fields=[
                'last_evaluated', 'total_triggers', 'last_triggered'
            ])
            
            return True, f"Rule evaluated: {alerts_created} alerts created"
        
        except Exception as e:
            return False, f"Rule evaluation failed: {str(e)}"
    
    def pause_rule(self, duration_hours, reason=''):
        """Pause the rule for specified duration"""
        self.is_paused = True
        self.pause_until = timezone.now() + timedelta(hours=duration_hours)
        
        self.save(update_fields=['is_paused', 'pause_until'])
        
        return True, f"Rule paused for {duration_hours} hours"
    
    def resume_rule(self):
        """Resume a paused rule"""
        self.is_paused = False
        self.pause_until = None
        
        self.save(update_fields=['is_paused', 'pause_until'])
        
        return True, "Rule resumed"
    
    def _get_evaluation_scope(self):
        """Get objects to evaluate based on rule scope"""
        # Implementation would depend on rule type and scope configuration
        # Return list of objects to evaluate
        return []  # Placeholder
    
    def _evaluate_conditions(self, obj):
        """Evaluate rule conditions against object"""
        # Implementation would evaluate conditions from conditions JSON
        return False  # Placeholder
    
    def _is_duplicate_alert(self, obj):
        """Check if similar alert already exists within suppression window"""
        if self.suppress_duplicates_minutes == 0:
            return False
        
        suppress_window = timezone.now() - timedelta(minutes=self.suppress_duplicates_minutes)
        
        # Check for similar alerts in suppression window
        similar_alerts = InventoryAlert.objects.filter(
            tenant_id=self.tenant_id,
            alert_rule=self,
            created_at__gte=suppress_window,
            status__in=['ACTIVE', 'ACKNOWLEDGED', 'IN_PROGRESS']
        )
        
        # Add object-specific filters based on the type of object
        return similar_alerts.exists()
    
    def _create_alert(self, obj):
        """Create alert for the object"""
        alert_data = self._build_alert_data(obj)
        
        alert = InventoryAlert.objects.create(
            tenant_id=self.tenant_id,
            alert_type=self.alert_type,
            severity=self.severity,
            title=alert_data['title'],
            message=alert_data['message'],
            alert_data=alert_data,
            alert_rule=self,
            rule_version=self.version,
            assigned_to=self.auto_assign_to,
            assigned_to_role=self.auto_assign_to_role,
            notification_channels=self.notification_channels,
            **alert_data['object_references']
        )
        
        # Send notifications if configured
        if self.notification_channels:
            for channel in self.notification_channels:
                alert.send_notification(channel)
        
        return alert
    
    def _build_alert_data(self, obj):
        """Build alert data from object and rule configuration"""
        # Implementation would build alert data based on object type and rule
        return {
            'title': f"Alert: {self.rule_name}",
            'message': f"Rule {self.rule_name} triggered",
            'object_references': {},
        }  # Placeholder
    
    @property
    def effectiveness_score(self):
        """Calculate rule effectiveness score"""
        if self.total_triggers == 0:
            return 0
        
        # Calculate based on false positive rate and resolution time
        false_positive_rate = self.false_positives / self.total_triggers
        effectiveness = (1 - false_positive_rate) * 100
        
        return max(0, min(100, effectiveness))
    
    @property
    def should_evaluate(self):
        """Check if rule should be evaluated now"""
        if not self.is_active or self.is_paused:
            return False
        
        if not self.last_evaluated:
            return True
        
        # Calculate next evaluation time based on frequency
        frequency_minutes = {
            'REAL_TIME': 0,  # Evaluated on events
            'EVERY_MINUTE': 1,
            'EVERY_5_MINUTES': 5,
            'EVERY_15_MINUTES': 15,
            'HOURLY': 60,
            'DAILY': 1440,
            'WEEKLY': 10080,
        }
        
        minutes_since_last = (timezone.now() - self.last_evaluated).total_seconds() / 60
        required_minutes = frequency_minutes.get(self.evaluation_frequency, 60)
        
        return minutes_since_last >= required_minutes


class AlertSubscription(TenantBaseModel):
    """
    User subscriptions to specific types of alerts
    """
    
    user = models.ForeignKey(