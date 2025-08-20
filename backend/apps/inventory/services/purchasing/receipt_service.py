from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockReceipt, StockReceiptItem, PurchaseOrder, 
    StockItem, StockMovement, StockMovementItem
)

class ReceiptService(BaseService):
    """
    Service for handling stock receipts and purchase order fulfillment
    """
    
    @transaction.atomic
    def create_ List[Dict[str, Any]]) -> ServiceResult:
        """
        Create a new stock receipt
        """
        try:
            self.validate_tenant()
            
            # Validate receipt data
            validation_result = self._validate_receipt_data(receipt_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create receipt
            receipt = StockReceipt.objects.create(
                tenant=self.tenant,
                received_by=self.user,
                **receipt_data
            )
            
            # Process receipt items
            total_quantity = Decimal('0')
            total_cost = Decimal('0')
            receipt_items = []
            
            for item_data in items_data:
                receipt_item = StockReceiptItem.objects.create(
                    receipt=receipt,
                    **item_data
                )
                
                # Calculate totals
                receipt_item.calculate_totals()
                receipt_items.append(receipt_item)
                total_quantity += receipt_item.quantity_received
                total_cost += receipt_item.total_cost
            
            # Update receipt totals
            receipt.total_quantity = total_quantity
            receipt.total_cost = total_cost
            receipt.save()
            
            # Update stock levels
            stock_update_result = self._update_stock_from_receipt(receipt)
            if not stock_update_result.is_success:
                raise Exception(f"Failed to update stock: {stock_update_result.message}")
            
            # Update purchase order if linked
            if receipt.purchase_order:
                self._update_purchase_order_status(receipt.purchase_order)
            
            # Generate quality control tasks if required
            self._generate_qc_tasks(receipt)
            
            self.log_operation('create_receipt', {
                'receipt_id': receipt.id,
                'receipt_number': receipt.receipt_number,
                'total_quantity': float(total_quantity),
                'total_cost': float(total_cost)
            })
            
            return ServiceResult.success(
                data=receipt,
                message=f"Stock Receipt {receipt.receipt_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create stock receipt: {str(e)}",
                errors={'receipt': [str(e)]}
            )
    
    def _validate_receipt_data(str, Any]]) -> ServiceResult:
        """Validate receipt data"""
        errors = {}
        
        # Validate purchase order if provided
        if receipt_data.get('purchase_order_id'):
            try:
                po = PurchaseOrder.objects.get(
                    id=receipt_data['purchase_order_id'],
                    tenant=self.tenant,
                    status__in=['APPROVED', 'PARTIALLY_RECEIVED']
                )
            except PurchaseOrder.DoesNotExist:
                errors['purchase_order'] = ['Invalid or non-approved purchase order']
        
        # Validate receipt date
        if receipt_data.get('receipt_date'):
            if receipt_data['receipt_date'] > timezone.now().date():
                errors['receipt_date'] = ['Receipt date cannot be in the future']
        
        # Validate items
        ifitems'] = ['At least one item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate quantities
            if not item_data.get('quantity_received') or item_data.get('quantity_received') <= 0:
                item_errors.append('Received quantity must be greater than zero')
            
            if item_data.get('quantity_rejected', 0) < 0:
                item_errors.append('Rejected quantity cannot be negative')
            
            # Validate unit cost
            if not item_data.get('unit_cost') or item_data.get('unit_cost') <= 0:
                item_errors.append('Unit cost must be greater than zero')
            
            # Validate PO item if receipt is linked to PO
            if receipt_data.get('purchase_order_id') and item_data.get('po_item_id'):
                try:
                    po_item = PurchaseOrderItem.objects.get(
                        id=item_data['po_item_id'],
                        purchase_order_id=receipt_data['purchase_order_id']
                    )
                    
                    # Check if receiving quantity exceeds outstanding quantity
                    outstanding_qty = po_item.quantity_ordered - po_item.quantity_received
                    if item_data['quantity_received'] > outstanding_qty:
                        item_errors.append(f'Receiving quantity exceeds outstanding quantity: {outstanding_qty}')
                        
                except PurchaseOrderItem.DoesNotExist:
                    item_errors.append('Invalid purchase order item')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _update_stock_from_receipt(self, receipt: StockReceipt) -> ServiceResult:
        """Update stock levels from receipt"""
        try:
            from ...services.stock.movement_service import StockMovementService
            
            movement_service = StockMovementService(tenant=self.tenant, user=self.user)
            
            # Create stock movement for receipt
            movement_data = {
                'movement_type': 'RECEIPT',
                'warehouse_id': receipt.warehouse.id,
                'reference_number': receipt.receipt_number,
                'notes': f'Stock receipt from {receipt.supplier.name if receipt.supplier else "Unknown"}'
            }
            
            # Prepare movement items
            movement_items = []
            for receipt_item in receipt.items.all():
                # Get or create stock item
                stock_item, created = StockItem.objects.get_or_create(
                    tenant=self.tenant,
                    product=receipt_item.product,
                    warehouse=receipt.warehouse,
                    defaults={
                        'unit_cost': receipt_item.unit_cost,
                        'reorder_level': receipt_item.product.default_reorder_level or 0,
                        'maximum_stock_level': receipt_item.product.default_maximum_level or 0
                    }
                )
                
                movement_items.append({
                    'stock_item_id': stock_item.id,
                    'quantity': receipt_item.quantity_received,
                    'unit_cost': receipt_item.unit_cost,
                    'notes': f'Receipt item - Batch: {receipt_item.batch_number or "N/A"}'
                })
            
            # Create stock movement
            return movement_service.create_movement(movement_data, movement_items)
            
        except Exception as e:
            return ServiceResult.error(f"Failed to update stock from receipt: {str(e)}")
    
    def _update_purchase_order_status(self, purchase_order: PurchaseOrder):
        """Update purchase order status based on receipts"""
        # Calculate total received quantities
        total_ordered = sum(item.quantity_ordered for item in purchase_order.items.all())
        total_received = sum(item.quantity_received for item in purchase_order.items.all())
        
        if total_received == 0:
            purchase_order.status = 'APPROVED'
        elif total_received < total_ordered:
            purchase_order.status = 'PARTIALLY_RECEIVED'
        else:
            purchase_order.status = 'COMPLETED'
            purchase_order.completed_date = timezone.now()
        
        purchase_order.save()
    
    def _generate_qc_tasks(self, receipt: StockReceipt):
        """Generate quality control tasks if required"""
        # Check if any received products require QC
        qc_required_items = receipt.items.filter(
            product__requires_quality_control=True
        )
        
        if qc_required_items.exists():
            from ...services.alerts.alert_service import AlertService
            
            alert_service = AlertService(tenant=self.tenant, user=self.user)
            alert_service.create_qc_required_alert(receipt)
    
    @transaction.atomic
    def process_quality_control(self, receipt_id: int, 
                               qc_results: List[Dict[str, Any]]) -> ServiceResult:
        """Process quality control results"""
        try:
            receipt = StockReceipt.objects.get(id=receipt_id, tenant=self.tenant)
            
            if receipt.qc_status == 'COMPLETED':
                return ServiceResult.error("Quality control already completed")
            
            passed_items = []
            failed_items = []
            
            for qc_result in qc_results:
                receipt_item = StockReceiptItem.objects.get(
                    id=qc_result['receipt_item_id'],
                    receipt=receipt
                )
                
                # Update QC status
                receipt_item.qc_status = qc_result['status']  # PASSED, FAILED, CONDITIONAL
                receipt_item.qc_notes = qc_result.get('notes', '')
                receipt_item.qc_performed_by = self.user
                receipt_item.qc_performed_date = timezone.now()
                
                if qc_result['status'] == 'FAILED':
                    # Handle failed QC
                    receipt_item.quantity_rejected = qc_result.get('quantity_rejected', 0)
                    failed_items.append(receipt_item)
                else:
                    passed_items.append(receipt_item)
                
                receipt_item.save()
            
            # Update overall receipt QC status
            receipt.qc_status = 'COMPLETED'
            receipt.qc_completed_date = timezone.now()
            receipt.save()
            
            # Create adjustments for rejected items
            if failed_items:
                self._process_rejected_items(failed_items)
            
            self.log_operation('process_quality_control', {
                'receipt_id': receipt.id,
                'passed_items': len(passed_items),
                'failed_items': len(failed_items)
            })
            
            return ServiceResult.success(
                data={
                    'receipt': receipt,
                    'passed_items': len(passed_items),
                    'failed_items': len(failed_items)
                },
                message="Quality control completed successfully"
            )
            
        except StockReceipt.DoesNotExist:
            return ServiceResult.error("Receipt not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to process quality control: {str(e)}")
    
    def _process_rejected_items(self, failed_items: List[StockReceiptItem]):
        """Process items that failed quality control"""
        from ...services.stock.movement_service import StockMovementService
        from ...services.adjustments.adjustment_service import AdjustmentService
        
        movement_service = StockMovementService(tenant=self.tenant, user=self.user)
        adjustment_service = AdjustmentService(tenant=self.tenant, user=self.user)
        
        for item in failed_items:
            if item.quantity_rejected > 0:
                # Create negative adjustment for rejected quantity
                adjustment_data = {
                    'warehouse_id': item.receipt.warehouse.id,
                    'adjustment_type': 'QUALITY_REJECTION',
                    'reason': 'Quality control rejection',
                    'notes': f'QC rejection for receipt {item.receipt.receipt_number}: {item.qc_notes}'
                }
                
                items_data = [{
                    'product_id': item.product.id,
                    'quantity': item.quantity_rejected,
                    'unit_cost': item.unit_cost,
                    'reason': 'Quality control rejection'
                }]
                
                adjustment_service.create_adjustment(adjustment_data, items_data)
    
    def get_receipt_summary(self, start_date: Optional[timezone.datetime] = None,
                           end_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Get receipt summary for a period"""
        try:
            queryset = StockReceipt.objects.for_tenant(self.tenant)
            
            if start_date and end_date:
                queryset = queryset.filter(receipt_date__range=[start_date.date(), end_date.date()])
            
            summary = queryset.aggregate(
                total_receipts=Count('id'),
                total_quantity=Sum('total_quantity'),
                total_cost=Sum('total_cost'),
                avg_receipt_value=Avg('total_cost'),
                pending_qc=Count('id', filter=Q(qc_status='PENDING')),
                completed_qc=Count('id', filter=Q(qc_status='COMPLETED'))
            )
            
            # Get supplier-wise breakdown
            supplier_breakdown = queryset.values(
                'supplier__name'
            ).annotate(
                receipt_count=Count('id'),
                total_value=Sum('total_cost')
            ).order_by('-total_value')
            
            return ServiceResult.success(data={
                'summary': summary,
                'supplier_breakdown': list(supplier_breakdown)
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get receipt summary: {str(e)}")
    
    def create_return_to_supplier(self, receipt_id: int, 
                                 return_items: List[Dict[str, Any]], 
                                 reason: str) -> ServiceResult:
        """Create return to supplier for defective items"""
        try:
            receipt = StockReceipt.objects.get(id=receipt_id, tenant=self.tenant)
            
            # Create return receipt (negative receipt)
            return_data = {
                'receipt_type': 'RETURN',
                'supplier_id': receipt.supplier.id if receipt.supplier else None,
                'warehouse_id': receipt.warehouse.id,
                'receipt_date': timezone.now().date(),
                'reference_number': f"RTN-{receipt.receipt_number}",
                'notes': f"Return to supplier - Reason: {reason}",
                'original_receipt_id': receipt.id
            }
            
            # Prepare return items
            return_items_data = []
            for return_item in return_items:
                return_items_data.append({
                    'product_id': return_item['product_id'],
                    'quantity_received': -return_item['quantity'],  # Negative for return
                    'unit_cost': return_item['unit_cost'],
                    'notes': f"Return - {reason}"
                })
            
            # Create return receipt
            return_result = self.create_receipt(return_data, return_items_data)
            
            if return_result.is_success:
                # Update original receipt
                receipt.has_returns = True
                receipt.save()
                
                return ServiceResult.success(
                    data=return_result.data,
                    message=f"Return created successfully for receipt {receipt.receipt_number}"
                )
            else:
                return return_result
                
        except StockReceipt.DoesNotExist:
            return ServiceResult.error("Original receipt not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to create return: {str(e)}")