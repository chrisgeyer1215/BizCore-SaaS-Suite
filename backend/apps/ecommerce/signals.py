from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from .models import (
    EcommerceProduct, ProductVariant, Cart, CartItem, Order, OrderItem,
    ProductReview, Coupon, CouponUsage, Collection, CollectionProduct
)
from .services import ProductService, CartService, AnalyticsService
from .tasks import (
    update_product_analytics, sync_inventory_stock, 
    send_abandoned_cart_email, update_search_index
)
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=EcommerceProduct)
def product_post_save(sender, instance, created, **kwargs):
    """Handle product save events"""
    if created:
        logger.info(f"New product created: {instance.title}")
        
        # Create analytics record
        from .models import ProductAnalytics
        ProductAnalytics.objects.get_or_create(
            product=instance,
            defaults={'tenant': instance.tenant}
        )
        
        # Schedule search index update
        update_search_index.delay(instance.id)
    else:
        # Clear product cache
        cache_key = f"product_{instance.tenant_id}_{instance.id}"
        cache.delete(cache_key)
        
        # Update search index if significant fields changed
        update_fields = kwargs.get('update_fields', [])
        search_fields = ['title', 'description', 'short_description', 'tags']
        
        if not update_fields or any(field in update_fields for field in search_fields):
            update_search_index.delay(instance.id)


@receiver(pre_save, sender=EcommerceProduct)
def product_pre_save(sender, instance, **kwargs):
    """Handle product pre-save events"""
    if instance.pk:
        try:
            old_instance = EcommerceProduct.objects.get(pk=instance.pk)
            
            # Check if stock quantity changed significantly
            if old_instance.stock_quantity != instance.stock_quantity:
                # Log stock change
                logger.info(
                    f"Stock changed for {instance.title}: "
                    f"{old_instance.stock_quantity} -> {instance.stock_quantity}"
                )
                
                # Send low stock alert if needed
                if (instance.stock_quantity <= instance.low_stock_threshold and 
                    old_instance.stock_quantity > instance.low_stock_threshold):
                    # Schedule low stock notification
                    from .tasks import send_low_stock_alert
                    send_low_stock_alert.delay(instance.id)
        
        except EcommerceProduct.DoesNotExist:
            pass


@receiver(post_save, sender=ProductVariant)
def variant_post_save(sender, instance, created, **kwargs):
    """Handle variant save events"""
    if created:
        # Update parent product to indicate it has variants
        instance.ecommerce_product.has_variants = True
        instance.ecommerce_product.save(update_fields=['has_variants'])
    
    # Clear product cache
    cache_key = f"product_{instance.tenant_id}_{instance.ecommerce_product_id}"
    cache.delete(cache_key)


@receiver(post_delete, sender=ProductVariant)
def variant_post_delete(sender, instance, **kwargs):
    """Handle variant deletion"""
    product = instance.ecommerce_product
    
    # Check if product still has variants
    if not product.variants.exists():
        product.has_variants = False
        product.save(update_fields=['has_variants'])
    
    # Clear product cache
    cache_key = f"product_{instance.tenant_id}_{product.id}"
    cache.delete(cache_key)


@receiver(post_save, sender=CartItem)
def cart_item_post_save(sender, instance, created, **kwargs):
    """Handle cart item changes"""
    # Recalculate cart totals
    CartService.calculate_totals(instance.cart)
    
    if created:
        # Track cart addition for analytics
        update_product_analytics.delay(instance.product.id)
        
        # Clear cart cache
        cache_key = f"cart_{instance.cart.cart_id}"
        cache.delete(cache_key)


@receiver(post_delete, sender=CartItem)
def cart_item_post_delete(sender, instance, **kwargs):
    """Handle cart item deletion"""
    # Recalculate cart totals
    CartService.calculate_totals(instance.cart)
    
    # Clear cart cache
    cache_key = f"cart_{instance.cart.cart_id}"
    cache.delete(cache_key)


@receiver(post_save, sender=Cart)
def cart_post_save(sender, instance, created, **kwargs):
    """Handle cart save events"""
    if not created:
        # Check if cart should be marked as abandoned
        if (instance.status == 'active' and 
            instance.customer and 
            instance.updated_at < timezone.now() - timezone.timedelta(hours=24)):
            
            # Schedule abandoned cart email
            send_abandoned_cart_email.delay(instance.id)


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """Handle order save events"""
    if created:
        logger.info(f"New order created: {instance.order_number}")
        
        # Update customer analytics
        if instance.customer:
            from .tasks import update_customer_analytics
            update_customer_analytics.delay(instance.customer.id)
        
        # Clear relevant caches
        cache.delete(f"orders_stats_{instance.tenant_id}")
    
    # Update order status cache
    cache_key = f"order_{instance.order_number}"
    cache.set(cache_key, {
        'status': instance.status,
        'payment_status': instance.payment_status,
        'total_amount': str(instance.total_amount)
    }, timeout=3600)


@receiver(post_save, sender=OrderItem)
def order_item_post_save(sender, instance, created, **kwargs):
    """Handle order item events"""
    if created:
        # Update product analytics
        update_product_analytics.delay(instance.product.id)
        
        # Sync inventory if needed
        if instance.product.track_quantity:
            sync_inventory_stock.delay(instance.product.id)


@receiver(post_save, sender=ProductReview)
def review_post_save(sender, instance, created, **kwargs):
    """Handle review save events"""
    # Update product rating cache
    if instance.status == 'APPROVED':
        # Schedule product metrics update
        update_product_analytics.delay(instance.product.id)
        
        # Clear product cache
        cache_key = f"product_{instance.tenant_id}_{instance.product_id}"
        cache.delete(cache_key)


@receiver(post_save, sender=Coupon)
def coupon_post_save(sender, instance, created, **kwargs):
    """Handle coupon save events"""
    # Clear coupon cache
    cache_key = f"coupon_{instance.tenant_id}_{instance.code}"
    cache.delete(cache_key)
    
    if created:
        logger.info(f"New coupon created: {instance.code}")


@receiver(post_save, sender=CouponUsage)
def coupon_usage_post_save(sender, instance, created, **kwargs):
    """Handle coupon usage events"""
    if created:
        # Update coupon usage count
        instance.coupon.usage_count = instance.coupon.usages.count()
        instance.coupon.save(update_fields=['usage_count'])
        
        # Clear coupon cache
        cache_key = f"coupon_{instance.tenant_id}_{instance.coupon.code}"
        cache.delete(cache_key)


@receiver(m2m_changed, sender=CollectionProduct)
def collection_products_changed(sender, instance, action, **kwargs):
    """Handle collection-product relationship changes"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Update collection product count
        instance.products_count = instance.products.filter(
            is_published=True,
            status='ACTIVE'
        ).count()
        instance.save(update_fields=['products_count'])
        
        # Clear collection cache
        cache_key = f"collection_{instance.tenant_id}_{instance.slug}"
        cache.delete(cache_key)


# Cache invalidation signals
@receiver([post_save, post_delete], sender=EcommerceProduct)
def invalidate_product_caches(sender, instance, **kwargs):
    """Invalidate product-related caches"""
    cache_keys = [
        f"products_featured_{instance.tenant_id}",
        f"products_bestsellers_{instance.tenant_id}",
        f"products_new_{instance.tenant_id}",
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Invalidate collection caches
    for collection in instance.collections.all():
        cache.delete(f"collection_products_{collection.id}")


@receiver([post_save, post_delete], sender=Order)
def invalidate_order_caches(sender, instance, **kwargs):
    """Invalidate order-related caches"""
    cache_keys = [
        f"orders_stats_{instance.tenant_id}",
        f"customer_orders_{instance.customer_id}" if instance.customer else None,
    ]
    
    for key in filter(None, cache_keys):
        cache.delete(key)


# Search index update signals
@receiver(post_save, sender=EcommerceProduct)
def update_product_search_index(sender, instance, **kwargs):
    """Update search index when product changes"""
    if instance.is_published and instance.status == 'ACTIVE':
        update_search_index.delay(instance.id)


@receiver(post_delete, sender=EcommerceProduct)
def remove_from_search_index(sender, instance, **kwargs):
    """Remove product from search index"""
    from .tasks import remove_from_search_index
    remove_from_search_index.delay(instance.id)
