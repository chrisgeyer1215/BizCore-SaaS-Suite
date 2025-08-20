from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockAdjustment, StockAdjustmentItem, StockWriteOff,
    StockItem, Product, Warehouse
)

class AdjustmentService(BaseService):
    """
    Service for handling stock adjustments and write-offs
    """
    
    ADJUSTMENT_TYPES = {
        'PHYSICAL_COUNT': 'Physical Count Adjustment',
        'DAMAGE': 'Damage Adjustment',
        'THEFT': 'Theft/Loss Adjustment',
        'EXPIRY': 'Expiry Adjustment', 
        'QUALITY_REJECTION': 'Quality Rejection',
        'SYSTEM_CORRECTION': 'System Correction',
        'TRANSFER_DAMAGE': 'Transfer Damage',
        'OBSOLETE': 'Obsolete Stock',
        'OTHER': 'Other Adjustment'
    }
    
    @transaction.atomic
    def create_ -> ServiceResult:
        """
        Create a new stock adjustment
        """
        try:
            self.validate_tenant()
            
            # Validate adjustment data
            validation_result = self._validate_adjustment_data(adjustment_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create adjustment
            adjustment = StockAdjustment.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **adjustment_data
            )
            
            # Process adjustment items
            total_quantity = Decimal('0')
            total_value = Decimal('0')
            adjustment_items = []
            
            for item_data in items_data:
                # Get stock item
                stock_item = self._get_or_create_stock_item(
                    item_data, adjustment.warehouse
                )
                
                adjustment_item = StockAdjustmentItem.objects.create(
                    adjustment=adjustment,
                    stock_item=stock_item,
                    **item_data
                )
                
                adjustment_items.append(adjustment_item)
                total_quantity += abs(adjustment_item.quantity_difference)
                total_value += abs(adjustment_item.quantity_difference * adjustment_item.unit_cost)
            
            # Update adjustment totals
            adjustment.total_quantity = total_quantity
            adjustment.total_value = total_value
            adjustment.save()
            
            # Apply adjustment if auto-approved or no approval required
            if self._should_auto_approve(adjustment):
                apply_result = self._apply_adjustment(adjustment)
                if not apply_result.is_success:
                    raise Exception(f"Failed to apply adjustment: {apply_result.message}")
            
            self.log_operation('create_adjustment', {
                'adjustment_id': adjustment.id,
                'adjustment_number': adjustment.adjustment_number,
                'adjustment_type': adjustment.adjustment_type,
                'total_items': len(adjustment_items)
            })
            
            return ServiceResult.success(
                data=adjustment,
                message=f"Stock Adjustment {adjustment.adjustment_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create stock adjustment: {str(e)}",
                errors={'adjustment': [str(e)]}
            )
    
    def _validate_adjustment_data(str, Any], 
                                items
        """Validate adjustment data"""
        errors = {}
        
        # Validate adjustment type
        if adjustment_data.get('adjustment_type') not in self.ADJUSTMENT_TYPES:
            errors['adjustment_type'] = ['Invalid adjustment type']
        
        # Validate warehouse
        try:
            Warehouse.objects.get(
                id=adjustment_data.get('warehouse_id'),
                tenant=self.tenant,
                is_active=True
            )
        except Warehouse.DoesNotExist:
            errors['warehouse'] = ['Invalid warehouse']
        
        # least one item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate quantity difference
            if not item_data.get('quantity_difference'):
                item_errors.append('Quantity difference is required')
            elif item_data.get('quantity_difference') == 0:
                item_errors.append('Quantity difference cannot be zero')
            
            # Validate unit cost
            if not item_data.get('unit_cost') or item_data.get('unit_cost') < 0:
                item_errors.append('Unit cost must be non-negative')
            
            # For negative adjustments, check available stock
            if item_data.get('quantity_difference', 0) < 0:
                try:
                    if item_data.get('stock_item_id'):
                        stock_item = StockItem.objects.get(
                            id=item_data['stock_item_id'],
                            tenant=self.tenant
                        )
                        available = stock_item.quantity_on_hand - stock_item.quantity_reserved
                        required = abs(item_data['quantity_difference'])
                        
                        if required > available:
                            item_errors.append(f'Insufficient stock. Available: {available}')
                except StockItem.DoesNotExist:
                    item_errors.append('Invalid stock item')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _ Dict[str, Any], 
                                warehouse: Warehouse) -> StockItem:
        """Get existing or create new stock item"""
        if item_data.get('stock_item_id'):
            return StockItem.objects.get(
                id=item_data['stock_item_id'],
                tenant=self.tenant
            )
        
        # Create new stock item if product_id provided
        if item_data.get('product_id'):
            product = Product.objects.get(
                id=item_data['product_id'],
                tenant=self.tenant
            )
            
            stock_item, created = StockItem.objects.get_or_create(
                tenant=self.tenant,
                product=product,
                warehouse=warehouse,
                defaults={
                    'unit_cost': item_data.get('unit_cost', 0),
                    'reorder_level': product.default_reorder_level or 0,
                    'maximum_stock_level': product.default_maximum_level or 0
                }
            )
            return stock_item
        
        raise ValueError("Either stock_item_id or product_id must be provided")
    
    def _should_auto_approve(self, adjustment: StockAdjustment) -> bool:
        """Determine if adjustment should be auto-approved"""
        # Auto-approve small adjustments or specific types
        auto_approve_types = ['PHYSICAL_COUNT', 'SYSTEM_CORRECTION']
        auto_approve_threshold = Decimal('1000.00')  # Configurable threshold
        
        return (
            adjustment.adjustment_type in auto_approve_types or
            adjustment.total_value <= auto_approve_threshold
        )
    
    def _apply_adjustment(self, adjustment: StockAdjustment) -> ServiceResult:
        """Apply adjustment to stock levels"""
        try:
            from ...services.stock.movement_service import StockMovementService
            
            movement_service = StockMovementService(tenant=self.tenant, user=self.user)
            
            # Group items by positive/negative adjustments
            positive_items = []
            negative_items = []
            
            for item in adjustment.items.all():
                if item.quantity_difference > 0:
                    positive_items.append(item)
                else:
                    negative_items.append(item)
            
            # Create positive adjustment movement
            if positive_items:
                pos_movement_data = {
                    'movement_type': 'ADJUSTMENT_POSITIVE',
                    'warehouse_id': adjustment.warehouse.id,
                    'reference_number': f"ADJ+-{adjustment.adjustment_number}",
                    'notes': f'Positive adjustment - {adjustment.reason}'
                }
                
                pos_items_data = []
                for item in positive_items:
                    pos_items_data.append({
                        'stock_item_id': item.stock_item.id,
                        'quantity': item.quantity_difference,
                        'unit_cost': item.unit_cost,
                        'notes': item.reason
                    })
                
                pos_result = movement_service.create_movement(pos_movement_data, pos_items_data)
                if not pos_result.is_success:
                    return pos_result
            
            # Create negative adjustment movement
            if negative_items:
                neg_movement_data = {
                    'movement_type': 'ADJUSTMENT_NEGATIVE',
                    'warehouse_id': adjustment.warehouse.id,
                    'reference_number': f"ADJ--{adjustment.adjustment_number}",
                    'notes': f'Negative adjustment - {adjustment.reason}'
                }
                
                neg_items_data = []
                for item in negative_items:
                    neg_items_data.append({
                        'stock_item_id': item.stock_item.id,
                        'quantity': abs(item.quantity_difference),
                        'unit_cost': item.unit_cost,
                        'notes': item.reason
                    })
                
                neg_result = movement_service.create_movement(neg_movement_data, neg_items_data)
                if not neg_result.is_success:
                    return neg_result
            
            # Update adjustment status
            adjustment.status = 'APPLIED'
            adjustment.applied_date = timezone.now()
            adjustment.applied_by = self.user
            adjustment.save()
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to apply adjustment: {str(e)}")
    
    @transaction.atomic
    def approve_adjustment(self, adjustment_id: int, approval_notes: str = "") -> ServiceResult:
        """Approve a stock adjustment"""
        try:
            adjustment = StockAdjustment.objects.get(id=adjustment_id, tenant=self.tenant)
            
            if adjustment.status != 'PENDING_APPROVAL':
                return ServiceResult.error("Adjustment is not pending approval")
            
            # Apply the adjustment
            apply_result = self._apply_adjustment(adjustment)
            if not apply_result.is_success:
                return apply_result
            
            # Update approval details
            adjustment.approved_by = self.user
            adjustment.approved_date = timezone.now()
            adjustment.approval_notes = approval_notes
            adjustment.save()
            
            self.log_operation('approve_adjustment', {
                'adjustment_id': adjustment.id,
                'adjustment_number': adjustment.adjustment_number,
                'approver': self.user.username
            })
            
            return ServiceResult.success(
                data=adjustment,
                message=f"Adjustment {adjustment.adjustment_number} approved and applied successfully"
            )
            
        except StockAdjustment.DoesNotExist:
            return ServiceResult.error("Adjustment not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to approve adjustment: {str(e)}")
    
    @transaction.atomic
    def create_write_off(self, write -> ServiceResult:
        """Create a stock write-off"""
        try:
            self.validate_tenant()
            
            # Create write-off record
            write_off = StockWriteOff.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **write_off_data
            )
            
            # Create corresponding negative adjustment
            adjustment_data = {
                'warehouse_id': write_off.stock_item.warehouse.id,
                'adjustment_type': 'WRITE_OFF',
                'reason': f'Write-off: {write_off.reason}',
                'notes': f'Stock write-off #{write_off.id}',
                'requires_approval': write_off.write_off_value > Decimal('500.00')  # Threshold
            }
            
            items_data = [{
                'stock_item_id': write_off.stock_item.id,
                'quantity_difference': -write_off.quantity,
                'unit_cost': write_off.unit_cost,
                'reason': write_off.reason
            }]
            
            adjustment_result = self.create_adjustment(adjustment_data, items_data)
            
            if adjustment_result.is_success:
                write_off.adjustment = adjustment_result.data
                write_off.save()
                
                self.log_operation('create_write_off', {
                    'write_off_id': write_off.id,
                    'stock_item': str(write_off.stock_item),
                    'quantity': float(write_off.quantity),
                    'value': float(write_off.write_off_value)
                })
                
                return ServiceResult.success(
                    data=write_off,
                    message=f"Write-off created successfully"
                )
            else:
                return adjustment_result
                
        except Exception as e:
            return ServiceResult.error(f"Failed to create write-off: {str(e)}")
    
    def get_adjustment_summary(self, start_date: Optional[timezone.datetime] = None,
                              end_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Get adjustment summary for a period"""
        try:
            queryset = StockAdjustment.objects.for_tenant(self.tenant)
            
            if start_date and end_date:
                queryset = queryset.filter(created_at__range=[start_date, end_date])
            
            summary = queryset.aggregate(
                total_adjustments=Count('id'),
                total_quantity=Sum('total_quantity'),
                total_value=Sum('total_value'),
                pending_approval=Count('id', filter=Q(status='PENDING_APPROVAL')),
                applied=Count('id', filter=Q(status='APPLIED')),
                rejected=Count('id', filter=Q(status='REJECTED'))
            )
            
            # Get adjustment type breakdown
            type_breakdown = queryset.values('adjustment_type').annotate(
                count=Count('id'),
                total_value=Sum('total_value')
            ).order_by('-total_value')
            
            return ServiceResult.success(data={
                'summary': summary,
                'type_breakdown': list(type_breakdown)
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get adjustment summary: {str(e)}")