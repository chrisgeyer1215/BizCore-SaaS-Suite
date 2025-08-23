"""
Cart Command Handlers
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ...domain.events.cart_events import ItemAddedToCartEvent, CartUpdatedEvent
from ...infrastructure.messaging.publishers import EventPublisher
from .base import BaseCommandHandler


@dataclass
class AddToCartCommand:
    """Command to add item to cart"""
    product_id: str
    quantity: int
    variant_id: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_key: Optional[str] = None


@dataclass
class UpdateCartCommand:
    """Command to update cart"""
    cart_id: str
    updates: List[Dict[str, Any]]
    user_id: Optional[str] = None


class CartCommandHandler(BaseCommandHandler):
    """Handler for cart commands"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.event_publisher = EventPublisher(tenant)
    
    def handle_add_to_cart(self, command: AddToCartCommand) -> Dict[str, Any]:
        """Handle add to cart command"""
        try:
            from ..use_cases.cart.add_to_cart import AddToCartUseCase
            
            use_case = AddToCartUseCase(self.tenant)
            result = use_case.execute(
                request_data={
                    'product_id': command.product_id,
                    'quantity': command.quantity,
                    'variant_id': command.variant_id,
                    'custom_attributes': command.custom_attributes
                },
                user_id=command.user_id,
                session_key=command.session_key
            )
            
            return {
                'cart_id': result.id,
                'item_count': result.item_count,
                'total': result.total
            }
            
        except Exception as e:
            self.log_error("Failed to add to cart", e)
            raise
    
    def handle_update_cart(self, command: UpdateCartCommand) -> Dict[str, Any]:
        """Handle update cart command"""
        try:
            from ..use_cases.cart.update_cart import UpdateCartUseCase
            
            use_case = UpdateCartUseCase(self.tenant)
            result = use_case.execute(
                cart_id=command.cart_id,
                updates=command.updates,
                user_id=command.user_id
            )
            
            return {
                'cart_id': result.id,
                'item_count': result.item_count,
                'total': result.total
            }
            
        except Exception as e:
            self.log_error("Failed to update cart", e)
            raise