from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockReservation, StockReservationItem, StockItem,
    ReservationFulfillment
)

class StockReservationService(BaseService):
    """
    Service for handling stock reservations and allocations
    """
    
    PRIORITY_LEVELS = {
        'LOW': 1,
        'MEDIUM': 2,
        'HIGH': 3,
        'CRITICAL': 4
    }
    
    FULFILLMENT_STRATEGIES = {
        'FIFO': 'First In First Out',
        'LIFO': 'Last In Last Out', 
        'PRIORITY': 'Priority Based',
        'PARTIAL_ALLOWED': 'Allow Partial Fulfillment',
        'ALL_OR_NOTHING': 'All or Nothing'
    }
    
    @transaction.atomic
    def create_ Any]]) -> ServiceResult:
        """
        Create a new stock reservation
        """
        try:
            self.validate_tenant()
            
            # Validate reservation data
            validation_result = self._validate_reservation_data(reservation_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create reservation
            reservation = StockReservation.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **reservation_data
            )
            
            # Process reservation items
            reserved_items = []
            total_quantity = Decimal('0')
            total_value = Decimal('0')
            
            for item_data in items_item = StockItem.objects.get(
                    id=item_data['stock_item_id'],
                    tenant=self.tenant
                )
                
                # Check availability
                available_qty = self._get_available_quantity(stock_item)
                requested_qty = item_data['quantity_requested']
                
                # Determine fulfillment strategy
                strategy = reservation_data.get('fulfillment_strategy', 'PARTIAL_ALLOWED')
                
                if strategy == 'ALL_OR_NOTHING' and available_qty < requested_qty:
                    raise Exception(f"Insufficient stock for {stock_item.product.name}. Available: {available_qty}, Requested: {requested_qty}")
                
                # Calculate actual reserved quantity
                reserved_qty = min(available_qty, requested_qty) if strategy == 'PARTIAL_ALLOWED' else requested_qty
                
                if reserved_qty > 0:
                    # Create reservation item
                    reservation_item = StockReservationItem.objects.create(
                        reservation=reservation,
                        stock_item=stock_item,
                        quantity_requested=requested_qty,
                        quantity_reserved=reserved_qty,
                        unit_price=item_data.get('unit_price', stock_item.unit_cost),
                        notes=item_data.get('notes', '')
                    )
                    
                    # Update stock item reservation
                    stock_item.quantity_reserved += reserved_qty
                    stock_item.save(update_fields=['quantity_reserved'])
                    
                    reserved_items.append(reservation_item)
                    total_quantity += reserved_qty
                    total_value += reserved_qty * reservation_item.unit_price
            
            # Update reservation totals
            reservation.total_quantity_requested = sum(item['quantity_requested'] for item in items_data)
            reservation.total_quantity_reserved = total_quantity
            reservation.total_value = total_value
            reservation.save()
            
            # Update status based on fulfillment
            if total_quantity == 0:
                reservation.status = 'FAILED'
            elif reservation.total_quantity_reserved < reservation.total_quantity_requested:
                reservation.status = 'PARTIALLY_RESERVED'
            else:
                reservation.status = 'RESERVED'
            
            reservation.save(update_fields=['status'])
            
            self.log_operation('create_reservation', {
                'reservation_id': reservation.id,
                'total_items': len(reserved_items),
                'total_quantity': float(total_quantity)
            })
            
            return ServiceResult.success(
                data=reservation,
                message=f"Reservation {reservation.reference_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create reservation: {str(e)}",
                errors={'reservation': [str(e)]}
            )
    
    def _validate_reservation_data(str, Any]]) -> ServiceResult:
        """Validate reservation data"""
        errors = {}
        
        # Validate reservation type
        valid_types = ['SALES_ORDER', 'TRANSFER', 'PRODUCTION', 'CUSTOMER_HOLD', 'QUALITY_HOLD']
        if reservation_data.get('reservation_type') not in valid_types:
            errors['reservation_type'] = ['Invalid reservation type']
        
        # Validate priority
        if reservation_data.get('priority') not in self.PRIORITY_LEVELS:
            errors['priority'] = ['Invalid priority level']
        
        # Validate fulfillment strategy
        if reservation_data.get('fulfillment_strategy') not in self.FULFILLMENT_STRATEGIES:
            errors['fulfillment_strategy'] = ['Invalid fulfillment strategy']
        
        # Validate items
         least one item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate stock item
            try:
                StockItem.objects.get(
                    id=item_data.get('stock_item_id'),
                    tenant=self.tenant
                )
            except StockItem.DoesNotExist:
                item_errors.append('Invalid stock item')
            
            # Validate quantity
            if not item_data.get('quantity_requested') or item_data.get('quantity_requested') <= 0:
                item_errors.append('Quantity requested must be greater than zero')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _get_available_quantity(self, stock_item: StockItem) -> Decimal:
        """Get available quantity for reservation"""
        return stock_item.quantity_on_hand - stock_item.quantity_reserved
    
    @transaction.atomic
    def fulfill_reservation(self, reservation_id: int, 
                          fulf None) -> ServiceResult:
        """
        Fulfill a stock reservation by creating stock movements
        """
        try:
            reservation = StockReservation.objects.get(id=reservation_id, tenant=self.tenant)
            
            if reservation.status not in ['RESERVED', 'PARTIALLY_RESERVED']:
                return ServiceResult.error("Reservation cannot be fulfilled in current status")
            
            # Create fulfillment records
            fulfillments = []
            total_fulfilled = Decimal('0')
            
            for reservation_item in reservation.items.all():
                if reservation_item.quantity_reserved > 0:
                    # Create fulfillment
                    fulfillment = ReservationFulfillment.objects.create(
                        tenant=self.tenant,
                        reservation_item=reservation_item,
                        quantity_fulfilled=reservation_item.quantity_reserved,
                        fulfillment_date=timezone.now(),
                        fulfilled_by=self.user,
                        notes=fulfillment_data.get('notes', '') if fulfillment_data else ''
                    )
                    
                    # Update stock item quantities
                    stock_item = reservation_item.stock_item
                    stock_item.quantity_reserved -= reservation_item.quantity_reserved
                    stock_item.quantity_on_hand -= reservation_item.quantity_reserved
                    stock_item.save()
                    
                    # Create stock movement for the fulfillment
                    self._create_fulfillment_movement(reservation_item, fulfillment)
                    
                    fulfillments.append(fulfillment)
                    total_fulfilled += fulfillment.quantity_fulfilled
            
            # Update reservation status
            reservation.status = 'FULFILLED'
            reservation.fulfilled_date = timezone.now()
            reservation.fulfilled_by = self.user
            reservation.total_quantity_fulfilled = total_fulfilled
            reservation.save()
            
            self.log_operation('fulfill_reservation', {
                'reservation_id': reservation.id,
                'total_fulfilled': float(total_fulfilled)
            })
            
            return ServiceResult.success(
                data={'fulfillments': fulfillments},
                message=f"Reservation {reservation.reference_number} fulfilled successfully"
            )
            
        except StockReservation.DoesNotExist:
            return ServiceResult.error("Reservation not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to fulfill reservation: {str(e)}")
    
    def _create_fulfillment_movement(self, reservation_item: StockReservationItem, 
                                   fulfillment: ReservationFulfillment):
        """Create stock movement for reservation fulfillment"""
        from ...services.stock.movement_service import StockMovementService
        
        movement_service = StockMovementService(tenant=self.tenant, user=self.user)
        
        movement_data = {
            'movement_type': 'ISSUE',
            'warehouse_id': reservation_item.stock_item.warehouse.id,
            'reference_number': f"RES-{reservation_item.reservation.reference_number}",
            'notes': f"Fulfillment of reservation {reservation_item.reservation.reference_number}"
        }
        
        items_data = [{
            'stock_item_id': reservation_item.stock_item.id,
            'quantity': fulfillment.quantity_fulfilled,
            'unit_cost': reservation_item.stock_item.unit_cost,
            'notes': f"Reservation fulfillment"
        }]
        
        return movement_service.create_movement(movement_data, items_data)
    
    @transaction.atomic
    def cancel_reservation(self, reservation_id: int, reason: str = "") -> ServiceResult:
        """
        Cancel a stock reservation and release reserved stock
        """
        try:
            reservation = StockReservation.objects.get(id=reservation_id, tenant=self.tenant)
            
            if reservation.status == 'CANCELLED':
                return ServiceResult.error("Reservation is already cancelled")
            
            if reservation.status == 'FULFILLED':
                return ServiceResult.error("Cannot cancel a fulfilled reservation")
            
            # Release reserved quantities
            for reservation_item in reservation.items.all():
                if reservation_item.quantity_reserved > 0:
                    stock_item = reservation_item.stock_item
                    stock_item.quantity_reserved -= reservation_item.quantity_reserved
                    stock_item.save(update_fields=['quantity_reserved'])
                    
                    # Update reservation item
                    reservation_item.quantity_cancelled = reservation_item.quantity_reserved
                    reservation_item.quantity_reserved = 0
                    reservation_item.save()
            
            # Update reservation status
            reservation.status = 'CANCELLED'
            reservation.cancelled_date = timezone.now()
            reservation.cancelled_by = self.user
            reservation.cancellation_reason = reason
            reservation.save()
            
            self.log_operation('cancel_reservation', {
                'reservation_id': reservation.id,
                'reason': reason
            })
            
            return ServiceResult.success(
                data=reservation,
                message=f"Reservation {reservation.reference_number} cancelled successfully"
            )
            
        except StockReservation.DoesNotExist:
            return ServiceResult.error("Reservation not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to cancel reservation: {str(e)}")
    
    def get_reservation_availability, Any]]) -> ServiceResult:
        """
        Check availability for potential reservation without creating it
        """
        try:
            availability_results = []
            
            for item_data in items_data:
                stock_item = StockItem.objects.get(
                    id=item_data['stock_item_id'],
                    tenant=self.tenant
                )
                
                available_qty = self._get_available_quantity(stock_item)
                requested_qty = item_data['quantity_requested']
                
                availability_results.append({
                    'stock_item_id': stock_item.id,
                    'product_name': stock_item.product.name,
                    'requested_quantity': requested_qty,
                    'available_quantity': available_qty,
                    'can_fulfill_fully': available_qty >= requested_qty,
                    'shortfall': max(0, requested_qty - available_qty)
                })
            
            total_shortfall = sum(item['shortfall'] for item in availability_results)
            can_fulfill_all = total_shortfall == 0
            
            return ServiceResult.success(data={
                'can_fulfill_all': can_fulfill_all,
                'total_shortfall': total_shortfall,
                'items': availability_results
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to check availability: {str(e)}")
    
    def get_reservation_queue(self, stock_item_id: int) -> ServiceResult:
        """
        Get reservation queue for a stock item ordered by priority and date
        """
        try:
            reservations = StockReservationItem.objects.filter(
                stock_item_id=stock_item_id,
                stock_item__tenant=self.tenant,
                reservation__status__in=['RESERVED', 'PARTIALLY_RESERVED']
            ).select_related('reservation').annotate(
                priority_value=models.Case(
                    *[models.When(reservation__priority=k, then=models.Value(v)) 
                      for k, v in self.PRIORITY_LEVELS.items()],
                    default=models.Value(1)
                )
            ).order_by('-priority_value', 'reservation__created_at')
            
            queue_data = []
            for item in reservations:
                queue_data.append({
                    'reservation_id': item.reservation.id,
                    'reference_number': item.reservation.reference_number,
                    'priority': item.reservation.priority,
                    'quantity_reserved': item.quantity_reserved,
                    'reservation_date': item.reservation.created_at,
                    'expected_fulfillment_date': item.reservation.expected_fulfillment_date,
                    'customer': item.reservation.customer_reference
                })
            
            return ServiceResult.success(data=queue_data)
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get reservation queue: {str(e)}")