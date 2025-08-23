"""
Cart Data Transfer Objects
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime

from ...domain.entities.cart import Cart, CartItem
from .base import BaseDTO


@dataclass
class AddToCartDTO(BaseDTO):
    """DTO for adding items to cart"""
    product_id: str
    quantity: int
    variant_id: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    
    def __
        self.product_id = data.get('product_id')
        self.quantity = int(data.get('quantity', 1))
        self.variant_id = data.get('variant_id')
        self.custom_attributes = data.get('custom_attributes', {})


@dataclass
class UpdateCartDTO(BaseDTO):
    """DTO for updating cart items"""
    item_id: str
    updates: Dict[str, Any]]):
        self.item_id = data.get('item_id')
        self.updates = data.get('updates', {})


@dataclass
class CartItemResponseDTO(BaseDTO):
    """DTO for cart item responses"""
    id: str
    product_id: str
    product_title: str
    product_sku: str
    variant_id: Optional[str]
    variant_title: Optional[str]
    quantity: int
    unit_price: float
    total_price: float
    currency: str
    custom_attributes: Dict[str, Any]
    
    @classmethod
    def from_entity(cls, item: CartItem) -> 'CartItemResponseDTO':
        """Create DTO from cart item entity"""
        return cls(
            id=str(item.id),
            product_id=str(item.product_id),
            product_title=item.product_title or "Product",
            product_sku=item.product_sku or "",
            variant_id=str(item.variant_id) if item.variant_id else None,
            variant_title=item.variant_title,
            quantity=item.quantity,
            unit_price=float(item.price.amount),
            total_price=float(item.total_price.amount),
            currency=item.price.currency,
            custom_attributes=item.custom_attributes or {}
        )


@dataclass
class CartResponseDTO(BaseDTO):
    """DTO for cart responses"""
    id: str
    user_id: Optional[str]
    session_key: Optional[str]
    items: List[CartItemResponseDTO]
    item_count: int
    subtotal: float
    shipping_cost: float
    tax_amount: float
    discount_amount: float
    total: float
    currency: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_entity(cls, cart: Cart) -> 'CartResponseDTO':
        """Create DTO from cart entity"""
        return cls(
            id=str(cart.id),
            user_id=str(cart.user_id) if cart.user_id else None,
            session_key=cart.session_key,
            items=[CartItemResponseDTO.from_entity(item) for item in cart.items],
            item_count=len(cart.items),
            subtotal=float(cart.subtotal.amount),
            shipping_cost=float(cart.shipping_cost.amount) if cart.shipping_cost else 0.0,
            tax_amount=float(cart.tax_amount.amount) if cart.tax_amount else 0.0,
            discount_amount=float(cart.discount_amount.amount) if cart.discount_amount else 0.0,
            total=float(cart.total.amount),
            currency=cart.currency,
            created_at=cart.created_at,
            updated_at=cart.updated_at
        )