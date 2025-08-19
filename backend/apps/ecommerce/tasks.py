from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
import logging

from .models import (
    EcommerceProduct, Cart, Order, ProductAnalytics, AbandonedCart,
    ProductReview, Coupon
)
from .services import ProductService, CartService, AnalyticsService
from apps.crm.models import Customer

logger = logging.getLogger(__name__)


@shared_task
def update_product_analytics(product_id):
    """Update analytics for a specific product"""
    try:
        product = EcommerceProduct.objects.get(id=product_id)
        analytics = ProductService.update_product_metrics(product)
        
        logger.info(f"Updated analytics for product {product.title}")
        return f"Analytics updated for product {product_id}"
        
    except EcommerceProduct.DoesNotExist:
        logger.error(f"Product {product_id} not found for analytics update")
        return f"Product {product_id} not found"


@shared_task
def bulk_update_product_analytics():
    """Update analytics for all products"""
    products = EcommerceProduct.objects.filter(is_published=True)
    updated_count = 0
    
    for product in products.iterator():
        try:
            ProductService.update_product_metrics(product)
            updated_count += 1
            
            if updated_count % 100 == 0:
                logger.info(f"Updated analytics for {updated_count} products")
                
        except Exception as e:
            logger.error(f"Error updating analytics for product {product.id}: {e}")
    
    logger.info(f"Bulk analytics update completed: {updated_count} products updated")
    return f"Updated analytics for {updated_count} products"


@shared_task
def sync_inventory_stock(product_id):
    """Sync inventory stock for a specific product"""
    try:
        product = EcommerceProduct.objects.get(id=product_id)
        ProductService.sync_inventory_stock(product)
        
        logger.info(f"Synced inventory for product {product.title}")
        return f"Inventory synced for product {product_id}"
        
    except EcommerceProduct.DoesNotExist:
        logger.error(f"Product {product_id} not found for inventory sync")
        return f"Product {product_id} not found"


@shared_task
def bulk_sync_inventory():
    """Sync inventory for all products"""
    products = EcommerceProduct.objects.filter(track_quantity=True)
    synced_count = 0
    
    for product in products.iterator():
        try:
            ProductService.sync_inventory_stock(product)
            synced_count += 1
            
            if synced_count % 100 == 0:
                logger.info(f"Synced inventory for {synced_count} products")
                
        except Exception as e:
            logger.error(f"Error syncing inventory for product {product.id}: {e}")
    
    logger.info(f"Bulk inventory sync completed: {synced_count} products synced")
    return f"Synced inventory for {synced_count} products"


@shared_task
def send_abandoned_cart_email(cart_id):
    """Send abandoned cart recovery email"""
    try:
        cart = Cart.objects.get(id=cart_id)
        
        if not cart.customer or cart.status != 'active':
            return f"Cart {cart_id} not eligible for recovery email"
        
        # Check if cart is still abandoned (not converted to order)
        if hasattr(cart, 'orders') and cart.orders.exists():
            return f"Cart {cart_id} already converted to order"
        
        # Get or create abandoned cart record
        abandoned_cart, created = AbandonedCart.objects.get_or_create(
            cart=cart,
            defaults={'tenant': cart.tenant}
        )
        
        # Check recovery email limits
        if abandoned_cart.recovery_email_count >= 3:
            return f"Max recovery emails sent for cart {cart_id}"
        
        # Send email
        subject = "You left something in your cart!"
        html_message = render_to_string('ecommerce/abandoned_cart_email.html', {
            'cart': cart,
            'customer': cart.customer,
            'items': cart.items.all(),
            'recovery_url': f"{settings.FRONTEND_URL}/cart/{cart.cart_id}"
        })
        
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[cart.customer.email],
            html_message=html_message,
            fail_silently=False
        )
        
        # Update abandoned cart record
        abandoned_cart.recovery_email_sent = True
        abandoned_cart.recovery_email_sent_at = timezone.now()
        abandoned_cart.recovery_email_count += 1
        abandoned_cart.save()
        
        logger.info(f"Abandoned cart email sent for cart {cart_id}")
        return f"Recovery email sent for cart {cart_id}"
        
    except Cart.DoesNotExist:
        logger.error(f"Cart {cart_id} not found for abandoned cart email")
        return f"Cart {cart_id} not found"
    except Exception as e:
        logger.error(f"Error sending abandoned cart email for cart {cart_id}: {e}")
        return f"Error sending email for cart {cart_id}: {str(e)}"


@shared_task
def process_abandoned_carts():
    """Process abandoned carts and send recovery emails"""
    # Find carts abandoned for 2+ hours
    cutoff_time = timezone.now() - timedelta(hours=2)
    
    abandoned_carts = Cart.objects.filter(
        status='active',
        customer__isnull=False,
        updated_at__lt=cutoff_time
    ).exclude(
        orders__isnull=False  # Exclude carts that became orders
    )
    
    processed_count = 0
    
    for cart in abandoned_carts:
        # Mark as abandoned
        cart.status = 'abandoned'
        cart.save()
        
        # Schedule recovery email
        send_abandoned_cart_email.delay(cart.id)
        processed_count += 1
    
    logger.info(f"Processed {processed_count} abandoned carts")
    return f"Processed {processed_count} abandoned carts"


@shared_task
def cleanup_old_carts():
    """Clean up old abandoned carts"""
    # Delete carts older than 30 days
    cutoff_date = timezone.now() - timedelta(days=30)
    
    old_carts = Cart.objects.filter(
        status__in=['abandoned', 'expired'],
        updated_at__lt=cutoff_date
    )
    
    count = old_carts.count()
    old_carts.delete()
    
    logger.info(f"Cleaned up {count} old carts")
    return f"Cleaned up {count} old carts"


@shared_task
def send_low_stock_alert(product_id):
    """Send low stock alert to administrators"""
    try:
        product = EcommerceProduct.objects.get(id=product_id)
        
        # Get admin email addresses
        admin_emails = settings.ADMIN_EMAIL_LIST if hasattr(settings, 'ADMIN_EMAIL_LIST') else []
        
        if not admin_emails:
            return "No admin emails configured"
        
        subject = f"Low Stock Alert: {product.title}"
        html_message = render_to_string('ecommerce/low_stock_alert.html', {
            'product': product,
            'current_stock': product.stock_quantity,
            'threshold': product.low_stock_threshold,
        })
        
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Low stock alert sent for product {product.title}")
        return f"Low stock alert sent for product {product_id}"
        
    except EcommerceProduct.DoesNotExist:
        logger.error(f"Product {product_id} not found for low stock alert")
        return f"Product {product_id} not found"
    except Exception as e:
        logger.error(f"Error sending low stock alert for product {product_id}: {e}")
        return f"Error sending low stock alert: {str(e)}"


@shared_task
def update_product_ratings():
    """Update product ratings based on reviews"""
    products_updated = 0
    
    products = EcommerceProduct.objects.filter(is_published=True)
    
    for product in products.iterator():
        reviews = ProductReview.objects.filter(
            product=product,
            status='APPROVED'
        )
        
        if reviews.exists():
            avg_rating = reviews.aggregate(
                avg=models.Avg('rating')
            )['avg']
            
            review_count = reviews.count()
            
            if product.average_rating != avg_rating or product.review_count != review_count:
                product.average_rating = avg_rating or 0
                product.review_count = review_count
                product.save(update_fields=['average_rating', 'review_count'])
                products_updated += 1
    
    logger.info(f"Updated ratings for {products_updated} products")
    return f"Updated ratings for {products_updated} products"


@shared_task
def expire_coupons():
    """Expire old coupons"""
    now = timezone.now()
    
    expired_coupons = Coupon.objects.filter(
        is_active=True,
        valid_until__lt=now
    )
    
    count = expired_coupons.update(is_active=False)
    
    logger.info(f"Expired {count} coupons")
    return f"Expired {count} coupons"


@shared_task
def generate_daily_sales_report():
    """Generate daily sales report"""
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Get yesterday's orders
    orders = Order.objects.filter(
        order_date__date=yesterday,
        status__in=['COMPLETED', 'DELIVERED']
    )
    
    if not orders.exists():
        return "No orders to report"
    
    # Calculate metrics
    metrics = orders.aggregate(
        total_orders=models.Count('id'),
        total_revenue=models.Sum('total_amount'),
        average_order_value=models.Avg('total_amount')
    )
    
    # Get top products
    top_products = orders.values(
        'items__product__title'
    ).annotate(
        quantity_sold=models.Sum('items__quantity')
    ).order_by('-quantity_sold')[:5]
    
    # Send report email
    admin_emails = getattr(settings, 'ADMIN_EMAIL_LIST', [])
    
    if admin_emails:
        subject = f"Daily Sales Report - {yesterday}"
        html_message = render_to_string('ecommerce/daily_sales_report.html', {
            'date': yesterday,
            'metrics': metrics,
            'top_products': top_products,
        })
        
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            html_message=html_message,
            fail_silently=False
        )
    
    logger.info(f"Daily sales report generated for {yesterday}")
    return f"Daily sales report generated for {yesterday}"


@shared_task
def update_search_index(product_id):
    """Update search index for product"""
    try:
        product = EcommerceProduct.objects.get(id=product_id)
        
        # Update Elasticsearch index (if using)
        # from django_elasticsearch_dsl.registries import registry
        # registry.update(product)
        
        # Or update other search backend
        # This is a placeholder for actual search implementation
        
        logger.info(f"Search index updated for product {product.title}")
        return f"Search index updated for product {product_id}"
        
    except EcommerceProduct.DoesNotExist:
        logger.error(f"Product {product_id} not found for search index update")
        return f"Product {product_id} not found"


@shared_task
def remove_from_search_index(product_id):
    """Remove product from search index"""
    try:
        # Remove from Elasticsearch index (if using)
        # This is a placeholder for actual search implementation
        
        logger.info(f"Product {product_id} removed from search index")
        return f"Product {product_id} removed from search index"
        
    except Exception as e:
        logger.error(f"Error removing product {product_id} from search index: {e}")
        return f"Error removing product {product_id} from search index"


@shared_task
def update_customer_analytics(customer_id):
    """Update customer analytics"""
    try:
        customer = Customer.objects.get(id=customer_id)
        
        # Calculate customer metrics
        orders = Order.objects.filter(
            customer=customer,
            status__in=['COMPLETED', 'DELIVERED']
        )
        
        metrics = orders.aggregate(
            total_orders=models.Count('id'),
            total_spent=models.Sum('total_amount'),
            average_order_value=models.Avg('total_amount')
        )
        
        # Update customer record with metrics
        # This would depend on your customer analytics model
        
        logger.info(f"Customer analytics updated for {customer.name}")
        return f"Customer analytics updated for {customer_id}"
        
    except Customer.DoesNotExist:
        logger.error(f"Customer {customer_id} not found for analytics update")
        return f"Customer {customer_id} not found"


# Periodic tasks (configure in celery beat)
@shared_task
def hourly_maintenance():
    """Hourly maintenance tasks"""
    tasks_run = []
    
    # Process abandoned carts
    result = process_abandoned_carts()
    tasks_run.append(f"Abandoned carts: {result}")
    
    # Expire coupons
    result = expire_coupons()
    tasks_run.append(f"Expire coupons: {result}")
    
    return f"Hourly maintenance completed: {', '.join(tasks_run)}"


@shared_task
def daily_maintenance():
    """Daily maintenance tasks"""
    tasks_run = []
    
    # Clean up old carts
    result = cleanup_old_carts()
    tasks_run.append(f"Cleanup carts: {result}")
    
    # Update product ratings
    result = update_product_ratings()
    tasks_run.append(f"Update ratings: {result}")
    
    # Generate sales report
    result = generate_daily_sales_report()
    tasks_run.append(f"Sales report: {result}")
    
    # Update analytics
    result = bulk_update_product_analytics()
    tasks_run.append(f"Analytics: {result}")
    
    return f"Daily maintenance completed: {', '.join(tasks_run)}"
