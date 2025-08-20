# apps/inventory/api/v1/views/reservations.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Case, When
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.reservations import (
    StockReservationSerializer, StockReservationDetailSerializer,
    StockReservationItemSerializer, BulkReservationSerializer
)
from apps.inventory.models.reservations.reservations import StockReservation, StockReservationItem
from apps.inventory.services.stock.reservation_service import ReservationService
from apps.inventory.utils.exceptions import InventoryError, InsufficientStockError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import RESERVATION_STATUSES, RESERVATION_TYPES


class StockReservationViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock reservations and allocations.
    
    Supports:
    - Sales order reservations
    - Production order allocations
    - Temporary holds and blocks
    - Automatic expiration handling
    - Batch reservation management
    """
    serializer_class = StockReservationSerializer
    detail_serializer_class = StockReservationDetailSerializer
    queryset = StockReservation.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific reservations with optimizations."""
        return StockReservation.objects.select_related(
            'warehouse', 'created_by', 'released_by'
        ).prefetch_related(
            'items__stock_item__product', 'items__stock_item__location'
        ).with_totals().with_expiration_status()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action == 'bulk_reserve':
            return BulkReservationSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create stock reservation with business logic."""
        try:
            reservation_service = ReservationService(self.request.user.tenant)
            
            reservation_data = serializer.validated_data
            items_data = reservation_data.pop('items', [])
            
            # Create reservation through service
            reservation = reservation_service.create_reservation(
                reservation_data=reservation_data,
                items_data=items_data,
                user=self.request.user
            )
            
            return reservation
        except Exception as e:
            raise InventoryError(f"Failed to create stock reservation: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get reservations dashboard summary."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_reservations = queryset.count()
            active_reservations = queryset.filter(status=RESERVATION_STATUSES.ACTIVE).count()
            expired_reservations = queryset.filter(
                status=RESERVATION_STATUSES.EXPIRED
            ).count()
            
            # Calculate total reserved value
            total_reserved_value = queryset.filter(
                status=RESERVATION_STATUSES.ACTIVE
            ).aggregate(
                total=Sum(F('items__quantity') * F('items__stock_item__unit_cost'))
            )['total'] or Decimal('0')
            
            # Expiring soon
            expiring_soon = queryset.filter(
                status=RESERVATION_STATUSES.ACTIVE,
                expires_at__lte=timezone.now() + timedelta(days=7)
            ).count()
            
            # Reservation types breakdown
            type_breakdown = queryset.filter(
                status=RESERVATION_STATUSES.ACTIVE
            ).values('reservation_type').annotate(
                count=Count('id'),
                total_quantity=Sum('items__quantity')
            ).order_by('-count')
            
            # Recent activity
            recent_reservations = queryset.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            return Response({
                'success': True,
                'data': {
                    'total_reservations': total_reservations,
                    'active_reservations': active_reservations,
                    'expired_reservations': expired_reservations,
                    'expiring_soon': expiring_soon,
                    'total_reserved_value': total_reserved_value,
                    'recent_reservations': recent_reservations,
                    'type_breakdown': list(type_breakdown)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get reservations expiring soon."""
        try:
            days = int(request.query_params.get('days', 7))
            cutoff_date = timezone.now() + timedelta(days=days)
            
            expiring_reservations = self.get_queryset().filter(
                status=RESERVATION_STATUSES.ACTIVE,
                expires_at__lte=cutoff_date
            ).order_by('expires_at')
            
            page = self.paginate_queryset(expiring_reservations)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(expiring_reservations, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': expiring_reservations.count(),
                'days_threshold': days
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve expiring reservations')
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """Release stock reservation."""
        try:
            reservation = self.get_object()
            
            if reservation.status != RESERVATION_STATUSES.ACTIVE:
                return Response({
                    'success': False,
                    'errors': ['Only active reservations can be released']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            
            release_reason = request.data.get('reason', 'Manual release')
            partial_release = request.data.get('partial_release', False)
            release_items = request.data.get('release_items', [])
            
            with transaction.atomic():
                if partial_release and release_items:
                    result = reservation_service.partial_release_reservation(
                        reservation=reservation,
                        release_items=release_items,
                        reason=release_reason,
                        user=request.user
                    )
                else:
                    result = reservation_service.release_reservation(
                        reservation=reservation,
                        reason=release_reason,
                        user=request.user
                    )
            
            return Response({
                'success': True,
                'message': 'Reservation released successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to release reservation')
    
    @action(detail=True, methods=['post'])
    def extend_expiration(self, request, pk=None):
        """Extend reservation expiration date."""
        try:
            reservation = self.get_object()
            
            if reservation.status != RESERVATION_STATUSES.ACTIVE:
                return Response({
                    'success': False,
                    'errors': ['Only active reservations can be extended']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            new_expiration = request.data.get('new_expiration_date')
            reason = request.data.get('reason', 'Extension requested')
            
            if not new_expiration:
                return Response({
                    'success': False,
                    'errors': ['new_expiration_date is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            
            with transaction.atomic():
                result = reservation_service.extend_reservation(
                    reservation=reservation,
                    new_expiration_date=new_expiration,
                    reason=reason,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Reservation extended successfully',
                'data': {
                    'reservation_id': reservation.id,
                    'old_expiration': reservation.expires_at,
                    'new_expiration': new_expiration,
                    'extension_reason': reason
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to extend reservation')
    
    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        """Fulfill reservation (convert to actual shipment/usage)."""
        try:
            reservation = self.get_object()
            
            if reservation.status != RESERVATION_STATUSES.ACTIVE:
                return Response({
                    'success': False,
                    'errors': ['Only active reservations can be fulfilled']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            
            fulfillment_data = {
                'reference_number': request.data.get('reference_number', ''),
                'notes': request.data.get('notes', ''),
                'partial_fulfillment': request.data.get('partial_fulfillment', False),
                'fulfilled_items': request.data.get('fulfilled_items', [])
            }
            
            with transaction.atomic():
                result = reservation_service.fulfill_reservation(
                    reservation=reservation,
                    fulfillment_data=fulfillment_data,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Reservation fulfilled successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to fulfill reservation')
    
    @action(detail=False, methods=['post'])
    def bulk_reserve(self, request):
        """Create multiple reservations in bulk."""
        try:
            reservations_data = request.data.get('reservations', [])
            
            if not reservations_data:
                return Response({
                    'success': False,
                    'errors': ['No reservations data provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            created_reservations = []
            errors = []
            
            with transaction.atomic():
                for i, reservation_data in enumerate(reservations_data):
                    try:
                        items_data = reservation_data.pop('items', [])
                        
                        reservation = reservation_service.create_reservation(
                            reservation_data=reservation_data,
                            items_data=items_data,
                            user=request.user
                        )
                        
                        created_reservations.append({
                            'index': i,
                            'reservation_id': reservation.id,
                            'reservation_number': reservation.reservation_number
                        })
                        
                    except InsufficientStockError as e:
                        errors.append({
                            'index': i,
                            'error': f"Insufficient stock: {str(e)}"
                        })
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'error': str(e)
                        })
            
            return Response({
                'success': True,
                'created_count': len(created_reservations),
                'error_count': len(errors),
                'created_reservations': created_reservations,
                'errors': errors,
                'message': f'Created {len(created_reservations)} reservations successfully'
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to create bulk reservations')
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Cleanup expired reservations."""
        try:
            reservation_service = ReservationService(request.user.tenant)
            
            cleanup_result = reservation_service.cleanup_expired_reservations()
            
            return Response({
                'success': True,
                'message': 'Expired reservations cleaned up successfully',
                'data': cleanup_result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to cleanup expired reservations')
    
    @action(detail=False, methods=['get'])
    def availability_check(self, request):
        """Check stock availability for potential reservations."""
        try:
            warehouse_id = request.query_params.get('warehouse_id')
            items_to_check = request.query_params.get('items', '').split(',')
            
            if not warehouse_id or not items_to_check:
                return Response({
                    'success': False,
                    'errors': ['warehouse_id and items parameters are required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reservation_service = ReservationService(request.user.tenant)
            
            availability = reservation_service.check_availability(
                warehouse_id=warehouse_id,
                product_ids=items_to_check
            )
            
            return Response({
                'success': True,
                'data': availability
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to check availability')
    
    @action(detail=False, methods=['get'])
    def reservation_analytics(self, request):
        """Get reservation analytics and trends."""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            analytics_data = {
                'period_days': days,
                'start_date': start_date,
                'reservation_trends': [],
                'fulfillment_rates': {},
                'average_reservation_duration': None,
                'top_reserved_products': []
            }
            
            # Daily reservation trends
            daily_stats = self.get_queryset().filter(
                created_at__gte=start_date
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(
                reservations_created=Count('id'),
                total_quantity=Sum('items__quantity')
            ).order_by('day')
            
            analytics_data['reservation_trends'] = list(daily_stats)
            
            # Fulfillment rates by type
            fulfillment_stats = self.get_queryset().filter(
                created_at__gte=start_date
            ).values('reservation_type').annotate(
                total_reservations=Count('id'),
                fulfilled_reservations=Count('id', filter=Q(status=RESERVATION_STATUSES.FULFILLED)),
                released_reservations=Count('id', filter=Q(status=RESERVATION_STATUSES.RELEASED)),
                expired_reservations=Count('id', filter=Q(status=RESERVATION_STATUSES.EXPIRED))
            )
            
            for stat in fulfillment_stats:
                fulfillment_rate = (
                    (stat['fulfilled_reservations'] / stat['total_reservations'] * 100)
                    if stat['total_reservations'] > 0 else 0
                )
                analytics_data['fulfillment_rates'][stat['reservation_type']] = {
                    'total': stat['total_reservations'],
                    'fulfilled': stat['fulfilled_reservations'],
                    'released': stat['released_reservations'],
                    'expired': stat['expired_reservations'],
                    'fulfillment_rate': round(fulfillment_rate, 2)
                }
            
            # Top reserved products
            top_products = self.get_queryset().filter(
                created_at__gte=start_date
            ).values(
                'items__stock_item__product__name',
                'items__stock_item__product__sku'
            ).annotate(
                total_reserved=Sum('items__quantity'),
                reservation_count=Count('id')
            ).order_by('-total_reserved')[:10]
            
            analytics_data['top_reserved_products'] = list(top_products)
            
            return Response({
                'success': True,
                'data': analytics_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate reservation analytics')