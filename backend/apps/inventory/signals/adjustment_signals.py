from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from ..models import (
    StockAdjustment, StockAdjustmentItem, StockWriteOff,
    CycleCount, CycleCountItem, CycleCountVariance
)
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, NotificationSignalMixin,
    IntegrationSignalMixin, CacheInvalidationMixin, AuditSignalMixin
)

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=StockAdjustment)
@BaseSignalHandler.safe_signal_execution
def stock_adjustment_pre_save(sender, instance, **kwargs):
    """Handle stock adjustment pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Generate adjustment number if not set
    if not instance.adjustment_number:
        from ..utils.helpers import generate_reference_number
        instance.adjustment_number = generate_reference_number('ADJ')
    
    # Set adjustment date if not set
    if not instance.adjustment_date:
        instance.adjustment_date = timezone.now().date()
    
    # Validate adjustment based on business rules
    if instance.total_value and instance.total_value > Decimal('10000'):
        instance.requires_approval = True
    
    # Store original values for change tracking
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except sender.DoesNotExist:
            pass

@receiver(post_save, sender=StockAdjustment)
@BaseSignalHandler.safe_signal_execution
def stock_adjustment_post_save(sender, instance, created, **kwargs):
    """Handle stock adjustment creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_adjustment_created', sender.__name__, instance.id)
        
        # Create audit record
        AuditSignalMixin.create_audit_record(
            instance, 'CREATE', 
            getattr(instance, '_current_user', None)
        )
        
        # Check if approval is required
        if instance.requires_approval:
            instance.status = 'PENDING_APPROVAL'
            sender.objects.filter(pk=instance.pk).update(status='PENDING_APPROVAL')
            
            # Send approval request
            _send_adjustment_approval_request.delay(instance.id)
        else:
            # Auto-approve if no approval required
            _auto_approve_adjustment.delay(instance.id)
        
        # Send creation notification for significant adjustments
        if instance.total_value and instance.total_value >= Decimal('1000'):
            NotificationSignalMixin.queue_notification(
                'significant_adjustment_created',
                instance,
                data={
                    'adjustment_number': instance.adjustment_number,
                    'adjustment_type': instance.adjustment_type,
                    'total_value': float(instance.total_value),
                    'reason': instance.reason
                }
            )
    
    else:
        # Handle status changes
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            _handle_adjustment_status_change.delay(
                instance.id, 
                instance._original_status, 
                instance.status
            )
    
    # Invalidate related cache
    cache_patterns = [
        f"adjustments_tenant_{instance.tenant_id}",
        f"warehouse_adjustments_{instance.warehouse_id}" if instance.warehouse else None
    ]
    CacheInvalidationMixin.invalidate_related_cache(
        instance, 
        [p for p in cache_patterns if p]
    )

@receiver(post_save, sender=StockAdjustmentItem)
@BaseSignalHandler.safe_signal_execution
def stock_adjustment_item_post_save(sender, instance, created, **kwargs):
    """Handle stock adjustment item changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Update adjustment totals
        _update_adjustment_totals.delay(instance.adjustment_id)
        
        # Validate adjustment against current stock
        _validate_adjustment_item.delay(instance.id)
        
        # Check for significant variances
        _check_adjustment_variance.delay(instance.id)

@receiver(post_save, sender=StockWriteOff)
@BaseSignalHandler.safe_signal_execution
def stock_write_off_post_save(sender, instance, created, **kwargs):
    """Handle stock write-off creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_write_off_created', sender.__name__, instance.id)
        
        # Create corresponding adjustment
        _create_write_off_adjustment.delay(instance.id)
        
        # Send write-off notification
        NotificationSignalMixin.queue_notification(
            'stock_write_off_created',
            instance,
            data={
                'stock_item': str(instance.stock_item),
                'quantity': float(instance.quantity),
                'write_off_value': float(instance.write_off_value),
                'reason': instance.reason
            }
        )
        
        # Update financial records
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'create', priority='high'
        )

# Cycle Count Signals
@receiver(pre_save, sender=CycleCount)
@BaseSignalHandler.safe_signal_execution
def cycle_count_pre_save(sender, instance, **kwargs):
    """Handle cycle count pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Generate count number if not set
    if not instance.count_number:
        from ..utils.helpers import generate_reference_number
        instance.count_number = generate_reference_number('CC')
    
    # Set scheduled date if not set
    if not instance.scheduled_date:
        instance.scheduled_date = timezone.now().date()

@receiver(post_save, sender=CycleCount)
@BaseSignalHandler.safe_signal_execution
def cycle_count_post_save(sender, instance, created, **kwargs):
    """Handle cycle count creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('cycle_count_created', sender.__name__, instance.id)
        
        # Generate count items based on selection criteria
        _generate_cycle_count_items.delay(instance.id)
        
        # Send count assignment notification
        NotificationSignalMixin.queue_notification(
            'cycle_count_assigned',
            instance,
            recipients=_get_count_team_members(instance),
            data={
                'count_number': instance.count_number,
                'scheduled_date': instance.scheduled_date.isoformat(),
                'location': instance.location.code if instance.location else 'All locations'
            }
        )
    
    # Handle status changes
    if not created and hasattr(instance, '_original_status'):
        if instance._original_status != instance.status:
            _handle_cycle_count_status_change.delay(instance.id, instance.status)

@receiver(post_save, sender=CycleCountItem)
@BaseSignalHandler.safe_signal_execution
def cycle_count_item_post_save(sender, instance, created, **kwargs):
    """Handle cycle count item changes"""
    if kwargs.get('raw', False):
        return
    
    if not created and instance.counted_quantity is not None:
        # Calculate variance when count is completed
        _calculate_count_variance.delay(instance.id)
        
        # Check if all items are counted
        _check_count_completion.delay(instance.cycle_count_id)

@receiver(post_save, sender=CycleCountVariance)
@BaseSignalHandler.safe_signal_execution
def cycle_count_variance_post_save(sender, instance, created, **kwargs):
    """Handle cycle count variance creation"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Check if variance exceeds threshold
        _check_variance_threshold.delay(instance.id)
        
        # Create adjustment if variance is approved
        if instance.requires_adjustment and instance.is_approved:
            _create_variance_adjustment.delay(instance.id)

# Approval workflow signals
@receiver(post_save, sender=StockAdjustment)
@BaseSignalHandler.safe_signal_execution
def handle_adjustment_approval(sender, instance, created, **kwargs):
    """Handle adjustment approval workflow"""
    if kwargs.get('raw', False) or created:
        return
    
    if (hasattr(instance, '_original_status') and 
        instance._original_status == 'PENDING_APPROVAL' and 
        instance.status == 'APPROVED'):
        
        # Adjustment approved - apply it
        _apply_approved_adjustment.delay(instance.id)

# Financial integration
@receiver(post_save, sender=StockAdjustment)
@BaseSignalHandler.safe_signal_execution
def sync_adjustment_to_finance(sender, instance, created, **kwargs):
    """Sync adjustment to finance system"""
    if kwargs.get('raw', False):
        return
    
    if instance.status == 'APPLIED':
        # Sync to finance module for journal entries
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'create' if created else 'update',
            priority='high'
        )

# Variance analysis
@receiver(post_save, sender=CycleCountVariance)
@BaseSignalHandler.safe_signal_execution
def analyze_count_variances(sender, instance, created, **kwargs):
    """Analyze cycle count variances for patterns"""
    if kwargs.get('raw', False) or not created:
        return
    
    # Queue variance analysis
    _analyze_variance_patterns.delay(instance.cycle_count.tenant_id, instance.id)

# Helper functions
def _get_count_team_members(cycle_count):
    """Get cycle count team members"""
    # Return list of users assigned to cycle counting
    return []  # Implement based on your team assignment logic

# Async task functions
try:
    from ..tasks.celery import (
        send_adjustment_approval_request, auto_approve_adjustment,
        handle_adjustment_status_change, update_adjustment_totals,
        validate_adjustment_item, check_adjustment_variance,
        create_write_off_adjustment, generate_cycle_count_items,
        handle_cycle_count_status_change, calculate_count_variance,
        check_count_completion, check_variance_threshold,
        create_variance_adjustment, apply_approved_adjustment,
        analyze_variance_patterns
    )
    
    # Make tasks available with delay method
    _send_adjustment_approval_request = send_adjustment_approval_request
    _auto_approve_adjustment = auto_approve_adjustment
    _handle_adjustment_status_change = handle_adjustment_status_change
    _update_adjustment_totals = update_adjustment_totals
    _validate_adjustment_item = validate_adjustment_item
    _check_adjustment_variance = check_adjustment_variance
    _create_write_off_adjustment = create_write_off_adjustment
    _generate_cycle_count_items = generate_cycle_count_items
    _handle_cycle_count_status_change = handle_cycle_count_status_change
    _calculate_count_variance = calculate_count_variance
    _check_count_completion = check_count_completion
    _check_variance_threshold = check_variance_threshold
    _create_variance_adjustment = create_variance_adjustment
    _apply_approved_adjustment = apply_approved_adjustment
    _analyze_variance_patterns = analyze_variance_patterns

except ImportError:
    # Fallback implementations
    logger.warning("Celery not available for adjustment signals, using synchronous execution")
    
    def _auto_approve_adjustment(adjustment_id):
        try:
            from ..services.adjustments.adjustment_service import AdjustmentService
            
            adjustment = StockAdjustment.objects.get(id=adjustment_id)
            adjustment_service = AdjustmentService(tenant=adjustment.tenant)
            
            # Auto-approve and apply small adjustments
            if adjustment.total_value <= Decimal('500'):
                adjustment.status = 'APPROVED'
                adjustment.approved_date = timezone.now()
                adjustment.save()
                
                # Apply the adjustment
                _apply_approved_adjustment(adjustment_id)
        except Exception as e:
            logger.error(f"Failed to auto-approve adjustment: {str(e)}")
    
    def _apply_approved_adjustment(adjustment_id):
        try:
            from ..services.adjustments.adjustment_service import AdjustmentService
            
            adjustment = StockAdjustment.objects.get(id=adjustment_id)
            adjustment_service = AdjustmentService(tenant=adjustment.tenant)
            
            # Apply the adjustment to stock levels
            adjustment_service._apply_adjustment(adjustment)
        except Exception as e:
            logger.error(f"Failed to apply approved adjustment: {str(e)}")
    
    def _update_adjustment_totals(adjustment_id):
        try:
            adjustment = StockAdjustment.objects.get(id=adjustment_id)
            items = adjustment.items.all()
            
            total_quantity = sum(abs(item.quantity_difference) for item in items)
            total_value = sum(
                abs(item.quantity_difference) * item.unit_cost 
                for item in items
            )
            
            adjustment.total_quantity = total_quantity
            adjustment.total_value = total_value
            adjustment.save()
        except Exception as e:
            logger.error(f"Failed to update adjustment totals: {str(e)}")
    
    def _calculate_count_variance(item_id):
        try:
            item = CycleCountItem.objects.get(id=item_id)
            
            if item.counted_quantity is not None:
                variance_quantity = item.counted_quantity - item.system_quantity
                variance_value = variance_quantity * item.unit_cost
                
                if abs(variance_quantity) > 0:
                    CycleCountVariance.objects.create(
                        tenant=item.cycle_count.tenant,
                        cycle_count=item.cycle_count,
                        cycle_count_item=item,
                        stock_item=item.stock_item,
                        system_quantity=item.system_quantity,
                        counted_quantity=item.counted_quantity,
                        variance_quantity=variance_quantity,
                        variance_value=variance_value,
                        unit_cost=item.unit_cost
                    )
        except Exception as e:
            logger.error(f"Failed to calculate count variance: {str(e)}")
    
    # Other fallback implementations
    def _send_adjustment_approval_request(adjustment_id): pass
    def _handle_adjustment_status_change(adjustment_id, old_status, new_status): pass
    def _validate_adjustment_item(item_id): pass
    def _check_adjustment_variance(item_id): pass
    def _create_write_off_adjustment(write_off_id): pass
    def _generate_cycle_count_items(count_id): pass
    def _handle_cycle_count_status_change(count_id, status): pass
    def _check_count_completion(count_id): pass
    def _check_variance_threshold(variance_id): pass
    def _create_variance_adjustment(variance_id): pass
    def _analyze_variance_patterns(tenant_id, variance_id): pass
    
    # Add delay method for consistency
    for func_name in ['_send_adjustment_approval_request', '_auto_approve_adjustment',
                      '_handle_adjustment_status_change', '_update_adjustment_totals',
                      '_validate_adjustment_item', '_check_adjustment_variance',
                      '_create_write_off_adjustment', '_generate_cycle_count_items',
                      '_handle_cycle_count_status_change', '_calculate_count_variance',
                      '_check_count_completion', '_check_variance_threshold',
                      '_create_variance_adjustment', '_apply_approved_adjustment',
                      '_analyze_variance_patterns']:
        func = locals()[func_name]
        func.delay = func