from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockTransfer, StockTransferItem, StockItem, 
    Warehouse, Product
)

class TransferService(BaseService):
    """
    Service for handling stock transfers between warehouses
    """
    
    @transaction.atomic
    def create_ ServiceResult:
        """
        Create a new stock transfer
        """
        try:
            self.validate_tenant()
            
            # Validate transfer data
            validation_result = self._validate_transfer_data(transfer_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create transfer
            transfer = StockTransfer.objects.create(
                tenant=self.tenant,
                requested_by=self.user,
                **transfer_data
            )
            
            # Process transfer items
            total_quantity = Decimal('0')
            total_value = Decimal('0')
            transfer_items = []
            
             stock item
                source_stock_item = StockItem.objects.get(
                    id=item_data['source_stock_item_id'],
                    tenant=self.tenant
                )
                
                transfer_item = StockTransferItem.objects.create(
                    transfer=transfer,
                    source_stock_item=source_stock_item,
                    **item_data
                )
                
                transfer_items.append(transfer_item)
                total_quantity += transfer_item.quantity_requested
                total_value += transfer_item.quantity_requested * source_stock_item.unit_cost
            
            # Update transfer totals
            transfer.total_quantity = total_quantity
            transfer.total_value = total_value
            transfer.save()
            
            # Reserve stock at source
            reservation_result = self._reserve_stock_for_transfer(transfer)
            if not reservation_result.is_success:
                raise Exception(f"Failed to reserve stock: {reservation_result.message}")
            
            # Send transfer notification
            self._send_transfer_notification(transfer)
            
            self.log_operation('create_transfer', {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'source_warehouse': transfer.source_warehouse.name,
                'destination_warehouse': transfer.destination_warehouse.name,
                'total_quantity': float(total_quantity)
            })
            
            return ServiceResult.success(
                data=transfer,
                message=f"Stock Transfer {transfer.transfer_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create stock transfer: {str(e)}",
                errors={'transfer': [str(e)]}
            )
    
    str, Any]]) -> ServiceResult:
        """Validate transfer data"""
        errors = {}
        
        # Validate warehouses
        try:
            source_warehouse = Warehouse.objects.get(
                id=transfer_data.get('source_warehouse_id'),
                tenant=self.tenant,
                is_active=True
            )
            destination_warehouse = Warehouse.objects.get(
                id=transfer_data.get('destination_warehouse_id'),
                tenant=self.tenant,
                is_active=True
            )
            
            # Cannot transfer to same warehouse
            if source_warehouse == destination_warehouse:
                errors['warehouses'] = ['Source and destination warehouses cannot be the same']
                
        except Warehouse.DoesNotExist:
            errors['warehouses'] = ['Invalid source or destination warehouse']
        
        # Validate transfer date
        if transfer_data.get('requested_date'):
            if transfer_data['requested_date'] < timezone.now().date():
                errors['requested_date'] = ['Transfer date cannot be in the past']
        
        # Validate items
        if item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate stock item
            try:
                stock_item = StockItem.objects.get(
                    id=item_data.get('source_stock_item_id'),
                    tenant=self.tenant,
                    warehouse_id=transfer_data.get('source_warehouse_id')
                )
                
                # Check available quantity
                available = stock_item.quantity_on_hand - stock_item.quantity_reserved
                requested = item_data.get('quantity_requested', 0)
                
                if requested <= 0:
                    item_errors.append('Quantity must be greater than zero')
                elif requested > available:
                    item_errors.append(f'Insufficient stock. Available: {available}')
                    
            except StockItem.DoesNotExist:
                item_errors.append('Invalid stock item or item not in source warehouse')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _reserve_stock_for_transfer(self, transfer: StockTransfer) -> ServiceResult:
        """Reserve stock at source warehouse"""
        try:
            for item in transfer.items.all():
                stock_item = item.source_stock_item
                stock_item.quantity_reserved += item.quantity_requested
                stock_item.save(update_fields=['quantity_reserved'])
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to reserve stock: {str(e)}")
    
    def _send_transfer_notification(self, transfer: StockTransfer):
        """Send transfer notification to destination warehouse"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_transfer_notification(transfer)
    
    @transaction.atomic
    def approve_transfer(self, transfer_id: int, approval_notes: str = "") -> ServiceResult:
        """Approve a stock transfer"""
        try:
            transfer = StockTransfer.objects.get(id=transfer_id, tenant=self.tenant)
            
            if transfer.status != 'PENDING_APPROVAL':
                return ServiceResult.error("Transfer is not pending approval")
            
            # Update transfer
            transfer.status = 'APPROVED'
            transfer.approved_by = self.user
            transfer.approved_date = timezone.now()
            transfer.approval_notes = approval_notes
            transfer.save()
            
            # Send approval notification
            self._send_approval_notification(transfer)
            
            self.log_operation('approve_transfer', {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'approver': self.user.username
            })
            
            return ServiceResult.success(
                data=transfer,
                message=f"Transfer {transfer.transfer_number} approved successfully"
            )
            
        except StockTransfer.DoesNotExist:
            return ServiceResult.error("Transfer not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to approve transfer: {str(e)}")
    
    def _send_approval_notification(self, transfer: StockTransfer):
        """Send approval notification"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_transfer_approved_notification(transfer)
    
    @transaction.atomic
    def ship_transfer(self, transfer_id: int, shipment_data: Dict[str, Any]) -> ServiceResult:
        """Ship approved transfer"""
        try:
            transfer = StockTransfer.objects.get(id=transfer_id, tenant=self.tenant)
            
            if transfer.status != 'APPROVED':
                return ServiceResult.error("Transfer must be approved before shipping")
            
            # Update transfer with shipment details
            transfer.status = 'IN_TRANSIT'
            transfer.shipped_by = self.user
            transfer.shipped_date = timezone.now()
            transfer.tracking_number = shipment_data.get('tracking_number', '')
            transfer.carrier = shipment_data.get('carrier', '')
            transfer.estimated_delivery_date = shipment_data.get('estimated_delivery_date')
            transfer.save()
            
            # Create outbound stock movement at source
            outbound_result = self._create_outbound_movement(transfer)
            if not outbound_result.is_success:
                raise Exception(f"Failed to create outbound movement: {outbound_result.message}")
            
            # Send shipment notification
            self._send_shipment_notification(transfer)
            
            self.log_operation('ship_transfer', {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'tracking_number': transfer.tracking_number
            })
            
            return ServiceResult.success(
                data=transfer,
                message=f"Transfer {transfer.transfer_number} shipped successfully"
            )
            
        except StockTransfer.DoesNotExist:
            return ServiceResult.error("Transfer not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to ship transfer: {str(e)}")
    
    def _create_outbound_movement(self, transfer: StockTransfer) -> ServiceResult:
        """Create outbound stock movement at source warehouse"""
        try:
            from ...services.stock.movement_service import StockMovementService
            
            movement_service = StockMovementService(tenant=self.tenant, user=self.user)
            
            movement_data = {
                'movement_type': 'TRANSFER_OUT',
                'warehouse_id': transfer.source_warehouse.id,
                'reference_number': f"OUT-{transfer.transfer_number}",
                'notes': f'Outbound transfer to {transfer.destination_warehouse.name}'
            }
            
            movement_items = []
            for item in transfer.items.all():
                movement_items.append({
                    'stock_item_id': item.source_stock_item.id,
                    'quantity': item.quantity_requested,
                    'unit_cost': item.source_stock_item.unit_cost,
                    'notes': f'Transfer to {transfer.destination_warehouse.name}'
                })
            
            return movement_service.create_movement(movement_data, movement_items)
            
        except Exception as e:
            return ServiceResult.error(f"Failed to create outbound movement: {str(e)}")
    
    def _send_shipment_notification(self, transfer: StockTransfer):
        """Send shipment notification"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_transfer_shipped_notification(transfer)
    
    @transaction.atomic
    def receive_transfer(self, transfer_id: int, 
                        receipt_data: Dict[str, Any]) -> ServiceResult:
        """Receive transfer at destination"""
        try:
            transfer = StockTransfer.objects.get(id=transfer_id, tenant=self.tenant)
            
            if transfer.status != 'IN_TRANSIT':
                return ServiceResult.error("Transfer is not in transit")
            
            # Process received quantities
            total_received = Decimal('0')
            for item_data in receipt_data.get('items', []):
                transfer_item = StockTransferItem.objects.get(
                    id=item_data['transfer_item_id'],
                    transfer=transfer
                )
                
                received_qty = item_data.get('quantity_received', 0)
                transfer_item.quantity_received = received_qty
                transfer_item.quantity_damaged = item_data.get('quantity_damaged', 0)
                transfer_item.received_notes = item_data.get('notes', '')
                transfer_item.save()
                
                total_received += received_qty
            
            # Update transfer
            transfer.status = 'COMPLETED' if total_received > 0 else 'CANCELLED'
            transfer.received_by = self.user
            transfer.received_date = timezone.now()
            transfer.total_quantity_received = total_received
            transfer.receiver_notes = receipt_data.get('notes', '')
            transfer.save()
            
            # Create inbound stock movement at destination
            if total_received > 0:
                inbound_result = self._create_inbound_movement(transfer)
                if not inbound_result.is_success:
                    raise Exception(f"Failed to create inbound movement: {inbound_result.message}")
            
            # Handle damages if any
            if any(item.quantity_damaged > 0 for item in transfer.items.all()):
                self._handle_transfer_damages(transfer)
            
            self.log_operation('receive_transfer', {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'total_received': float(total_received)
            })
            
            return ServiceResult.success(
                data=transfer,
                message=f"Transfer {transfer.transfer_number} received successfully"
            )
            
        except StockTransfer.DoesNotExist:
            return ServiceResult.error("Transfer not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to receive transfer: {str(e)}")
    
    def _create_inbound_movement(self, transfer: StockTransfer) -> ServiceResult:
        """Create inbound stock movement at destination warehouse"""
        try:
            from ...services.stock.movement_service import StockMovementService
            
            movement_service = StockMovementService(tenant=self.tenant, user=self.user)
            
            movement_data = {
                'movement_type': 'TRANSFER_IN',
                'warehouse_id': transfer.destination_warehouse.id,
                'reference_number': f"IN-{transfer.transfer_number}",
                'notes': f'Inbound transfer from {transfer.source_warehouse.name}'
            }
            
            movement_items = []
            for item in transfer.items.filter(quantity_received__gt=0):
                # Get or create stock item at destination
                dest_stock_item, created = StockItem.objects.get_or_create(
                    tenant=self.tenant,
                    product=item.source_stock_item.product,
                    warehouse=transfer.destination_warehouse,
                    defaults={
                        'unit_cost': item.source_stock_item.unit_cost,
                        'reorder_level': item.source_stock_item.reorder_level,
                        'maximum_stock_level': item.source_stock_item.maximum_stock_level
                    }
                )
                
                movement_items.append({
                    'stock_item_id': dest_stock_item.id,
                    'quantity': item.quantity_received,
                    'unit_cost': item.source_stock_item.unit_cost,
                    'notes': f'Transfer from {transfer.source_warehouse.name}'
                })
            
            return movement_service.create_movement(movement_data, movement_items)
            
        except Exception as e:
            return ServiceResult.error(f"Failed to create inbound movement: {str(e)}")
    
    def _handle_transfer_damages(self, transfer: StockTransfer):
        """Handle damaged items in transfer"""
        from ...services.adjustments.adjustment_service import AdjustmentService
        
        adjustment_service = AdjustmentService(tenant=self.tenant, user=self.user)
        
        # Create adjustment for damages at destination
        damaged_items = transfer.items.filter(quantity_damaged__gt=0)
        
        if damaged_items.exists():
            adjustment_data = {
                'warehouse_id': transfer.destination_warehouse.id,
                'adjustment_type': 'TRANSFER_DAMAGE',
                'reason': 'Damaged during transfer',
                'notes': f'Damage adjustment for transfer {transfer.transfer_number}'
            }
            
            items_data = []
            for item in damaged_items:
                dest_stock_item = StockItem.objects.get_or_create(
                    tenant=self.tenant,
                    product=item.source_stock_item.product,
                    warehouse=transfer.destination_warehouse,
                    defaults={'unit_cost': item.source_stock_item.unit_cost}
                )[0]
                
                items_data.append({
                    'stock_item_id': dest_stock_item.id,
                    'quantity': -item.quantity_damaged,  # Negative adjustment
                    'unit_cost': item.source_stock_item.unit_cost,
                    'reason': 'Transfer damage'
                })
            
            adjustment_service.create_adjustment(adjustment_data, items_data)
    
    def get_transfer_summary(self, start_date: Optional[timezone.datetime] = None,
                            end_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Get transfer summary for a period"""
        try:
            queryset = StockTransfer.objects.for_tenant(self.tenant)
            
            if start_date and end_date:
                queryset = queryset.filter(requested_date__range=[start_date.date(), end_date.date()])
            
            summary = queryset.aggregate(
                total_transfers=Count('id'),
                total_quantity=Sum('total_quantity'),
                total_value=Sum('total_value'),
                pending_approval=Count('id', filter=Q(status='PENDING_APPROVAL')),
                approved=Count('id', filter=Q(status='APPROVED')),
                in_transit=Count('id', filter=Q(status='IN_TRANSIT')),
                completed=Count('id', filter=Q(status='COMPLETED')),
                cancelled=Count('id', filter=Q(status='CANCELLED'))
            )
            
            # Get warehouse-wise breakdown
            warehouse_breakdown = queryset.values(
                'source_warehouse__name',
                'destination_warehouse__name'
            ).annotate(
                transfer_count=Count('id'),
                total_value=Sum('total_value')
            ).order_by('-total_value')
            
            return ServiceResult.success(data={
                'summary': summary,
                'warehouse_breakdown': list(warehouse_breakdown)
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get transfer summary: {str(e)}")
    
    @transaction.atomic
    def cancel_transfer(self, transfer_id: int, reason: str = "") -> ServiceResult:
        """Cancel a transfer and release reserved stock"""
        try:
            transfer = StockTransfer.objects.get(id=transfer_id, tenant=self.tenant)
            
            if transfer.status in ['COMPLETED', 'CANCELLED']:
                return ServiceResult.error("Cannot cancel completed or already cancelled transfer")
            
            # Release reserved stock
            for item in transfer.items.all():
                stock_item = item.source_stock_item
                stock_item.quantity_reserved -= item.quantity_requested
                stock_item.save(update_fields=['quantity_reserved'])
            
            # Update transfer
            transfer.status = 'CANCELLED'
            transfer.cancelled_by = self.user
            transfer.cancelled_date = timezone.now()
            transfer.cancellation_reason = reason
            transfer.save()
            
            self.log_operation('cancel_transfer', {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'reason': reason
            })
            
            return ServiceResult.success(
                data=transfer,
                message=f"Transfer {transfer.transfer_number} cancelled successfully"
            )
            
        except StockTransfer.DoesNotExist:
            return ServiceResult.error("Transfer not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to cancel transfer: {str(e)}")