from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from ..models import StockTransfer, StockTransferItem, Warehouse
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, NotificationSignalMixin,
    IntegrationSignalMixin, CacheInvalidationMixin, AuditSignalMixin
)

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def stock_transfer_pre_save(sender, instance, **kwargs):
    """Handle stock transfer pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Generate transfer number if not set
    if not instance.transfer_number:
        from ..utils.helpers import generate_reference_number
        instance.transfer_number = generate_reference_number('TRF')
    
    # Set requested date if not set
    if not instance.requested_date:
        instance.requested_date = timezone.now().date()
    
    # Validate source and destination warehouses
    if instance.source_warehouse == instance.destination_warehouse:
        raise ValueError("Source and destination warehouses cannot be the same")
    
    # Store original values for change tracking
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._original_status = original.status
            instance._original_priority = original.priority
        except sender.DoesNotExist:
            pass

@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def stock_transfer_post_save(sender, instance, created, **kwargs):
    """Handle stock transfer creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_transfer_created', sender.__name__, instance.id)
        
        # Create audit record
        AuditSignalMixin.create_audit_record(
            instance, 'CREATE', 
            getattr(instance, '_current_user', None)
        )
        
        # Reserve stock at source warehouse
        _reserve_stock_for_transfer.delay(instance.id)
        
        # Send transfer request notification to destination warehouse
        NotificationSignalMixin.queue_notification(
            'transfer_request_created',
            instance,
            recipients=_get_warehouse_managers(instance.destination_warehouse),
            data={
                'transfer_number': instance.transfer_number,
                'source_warehouse': instance.source_warehouse.name,
                'destination_warehouse': instance.destination_warehouse.name,
                'total_quantity': float(instance.total_quantity or 0),
                'priority': instance.priority,
                'requested_by': instance.requested_by.username if instance.requested_by else 'System'
            }
        )
        
        # Check if approval is required
        if _requires_approval(instance):
            instance.status = 'PENDING_APPROVAL'
            sender.objects.filter(pk=instance.pk).update(status='PENDING_APPROVAL')
            
            # Send approval request
            _send_transfer_approval_request.delay(instance.id)
    
    else:
        # Handle status changes
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            _handle_transfer_status_change.delay(
                instance.id, 
                instance._original_status, 
                instance.status
            )
        
        # Handle priority changes
        if (hasattr(instance, '_original_priority') and 
            instance._original_priority != instance.priority):
            _handle_transfer_priority_change.delay(instance.id)
    
    # Invalidate related cache
    cache_patterns = [
        f"transfers_tenant_{instance.tenant_id}",
        f"warehouse_transfers_{instance.source_warehouse_id}",
        f"warehouse_transfers_{instance.destination_warehouse_id}"
    ]
    CacheInvalidationMixin.invalidate_related_cache(instance, cache_patterns)

@receiver(post_save, sender=StockTransferItem)
@BaseSignalHandler.safe_signal_execution
def stock_transfer_item_post_save(sender, instance, created, **kwargs):
    """Handle stock transfer item changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Update transfer totals
        _update_transfer_totals.delay(instance.transfer_id)
        
        # Validate stock availability
        _validate_transfer_item_availability.delay(instance.id)
    
    # Check for quantity changes that might affect reservations
    if not created and instance.pk:
        _adjust_stock_reservations.delay(instance.id)

@receiver(pre_delete, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def stock_transfer_pre_delete(sender, instance, **kwargs):
    """Handle stock transfer deletion"""
    # Check if transfer can be deleted
    if instance.status in ['IN_TRANSIT', 'COMPLETED']:
        raise ValueError("Cannot delete transfer that is in transit or completed")
    
    # Release reserved stock
    if instance.status in ['PENDING_APPROVAL', 'APPROVED']:
        _release_transfer_reservations.delay(instance.id)
    
    # Log deletion
    BaseSignalHandler.log_signal('stock_transfer_deleted', sender.__name__, instance.id)
    
    # Create audit record
    AuditSignalMixin.create_audit_record(
        instance, 'DELETE', 
        getattr(instance, '_current_user', None)
    )

@receiver(pre_delete, sender=StockTransferItem)
@BaseSignalHandler.safe_signal_execution
def stock_transfer_item_pre_delete(sender, instance, **kwargs):
    """Handle stock transfer item deletion"""
    # Release stock reservation for this item
    _release_item_reservation.delay(instance.id)

# Status change handlers
@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def handle_transfer_approval(sender, instance, created, **kwargs):
    """Handle transfer approval workflow"""
    if kwargs.get('raw', False) or created:
        return
    
    if (hasattr(instance, '_original_status') and 
        instance._original_status == 'PENDING_APPROVAL' and 
        instance.status == 'APPROVED'):
        
        # Transfer approved
        _handle_transfer_approved.delay(instance.id)

@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def handle_transfer_shipment(sender, instance, created, **kwargs):
    """Handle transfer shipment"""
    if kwargs.get('raw', False) or created:
        return
    
    if (hasattr(instance, '_original_status') and 
        instance._original_status == 'APPROVED' and 
        instance.status == 'IN_TRANSIT'):
        
        # Transfer shipped
        _handle_transfer_shipped.delay(instance.id)

@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def handle_transfer_completion(sender, instance, created, **kwargs):
    """Handle transfer completion"""
    if kwargs.get('raw', False) or created:
        return
    
    if (hasattr(instance, '_original_status') and 
        instance._original_status == 'IN_TRANSIT' and 
        instance.status == 'COMPLETED'):
        
        # Transfer completed
        _handle_transfer_completed.delay(instance.id)

@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def handle_transfer_cancellation(sender, instance, created, **kwargs):
    """Handle transfer cancellation"""
    if kwargs.get('raw', False) or created:
        return
    
    if (hasattr(instance, '_original_status') and 
        instance._original_status in ['PENDING_APPROVAL', 'APPROVED', 'IN_TRANSIT'] and 
        instance.status == 'CANCELLED'):
        
        # Transfer cancelled
        _handle_transfer_cancelled.delay(instance.id)

# Performance and analytics
@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def track_transfer_performance(sender, instance, created, **kwargs):
    """Track transfer performance metrics"""
    if kwargs.get('raw', False):
        return
    
    if not created and instance.status == 'COMPLETED':
        # Track completion metrics
        _track_transfer_metrics.delay(instance.id)

# Integration with warehouse management
@receiver(post_save, sender=StockTransfer)
@BaseSignalHandler.safe_signal_execution
def integrate_warehouse_systems(sender, instance, created, **kwargs):
    """Integrate with warehouse management systems"""
    if kwargs.get('raw', False):
        return
    
    # Sync with warehouse management system
    if instance.status in ['APPROVED', 'IN_TRANSIT', 'COMPLETED']:
        IntegrationSignalMixin.queue_integration_sync(
            'wms', instance, 'create' if created else 'update'
        )

# Helper functions
def _get_warehouse_managers(warehouse):
    """Get managers for a warehouse"""
    # This would return a list of user emails/IDs who manage the warehouse
    return []  # Implement based on your user-warehouse relationship

def _requires_approval(transfer):
    """Check if transfer requires approval"""
    # Implement approval logic based on:
    # - Transfer value
    # - Warehouse policies
    # - User permissions
    # - Product criticality
    approval_threshold = getattr(transfer.tenant, 'transfer_approval_threshold', 10000)
    return float(transfer.total_value or 0) >= approval_threshold

# Async task functions
try:
    from ..tasks.celery import (
        reserve_stock_for_transfer, send_transfer_approval_request,
        handle_transfer_status_change, handle_transfer_priority_change,
        update_transfer_totals, validate_transfer_item_availability,
        adjust_stock_reservations, release_transfer_reservations,
        release_item_reservation, handle_transfer_approved,
        handle_transfer_shipped, handle_transfer_completed,
        handle_transfer_cancelled, track_transfer_metrics
    )
    
    # Make tasks available with delay method
    _reserve_stock_for_transfer = reserve_stock_for_transfer
    _send_transfer_approval_request = send_transfer_approval_request
    _handle_transfer_status_change = handle_transfer_status_change
    _handle_transfer_priority_change = handle_transfer_priority_change
    _update_transfer_totals = update_transfer_totals
    _validate_transfer_item_availability = validate_transfer_item_availability
    _adjust_stock_reservations = adjust_stock_reservations
    _release_transfer_reservations = release_transfer_reservations
    _release_item_reservation = release_item_reservation
    _handle_transfer_approved = handle_transfer_approved
    _handle_transfer_shipped = handle_transfer_shipped
    _handle_transfer_completed = handle_transfer_completed
    _handle_transfer_cancelled = handle_transfer_cancelled
    _track_transfer_metrics = track_transfer_metrics

except ImportError:
    # Fallback implementations
    logger.warning("Celery not available for transfer signals, using synchronous execution")
    
    def _reserve_stock_for_transfer(transfer_id):
        try:
            transfer = StockTransfer.objects.get(id=transfer_id)
            for item in transfer.items.all():
                stock_item = item.source_stock_item
                stock_item.quantity_reserved += item.quantity_requested
                stock_item.save()
        except Exception as e:
            logger.error(f"Failed to reserve stock for transfer: {str(e)}")
    
    def _handle_transfer_status_change(transfer_id, old_status, new_status):
        try:
            transfer = StockTransfer.objects.get(id=transfer_id)
            
            # Send status change notifications
            NotificationSignalMixin.queue_notification(
                'transfer_status_changed',
                transfer,
                data={
                    'transfer_number': transfer.transfer_number,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )
        except Exception as e:
            logger.error(f"Failed to handle transfer status change: {str(e)}")
    
    def _update_transfer_totals(transfer_id):
        try:
            transfer = StockTransfer.objects.get(id=transfer_id)
            items = transfer.items.all()
            
            total_quantity = sum(item.quantity_requested for item in items)
            total_value = sum(
                item.quantity_requested * item.source_stock_item.unit_cost 
                for item in items
            )
            
            transfer.total_quantity = total_quantity
            transfer.total_value = total_value
            transfer.save()
        except Exception as e:
            logger.error(f"Failed to update transfer totals: {str(e)}")
    
    def _handle_transfer_completed(transfer_id):
        try:
            from ..services.transfers.transfer_service import TransferService
            
            transfer = StockTransfer.objects.get(id=transfer_id)
            transfer_service = TransferService(tenant=transfer.tenant)
            
            # Create stock movements for the completed transfer
            # This would involve creating inbound movements at destination
            # and outbound movements at source
            
            NotificationSignalMixin.queue_notification(
                'transfer_completed',
                transfer,
                data={
                    'transfer_number': transfer.transfer_number,
                    'total_quantity': float(transfer.total_quantity_received or 0)
                }
            )
        except Exception as e:
            logger.error(f"Failed to handle transfer completion: {str(e)}")
    
    # Other fallback implementations
    def _send_transfer_approval_request(transfer_id): pass
    def _handle_transfer_priority_change(transfer_id): pass
    def _validate_transfer_item_availability(item_id): pass
    def _adjust_stock_reservations(item_id): pass
    def _release_transfer_reservations(transfer_id): pass
    def _release_item_reservation(item_id): pass
    def _handle_transfer_approved(transfer_id): pass
    def _handle_transfer_shipped(transfer_id): pass
    def _handle_transfer_cancelled(transfer_id): pass
    def _track_transfer_metrics(transfer_id): pass
    
    # Add delay method for consistency
    for func_name in ['_reserve_stock_for_transfer', '_send_transfer_approval_request',
                      '_handle_transfer_status_change', '_handle_transfer_priority_change',
                      '_update_transfer_totals', '_validate_transfer_item_availability',
                      '_adjust_stock_reservations', '_release_transfer_reservations',
                      '_release_item_reservation', '_handle_transfer_approved',
                      '_handle_transfer_shipped', '_handle_transfer_completed',
                      '_handle_transfer_cancelled', '_track_transfer_metrics']:
        func = locals()[func_name]
        func.delay = func