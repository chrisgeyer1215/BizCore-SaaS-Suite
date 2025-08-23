"""
Order Data Transfer Objects
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

from ...domain.entities.order import Order, OrderItem
from .base import BaseDTO


@dataclass
class CreateOrderDTO(BaseDTO):
    """DTO for creating orders"""
    cart_id: str
    email: str
    phone: Optional[str]
    shipping_address: Dict[str, str]
    billing_address: Dict[str, str]
    shipping_cost: float
    tax_amount: float
    payment_method: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    
    def __init__(self]):
        self.cart_id = data.get('cart_id')
        self.email = data.get('email')
        self.phone = data.get('phone')
        self.shipping_address = data.get('shipping_address', {})
        self.billing_address = data.get('billing_address', {})
        self.shipping_cost = float(data.get('shipping_cost', 0))
        self.tax_amount = float(data.get('tax_amount', 0))
        self.payment_method = data.get('payment_method')
        self.payment_details = data.get('payment_details')
        self.notes = data.get('notes')


@dataclass
class OrderItemResponseDTO(BaseDTO):
    """DTO for order item responses"""
    id: str
    product_id: str
    product_title: str
    product_sku: str
    variant_id: Optional[str]
    variant_title: Optional[str]
    quantity: int
    unit_price: float
    total_price: float
    
    @classmethod
    def from_entity(cls, item: OrderItem) -> 'OrderItemResponseDTO':
        """Create DTO from order item entity"""
        return cls(
            id=str(item.id),
            product_id=str(item.product_id),
            product_title=item.product_title,
            product_sku=item.product_sku,
            variant_id=str(item.variant_id) if item.variant_id else None,
            variant_title=item.variant_title,
            quantity=item.quantity,
            unit_price=float(item.unit_price.amount),
            total_price=float(item.total_price.amount)
        )


@dataclass
class OrderResponseDTO(BaseDTO):
    """DTO for order responses"""
    id: str
    order_number: str
    user_id: Optional[str]
    email: str
    phone: Optional[str]
    status: str
    payment_status: str
    fulfillment_status: str
    items: List[OrderItemResponseDTO]
    subtotal: float
    shipping_cost: float
    tax_amount: float
    total: float
    currency: str
    shipping_address: Dict[str, str]
    billing_address: Dict[str, str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_entity(cls, order: Order) -> 'OrderResponseDTO':
        """Create DTO from order entity"""
        return cls(
            id=str(order.id),
            order_number=order.order_number,
            user_id=str(order.user_id) if order.user_id else None,
            email=order.email,
            phone=order.phone,
            status=order.status,
            payment_status=order.payment_status,
            fulfillment_status=order.fulfillment_status,
            items=[OrderItemResponseDTO.from_entity(item) for item in order.items],
            subtotal=float(order.subtotal.amount),
            shipping_cost=float(order.shipping_cost.amount),
            tax_amount=float(order.tax_amount.amount),
            total=float(order.total.amount),
            currency=order.currency,
            shipping_address=order.shipping_address.to_dict() if order.shipping_address else {},
            billing_address=order.billing_address.to_dict() if order.billing_address else {},
            notes=order.notes,
            created_at=order.created_at,
            updated_at=order.updated_at
        )