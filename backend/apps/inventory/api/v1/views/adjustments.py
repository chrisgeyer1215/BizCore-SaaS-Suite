# apps/inventory/api/v1/views/adjustments.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Avg, Case, When, DecimalField
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.adjustments import (
    StockAdjustmentSerializer, StockAdjustmentDetailSerializer, StockAdjustmentCreateSerializer,
    StockAdjustmentItemSerializer, CycleCountSerializer, CycleCountDetailSerializer,
    CycleCountItemSerializer, AdjustmentApprovalSerializer
)
from apps.inventory.models.adjustments.adjustments import StockAdjustment, StockAdjustmentItem
from apps.inventory.models.adjustments.cycle_counts import CycleCount, CycleCountItem
from apps.inventory.services.adjustments.adjustment_service import AdjustmentService
from apps.inventory.services.adjustments.count_service import CycleCountService
from apps.inventory.services.stock.movement_service import StockMovementService
from apps.inventory.services.reports.analytics_service import AnalyticsService
from apps.inventory.utils.exceptions import InventoryError, InvalidOperationError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import ADJUSTMENT_STATUSES, ADJUSTMENT_TYPES, COUNT_STATUSES


class StockAdjustmentViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing stock adjustments with approval workflows.
    
    Supports:
    - Various adjustment types (shrinkage, damage, obsolete, etc.)
    - Value-based approval workflows
    - Batch adjustments
    - Variance analysis and reporting
    - Integration with financial systems
    """
    serializer_class = StockAdjustmentSerializer
    detail_serializer_class = StockAdjustmentDetailSerializer
    create_serializer_class = StockAdjustmentCreateSerializer
    queryset = StockAdjustment.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific adjustments with optimizations."""
        return StockAdjustment.objects.select_related(
            'warehouse', 'created_by', 'approved_by'
        ).prefetch_related(
            'items__product', 'items__stock_item'
        ).with_totals().with_approval_status()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return self.create_serializer_class
        elif self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action in ['approve', 'reject']:
            return AdjustmentApprovalSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create stock adjustment with business logic."""
        try:
            adjustment_service = AdjustmentService(self.request.user.tenant)
            
            adjustment_data = serializer.validated_data
            items_data = adjustment_data.pop('items', [])
            
            # Create adjustment through service
            adjustment = adjustment_service.create_adjustment(
                adjustment_data=adjustment_data,
                items_data=items_data,
                user=self.request.user
            )
            
            return adjustment
        except Exception as e:
            raise InventoryError(f"Failed to create stock adjustment: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get adjustments dashboard summary."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_adjustments = queryset.count()
            pending_adjustments = queryset.filter(status=ADJUSTMENT_STATUSES.PENDING).count()
            approved_adjustments = queryset.filter(status=ADJUSTMENT_STATUSES.APPROVED).count()
            
            # Financial impact
            total_value_impact = queryset.filter(
                status=ADJUSTMENT_STATUSES.APPROVED
            ).aggregate(
                total=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            )['total'] or Decimal('0')
            
            positive_adjustments = queryset.filter(
                status=ADJUSTMENT_STATUSES.APPROVED,
                items__quantity_adjusted__gt=0
            ).aggregate(
                total=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            )['total'] or Decimal('0')
            
            negative_adjustments = queryset.filter(
                status=ADJUSTMENT_STATUSES.APPROVED,
                items__quantity_adjusted__lt=0
            ).aggregate(
                total=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            )['total'] or Decimal('0')
            
            # Adjustment types breakdown
            type_breakdown = queryset.filter(
                status=ADJUSTMENT_STATUSES.APPROVED
            ).values('adjustment_type').annotate(
                count=Count('id'),
                total_value=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            ).order_by('-count')
            
            # Recent activity
            recent_adjustments = queryset.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            return Response({
                'success': True,
                'data': {
                    'total_adjustments': total_adjustments,
                    'pending_adjustments': pending_adjustments,
                    'approved_adjustments': approved_adjustments,
                    'total_value_impact': total_value_impact,
                    'positive_adjustments_value': positive_adjustments,
                    'negative_adjustments_value': abs(negative_adjustments),
                    'recent_adjustments': recent_adjustments,
                    'type_breakdown': list(type_breakdown)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get adjustments pending approval."""
        try:
            pending_adjustments = self.get_queryset().filter(
                status=ADJUSTMENT_STATUSES.PENDING,
                requires_approval=True
            ).order_by('created_at')
            
            # Filter by user's approval authority if applicable
            user_approval_limit = getattr(request.user, 'adjustment_approval_limit', None)
            if user_approval_limit:
                pending_adjustments = pending_adjustments.annotate(
                    total_impact=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
                ).filter(total_impact__lte=user_approval_limit)
            
            page = self.paginate_queryset(pending_adjustments)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(pending_adjustments, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': pending_adjustments.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve pending approvals')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve stock adjustment."""
        try:
            adjustment = self.get_object()
            
            if adjustment.status != ADJUSTMENT_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending adjustments can be approved']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            adjustment_service = AdjustmentService(request.user.tenant)
            notes = request.data.get('notes', '')
            
            # Check approval authority
            can_approve, reason = adjustment_service.can_user_approve_adjustment(
                user=request.user,
                adjustment=adjustment
            )
            
            if not can_approve:
                return Response({
                    'success': False,
                    'errors': [reason]
                }, status=status.HTTP_403_FORBIDDEN)
            
            with transaction.atomic():
                adjustment_service.approve_adjustment(
                    adjustment=adjustment,
                    approver=request.user,
                    notes=notes
                )
            
            return Response({
                'success': True,
                'message': 'Adjustment approved and processed successfully',
                'data': {
                    'adjustment_id': adjustment.id,
                    'status': adjustment.status,
                    'approved_at': adjustment.approved_at,
                    'approved_by': adjustment.approved_by.get_full_name()
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to approve adjustment')
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject stock adjustment."""
        try:
            adjustment = self.get_object()
            
            if adjustment.status != ADJUSTMENT_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending adjustments can be rejected']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            adjustment_service = AdjustmentService(request.user.tenant)
            reason = request.data.get('reason', 'No reason provided')
            notes = request.data.get('notes', '')
            
            with transaction.atomic():
                adjustment_service.reject_adjustment(
                    adjustment=adjustment,
                    rejector=request.user,
                    reason=reason,
                    notes=notes
                )
            
            return Response({
                'success': True,
                'message': 'Adjustment rejected',
                'data': {
                    'adjustment_id': adjustment.id,
                    'status': adjustment.status,
                    'rejection_reason': reason
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to reject adjustment')
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple adjustments in bulk."""
        try:
            adjustments_data = request.data.get('adjustments', [])
            ': False,
                    'errors': ['No adjustments data provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            adjustment_service = AdjustmentService(request.user.tenant)
            created_adjustments = []
            errors = []
            
            with transaction.atomic():
                for i, adjustment_data in enumerate(adjustments_data):
                    try:
                        items_data = adjustment_data.pop('items', [])
                        
                        adjustment = adjustment_service.create_adjustment(
                            adjustment_data=adjustment_data,
                            items_data=items_data,
                            user=request.user
                        )
                        
                        created_adjustments.append({
                            'index': i,
                            'adjustment_id': adjustment.id,
                            'adjustment_number': adjustment.adjustment_number
                        })
                        
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'error': str(e)
                        })
            
            return Response({
                'success': True,
                'created_count': len(created_adjustments),
                'error_count': len(errors),
                'created_adjustments': created_adjustments,
                'errors': errors,
                'message': f'Created {len(created_adjustments)} adjustments successfully'
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to create bulk adjustments')
    
    @action(detail=False, methods=['get'])
    def variance_analysis(self, request):
        """Get variance analysis for adjustments."""
        try:
            days = int(request.query_params.get('days', 30))
            warehouse_id = request.query_params.get('warehouse_id')
            category_id = request.query_params.get('category_id')
            
            analytics_service = AnalyticsService(request.user.tenant)
            
            variance_data = analytics_service.get_adjustment_variance_analysis(
                days=days,
                warehouse_id=warehouse_id,
                category_id=category_id
            )
            
            return Response({
                'success': True,
                'data': variance_data
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate variance analysis')
    
    @action(detail=False, methods=['get'])
    def shrinkage_report(self, request):
        """Get shrinkage analysis report."""
        try:
            days = int(request.query_params.get('days', 90))
            start_date = timezone.now() - timedelta(days=days)
            
            shrinkage_adjustments = self.get_queryset().filter(
                status=ADJUSTMENT_STATUSES.APPROVED,
                adjustment_type=ADJUSTMENT_TYPES.SHRINKAGE,
                created_at__gte=start_date
            )
            
            # Calculate shrinkage metrics
            total_shrinkage_value = shrinkage_adjustments.aggregate(
                total=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            )['total'] or Decimal('0')
            
            # Shrinkage by product category
            category_shrinkage = shrinkage_adjustments.values(
                'items__product__category__name'
            ).annotate(
                shrinkage_count=Count('items'),
                shrinkage_value=Sum(F('items__quantity_adjusted') * F('items__unit_cost')),
                avg_shrinkage=Avg(F('items__quantity_adjusted') * F('items__unit_cost'))
            ).order_by('-shrinkage_value')
            
            # Shrinkage by warehouse
            warehouse_shrinkage = shrinkage_adjustments.values(
                'warehouse__name'
            ).annotate(
                shrinkage_count=Count('items'),
                shrinkage_value=Sum(F('items__quantity_adjusted') * F('items__unit_cost'))
            ).order_by('-shrinkage_value')
            
            # Top products with shrinkage
            product_shrinkage = shrinkage_adjustments.values(
                'items__product__name',
                'items__product__sku'
            ).annotate(
                shrinkage_qty=Sum('items__quantity_adjusted'),
                shrinkage_value=Sum(F('items__quantity_adjusted') * F('items__unit_cost')),
                shrinkage_incidents=Count('items')
            ).order_by('-shrinkage_value')[:10]
            
            return Response({
                'success': True,
                'data': {
                    'total_shrinkage_value': abs(total_shrinkage_value),
                    'shrinkage_incidents': shrinkage_adjustments.count(),
                    'average_shrinkage_per_incident': (
                        abs(total_shrinkage_value) / shrinkage_adjustments.count()
                        if shrinkage_adjustments.count() > 0 else 0
                    ),
                    'category_breakdown': list(category_shrinkage),
                    'warehouse_breakdown': list(warehouse_shrinkage),
                    'top_products': list(product_shrinkage),
                    'period_days': days
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate shrinkage report')


class CycleCountViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing cycle counts and inventory audits.
    
    Supports:
    - Scheduled and ad-hoc cycle counts
    - ABC analysis-based counting frequency
    - Multi-user counting with reconciliation
    - Variance tracking and adjustment generation
    - Mobile-friendly counting interfaces
    """
    serializer_class = CycleCountSerializer
    detail_serializer_class = CycleCountDetailSerializer
    queryset = CycleCount.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific cycle counts with optimizations."""
        return CycleCount.objects.select_related(
            'warehouse', 'created_by', 'approved_by'
        ).prefetch_related(
            'items__product', 'items__stock_item'
        ).with_progress().with_variance_summary()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return self.detail_serializer_class
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create cycle count with business logic."""
        try:
            count_service = CycleCountService(self.request.user.tenant)
            
            count_data = serializer.validated_data
            
            # Create cycle count through service
            cycle_count = count_service.create_cycle_count(
                count_data=count_data,
                user=self.request.user
            )
            
            return cycle_count
        except Exception as e:
            raise InventoryError(f"Failed to create cycle count: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get cycle count dashboard summary."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_counts = queryset.count()
            active_counts = queryset.filter(status=COUNT_STATUSES.IN_PROGRESS).count()
            completed_counts = queryset.filter(status=COUNT_STATUSES.COMPLETED).count()
            pending_counts = queryset.filter(status=COUNT_STATUSES.PENDING).count()
            
            # Variance metrics
            recent_counts = queryset.filter(
                completed_at__gte=timezone.now() - timedelta(days=30),
                status=COUNT_STATUSES.COMPLETED
            )
            
            total_variances = recent_counts.aggregate(
                variance_count=Sum('items__variance_quantity'),
                variance_value=Sum(F('items__variance_quantity') * F('items__unit_cost'))
            )
            
            # Accuracy metrics
            accurate_counts = recent_counts.filter(
                items__variance_quantity=0
            ).count()
            
            accuracy_rate = (
                (accurate_counts / recent_counts.count() * 100)
                if recent_counts.count() > 0 else 100
            )
            
            return Response({
                'success': True,
                'data': {
                    'total_counts': total_counts,
                    'active_counts': active_counts,
                    'completed_counts': completed_counts,
                    'pending_counts': pending_counts,
                    'accuracy_rate': round(accuracy_rate, 2),
                    'total_variance_items': total_variances['variance_count'] or 0,
                    'total_variance_value': total_variances['variance_value'] or Decimal('0')
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard summary')
    
    @action(detail=False, methods=['post'])
    def generate_abc_counts(self, request):
        """Generate cycle counts based on ABC analysis."""
        try:
            warehouse_id = request.data.get('warehouse_id')
            count_frequency = request.data.get('count_frequency', 'MONTHLY')
            
            if not warehouse_id:
                return Response({
                    'success': False,
                    'errors': ['warehouse_id is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            count_service = CycleCountService(request.user.tenant)
            
            # Generate counts based on ABC classification
            generated_counts = count_service.generate_abc_based_counts(
                warehouse_id=warehouse_id,
                count_frequency=count_frequency,
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': f'Generated {len(generated_counts)} cycle counts',
                'data': {
                    'generated_count': len(generated_counts),
                    'counts': [
                        {
                            'count_id': count.id,
                            'count_name': count.count_name,
                            'items_count': count.items.count()
                        }
                        for count in generated_counts
                    ]
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate ABC-based counts')
    
    @action(detail=True, methods=['post'])
    def start_counting(self, request, pk=None):
        """Start the counting process for a cycle count."""
        try:
            cycle_count = self.get_object()
            
            if cycle_count.status != COUNT_STATUSES.PENDING:
                return Response({
                    'success': False,
                    'errors': ['Only pending counts can be started']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            count_service = CycleCountService(request.user.tenant)
            
            with transaction.atomic():
                count_service.start_cycle_count(
                    cycle_count=cycle_count,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Cycle count started successfully',
                'data': {
                    'count_id': cycle_count.id,
                    'status': cycle_count.status,
                    'started_at': cycle_count.started_at
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to start cycle count')
    
    @action(detail=True, methods=['post'])
    def submit_counts(self, request, pk=None):
        """Submit actual counts for cycle count items."""
        try:
            cycle_count = self.get_object()
            
            if cycle_count.status != COUNT_STATUSES.IN_PROGRESS:
                return Response({
                    'success': False,
                    'errors': ['Count must be in progress to submit counts']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            count_data = request.data.get('counts', [])
            
            if Response({
                    'success': False,
                    'errors': ['No count data provided']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            count_service = CycleCountService(request.user.tenant)
            
            with transaction.atomic():
                result = count_service.submit_cycle_counts(
                    cycle_count=cycle_count,
                    count_data=count_data,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Counts submitted successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to submit counts')
    
    @action(detail=True, methods=['post'])
    def complete_count(self, request, pk=None):
        """Complete cycle count and generate adjustments for variances."""
        try:
            cycle_count = self.get_object()
            
            if cycle_count.status != COUNT_STATUSES.IN_PROGRESS:
                return Response({
                    'success': False,
                    'errors': ['Count must be in progress to complete']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            count_service = CycleCountService(request.user.tenant)
            generate_adjustments = request.data.get('generate_adjustments', True)
            adjustment_reason = request.data.get('adjustment_reason', 'Cycle count variance')
            
            with transaction.atomic():
                result = count_service.complete_cycle_count(
                    cycle_count=cycle_count,
                    generate_adjustments=generate_adjustments,
                    adjustment_reason=adjustment_reason,
                    user=request.user
                )
            
            return Response({
                'success': True,
                'message': 'Cycle count completed successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to complete cycle count')
    
    @action(detail=True, methods=['get'])
    def variance_report(self, request, pk=None):
        """Get detailed variance report for cycle count."""
        try:
            cycle_count = self.get_object()
            
            # Get items with variances
            variance_items = cycle_count.items.filter(
                variance_quantity__ne=0
            ).select_related('product', 'stock_item')
            
            variance_summary = {
                'cycle_count_id': cycle_count.id,
                'count_name': cycle_count.count_name,
                'total_items_counted': cycle_count.items.count(),
                'items_with_variance': variance_items.count(),
                'accuracy_rate': (
                    ((cycle_count.items.count() - variance_items.count()) /
                     cycle_count.items.count() * 100)
                    if cycle_count.items.count() > 0 else 100
                ),
                'variances': []
            }
            
            total_variance_value = Decimal('0')
            
            for item in variance_items:
                variance_value = item.variance_quantity * item.unit_cost
                total_variance_value += variance_value
                
                variance_summary['variances'].append({
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'expected_quantity': item.expected_quantity,
                    'counted_quantity': item.counted_quantity,
                    'variance_quantity': item.variance_quantity,
                    'unit_cost': item.unit_cost,
                    'variance_value': variance_value,
                    'variance_percentage': (
                        (item.variance_quantity / item.expected_quantity * 100)
                        if item.expected_quantity > 0 else 0
                    )
                })
            
            variance_summary['total_variance_value'] = total_variance_value
            
            return Response({
                'success': True,
                'data': variance_summary
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate variance report')
    
    @action(detail=False, methods=['get'])
    def counting_schedule(self, request):
        """Get upcoming counting schedule based on ABC classification."""
        try:
            warehouse_id = request.query_params.get('warehouse_id')
            days_ahead = int(request.query_params.get('days_ahead', 30))
            
            count_service = CycleCountService(request.user.tenant)
            
            schedule = count_service.get_counting_schedule(
                warehouse_id=warehouse_id,
                days_ahead=days_ahead
            )
            
            return Response({
                'success': True,
                'data': schedule
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve counting schedule')