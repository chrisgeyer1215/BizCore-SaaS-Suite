from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from ..models import (
    InventoryAlert, AlertRule, AlertHistory, StockItem,
    StockMovement, PurchaseOrder, StockTransfer
)
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, NotificationSignalMixin,
    IntegrationSignalMixin, CacheInvalidationMixin
)

logger = logging.getLogger(__name__)

@receiver(post_save, sender=InventoryAlert)
@BaseSignalHandler.safe_signal_execution
def alert_post_save(sender, instance, created, **kwargs):
    """Handle alert creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('alert_created', sender.__name__, instance.id)
        
        # Generate reference number if not set
        if not instance.reference_number:
            instance.reference_number = instance.generate_reference_number()
            sender.objects.filter(pk=instance.pk).update(
                reference_number=instance.reference_number
            )
        
        # Set auto-resolve date for auto-resolvable alerts
        if instance.is_auto_resolvable and not instance.auto_resolve_at:
            auto_resolve_hours = _get_auto_resolve_hours(instance.alert_rule.alert_type)
            if auto_resolve_hours:
                instance.auto_resolve_at = timezone.now() + timezone.timedelta(hours=auto_resolve_hours)
                sender.objects.filter(pk=instance.pk).update(
                    auto_resolve_at=instance.auto_resolve_at
                )
        
        # Send notifications based on alert priority and type
        _send_alert_notifications.delay(instance.id)
        
        # Update alert rule trigger count
        if instance.alert_rule:
            instance.alert_rule.mark_triggered()
        
        # Queue dashboard updates
        _update_alert_dashboard_metrics.delay(instance.tenant_id)
        
        # Create initial alert history
        AlertHistory.objects.create(
            tenant=instance.tenant,
            alert=instance,
            action='CREATED',
            old_status='',
            new_status=instance.status,
            notes='Alert created by system',
            timestamp=timezone.now()
        )
    
    else:
        # Handle status changes
        if hasattr(instance, '_original_status'):
            if instance._original_status != instance.status:
                _handle_alert_status_change.delay(instance.id, instance._original_status, instance.status)

@receiver(pre_save, sender=InventoryAlert)
@BaseSignalHandler.safe_signal_execution
def alert_pre_save(sender, instance, **kwargs):
    """Handle alert pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Store original status for comparison
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except sender.DoesNotExist:
            pass
    
    # Set priority based on alert rule if not set
    if not instance.priority and instance.alert_rule:
        instance.priority = instance.alert_rule.severity
    
    # Validate alert data
    if instance.status == 'RESOLVED' and not instance.resolved_at:
        instance.resolved_at = timezone.now()
    
    if instance.status == 'ACKNOWLEDGED' and not instance.acknowledged_at:
        instance.acknowledged_at = timezone.now()

@receiver(post_save, sender=AlertRule)
@BaseSignalHandler.safe_signal_execution
def alert_rule_post_save(sender, instance, created, **kwargs):
    """Handle alert rule changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('alert_rule_created', sender.__name__, instance.id)
        
        # Queue initial rule evaluation if active
        if instance.is_active:
            _evaluate_alert_rule.delay(instance.id)
    else:
        # Handle rule updates
        if instance.pk:
            _handle_alert_rule_updates.delay(instance.id)
    
    # Invalidate alert cache
    CacheInvalidationMixin.invalidate_related_cache(
        instance, 
        [f"alert_rules_tenant_{instance.tenant_id}"]
    )

@receiver(pre_delete, sender=AlertRule)
@BaseSignalHandler.safe_signal_execution
def alert_rule_pre_delete(sender, instance, **kwargs):
    """Handle alert rule deletion"""
    # Check if there are open alerts for this rule
    open_alerts = InventoryAlert.objects.filter(
        alert_rule=instance,
        status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']
    )
    
    if open_alerts.exists():
        # Auto-resolve open alerts when rule is deleted
        for alert in open_alerts:
            alert.status = 'AUTO_RESOLVED'
            alert.resolved_at = timezone.now()
            alert.resolution_notes = f"Auto-resolved due to alert rule deletion"
            alert.save()
            
            # Create history record
            AlertHistory.objects.create(
                tenant=alert.tenant,
                alert=alert,
                action='AUTO_RESOLVED',
                old_status='OPEN',
                new_status='AUTO_RESOLVED',
                notes='Alert rule was deleted',
                timestamp=timezone.now()
            )

# Integration with other models to trigger alerts
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def check_stock_alerts_on_stock_change(sender, instance, created, **kwargs):
    """Check for stock-related alerts when stock changes"""
    if kwargs.get('raw', False):
        return
    
    # Queue alert checks for this stock item
    _check_stock_item_alerts.delay(instance.id)

@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def check_movement_alerts(sender, instance, created, **kwargs):
    """Check for movement-related alerts"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'COMPLETED':
        # Check for unusual movement patterns
        _check_movement_pattern_alerts.delay(instance.id)
        
        # Check cost variance alerts
        if instance.movement_type in ['RECEIPT', 'ADJUSTMENT_POSITIVE']:
            _check_cost_variance_alerts.delay(instance.id)

@receiver(post_save, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def check_po_alerts(sender, instance, created, **kwargs):
    """Check for purchase order related alerts"""
    if kwargs.get('raw', False):
        return
    
    # Check for overdue POs
    if instance.expected_delivery_date and instance.expected_delivery_date < timezone.now().date():
        _create_overdue_po_alert.delay(instance.id)
    
    # Check for budget variance alerts
    if instance.total_amount and instance.estimated_amount:
        variance_percentage = abs(instance.total_amount - instance.estimated_amount) / instance.estimated_amount * 100
        if variance_percentage > 10:  # Configurable threshold
            _create_budget_variance_alert.delay(instance.id, variance_percentage)

# Automatic alert resolution
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def auto_resolve_stock_alerts(sender, instance, created, **kwargs):
    """Auto-resolve stock alerts when conditions improve"""
    if kwargs.get('raw', False) or created:
        return
    
    # Auto-resolve out of stock alerts if stock is available
    if instance.quantity_on_hand > 0:
        _auto_resolve_alerts.delay(instance.id, 'OUT_OF_STOCK')
    
    # Auto-resolve low stock alerts if above reorder level
    if instance.quantity_on_hand > instance.reorder_level and instance.reorder_level > 0:
        _auto_resolve_alerts.delay(instance.id, 'LOW_STOCK')
    
    # Auto-resolve overstock alerts if below maximum level
    if (instance.maximum_stock_level > 0 and 
        instance.quantity_on_hand < instance.maximum_stock_level):
        _auto_resolve_alerts.delay(instance.id, 'OVERSTOCK')

# Alert escalation
@receiver(post_save, sender=InventoryAlert)
@BaseSignalHandler.safe_signal_execution
def handle_alert_escalation(sender, instance, created, **kwargs):
    """Handle alert escalation based on age and priority"""
    if kwargs.get('raw', False) or created:
        return
    
    # Check if alert needs escalation
    if instance.status in ['OPEN', 'ACKNOWLEDGED'] and instance.is_overdue:
        _escalate_alert.delay(instance.id)

# Performance monitoring for alerts
@receiver(post_save, sender=InventoryAlert)
@BaseSignalHandler.safe_signal_execution
def monitor_alert_performance(sender, instance, created, **kwargs):
    """Monitor alert system performance"""
    if kwargs.get('raw', False):
        return
    
    # Track alert response times and patterns
    _track_alert_metrics.delay(instance.tenant_id, instance.id)

# Async task functions
def _get_auto_resolve_hours(alert_type):
    """Get auto-resolve hours based on alert type"""
    auto_resolve_hours = {
        'LOW_STOCK': 24,
        'OUT_OF_STOCK': 48,
        'OVERSTOCK': 72,
        'EXPIRY': 168,  # 1 week
        'SLOW_MOVING': 168,
        'DEAD_STOCK': 168,
        'COST_VARIANCE': 48,
    }
    return auto_resolve_hours.get(alert_type)

try:
    from ..tasks.celery import (
        send_alert_notifications, update_alert_dashboard_metrics,
        handle_alert_status_change, evaluate_alert_rule,
        handle_alert_rule_updates, check_stock_item_alerts,
        check_movement_pattern_alerts, check_cost_variance_alerts,
        create_overdue_po_alert, create_budget_variance_alert,
        auto_resolve_alerts, escalate_alert, track_alert_metrics
    )
    
    # Make tasks available with delay method
    _send_alert_notifications = send_alert_notifications
    _update_alert_dashboard_metrics = update_alert_dashboard_metrics
    _handle_alert_status_change = handle_alert_status_change
    _evaluate_alert_rule = evaluate_alert_rule
    _handle_alert_rule_updates = handle_alert_rule_updates
    _check_stock_item_alerts = check_stock_item_alerts
    _check_movement_pattern_alerts = check_movement_pattern_alerts
    _check_cost_variance_alerts = check_cost_variance_alerts
    _create_overdue_po_alert = create_overdue_po_alert
    _create_budget_variance_alert = create_budget_variance_alert
    _auto_resolve_alerts = auto_resolve_alerts
    _escalate_alert = escalate_alert
    _track_alert_metrics = track_alert_metrics

except ImportError:
    # Fallback functions for synchronous execution
    logger.warning("Celery not available for alerts, using synchronous execution")
    
    def _send_alert_notifications(alert_id):
        try:
            alert = InventoryAlert.objects.get(id=alert_id)
            from ..services.alerts.notification_service import NotificationService
            notification_service = NotificationService(tenant=alert.tenant)
            notification_service.send_alert_notification(alert)
        except Exception as e:
            logger.error(f"Failed to send alert notifications: {str(e)}")
    
    def _handle_alert_status_change(alert_id, old_status, new_status):
        try:
            alert = InventoryAlert.objects.get(id=alert_id)
            AlertHistory.objects.create(
                tenant=alert.tenant,
                alert=alert,
                action='STATUS_CHANGED',
                old_status=old_status,
                new_status=new_status,
                timestamp=timezone.now()
            )
        except Exception as e:
            logger.error(f"Failed to handle alert status change: {str(e)}")
    
    def _auto_resolve_alerts(stock_item_id, alert_type):
        try:
            stock_item = StockItem.objects.get(id=stock_item_id)
            alerts_to_resolve = InventoryAlert.objects.filter(
                stock_item=stock_item,
                alert_rule__alert_type=alert_type,
                status__in=['OPEN', 'ACKNOWLEDGED']
            )
            
            for alert in alerts_to_resolve:
                alert.auto_resolve()
                AlertHistory.objects.create(
                    tenant=alert.tenant,
                    alert=alert,
                    action='AUTO_RESOLVED',
                    old_status=alert.status,
                    new_status='AUTO_RESOLVED',
                    notes=f'Condition resolved: {alert_type}',
                    timestamp=timezone.now()
                )
        except Exception as e:
            logger.error(f"Failed to auto-resolve alerts: {str(e)}")
    
    # Add other fallback functions
    def _update_alert_dashboard_metrics(tenant_id): pass
    def _evaluate_alert_rule(rule_id): pass
    def _handle_alert_rule_updates(rule_id): pass
    def _check_stock_item_alerts(stock_item_id): pass
    def _check_movement_pattern_alerts(movement_id): pass
    def _check_cost_variance_alerts(movement_id): pass
    def _create_overdue_po_alert(po_id): pass
    def _create_budget_variance_alert(po_id, variance): pass
    def _escalate_alert(alert_id): pass
    def _track_alert_metrics(tenant_id, alert_id): pass
    
    # Add delay method for consistency
    for func_name in ['_send_alert_notifications', '_update_alert_dashboard_metrics',
                      '_handle_alert_status_change', '_evaluate_alert_rule',
                      '_handle_alert_rule_updates', '_check_stock_item_alerts',
                      '_check_movement_pattern_alerts', '_check_cost_variance_alerts',
                      '_create_overdue_po_alert', '_create_budget_variance_alert',
                      '_auto_resolve_alerts', '_escalate_alert', '_track_alert_metrics']:
        func = locals()[func_name]
        func.delay = func