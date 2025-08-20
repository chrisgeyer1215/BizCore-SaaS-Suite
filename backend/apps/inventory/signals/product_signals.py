from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from ..models import Product, ProductVariation, StockItem
from .handlers import (
    BaseSignalHandler, TenantSignalMixin, NotificationSignalMixin,
    IntegrationSignalMixin, CacheInvalidationMixin
)

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def product_pre_save(sender, instance, **kwargs):
    """Handle product pre-save operations"""
    if kwargs.get('raw', False):
        return
    
    # Generate SKU if not provided
    if not instance.sku:
        from ..utils.helpers import generate_sku
        instance.sku = generate_sku(
            instance.name,
            instance.category.code if instance.category else '',
            instance.brand.code if instance.brand else ''
        )
    
    # Generate slug for URL-friendly access
    if not instance.slug:
        from django.utils.text import slugify
        instance.slug = slugify(instance.name)
    
    # Set default values
    if instance.product_type is None:
        instance.product_type = 'FINISHED_GOOD'
    
    if instance.track_inventory is None:
        instance.track_inventory = True
    
    # Validate business rules
    if instance.selling_price and instance.cost_price:
        if instance.selling_price < instance.cost_price:
            logger.warning(f"Product {instance.name} has selling price below cost price")

@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def product_post_save(sender, instance, created, **kwargs):
    """Handle product creation and updates"""
    if kwargs.get('raw', False):
        return
    
    if created:
        BaseSignalHandler.log_signal('product_created', sender.__name__, instance.id)
        
        # Create stock items for all warehouses if auto-create is enabled
        if getattr(instance.tenant, 'auto_create_stock_items', False):
            _create_stock_items_for_all_warehouses.delay(instance.id)
        
        # Sync to e-commerce platforms
        IntegrationSignalMixin.queue_integration_sync(
            'ecommerce', instance, 'create'
        )
        
        # Sync to CRM for new product notifications
        IntegrationSignalMixin.queue_integration_sync(
            'crm', instance, 'create'
        )
        
        # Queue new product notification
        NotificationSignalMixin.queue_notification(
            'new_product_created',
            instance,
            data={
                'product_name': instance.name,
                'sku': instance.sku,
                'category': instance.category.name if instance.category else 'N/A'
            }
        )
    else:
        # Handle product updates
        if instance.pk:
            _handle_product_updates.delay(instance.id)
        
        # Sync updates to external systems
        IntegrationSignalMixin.queue_integration_sync(
            'ecommerce', instance, 'update'
        )
    
    # Invalidate related cache
    cache_patterns = [
        f"product_{instance.id}",
        f"products_tenant_{instance.tenant_id}",
        f"category_products_{instance.category_id}" if instance.category else None,
        f"brand_products_{instance.brand_id}" if instance.brand else None
    ]
    CacheInvalidationMixin.invalidate_related_cache(
        instance, 
        [p for p in cache_patterns if p]
    )

@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def handle_product_status_changes(sender, instance, created, **kwargs):
    """Handle product status changes"""
    if kwargs.get('raw', False) or created:
        return
    
    try:
        # Get original instance to compare changes
        original = sender.objects.get(pk=instance.pk)
        
        # Handle activation/deactivation
        if original.is_active != instance.is_active:
            if not instance.is_active:
                # Product deactivated
                _handle_product_deactivation.delay(instance.id)
                
                NotificationSignalMixin.queue_notification(
                    'product_deactivated',
                    instance,
                    data={'reason': 'Product has been deactivated'}
                )
            else:
                # Product reactivated
                _handle_product_reactivation.delay(instance.id)
        
        # Handle sellability changes
        if original.is_sellable != instance.is_sellable:
            _update_ecommerce_availability.delay(instance.id, instance.is_sellable)
        
        # Handle price changes
        if (original.selling_price != instance.selling_price or 
            original.cost_price != instance.cost_price):
            _handle_price_changes.delay(instance.id, created)
    
    except sender.DoesNotExist:
        pass  # Original instance not found, might be a creation

@receiver(post_delete, sender=Product)
@BaseSignalHandler.safe_signal_execution
def product_post_delete(sender, instance, **kwargs):
    """Handle product deletion"""
    BaseSignalHandler.log_signal('product_deleted', sender.__name__, instance.id)
    
    # Sync deletion to external systems
    IntegrationSignalMixin.queue_integration_sync(
        'ecommerce', instance, 'delete'
    )
    
    # Notify about product deletion
    NotificationSignalMixin.queue_notification(
        'product_deleted',
        instance,
        data={
            'product_name': instance.name,
            'sku': instance.sku
        }
    )

@receiver(post_save, sender=ProductVariation)
@BaseSignalHandler.safe_signal_execution
def product_variation_post_save(sender, instance, created, **kwargs):
    """Handle product variation changes"""
    if kwargs.get('raw', False):
        return
    
    if created:
        # Create stock items for the variation
        _create_stock_items_for_variation.delay(instance.id)
        
        # Sync to e-commerce
        IntegrationSignalMixin.queue_integration_sync(
            'ecommerce', instance.product, 'update'
        )
    
    # Invalidate product cache
    CacheInvalidationMixin.invalidate_related_cache(instance.product)

# Async task functions
def _create_stock_items_for_all_warehouses(product_id):
    """Create stock items for all active warehouses"""
    try:
        from ..models import Product, Warehouse, StockItem
        
        product = Product.objects.get(id=product_id)
        warehouses = Warehouse.objects.filter(
            tenant=product.tenant,
            is_active=True
        )
        
        stock_items_to_create = []
        for warehouse in warehouses:
            # Check if stock item already exists
            if not StockItem.objects.filter(
                product=product,
                warehouse=warehouse
            ).exists():
                stock_items_to_create.append(
                    StockItem(
                        tenant=product.tenant,
                        product=product,
                        warehouse=warehouse,
                        quantity_on_hand=0,
                        unit_cost=product.cost_price or 0,
                        reorder_level=product.default_reorder_level or 0,
                        maximum_stock_level=product.default_maximum_level or 0
                    )
                )
        
        if stock_items_to_create:
            StockItem.objects.bulk_create(stock_items_to_create)
            logger.info(f"Created {len(stock_items_to_create)} stock items for product {product.sku}")
    
    except Exception as e:
        logger.error(f"Failed to create stock items for product {product_id}: {str(e)}")

def _handle_product_updates(product_id):
    """Handle product updates"""
    try:
        from ..models import Product, StockItem
        
        product = Product.objects.get(id=product_id)
        
        # Update related stock items with new product information
        StockItem.objects.filter(product=product).update(
            updated_at=timezone.now()
        )
        
        # Update cost prices if changed
        if hasattr(product, '_cost_price_changed'):
            StockItem.objects.filter(
                product=product,
                unit_cost=0  # Only update items with zero cost
            ).update(
                unit_cost=product.cost_price or 0
            )
    
    except Exception as e:
        logger.error(f"Failed to handle product updates for {product_id}: {str(e)}")

def _handle_product_deactivation(product_id):
    """Handle product deactivation"""
    try:
        from ..models import Product, StockReservation
        
        product = Product.objects.get(id=product_id)
        
        # Cancel pending reservations
        pending_reservations = StockReservation.objects.filter(
            items__stock_item__product=product,
            status__in=['PENDING', 'RESERVED']
        ).distinct()
        
        for reservation in pending_reservations:
            # You would call a service to cancel these reservations
            logger.info(f"Cancelling reservation {reservation.reference_number} due to product deactivation")
        
        # Update e-commerce platforms to mark as unavailable
        _update_ecommerce_availability.delay(product_id, False)
    
    except Exception as e:
        logger.error(f"Failed to handle product deactivation for {product_id}: {str(e)}")

def _handle_product_reactivation(product_id):
    """Handle product reactivation"""
    try:
        # Update e-commerce platforms to mark as available
        _update_ecommerce_availability.delay(product_id, True)
        
    except Exception as e:
        logger.error(f"Failed to handle product reactivation for {product_id}: {str(e)}")

def _update_ecommerce_availability(product_id, is_available):
    """Update product availability on e-commerce platforms"""
    try:
        from ..models import Product
        from ..services.integration.ecommerce_service import ECommerceIntegrationService
        
        product = Product.objects.get(id=product_id)
        ecommerce_service = ECommerceIntegrationService(tenant=product.tenant)
        
        # Update availability on all configured platforms
        platforms = ['shopify', 'woocommerce', 'magento']  # Configure as needed
        
        for platform in platforms:
            try:
                # This would be implemented in the ecommerce service
                # ecommerce_service.update_product_availability(product, is_available, platform)
                pass
            except Exception as e:
                logger.error(f"Failed to update {platform} availability for product {product.sku}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Failed to update e-commerce availability for product {product_id}: {str(e)}")

def _handle_price_changes(product_id, is_new_product):
    """Handle product price changes"""
    try:
        from ..models import Product
        
        product = Product.objects.get(id=product_id)
        
        if not is_new_product:
            # Sync price changes to e-commerce platforms
            IntegrationSignalMixin.queue_integration_sync(
                'ecommerce', product, 'update', priority='high'
            )
            
            # Notify relevant stakeholders about price changes
            NotificationSignalMixin.queue_notification(
                'product_price_changed',
                product,
                data={
                    'product_name': product.name,
                    'sku': product.sku,
                    'new_selling_price': float(product.selling_price) if product.selling_price else None,
                    'new_cost_price': float(product.cost_price) if product.cost_price else None
                }
            )
    
    except Exception as e:
        logger.error(f"Failed to handle price changes for product {product_id}: {str(e)}")

def _create_stock_items_for_variation(variation_id):
    """Create stock items for product variation"""
    try:
        from ..models import ProductVariation, StockItem, Warehouse
        
        variation = ProductVariation.objects.get(id=variation_id)
        product = variation.product
        
        # Create stock items for all warehouses where the main product exists
        existing_warehouses = StockItem.objects.filter(
            product=product
        ).values_list('warehouse', flat=True).distinct()
        
        warehouses = Warehouse.objects.filter(id__in=existing_warehouses)
        
        stock_items_to_create = []
        for warehouse in warehouses:
            # Create stock item for this variation
            stock_items_to_create.append(
                StockItem(
                    tenant=product.tenant,
                    product=product,  # Variations share the same product
                    warehouse=warehouse,
                    product_variation=variation,
                    quantity_on_hand=0,
                    unit_cost=variation.cost_price or product.cost_price or 0,
                    reorder_level=product.default_reorder_level or 0,
                    maximum_stock_level=product.default_maximum_level or 0
                )
            )
        
        if stock_items_to_create:
            StockItem.objects.bulk_create(stock_items_to_create)
    
    except Exception as e:
        logger.error(f"Failed to create stock items for variation {variation_id}: {str(e)}")

# Add delay methods for async execution
try:
    from ..tasks.celery import (
        create_stock_items_for_all_warehouses as _create_stock_items_task,
        handle_product_updates as _handle_product_updates_task,
        handle_product_deactivation as _handle_product_deactivation_task,
        handle_product_reactivation as _handle_product_reactivation_task,
        update_ecommerce_availability as _update_ecommerce_availability_task,
        handle_price_changes as _handle_price_changes_task,
        create_stock_items_for_variation as _create_stock_items_for_variation_task
    )
    
    _create_stock_items_for_all_warehouses.delay = _create_stock_items_task.delay
    _handle_product_updates.delay = _handle_product_updates_task.delay
    _handle_product_deactivation.delay = _handle_product_deactivation_task.delay
    _handle_product_reactivation.delay = _handle_product_reactivation_task.delay
    _update_ecommerce_availability.delay = _update_ecommerce_availability_task.delay
    _handle_price_changes.delay = _handle_price_changes_task.delay
    _create_stock_items_for_variation.delay = _create_stock_items_for_variation_task.delay

except ImportError:
    # Fallback for synchronous execution
    for func_name in ['_create_stock_items_for_all_warehouses', '_handle_product_updates',
                      '_handle_product_deactivation', '_handle_product_reactivation',
                      '_update_ecommerce_availability', '_handle_price_changes',
                      '_create_stock_items_for_variation']:
        func = locals()[func_name]
        func.delay = func

# SEO and search optimization
@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def update_search_index(sender, instance, created, **kwargs):
    """Update search index for product discovery"""
    if kwargs.get('raw', False):
        return
    
    # Queue search index update
    try:
        from ..tasks.celery import update_product_search_index
        update_product_search_index.delay(instance.id)
    except ImportError:
        # Synchronous fallback
        pass

# Analytics and reporting
@receiver(post_save, sender=Product)
@BaseSignalHandler.safe_signal_execution
def update_product_analytics(sender, instance, created, **kwargs):
    """Update product analytics data"""
    if kwargs.get('raw', False):
        return
    
    # Queue analytics update
    try:
        from ..tasks.celery import update_product_analytics_task
        update_product_analytics_task.delay(instance.tenant_id, instance.id)
    except ImportError:
        pass