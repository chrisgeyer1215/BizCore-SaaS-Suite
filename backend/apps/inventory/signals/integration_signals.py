from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import logging
import json

from ..models import (
    Product, StockItem, PurchaseOrder, StockMovement,
    StockTransfer, StockReceipt, Supplier
)
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, IntegrationSignalMixin
)

logger = logging.getLogger(__name__)

# E-commerce Integration Signals
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def sync_stock_to_ecommerce(sender, instance, created, **kwargs):
    """Sync stock levels to e-commerce platforms"""
    if kwargs.get('raw', False):
        return
    
    # Only sync sellable products
    if not instance.product.is_sellable or not instance.product.is_active:
        return
    
    # Queue sync to all configured e-commerce platforms
    platforms = _get_configured_ecommerce_platforms(instance.tenant)
    
    for platform in platforms:
        IntegrationSignalMixin.queue_integration_sync(
            f'ecommerce_{platform}', 
            instance, 
            'update',
            priority='high'
        )

@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def sync_product_to_ecommerce(sender, instance, created, **kwargs):
    """Sync product information to e-commerce platforms"""
    if kwargs.get('raw', False):
        return
    
    # Only sync sellable products
    if not instance.is_sellable:
        return
    
    platforms = _get_configured_ecommerce_platforms(instance.tenant)
    action = 'create' if created else 'update'
    
    for platform in platforms:
        IntegrationSignalMixin.queue_integration_sync(
            f'ecommerce_{platform}', 
            instance, 
            action
        )

@receiver(post_delete, sender=Product)
@BaseSignalHandler.safe_signal_execution
def remove_product_from_ecommerce(sender, instance, **kwargs):
    """Remove product from e-commerce platforms"""
    platforms = _get_configured_ecommerce_platforms(instance.tenant)
    
    for platform in platforms:
        IntegrationSignalMixin.queue_integration_sync(
            f'ecommerce_{platform}', 
            instance, 
            'delete'
        )

# ERP Integration Signals
@receiver(post_save, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def sync_po_to_erp(sender, instance, created, **kwargs):
    """Sync purchase orders to ERP system"""
    if kwargs.get('raw', False):
        return
    
    if instance.status in ['APPROVED', 'COMPLETED']:
        IntegrationSignalMixin.queue_integration_sync(
            'erp', instance, 'create' if created else 'update'
        )

@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def sync_movement_to_erp(sender, instance, created, **kwargs):
    """Sync stock movements to ERP system"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'COMPLETED':
        IntegrationSignalMixin.queue_integration_sync(
            'erp', instance, 'create'
        )

# Finance Integration Signals
@receiver(post_save, sender=StockReceipt)
@BaseSignalHandler.safe_signal_execution
def sync_receipt_to_finance(sender, instance, created, **kwargs):
    """Sync stock receipts to finance system"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'COMPLETED':
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'create' if created else 'update',
            priority='high'
        )

@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def sync_movement_to_finance(sender, instance, created, **kwargs):
    """Sync stock movements to finance for COGS tracking"""
    if kwargs.get('raw', False):
        return
    
    # Only sync movements that affect COGS
    cogs_movement_types = ['ISSUE', 'ADJUSTMENT_NEGATIVE', 'DAMAGED', 'EXPIRED']
    
    if instance.movement_type in cogs_movement_types and instance.status == 'COMPLETED':
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'create',
            priority='high'
        )

# CRM Integration Signals
@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def sync_product_to_crm(sender, instance, created, **kwargs):
    """Sync new products to CRM system"""
    if kwargs.get('raw', False):
        return
    
    if created and instance.is_sellable:
        IntegrationSignalMixin.queue_integration_sync(
            'crm', instance, 'create'
        )

@receiver(post_save, sender=Supplier)
@BaseSignalHandler.safe_signal_execution
def sync_supplier_to_crm(sender, instance, created, **kwargs):
    """Sync suppliers to CRM system"""
    if kwargs.get('raw', False):
        return
    
    IntegrationSignalMixin.queue_integration_sync(
        'crm', instance, 'create' if created else 'update'
    )

# Analytics Integration Signals
@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def sync_movement_to_analytics(sender, instance, created, **kwargs):
    """Sync movements to analytics platform"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'COMPLETED':
        IntegrationSignalMixin.queue_integration_sync(
            'analytics', instance, 'create'
        )

@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def sync_stock_to_analytics(sender, instance, created, **kwargs):
    """Sync stock changes to analytics platform"""
    if kwargs.get('raw', False):
        return
    
    # Only sync significant stock changes
    if not created and hasattr(instance, '_original_quantity'):
        quantity_change = abs(instance.quantity_on_hand - instance._original_quantity)
        if quantity_change >= 1:  # Configurable threshold
            IntegrationSignalMixin.queue_integration_sync(
                'analytics', instance, 'update'
            )

# Warehouse Management System Integration
@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def sync_transfer_to_wms(sender, instance, created, **kwargs):
    """Sync stock transfers to warehouse management system"""
    if kwargs.get('raw', False):
        return
    
    if instance.status in ['APPROVED', 'IN_TRANSIT', 'COMPLETED']:
        IntegrationSignalMixin.queue_integration_sync(
            'wms', instance, 'create' if created else 'update'
        )

# Third-party Logistics Integration
@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def sync_transfer_to_3pl(sender, instance, created, **kwargs):
    """Sync transfers to 3PL systems"""
    if kwargs.get('raw', False):
        return
    
    # Only sync if using 3PL for this warehouse
    if (_is_3pl_warehouse(instance.source_warehouse) or 
        _is_3pl_warehouse(instance.destination_warehouse)):
        
        if instance.status == 'APPROVED':
            IntegrationSignalMixin.queue_integration_sync(
                '3pl', instance, 'create'
            )

# API Webhook Integrations
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def trigger_stock_webhooks(sender, instance, created, **kwargs):
    """Trigger webhooks for stock changes"""
    if kwargs.get('raw', False):
        return
    
    # Get configured webhooks for this tenant
    webhooks = _get_tenant_webhooks(instance.tenant, 'stock_change')
    
    for webhook in webhooks:
        _trigger_webhook.delay(webhook['url'], {
            'event': 'stock_change',
            'tenant_id': instance.tenant_id,
            'product_sku': instance.product.sku,
            'warehouse_code': instance.warehouse.code,
            'quantity_on_hand': float(instance.quantity_on_hand),
            'quantity_reserved': float(instance.quantity_reserved),
            'timestamp': timezone.now().isoformat()
        })

@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def trigger_product_webhooks(sender, instance, created, **kwargs):
    """Trigger webhooks for product changes"""
    if kwargs.get('raw', False):
        return
    
    event_type = 'product_created' if created else 'product_updated'
    webhooks = _get_tenant_webhooks(instance.tenant, event_type)
    
    for webhook in webhooks:
        _trigger_webhook.delay(webhook['url'], {
            'event': event_type,
            'tenant_id': instance.tenant_id,
            'product_id': instance.id,
            'product_sku': instance.sku,
            'product_name': instance.name,
            'is_active': instance.is_active,
            'is_sellable': instance.is_sellable,
            'timestamp': timezone.now().isoformat()
        })

# Real-time Updates Integration
@receiver(post_save, sender=StockItem)
@BaseSignalHandler.safe_signal_execution
def broadcast_stock_updates(sender, instance, created, **kwargs):
    """Broadcast real-time stock updates via WebSocket"""
    if kwargs.get('raw', False):
        return
    
    # Broadcast to WebSocket channels
    _broadcast_realtime_update.delay('stock_update', {
        'tenant_id': instance.tenant_id,
        'product_id': instance.product_id,
        'warehouse_id': instance.warehouse_id,
        'quantity_on_hand': float(instance.quantity_on_hand),
        'quantity_available': float(instance.quantity_on_hand - instance.quantity_reserved),
        'timestamp': timezone.now().isoformat()
    })

# Integration Health Monitoring
@receiver(post_save)
@BaseSignalHandler.safe_signal_execution
def monitor_integration_health(sender, instance, created, **kwargs):
    """Monitor integration health and performance"""
    if kwargs.get('raw', False):
        return
    
    # Only monitor inventory app models
    if sender._meta.app_label != 'inventory':
        return
    
    # Track integration sync metrics
    _track_integration_metrics.delay(
        sender.__name__,
        instance.tenant_id if hasattr(instance, 'tenant_id') else None,
        'create' if created else 'update'
    )

# Batch Integration Processing
@receiver(post_save, sender=StockMovement)
@BaseSignalHandler.safe_signal_execution
def queue_batch_integration_sync(sender, instance, created, **kwargs):
    """Queue movements for batch integration processing"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'COMPLETED':
        # Add to batch processing queue
        _add_to_batch_sync_queue.delay('stock_movements', instance.id)

# Helper functions
def _get_configured_ecommerce_platforms(tenant):
    """Get configured e-commerce platforms for tenant"""
    # This would fetch from tenant settings or configuration
    return ['shopify', 'woocommerce']  # Example

def _is_3pl_warehouse(warehouse):
    """Check if warehouse is managed by 3PL"""
    return warehouse.warehouse_type == 'THIRD_PARTY' if warehouse else False

def _get_tenant_webhooks(tenant, event_type):
    """Get configured webhooks for tenant and event type"""
    # This would fetch from tenant webhook configuration
    return []  # Implement based on your webhook configuration model

# Async task functions
try:
    from ..tasks.celery import (
        trigger_webhook, broadcast_realtime_update, track_integration_metrics,
        add_to_batch_sync_queue, process_integration_queue
    )
    
    _trigger_webhook = trigger_webhook
    _broadcast_realtime_update = broadcast_realtime_update
    _track_integration_metrics = track_integration_metrics
    _add_to_batch_sync_queue = add_to_batch_sync_queue
    _process_integration_queue = process_integration_queue

except ImportError:
    # Fallback implementations
    logger.warning("Celery not available for integration signals, using synchronous execution")
    
    def _trigger_webhook(url, data):
        try:
            import requests
            response = requests.post(
                url, 
                json=data, 
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            logger.info(f"Webhook triggered: {url}, status: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to trigger webhook {url}: {str(e)}")
    
    def _broadcast_realtime_update(channel, data):
        try:
            # This would integrate with your WebSocket system (Django Channels, etc.)
            logger.info(f"Broadcasting to {channel}: {data}")
        except Exception as e:
            logger.error(f"Failed to broadcast update: {str(e)}")
    
    def _track_integration_metrics(model_name, tenant_id, action):
        try:
            # Track metrics for monitoring
            cache_key = f"integration_metrics_{tenant_id}_{model_name}"
            metrics = cache.get(cache_key, {'total': 0, 'creates': 0, 'updates': 0})
            
            metrics['total'] += 1
            if action == 'create':
                metrics['creates'] += 1
            else:
                metrics['updates'] += 1
            
            cache.set(cache_key, metrics, 3600)  # Cache for 1 hour
        except Exception as e:
            logger.error(f"Failed to track integration metrics: {str(e)}")
    
    def _add_to_batch_sync_queue(queue_name, item_id):
        try:
            # Add item to batch processing queue
            queue_key = f"batch_sync_{queue_name}"
            current_batch = cache.get(queue_key, [])
            current_batch.append(item_id)
            cache.set(queue_key, current_batch, 3600)
            
            # Process batch if it reaches threshold
            if len(current_batch) >= 100:  # Configurable batch size
                _process_integration_queue(queue_name, current_batch)
                cache.delete(queue_key)
        except Exception as e:
            logger.error(f"Failed to add to batch sync queue: {str(e)}")
    
    def _process_integration_queue(queue_name, item_ids):
        try:
            # Process batch of items
            logger.info(f"Processing batch integration queue {queue_name} with {len(item_ids)} items")
            # Implement batch processing logic here
        except Exception as e:
            logger.error(f"Failed to process integration queue: {str(e)}")
    
    # Add delay method for consistency
    for func_name in ['_trigger_webhook', '_broadcast_realtime_update', '_track_integration_metrics',
                      '_add_to_batch_sync_queue', '_process_integration_queue']:
        func = locals()[func_name]
        func.delay = func

# Integration circuit breaker
@receiver(post_save)
@BaseSignalHandler.safe_signal_execution
def integration_circuit_breaker(sender, instance, created, **kwargs):
    """Implement circuit breaker pattern for integrations"""
    if kwargs.get('raw', False):
        return
    
    # Only handle inventory app models
    if sender._meta.app_label != 'inventory':
        return
    
    # Check integration health before queuing
    tenant_id = getattr(instance, 'tenant_id', None)
    if tenant_id:
        _check_integration_circuit_breaker.delay(tenant_id)

try:
    from ..tasks.celery import check_integration_circuit_breaker
    _check_integration_circuit_breaker = check_integration_circuit_breaker
except ImportError:
    def _check_integration_circuit_breaker(tenant_id):
        try:
            # Check integration error rates and disable if too high
            error_key = f"integration_errors_{tenant_id}"
            error_count = cache.get(error_key, 0)
            
            if error_count > 100:  # Configurable threshold
                # Disable integrations for this tenant temporarily
                cache.set(f"integration_disabled_{tenant_id}", True, 1800)  # 30 minutes
                logger.warning(f"Integration circuit breaker activated for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to check integration circuit breaker: {str(e)}")
    
    _check_integration_circuit_breaker.delay = _check_integration_circuit_breaker