"""
Create Order Use Case
"""

from typing import Dict, Any, Optional
from decimal import Decimal

from ...domain.entities.order import Order, OrderItem
from ...domain.entities.cart import Cart
from ...domain.entities.customer import Customer
from ...domain.value_objects.address import Address
from ...domain.value_objects.money import Money
from ...domain.events.order_events import OrderCreatedEvent
from ...domain.services.order_service import OrderService
from ...domain.services.inventory_service import InventoryService
from ...infrastructure.persistence.repositories.order_repository_impl import OrderRepositoryImpl
from ...infrastructure.persistence.repositories.cart_repository_impl import CartRepositoryImpl
from ...infrastructure.external.payment.payment_processor import PaymentProcessor
from ...infrastructure.messaging.publishers import EventPublisher
from ..dto.order_dto import CreateOrderDTO, OrderResponseDTO
from .base import BaseUseCase


class CreateOrderUseCase(BaseUseCase):
    """Use case for creating orders from cart"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.order_repository = OrderRepositoryImpl(tenant)
        self.cart_repository = CartRepositoryImpl(tenant)
        self.order_service = OrderService(tenant)
        self.inventory_service = InventoryService(tenant)
        self.payment_processor = PaymentProcessor(tenant)
        self.event_publisher = EventPublisher(tenant)
    
    def
                user_id: Optional[str] = None) -> OrderResponseDTO:
        """Execute order creation use case"""
        try:
            # Create and validate DTO
            create_dto = CreateOrderDTO(request_data)
            self.validate_input(create_dto)
            
            # Get cart
            cart = self.get_cart(create_dto.cart_id, user_id)
            
            # Validate cart
            self.validate_cart_for_checkout(cart)
            
            # Reserve inventory
            reservations = self.reserve_inventory(cart)
            
            try:
                # Create order from cart
                order = self.create_order_from_cart(cart, create_dto, user_id)
                
                # Process payment if required
                if create_dto.payment_method and create_dto.payment_details:
                    payment_result = self.process_payment(order, create_dto)
                    order.update_payment_status(payment_result)
                
                # Save order
                saved_order = self.order_repository.save(order)
                
                # Clear cart
                self.clear_cart(cart)
                
                # Confirm inventory reservations
                self.confirm_inventory_reservations(reservations)
                
                # Publish event
                self.publish_order_created_event(saved_order, user_id)
                
                return OrderResponseDTO.from_entity(saved_order)
                
            except Exception as e:
                # Release inventory reservations on failure
                self.release_inventory_reservations(reservations)
                raise e
                
        except Exception as e:
            self.log_error("Failed to create order", e, {
                'request_data': request_data,
                'user_id': user_id
            })
            raise self.handle_service_error(e, "create_order")
    
    def validate_input(self, dto: CreateOrderDTO):
        """Validate input data"""
        errors = []
        
        if not dto.cart_id:
            errors.append("Cart ID is required")
        
        if not dto.shipping_address:
            errors.append("Shipping address is required")
        
        if not dto.billing_address:
            errors.append("Billing address is required")
        
        if errors:
            raise ValidationError("Invalid order data", details={'errors': errors})
    
    def get_cart(self, cart_id: str, user_id: Optional[str]) -> Cart:
        """Get cart for order creation"""
        cart = self.cart_repository.find_by_id(cart_id)
        if not cart:
            raise NotFoundError("Cart not found")
        
        if user_id and cart.user_id != user_id:
            raise PermissionError("Cart does not belong to user")
        
        return cart
    
    def validate_cart_for_checkout(self, cart: Cart):
        """Validate cart is ready for checkout"""
        if not cart.items:
            raise ValidationError("Cart is empty")
        
        for item in cart.items:
            # Validate item availability
            if not self.inventory_service.is_item_available(
                item.product_id, item.variant_id, item.quantity
            ):
                raise ValidationError(
                    f"Item {item.product_id} is no longer available in requested quantity"
                )
    
    def reserve_inventory(self, cart: Cart) -> List[str]:
        """Reserve inventory for cart items"""
        reservations = []
        
        for item in cart.items:
            reservation_id = self.inventory_service.reserve_item(
                product_id=item.product_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                expires_minutes=15  # Reserve for 15 minutes
            )
            reservations.append(reservation_id)
        
        return reservations
    
    def create_order_from_cart(self, cart: Cart, dto: CreateOrderDTO, 
                              user_id: Optional[str]) -> Order:
        """Create order entity from cart"""
        # Create order items from cart items
        order_items = []
        for cart_item in cart.items:
            order_item = OrderItem.create(
                product_id=cart_item.product_id,
                variant_id=cart_item.variant_id,
                quantity=cart_item.quantity,
                unit_price=cart_item.price,
                total_price=cart_item.total_price,
                product_title=cart_item.product_title,
                product_sku=cart_item.product_sku
            )
            order_items.append(order_item)
        
        # Create addresses
        shipping_address = Address.from_dict(dto.shipping_address)
        billing_address = Address.from_dict(dto.billing_address)
        
        # Generate order number
        order_number = self.order_service.generate_order_number()
        
        # Create order
        order = Order.create(
            order_number=order_number,
            user_id=user_id,
            email=dto.email,
            phone=dto.phone,
            shipping_address=shipping_address,
            billing_address=billing_address,
            items=order_items,
            subtotal=cart.subtotal,
            shipping_cost=Money(dto.shipping_cost, cart.currency),
            tax_amount=Money(dto.tax_amount, cart.currency),
            total=cart.total,
            currency=cart.currency,
            notes=dto.notes
        )
        
        return order
    
    def process_payment(self, order: Order, dto: CreateOrderDTO) -> Dict[str, Any]:
        """Process payment for order"""
        payment_request = {
            'amount': float(order.total.amount),
            'currency': order.total.currency,
            'payment_method': dto.payment_method,
            'payment_details': dto.payment_details,
            'order_number': order.order_number,
            'customer_email': order.email,
            'description': f"Order {order.order_number}"
        }
        
        return self.payment_processor.process_payment(payment_request)
    
    def clear_cart(self, cart: Cart):
        """Clear cart after successful order"""
        cart.clear()
        self.cart_repository.save(cart)
    
    def confirm_inventory_reservations(self, reservation_ids: List[str]):
        """Confirm inventory reservations"""
        for reservation_id in reservation_ids:
            self.inventory_service.confirm_reservation(reservation_id)
    
    def release_inventory_reservations(self, reservation_ids: List[str]):
        """Release inventory reservations"""
        for reservation_id in reservation_ids:
            self.inventory_service.release_reservation(reservation_id)
    
    def publish_order_created_event(self, order: Order, user_id: Optional[str]):
        """Publish order created event"""
        event = OrderCreatedEvent(
            order_id=str(order.id),
            order_number=order.order_number,
            user_id=user_id,
            email=order.email,
            total_amount=float(order.total.amount),
            currency=order.total.currency,
            item_count=len(order.items),
            timestamp=self.get_current_timestamp()
        )
        
        self.event_publisher.publish(event)