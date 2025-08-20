from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockItem, StockMovementItem, StockValuationLayer,
    LandedCost, LandedCostAllocation
)

class StockValuationService(BaseService):
    """
    Service for handling stock valuation and costing methods
    """
    
    COSTING_METHODS = {
        'FIFO': 'First In First Out',
        'LIFO': 'Last In First Out', 
        'WEIGHTED_AVERAGE': 'Weighted Average',
        'STANDARD': 'Standard Cost',
        'SPECIFIC': 'Specific Identification'
    }
    
    def __init__(self, tenant=None, user=None, costing_method='FIFO'):
        super().__init__(tenant, user)
        self.costing_method = costing_method
    
    @transaction.atomic
    def update_valuation_layers(self, movement_item: StockMovementItem) -> ServiceResult:
        """
        Update stock valuation layers based on movement
        """
        try:
            stock_item = movement_item.stock_item
            movement_type = movement_item.movement.movement_type
            quantity = movement_item.quantity
            unit_cost = movement_item.unit_cost
            
            if movement_type in self._get_inbound_movement_types():
                return self._process_inbound_movement(stock_item, quantity, unit_cost, movement_item)
            elif movement_type in self._get_outbound_movement_types():
                return self._process_outbound_movement(stock_item, quantity, movement_item)
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to update valuation layers: {str(e)}")
    
    def _get_inbound_movement_types(self):
        return [
            'RECEIPT', 'TRANSFER_IN', 'ADJUSTMENT_POSITIVE',
            'PRODUCTION_OUTPUT', 'RETURN_FROM_CUSTOMER', 'FOUND'
        ]
    
    def _get_outbound_movement_types(self):
        return [
            'ISSUE', 'TRANSFER_OUT', 'ADJUSTMENT_NEGATIVE',
            'PRODUCTION_CONSUMPTION', 'RETURN_TO_SUPPLIER',
            'DAMAGED', 'EXPIRED', 'LOST'
        ]
    
    def _process_inbound_movement(self, stock_item: StockItem, quantity: Decimal, 
                                unit_cost: Decimal, movement_item: StockMovementItem) -> ServiceResult:
        """Process inbound movement and create valuation layer"""
        try:
            # Create new valuation layer for inbound stock
            valuation_layer = StockValuationLayer.objects.create(
                tenant=self.tenant,
                stock_item=stock_item,
                movement_item=movement_item,
                quantity_in=quantity,
                quantity_remaining=quantity,
                unit_cost=unit_cost,
                total_cost=quantity * unit_cost,
                layer_date=timezone.now(),
                costing_method=self.costing_method
            )
            
            # Update stock item average cost
            self._update_average_cost(stock_item)
            
            return ServiceResult.success(data=valuation_layer)
            
        except Exception as e:
            return ServiceResult.error(f"Failed to process inbound movement: {str(e)}")
    
    def _process_outbound_movement(self, stock_item: StockItem, quantity: Decimal,
                                 movement_item: StockMovementItem) -> ServiceResult:
        """Process outbound movement and consume from valuation layers"""
        try:
            remaining_to_consume = quantity
            total_cost = Decimal('0')
            layers_consumed = []
            
            # Get available valuation layers based on costing method
            available_layers = self._get_available_layers(stock_item)
            
            for layer in available_layers:
                if remaining_to_consume <= 0:
                    break
                
                # Calculate quantity to consume from this layer
                consume_quantity = min(remaining_to_consume, layer.quantity_remaining)
                consume_cost = consume_quantity * layer.unit_cost
                
                # Update layer
                layer.quantity_out += consume_quantity
                layer.quantity_remaining -= consume_quantity
                layer.save()
                
                # Create consumption record
                consumption = StockValuationLayer.objects.create(
                    tenant=self.tenant,
                    stock_item=stock_item,
                    movement_item=movement_item,
                    source_layer=layer,
                    quantity_out=consume_quantity,
                    unit_cost=layer.unit_cost,
                    total_cost=consume_cost,
                    layer_date=timezone.now(),
                    costing_method=self.costing_method
                )
                
                layers_consumed.append({
                    'layer_id': layer.id,
                    'quantity': consume_quantity,
                    'cost': consume_cost
                })
                
                total_cost += consume_cost
                remaining_to_consume -= consume_quantity
            
            # Update movement item with actual cost
            movement_item.actual_unit_cost = total_cost / quantity if quantity > 0 else Decimal('0')
            movement_item.save()
            
            # Update stock item average cost
            self._update_average_cost(stock_item)
            
            return ServiceResult.success(data={
                'layers_consumed': layers_consumed,
                'total_cost': total_cost,
                'actual_unit_cost': movement_item.actual_unit_cost
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to process outbound movement: {str(e)}")
    
    def _get_available_layers(self, stock_item: StockItem):
        """Get available valuation layers based on costing method"""
        base_query = StockValuationLayer.objects.filter(
            stock_item=stock_item,
            quantity_remaining__gt=0
        )
        
        if self.costing_method == 'FIFO':
            return base_query.order_by('layer_date', 'id')
        elif self.costing_method == 'LIFO':
            return base_query.order_by('-layer_date', '-id')
        elif self.costing_method in ['WEIGHTED_AVERAGE', 'STANDARD']:
            return base_query.order_by('layer_date', 'id')
        else:
            return base_query.order_by('layer_date', 'id')
    
    def _update_average_cost(self, stock_item: StockItem):
        """Update stock item average cost based on valuation layers"""
        layers = StockValuationLayer.objects.filter(
            stock_item=stock_item,
            quantity_remaining__gt=0
        )
        
        total_quantity = sum(layer.quantity_remaining for layer in layers)
        total_cost = sum(layer.quantity_remaining * layer.unit_cost for layer in layers)
        
        if total_quantity > 0:
            stock_item.average_unit_cost = total_cost / total_quantity
            stock_item.save(update_fields=['average_unit_cost'])
    
    def calculate_inventory_value(self, warehouse_id: Optional[int] = None, 
                                product_ids: Optional[List[int]] = None) -> ServiceResult:
        """Calculate total inventory value"""
        try:
            queryset = StockItem.objects.filter(tenant=self.tenant)
            
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            if product_ids:
                queryset = queryset.filter(product_id__in=product_ids)
            
            total_value = Decimal('0')
            item_values = []
            
            for stock_item in queryset:
                # Calculate value based on costing method
                if self.costing_method == 'WEIGHTED_AVERAGE':
                    value = stock_item.quantity_on_hand * stock_item.average_unit_cost
                elif self.costing_method == 'STANDARD':
                    value = stock_item.quantity_on_hand * stock_item.standard_cost
                else:  # FIFO/LIFO
                    value = self._calculate_fifo_lifo_value(stock_item)
                
                item_values.append({
                    'stock_item_id': stock_item.id,
                    'product_name': stock_item.product.name,
                    'quantity': stock_item.quantity_on_hand,
                    'value': value
                })
                
                total_value += value
            
            return ServiceResult.success(data={
                'total_value': total_value,
                'item_values': item_values,
                'costing_method': self.costing_method
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to calculate inventory value: {str(e)}")
    
    def _calculate_fifo_lifo_value(self, stock_item: StockItem) -> Decimal:
        """Calculate FIFO/LIFO inventory value"""
        layers = self._get_available_layers(stock_item)
        remaining_quantity = stock_item.quantity_on_hand
        total_value = Decimal('0')
        
        for layer in layers:
            if remaining_quantity <= 0:
                break
            
            layer_quantity = min(remaining_quantity, layer.quantity_remaining)
            total_value += layer_quantity * layer.unit_cost
            remaining_quantity -= layer_quantity
        
        return total_value
    
    @transaction.atomic
    def apply_landed_costs(self, landed_cost_id: int) -> ServiceResult:
        """Apply landed costs to stock items"""
        try:
            landed_cost = LandedCost.objects.get(id=landed_cost_id, tenant=self.tenant)
            
            if landed_cost.status == 'APPLIED':
                return ServiceResult.error("Landed cost has already been applied")
            
            # Get related stock receipts/movements
            related_movements = landed_cost.related_movements.all()
            
            if not related_movements.exists():
                return ServiceResult.error("No related movements found for landed cost")
            
            # Calculate total base cost for allocation
            total_base_cost = sum(
                item.quantity * item.unit_cost
                for movement in related_movements
                for item in movement.items.all()
            )
            
            if total_base_cost <= 0:
                return ServiceResult.error("Total base cost is zero, cannot allocate landed costs")
            
            allocations = []
            
            # Allocate landed costs proportionally
            for movement in related_movements:
                for movement_item in movement.items.all():
                    item_base_cost = movement_item.quantity * movement_item.unit_cost
                    allocation_percentage = item_base_cost / total_base_cost
                    allocated_cost = landed_cost.total_cost * allocation_percentage
                    
                    # Create allocation record
                    allocation = LandedCostAllocation.objects.create(
                        tenant=self.tenant,
                        landed_cost=landed_cost,
                        stock_item=movement_item.stock_item,
                        movement_item=movement_item,
                        base_cost=item_base_cost,
                        allocated_cost=allocated_cost,
                        allocation_percentage=allocation_percentage * 100
                    )
                    allocations.append(allocation)
                    
                    # Update valuation layers with landed cost
                    self._apply_landed_cost_to_layers(movement_item, allocated_cost)
            
            # Mark landed cost as applied
            landed_cost.status = 'APPLIED'
            landed_cost.applied_date = timezone.now()
            landed_cost.applied_by = self.user
            landed_cost.save()
            
            return ServiceResult.success(data={
                'landed_cost': landed_cost,
                'allocations': allocations,
                'total_allocated': sum(a.allocated_cost for a in allocations)
            })
            
        except LandedCost.DoesNotExist:
            return ServiceResult.error("Landed cost not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to apply landed costs: {str(e)}")
    
    def _apply_landed_cost_to_layers(self, movement_item: StockMovementItem, allocated_cost: Decimal):
        """Apply allocated landed cost to valuation layers"""
        # Find the valuation layer created for this movement item
        layer = StockValuationLayer.objects.filter(
            movement_item=movement_item,
            quantity_in__gt=0
        ).first()
        
        if layer and layer.quantity_remaining > 0:
            # Calculate additional cost per unit
            additional_cost_per_unit = allocated_cost / layer.quantity_in
            
            # Update layer cost
            layer.unit_cost += additional_cost_per_unit
            layer.total_cost = layer.quantity_remaining * layer.unit_cost
            layer.landed_cost_allocated += allocated_cost
            layer.save()
            
            # Update stock item average cost
            self._update_average_cost(layer.stock_item)
    
    def get_cost_analysis(self, stock_item_id: int) -> ServiceResult:
        """Get detailed cost analysis for a stock item"""
        try:
            stock_item = StockItem.objects.get(id=stock_item_id, tenant=self.tenant)
            
            # Get all valuation layers
            layers = StockValuationLayer.objects.filter(
                stock_item=stock_item
            ).order_by('layer_date')
            
            layer_data = []
            for layer in layers:
                layer_data.append({
                    'date': layer.layer_date,
                    'quantity_in': layer.quantity_in,
                    'quantity_out': layer.quantity_out,
                    'quantity_remaining': layer.quantity_remaining,
                    'unit_cost': layer.unit_cost,
                    'total_cost': layer.total_cost,
                    'landed_cost_allocated': layer.landed_cost_allocated,
                    'movement_reference': layer.movement_item.movement.reference_number if layer.movement_item else None
                })
            
            # Calculate current inventory value
            current_value = self._calculate_fifo_lifo_value(stock_item)
            
            return ServiceResult.success(data={
                'stock_item': {
                    'id': stock_item.id,
                    'product_name': stock_item.product.name,
                    'quantity_on_hand': stock_item.quantity_on_hand,
                    'average_unit_cost': stock_item.average_unit_cost,
                    'current_inventory_value': current_value
                },
                'layers': layer_data,
                'costing_method': self.costing_method
            })
            
        except StockItem.DoesNotExist:
            return ServiceResult.error("Stock item not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to get cost analysis: {str(e)}")