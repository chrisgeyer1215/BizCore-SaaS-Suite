from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockMovement, StockMovementItem, StockItem, 
    Product, Warehouse, StockValuationLayer
)

class StockMovementService(BaseService):
    """
    Service for handling stock movements and inventory transactions
    """
    
    MOVEMENT_TYPES = {
        'RECEIPT': 'Stock Receipt',
        'ISSUE': 'Stock Issue', 
        'TRANSFER_OUT': 'Transfer Out',
        'TRANSFER_IN': 'Transfer In',
        'ADJUSTMENT_POSITIVE': 'Positive Adjustment',
        'ADJUSTMENT_NEGATIVE': 'Negative Adjustment',
        'PRODUCTION_CONSUMPTION': 'Production Consumption',
        'PRODUCTION_OUTPUT': 'Production Output',
        'RETURN_FROM_CUSTOMER': 'Return from Customer',
        'RETURN_TO_SUPPLIER': 'Return to Supplier',
        'DAMAGED': 'Damaged Stock',
        'EXPIRED': 'Expired Stock',
        'LOST': 'Lost Stock',
        'FOUND': 'Found Stock',
        'CYCLE_COUNT': 'Cycle Count',
        'OPENING_BALANCE': 'Opening Balance',
        'RESERVATION': 'Reservation',
        'UNRESERVATION': 'Unreservation',
    }
    
    @transaction.atomic
    def create_ Any]]) -> ServiceResult:
        """
        Create a new stock movement with items
        """
        try:
            self.validate_tenant()
            
            # Validate movement data
            validation_result = self._validate_movement_data(movement_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create movement
            movement = StockMovement.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **movement_data
            )
            
            # Process items
            total_quantity = Decimal('0')
            total_value = Decimal('0')
            
            for item_data Create movement item
                movement_item = StockMovementItem.objects.create(
                    movement=movement,
                    **item_data
                )
                
                # Update stock levels
                stock_update_result = self._update_stock_levels(movement_item)
                if not stock_update_result.is_success:
                    raise Exception(f"Failed to update stock: {stock_update_result.message}")
                
                # Update valuation layers
                self._update_valuation_layers(movement_item)
                
                total_quantity += movement_item.quantity
                total_value += movement_item.quantity * movement_item.unit_cost
            
            # Update movement totals
            movement.total_quantity = total_quantity
            movement.total_value = total_value
            movement.save(update_fields=['total_quantity', 'total_value'])
            
            # Generate alerts if needed
            self._check_and_generate_alerts(movement)
            
            self.log_operation('create_movement', {
                'movement_id': movement.id,
                'movement_type': movement.movement_type,
                'total_quantity': float(total_quantity)
            })
            
            return ServiceResult.success(
                data=movement,
                message=f"Stock movement {movement.reference_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create stock movement: {str(e)}",
                errors={'movement': [str(e)]}
            )
    
    def _validate_movement_data( List[Dict[str, Any]]) -> ServiceResult:
        """Validate movement and items data"""
        errors = {}
        
        # Validate movement type
        if movement_data.get('movement_type') not in self.MOVEMENT_TYPES:
            errors['movement_type'] = ['Invalid movement type']
        
        # Validate warehouse
        try:
            warehouse = Warehouse.objects.get(
                id=movement_data.get('warehouse_id'),
                tenant=self.tenant
            )
        except Warehouse.DoesNotExist:
            errors['warehouse'] = ['Invalid warehouse']
        
        #['items'] = ['At least one item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate stock item
            try:
                stock_item = StockItem.objects.get(
                    id=item_data.get('stock_item_id'),
                    tenant=self.tenant
                )
                
                # Check available quantity for outbound movements
                if movement_data.get('movement_type') in ['ISSUE', 'TRANSFER_OUT', 'ADJUSTMENT_NEGATIVE']:
                    available = stock_item.quantity_on_hand - stock_item.quantity_reserved
                    if item_data.get('quantity', 0) > available:
                        item_errors.append(f'Insufficient stock. Available: {available}')
                
            except StockItem.DoesNotExist:
                item_errors.append('Invalid stock item')
            
            # Validate quantity
            if not item_data.get('quantity') or item_data.get('quantity') <= 0:
                item_errors.append('Quantity must be greater than zero')
            
            # Validate unit cost
            if not item_data.get('unit_cost') or item_data.get('unit_cost') < 0:
                item_errors.append('Unit cost must be non-negative')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _update_stock_levels(self, movement_item: StockMovementItem) -> ServiceResult:
        """Update stock levels based on movement"""
        try:
            stock_item = movement_item.stock_item
            quantity = movement_item.quantity
            movement_type = movement_item.movement.movement_type
            
            # Determine if this is an inbound or outbound movement
            inbound_movements = [
                'RECEIPT', 'TRANSFER_IN', 'ADJUSTMENT_POSITIVE', 
                'PRODUCTION_OUTPUT', 'RETURN_FROM_CUSTOMER', 'FOUND'
            ]
            
            outbound_movements = [
                'ISSUE', 'TRANSFER_OUT', 'ADJUSTMENT_NEGATIVE',
                'PRODUCTION_CONSUMPTION', 'RETURN_TO_SUPPLIER', 
                'DAMAGED', 'EXPIRED', 'LOST'
            ]
            
            if movement_type in inbound_movements:
                # Increase stock
                stock_item.quantity_on_hand += quantity
                stock_item.total_quantity_received += quantity
                
                # Update costs for receipts
                if movement_type == 'RECEIPT':
                    # Weighted average cost calculation
                    total_value = (stock_item.quantity_on_hand - quantity) * stock_item.unit_cost
                    total_value += quantity * movement_item.unit_cost
                    total_quantity = stock_item.quantity_on_hand
                    
                    if total_quantity > 0:
                        stock_item.unit_cost = total_value / total_quantity
                
            elif movement_type in outbound_movements:
                # Decrease stock
                stock_item.quantity_on_hand -= quantity
                stock_item.total_quantity_issued += quantity
                
            elif movement_type == 'RESERVATION':
                # Reserve stock
                stock_item.quantity_reserved += quantity
                
            elif movement_type == 'UNRESERVATION':
                # Unreserve stock
                stock_item.quantity_reserved -= quantity
            
            # Update last movement date
            stock_item.last_movement_date = timezone.now()
            
            # Update ABC classification if needed
            if movement_type in inbound_movements + outbound_movements:
                stock_item.movement_count += 1
            
            stock_item.save()
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to update stock levels: {str(e)}")
    
    def _update_valuation_layers(self, movement_item: StockMovementItem):
        """Update stock valuation layers for cost tracking"""
        from ...services.stock.valuation_service import StockValuationService
        
        valuation_service = StockValuationService(tenant=self.tenant, user=self.user)
        valuation_service.update_valuation_layers(movement_item)
    
    def _check_and_generate_alerts(self, movement: StockMovement):
        """Check if alerts need to be generated after movement"""
        from ...services.alerts.alert_service import AlertService
        
        alert_service = AlertService(tenant=self.tenant, user=self.user)
        
        for item in movement.items.all():
            stock_item = item.stock_item
            
            # Check for low stock
            if stock_item.quantity_on_hand <= stock_item.reorder_level:
                alert_service.create_low_stock_alert(stock_item)
            
            # Check for negative stock
            if stock_item.quantity_on_hand < 0:
                alert_service.create_negative_stock_alert(stock_item)
    
    def get_movement_history(self, stock_item_id: int, days: int = 30) -> ServiceResult:
        """Get movement history for a stock item"""
        try:
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=days)
            
            movements = StockMovementItem.objects.filter(
                stock_item_id=stock_item_id,
                stock_item__tenant=self.tenant,
                movement__created_at__range=[start_date, end_date]
            ).select_related(
                'movement', 'stock_item__product'
            ).order_by('-movement__created_at')
            
            movement_data = []
            for item in movements:
                movement_data.append({
                    'date': item.movement.created_at,
                    'type': item.movement.get_movement_type_display(),
                    'quantity': item.quantity,
                    'unit_cost': item.unit_cost,
                    'total_value': item.quantity * item.unit_cost,
                    'reference': item.movement.reference_number,
                    'notes': item.movement.notes
                })
            
            return ServiceResult.success(
                data=movement_data,
                message=f"Retrieved {len(movement_data)} movements"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get movement history: {str(e)}")
    
    @transaction.atomic
    def reverse_movement(self, movement_id: int, reason: str = "") -> ServiceResult:
        """Reverse a stock movement"""
        try:
            movement = StockMovement.objects.get(id=movement_id, tenant=self.tenant)
            
            if movement.status == 'REVERSED':
                return ServiceResult.error("Movement is already reversed")
            
            # Create reverse movement
            reverse_data = {
                'movement_type': self._get_reverse_movement_type(movement.movement_type),
                'warehouse': movement.warehouse,
                'reference_number': f"REV-{movement.reference_number}",
                'notes': f"Reversal of {movement.reference_number}. Reason: {reason}",
                'original_movement': movement
            }
            
            # Get reverse items data
            reverse_items = []
            for item in movement.items.all():
                reverse_items.append({
                    'stock_item_id': item.stock_item.id,
                    'quantity': item.quantity,
                    'unit_cost': item.unit_cost,
                    'notes': f"Reversal of movement item {item.id}"
                })
            
            # Create reverse movement
            reverse_result = self.create_movement(reverse_data, reverse_items)
            
            if reverse_result.is_success:
                # Mark original movement as reversed
                movement.status = 'REVERSED'
                movement.reversed_at = timezone.now()
                movement.reversed_by = self.user
                movement.reversal_reason = reason
                movement.save()
                
                return ServiceResult.success(
                    data=reverse_result.data,
                    message=f"Movement {movement.reference_number} reversed successfully"
                )
            else:
                return reverse_result
                
        except StockMovement.DoesNotExist:
            return ServiceResult.error("Movement not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to reverse movement: {str(e)}")
    
    def _get_reverse_movement_type(self, original_type: str) -> str:
        """Get the reverse movement type"""
        reverse_mapping = {
            'RECEIPT': 'ADJUSTMENT_NEGATIVE',
            'ISSUE': 'ADJUSTMENT_POSITIVE',
            'TRANSFER_OUT': 'TRANSFER_IN',
            'TRANSFER_IN': 'TRANSFER_OUT',
            'ADJUSTMENT_POSITIVE': 'ADJUSTMENT_NEGATIVE',
            'ADJUSTMENT_NEGATIVE': 'ADJUSTMENT_POSITIVE',
            'RESERVATION': 'UNRESERVATION',
            'UNRESERVATION': 'RESERVATION',
        }
        return reverse_mapping.get(original_type, 'ADJUSTMENT_NEGATIVE')
    
    def bulk_create_movements(self, movements_data: List[Dict[str, Any]]) -> ServiceResult:
        """Bulk create multiple stock movements"""
        results = []
        errors = {}
        
        try:
            with transaction.atomic():
                for i, movement_data in enumerate(movements_data):
                    items_data = movement_data.pop('items', [])
                    result = self.create_movement(movement_data, items_data)
                    
                    if result.is_success:
                        results.append(result.data)
                    else:
                        errors[f'movement_{i}'] = result.errors
                        if not result.errors:  # If no specific errors, use the message
                            errors[f'movement_{i}'] = {'general': [result.message]}
                
                if errors:
                    # If there are any errors, rollback the transaction
                    raise Exception("Bulk movement creation failed")
                
                return ServiceResult.success(
                    data=results,
                    message=f"Successfully created {len(results)} movements"
                )
                
        except Exception as e:
            return ServiceResult.error(
                message="Bulk movement creation failed",
                errors=errors
            )