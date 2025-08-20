from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from ..models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderApproval,
    StockReceipt, StockReceiptItem, Supplier
)
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, NotificationSignalMixin,
    IntegrationSignalMixin, CacheInvalidationMixin, AuditSignalMixin
)

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def purchase_order_pre_save(sender, instance, **kwargs):
    """Handle purchase order pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Generate PO number if not set
    if not instance.po_number:
        from ..utils.helpers import generate_reference_number
        instance.po_number = generate_reference_number('PO')
    
    # Set order date if not set
    if not instance.order_date:
        instance.order_date = timezone.now().date()
    
    # Calculate expected delivery date if not set
    if not instance.expected_delivery_date and instance.supplier:
        lead_time_days = getattr(instance.supplier, 'default_lead_time_days', 14)
        instance.expected_delivery_date = instance.order_date + timezone.timedelta(days=lead_time_days)
    
    # Store original values for change tracking
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._original_status = original.status
            instance._original_total_amount = original.total_amount
        except sender.DoesNotExist:
            pass

@receiver(post_save, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def purchase_order_post_save(sender, instance, created, **kwargs):
    """Handle purchase order creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('purchase_order_created', sender.__name__, instance.id)
        
        # Create audit record
        AuditSignalMixin.create_audit_record(
            instance, 'CREATE', 
            getattr(instance, '_current_user', None)
        )
        
        # Initialize approval workflow if required
        if instance.requires_approval:
            _initiate_po_approval_workflow.delay(instance.id)
        
        # Send creation notification
        NotificationSignalMixin.queue_notification(
            'purchase_order_created',
            instance,
            data={
                'po_number': instance.po_number,
                'supplier_name': instance.supplier.name if instance.supplier else 'N/A',
                'total_amount': float(instance.total_amount),
                'status': instance.status
            }
        )
        
        # Update supplier statistics
        _update_supplier_statistics.delay(instance.supplier_id, 'order_created')
        
        # Queue finance integration for budget checking
        IntegrationSignalMixin.queue_integration_sync(
            'finance', instance, 'create', priority='high'
        )
    
    else:
        # Handle status changes
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            _handle_po_status_change.delay(
                instance.id, 
                instance._original_status, 
                instance.status
            )
        
        # Handle amount changes
        if (hasattr(instance, '_original_total_amount') and 
            instance._original_total_amount != instance.total_amount):
            _handle_po_amount_change.delay(instance.id)
        
        # Create audit record for updates
        if instance.pk:
            changes = AuditSignalMixin.track_field_changes(
                instance, 
                getattr(instance, '_original_instance', None)
            )
            if changes:
                AuditSignalMixin.create_audit_record(
                    instance, 'UPDATE', 
                    getattr(instance, '_current_user', None),
                    changes
                )
    
    # Invalidate related cache
    cache_patterns = [
        f"purchase_orders_tenant_{instance.tenant_id}",
        f"supplier_orders_{instance.supplier_id}" if instance.supplier else None,
        f"warehouse_orders_{instance.warehouse_id}" if instance.warehouse else None
    ]
    CacheInvalidationMixin.invalidate_related_cache(
        instance, 
        [p for p in cache_patterns if p]
    )

@receiver(post_save, sender=PurchaseOrderItem)
@BaseSignalHandler.safe_signal_execution
def purchase_order_item_post_save(sender, instance, created, **kwargs):
    """Handle purchase order item changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Update PO totals
        _update_po_totals.delay(instance.purchase_order_id)
        
        # Update product purchase statistics
        _update_product_purchase_stats.delay(instance.product_id)
    
    # Check for price variances
    _check_price_variances.delay(instance.id)

@receiver(post_save, sender=PurchaseOrderApproval)
@BaseSignalHandler.safe_signal_execution
def po_approval_post_save(sender, instance, created, **kwargs):
    """Handle PO approval changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Send approval request notification
        NotificationSignalMixin.queue_notification(
            'po_approval_requested',
            instance.purchase_order,
            data={
                'po_number': instance.purchase_order.po_number,
                'required_approval_level': instance.required_approval_level,
                'total_amount': float(instance.purchase_order.total_amount)
            }
        )
    
    elif instance.status in ['APPROVED', 'REJECTED']:
        # Handle approval decision
        _handle_po_approval_decision.delay(instance.id)

@receiver(post_save, sender=StockReceipt)
@BaseSignalHandler.safe_signal_execution
def stock_receipt_post_save(sender, instance, created, **kwargs):
    """Handle stock receipt creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('stock_receipt_created', sender.__name__, instance.id)
        
        # Generate receipt number if not set
        if not instance.receipt_number:
            from ..utils.helpers import generate_reference_number
            instance.receipt_number = generate_reference_number('RCT')
            sender.objects.filter(pk=instance.pk).update(
                receipt_number=instance.receipt_number
            )
        
        # Update related PO status
        if instance.purchase_order:
            _update_po_receipt_status.delay(instance.purchase_order_id)
        
        # Queue quality control if required
        if _requires_quality_control(instance):
            _queue_quality_control_tasks.delay(instance.id)
        
        # Update supplier performance metrics
        if instance.supplier:
            _update_supplier_performance.delay(instance.supplier_id, instance.id)
        
        # Send receipt notification
        NotificationSignalMixin.queue_notification(
            'stock_receipt_created',
            instance,
            data={
                'receipt_number': instance.receipt_number,
                'supplier_name': instance.supplier.name if instance.supplier else 'N/A',
                'total_quantity': float(instance.total_quantity or 0),
                'total_cost': float(instance.total_cost or 0)
            }
        )
    
    # Update financial records
    IntegrationSignalMixin.queue_integration_sync(
        'finance', instance, 'create' if created else 'update'
    )

@receiver(post_save, sender=StockReceiptItem)
@BaseSignalHandler.safe_signal_execution
def stock_receipt_item_post_save(sender, instance, created, **kwargs):
    """Handle stock receipt item changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Update receipt totals
        _update_receipt_totals.delay(instance.receipt_id)
        
        # Update PO item received quantities
        if instance.po_item:
            _update_po_item_received_quantity.delay(instance.po_item_id, instance.quantity_received)
        
        # Check for quantity variances
        if instance.po_item and instance.quantity_received != instance.po_item.quantity_ordered:
            _create_quantity_variance_alert.delay(instance.id)

@receiver(pre_delete, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def purchase_order_pre_delete(sender, instance, **kwargs):
    """Handle purchase order deletion"""
    # Check if PO can be deleted
    if instance.status in ['APPROVED', 'PARTIALLY_RECEIVED', 'COMPLETED']:
        raise ValueError("Cannot delete approved or received purchase order")
    
    # Check for associated receipts
    if instance.stockreceipt_set.exists():
        raise ValueError("Cannot delete purchase order with associated receipts")
    
    # Log deletion
    BaseSignalHandler.log_signal('purchase_order_deleted', sender.__name__, instance.id)
    
    # Create audit record
    AuditSignalMixin.create_audit_record(
        instance, 'DELETE', 
        getattr(instance, '_current_user', None)
    )

@receiver(pre_delete, sender=StockReceipt)
@BaseSignalHandler.safe_signal_execution
def stock_receipt_pre_delete(sender, instance, **kwargs):
    """Handle stock receipt deletion"""
    # Check if receipt can be deleted
    if instance.status == 'COMPLETED' and instance.total_quantity > 0:
        # Check if stock has been issued
        issued_items = instance.items.filter(
            product__stockitem__total_quantity_issued__gt=0
        )
        if issued_items.exists():
            raise ValueError("Cannot delete receipt - stock has already been issued")
    
    # Reverse stock movements if necessary
    if instance.status == 'COMPLETED':
        _reverse_receipt_stock_movements.delay(instance.id)

# Supplier-related signals
@receiver(post_save, sender=Supplier)
@BaseSignalHandler.safe_signal_execution
def supplier_post_save(sender, instance, created, **kwargs):
    """Handle supplier changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Initialize supplier performance tracking
        _initialize_supplier_performance.delay(instance.id)
    
    # Update related POs if supplier status changed
    if not created and hasattr(instance, '_original_status'):
        if instance._original_status != instance.status:
            _handle_supplier_status_change.delay(instance.id, instance.status)

# Budget and financial controls
@receiver(post_save, sender=PurchaseOrder)
@BaseSignalHandler.safe_signal_execution
def check_budget_controls(sender, instance, created, **kwargs):
    """Check budget controls and limits"""
    if kwargs.get('raw', False):
        return
    
    if created or (hasattr(instance, '_original_total_amount') and 
                   instance._original_total_amount != instance.total_amount):
        # Check budget availability
        _check_budget_availability.delay(instance.id)
        
        # Check spending limits
        _check_spending_limits.delay(instance.id)

# Lead time tracking
@receiver(post_save, sender=StockReceipt)
@BaseSignalHandler.safe_signal_execution
def track_lead_times(sender, instance, created, **kwargs):
    """Track supplier lead times"""
    if kwargs.get('raw', False) or not created:
        return
    
    if instance.purchase_order and instance.receipt_date:
        # Calculate actual lead time
        actual_lead_time = (instance.receipt_date - instance.purchase_order.order_date).days
        _update_supplier_lead_time_performance.delay(
            instance.supplier_id, 
            actual_lead_time,
            instance.purchase_order.expected_delivery_date <= instance.receipt_date
        )

# Async task functions
def _requires_quality_control(receipt):
    """Check if receipt requires quality control"""
    return any(
        item.product.requires_quality_control 
        for item in receipt.items.all()
    )

# Task implementations with fallbacks
try:
    from ..tasks.celery import (
        initiate_po_approval_workflow, update_supplier_statistics,
        handle_po_status_change, handle_po_amount_change,
        update_po_totals, update_product_purchase_stats,
        check_price_variances, handle_po_approval_decision,
        update_po_receipt_status, queue_quality_control_tasks,
        update_supplier_performance, update_receipt_totals,
        update_po_item_received_quantity, create_quantity_variance_alert,
        reverse_receipt_stock_movements, initialize_supplier_performance,
        handle_supplier_status_change, check_budget_availability,
        check_spending_limits, update_supplier_lead_time_performance
    )
    
    # Make tasks available with delay method
    _initiate_po_approval_workflow = initiate_po_approval_workflow
    _update_supplier_statistics = update_supplier_statistics
    _handle_po_status_change = handle_po_status_change
    _handle_po_amount_change = handle_po_amount_change
    _update_po_totals = update_po_totals
    _update_product_purchase_stats = update_product_purchase_stats
    _check_price_variances = check_price_variances
    _handle_po_approval_decision = handle_po_approval_decision
    _update_po_receipt_status = update_po_receipt_status
    _queue_quality_control_tasks = queue_quality_control_tasks
    _update_supplier_performance = update_supplier_performance
    _update_receipt_totals = update_receipt_totals
    _update_po_item_received_quantity = update_po_item_received_quantity
    _create_quantity_variance_alert = create_quantity_variance_alert
    _reverse_receipt_stock_movements = reverse_receipt_stock_movements
    _initialize_supplier_performance = initialize_supplier_performance
    _handle_supplier_status_change = handle_supplier_status_change
    _check_budget_availability = check_budget_availability
    _check_spending_limits = check_spending_limits
    _update_supplier_lead_time_performance = update_supplier_lead_time_performance

except ImportError:
    # Fallback implementations
    logger.warning("Celery not available for purchasing signals, using synchronous execution")
    
    def _initiate_po_approval_workflow(po_id):
        try:
            from ..services.purchasing.approval_service import ApprovalService
            po = PurchaseOrder.objects.get(id=po_id)
            approval_service = ApprovalService(tenant=po.tenant)
            approval_service.initiate_approval_workflow(po)
        except Exception as e:
            logger.error(f"Failed to initiate PO approval workflow: {str(e)}")
    
    def _handle_po_status_change(po_id, old_status, new_status):
        try:
            po = PurchaseOrder.objects.get(id=po_id)
            
            if new_status == 'APPROVED':
                NotificationSignalMixin.queue_notification(
                    'po_approved', po,
                    data={'po_number': po.po_number}
                )
            elif new_status == 'REJECTED':
                NotificationSignalMixin.queue_notification(
                    'po_rejected', po,
                    data={'po_number': po.po_number}
                )
        except Exception as e:
            logger.error(f"Failed to handle PO status change: {str(e)}")
    
    def _update_po_totals(po_id):
        try:
            po = PurchaseOrder.objects.get(id=po_id)
            items = po.items.all()
            
            subtotal = sum(item.total_amount for item in items)
            po.subtotal = subtotal
            po.calculate_totals()  # This would calculate taxes, discounts, etc.
            po.save()
        except Exception as e:
            logger.error(f"Failed to update PO totals: {str(e)}")
    
    # Other fallback implementations
    def _update_supplier_statistics(supplier_id, action): pass
    def _handle_po_amount_change(po_id): pass
    def _update_product_purchase_stats(product_id): pass
    def _check_price_variances(item_id): pass
    def _handle_po_approval_decision(approval_id): pass
    def _update_po_receipt_status(po_id): pass
    def _queue_quality_control_tasks(receipt_id): pass
    def _update_supplier_performance(supplier_id, receipt_id): pass
    def _update_receipt_totals(receipt_id): pass
    def _update_po_item_received_quantity(item_id, quantity): pass
    def _create_quantity_variance_alert(receipt_item_id): pass
    def _reverse_receipt_stock_movements(receipt_id): pass
    def _initialize_supplier_performance(supplier_id): pass
    def _handle_supplier_status_change(supplier_id, status): pass
    def _check_budget_availability(po_id): pass
    def _check_spending_limits(po_id): pass
    def _update_supplier_lead_time_performance(supplier_id, lead_time, on_time): pass
    
    # Add delay method for consistency
    for func_name in ['_initiate_po_approval_workflow', '_update_supplier_statistics',
                      '_handle_po_status_change', '_handle_po_amount_change',
                      '_update_po_totals', '_update_product_purchase_stats',
                      '_check_price_variances', '_handle_po_approval_decision',
                      '_update_po_receipt_status', '_queue_quality_control_tasks',
                      '_update_supplier_performance', '_update_receipt_totals',
                      '_update_po_item_received_quantity', '_create_quantity_variance_alert',
                      '_reverse_receipt_stock_movements', '_initialize_supplier_performance',
                      '_handle_supplier_status_change', '_check_budget_availability',
                      '_check_spending_limits', '_update_supplier_lead_time_performance']:
        func = locals()[func_name]
        func.delay = func