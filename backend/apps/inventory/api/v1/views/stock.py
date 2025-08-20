# apps/inventory/api/v1/views/stock.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Avg, Count, Max
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.stock import (
    StockItemSerializer, StockItemDetailSerializer, StockMovementSerializer,
    BatchSerializer, StockValuationSerializer, StockAdjustmentSerializer,
    BulkStockUpdateSerializer
)
from apps.inventory.models.stock.items import StockItem
from apps.inventory.models.stock.movements import StockMovement
from apps.inventory.models.stock.batches import Batch
from apps.inventory.models.stock.valuation import StockValuationLayer
from apps.inventory.services.stock.movement_service import StockMovementService
from apps.inventory.services.stock.valuation_service import ValuationService
from apps.inventory.services.stock.reservation_service import ReservationService
from apps.inventory.services.reports.analytics_service import AnalyticsService
from apps.inventory.utils.exceptions import InventoryError, InsufficientStockError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import MOVEMENT_TYPES


class StockItemViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock items with comprehensive stock operations.
    
    Supports:
    - Real-time stock tracking
    - Multi-warehouse management
    - Batch and serial number tracking
    - Stock reservations
    - Bulk operations
    """
    serializer_class = StockItemSerializer
    detail_serializer_class = StockItemDetailSerializer
    queryset = StockItem.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific stock items with optimizations."""
        return StockItem.objects.select_related(
            'product', 'warehouse', 'location', 'batch'
        ).prefetch_related(
            'reservations', 'movements'
        ).with_valuation().with_aging()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action == 'bulk_update':
            return BulkStockUpdateSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get stock dashboard summary with key metrics."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_items = queryset.count()
            total_value = queryset.aggregate(
                total=Sum(F('quantity_on_hand') * F('unit_cost'))
            )['total'] or Decimal('0')
            
            low_stock_count = queryset.filter(
                quantity_on_hand__lte=F('product__reorder_level')
            ).count()
            
            out_of_stock_count = queryset.filter(
                quantity_on_hand=0
            ).count()
            
            overstock_count = queryset.filter(
                quantity_on_hand__gte=F('product__max_stock_level')
            ).count()
            
            # Recent movements
            recent_movements = StockMovement.objects.filter(
                tenant=request.user.tenant,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Top products by value
            top_products = queryset.annotate(
                total_value=F('quantity_on_hand') * F('unit_cost')
            ).order_by('-total_value')[:5]
            
            top_products_data = []
            for item in top_products:
                top_products_data.append({
                    'product_name': item.product.name,
                    'sku': item.product.sku,
                    'quantity': item.quantity_on_hand,
                    'unit_cost': item.unit_cost,
                    'total_value': item.total_value,
                    'warehouse': item.warehouse.name
                })
            
            return Response({
                'success': True,
                'data': {
                    'total_items': total_items,
                    'total_value': total_value,
                    'low_stock_count': low_stock_count,
                    'out_of_stock_count': out_of_stock_count,
                    'overstock_count': overstock_count,
                    'recent_movements': recent_movements,
                    'top_products': top_products_data
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['get'])
    def low_stock_alerts(self, request):
        """Get items with low stock levels."""
        try:
            queryset = self.get_queryset().filter(
                quantity_on_hand__lte=F('product__reorder_level'),
                product__reorder_level__gt=0
            ).select_related('product', 'warehouse')
            
            # Apply additional filters
            warehouse_id = request.query_params.get('warehouse_id')
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            category_id = request.query_params.get('category_id')
            if category_id:
                queryset = queryset.filter(product__category_id=category_id)
            
            # Paginate results
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': queryset.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve low stock alerts')
    
    @action(detail=False, methods=['get'])
    def valuation_report(self, request):
        """Get stock valuation report."""
        try:
            valuation_service = ValuationService(request.user.tenant)
            
            # Get valuation method from settings
            method = request.query_params.get('method', 'FIFO')
            warehouse_id = request.query_params.get('warehouse_id')
            category_id = request.query_params.get('category_id')
            
            report_data = valuation_service.generate_valuation_report(
                method=method,
                warehouse_id=warehouse_id,
                category_id=category_id
            )
            
            return Response({
                'success': True,
                'data': report_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate valuation report')
    
    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """Adjust stock quantity for a specific item."""
        try:
            stock_item = self.get_object()
            
            adjustment_qty = Decimal(str(request.data.get('quantity', 0)))
            reason = request.data.get('reason', 'Manual Adjustment')
            reference = request.data.get('reference', '')
            unit_cost = request.data.get('unit_cost')
            
            if adjustment_qty == 0:
                return Response({
                    'success': False,
                    'errors': ['Adjustment quantity cannot be zero']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            movement_service = StockMovementService(request.user.tenant)
            
            with transaction.atomic():
                # Create stock movement
                movement = movement_service.create_movement(
                    product=stock_item.product,
                    warehouse=stock_item.warehouse,
                    location=stock_item.location,
                    movement_type=MOVEMENT_TYPES.ADJUSTMENT,
                    quantity=adjustment_qty,
                    unit_cost=unit_cost or stock_item.unit_cost,
                    reference=reference,
                    reason=reason,
                    user=request.user
                )
                
                # Update stock item
                stock_item.quantity_on_hand += adjustment_qty
                if stock_item.quantity_on_hand < 0:
                    stock_item.quantity_on_hand = 0
                
                stock_item.save()
            
            return Response({
                'success': True,
                'data': {
                    'movement_id': movement.id,
                    'new_quantity': stock_item.quantity_on_hand,
                    'adjustment_quantity': adjustment_qty
                },
                'message': 'Stock adjusted successfully'
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to adjust stock')
    
    @action(detail=True, methods=['post'])
    def reserve_stock(self, request, pk=None):
        """Reserve stock for specific purpose."""
        try:
            stock_item = self.get_object()
            
            quantity = Decimal(str(request.data.get('quantity', 0)))
            reference = request.data.get('reference', '')
            reason = request.data.get('reason', 'Manual Reservation')
            expires_at = request.data.get('expires_at')
            
            if quantity <= 0:
                return Response({
                    'success': False,
                    'errors': ['Quantity must be greater than zero']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            
            reservation = reservation_service.create_reservation(
                stock_item=stock_item,
                quantity=quantity,
                reference=reference,
                reason=reason,
                expires_at=expires_at,
                user=request.user
            )
            
            return Response({
                'success': True,
                'data': {
                    'reservation_id': reservation.id,
                    'reserved_quantity': quantity,
                    'available_quantity': stock_item.quantity_available
                },
                'message': 'Stock reserved successfully'
            })
        except InsufficientStockError as e:
            return Response({
                'success': False,
                'errors': [str(e)]
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.handle_error(e, 'Failed to reserve stock')
    
    @action(detail=False, methods=['post'])
    def bulk_adjust(self, request):
        """Bulk adjust multiple stock items."""
        try:
            adjustments = request.data.get('adjustments', [])
            
            if not adjustments:
                return Response({
                    'success': False,
                    'errors': ['No adjustments provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            movement_service = StockMovementService(request.user.tenant)
            processed_count = 0
            errors = []
            
            with transaction.atomic():
                for adjustment in adjustments:
                    try:
                        stock_item_id = adjustment.get('stock_item_id')
                        quantity = Decimal(str(adjustment.get('quantity', 0)))
                        reason = adjustment.get('reason', 'Bulk Adjustment')
                        
                        stock_item = StockItem.objects.get(
                            id=stock_item_id,
                            tenant=request.user.tenant
                        )
                        
                        # Create movement
                        movement_service.create_movement(
                            product=stock_item.product,
                            warehouse=stock_item.warehouse,
                            location=stock_item.location,
                            movement_type=MOVEMENT_TYPES.ADJUSTMENT,
                            quantity=quantity,
                            unit_cost=stock_item.unit_cost,
                            reason=reason,
                            user=request.user
                        )
                        
                        # Update stock
                        stock_item.quantity_on_hand += quantity
                        if stock_item.quantity_on_hand < 0:
                            stock_item.quantity_on_hand = 0
                        
                        stock_item.save()
                        processed_count += 1
                        
                    except StockItem.DoesNotExist:
                        errors.append(f"Stock item {stock_item_id} not found")
                    except Exception as e:
                        errors.append(f"Error processing item {stock_item_id}: {str(e)}")
            
            return Response({
                'success': True,
                'processed_count': processed_count,
                'errors': errors,
                'message': f'Processed {processed_count} adjustments'
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to process bulk adjustments')
    
    @action(detail=False, methods=['get'])
    def aging_report(self, request):
        """Get stock aging report."""
        try:
            analytics_service = AnalyticsService(request.user.tenant)
            
            warehouse_id = request.query_params.get('warehouse_id')
            category_id = request.query_params.get('category_id')
            aging_periods = request.query_params.get('periods', '30,60,90,180').split(',')
            
            aging_data = analytics_service.get_stock_aging_analysis(
                warehouse_id=warehouse_id,
                category_id=category_id,
                aging_periods=[int(p) for p in aging_periods]
            )
            
            return Response({
                'success': True,
                'data': aging_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate aging report')


class StockMovementViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock movements and transaction history.
    """
    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific movements."""
        return StockMovement.objects.select_related(
            'product', 'warehouse', 'location', 'user'
        ).order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def by_product(self, request):
        """Get movements by product."""
        try:
            product_id = request.query_params.get('product_id')
            if not product_id:
                return Response({
                    'success': False,
                    'errors': ['product_id parameter is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            movements = self.get_queryset().filter(product_id=product_id)
            
            # Apply date filters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if start_date:
                movements = movements.filter(created_at__gte=start_date)
            if end_date:
                movements = movements.filter(created_at__lte=end_date)
            
            page = self.paginate_queryset(movements)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(movements, many=True)
            return Response({
                'success': True,
                'data': serializer.data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve movements')
    
    @action(detail=False, methods=['get'])
    def summary_by_type(self, request):
        """Get movement summary grouped by type."""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            movements = self.get_queryset().filter(created_at__gte=start_date)
            
            summary = movements.values('movement_type').annotate(
                count=Count('id'),
                total_quantity=Sum('quantity'),
                avg_quantity=Avg('quantity')
            ).order_by('movement_type')
            
            return Response({
                'success': True,
                'data': list(summary),
                'period_days': days
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate movement summary')


class BatchViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing batches and lot tracking.
    """
    serializer_class = BatchSerializer
    queryset = Batch.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific batches."""
        return Batch.objects.select_related(
            'product', 'supplier'
        ).prefetch_related('stock_items')
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get batches expiring soon."""
        try:
            days = int(request.query_params.get('days', 30))
            expiry_date = timezone.now().date() + timedelta(days=days)
            
            batches = self.get_queryset().filter(
                expiry_date__lte=expiry_date,
                expiry_date__gte=timezone.now().date()
            ).order_by('expiry_date')
            
            serializer = self.get_serializer(batches, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'expiry_threshold_days': days
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve expiring batches')
    
    @action(detail=True, methods=['get'])
    def traceability(self, request, pk=None):
        """Get complete traceability information for batch."""
        try:
            batch = self.get_object()
            
            # Get all stock items with this batch
            stock_items = batch.stock_items.select_related(
                'warehouse', 'location'
            ).all()
            
            # Get all movements for this batch
            movements = StockMovement.objects.filter(
                batch=batch,
                tenant=request.user.tenant
            ).select_related('user').order_by('created_at')
            
            traceability_data = {
                'batch_info': self.get_serializer(batch).data,
                'current_locations': [
                    {
                        'warehouse': item.warehouse.name,
                        'location': item.location.name if item.location else 'Default',
                        'quantity': item.quantity_on_hand
                    }
                    for item in stock_items if item.quantity_on_hand > 0
                ],
                'movement_history': [
                    {
                        'date': movement.created_at,
                        'type': movement.movement_type,
                        'quantity': movement.quantity,
                        'warehouse': movement.warehouse.name,
                        'location': movement.location.name if movement.location else 'Default',
                        'reference': movement.reference,
                        'user': movement.user.get_full_name() if movement.user else 'System'
                    }
                    for movement in movements
                ]
            }
            
            return Response({
                'success': True,
                'data': traceability_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve traceability information')