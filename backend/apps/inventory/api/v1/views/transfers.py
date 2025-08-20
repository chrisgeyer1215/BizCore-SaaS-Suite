# apps/inventory/api/v1/views/transfers.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Case, When
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.transfers import (
    StockTransferSerializer, StockTransferDetailSerializer, StockTransferCreateSerializer,
    StockTransferItemSerializer, StockTransferApprovalSerializer
)
from apps.inventory.models.transfers.transfers import StockTransfer, StockTransferItem
from apps.inventory.services.transfers.transfer_service import TransferService
from apps.inventory.services.stock.reservation_service import ReservationService
from apps.inventory.utils.exceptions import InventoryError, InsufficientStockError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import TRANSFER_STATUSES


class StockTransferViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock transfers between warehouses/locations.
    
    Supports:
    - Inter-warehouse transfers
    - Intra-warehouse location transfers
    - Transfer approval workflows
    - In-transit tracking
    - Partial transfers and shipments
    """
    serializer_class = StockTransferSerializer
    detail_serializer_class = StockTransferDetailSerializer
    create_serializer_class = StockTransferCreateSerializer
    queryset = StockTransfer.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific transfers with optimizations."""
        return StockTransfer.objects.select_related(
            'from_warehouse', 'to_warehouse', 'created_by', 'approved_by'
        ).prefetch_related(
            'items__product', 'items__from_location', 'items__to_location'
        ).with_totals().with_progress()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return self.create_serializer_class
        elif self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action in ['approve', 'reject']:
            return StockTransferApprovalSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create stock transfer with business logic."""
        try:
            transfer_service = TransferService(self.request.user.tenant)
            
            transfer_data = serializer.validated_data
            items_data = transfer_data.pop('items', [])
            
            # Create transfer through service
            transfer = transfer_service.create_transfer(
                transfer_data=transfer_data,
                items_data=items_data,
                user=self.request.user
            )
            
            return transfer
        except Exception as e:
            raise InventoryError(f"Failed to create stock transfer: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get transfers dashboard summary."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_transfers = queryset.count()
            pending_transfers = queryset.filter(status=TRANSFER_STATUSES.PENDING).count()
            in_transit_transfers = queryset.filter(status=TRANSFER_STATUSES.IN_TRANSIT).count()
            completed_transfers = queryset.filter(status=TRANSFER_STATUSES.COMPLETED).count()
            
            # Recent activity
            recent_transfers = queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
            
            # Transfers by warehouse
            warehouse_stats = queryset.values(
                'from_warehouse__name',
                'to_warehouse__name'
            ).annotate(
                transfer_count=Count('id'),
                total_items=Sum('items__quantity')
            ).order_by('-transfer_count')[:5]
            
            return Response({
                'success': True,
                'data': {
                    'total_transfers': total_transfers,
                    'pending_transfers': pending_transfers,
                    'in_transit_transfers': in_transit_transfers,
                    'completed_transfers': completed_transfers,
                    'recent_transfers': recent_transfers,
                    'top_routes': list(warehouse_stats)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get transfers pending approval."""
        try:
            pending_transfers = self.get_queryset().filter(
                status=TRANSFER_STATUSES.PENDING,
                requires_approval=True
            ).order_by('created_at')
            
            page = self.paginate_queryset(pending_transfers)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(pending_transfers, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': pending_transfers.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve pending approvals')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve stock transfer."""
        try:
            transfer = self.get_object()
            
            if transfer.status != TRANSFER_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending transfers can be approved']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            transfer_service = TransferService(request.user.tenant)
            notes = request.data.get('notes', '')
            
            with transaction.atomic():
                transfer_service.approve_transfer(
                    transfer=transfer,
                    approver=request.user,
                    notes=notes
                )
            
            return Response({
                'success': True,
                'message': 'Transfer approved successfully',
                'data': {
                    'transfer_id': transfer.id,
                    'status': transfer.status,
                    'approved_at': transfer.approved_at,
                    'approved_by': transfer.approved_by.get_full_name()
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to approve transfer')
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject stock transfer."""
        try:
            transfer = self.get_object()
            
            if transfer.status != TRANSFER_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending transfers can be rejected']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            transfer_service = TransferService(request.user.tenant)
            reason = request.data.get('reason', 'No reason provided')
            notes = request.data.get('notes', '')
            
            with transaction.atomic():
                transfer_service.reject_transfer(
                    transfer=transfer,
                    rejector=request.user,
                    reason=reason,
                    notes=notes
                )
            
            return Response({
                'success': True,
                'message': 'Transfer rejected',
                'data': {
                    'transfer_id': transfer.id,
                    'status': transfer.status,
                    'rejection_reason': reason
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to reject transfer')
    
    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Mark transfer as shipped/in-transit."""
        try:
            transfer = self.get_object()
            
            if transfer.status != TRANSFER_STATUSES.APPROVED:
                return Response({
                    'success': False,
                    'errors': ['Only approved transfers can be shipped']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            transfer_service = TransferService(request.user.tenant)
            
            shipping_data = {
                'tracking_number': request.data.get('tracking_number', ''),
                'carrier': request.data.get('carrier', ''),
                'expected_arrival': request.data.get('expected_arrival'),
                'notes': request.data.get('notes', '')
            }
            
            with transaction.atomic():
                transfer_service.ship_transfer(
                    transfer=transfer,
                    shipping_data=shipping_data,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Transfer marked as shipped',
                'data': {
                    'transfer_id': transfer.id,
                    'status': transfer.status,
                    'shipped_at': transfer.shipped_at,
                    'tracking_number': transfer.tracking_number
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to ship transfer')
    
    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """Receive stock transfer at destination."""
        try:
            transfer = self.get_object()
            
            if transfer.status != TRANSFER_STATUSES.IN_TRANSIT:
                return Response({
                    'success': False,
                    'errors': ['Only in-transit transfers can be received']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            transfer_service = TransferService(request.user.tenant)
            
            # Get receiving details
            received_items = request.data.get('received_items', [])
            notes = request.data.get('notes', '')
            damage_report = request.data.get('damage_report', '')
            
            with transaction.atomic():
                result = transfer_service.receive_transfer(
                    transfer=transfer,
                    received_items=received_items,
                    notes=notes,
                    damage_report=damage_report,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Transfer received successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to receive transfer')
    
    @action(detail=True, methods=['get'])
    def tracking_info(self, request, pk=None):
        """Get detailed tracking information for transfer."""
        try:
            transfer = self.get_object()
            
            # Build tracking timeline
            timeline = []
            
            # Created
            timeline.append({
                'status': 'CREATED',
                'timestamp': transfer.created_at,
                'user': transfer.created_by.get_full_name() if transfer.created_by else None,
                'description': 'Transfer request created'
            })
            
            # Approved
            if transfer.approved_at:
                timeline.append({
                    'status': 'APPROVED',
                    'timestamp': transfer.approved_at,
                    'user': transfer.approved_by.get_full_name() if transfer.approved_by else None,
                    'description': 'Transfer approved'
                })
            
            # Shipped
            if transfer.shipped_at:
                timeline.append({
                    'status': 'SHIPPED',
                    'timestamp': transfer.shipped_at,
                    'user': None,
                    'description': f'Transfer shipped via {transfer.carrier or "Unknown carrier"}',
                    'tracking_number': transfer.tracking_number
                })
            
            # Received
            if transfer.received_at:
                timeline.append({
                    'status': 'RECEIVED',
                    'timestamp': transfer.received_at,
                    'user': transfer.received_by.get_full_name() if transfer.received_by else None,
                    'description': 'Transfer received at destination'
                })
            
            # Calculate estimated delivery if in transit
            estimated_delivery = None
            if transfer.status == TRANSFER_STATUSES.IN_TRANSIT and transfer.expected_arrival:
                estimated_delivery = transfer.expected_arrival
            
            # Calculate progress percentage
            progress_percentage = 0
            if transfer.status == TRANSFER_STATUSES.PENDING:
                progress_percentage = 25
            elif transfer.status == TRANSFER_STATUSES.APPROVED:
                progress_percentage = 50
            elif transfer.status == TRANSFER_STATUSES.IN_TRANSIT:
                progress_percentage = 75
            elif transfer.status == TRANSFER_STATUSES.COMPLETED:
                progress_percentage = 100
            
            tracking_info = {
                'transfer_id': transfer.id,
                'transfer_number': transfer.transfer_number,
                'current_status': transfer.status,
                'progress_percentage': progress_percentage,
                'from_warehouse': transfer.from_warehouse.name,
                'to_warehouse': transfer.to_warehouse.name,
                'estimated_delivery': estimated_delivery,
                'tracking_number': transfer.tracking_number,
                'carrier': transfer.carrier,
                'timeline': timeline,
                'total_items': transfer.items.count(),
                'total_quantity': sum(item.quantity for item in transfer.items.all())
            }
            
            return Response({
                'success': True,
                'data': tracking_info
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve tracking information')
    
    @action(detail=False, methods=['get'])
    def in_transit_summary(self, request):
        """Get summary of all in-transit transfers."""
        try:
            in_transit_transfers = self.get_queryset().filter(
                status=TRANSFER_STATUSES.IN_TRANSIT
            ).select_related(
                'from_warehouse', 'to_warehouse'
            ).order_by('shipped_at')
            
            summary_data = []
            for transfer in in_transit_transfers:
                # Calculate days in transit
                days_in_transit = None
                if transfer.shipped_at:
                    days_in_transit = (timezone.now() - transfer.shipped_at).days
                
                # Check if overdue
                is_overdue = False
                if transfer.expected_arrival and transfer.expected_arrival < timezone.now().date():
                    is_overdue = True
                
                summary_data.append({
                    'transfer_id': transfer.id,
                    'transfer_number': transfer.transfer_number,
                    'from_warehouse': transfer.from_warehouse.name,
                    'to_warehouse': transfer.to_warehouse.name,
                    'shipped_date': transfer.shipped_at.date() if transfer.shipped_at else None,
                    'expected_arrival': transfer.expected_arrival,
                    'days_in_transit': days_in_transit,
                    'is_overdue': is_overdue,
                    'tracking_number': transfer.tracking_number,
                    'carrier': transfer.carrier,
                    'total_items': transfer.items.count()
                })
            
            return Response({
                'success': True,
                'data': summary_data,
                'total_in_transit': len(summary_data),
                'overdue_count': sum(1 for t in summary_data if t['is_overdue'])
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve in-transit summary')
    
    @action(detail=False, methods=['get'])
    def warehouse_transfer_stats(self, request):
        """Get transfer statistics by warehouse."""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            transfers = self.get_queryset().filter(created_at__gte=start_date)
            
            # Outbound transfers by warehouse
            outbound_stats = transfers.values(
                'from_warehouse__name',
                'from_warehouse__id'
            ).annotate(
                outbound_count=Count('id'),
                outbound_items=Sum('items__quantity'),
                completed_outbound=Count('id', filter=Q(status=TRANSFER_STATUSES.COMPLETED)),
                pending_outbound=Count('id', filter=Q(status=TRANSFER_STATUSES.PENDING)),
                in_transit_outbound=Count('id', filter=Q(status=TRANSFER_STATUSES.IN_TRANSIT))
            ).order_by('-outbound_count')
            
            # Inbound transfers by warehouse
            inbound_stats = transfers.values(
                'to_warehouse__name',
                'to_warehouse__id'
            ).annotate(
                inbound_count=Count('id'),
                inbound_items=Sum('items__quantity'),
                completed_inbound=Count('id', filter=Q(status=TRANSFER_STATUSES.COMPLETED)),
                pending_inbound=Count('id', filter=Q(status=TRANSFER_STATUSES.PENDING)),
                in_transit_inbound=Count('id', filter=Q(status=TRANSFER_STATUSES.IN_TRANSIT))
            ).order_by('-inbound_count')
            
            return Response({
                'success': True,
                'data': {
                    'outbound_transfers': list(outbound_stats),
                    'inbound_transfers': list(inbound_stats),
                    'period_days': days
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve warehouse transfer stats')