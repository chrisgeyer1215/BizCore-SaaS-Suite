from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderApproval,
    Supplier, Product, Warehouse
)

class PurchaseOrderService(BaseService):
    """
    Service for handling purchase order operations
    """
    
    APPROVAL_LEVELS = {
        'AUTO_APPROVE': 0,
        'SUPERVISOR': 1000,
        'MANAGER': 5000,
        'DIRECTOR': 25000,
        'CEO': 100000
    }
    
    @transaction.atomic
    def create_str, Any]]) -> ServiceResult:
        """
        Create a new purchase order with items
        """
        try:
            self.validate_tenant()
            
            # Validate order data
            validation_result = self._validate_order_data(order_data, items_data)
            if not validation_result.is_success:
                return validation_result
            
            # Create purchase order
            purchase_order = PurchaseOrder.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **order_data
            )
            
            # Process order items
            total_amount = Decimal('0')
            order_items = []
            
            for item_data in items_data:
                product = Product.objects.get(
                    id=item_data['product_id'], 
                    tenant=self.tenant
                )
                
                order_item = PurchaseOrderItem.objects.create(
                    purchase_order=purchase_order,
                    product=product,
                    **item_data
                )
                
                # Calculate item totals
                order_item.calculate_totals()
                order_items.append(order_item)
                total_amount += order_item.total_amount
            
            # Update order totals
            purchase_order.subtotal = total_amount
            purchase_order.calculate_totals()
            purchase_order.save()
            
            # Handle approval workflow
            approval_result = self._initiate_approval_workflow(purchase_order)
            if not approval_result.is_success:
                return approval_result
            
            self.log_operation('create_purchase_order', {
                'po_id': purchase_order.id,
                'po_number': purchase_order.po_number,
                'supplier': purchase_order.supplier.name,
                'total_amount': float(purchase_order.total_amount)
            })
            
            return ServiceResult.success(
                data=purchase_order,
                message=f"Purchase Order {purchase_order.po_number} created successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(
                message=f"Failed to create purchase order: {str(e)}",
                errors={'purchase_order': [str(e)]}
            )
    
    def _validate_order_data(self, Any]]) -> ServiceResult:
        """Validate purchase order data"""
        errors = {}
        
        # Validate supplier
        try:
            supplier = Supplier.objects.get(
                id=order_data.get('supplier_id'),
                tenant=self.tenant,
                is_active=True
            )
            
            # Check supplier status
            if supplier.status not in ['ACTIVE', 'APPROVED']:
                errors['supplier'] = ['Supplier is not active or approved']
                
        except Supplier.DoesNotExist:
            errors['supplier'] = ['Invalid or inactive supplier']
        
        # Validate warehouse
        try:
            Warehouse.objects.get(
                id=order_data.get('warehouse_id'),
                tenant=self.tenant,
                is_active=True
            )
        except Warehouse.DoesNotExist:
            errors['warehouse'] = ['Invalid warehouse']
        
        # Validate order date
        if order_data.get('order_date') and order_data['order_date'] > timezone.now().date():
            errors['order_date'] = ['Order date cannot be in the future']
        
        # Validate items
        if least one item is required']
        
        for i, item_data in enumerate(items_data):
            item_errors = []
            
            # Validate product
            try:
                product = Product.objects.get(
                    id=item_data.get('product_id'),
                    tenant=self.tenant,
                    is_active=True,
                    is_purchasable=True
                )
            except Product.DoesNotExist:
                item_errors.append('Invalid or non-purchasable product')
            
            # Validate quantities
            if not item_data.get('quantity_ordered') or item_data.get('quantity_ordered') <= 0:
                item_errors.append('Quantity must be greater than zero')
            
            # Validate unit cost
            if not item_data.get('unit_cost') or item_data.get('unit_cost') <= 0:
                item_errors.append('Unit cost must be greater than zero')
            
            if item_errors:
                errors[f'item_{i}'] = item_errors
        
        if errors:
            return ServiceResult.error("Validation failed", errors=errors)
        
        return ServiceResult.success()
    
    def _initiate_approval_workflow(self, purchase_order: PurchaseOrder) -> ServiceResult:
        """Initiate approval workflow based on order value"""
        try:
            total_amount = purchase_order.total_amount
            
            # Determine required approval level
            required_level = None
            for level, threshold in sorted(self.APPROVAL_LEVELS.items(), 
                                         key=lambda x: x[1], reverse=True):
                if total_amount >= threshold:
                    required_level = level
                    break
            
            if required_level == 'AUTO_APPROVE':
                # Auto-approve small orders
                purchase_order.status = 'APPROVED'
                purchase_order.approved_date = timezone.now()
                purchase_order.approved_by = self.user
                purchase_order.save()
            else:
                # Create approval record
                approval = PurchaseOrderApproval.objects.create(
                    tenant=self.tenant,
                    purchase_order=purchase_order,
                    required_approval_level=required_level,
                    requested_by=self.user,
                    requested_date=timezone.now()
                )
                
                purchase_order.status = 'PENDING_APPROVAL'
                purchase_order.save()
                
                # Send approval notification
                self._send_approval_notification(approval)
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to initiate approval workflow: {str(e)}")
    
    def _send_approval_notification(self, approval: PurchaseOrderApproval):
        """Send notification to approvers"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_po_approval_notification(approval)
    
    @transaction.atomic
    def approve_purchase_order(self, po_id: int, approval_notes: str = "") -> ServiceResult:
        """Approve a purchase order"""
        try:
            purchase_order = PurchaseOrder.objects.get(id=po_id, tenant=self.tenant)
            
            if purchase_order.status != 'PENDING_APPROVAL':
                return ServiceResult.error("Purchase order is not pending approval")
            
            # Check if user has authority to approve
            approval = purchase_order.approval
            if not self._can_approve(approval.required_approval_level):
                return ServiceResult.error("Insufficient authority to approve this purchase order")
            
            # Update approval record
            approval.approved_by = self.user
            approval.approved_date = timezone.now()
            approval.approval_notes = approval_notes
            approval.status = 'APPROVED'
            approval.save()
            
            # Update purchase order
            purchase_order.status = 'APPROVED'
            purchase_order.approved_date = timezone.now()
            purchase_order.approved_by = self.user
            purchase_order.save()
            
            # Send confirmation to requester
            self._send_approval_confirmation(purchase_order)
            
            self.log_operation('approve_purchase_order', {
                'po_id': purchase_order.id,
                'po_number': purchase_order.po_number,
                'approver': self.user.username
            })
            
            return ServiceResult.success(
                data=purchase_order,
                message=f"Purchase Order {purchase_order.po_number} approved successfully"
            )
            
        except PurchaseOrder.DoesNotExist:
            return ServiceResult.error("Purchase order not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to approve purchase order: {str(e)}")
    
    def _can_approve(self, required_level: str) -> bool:
        """Check if user can approve at required level"""
        # Implement based on your user role/permission system
        user_roles = self.user.groups.values_list('name', flat=True) if self.user else []
        
        approval_permissions = {
            'SUPERVISOR': ['supervisor', 'manager', 'director', 'ceo'],
            'MANAGER': ['manager', 'director', 'ceo'],
            'DIRECTOR': ['director', 'ceo'],
            'CEO': ['ceo']
        }
        
        allowed_roles = approval_permissions.get(required_level, [])
        return any(role in user_roles for role in allowed_roles)
    
    def _send_approval_confirmation(self, purchase_order: PurchaseOrder):
        """Send approval confirmation notification"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_po_approved_notification(purchase_order)
    
    @transaction.atomic
    def reject_purchase_order(self, po_id: int, rejection_reason: str) -> ServiceResult:
        """Reject a purchase order"""
        try:
            purchase_order = PurchaseOrder.objects.get(id=po_id, tenant=self.tenant)
            
            if purchase_order.status != 'PENDING_APPROVAL':
                return ServiceResult.error("Purchase order is not pending approval")
            
            # Update approval record
            approval = purchase_order.approval
            approval.approved_by = self.user
            approval.approved_date = timezone.now()
            approval.approval_notes = rejection_reason
            approval.status = 'REJECTED'
            approval.save()
            
            # Update purchase order
            purchase_order.status = 'REJECTED'
            purchase_order.rejection_reason = rejection_reason
            purchase_order.save()
            
            # Send rejection notification
            self._send_rejection_notification(purchase_order)
            
            self.log_operation('reject_purchase_order', {
                'po_id': purchase_order.id,
                'po_number': purchase_order.po_number,
                'rejector': self.user.username,
                'reason': rejection_reason
            })
            
            return ServiceResult.success(
                data=purchase_order,
                message=f"Purchase Order {purchase_order.po_number} rejected"
            )
            
        except PurchaseOrder.DoesNotExist:
            return ServiceResult.error("Purchase order not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to reject purchase order: {str(e)}")
    
    def _send_rejection_notification(self, purchase_order: PurchaseOrder):
        """Send rejection notification"""
        from ...services.alerts.notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_po_rejected_notification(purchase_order)
    
    def generate_reorder_suggestions(self, warehouse_id: Optional[int] = None) -> ServiceResult:
        """Generate purchase order suggestions based on reorder points"""
        try:
            from ...models import StockItem, ProductSupplier
            
            # Get items that need reordering
            queryset = StockItem.objects.for_tenant(self.tenant).filter(
                quantity_on_hand__lte=models.F('reorder_level'),
                product__is_active=True,
                product__is_purchasable=True,
                reorder_level__gt=0
            )
            
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            suggestions = []
            
            for stock_item in queryset:
                # Get primary supplier
                primary_supplier = ProductSupplier.objects.filter(
                    product=stock_item.product,
                    tenant=self.tenant,
                    is_primary=True
                ).first()
                
                if primary_supplier:
                    suggested_quantity = max(
                        stock_item.reorder_quantity or 0,
                        stock_item.maximum_stock_level - stock_item.quantity_on_hand
                    )
                    
                    suggestions.append({
                        'product': stock_item.product,
                        'supplier': primary_supplier.supplier,
                        'current_stock': stock_item.quantity_on_hand,
                        'reorder_level': stock_item.reorder_level,
                        'suggested_quantity': suggested_quantity,
                        'unit_cost': primary_supplier.supplier_cost,
                        'estimated_cost': suggested_quantity * primary_supplier.supplier_cost,
                        'lead_time_days': primary_supplier.lead_time_days
                    })
            
            # Group by supplier
            supplier_suggestions = {}
            for suggestion in suggestions:
                supplier_id = suggestion['supplier'].id
                if supplier_id not in supplier_suggestions:
                    supplier_suggestions[supplier_id] = {
                        'supplier': suggestion['supplier'],
                        'items': [],
                        'total_estimated_cost': Decimal('0')
                    }
                
                supplier_suggestions[supplier_id]['items'].append(suggestion)
                supplier_suggestions[supplier_id]['total_estimated_cost'] += suggestion['estimated_cost']
            
            return ServiceResult.success(
                data=list(supplier_suggestions.values()),
                message=f"Generated {len(suggestions)} reorder suggestions"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to generate reorder suggestions: {str(e)}")
    
    @transaction.atomic
    def create_po_from_suggestions(self, suggestions_
        """Create purchase orders from reorder suggestions"""
        try:
            created_orders = []
            
            
                supplier_id = supplier_data['supplier_id']
                items = supplier_data['items']
                warehouse_id = supplier_data.get('warehouse_id')
                
                # Create order data
                order_data = {
                    'supplier_id': supplier_id,
                    'warehouse_id': warehouse_id,
                    'order_date': timezone.now().date(),
                    'notes': 'Auto-generated from reorder suggestions',
                    'priority': 'MEDIUM'
                }
                
                # Prepare items data
                items_data = []
                for item in items:
                    items_data.append({
                        'product_id': item['product_id'],
                        'quantity_ordered': item['quantity'],
                        'unit_cost': item['unit_cost'],
                        'notes': f"Reorder - Current stock: {item.get('current_stock', 0)}"
                    })
                
                # Create purchase order
                result = self.create_purchase_order(order_data, items_data)
                if result.is_success:
                    created_orders.append(result.data)
                else:
                    return result  # Return first error
            
            return ServiceResult.success(
                data=created_orders,
                message=f"Created {len(created_orders)} purchase orders from suggestions"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to create POs from suggestions: {str(e)}")
    
    def get_po_status_summary(self, start_date: Optional[timezone.datetime] = None,
                             end_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Get purchase order status summary"""
        try:
            queryset = PurchaseOrder.objects.for_tenant(self.tenant)
            
            if start_date and end_date:
                queryset = queryset.filter(created_at__range=[start_date, end_date])
            
            summary = queryset.values('status').annotate(
                count=Count('id'),
                total_value=Sum('total_amount')
            ).order_by('status')
            
            # Get additional metrics
            metrics = queryset.aggregate(
                total_orders=Count('id'),
                total_value=Sum('total_amount'),
                avg_order_value=Avg('total_amount'),
                pending_approval_count=Count('id', filter=Q(status='PENDING_APPROVAL')),
                approved_count=Count('id', filter=Q(status='APPROVED')),
                completed_count=Count('id', filter=Q(status='COMPLETED'))
            )
            
            return ServiceResult.success(data={
                'status_breakdown': list(summary),
                'metrics': metrics
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get PO status summary: {str(e)}")