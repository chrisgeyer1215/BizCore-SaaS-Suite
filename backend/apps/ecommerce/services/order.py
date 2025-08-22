"""
E-Commerce Order Service
Handles order creation, processing, fulfillment, and management
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from typing import Optional, Dict, List, Union
import uuid

from .base import BaseEcommerceService, ServiceError, ValidationError as ServiceValidationError
from ..models import (
    Order, OrderItem, OrderStatusHistory, OrderNote, OrderTag,
    Cart, CartItem, Customer, Product, ProductVariant,
    ShippingAddress, BillingAddress, ShippingMethod, PaymentMethod,
    Discount, GiftCard, TaxRate, Refund, Return
)


class OrderService(BaseEcommerceService):
    """Service for managing order operations"""
    
    def create_order_from_cart(self, cart: Cart, order_data: Dict) -> Order:
        """Create order from cart"""
        try:
            with transaction.atomic():
                # Validate cart
                validation_result = self.validate_cart_for_order(cart)
                if not validation_result['is_valid']:
                    raise ServiceValidationError(
                        "Cart validation failed",
                        details={'errors': validation_result['errors']}
                    )
                
                # Create order
                order = self.create_order_record(cart, order_data)
                
                # Create order items
                self.create_order_items(order, cart)
                
                # Create addresses
                self.create_order_addresses(order, order_data)
                
                # Apply discounts and gift cards
                self.apply_order_discounts(order, order_data)
                self.apply_gift_cards(order, order_data)
                
                # Calculate final totals
                self.calculate_order_totals(order)
                
                # Set initial status
                self.create_status_history(
                    order, 
                    'pending', 
                    'Order created from cart',
                    order_data.get('created_by')
                )
                
                # Log order creation
                self.log_info(f"Order {order.order_number} created", {
                    'order_id': str(order.id),
                    'customer_id': str(order.customer.id) if order.customer else None,
                    'total_amount': str(order.total_amount)
                })
                
                return order
                
        except Exception as e:
            self.log_error("Order creation failed", e, {
                'cart_id': str(cart.id),
                'order_data': str(order_data)
            })
            raise
    
    def validate_cart_for_order(self, cart: Cart) -> Dict:
        """Validate cart can be converted to order"""
        errors = []
        
        # Check cart has items
        if cart.items.count() == 0:
            errors.append("Cart is empty")
            return {'is_valid': False, 'errors': errors}
        
        # Check inventory availability
        for item in cart.items.select_related('product', 'product_variant'):
            if not self.check_item_availability(item):
                errors.append(f"{item.product.name} is no longer available")
        
        # Check product status
        for item in cart.items.select_related('product'):
            if not item.product.is_active or item.product.status != 'PUBLISHED':
                errors.append(f"{item.product.name} has been discontinued")
        
        # Check minimum order requirements
        min_order_amount = self.get_minimum_order_amount()
        if min_order_amount and cart.subtotal < min_order_amount:
            errors.append(f"Minimum order amount is {self.format_currency(min_order_amount)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def create_order_record(self, cart: Cart, order_data: Dict) -> Order:
        """Create the main order record"""
        order = Order.objects.create(
            tenant=self.tenant,
            order_number=self.generate_order_number(),
            customer=cart.customer,
            email=self.get_customer_email(cart, order_data),
            currency=cart.currency,
            status='pending',
            
            # Guest information
            guest_first_name=order_data.get('guest_info', {}).get('first_name', ''),
            guest_last_name=order_data.get('guest_info', {}).get('last_name', ''),
            guest_email=order_data.get('guest_info', {}).get('email', ''),
            guest_phone=order_data.get('guest_info', {}).get('phone', ''),
            
            # Shipping and payment methods
            shipping_method_name=order_data.get('shipping_method', {}).get('name', ''),
            shipping_cost=Decimal(order_data.get('shipping_method', {}).get('cost', '0.00')),
            payment_method=order_data.get('payment_method', ''),
            
            # Notes
            order_notes=order_data.get('order_notes', ''),
            
            # Tracking
            source='web',
            source_details={'cart_id': str(cart.id)},
            
            # Timestamps
            order_date=timezone.now()
        )
        
        return order
    
    def create_order_items(self, order: Order, cart: Cart):
        """Create order items from cart items"""
        for cart_item in cart.items.select_related('product', 'product_variant'):
            OrderItem.objects.create(
                tenant=self.tenant,
                order=order,
                product=cart_item.product,
                product_variant=cart_item.product_variant,
                product_name=cart_item.product.name,
                product_sku=cart_item.product_variant.sku if cart_item.product_variant else cart_item.product.sku,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                total_price=cart_item.total_price,
                custom_attributes=cart_item.custom_attributes,
                
                # Snapshot product details for historical record
                product_details={
                    'name': cart_item.product.name,
                    'description': cart_item.product.description,
                    'weight': float(cart_item.product.weight) if cart_item.product.weight else None,
                    'image_url': cart_item.product.featured_image.url if cart_item.product.featured_image else None
                }
            )
    
    def create_order_addresses(self, order: Order, order_data: Dict):
        """Create shipping and billing addresses for order"""
        # Shipping address
        shipping_data = order_data.get('shipping_address', {})
        if shipping_data:
            shipping_address = ShippingAddress.objects.create(
                tenant=self.tenant,
                order=order,
                **self.parse_address(shipping_data)
            )
            order.shipping_address = shipping_address
        
        # Billing address
        billing_data = order_data.get('billing_address', {})
        if order_data.get('same_billing', False):
            billing_data = shipping_data
        
        if billing_data:
            billing_address = BillingAddress.objects.create(
                tenant=self.tenant,
                order=order,
                **self.parse_address(billing_data)
            )
            order.billing_address = billing_address
        
        order.save(update_fields=['shipping_address', 'billing_address'])
    
    def apply_order_discounts(self, order: Order, order_data: Dict):
        """Apply discounts to order"""
        applied_discounts = order_data.get('applied_discounts', [])
        
        for discount_code in applied_discounts:
            try:
                discount = Discount.objects.get(
                    tenant=self.tenant,
                    code=discount_code,
                    is_active=True
                )
                
                # Calculate discount amount
                discount_amount = self.calculate_discount_amount(discount, order)
                
                if discount_amount > 0:
                    # Create discount application record
                    # This would be in a separate DiscountApplication model
                    order.discount_amount += discount_amount
                    
            except Discount.DoesNotExist:
                self.log_error(f"Discount code {discount_code} not found for order {order.order_number}")
    
    def apply_gift_cards(self, order: Order, order_data: Dict):
        """Apply gift cards to order"""
        applied_gift_cards = order_data.get('applied_gift_cards', [])
        
        for gift_card_data in applied_gift_cards:
            try:
                gift_card = GiftCard.objects.get(
                    tenant=self.tenant,
                    code=gift_card_data['code'],
                    is_active=True
                )
                
                amount_to_apply = min(
                    gift_card.balance,
                    Decimal(gift_card_data['amount'])
                )
                
                if amount_to_apply > 0:
                    # Create gift card application record
                    # This would be in a separate GiftCardApplication model
                    order.gift_card_amount += amount_to_apply
                    
                    # Update gift card balance
                    gift_card.balance -= amount_to_apply
                    gift_card.save(update_fields=['balance'])
                    
            except GiftCard.DoesNotExist:
                self.log_error(f"Gift card {gift_card_data['code']} not found for order {order.order_number}")
    
    def calculate_order_totals(self, order: Order):
        """Calculate and update order totals"""
        # Sum item totals
        items_total = order.items.aggregate(
            total=models.Sum('total_price')
        )['total'] or Decimal('0.00')
        
        # Calculate tax
        tax_amount = self.calculate_order_tax(order, items_total)
        
        # Calculate final total
        total_amount = (
            items_total + 
            order.shipping_cost + 
            tax_amount - 
            order.discount_amount - 
            order.gift_card_amount
        )
        
        # Ensure total is not negative
        total_amount = max(total_amount, Decimal('0.00'))
        
        # Update order
        order.subtotal = items_total
        order.tax_amount = tax_amount
        order.total_amount = total_amount
        order.save(update_fields=[
            'subtotal', 'tax_amount', 'total_amount'
        ])
    
    def calculate_order_tax(self, order: Order, subtotal: Decimal) -> Decimal:
        """Calculate tax for order"""
        # Simplified tax calculation
        # In practice, this would integrate with tax services like Avalara
        
        if self.is_tax_included():
            return Decimal('0.00')
        
        tax_settings = self.get_tax_settings()
        default_rate = tax_settings.get('default_rate', 0)
        
        if default_rate:
            return subtotal * (Decimal(str(default_rate)) / 100)
        
        return Decimal('0.00')
    
    def calculate_discount_amount(self, discount: Discount, order: Order) -> Decimal:
        """Calculate discount amount for order"""
        # This would integrate with discount service
        if discount.discount_type == 'PERCENTAGE':
            return order.subtotal * (discount.discount_value / 100)
        elif discount.discount_type == 'FIXED_AMOUNT':
            return min(discount.discount_value, order.subtotal)
        
        return Decimal('0.00')
    
    def update_order_status(self, order: Order, new_status: str, notes: str = '', user=None):
        """Update order status with history tracking"""
        old_status = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        
        # Create status history
        self.create_status_history(order, new_status, notes, user)
        
        # Trigger status-specific actions
        self.handle_status_change(order, old_status, new_status)
        
        self.log_info(f"Order {order.order_number} status changed from {old_status} to {new_status}")
    
    def create_status_history(self, order: Order, status: str, notes: str = '', user=None):
        """Create order status history record"""
        OrderStatusHistory.objects.create(
            tenant=self.tenant,
            order=order,
            status=status,
            notes=notes,
            changed_by=user,
            timestamp=timezone.now()
        )
    
    def handle_status_change(self, order: Order, old_status: str, new_status: str):
        """Handle order status change events"""
        if new_status == 'confirmed':
            self.handle_order_confirmation(order)
        elif new_status == 'processing':
            self.handle_order_processing(order)
        elif new_status == 'shipped':
            self.handle_order_shipped(order)
        elif new_status == 'delivered':
            self.handle_order_delivered(order)
        elif new_status == 'cancelled':
            self.handle_order_cancellation(order)
        elif new_status == 'refunded':
            self.handle_order_refund(order)
    
    def handle_order_confirmation(self, order: Order):
        """Handle order confirmation"""
        # Reserve inventory
        self.reserve_order_inventory(order)
        
        # Send confirmation email
        self.queue_background_task('send_order_confirmation_email', order.id)
        
        # Track analytics
        self.track_event('order_confirmed', {
            'order_id': str(order.id),
            'total_amount': str(order.total_amount),
            'items_count': order.items.count()
        })
    
    def handle_order_processing(self, order: Order):
        """Handle order processing"""
        # Update inventory (if not already done)
        self.process_order_inventory(order)
        
        # Generate picking list
        self.queue_background_task('generate_picking_list', order.id)
    
    def handle_order_shipped(self, order: Order):
        """Handle order shipped"""
        # Set shipped date
        order.shipped_date = timezone.now()
        order.save(update_fields=['shipped_date'])
        
        # Send shipping notification
        self.queue_background_task('send_shipping_notification', order.id)
        
        # Create tracking information
        self.create_shipment_tracking(order)
    
    def handle_order_delivered(self, order: Order):
        """Handle order delivered"""
        # Set delivered date
        order.delivered_date = timezone.now()
        order.save(update_fields=['delivered_date'])
        
        # Send delivery confirmation
        self.queue_background_task('send_delivery_confirmation', order.id)
        
        # Request review
        self.queue_background_task('request_product_reviews', order.id)
    
    def handle_order_cancellation(self, order: Order):
        """Handle order cancellation"""
        # Release inventory reservations
        self.release_order_inventory(order)
        
        # Process refunds if payment was captured
        if order.payment_status == 'paid':
            self.initiate_refund(order, order.total_amount, 'Order cancelled')
        
        # Send cancellation notification
        self.queue_background_task('send_cancellation_notification', order.id)
    
    def handle_order_refund(self, order: Order):
        """Handle order refund"""
        # This would be called after refund is processed
        # Send refund confirmation
        self.queue_background_task('send_refund_confirmation', order.id)
    
    def reserve_order_inventory(self, order: Order):
        """Reserve inventory for order items"""
        for item in order.items.all():
            if item.product.track_inventory and item.product_variant:
                # Create inventory reservation
                # This would integrate with inventory service
                pass
    
    def process_order_inventory(self, order: Order):
        """Process inventory changes for order"""
        for item in order.items.all():
            if item.product.track_inventory and item.product_variant:
                # Reduce inventory
                variant = item.product_variant
                variant.inventory_quantity = max(
                    0, 
                    variant.inventory_quantity - item.quantity
                )
                variant.save(update_fields=['inventory_quantity'])
    
    def release_order_inventory(self, order: Order):
        """Release inventory reservations"""
        for item in order.items.all():
            if item.product.track_inventory and item.product_variant:
                # Release inventory reservation
                # This would integrate with inventory service
                pass
    
    def create_shipment_tracking(self, order: Order):
        """Create shipment tracking information"""
        # This would integrate with shipping providers
        # For now, generate a dummy tracking number
        if not order.tracking_number:
            order.tracking_number = self.generate_tracking_number()
            order.save(update_fields=['tracking_number'])
    
    def initiate_refund(self, order: Order, amount: Decimal, reason: str = '') -> bool:
        """Initiate refund for order"""
        try:
            # Create refund record
            refund = Refund.objects.create(
                tenant=self.tenant,
                order=order,
                amount=amount,
                reason=reason,
                status='pending',
                requested_date=timezone.now()
            )
            
            # Queue refund processing
            self.queue_background_task('process_refund', refund.id)
            
            return True
            
        except Exception as e:
            self.log_error(f"Failed to initiate refund for order {order.order_number}", e)
            return False
    
    def cancel_order(self, order: Order, reason: str = '', user=None) -> bool:
        """Cancel order"""
        if order.status in ['delivered', 'cancelled', 'refunded']:
            raise ServiceValidationError(f"Cannot cancel order with status: {order.status}")
        
        self.update_order_status(order, 'cancelled', f"Cancelled: {reason}", user)
        return True
    
    def get_order_by_number(self, order_number: str) -> Optional[Order]:
        """Get order by order number"""
        try:
            return Order.objects.get(
                tenant=self.tenant,
                order_number=order_number
            )
        except Order.DoesNotExist:
            return None
    
    def get_customer_orders(self, customer: Customer, status: str = None) -> List[Order]:
        """Get orders for customer"""
        queryset = Order.objects.filter(
            tenant=self.tenant,
            customer=customer
        ).order_by('-order_date')
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset)
    
    def get_orders_requiring_attention(self) -> List[Order]:
        """Get orders that require attention"""
        # Orders that are pending for too long
        pending_cutoff = timezone.now() - timezone.timedelta(hours=24)
        
        return list(Order.objects.filter(
            tenant=self.tenant,
            status='pending',
            created_at__lt=pending_cutoff
        ))
    
    def add_order_note(self, order: Order, note: str, is_public: bool = False, user=None) -> OrderNote:
        """Add note to order"""
        return OrderNote.objects.create(
            tenant=self.tenant,
            order=order,
            note=note,
            is_public=is_public,
            created_by=user,
            timestamp=timezone.now()
        )
    
    def add_order_tag(self, order: Order, tag_name: str) -> bool:
        """Add tag to order"""
        tag, created = OrderTag.objects.get_or_create(
            tenant=self.tenant,
            name=tag_name.lower().strip()
        )
        
        order.tags.add(tag)
        return True
    
    def remove_order_tag(self, order: Order, tag_name: str) -> bool:
        """Remove tag from order"""
        try:
            tag = OrderTag.objects.get(
                tenant=self.tenant,
                name=tag_name.lower().strip()
            )
            order.tags.remove(tag)
            return True
        except OrderTag.DoesNotExist:
            return False
    
    def calculate_order_analytics(self, start_date=None, end_date=None) -> Dict:
        """Calculate order analytics"""
        queryset = Order.objects.filter(tenant=self.tenant)
        
        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)
        
        from django.db.models import Sum, Count, Avg
        
        analytics = queryset.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            average_order_value=Avg('total_amount'),
            confirmed_orders=Count('id', filter=models.Q(status='confirmed')),
            cancelled_orders=Count('id', filter=models.Q(status='cancelled'))
        )
        
        # Calculate conversion rate
        total_orders = analytics['total_orders'] or 0
        confirmed_orders = analytics['confirmed_orders'] or 0
        
        analytics['conversion_rate'] = (
            (confirmed_orders / total_orders * 100) if total_orders > 0 else 0
        )
        
        return analytics
    
    def export_order_data(self, order: Order) -> Dict:
        """Export order data for external systems"""
        items_data = []
        
        for item in order.items.select_related('product', 'product_variant'):
            items_data.append({
                'product_id': str(item.product.id),
                'product_name': item.product_name,
                'product_sku': item.product_sku,
                'variant_id': str(item.product_variant.id) if item.product_variant else None,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price),
                'custom_attributes': item.custom_attributes
            })
        
        return {
            'order_id': str(order.id),
            'order_number': order.order_number,
            'customer_id': str(order.customer.id) if order.customer else None,
            'email': order.email,
            'status': order.status,
            'currency': order.currency,
            'subtotal': str(order.subtotal),
            'tax_amount': str(order.tax_amount),
            'shipping_cost': str(order.shipping_cost),
            'discount_amount': str(order.discount_amount),
            'gift_card_amount': str(order.gift_card_amount),
            'total_amount': str(order.total_amount),
            'payment_method': order.payment_method,
            'shipping_method': order.shipping_method_name,
            'tracking_number': order.tracking_number,
            'order_notes': order.order_notes,
            'items': items_data,
            'shipping_address': self.serialize_address(order.shipping_address),
            'billing_address': self.serialize_address(order.billing_address),
            'order_date': order.order_date.isoformat(),
            'shipped_date': order.shipped_date.isoformat() if order.shipped_date else None,
            'delivered_date': order.delivered_date.isoformat() if order.delivered_date else None
        }
    
    def serialize_address(self, address) -> Dict:
        """Serialize address to dict"""
        if not address:
            return {}
        
        return {
            'first_name': address.first_name,
            'last_name': address.last_name,
            'company': address.company,
            'address1': address.address1,
            'address2': address.address2,
            'city': address.city,
            'state': address.state,
            'zip_code': address.zip_code,
            'country': address.country,
            'phone': address.phone
        }
    
    # Helper methods
    def generate_order_number(self) -> str:
        """Generate unique order number"""
        return self.generate_unique_code('ORD', 8)
    
    def generate_tracking_number(self) -> str:
        """Generate tracking number"""
        return self.generate_unique_code('TRK', 12)
    
    def get_customer_email(self, cart: Cart, order_data: Dict) -> str:
        """Get customer email from cart or order data"""
        if cart.customer:
            return cart.customer.email
        
        guest_info = order_data.get('guest_info', {})
        return guest_info.get('email', '')
    
    def get_minimum_order_amount(self) -> Optional[Decimal]:
        """Get minimum order amount setting"""
        settings = self.get_settings()
        min_amount = settings.get('minimum_order_amount')
        return Decimal(str(min_amount)) if min_amount else None
    
    def check_item_availability(self, cart_item: CartItem) -> bool:
        """Check if cart item is still available"""
        if not self.is_inventory_tracking_enabled():
            return True
        
        if not cart_item.product.track_inventory:
            return True
        
        if cart_item.product_variant:
            available = cart_item.product_variant.inventory_quantity
        else:
            available = sum(
                v.inventory_quantity 
                for v in cart_item.product.variants.all()
            )
        
        return available >= cart_item.quantity or self.are_backorders_allowed()