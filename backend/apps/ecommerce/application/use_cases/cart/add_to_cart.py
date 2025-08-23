"""
Add to Cart Use Case
"""

from typing import Dict, Any, Optional
from decimal import Decimal

from ...domain.entities.cart import Cart, CartItem
from ...domain.entities.product import Product
from ...domain.value_objects.money import Money
from ...domain.events.cart_events import ItemAddedToCartEvent
from ...domain.services.pricing_service import PricingService
from ...infrastructure.persistence.repositories.cart_repository_impl import CartRepositoryImpl
from ...infrastructure.persistence.repositories.product_repository_impl import ProductRepositoryImpl
from ...infrastructure.messaging.publishers import EventPublisher
from ..dto.cart_dto import AddToCartDTO, CartResponseDTO
from .base import BaseUseCase


class AddToCartUseCase(BaseUseCase):
    """Use case for adding items to cart"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.cart_repository = CartRepositoryImpl(tenant)
        self.product_repository = ProductRepositoryImpl(tenant)
        self.pricing_service = PricingService(tenant)
        self.event_publisher = EventPublisher(tenant)[str, Any], 
                user_id: Optional[str] = None, 
                session_key: Optional[str] = None) -> CartResponseDTO:
        """Execute add to cart use case"""
        try:
            # Create and validate DTO
            add_dto = AddToCartDTO(request_data)
            self.validate_input(add_dto)
            
            # Get or create cart
            cart = self.get_or_create_cart(user_id, session_key)
            
            # Get product
            product = self.get_product(add_dto.product_id)
            
            # Validate product availability
            self.validate_product_availability(product, add_dto)
            
            # Calculate pricing
            item_price = self.calculate_item_price(product, add_dto)
            
            # Add item to cart
            cart_item = self.add_item_to_cart(cart, product, add_dto, item_price)
            
            # Save cart
            updated_cart = self.cart_repository.save(cart)
            
            # Publish event
            self.publish_item_added_event(updated_cart, cart_item, user_id)
            
            # Return response
            return CartResponseDTO.from_entity(updated_cart)
            
        except Exception as e:
            self.log_error("Failed to add item to cart", e, {
                'request_data': request_data,
                'user_id': user_id,
                'session_key': session_key
            })
            raise self.handle_service_error(e, "add_to_cart")
    
    def validate_input(self, dto: AddToCartDTO):
        """Validate input data"""
        errors = []
        
        if not dto.product_id:
            errors.append("Product ID is required")
        
        if dto.quantity <= 0:
            errors.append("Quantity must be greater than 0")
        
        if dto.quantity > 100:  # Business rule
            errors.append("Maximum quantity per item is 100")
        
        if errors:
            raise ValidationError("Invalid cart data", details={'errors': errors})
    
    def get_or_create_cart(self, user_id: Optional[str], 
                          session_key: Optional[str]) -> Cart:
        """Get existing cart or create new one"""
        if user_id:
            cart = self.cart_repository.find_by_user_id(user_id)
            if not cart:
                cart = Cart.create_user_cart(user_id)
        else:
            if not session_key:
                raise ValidationError("Session key required for guest cart")
            cart = self.cart_repository.find_by_session_key(session_key)
            if not cart:
                cart = Cart.create_session_cart(session_key)
        
        return cart
    
    def get_product(self, product_id: str) -> Product:
        """Get product by ID"""
        product = self.product_repository.find_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")
        
        if not product.is_active or not product.is_published:
            raise ValidationError("Product is not available")
        
        return product
    
    def validate_product_availability(self, product: Product, dto: AddToCartDTO):
        """Validate product availability"""
        if product.track_quantity:
            available_quantity = product.get_available_quantity()
            
            if available_quantity <= 0:
                raise ValidationError("Product is out of stock")
            
            if dto.quantity > available_quantity:
                raise ValidationError(
                    f"Only {available_quantity} items available in stock"
                )
        
        # Check variant availability if specified
        if dto.variant_id:
            variant = product.get_variant(dto.variant_id)
            if not variant:
                raise NotFoundError("Product variant not found")
            
            if not variant.is_active:
                raise ValidationError("Product variant is not available")
            
            if variant.track_quantity and variant.stock_quantity < dto.quantity:
                raise ValidationError(
                    f"Only {variant.stock_quantity} items available for this variant"
                )
    
    def calculate_item_price(self, product: Product, dto: AddToCartDTO) -> Money:
        """Calculate item price with any applicable discounts"""
        base_price = product.price
        
        if dto.variant_id:
            variant = product.get_variant(dto.variant_id)
            if variant and variant.price:
                base_price = variant.price
        
        # Apply pricing rules
        final_price = self.pricing_service.calculate_cart_item_price(
            product=product,
            variant_id=dto.variant_id,
            quantity=dto.quantity,
            base_price=base_price
        )
        
        return final_price
    
    def add_item_to_cart(self, cart: Cart, product: Product, 
                        dto: AddToCartDTO, price: Money) -> CartItem:
        """Add item to cart or update existing item"""
        existing_item = cart.find_item(
            product_id=product.id,
            variant_id=dto.variant_id,
            custom_attributes=dto.custom_attributes
        )
        
        if existing_item:
            # Update existing item quantity
            new_quantity = existing_item.quantity + dto.quantity
            existing_item.update_quantity(new_quantity)
            existing_item.update_price(price)
            return existing_item
        else:
            # Add new item
            cart_item = CartItem.create(
                product_id=product.id,
                variant_id=dto.variant_id,
                quantity=dto.quantity,
                price=price,
                custom_attributes=dto.custom_attributes
            )
            cart.add_item(cart_item)
            return cart_item
    
    def publish_item_added_event(self, cart: Cart, item: CartItem, user_id: Optional[str]):
        """Publish item added to cart event"""
        event = ItemAddedToCartEvent(
            cart_id=str(cart.id),
            item_id=str(item.id),
            product_id=str(item.product_id),
            variant_id=str(item.variant_id) if item.variant_id else None,
            quantity=item.quantity,
            price=float(item.price.amount),
            currency=item.price.currency,
            user_id=user_id,
            timestamp=self.get_current_timestamp()
        )
        
        self.event_publisher.publish(event)