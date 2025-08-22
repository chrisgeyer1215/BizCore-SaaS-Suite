from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import TenantBaseModel, SoftDeleteMixin
from ..abstract.auditable import AuditableMixin

User = get_user_model()

class AlertRule(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Configurable rules for generating inventory alerts
    """
    ALERT_TYPES = [
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('EXPIRY', 'Expiry Warning'),
        ('SLOW_MOVING', 'Slow Moving'),
        ('DEAD_STOCK', 'Dead Stock'),
        ('REORDER_POINT', 'Reorder Point'),
        ('NEGATIVE_STOCK', 'Negative Stock'),
        ('COST_VARIANCE', 'Cost Variance'),
        ('ABC_CHANGE', 'ABC Classification Change'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    CONDITION_OPERATORS = [
        ('LT', 'Less Than'),
        ('LTE', 'Less Than or Equal'),
        ('GT', 'Greater Than'),
        ('GTE', 'Greater Than or Equal'),
        ('EQ', 'Equal'),
        ('NEQ', 'Not Equal'),
        ('BETWEEN', 'Between'),
        ('IN', 'In List'),
    ]
    
    name = models.CharField(max_length=100)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    description = models.TextField(blank=True)
    
    # Rule conditions
    condition_field = models.CharField(max_length=50)  # e.g., 'quantity_available', 'days_since_last_movement'
    condition_operator = models.CharField(max_length=10, choices=CONDITION_OPERATORS)
    condition_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    condition_value_2 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)  # For BETWEEN operator
    condition_list = models.JSONField(default=list, blank=True)  # For IN operator
    
    # Scope filters
    apply_to_all_products = models.BooleanField(default=True)
    product_categories = models.ManyToManyField('inventory.Category', blank=True)
    specific_products = models.ManyToManyField('inventory.Product', blank=True)
    warehouses = models.ManyToManyField('inventory.Warehouse', blank=True)
    
    # Notification settings
    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=True)
    email_recipients = models.JSONField(default=list, blank=True)
    
    # Frequency settings
    check_frequency_minutes = models.PositiveIntegerField(default=60)  # How often to check
    cooldown_minutes = models.PositiveIntegerField(default=240)  # Min time between same alerts
    
    # Status
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'alert_type', 'is_active']),
            models.Index(fields=['last_checked_at']),
            models.Index(fields=['check_frequency_minutes']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_alert_type_display()})"
    
    def should_check(self):
        """Determine if this rule should be checked now"""
        if not self.is_active:
            return False
        
        if not self.last_checked_at:
            return True
        
        next_check = self.last_checked_at + timezone.timedelta(minutes=self.check_frequency_minutes)
        return timezone.now() >= next_check
    
    def evaluate_condition(self, value):
        """Evaluate if the condition is met for a given value"""
        if self.condition_operator == 'LT':
            return value < self.condition_value
        elif self.condition_operator == 'LTE':
            return value <= self.condition_value
        elif self.condition_operator == 'GT':
            return value > self.condition_value
        elif self.condition_operator == 'GTE':
            return value >= self.condition_value
        elif self.condition_operator == 'EQ':
            return value == self.condition_value
        elif self.condition_operator == 'NEQ':
            return value != self.condition_value
        elif self.condition_operator == 'BETWEEN':
            return self.condition_value <= value <= self.condition_value_2
        elif self.condition_operator == 'IN':
            return str(value) in self.condition_list
        return False
    
    def mark_checked(self):
        """Mark this rule as checked"""
        self.last_checked_at = timezone.now()
        self.save(update_fields=['last_checked_at'])
    
    def mark_triggered(self):
        """Mark this rule as triggered"""
        self.last_triggered_at = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered_at', 'trigger_count'])
    
    def can_trigger_again(self):
        """Check if enough time has passed since last trigger"""
        if not self.last_triggered_at:
            return True
        
        cooldown_end = self.last_triggered_at + timezone.timedelta(minutes=self.cooldown_minutes)
        return timezone.now() >= cooldown_end

class InventoryAlert(TenantBaseModel, AuditableMixin, SoftDeleteMixin):
    """
    Generated inventory alerts
    """
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
        ('AUTO_RESOLVED', 'Auto Resolved'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Alert identification
    alert_rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    reference_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # Related objects
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE, null=True, blank=True)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, null=True, blank=True)
    stock_item = models.ForeignKey('inventory.StockItem', on_delete=models.CASCADE, null=True, blank=True)
    
    # Alert details
    current_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    
    # Resolution tracking
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acknowledged_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_alerts'
    )
    resolution_notes = models.TextField(blank=True)
    
    # Auto-resolution
    auto_resolve_at = models.DateTimeField(null=True, blank=True)
    is_auto_resolvable = models.BooleanField(default=True)
    
    # Notification tracking
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    notification_attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'status', 'priority']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['alert_rule', 'status']),
            models.Index(fields=['product', 'status']),
            models.Index(fields=['warehouse', 'status']),
            models.Index(fields=['auto_resolve_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reference_number}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
        if not self.priority and self.alert_rule:
            self.priority = self.alert_rule.severity
        super().save(*args, **kwargs)
    
    def generate_reference_number(self):
        """Generate unique reference number"""
        from django.utils.crypto import get_random_string
        prefix = 'ALT'
        timestamp = timezone.now().strftime('%Y%m%d')
        random_suffix = get_random_string(4, '0123456789')
        return f"{prefix}-{timestamp}-{random_suffix}"
    
    def acknowledge(self, user, notes=None):
        """Acknowledge the alert"""
        if self.status == 'OPEN':
            self.status = 'ACKNOWLEDGED'
            self.acknowledged_at = timezone.now()
            self.acknowledged_by = user
            if notes:
                self.resolution_notes = notes
            self.save(update_fields=['status', 'acknowledged_at', 'acknowledged_by', 'resolution_notes'])
    
    def resolve(self, user, notes=None):
        """Resolve the alert"""
        if self.status in ['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']:
            self.status = 'RESOLVED'
            self.resolved_at = timezone.now()
            self.resolved_by = user
            if notes:
                self.resolution_notes = notes
            self.save(update_fields=['status', 'resolved_at', 'resolved_by', 'resolution_notes'])
    
    def dismiss(self, user, notes=None):
        """Dismiss the alert"""
        if self.status in ['OPEN', 'ACKNOWLEDGED']:
            self.status = 'DISMISSED'
            self.resolved_at = timezone.now()
            self.resolved_by = user
            if notes:
                self.resolution_notes = notes
            self.save(update_fields=['status', 'resolved_at', 'resolved_by', 'resolution_notes'])
    
    def auto_resolve(self):
        """Auto-resolve the alert"""
        if self.is_auto_resolvable and self.status in ['OPEN', 'ACKNOWLEDGED']:
            self.status = 'AUTO_RESOLVED'
            self.resolved_at = timezone.now()
            self.save(update_fields=['status', 'resolved_at'])
    
    def should_auto_resolve(self):
        """Check if alert should be auto-resolved"""
        if not self.is_auto_resolvable or not self.auto_resolve_at:
            return False
        return timezone.now() >= self.auto_resolve_at
    
    @property
    def age_hours(self):
        """Get alert age in hours"""
        return (timezone.now() - self.created_at).total_seconds() / 3600
    
    @property
    def is_overdue(self):
        """Check if alert is overdue based on priority"""
        age_hours = self.age_hours
        if self.priority == 'CRITICAL':
            return age_hours > 1  # 1 hour
        elif self.priority == 'HIGH':
            return age_hours > 4  # 4 hours
        elif self.priority == 'MEDIUM':
            return age_hours > 24  # 1 day
        return age_hours > 72  # 3 days for low priority

class AlertHistory(TenantBaseModel):
    """
    Historical record of alert state changes
    """
    alert = models.ForeignKey(InventoryAlert, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=50)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['alert', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.alert.reference_number}: {self.action} at {self.timestamp}"