"""
Update Cart Use Case
"""

from typing import Dict, Any, Optional, List

from ...domain.entities.cart import Cart
from ...domain.events.cart_events import CartUpdatedEvent
from ...domain.services.pricing_service import PricingService
from ...infrastructure.persistence.repositories.cart_repository_impl import CartRepositoryImpl
from ...infrastructure.messaging.publishers import EventPublisher
from ..dto.cart_dto import UpdateCartDTO, CartResponseDTO
from .base import BaseUseCase


class UpdateCartUseCase(BaseUseCase):
    """Use case for updating cart items"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.cart_repository = CartRepositoryImpl(tenant)
        self.pricing_service = PricingService(tenant)
        self.event_publisher = EventPublisher(tenant)
    
    def execute(self, cart_id: str, updates: List[Dict[str, Any]], 
                user_id: Optional[str] = None) -> CartResponseDTO:
        """Execute cart update use case"""
        try:
            # Get cart
            cart = self.get_cart(cart_id, user_id)
            
            # Validate updates
            update_dtos = [UpdateCartDTO(update) for update in updates]
            self.validate_updates(update_dtos)
            
            # Apply updates
            changes = self.apply_updates(cart, update_dtos)
            
            # Recalculate cart totals
            self.recalculate_cart(cart)
            
            # Save cart
            updated_cart = self.cart_repository.save(cart)
            
            # Publish event
            self.publish_cart_updated_event(updated_cart, changes, user_id)
            
            return CartResponseDTO.from_entity(updated_cart)
            
        except Exception as e:
            self.log_error("Failed to update cart", e, {
                'cart_id': cart_id,
                'updates': updates,
                'user_id': user_id
            })
            raise self.handle_service_error(e, "update_cart")
    
    def get_cart(self, cart_id: str, user_id: Optional[str]) -> Cart:
        """Get cart with validation"""
        cart = self.cart_repository.find_by_id(cart_id)
        if not cart:
            raise NotFoundError("Cart not found")
        
        # Validate ownership
        if user_id and cart.user_id != user_id:
            raise PermissionError("Cart does not belong to user")
        
        return cart
    
    def validate_updates(self, update_dtos: List[UpdateCartDTO]):
        """Validate all updates"""
        for dto in update_dtos:
            if not dto.item_id:
                raise ValidationError("Item ID is required")
            
            if 'quantity' in dto.updates:
                quantity = dto.updates['quantity']
                if quantity < 0:
                    raise ValidationError("Quantity cannot be negative")
                if quantity > 100:
                    raise ValidationError("Maximum quantity per item is 100")
    
    def apply_updates(self, cart: Cart, update_dtos: List[UpdateCartDTO]) -> List[Dict]:
        """Apply updates to cart items"""
        changes = []
        
        for dto in update_dtos:
            item = cart.get_item(dto.item_id)
            if not item:
                continue  # Skip non-existent items
            
            item_changes = {}
            
            # Update quantity
            if 'quantity' in dto.updates:
                new_quantity = dto.updates['quantity']
                if new_quantity == 0:
                    # Remove item
                    cart.remove_item(dto.item_id)
                    item_changes['action'] = 'removed'
                else:
                    old_quantity = item.quantity
                    item.update_quantity(new_quantity)
                    item_changes['quantity_changed'] = {
                        'from': old_quantity,
                        'to': new_quantity
                    }
            
            # Update custom attributes
            if 'custom_attributes' in dto.updates:
                item.update_custom_attributes(dto.updates['custom_attributes'])
                item_changes['attributes_updated'] = True
            
            if item_changes:
                item_changes['item_id'] = dto.item_id
                changes.append(item_changes)
        
        return changes
    
    def recalculate_cart(self, cart: Cart):
        """Recalculate cart totals and apply discounts"""
        # Recalculate item prices (in case of price changes)
        for item in cart.items:
            updated_price = self.pricing_service.calculate_cart_item_price(
                product_id=item.product_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                base_price=item.price
            )
            item.update_price(updated_price)
        
        # Calculate cart totals
        cart.calculate_totals()
        
        # Apply cart-level discounts
        self.pricing_service.apply_cart_discounts(cart)
    
    def publish_cart_updated_event(self, cart: Cart, changes: List[Dict], 
                                 user_id: Optional[str]):
        """Publish cart updated event"""
        event = CartUpdatedEvent(
            cart_id=str(cart.id),
            changes=changes,
            item_count=len(cart.items),
            subtotal=float(cart.subtotal.amount),
            total=float(cart.total.amount),
            user_id=user_id,
            timestamp=self.get_current_timestamp()
        )
        
        self.event_publisher.publish(event)