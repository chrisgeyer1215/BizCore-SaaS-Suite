# apps/inventory/api/v1/views/purchasing.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.purchasing import (
    PurchaseOrderSerializer, PurchaseOrderDetailSerializer, PurchaseOrderCreateSerializer,
    PurchaseOrderItemSerializer, StockReceiptSerializer, StockReceiptDetailSerializer,
    StockReceiptItemSerializer, PurchaseOrderApprovalSerializer
)
from apps.inventory.models.purchasing.orders import PurchaseOrder, PurchaseOrderItem
from apps.inventory.models.purchasing.receipts import StockReceipt, StockReceiptItem
from apps.inventory.services.purchasing.order_service import PurchaseOrderService
from apps.inventory.services.purchasing.receipt_service import ReceiptService
from apps.inventory.services.purchasing.approval_service import ApprovalService
from apps.inventory.services.stock.movement_service import StockMovementService
from apps.inventory.utils.exceptions import InventoryError, InvalidOperationError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import PO_STATUSES, RECEIPT_STATUSES


class PurchaseOrderViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing purchase orders with full lifecycle support.
    
    Supports:
    - PO creation, modification, and approval workflows
    - Multi-item orders with detailed tracking
    - Supplier management integration
    - Receipt tracking and partial deliveries
    - Financial integration and budgeting
    """
    serializer_class = PurchaseOrderSerializer
    detail_serializer_class = PurchaseOrderDetailSerializer
    create_serializer_class = PurchaseOrderCreateSerializer
    queryset = PurchaseOrder.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific purchase orders with optimizations."""
        return PurchaseOrder.objects.select_related(
            'supplier', 'warehouse', 'created_by', 'approved_by'
        ).prefetch_related(
            'items__product', 'receipts'
        ).with_totals().with_receipt_status()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return self.create_serializer_class
        elif self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action == 'approve' or self.action == 'reject':
            return PurchaseOrderApprovalSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create purchase order with business logic."""
        try:
            po_service = PurchaseOrderService(self.request.user.tenant)
            
            po_data = serializer.validated_data
            items_data = po_data.pop('items', [])
            
            # Create PO through service
            purchase_order = po_service.create_purchase_order(
                po_data=po_data,
                items_data=items_data,
                user=self.request.user
            )
            
            return purchase_order
        except Exception as e:
            raise InventoryError(f"Failed to create purchase order: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get purchase orders dashboard summary."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_orders = queryset.count()
            pending_orders = queryset.filter(status=PO_STATUSES.PENDING).count()
            approved_orders = queryset.filter(status=PO_STATUSES.APPROVED).count()
            completed_orders = queryset.filter(status=PO_STATUSES.COMPLETED).count()
            
            # Financial metrics
            total_value = queryset.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0')
            
            pending_value = queryset.filter(
                status=PO_STATUSES.PENDING
            ).aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0')
            
            # Recent activity
            recent_orders = queryset.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Top suppliers by order count
            top_suppliers = queryset.values(
                'supplier__name', 'supplier__id'
            ).annotate(
                order_count=Count('id'),
                total_value=Sum('total_amount')
            ).order_by('-order_count')[:5]
            
            return Response({
                'success': True,
                'data': {
                    'total_orders': total_orders,
                    'pending_orders': pending_orders,
                    'approved_orders': approved_orders,
                    'completed_orders': completed_orders,
                    'total_value': total_value,
                    'pending_value': pending_value,
                    'recent_orders': recent_orders,
                    'top_suppliers': list(top_suppliers)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get purchase orders pending approval."""
        try:
            pending_orders = self.get_queryset().filter(
                status=PO_STATUSES.PENDING,
                requires_approval=True
            ).order_by('created_at')
            
            # Filter by approval amount if user has limited approval authority
            user_approval_limit = getattr(request.user, 'approval_limit', None)
            if user_approval_limit:
                pending_orders = pending_orders.filter(
                    total_amount__lte=user_approval_limit
                )
            
            page = self.paginate_queryset(pending_orders)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(pending_orders, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': pending_orders.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve pending approvals')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve purchase order."""
        try:
            purchase_order = self.get_object()
            
            if purchase_order.status != PO_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending orders can be approved']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            approval_service = ApprovalService(request.user.tenant)
            notes = request.data.get('notes', '')
            
            # Check approval authority
            can_approve, reason = approval_service.can_user_approve_po(
                user=request.user,
                purchase_order=purchase_order
            )
            
            if not can_approve:
                return Response({
                    'success': False,
                    'errors': [reason]
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Approve the order
            approval_service.approve_purchase_order(
                purchase_order=purchase_order,
                approver=request.user,
                notes=notes
            )
            
            return Response({
                'success': True,
                'message': 'Purchase order approved successfully',
                'data': {
                    'order_id': purchase_order.id,
                    'status': purchase_order.status,
                    'approved_at': purchase_order.approved_at,
                    'approved_by': purchase_order.approved_by.get_full_name()
                }
            })
        except InvalidOperationError as e:
            return Response({
                'success': False,
                'errors': [str(e)]
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.handle_error(e, 'Failed to approve purchase order')
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject purchase order."""
        try:
            purchase_order = self.get_object()
            
            if purchase_order.status != PO_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending orders can be rejected']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            approval_service = ApprovalService(request.user.tenant)
            notes = request.data.get('notes', '')
            reason = request.data.get('reason', 'No reason provided')
            
            # Reject the order
            approval_service.reject_purchase_order(
                purchase_order=purchase_order,
                rejector=request.user,
                reason=reason,
                notes=notes
            )
            
            return Response({
                'success': True,
                'message': 'Purchase order rejected',
                'data': {
                    'order_id': purchase_order.id,
                    'status': purchase_order.status,
                    'rejected_at': timezone.now(),
                    'rejected_by': request.user.get_full_name(),
                    'reason': reason
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to reject purchase order')
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel purchase order."""
        try:
            purchase_order = self.get_object()
            
            if purchase_order.status in [PO_STATUSES.COMPLETED, PO_STATUSES.CANCELLED]:
                return Response({
                    'success': False,
                    'errors': ['Cannot cancel completed or already cancelled orders']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            po_service = PurchaseOrderService(request.user.tenant)
            reason = request.data.get('reason', 'Cancelled by user')
            
            with transaction.atomic():
                po_service.cancel_purchase_order(
                    purchase_order=purchase_order,
                    reason=reason,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Purchase order cancelled successfully',
                'data': {
                    'order_id': purchase_order.id,
                    'status': purchase_order.status
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to cancel purchase order')
    
    @action(detail=True, methods=['get'])
    def receipt_history(self, request, pk=None):
        """Get receipt history for purchase order."""
        try:
            purchase_order = self.get_object()
            
            receipts = purchase_order.receipts.select_related(
                'warehouse', 'received_by'
            ).prefetch_related(
                'items__product'
            ).order_by('-received_date')
            
            receipt_data = []
            for receipt in receipts:
                receipt_data.append({
                    'receipt_id': receipt.id,
                    'receipt_number': receipt.receipt_number,
                    'received_date': receipt.received_date,
                    'warehouse': receipt.warehouse.name,
                    'received_by': receipt.received_by.get_full_name() if receipt.received_by else None,
                    'status': receipt.status,
                    'total_items': receipt.items.count(),
                    'total_quantity': sum(item.quantity_received for item in receipt.items.all()),
                    'notes': receipt.notes
                })
            
            return Response({
                'success': True,
                'data': {
                    'purchase_order_id': purchase_order.id,
                    'receipts': receipt_data,
                    'total_receipts': len(receipt_data)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve receipt history')
    
    @action(detail=True, methods=['get'])
    def delivery_performance(self, request, pk=None):
        """Get delivery performance metrics for purchase order."""
        try:
            purchase_order = self.get_object()
            
            # Calculate delivery performance
            total_items = purchase_order.items.count()
            total_ordered_qty = purchase_order.items.aggregate(
                total=Sum('quantity')
            )['total'] or 0
            
            total_received_qty = StockReceiptItem.objects.filter(
                receipt__purchase_order=purchase_order
            ).aggregate(
                total=Sum('quantity_received')
            )['total'] or 0
            
            # Expected vs actual delivery dates
            expected_delivery = purchase_order.expected_delivery_date
            actual_deliveries = purchase_order.receipts.aggregate(
                first_delivery=Min('received_date'),
                last_delivery=Max('received_date')
            )
            
            # Calculate completion percentage
            completion_percentage = (
                (total_received_qty / total_ordered_qty * 100)
                if total_ordered_qty > 0 else 0
            )
            
            # Delivery status
            if total_received_qty >= total_ordered_qty:
                delivery_status = 'COMPLETE'
            elif total_received_qty > 0:
                delivery_status = 'PARTIAL'
            else:
                delivery_status = 'PENDING'
            
            # Calculate delivery delay
            delivery_delay_days = None
            if expected_delivery and actual_deliveries['first_delivery']:
                delivery_delay_days = (
                    actual_deliveries['first_delivery'].date() - expected_delivery
                ).days
            
            performance_data = {
                'purchase_order_id': purchase_order.id,
                'total_items': total_items,
                'total_ordered_quantity': total_ordered_qty,
                'total_received_quantity': total_received_qty,
                'completion_percentage': round(completion_percentage, 2),
                'delivery_status': delivery_status,
                'expected_delivery_date': expected_delivery,
                'first_delivery_date': actual_deliveries['first_delivery'],
                'last_delivery_date': actual_deliveries['last_delivery'],
                'delivery_delay_days': delivery_delay_days,
                'on_time_delivery': delivery_delay_days <= 0 if delivery_delay_days is not None else None
            }
            
            return Response({
                'success': True,
                'data': performance_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to calculate delivery performance')
    
    @action(detail=False, methods=['get'])
    def supplier_performance(self, request):
        """Get supplier performance analytics."""
        try:
            supplier_id = request.query_params.get('supplier_id')
            days = int(request.query_params.get('days', 90))
            
            start_date = timezone.now() - timedelta(days=days)
            
            queryset = self.get_queryset().filter(created_at__gte=start_date)
            
            if supplier_id:
                queryset = queryset.filter(supplier_id=supplier_id)
            
            # Calculate supplier metrics
            performance_data = queryset.values('supplier__name', 'supplier__id').annotate(
                total_orders=Count('id'),
                total_value=Sum('total_amount'),
                avg_order_value=Avg('total_amount'),
                completed_orders=Count('id', filter=Q(status=PO_STATUSES.COMPLETED)),
                cancelled_orders=Count('id', filter=Q(status=PO_STATUSES.CANCELLED)),
                avg_lead_time=Avg(
                    F('receipts__received_date') - F('order_date'),
                    filter=Q(receipts__isnull=False)
                )
            ).order_by('-total_value')
            
            # Calculate completion rates
            for['completion_rate'] = (
                    (supplier['completed_orders'] / supplier['total_orders'] * 100)
                    if supplier['total_orders'] > 0 else 0
                )
                supplier['cancellation_rate'] = (
                    (supplier['cancelled_orders'] / supplier['total_orders'] * 100)
                    if supplier['total_orders'] > 0 else 0
                )
                
                # Convert timedelta to days for avg_lead_time
                if supplier['avg_lead_time']:
                    supplier['avg_lead_time_days'] = supplier['avg_lead_time'].days
                else:
                    supplier['avg_lead_time_days'] = None
            
            return Response({
                'success': True,
                'data': list(performance_data),
                'period_days': days
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve supplier performance')


class StockReceiptViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock receipts and goods receiving.
    
    Supports:
    - Receipt creation from purchase orders
    - Quality control and inspection
    - Partial receipts and back orders
    - Batch and serial number tracking
    - Supplier returns and damaged goods
    """
    serializer_class = StockReceiptSerializer
    detail_serializer_class = StockReceiptDetailSerializer
    queryset = StockReceipt.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific receipts with optimizations."""
        return StockReceipt.objects.select_related(
            'purchase_order', 'warehouse', 'received_by'
        ).prefetch_related(
            'items__product', 'purchase_order__supplier'
        ).with_totals()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return self.detail_serializer_class
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create stock receipt with business logic."""
        try:
            receipt_service = ReceiptService(self.request.user.tenant)
            
            receipt_data = serializer.validated_data
            items_data = receipt_data.pop('items', [])
            
            # Create receipt through service
            receipt = receipt_service.create_stock_receipt(
                receipt_data=receipt_data,
                items_data=items_data,
                user=self.request.user
            )
            
            return receipt
        except Exception as e:
            raise InventoryError(f"Failed to create stock receipt: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def pending_receipts(self, request):
        """Get receipts pending processing."""
        try:
            pending_receipts = self.get_queryset().filter(
                status__in=[RECEIPT_STATUSES.PENDING, RECEIPT_STATUSES.IN_PROGRESS]
            ).order_by('received_date')
            
            page = self.paginate_queryset(pending_receipts)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(pending_receipts, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': pending_receipts.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve pending receipts')
    
    @action(detail=True, methods=['post'])
    def process_receipt(self, request, pk=None):
        """Process stock receipt and update inventory."""
        try:
            receipt = self.get_object()
            
            if receipt.status == RECEIPT_STATUSES.COMPLETED:
                return Response({
                    'success': False,
                    'errors': ['Receipt is already processed']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            receipt_service = ReceiptService(request.user.tenant)
            
            # Get processing options
            quality_check_passed = request.data.get('quality_check_passed', True)
            notes = request.data.get('notes', '')
            damaged_items = request.data.get('damaged_items', [])
            
            with transaction.atomic():
                result = receipt_service.process_receipt(
                    receipt=receipt,
                    quality_check_passed=quality_check_passed,
                    notes=notes,
                    damaged_items=damaged_items,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Receipt processed successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to process receipt')
    
    @action(detail=True, methods=['post'])
    def create_return(self, request, pk=None):
        """Create return for damaged or incorrect items."""
        try:
            receipt = self.get_object()
            
            return_items = request.data.get('return_items', [])
            reason = request.data.get('reason', 'Quality issue')
            notes = request.data.get('notes', '')
            
            if not return_items:
                return Response({
                    'success': False,
                    'errors': ['No return items specified']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            receipt_service = ReceiptService(request.user.tenant)
            
            with transaction.atomic():
                return_receipt = receipt_service.create_supplier_return(
                    original_receipt=receipt,
                    return_items=return_items,
                    reason=reason,
                    notes=notes,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Return created successfully',
                'data': {
                    'return_receipt_id': return_receipt.id,
                    'return_receipt_number': return_receipt.receipt_number,
                    'return_items_count': len(return_items)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to create return')
    
    @action(detail=False, methods=['get'])
    def quality_control_summary(self, request):
        """Get quality control summary and metrics."""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            receipts = self.get_queryset().filter(received_date__gte=start_date)
            
            total_receipts = receipts.count()
            receipts_with_issues = receipts.filter(
                quality_check_passed=False
            ).count()
            
            # Calculate quality metrics by supplier
            supplier_quality = receipts.values(
                'purchase_order__supplier__name',
                'purchase_order__supplier__id'
            ).annotate(
                total_receipts=Count('id'),
                failed_receipts=Count('id', filter=Q(quality_check_passed=False)),
                total_items=Sum('items__quantity_received'),
                damaged_items=Sum('items__quantity_damaged')
            ).order_by('-total_receipts')
            
            for supplier in supplier_quality:
                supplier['quality_rate'] = (
                    ((supplier['total_receipts'] - supplier['failed_receipts']) /
                     supplier['total_receipts'] * 100)
                    if supplier['total_receipts'] > 0 else 100
                )
                supplier['damage_rate'] = (
                    (supplier['damaged_items'] / supplier['total_items'] * 100)
                    if supplier['total_items'] > 0 else 0
                )
            
            return Response({
                'success': True,
                'data': {
                    'total_receipts': total_receipts,
                    'receipts_with_issues': receipts_with_issues,
                    'overall_quality_rate': (
                        ((total_receipts - receipts_with_issues) / total_receipts * 100)
                        if total_receipts > 0 else 100
                    ),
                    'supplier_quality_metrics': list(supplier_quality),
                    'period_days': days
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve quality control summary')