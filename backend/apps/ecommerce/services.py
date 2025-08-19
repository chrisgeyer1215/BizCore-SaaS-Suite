from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from decimal import Decimal
import logging
from typing import Dict, List, Optional, Tuple

from .models import (
    EcommerceProduct, Cart, CartItem, Order, OrderItem, 
    PaymentTransaction, Coupon, ShippingMethod, ShippingZone,
    ProductAnalytics, AbandonedCart, ReturnRequest, ProductReview
)
from apps.inventory.services import InventoryService
from apps.crm.models import Customer

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product-related operations"""
    
    @staticmethod
    def get_product_recommendations(product: EcommerceProduct, limit: int = 4) -> List[EcommerceProduct]:
        """Get product recommendations based on various factors"""
        recommendations = []
        
        # Get products from same collections
        collection_products = EcommerceProduct.objects.filter(
            collections__in=product.collections.all(),
            is_published=True,
            status='ACTIVE'
        ).exclude(id=product.id).distinct()[:limit]
        
        recommendations.extend(collection_products)
        
        # Fill remaining slots with similar products
        if len(recommendations) < limit:
            remaining_slots = limit - len(recommendations)
            similar_products = EcommerceProduct.objects.filter(
                vendor=product.vendor,
                is_published=True,
                status='ACTIVE'
            ).exclude(id=product.id).exclude(
                id__in=[p.id for p in recommendations]
            )[:remaining_slots]
            
            recommendations.extend(similar_products)
        
        return recommendations[:limit]
    
    @staticmethod
    def update_product_metrics(product: EcommerceProduct):
        """Update product performance metrics"""
        analytics, created = ProductAnalytics.objects.get_or_create(
            product=product,
            defaults={'tenant': product.tenant}
        )
        
        # Update sales metrics
        order_items = OrderItem.objects.filter(
            product=product,
            order__status__in=['COMPLETED', 'DELIVERED']
        )
        
        analytics.times_purchased = order_items.count()
        
        # Revenue metrics
        revenue_data = order_items.aggregate(
            total_revenue=Sum('line_total'),
            avg_order_value=Avg('line_total')
        )
        
        analytics.total_revenue = revenue_data['total_revenue'] or 0
        analytics.average_order_value = revenue_data['avg_order_value'] or 0
        
        # Cart metrics
        cart_additions = CartItem.objects.filter(product=product).count()
        analytics.times_added_to_cart = cart_additions
        
        # Calculate conversion rate
        if cart_additions > 0:
            conversion_rate = (analytics.times_purchased / cart_additions) * 100
            analytics.conversion_rate = min(conversion_rate, 100)
        
        # Update product-level metrics
        product.sales_count = analytics.times_purchased
        
        # Review metrics
        reviews = ProductReview.objects.filter(
            product=product, 
            status='APPROVED'
        )
        review_stats = reviews.aggregate(
            count=Count('id'),
            avg_rating=Avg('rating')
        )
        
        product.review_count = review_stats['count'] or 0
        product.average_rating = review_stats['avg_rating'] or 0
        
        product.save(update_fields=['sales_count', 'review_count', 'average_rating'])
        analytics.save()
        
        return analytics
    
    @staticmethod
    def sync_inventory_stock(product: EcommerceProduct):
        """Sync stock quantity from inventory system"""
        if not product.inventory_product:
            return
        
        if product.track_quantity:
            # Get available stock from inventory
            available_stock = product.inventory_product.stock_items.filter(
                warehouse__is_sellable=True
            ).aggregate(
                total=Sum('quantity_available')
            )['total'] or 0
            
            product.stock_quantity = max(0, available_stock)
            
            # Update stock status
            if product.stock_quantity <= 0:
                if product.allow_backorders:
                    product.stock_status = 'ON_BACKORDER'
                else:
                    product.stock_status = 'OUT_OF_STOCK'
            else:
                product.stock_status = 'IN_STOCK'
            
            product.save(update_fields=['stock_quantity', 'stock_status'])
    
    @staticmethod
    def check_stock_availability(product: EcommerceProduct, quantity: int, variant=None) -> Tuple[bool, str]:
        """Check if requested quantity is available"""
        if not product.track_quantity:
            return True, "Stock tracking disabled"
        
        available = variant.available_quantity if variant else product.available_inventory
        
        if quantity <= available:
            return True, "In stock"
        elif product.continue_selling_when_out_of_stock:
            return True, "Backorder allowed"
        else:
            return False, f"Only {available} items available"


class CartService:
    """Service for cart operations"""
    
    @staticmethod
    def get_or_create_cart(customer: Customer = None, session_key: str = None) -> Cart:
        """Get or create cart for customer or session"""
        if customer:
            cart, created = Cart.objects.get_or_create(
                tenant=customer.tenant,
                customer=customer,
                status='active',
                defaults={
                    'currency': 'USD',  # Get from settings
                }
            )
        else:
            cart, created = Cart.objects.get_or_create(
                tenant_id=1,  # Get from request context
                session_key=session_key,
                status='active',
                defaults={
                    'currency': 'USD',
                }
            )
        
        return cart
    
    @staticmethod
    def add_to_cart(cart: Cart, product: EcommerceProduct, quantity: int = 1, 
                   variant=None, custom_attributes: dict = None) -> Tuple[CartItem, bool]:
        """Add item to cart"""
        # Check stock availability
        is_available, message = ProductService.check_stock_availability(
            product, quantity, variant
        )
        
        if not is_available:
            raise ValueError(message)
        
        # Get or create cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={
                'tenant': cart.tenant,
                'quantity': quantity,
                'price': variant.effective_price if variant else product.current_price,
                'custom_attributes': custom_attributes or {}
            }
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        # Recalculate cart totals
        CartService.calculate_totals(cart)
        
        return cart_item, created
    
    @staticmethod
    def remove_from_cart(cart: Cart, item_id: int) -> bool:
        """Remove item from cart"""
        try:
            item = cart.items.get(id=item_id)
            item.delete()
            CartService.calculate_totals(cart)
            return True
        except CartItem.DoesNotExist:
            return False
    
    @staticmethod
    def update_cart_item(cart: Cart, item_id: int, quantity: int) -> bool:
        """Update cart item quantity"""
        try:
            item = cart.items.get(id=item_id)
            
            if quantity <= 0:
                item.delete()
            else:
                # Check stock availability
                is_available, message = ProductService.check_stock_availability(
                    item.product, quantity, item.variant
                )
                
                if not is_available:
                    raise ValueError(message)
                
                item.quantity = quantity
                item.save()
            
            CartService.calculate_totals(cart)
            return True
            
        except CartItem.DoesNotExist:
            return False
    
    @staticmethod
    def calculate_totals(cart: Cart):
        """Calculate cart totals"""
        items = cart.items.all()
        
        subtotal = sum(item.line_total for item in items)
        
        # TODO: Calculate tax based on settings and location
        tax_amount = Decimal('0.00')
        
        # TODO: Calculate shipping based on selected method
        shipping_amount = Decimal('0.00')
        
        # Apply discounts
        discount_amount = CartService.calculate_discounts(cart)
        
        cart.subtotal = subtotal
        cart.tax_amount = tax_amount
        cart.shipping_amount = shipping_amount
        cart.discount_amount = discount_amount
        cart.total = subtotal + tax_amount + shipping_amount - discount_amount
        
        cart.save(update_fields=[
            'subtotal', 'tax_amount', 'shipping_amount', 
            'discount_amount', 'total'
        ])
        
        return cart.total
    
    @staticmethod
    def calculate_discounts(cart: Cart) -> Decimal:
        """Calculate total discounts for cart"""
        total_discount = Decimal('0.00')
        
        for coupon_code in cart.discount_codes:
            try:
                coupon = Coupon.objects.get(
                    tenant=cart.tenant,
                    code=coupon_code
                )
                discount_amount = coupon.calculate_discount_amount(cart)
                total_discount += discount_amount
                
            except Coupon.DoesNotExist:
                # Remove invalid coupon
                cart.discount_codes.remove(coupon_code)
                cart.save()
        
        return total_discount
    
    @staticmethod
    def apply_coupon(cart: Cart, coupon_code: str) -> Tuple[bool, str]:
        """Apply coupon to cart"""
        try:
            coupon = Coupon.objects.get(
                tenant=cart.tenant,
                code=coupon_code
            )
            
            can_apply, message = coupon.can_apply_to_cart(cart)
            if not can_apply:
                return False, message
            
            if coupon_code not in cart.discount_codes:
                cart.discount_codes.append(coupon_code)
                cart.save()
                CartService.calculate_totals(cart)
                
                return True, f"Coupon {coupon_code} applied successfully"
            else:
                return False, "Coupon already applied"
                
        except Coupon.DoesNotExist:
            return False, "Invalid coupon code"
    
    @staticmethod
    def remove_coupon(cart: Cart, coupon_code: str) -> bool:
        """Remove coupon from cart"""
        if coupon_code in cart.discount_codes:
            cart.discount_codes.remove(coupon_code)
            cart.save()
            CartService.calculate_totals(cart)
            return True
        return False
    
    @staticmethod
    def mark_as_abandoned(cart: Cart):
        """Mark cart as abandoned for recovery"""
        if cart.customer and cart.status == 'active':
            cart.status = 'abandoned'
            cart.save()
            
            # Create abandoned cart record
            abandoned_cart, created = AbandonedCart.objects.get_or_create(
                cart=cart,
                defaults={
                    'tenant': cart.tenant,
                }
            )
            
            return abandoned_cart
        return None


class OrderService:
    """Service for order operations"""
    
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(cart: Cart, customer_info: dict, 
                              shipping_info: dict, payment_info: dict) -> Order:
        """Create order from cart"""
        
        # Create order
        order = Order.objects.create(
            tenant=cart.tenant,
            customer=cart.customer,
            customer_email=customer_info.get('email'),
            customer_phone=customer_info.get('phone'),
            
            # Financial info
            currency=cart.currency,
            subtotal=cart.subtotal,
            tax_amount=cart.tax_amount,
            shipping_amount=cart.shipping_amount,
            discount_amount=cart.discount_amount,
            total_amount=cart.total,
            
            # Addresses
            billing_address=customer_info,
            shipping_address=shipping_info,
            
            # Payment info
            payment_method=payment_info.get('method'),
            payment_gateway=payment_info.get('gateway'),
            
            # Applied discounts
            coupon_codes=cart.discount_codes,
            applied_discounts=cart.applied_coupons,
            
            # Source
            source_cart=cart,
            source_name=payment_info.get('source', 'web'),
        )
        
        # Create order items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                tenant=cart.tenant,
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                title=cart_item.product.title,
                variant_title=cart_item.variant.title if cart_item.variant else '',
                sku=cart_item.variant.sku if cart_item.variant else cart_item.product.sku,
                quantity=cart_item.quantity,
                price=cart_item.price,
                line_total=cart_item.line_total,
                custom_attributes=cart_item.custom_attributes,
            )
        
        # Update coupon usage
        for coupon_code in cart.discount_codes:
            try:
                coupon = Coupon.objects.get(tenant=cart.tenant, code=coupon_code)
                coupon.usage_count = F('usage_count') + 1
                coupon.save()
            except Coupon.DoesNotExist:
                pass
        
        # Mark cart as completed
        cart.status = 'completed'
        cart.save()
        
        return order
    
    @staticmethod
    def calculate_shipping_rates(cart: Cart, shipping_address: dict) -> List[dict]:
        """Calculate available shipping rates"""
        country = shipping_address.get('country')
        state = shipping_address.get('state')
        
        # Find applicable shipping zones
        zones = ShippingZone.objects.filter(
            tenant=cart.tenant,
            is_active=True,
            countries__contains=[country]
        )
        
        shipping_rates = []
        total_weight = sum(
            (item.product.weight or 0) * item.quantity 
            for item in cart.items.all()
        )
        
        for zone in zones:
            for method in zone.shipping_methods.filter(is_active=True):
                rate = method.calculate_rate(cart.subtotal, total_weight)
                if rate is not None:
                    shipping_rates.append({
                        'method_id': method.id,
                        'name': method.name,
                        'description': method.description,
                        'rate': rate,
                        'estimated_days_min': method.estimated_delivery_days_min,
                        'estimated_days_max': method.estimated_delivery_days_max,
                    })
        
        return shipping_rates
    
    @staticmethod
    def update_order_status(order: Order, status: str, user=None):
        """Update order status with logging"""
        old_status = order.status
        order.status = status
        
        # Set timestamps based on status
        now = timezone.now()
        if status == 'CONFIRMED' and not order.confirmed_at:
            order.confirmed_at = now
        elif status == 'SHIPPED' and not order.shipped_date:
            order.shipped_date = now
        elif status == 'DELIVERED' and not order.delivered_date:
            order.delivered_date = now
        elif status == 'CANCELLED' and not order.cancelled_at:
            order.cancelled_at = now
        
        if user:
            order.processed_by = user
            order.processed_at = now
        
        order.save()
        
        # Send notifications
        OrderService.send_status_notification(order, old_status, status)
        
        logger.info(f"Order {order.order_number} status changed from {old_status} to {status}")
    
    @staticmethod
    def send_status_notification(order: Order, old_status: str, new_status: str):
        """Send order status notification email"""
        if new_status == 'CONFIRMED':
            OrderService.send_order_confirmation(order)
        elif new_status == 'SHIPPED':
            OrderService.send_shipping_notification(order)
    
    @staticmethod
    def send_order_confirmation(order: Order):
        """Send order confirmation email"""
        try:
            subject = f'Order Confirmation #{order.order_number}'
            html_message = render_to_string('ecommerce/order_confirmation.html', {
                'order': order,
                'items': order.items.all(),
            })
            
            send_mail(
                subject=subject,
                message='',  # Plain text version
                from_email=None,  # Use default
                recipient_list=[order.customer_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Order confirmation sent for {order.order_number}")
            
        except Exception as e:
            logger.error(f"Failed to send order confirmation for {order.order_number}: {e}")
    
    @staticmethod
    def send_shipping_notification(order: Order):
        """Send shipping notification email"""
        try:
            subject = f'Your Order #{order.order_number} Has Shipped'
            html_message = render_to_string('ecommerce/shipping_notification.html', {
                'order': order,
                'tracking_number': order.tracking_number,
                'tracking_url': order.tracking_url,
            })
            
            send_mail(
                subject=subject,
                message='',
                from_email=None,
                recipient_list=[order.customer_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Shipping notification sent for {order.order_number}")
            
        except Exception as e:
            logger.error(f"Failed to send shipping notification for {order.order_number}: {e}")


class PaymentService:
    """Service for payment operations"""
    
    @staticmethod
    def mark_order_as_paid(order as paid and update inventory"""
        with transaction.atomic():
            # Update order status
            order.payment_status = 'PAID'
            order.payment_date = timezone.now()
            
            if order.status == 'PENDING':
                order.status = 'CONFIRMED'
                order.confirmed_at = timezone.now()
            
            order.save()
            
            # Deduct inventory based on settings
            settings = order.tenant.ecommerce_settings.first()
            if settings and settings.deduct_inventory_on == 'PAYMENT':
                PaymentService.deduct_inventory(order)
            
            # Send confirmation email
            OrderService.send_order_confirmation(order)
            
            logger.info(f"Order {order.order_number} marked as paid")
    
    @staticmethod
    def deduct_inventory(order: Order):
        """Deduct inventory for order items"""
        for item in order.items.all():
            if item.product.track_quantity:
                try:
                    # Use inventory service to deduct stock
                    InventoryService.allocate_stock(
                        product=item.product.inventory_product,
                        quantity=item.quantity,
                        reference=f"Order-{order.order_number}"
                    )
                    
                    # Update e-commerce product stock
                    ProductService.sync_inventory_stock(item.product)
                    
                except Exception as e:
                    logger.error(f"Failed to deduct inventory for {item.product.title}: {e}")
    
    @staticmethod
    def process_refund(order: Order, amount: Decimal, reason: str = '', user=None) -> PaymentTransaction:
        """Process refund for order"""
        with transaction.atomic():
            # Create refund transaction
            refund_transaction = PaymentTransaction.objects.create(
                tenant=order.tenant,
                order=order,
                transaction_type='REFUND',
                payment_method=order.payment_method,
                payment_gateway=order.payment_gateway,
                amount=amount,
                currency=order.currency,
                status='SUCCESS',  # Assume successful for now
                notes=reason
            )
            
            # Update order status if full refund
            if amount >= order.total_amount:
                order.payment_status = 'REFUNDED'
                order.status = 'REFUNDED'
            else:
                order.payment_status = 'PARTIAL'
            
            order.save()
            
            # Restore inventory if needed
            PaymentService.restore_inventory(order, amount, order.total_amount)
            
            logger.info(f"Refund of {amount} processed for order {order.order_number}")
            
            return refund_transaction
    
    @staticmethod
    def restore_inventory(order: Order, refund_amount: Decimal, total_amount: Decimal):
        """Restore inventory for refunded items"""
        refund_ratio = refund_amount / total_amount
        
        for item in order.items.all():
            if item.product.track_quantity:
                quantity_to_restore = int(item.quantity * refund_ratio)
                
                if quantity_to_restore > 0:
                    try:
                        # Use inventory service to restore stock
                        InventoryService.restore_stock(
                            product=item.product.inventory_product,
                            quantity=quantity_to_restore,
                            reference=f"Refund-{order.order_number}"
                        )
                        
                        # Update e-commerce product stock
                        ProductService.sync_inventory_stock(item.product)
                        
                    except Exception as e:
                        logger.error(f"Failed to restore inventory for {item.product.title}: {e}")


class ReturnService:
    """Service for return/refund operations"""
    
    @staticmethod
    def process_return_request(return_request: ReturnRequest, approve: bool = True, user=None):
        """Process return request"""
        with transaction.atomic():
            if approve:
                return_request.status = 'APPROVED'
                return_request.approved_at = timezone.now()
            else:
                return_request.status = 'REJECTED'
            
            return_request.processed_by = user
            return_request.processed_at = timezone.now()
            return_request.save()
            
            if approve:
                # Calculate refund amount
                total_refund = sum(
                    item.refund_amount for item in return_request.items.all()
                )
                
                if total_refund > 0:
                    # Process refund
                    PaymentService.process_refund(
                        order=return_request.order,
                        amount=total_refund,
                        reason=f"Return request #{return_request.return_number}",
                        user=user
                    )
                    
                    return_request.refund_amount = total_refund
                    return_request.status = 'REFUNDED'
                    return_request.refunded_at = timezone.now()
                    return_request.save()
            
            logger.info(f"Return request {return_request.return_number} {'approved' if approve else 'rejected'}")


class AnalyticsService:
    """Service for analytics and reporting"""
    
    @staticmethod
    def get_sales_summary(tenant, date_from=None, date_to=None) -> dict:
        """Get sales summary for date range"""
        orders = Order.objects.filter(
            tenant=tenant,
            status__in=['COMPLETED', 'DELIVERED']
        )
        
        if date_from:
            orders = orders.filter(order_date__gte=date_from)
        if date_to:
            orders = orders.filter(order_date__lte=date_to)
        
        summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            average_order_value=Avg('total_amount'),
            total_items=Sum('items__quantity')
        )
        
        return {
            'total_orders': summary['total_orders'] or 0,
            'total_revenue': summary['total_revenue'] or Decimal('0'),
            'average_order_value': summary['average_order_value'] or Decimal('0'),
            'total_items': summary['total_items'] or 0,
        }
    
    @staticmethod
    def get_top_products(tenant, limit: int = 10, date_from=None, date_to=None) -> List[dict]:
        """Get top-selling products"""
        order_items = OrderItem.objects.filter(
            tenant=tenant,
            order__status__in=['COMPLETED', 'DELIVERED']
        )
        
        if date_from:
            order_items = order_items.filter(order__order_date__gte=date_from)
        if date_to:
            order_items = order_items.filter(order__order_date__lte=date_to)
        
        top_products = order_items.values(
            'product__id',
            'product__title'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('line_total')
        ).order_by('-total_sold')[:limit]
        
        return list(top_products)
    
    @staticmethod
    def get_abandoned_cart_recovery_stats(tenant) -> dict:
        """Get abandoned cart recovery statistics"""
        abandoned_carts = AbandonedCart.objects.filter(tenant=tenant)
        
        total_abandoned = abandoned_carts.count()
        recovered = abandoned_carts.filter(recovered=True).count()
        recovery_rate = (recovered / total_abandoned * 100) if total_abandoned > 0 else 0
        
        return {
            'total_abandoned': total_abandoned,
            'recovered': recovered,
            'recovery_rate': round(recovery_rate, 2),
        }
