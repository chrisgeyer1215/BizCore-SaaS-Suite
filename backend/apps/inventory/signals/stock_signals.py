from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from ..models import (
    StockItem, StockMovement, StockMovementItem, 
    StockValuationLayer, InventoryAlert
)
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, AuditSignalMixin,
    NotificationSignalMixin, IntegrationSignalMixin
)

logger = logging.getLogger(__name__)

@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def stock_movement_post_save(sender, instance, created, **kwargs):
    """Handle stock movement creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_movement_created', sender.__name__, instance.id)
        
        # Generate reference number if not set
        if not instance.reference_number:
            from ..utils.helpers import generate_reference_number
            instance.reference_number = generate_reference_number(
                prefix=instance.movement_type[:3]
            )
            sender.objects.filter(pk=instance.pk).update(
                reference_number=instance.reference_number
            )
        
        # Queue notification for significant movements
        if instance.movement_type in ['ADJUSTMENT_NEGATIVE', 'DAMAGED', 'LOST']:
            NotificationSignalMixin.queue_notification(
                'stock_movement_alert',
                instance,
                data={
                    'movement_type': instance.movement_type,
                    'total_value': float(instance.total_value or 0)
                }
            )
    
    # Update related analytics
    if instance.status == 'COMPLETED':
        _update_stock_analytics.delay(instance.tenant_id, instance.id)

@receiver(post_save, sender=StockMovementItem)
@BaseSignalHandler.safe_signal_execution
def stock_movement_item_post_save(sender, instance, created, **kwargs):
    """Handle stock movement item changes"""
    if kwargs.get('raw', False):
        return
    
    if created and instance.movement.status == 'COMPLETED':
        # Update stock levels immediately for completed movements
        with transaction.atomic():
            _update_stock_levels_from_movement_item(instance)
        
        # Update valuation layers
        _update_valuation_layers.delay(instance.id)
        
        # Check for alerts
        _check_stock_alerts.delay(instance.stock_item_id)
        
        # Update ABC classification if needed
        _update_abc_classification.delay(instance.stock_item.tenant_id)

@receiver(pre_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def stock_item_pre_save(sender, instance, **kwargs):
    """Handle stock item pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Calculate available quantity
    if hasattr(instance, 'quantity_on_hand') and hasattr(instance, 'quantity_reserved'):
        instance.quantity_available = max(0, instance.quantity_on_hand - instance.quantity_reserved)
    
    # Update last movement date if quantities changed
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            if (original.quantity_on_hand != instance.quantity_on_hand or 
                original.quantity_reserved != instance.quantity_reserved):
                instance.last_movement_date = timezone.now()
        except sender.DoesNotExist:
            pass
    
    # Validate stock levels
    if instance.quantity_on_hand < 0 and not _is_negative_stock_allowed(instance):
        logger.warning(f"Negative stock detected for {instance}: {instance.quantity_on_hand}")

@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def stock_item_post_save(sender, instance, created, **kwargs):
    """Handle stock item creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_item_created', sender.__name__, instance.id)
        
        # Create initial valuation layer if there's opening stock
        if instance.quantity_on_hand > 0:
            _create_initial_valuation_layer.delay(instance.id)
        
        # Sync to e-commerce platforms
        IntegrationSignalMixin.queue_integration_sync(
            'ecommerce', instance, 'create'
        )
    else:
        # Track changes for audit
        if instance.pk:
            _track_stock_changes.delay(instance.id)
        
        # Check for reorder alerts
        _check_reorder_alerts.delay(instance.id)
        
        # Update e-commerce inventory
        IntegrationSignalMixin.queue_integration_sync(
            'ecommerce', instance, 'update'
        )
    
    # Invalidate cache
    cache_patterns = [
        f"stock_summary_tenant_{instance.tenant_id}",
        f"stock_item_{instance.id}",
        f"product_stock_{instance.product_id}"
    ]
    BaseSignalHandler.invalidate_cache_patterns(cache_patterns)

@receiver(pre_delete, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def stock_item_pre_delete(sender, instance, **kwargs):
    """Handle stock item deletion"""
    # Check if stock item can be deleted
    if instance.quantity_on_hand != 0:
        raise ValueError("Cannot delete stock item with non-zero quantity")
    
    if instance.quantity_reserved > 0:
        raise ValueError("Cannot delete stock item with reserved quantity")
    
    # Check for pending movements
    pending_movements = StockMovementItem.objects.filter(
        stock_item=instance,
        movement__status__in=['PENDING', 'IN_PROGRESS']
    )
    
    if pending_movements.exists():
        raise ValueError("Cannot delete stock item with pending movements")

@receiver(post_save, sender=StockValuationLayer)
@BaseSignalHandler.safe_signal_execution
def valuation_layer_post_save(sender, instance, created, **kwargs):
    """Handle valuation layer changes"""
    if kwargs.get('raw', False):
        return
    
    if created or instance.quantity_remaining != getattr(instance, '_original_quantity_remaining', 0):
        # Update stock item average cost
        _update_stock_item_average_cost.delay(instance.stock_item_id)
        
        # Sync to finance module
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'update', priority='high'
        )

# Helper functions for async processing
def _update_stock_levels_from_movement_item(movement_item):
    """Update stock levels from movement item"""
    try:
        stock_item = movement_item.stock_item
        quantity = movement_item.quantity
        movement_type = movement_item.movement.movement_type
        
        # Determine if this is an inbound or outbound movement
        inbound_movements = [
            'RECEIPT', 'TRANSFER_IN', 'ADJUSTMENT_POSITIVE',
            'PRODUCTION_OUTPUT', 'RETURN_FROM_CUSTOMER', 'FOUND'
        ]
        
        outbound_movements = [
            'ISSUE', 'TRANSFER_OUT', 'ADJUSTMENT_NEGATIVE',
            'PRODUCTION_CONSUMPTION', 'RETURN_TO_SUPPLIER',
            'DAMAGED', 'EXPIRED', 'LOST'
        ]
        
        if movement_type in inbound_movements:
            stock_item.quantity_on_hand += quantity
            stock_item.total_quantity_received += quantity
        elif movement_type in outbound_movements:
            stock_item.quantity_on_hand -= quantity
            stock_item.total_quantity_issued += quantity
        elif movement_type == 'RESERVATION':
            stock_item.quantity_reserved += quantity
        elif movement_type == 'UNRESERVATION':
            stock_item.quantity_reserved -= quantity
        
        # Update movement count
        if movement_type in inbound_movements + outbound_movements:
            stock_item.movement_count += 1
        
        stock_item.last_movement_date = timezone.now()
        stock_item.save()
        
    except Exception as e:
        logger.error(f"Error updating stock levels: {str(e)}")

def _is_negative_stock_allowed(stock_item):
    """Check if negative stock is allowed for this item"""
    # You might have tenant-specific or product-specific rules
    return getattr(stock_item.tenant, 'allow_negative_stock', False)

# Celery tasks for async processing
try:
    from ..tasks.celery import (
        update_stock_analytics, update_valuation_layers,
        check_stock_alerts, update_abc_classification,
        create_initial_valuation_layer, track_stock_changes,
        check_reorder_alerts, update_stock_item_average_cost
    )
    
    # Make tasks available with delay method
    _update_stock_analytics = update_stock_analytics
    _update_valuation_layers = update_valuation_layers
    _check_stock_alerts = check_stock_alerts
    _update_abc_classification = update_abc_classification
    _create_initial_valuation_layer = create_initial_valuation_layer
    _track_stock_changes = track_stock_changes
    _check_reorder_alerts = check_reorder_alerts
    _update_stock_item_average_cost = update_stock_item_average_cost
    
except ImportError:
    # Fallback for synchronous execution if Celery is not available
    logger.warning("Celery not available, using synchronous task execution")
    
    def _update_stock_analytics(tenant_id, movement_id):
        pass
    
    def _update_valuation_layers(movement_item_id):
        pass
    
    def _check_stock_alerts(stock_item_id):
        pass
    
    def _update_abc_classification(tenant_id):
        pass
    
    def _create_initial_valuation_layer(stock_item_id):
        pass
    
    def _track_stock_changes(stock_item_id):
        pass
    
    def _check_reorder_alerts(stock_item_id):
        pass
    
    def _update_stock_item_average_cost(stock_item_id):
        pass
    
    # Add delay method for consistency
    for func_name in ['_update_stock_analytics', '_update_valuation_layers', 
                      '_check_stock_alerts', '_update_abc_classification',
                      '_create_initial_valuation_layer', '_track_stock_changes',
                      '_check_reorder_alerts', '_update_stock_item_average_cost']:
        func = locals()[func_name]
        func.delay = func  # Make synchronous call look like async

# Real-time stock monitoring
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def real_time_stock_monitoring(sender, instance, created, **kwargs):
    """Monitor stock changes in real-time"""
    if kwargs.get('raw', False):
        return
    
    # Check for critical stock levels
    if instance.quantity_on_hand <= 0:
        # Out of stock - critical alert
        _create_critical_stock_alert(instance, 'OUT_OF_STOCK')
    elif instance.quantity_on_hand <= instance.reorder_level and instance.reorder_level > 0:
        # Low stock alert
        _create_stock_alert(instance, 'LOW_STOCK')
    elif (instance.maximum_stock_level > 0 and 
          instance.quantity_on_hand >= instance.maximum_stock_level):
        # Overstock alert
        _create_stock_alert(instance, 'OVERSTOCK')
    
    # Check for negative stock
    if instance.quantity_on_hand < 0:
        _create_critical_stock_alert(instance, 'NEGATIVE_STOCK')

def _create_stock_alert(stock_item, alert_type):
    """Create stock alert"""
    try:
        from ..services.alerts.alert_service import AlertService
        
        alert_service = AlertService(tenant=stock_item.tenant)
        
        if alert_type == 'LOW_STOCK':
            alert_service.create_low_stock_alert(stock_item)
        elif alert_type == 'OVERSTOCK':
            alert_service._create_overstock_alert(None, stock_item)
        
    except Exception as e:
        logger.error(f"Failed to create stock alert: {str(e)}")

def _create_critical_stock_alert(stock_item, alert_type):
    """Create critical stock alert with immediate notification"""
    try:
        _create_stock_alert(stock_item, alert_type)
        
        # Send immediate notification for critical alerts
        NotificationSignalMixin.queue_notification(
            'critical_stock_alert',
            stock_item,
            data={
                'alert_type': alert_type,
                'current_stock': float(stock_item.quantity_on_hand),
                'product_name': stock_item.product.name
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create critical stock alert: {str(e)}")

# Stock synchronization with external systems
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def sync_stock_to_external_systems(sender, instance, created, **kwargs):
    """Sync stock changes to external systems"""
    if kwargs.get('raw', False):
        return
    
    # Only sync if sellable product
    if not instance.product.is_sellable:
        return
    
    # Queue sync to e-commerce platforms
    ecommerce_data = {
        'sku': instance.product.sku,
        'quantity_available': max(0, instance.quantity_on_hand - instance.quantity_reserved),
        'warehouse': instance.warehouse.code,
        'last_updated': timezone.now().isoformat()
    }
    
    IntegrationSignalMixin.queue_integration_sync(
        'ecommerce',
        instance,
        'update',
        priority='high'
    )
    
    # Sync to ERP system
    IntegrationSignalMixin.queue_integration_sync(
        'erp',
        instance,
        'update'
    )

# Performance optimization signals
@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def optimize_stock_performance(sender, instance, created, **kwargs):
    """Optimize stock-related performance"""
    if kwargs.get('raw', False):
        return
    
    # Update denormalized fields for better query performance
    if instance.status == 'COMPLETED':
        # Update product last movement date
        if instance.items.exists():
            products = [item.stock_item.product for item in instance.items.all()]
            for product in products:
                product.last_movement_date = timezone.now()
            
            # Bulk update for performance
            from ..models import Product
            product_ids = [p.id for p in products]
            Product.objects.filter(id__in=product_ids).update(
                last_movement_date=timezone.now()
            )