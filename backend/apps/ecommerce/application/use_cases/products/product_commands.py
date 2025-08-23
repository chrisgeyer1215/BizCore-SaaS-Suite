"""
Product Command Handlers
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from ...domain.events.product_events import (
    ProductCreatedEvent, ProductUpdatedEvent, ProductDeletedEvent,
    ProductPublishedEvent, ProductUnpublishedEvent
)
from ...infrastructure.messaging.publishers import EventPublisher
from .base import BaseCommandHandler


@dataclass
class CreateProductCommand:
    """Command to create a new product"""
    title: str
    description: str
    price: float
    sku: Optional[str] = None
    brand: Optional[str] = None
    product_type: Optional[str] = None
    currency: str = 'USD'
    stock_quantity: int = 0
    track_quantity: bool = True
    is_active: bool = True
    user_id: Optional[str] = None
    
    def validate(self):
        """Validate command data"""
        if not self.title or len(self.title.strip()) == 0:
            raise ValidationError("Title is required")
        
        if not self.price or self.price <= 0:
            raise ValidationError("Price must be greater than 0")


@dataclass
class UpdateProductCommand:
    """Command to update an existing product"""
    product_id: str
    updates: Dict[str, Any]
    user_id: Optional[str] = None
    
    def validate(self):
        """Validate command data"""
        if not self.product_id:
            raise ValidationError("Product ID is required")
        
        if not self.updates:
            raise ValidationError("No updates provided")


class ProductCommandHandler(BaseCommandHandler):
    """Handler for product commands"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.event_publisher = EventPublisher(tenant)
    
    def handle_create_product(self, command: CreateProductCommand) -> str:
        """Handle create product command"""
        try:
            command.validate()
            
            # Use the create product use case
            from ..use_cases.products.create_product import CreateProductUseCase
            
            create_use_case = CreateProductUseCase(self.tenant)
            result = create_use_case.execute(
                request_data=command.__dict__,
                user_id=command.user_id
            )
            
            self.log_info("Product created successfully", {
                'product_id': result.id,
                'title': result.title
            })
            
            return result.id
            
        except Exception as e:
            self.log_error("Failed to create product", e)
            raise
    
    def handle_update_product(self, command: UpdateProductCommand) -> bool:
        """Handle update product command"""
        try:
            command.validate()
            
            # Use the update product use case
            from ..use_cases.products.update_product import UpdateProductUseCase
            
            update_use_case = UpdateProductUseCase(self.tenant)
            result = update_use_case.execute(
                product_id=command.product_id,
                updates=command.updates,
                user_id=command.user_id
            )
            
            # Publish updated event
            event = ProductUpdatedEvent(
                product_id=command.product_id,
                tenant_id=str(self.tenant.id),
                updates=command.updates,
                user_id=command.user_id,
                timestamp=self.get_current_timestamp()
            )
            self.event_publisher.publish(event)
            
            return True
            
        except Exception as e:
            self.log_error("Failed to update product", e)
            raise