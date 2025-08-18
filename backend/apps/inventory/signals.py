"""
Django signals for inventory management
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
import logging

from .models import (
    Product, StockItem, StockMovement, Batch, PurchaseOrderItem,
    StockReceipt, InventoryAlert, ProductVariation, StockReservationItem
)

logger = logging.getLogger(__name__)


# ============================================================================
# PRODUCT SIGNALS
# ============================================================================

@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """Handle product creation and updates"""
    if created:
        logger.info(f"New product created: {instance.sku} - {instance.name}")
        
        # Auto-generate barcode if enabled and not provided
        if not instance.barcode and hasattr(instance, 'tenant'):
            try:
                settings = instance.tenant.inventory_settings.first()
                if settings and settings.auto_generate_barcodes:
                    instance.barcode = generate_barcode(instance)
                    instance.save(update_fields=['barcode'])
            except Exception as e:
                logger.error(f"Error generating barcode for product {instance.sku}: {str(e)}")


@receiver(pre_save, sender=Product)
def product_pre_save(sender, instance, **kwargs):
    """Handle product updates before saving"""
    if instance.pk:  # Existing product
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            
            # Check if reorder point changed
            if old_instance.reorder_point != instance.reorder_point:
                # Update existing stock items with new reorder point if they don't have custom values
                StockItem.objects.filter(
                    product=instance,
                    is_active=True
                ).update(last_updated=timezone.now())
                
                logger.info(f"Reorder point updated for product {instance.sku}")
            
            # Check if status changed to inactive
            if old_instance.status == 'ACTIVE' and instance.status != 'ACTIVE':
                # Create alert for inactive product with stock
                stock_items = StockItem.objects.filter(
                    product=instance,
                    is_active=True,
                    quantity_on_hand__gt=0
                )
                
                if stock_items.exists():
                    total_stock = sum(item.quantity_on_hand for item in stock_items)
                    
                    InventoryAlert.objects.create(
                        tenant=instance.tenant,
                        alert_type='OTHER',
                        severity='MEDIUM',
                        title=f'Inactive Product with Stock: {instance.name}',
                        message=f'Product {instance.sku} has been made inactive but still has {total_stock} units in stock',
                        product=instance,
                        details={
                            'total_stock': float(total_stock),
                            'old_status': old_instance.status,
                            'new_status': instance.status
                        }
                    )
                    
        except Product.DoesNotExist:
            pass  # New product
        except Exception as e:
            logger.error(f"Error in product pre_save signal: {str(e)}")


# ============================================================================
# STOCK ITEM SIGNALS
# ============================================================================

@receiver(post_save, sender=StockItem)
def stock_item_post_save(sender, instance, created, **kwargs):
    """Handle stock item creation and updates"""
    try:
        # Check for low stock alerts
        if instance.is_low_stock and not created:
            # Check if alert already exists
            existing_alert = InventoryAlert.objects.filter(
                tenant=instance.tenant,
                alert_type='LOW_STOCK',
                product=instance.product,
                warehouse=instance.warehouse,
                status='ACTIVE'
            ).first()
            
            if not existing_alert:
                InventoryAlert.objects.create(
                    tenant=instance.tenant,
                    alert_type='LOW_STOCK',
                    severity='HIGH' if instance.quantity_available <= 0 else 'MEDIUM',
                    title=f'Low Stock Alert: {instance.product.name}',
                    message=f'Stock for {instance.product.sku} in {instance.warehouse.name} is below reorder point',
                    product=instance.product,
                    warehouse=instance.warehouse,
                    stock_item=instance,
                    details={
                        'current_stock': float(instance.quantity_available),
                        'reorder_point': float(instance.product.reorder_point),
                        'reorder_quantity': float(instance.product.reorder_quantity)
                    }
                )
                
                logger.info(f"Low stock alert created for {instance.product.sku} in {instance.warehouse.name}")
        
        # Resolve low stock alerts if stock is above reorder point
        elif not instance.is_low_stock:
            resolved_alerts = InventoryAlert.objects.filter(
                tenant=instance.tenant,
                alert_type__in=['LOW_STOCK', 'OUT_OF_STOCK'],
                product=instance.product,
                warehouse=instance.warehouse,
                status='ACTIVE'
            ).update(
                status='RESOLVED',
                resolved_at=timezone.now(),
                notes='Stock level restored above reorder point'
            )
            
            if resolved_alerts > 0:
                logger.info(f"Resolved {resolved_alerts} stock alerts for {instance.product.sku}")
        
        # Update product's ABC classification if needed
        if created or instance.total_value != getattr(instance, '_old_value', 0):
            # Trigger ABC analysis recalculation (async)
            from .tasks import calculate_abc_analysis
            calculate_abc_analysis.delay(instance.tenant.id)
            
    except Exception as e:
        logger.error(f"Error in stock_item_post_save signal: {str(e)}")


@receiver(pre_save, sender=StockItem)
def stock_item_pre_save(sender, instance, **kwargs):
    """Store old values before saving stock item"""
    if instance.pk:
        try:
            old_instance = StockItem.objects.get(pk=instance.pk)
            instance._old_value = old_instance.total_value
        except StockItem.DoesNotExist:
            instance._old_value = 0
    else:
        instance._old_value = 0


# ============================================================================
# STOCK MOVEMENT SIGNALS
# ============================================================================

@receiver(post_save, sender=StockMovement)
def stock_movement_post_save(sender, instance, created, **kwargs):
    """Handle stock movement creation"""
    if created:
        try:
            # Update stock item last movement date
            instance.stock_item.last_movement_date = instance.movement_date
            instance.stock_item.last_movement_type = instance.movement_type
            instance.stock_item.total_movements_count += 1
            instance.stock_item.save(update_fields=[
                'last_movement_date', 'last_movement_type', 'total_movements_count'
            ])
            
            # Create valuation layer for inbound movements
            if instance.is_inbound and instance.unit_cost > 0:
                from .models import StockValuationLayer
                
                StockValuationLayer.objects.create(
                    tenant=instance.tenant,
                    stock_item=instance.stock_item,
                    batch=instance.batch,
                    quantity_received=instance.quantity,
                    quantity_remaining=instance.quantity,
                    unit_cost=instance.unit_cost,
                    total_cost=instance.total_cost,
                    source_movement=instance,
                    source_document_type=instance.reference_type,
                    source_document_id=instance.reference_id
                )
                
                logger.debug(f"Created valuation layer for movement {instance.movement_id}")
            
            # Check for negative stock alerts
            if instance.stock_item.quantity_on_hand < 0 and not instance.stock_item.warehouse.allow_negative_stock:
                InventoryAlert.objects.get_or_create(
                    tenant=instance.tenant,
                    alert_type='NEGATIVE_STOCK',
                    product=instance.stock_item.product,
                    warehouse=instance.stock_item.warehouse,
                    stock_item=instance.stock_item,
                    status='ACTIVE',
                    defaults={
                        'severity': 'CRITICAL',
                        'title': f'Negative Stock: {instance.stock_item.product.name}',
                        'message': f'Stock for {instance.stock_item.product.sku} in {instance.stock_item.warehouse.name} has gone negative',
                        'details': {
                            'current_stock': float(instance.stock_item.quantity_on_hand),
                            'movement_type': instance.movement_type,
                            'movement_quantity': float(instance.quantity)
                        }
                    }
                )
                
                logger.warning(f"Negative stock alert created for {instance.stock_item.product.sku}")
                
        except Exception as e:
            logger.error(f"Error in stock_movement_post_save signal: {str(e)}")


# ============================================================================
# BATCH SIGNALS
# ============================================================================

@receiver(post_save, sender=Batch)
def batch_post_save(sender, instance, created, **kwargs):
    """Handle batch creation and updates"""
    if created:
        logger.info(f"New batch created: {instance.batch_number} for product {instance.product.sku}")
        
        # Check if batch is already expired
        if instance.is_expired:
            instance.status = 'EXPIRED'
            instance.save(update_fields=['status'])
            
            # Create expired stock alert
            InventoryAlert.objects.create(
                tenant=instance.tenant,
                alert_type='EXPIRED_STOCK',
                severity='CRITICAL',
                title=f'Expired Batch: {instance.product.name}',
                message=f'Batch {instance.batch_number} has already expired',
                product=instance.product,
                details={
                    'batch_number': instance.batch_number,
                    'expiry_date': instance.expiry_date.isoformat() if instance.expiry_date else None,
                    'current_quantity': float(instance.current_quantity)
                }
            )
        
        # Check if batch is expiring soon
        elif instance.is_near_expiry:
            days_until_expiry = instance.days_until_expiry
            severity = 'CRITICAL' if days_until_expiry <= 7 else 'HIGH'
            
            InventoryAlert.objects.get_or_create(
                tenant=instance.tenant,
                alert_type='EXPIRY_WARNING',
                product=instance.product,
                status='ACTIVE',
                defaults={
                    'severity': severity,
                    'title': f'Batch Expiring Soon: {instance.product.name}',
                    'message': f'Batch {instance.batch_number} expires in {days_until_expiry} days',
                    'details': {
                        'batch_number': instance.batch_number,
                        'expiry_date': instance.expiry_date.isoformat() if instance.expiry_date else None,
                        'days_until_expiry': days_until_expiry,
                        'current_quantity': float(instance.current_quantity)
                    }
                }
            )


# ============================================================================
# PURCHASE ORDER SIGNALS
# ============================================================================

@receiver(post_save, sender=PurchaseOrderItem)
def purchase_order_item_post_save(sender, instance, created, **kwargs):
    """Handle purchase order item updates"""
    if not created:
        # Check if item is fully received
        if instance.is_fully_received and instance.status != 'RECEIVED':
            instance.status = 'RECEIVED'
            instance.save(update_fields=['status'])
            
            logger.info(f"PO item {instance.purchase_order.po_number}-{instance.line_number} marked as fully received")
        
        # Update purchase order status
        po = instance.purchase_order
        if po.is_fully_received and po.status != 'RECEIVED':
            po.status = 'RECEIVED'
            po.delivery_date = timezone.now().date()
            po.save(update_fields=['status', 'delivery_date'])
            
            logger.info(f"Purchase order {po.po_number} marked as fully received")


# ============================================================================
# RESERVATION SIGNALS
# ============================================================================

@receiver(post_save, sender=StockReservationItem)
def reservation_item_post_save(sender, instance, created, **kwargs):
    """Handle reservation item updates"""
    if not created:
        # Update reservation status based on fulfillment
        reservation = instance.reservation
        total_items = reservation.items.count()
        fulfilled_items = reservation.items.filter(status='FULFILLED').count()
        
        if fulfilled_items == total_items:
            reservation.status = 'FULFILLED'
            reservation.fulfilled_date = timezone.now()
        elif fulfilled_items > 0:
            reservation.status = 'PARTIAL_FULFILLED'
        
        reservation.save(update_fields=['status', 'fulfilled_date'])


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_barcode(product):
    """Generate barcode for product"""
    try:
        # Simple barcode generation (you might want to use a proper barcode library)
        import hashlib
        
        # Create a hash based on tenant + product info
        hash_input = f"{product.tenant.id}-{product.sku}-{product.name}".encode()
        hash_digest = hashlib.md5(hash_input).hexdigest()
        
        # Take first 12 digits and calculate check digit
        barcode_base = ''.join(filter(str.isdigit, hash_digest))[:12]
        if len(barcode_base) < 12:
            barcode_base = barcode_base.ljust(12, '0')
        
        # Calculate UPC check digit
        check_digit = calculate_upc_check_digit(barcode_base)
        barcode = barcode_base + str(check_digit)
        
        return barcode[:13]  # Return 13-digit barcode
        
    except Exception as e:
        logger.error(f"Error generating barcode: {str(e)}")
        return None


def calculate_upc_check_digit(barcode_base):
    """Calculate UPC check digit"""
    odd_sum = sum(int(barcode_base[i]) for i in range(0, len(barcode_base), 2))
    even_sum = sum(int(barcode_base[i]) for i in range(1, len(barcode_base), 2))
    
    total = (odd_sum * 3) + even_sum
    check_digit = (10 - (total % 10)) % 10
    
    return check_digit
