from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal

from apps.ecommerce.domain.events.base import DomainEvent


# ============================================================================
# INVENTORY DOMAIN RESPONSE EVENTS (Expected responses)
# ============================================================================

class StockLevelUpdatedEvent(DomainEvent):
    """Published by Inventory Domain when stock level changes"""
    
    def __init__(
        self,
        aggregate_id: str,  # This would be inventory_item_id
        sku: str,
        old_quantity: int,
        new_quantity: int,
        available_quantity: int,
        reserved_quantity: int,
        warehouse_location: str,
        reason: str = "",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.old_quantity = old_quantity
        self.new_quantity = new_quantity
        self.available_quantity = available_quantity
        self.reserved_quantity = reserved_quantity
        self.warehouse_location = warehouse_location
        self.reason = reason
        
        self.event_data.update({
            'sku': sku,
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'available_quantity': available_quantity,
            'reserved_quantity': reserved_quantity,
            'total_quantity': new_quantity + reserved_quantity,
            'warehouse_location': warehouse_location,
            'reason': reason,
            'stock_change': new_quantity - old_quantity
        })


class StockReservationConfirmedEvent(DomainEvent):
    """Published by Inventory Domain when stock reservation is confirmed"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity_reserved: int,
        reservation_id: str,
        order_id: str,
        expires_at: datetime,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity_reserved = quantity_reserved
        self.reservation_id = reservation_id
        self.order_id = order_id
        self.expires_at = expires_at
        
        self.event_data.update({
            'sku': sku,
            'quantity_reserved': quantity_reserved,
            'reservation_id': reservation_id,
            'order_id': order_id,
            'expires_at': expires_at.isoformat(),
            'status': 'confirmed'
        })


class StockReservationFailedEvent(DomainEvent):
    """Published by Inventory Domain when stock reservation fails"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        requested_quantity: int,
        available_quantity: int,
        order_id: str,
        failure_reason: str,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.requested_quantity = requested_quantity
        self.available_quantity = available_quantity
        self.order_id = order_id
        self.failure_reason = failure_reason
        
        self.event_data.update({
            'sku': sku,
            'requested_quantity': requested_quantity,
            'available_quantity': available_quantity,
            'order_id': order_id,
            'failure_reason': failure_reason,
            'status': 'failed'
        })


class StockCommittedEvent(DomainEvent):
    """Published by Inventory Domain when reserved stock is committed"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity_committed: int,
        reservation_id: str,
        order_id: str,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity_committed = quantity_committed
        self.reservation_id = reservation_id
        self.order_id = order_id
        
        self.event_data.update({
            'sku': sku,
            'quantity_committed': quantity_committed,
            'reservation_id': reservation_id,
            'order_id': order_id,
            'status': 'committed'
        })


class StockReleasedEvent(DomainEvent):
    """Published by Inventory Domain when reserved stock is released"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity_released: int,
        reservation_id: str,
        order_id: str,
        reason: str = "",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity_released = quantity_released
        self.reservation_id = reservation_id
        self.order_id = order_id
        self.reason = reason
        
        self.event_data.update({
            'sku': sku,
            'quantity_released': quantity_released,
            'reservation_id': reservation_id,
            'order_id': order_id,
            'reason': reason,
            'status': 'released'
        })


class InventoryLowStockAlertEvent(DomainEvent):
    """Published by Inventory Domain when stock is low"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        current_quantity: int,
        reorder_point: int,
        recommended_reorder_quantity: int,
        supplier_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.current_quantity = current_quantity
        self.reorder_point = reorder_point
        self.recommended_reorder_quantity = recommended_reorder_quantity
        self.supplier_info = supplier_info
        
        self.event_data.update({
            'sku': sku,
            'current_quantity': current_quantity,
            'reorder_point': reorder_point,
            'recommended_reorder_quantity': recommended_reorder_quantity,
            'supplier_info': supplier_info,
            'urgency': 'HIGH' if current_quantity <= reorder_point * 0.5 else 'MEDIUM'
        })


class InventoryItemCreatedEvent(DomainEvent):
    """Published by Inventory Domain when new inventory item is created"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        initial_quantity: int,
        warehouse_location: str,
        cost_per_unit: Optional[Decimal] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.initial_quantity = initial_quantity
        self.warehouse_location = warehouse_location
        self.cost_per_unit = cost_per_unit
        
        self.event_data.update({
            'sku': sku,
            'initial_quantity': initial_quantity,
            'warehouse_location': warehouse_location,
            'cost_per_unit': float(cost_per_unit) if cost_per_unit else None
        })