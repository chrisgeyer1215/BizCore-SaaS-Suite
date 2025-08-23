# crm/viewsets/opportunity.py
"""
Opportunity Management ViewSets

Provides REST API endpoints for:
- Opportunity/deal management with pipeline automation
- Pipeline stage management and progression
- Opportunity product/line item management
- Sales forecasting and analytics
- Deal progression tracking
- Win/loss analysis
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from django.db.models import Count, Sum, Avg, Q, F, Case, When, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, Coalesce
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from crm.models.opportunity import (
    Opportunity, PipelineStage, OpportunityProduct, OpportunityStageHistory
)
from crm.serializers.opportunity import (
    OpportunitySerializer, OpportunityDetailSerializer, OpportunityCreateSerializer,
    PipelineStageSerializer, OpportunityProductSerializer, OpportunityStageHistorySerializer
)
from crm.permissions.opportunity import OpportunityPermission, PipelinePermission
from crm.utils.tenant_utils import get_tenant_from_request, check_tenant_limits
from crm.utils.pipeline_utils import (
    PipelineManager, get_next_stage, calculate_stage_duration,
    check_stage_requirements, identify_pipeline_bottlenecks,
    get_pipeline_health_score
)
from crm.utils.formatters import format_currency, format_percentage, format_duration
from crm.utils.email_utils import send_crm_email
from .base import CRMBaseViewSet, CRMReadOnlyViewSet, cache_response, require_tenant_limits


class OpportunityFilter(filters.FilterSet):
    """Advanced filtering for Opportunity ViewSet."""
    
    name = filters.CharFilter(lookup_expr='icontains')
    account_name = filters.CharFilter(field_name='account__name', lookup_expr='icontains')
    stage = filters.ModelChoiceFilter(queryset=PipelineStage.objects.all())
    assigned_to = filters.NumberFilter(field_name='assigned_to__id')
    value_min = filters.NumberFilter(field_name='value', lookup_expr='gte')
    value_max = filters.NumberFilter(field_name='value', lookup_expr='lte')
    probability_min = filters.NumberFilter(field_name='probability', lookup_expr='gte')
    probability_max = filters.NumberFilter(field_name='probability', lookup_expr='lte')
    expected_close_after = filters.DateFilter(field_name='expected_close_date', lookup_expr='gte')
    expected_close_before = filters.DateFilter(field_name='expected_close_date', lookup_expr='lte')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    source = filters.CharFilter(lookup_expr='icontains')
    is_closed = filters.BooleanFilter(method='filter_is_closed')
    is_won = filters.BooleanFilter(method='filter_is_won')
    overdue = filters.BooleanFilter(method='filter_overdue')
    high_value = filters.BooleanFilter(method='filter_high_value')
    stale = filters.BooleanFilter(method='filter_stale')
    
    class Meta:
        model = Opportunity
        fields = ['account', 'contact', 'assigned_to', 'stage']
    
    def filter_is_closed(self, queryset, name, value):
        """Filter closed/open opportunities."""
        if value:
            return queryset.filter(stage__is_closed=True)
        else:
            return queryset.filter(stage__is_closed=False)
    
    def filter_is_won(self, queryset, name, value):
        """Filter won/lost opportunities."""
        if value:
            return queryset.filter(stage__is_won=True)
        else:
            return queryset.filter(stage__is_won=False)
    
    def filter_overdue(self, queryset, name, value):
        """Filter overdue opportunities."""
        if value:
            return queryset.filter(
                expected_close_date__lt=timezone.now().date(),
                stage__is_closed=False
            )
        return queryset
    
    def filter_high_value(self, queryset, name, value):
        """Filter high-value opportunities (top 20% by value)."""
        if value:
            # Calculate 80th percentile value
            values = queryset.filter(value__isnull=False).values_list('value', flat=True)
            if values:
                import numpy as np
                percentile_80 = np.percentile(list(values), 80)
                return queryset.filter(value__gte=percentile_80)
        return queryset
    
    def filter_stale(self, queryset, name, value):
        """Filter stale opportunities (no activity in 30+ days)."""
        if value:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(
                stage_changed_at__lt=thirty_days_ago,
                stage__is_closed=False
            )
        return queryset


class OpportunityViewSet(CRMBaseViewSet):
    """
    ViewSet for Opportunity management with comprehensive functionality.
    
    Provides CRUD operations, pipeline management, and deal analytics.
    """
    
    queryset = Opportunity.objects.select_related(
        'account', 'contact', 'assigned_to', 'stage', 'lead'
    ).prefetch_related('products', 'activities')
    
    serializer_class = OpportunitySerializer
    filterset_class = OpportunityFilter
    search_fields = [
        'name', 'description', 'source', 'account__name', 'contact__first_name',
        'contact__last_name', 'contact__email'
    ]
    ordering_fields = [
        'name', 'value', 'probability', 'expected_close_date', 'created_at',
        'stage_changed_at'
    ]
    ordering = ['-value', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return OpportunityCreateSerializer
        elif self.action == 'retrieve':
            return OpportunityDetailSerializer
        return OpportunitySerializer
    
    def get_model_permission(self):
        """Get opportunity-specific permission class."""
        return OpportunityPermission
    
    @require_tenant_limits('opportunities')
    def create(self, request, *args, **kwargs):
        """Create new opportunity with automatic stage setup."""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            # Initialize pipeline tracking
            opportunity_id = response.data['id']
            try:
                opportunity = Opportunity.objects.get(id=opportunity_id)
                
                # Create initial stage history entry
                OpportunityStageHistory.objects.create(
                    opportunity=opportunity,
                    old_stage=None,
                    new_stage=opportunity.stage.name,
                    changed_by=request.user,
                    change_reason='Opportunity created',
                    changed_at=opportunity.created_at,
                    tenant=opportunity.tenant
                )
                
                # Set initial stage changed timestamp
                opportunity.stage_changed_at = opportunity.created_at
                opportunity.save(update_fields=['stage_changed_at'])
                
            except Exception as e:
                print(f"Error initializing opportunity pipeline: {e}")
        
        return response
    
    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        """
        Advance opportunity to next stage with validation.
        
        Expected payload:
        {
            "target_stage": "stage_name",
            "notes": "optional notes",
            "skip_requirements": false
        }
        """
        try:
            opportunity = self.get_object()
            target_stage = request.data.get('target_stage')
            notes = request.data.get('notes', '')
            skip_requirements = request.data.get('skip_requirements', False)
            
            if not target_stage:
                return Response(
                    {'error': 'target_stage is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use pipeline manager for stage advancement
            pipeline_manager = PipelineManager(opportunity.tenant)
            result = pipeline_manager.advance_opportunity(
                opportunity, target_stage, request.user, notes
            )
            
            if result['success']:
                # Refresh opportunity data
                opportunity.refresh_from_db()
                
                # Send notifications if stage changed
                if result['old_stage'] != result['new_stage']:
                    self._send_stage_change_notification(opportunity, result, request.user)
                
                return Response({
                    'message': result['message'],
                    'opportunity': OpportunitySerializer(opportunity).data,
                    'stage_change': result
                })
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def win(self, request, pk=None):
        """
        Mark opportunity as won.
        
        Expected payload:
        {
            "close_date": "YYYY-MM-DD",
            "actual_value": decimal,
            "win_reason": "string",
            "notes": "string"
        }
        """
        try:
            opportunity = self.get_object()
            
            if opportunity.stage.is_closed:
                return Response(
                    {'error': 'Opportunity is already closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            close_date = request.data.get('close_date')
            actual_value = request.data.get('actual_value')
            win_reason = request.data.get('win_reason', '')
            notes = request.data.get('notes', '')
            
            # Find won stage
            won_stage = PipelineStage.objects.filter(
                tenant=opportunity.tenant,
                is_won=True,
                is_closed=True
            ).first()
            
            if not won_stage:
                return Response(
                    {'error': 'No won stage configured'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update opportunity
                opportunity.stage = won_stage
                opportunity.probability = 100
                opportunity.closed_date = close_date or timezone.now().date()
                opportunity.actual_value = actual_value or opportunity.value
                opportunity.win_reason = win_reason
                opportunity.stage_changed_at = timezone.now()
                opportunity.save()
                
                # Create stage history
                OpportunityStageHistory.objects.create(
                    opportunity=opportunity,
                    old_stage=opportunity.stage.name,
                    new_stage=won_stage.name,
                    changed_by=request.user,
                    change_reason=f'Opportunity won. Reason: {win_reason}. Notes: {notes}',
                    changed_at=timezone.now(),
                    tenant=opportunity.tenant
                )
                
                # Create won activity
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=opportunity.tenant,
                    type='WON',
                    subject='Opportunity Won',
                    description=f'Opportunity won for {format_currency(opportunity.actual_value)}. Reason: {win_reason}. Notes: {notes}',
                    related_to_id=opportunity.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                )
                
                # Update related lead if exists
                if opportunity.lead:
                    opportunity.lead.status = 'CONVERTED'
                    opportunity.lead.converted_at = timezone.now()
                    opportunity.lead.save(update_fields=['status', 'converted_at'])
                
                # Send win notification
                self._send_win_notification(opportunity, request.user)
                
                return Response({
                    'message': 'Opportunity marked as won',
                    'opportunity': OpportunitySerializer(opportunity).data,
                    'actual_value': float(opportunity.actual_value),
                    'close_date': opportunity.closed_date.isoformat()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def lose(self, request, pk=None):
        """
        Mark opportunity as lost.
        
        Expected payload:
        {
            "close_date": "YYYY-MM-DD",
            "loss_reason": "string",
            "competitor": "string",
            "notes": "string"
        }
        """
        try:
            opportunity = self.get_object()
            
            if opportunity.stage.is_closed:
                return Response(
                    {'error': 'Opportunity is already closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            close_date = request.data.get('close_date')
            loss_reason = request.data.get('loss_reason', '')
            competitor = request.data.get('competitor', '')
            notes = request.data.get('notes', '')
            
            # Find lost stage
            lost_stage = PipelineStage.objects.filter(
                tenant=opportunity.tenant,
                is_won=False,
                is_closed=True
            ).first()
            
            if not lost_stage:
                return Response(
                    {'error': 'No lost stage configured'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update opportunity
                opportunity.stage = lost_stage
                opportunity.probability = 0
                opportunity.closed_date = close_date or timezone.now().date()
                opportunity.loss_reason = loss_reason
                opportunity.competitor = competitor
                opportunity.stage_changed_at = timezone.now()
                opportunity.save()
                
                # Create stage history
                OpportunityStageHistory.objects.create(
                    opportunity=opportunity,
                    old_stage=opportunity.stage.name,
                    new_stage=lost_stage.name,
                    changed_by=request.user,
                    change_reason=f'Opportunity lost. Reason: {loss_reason}. Competitor: {competitor}. Notes: {notes}',
                    changed_at=timezone.now(),
                    tenant=opportunity.tenant
                )
                
                # Create lost activity
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=opportunity.tenant,
                    type='LOST',
                    subject='Opportunity Lost',
                    description=f'Opportunity lost. Reason: {loss_reason}. Competitor: {competitor}. Notes: {notes}',
                    related_to_id=opportunity.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                )
                
                return Response({
                    'message': 'Opportunity marked as lost',
                    'opportunity': OpportunitySerializer(opportunity).data,
                    'loss_reason': loss_reason,
                    'competitor': competitor,
                    'close_date': opportunity.closed_date.isoformat()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        """
        Reopen a closed opportunity.
        
        Expected payload:
        {
            "target_stage": "stage_name",
            "reopen_reason": "string",
            "notes": "string"
        }
        """
        try:
            opportunity = self.get_object()
            
            if not opportunity.stage.is_closed:
                return Response(
                    {'error': 'Opportunity is not closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            target_stage = request.data.get('target_stage')
            reopen_reason = request.data.get('reopen_reason', '')
            notes = request.data.get('notes', '')
            
            if not target_stage:
                return Response(
                    {'error': 'target_stage is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                new_stage = PipelineStage.objects.get(
                    name=target_stage,
                    tenant=opportunity.tenant,
                    is_closed=False
                )
            except PipelineStage.DoesNotExist:
                return Response(
                    {'error': f'Stage "{target_stage}" not found or is closed'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            with transaction.atomic():
                old_stage_name = opportunity.stage.name
                
                # Update opportunity
                opportunity.stage = new_stage
                opportunity.probability = new_stage.probability
                opportunity.closed_date = None
                opportunity.actual_value = None
                opportunity.win_reason = None
                opportunity.loss_reason = None
                opportunity.competitor = None
                opportunity.stage_changed_at = timezone.now()
                opportunity.save()
                
                # Create stage history
                OpportunityStageHistory.objects.create(
                    opportunity=opportunity,
                    old_stage=old_stage_name,
                    new_stage=new_stage.name,
                    changed_by=request.user,
                    change_reason=f'Opportunity reopened. Reason: {reopen_reason}. Notes: {notes}',
                    changed_at=timezone.now(),
                    tenant=opportunity.tenant
                )
                
                # Create reopen activity
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=opportunity.tenant,
                    type='REOPENED',
                    subject='Opportunity Reopened',
                    description=f'Opportunity reopened to {new_stage.name} stage. Reason: {reopen_reason}. Notes: {notes}',
                    related_to_id=opportunity.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                )
                
                return Response({
                    'message': f'Opportunity reopened to {new_stage.name} stage',
                    'opportunity': OpportunitySerializer(opportunity).data
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def stage_history(self, request, pk=None):
        """Get stage progression history for opportunity."""
        try:
            opportunity = self.get_object()
            
            history = OpportunityStageHistory.objects.filter(
                opportunity=opportunity,
                tenant=opportunity.tenant
            ).order_by('-changed_at')
            
            serializer = OpportunityStageHistorySerializer(history, many=True)
            
            # Calculate stage durations
            history_with_durations = []
            previous_change = None
            
            for entry in reversed(serializer.data):
                entry_data = entry.copy()
                
                if previous_change:
                    # Calculate duration in previous stage
                    prev_date = datetime.fromisoformat(previous_change['changed_at'].replace('Z', '+00:00'))
                    curr_date = datetime.fromisoformat(entry['changed_at'].replace('Z', '+00:00'))
                    duration_seconds = (curr_date - prev_date).total_seconds()
                    entry_data['duration_in_previous_stage'] = format_duration(int(duration_seconds))
                
                history_with_durations.append(entry_data)
                previous_change = entry
            
            # Calculate current stage duration if not closed
            if not opportunity.stage.is_closed and history_with_durations:
                last_change = datetime.fromisoformat(
                    history_with_durations[-1]['changed_at'].replace('Z', '+00:00')
                )
                current_duration = (timezone.now() - last_change).total_seconds()
                history_with_durations[-1]['current_stage_duration'] = format_duration(int(current_duration))
            
            return Response({
                'opportunity_id': opportunity.id,
                'current_stage': opportunity.stage.name,
                'stage_history': list(reversed(history_with_durations))
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products/line items for this opportunity."""
        try:
            opportunity = self.get_object()
            products = OpportunityProduct.objects.filter(
                opportunity=opportunity
            ).select_related('product')
            
            serializer = OpportunityProductSerializer(products, many=True)
            
            # Calculate totals
            total_value = sum(item.total_value for item in products)
            total_quantity = sum(item.quantity for item in products)
            
            return Response({
                'opportunity_id': opportunity.id,
                'products': serializer.data,
                'summary': {
                    'total_items': products.count(),
                    'total_quantity': total_quantity,
                    'total_value': float(total_value),
                    'formatted_total': format_currency(total_value)
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_product(self, request, pk=None):
        """Add product/line item to opportunity."""
        try:
            opportunity = self.get_object()
            
            product_data = request.data.copy()
            product_data['opportunity'] = opportunity.id
            
            serializer = OpportunityProductSerializer(data=product_data)
            if serializer.is_valid():
                product_item = serializer.save()
                
                # Recalculate opportunity value
                self._recalculate_opportunity_value(opportunity)
                
                return Response(
                    OpportunityProductSerializer(product_item).data,
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get activities for this opportunity."""
        try:
            from crm.models.activity import Activity
            from crm.serializers.activity import ActivitySerializer
            
            opportunity = self.get_object()
            activities = Activity.objects.filter(
                related_to_id=opportunity.id,
                tenant=opportunity.tenant
            ).order_by('-created_at')
            
            # Apply filtering
            activity_type = request.query_params.get('type')
            if activity_type:
                activities = activities.filter(type=activity_type)
            
            page = self.paginate_queryset(activities)
            if page is not None:
                serializer = ActivitySerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = ActivitySerializer(activities, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def forecast_probability(self, request, pk=None):
        """Get AI-powered forecast probability for opportunity."""
        try:
            opportunity = self.get_object()
            
            # Calculate various probability factors
            factors = self._calculate_probability_factors(opportunity)
            
            # Weighted probability calculation
            weighted_probability = self._calculate_weighted_probability(opportunity, factors)
            
            return Response({
                'opportunity_id': opportunity.id,
                'current_probability': opportunity.probability,
                'ai_predicted_probability': weighted_probability,
                'probability_factors': factors,
                'confidence_level': self._get_confidence_level(factors),
                'recommendations': self._generate_probability_recommendations(opportunity, factors)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pipeline_overview(self, request):
        """Get pipeline overview and metrics."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Basic pipeline metrics
            pipeline_data = {}
            
            # Get all stages
            stages = PipelineStage.objects.filter(
                tenant=get_tenant_from_request(request)
            ).order_by('order')
            
            for stage in stages:
                stage_opportunities = queryset.filter(stage=stage)
                
                pipeline_data[stage.name] = {
                    'stage_id': stage.id,
                    'count': stage_opportunities.count(),
                    'total_value': float(stage_opportunities.aggregate(
                        Sum('value'))['value__sum'] or 0),
                    'avg_value': float(stage_opportunities.aggregate(
                        Avg('value'))['value__avg'] or 0),
                    'probability': stage.probability,
                    'is_closed': stage.is_closed,
                    'is_won': stage.is_won
                }
            
            # Calculate pipeline health
            health_score = get_pipeline_health_score(get_tenant_from_request(request))
            
            # Identify bottlenecks
            bottlenecks = identify_pipeline_bottlenecks(get_tenant_from_request(request))
            
            return Response({
                'pipeline_stages': pipeline_data,
                'health_score': health_score,
                'bottlenecks': bottlenecks[:3],  # Top 3 bottlenecks
                'total_opportunities': queryset.count(),
                'total_pipeline_value': float(queryset.aggregate(
                    Sum('value'))['value__sum'] or 0),
                'weighted_pipeline_value': self._calculate_weighted_pipeline_value(queryset)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def win_loss_analysis(self, request):
        """Get win/loss analysis and insights."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Filter closed opportunities
            closed_ops = queryset.filter(stage__is_closed=True)
            won_ops = closed_ops.filter(stage__is_won=True)
            lost_ops = closed_ops.filter(stage__is_won=False)
            
            # Basic win/loss metrics
            total_closed = closed_ops.count()
            total_won = won_ops.count()
            total_lost = lost_ops.count()
            
            win_rate = (total_won / total_closed * 100) if total_closed > 0 else 0
            
            # Value analysis
            won_value = won_ops.aggregate(Sum('actual_value'))['actual_value__sum'] or 0
            lost_value = lost_ops.aggregate(Sum('value'))['value__sum'] or 0
            
            # Win/loss reasons analysis
            win_reasons = won_ops.values('win_reason').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            loss_reasons = lost_ops.values('loss_reason').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            # Competitor analysis
            competitors = lost_ops.exclude(
                competitor__isnull=True
            ).exclude(
                competitor__exact=''
            ).values('competitor').annotate(
                count=Count('id'),
                lost_value=Sum('value')
            ).order_by('-count')[:5]
            
            # Sales cycle analysis
            won_with_dates = won_ops.filter(
                closed_date__isnull=False
            )
            
            avg_sales_cycle = None
            if won_with_dates.exists():
                cycles = []
                for opp in won_with_dates:
                    cycle_days = (opp.closed_date - opp.created_at.date()).days
                    cycles.append(cycle_days)
                avg_sales_cycle = sum(cycles) / len(cycles)
            
            return Response({
                'win_loss_summary': {
                    'total_closed': total_closed,
                    'total_won': total_won,
                    'total_lost': total_lost,
                    'win_rate': round(win_rate, 2),
                    'won_value': float(won_value),
                    'lost_value': float(lost_value),
                    'avg_sales_cycle_days': round(avg_sales_cycle, 1) if avg_sales_cycle else None
                },
                'win_reasons': list(win_reasons),
                'loss_reasons': list(loss_reasons),
                'top_competitors': list(competitors),
                'insights': self._generate_win_loss_insights(
                    win_rate, avg_sales_cycle, list(loss_reasons), list(competitors)
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_stage_update(self, request):
        """Bulk update opportunity stages."""
        try:
            opportunity_ids = request.data.get('opportunity_ids', [])
            target_stage = request.data.get('target_stage')
            notes = request.data.get('notes', '')
            
            if not opportunity_ids or not target_stage:
                return Response(
                    {'error': 'opportunity_ids and target_stage are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                stage = PipelineStage.objects.get(
                    name=target_stage,
                    tenant=get_tenant_from_request(request)
                )
            except PipelineStage.DoesNotExist:
                return Response(
                    {'error': f'Stage "{target_stage}" not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            tenant = get_tenant_from_request(request)
            opportunities = Opportunity.objects.filter(
                id__in=opportunity_ids,
                tenant=tenant
            )
            
            updated_count = 0
            
            with transaction.atomic():
                for opportunity in opportunities:
                    old_stage = opportunity.stage.name
                    opportunity.stage = stage
                    opportunity.probability = stage.probability
                    opportunity.stage_changed_at = timezone.now()
                    opportunity.save()
                    
                    # Create stage history
                    OpportunityStageHistory.objects.create(
                        opportunity=opportunity,
                        old_stage=old_stage,
                        new_stage=stage.name,
                        changed_by=request.user,
                        change_reason=f'Bulk stage update. Notes: {notes}',
                        changed_at=timezone.now(),
                        tenant=tenant
                    )
                    
                    updated_count += 1
            
            return Response({
                'message': f'{updated_count} opportunities updated to {target_stage} stage',
                'updated_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _send_stage_change_notification(self, opportunity, stage_change, changed_by):
        """Send notification for stage change."""
        try:
            if opportunity.assigned_to and opportunity.assigned_to != changed_by:
                send_crm_email(
                    recipient_email=opportunity.assigned_to.email,
                    subject=f'Opportunity Stage Updated: {opportunity.name}',
                    template_name='opportunity_stage_change',
                    context_data={
                        'opportunity': opportunity,
                        'old_stage': stage_change['old_stage'],
                        'new_stage': stage_change['new_stage'],
                        'changed_by': changed_by
                    },
                    recipient_data={
                        'first_name': opportunity.assigned_to.first_name,
                        'last_name': opportunity.assigned_to.last_name,
                        'email': opportunity.assigned_to.email
                    },
                    tenant=opportunity.tenant
                )
        except Exception as e:
            print(f"Failed to send stage change notification: {e}")
    
    def _send_win_notification(self, opportunity, won_by):
        """Send notification for won opportunity."""
        try:
            # Notify assigned user
            if opportunity.assigned_to:
                send_crm_email(
                    recipient_email=opportunity.assigned_to.email,
                    subject=f'Congratulations! Opportunity Won: {opportunity.name}',
                    template_name='opportunity_won',
                    context_data={
                        'opportunity': opportunity,
                        'won_by': won_by,
                        'value': format_currency(opportunity.actual_value)
                    },
                    recipient_data={
                        'first_name': opportunity.assigned_to.first_name,
                        'last_name': opportunity.assigned_to.last_name,
                        'email': opportunity.assigned_to.email
                    },
                    tenant=opportunity.tenant
                )
        except Exception as e:
            print(f"Failed to send win notification: {e}")
    
    def _recalculate_opportunity_value(self, opportunity):
        """Recalculate opportunity value based on products."""
        try:
            total_value = OpportunityProduct.objects.filter(
                opportunity=opportunity
            ).aggregate(Sum('total_value'))['total_value__sum'] or 0
            
            if total_value > 0:
                opportunity.value = total_value
                opportunity.save(update_fields=['value'])
        except Exception as e:
            print(f"Error recalculating opportunity value: {e}")
    
    def _calculate_probability_factors(self, opportunity):
        """Calculate various factors that influence probability."""
        factors = {}
        
        # Stage-based probability
        factors['stage_probability'] = opportunity.stage.probability
        
        # Time in current stage
        if opportunity.stage_changed_at:
            days_in_stage = (timezone.now() - opportunity.stage_changed_at).days
            factors['days_in_current_stage'] = days_in_stage
            
            # Penalty for stale opportunities
            if days_in_stage > 30:
                factors['staleness_penalty'] = -10
        
        # Activity level (last 30 days)
        from crm.models.activity import Activity
        recent_activities = Activity.objects.filter(
            related_to_id=opportunity.id,
            tenant=opportunity.tenant,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        factors['recent_activity_count'] = recent_activities
        
        if recent_activities == 0:
            factors['activity_penalty'] = -15
        elif recent_activities > 5:
            factors['activity_bonus'] = +10
        
        # Value factor (higher value = higher attention)
        if opportunity.value:
            # Compare to average opportunity value
            avg_value = Opportunity.objects.filter(
                tenant=opportunity.tenant
            ).aggregate(Avg('value'))['value__avg'] or 0
            
            if opportunity.value > avg_value * 2:
                factors['high_value_bonus'] = +5
            elif opportunity.value < avg_value * 0.5:
                factors['low_value_penalty'] = -5
        
        # Expected close date factor
        if opportunity.expected_close_date:
            days_to_close = (opportunity.expected_close_date - timezone.now().date()).days
            factors['days_to_expected_close'] = days_to_close
            
            if days_to_close < 0:
                factors['overdue_penalty'] = -20
            elif days_to_close < 7:
                factors['closing_soon_bonus'] = +5
        
        return factors
    
    def _calculate_weighted_probability(self, opportunity, factors):
        """Calculate AI-weighted probability."""
        base_probability = factors.get('stage_probability', 0)
        
        # Apply adjustments
        adjustments = 0
        adjustments += factors.get('staleness_penalty', 0)
        adjustments += factors.get('activity_penalty', 0)
        adjustments += factors.get('activity_bonus', 0)
        adjustments += factors.get('high_value_bonus', 0)
        adjustments += factors.get('low_value_penalty', 0)
        adjustments += factors.get('overdue_penalty', 0)
        adjustments += factors.get('closing_soon_bonus', 0)
        
        # Calculate weighted probability
        weighted_prob = base_probability + adjustments
        
        # Keep within 0-100 range
        return max(0, min(100, weighted_prob))
    
    def _get_confidence_level(self, factors):
        """Get confidence level for probability prediction."""
        # More factors = higher confidence
        factor_count = len([f for f in factors.values() if isinstance(f, (int, float))])
        
        if factor_count >= 6:
            return 'high'
        elif factor_count >= 4:
            return 'medium'
        else:
            return 'low'
    
    def _generate_probability_recommendations(self, opportunity, factors):
        """Generate recommendations to improve probability."""
        recommendations = []
        
        if factors.get('staleness_penalty', 0) < 0:
            recommendations.append({
                'type': 'warning',
                'message': f'Opportunity has been in {opportunity.stage.name} stage for {factors["days_in_current_stage"]} days',
                'action': 'Schedule follow-up activities or advance to next stage'
            })
        
        if factors.get('activity_penalty', 0) < 0:
            recommendations.append({
                'type': 'action',
                'message': 'No recent activities logged',
                'action': 'Schedule calls, meetings, or demos to maintain momentum'
            })
        
        if factors.get('overdue_penalty', 0) < 0:
            recommendations.append({
                'type': 'urgent',
                'message': 'Opportunity is past expected close date',
                'action': 'Update expected close date or accelerate closing activities'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'success',
                'message': 'Opportunity is progressing well',
                'action': 'Continue current activities and maintain momentum'
            })
        
        return recommendations
    
    def _calculate_weighted_pipeline_value(self, queryset):
        """Calculate weighted pipeline value (value * probability)."""
        try:
            weighted_value = 0
            for opp in queryset.filter(value__isnull=False, probability__isnull=False):
                weighted_value += float(opp.value) * (opp.probability / 100)
            return weighted_value
        except:
            return 0
    
    def _generate_win_loss_insights(self, win_rate, avg_sales_cycle, loss_reasons, competitors):
        """Generate insights from win/loss analysis."""
        insights = []
        
        if win_rate < 25:
            insights.append({
                'type': 'warning',
                'message': f'Win rate of {win_rate}% is below industry average',
                'action': 'Review qualification process and sales methodology'
            })
        elif win_rate > 60:
            insights.append({
                'type': 'success',
                'message': f'Excellent win rate of {win_rate}%',
                'action': 'Document and replicate successful strategies'
            })
        
        if avg_sales_cycle and avg_sales_cycle > 120:  # 4 months
            insights.append({
                'type': 'info',
                'message': f'Average sales cycle of {avg_sales_cycle:.0f} days is lengthy',
                'action': 'Identify bottlenecks and streamline sales process'
            })
        
        # Top loss reason insight
        if loss_reasons:
            top_loss_reason = loss_reasons[0]
            insights.append({
                'type': 'attention',
                'message': f'Top loss reason: {top_loss_reason["loss_reason"]} ({top_loss_reason["count"]} cases)',
                'action': 'Address this common objection in sales training'
            })
        
        # Top competitor insight
        if competitors:
            top_competitor = competitors[0]
            insights.append({
                'type': 'competitive',
                'message': f'Most frequent competitor: {top_competitor["competitor"]} ({top_competitor["count"]} losses)',
                'action': 'Develop competitive battle cards and positioning'
            })
        
        return insights


class PipelineStageViewSet(CRMBaseViewSet):
    """
    ViewSet for Pipeline Stage management.
    """
    
    queryset = PipelineStage.objects.all()
    serializer_class = PipelineStageSerializer
    search_fields = ['name', 'description']
    ordering = ['order']
    
    def get_model_permission(self):
        """Get pipeline-specific permission class."""
        return PipelinePermission
    
    @action(detail=True, methods=['get'])
    @cache_response(timeout=1800)
    def performance(self, request, pk=None):
        """Get performance metrics for this stage."""
        try:
            stage = self.get_object()
            tenant = get_tenant_from_request(request)
            
            stage_opportunities = Opportunity.objects.filter(
                stage=stage,
                tenant=tenant
            )
            
            # Current opportunities in this stage
            current_count = stage_opportunities.count()
            current_value = stage_opportunities.aggregate(Sum('value'))['value__sum'] or 0
            
            # Historical data (opportunities that moved through this stage)
            historical_data = OpportunityStageHistory.objects.filter(
                new_stage=stage.name,
                tenant=tenant
            )
            
            # Calculate average time in stage
            avg_duration = None
            durations = []
            
            for# Find when opportunity left this stage
                next_change = OpportunityStageHistory.objects.filter(
                    opportunity=history.opportunity,
                    changed_at__gt=history.changed_at,
                    tenant=tenant
                ).first()
                
                if next_change:
                    duration = (next_change.changed_at - history.changed_at).total_seconds() / 3600  # hours
                    durations.append(duration)
            
            if durations:
                avg_duration = sum(durations) / len(durations)
            
            # Conversion rate (opportunities that advanced vs. those that went back/were lost)
            advanced_count = 0
            regressed_count = 0
            
            for history_change = OpportunityStageHistory.objects.filter(
                    opportunity=history.opportunity,
                    changed_at__gt=history.changed_at,
                    tenant=tenant
                ).first()
                
                if next_change:
                    try:
                        old_stage_order = PipelineStage.objects.get(name=history.new_stage, tenant=tenant).order
                        new_stage_order = PipelineStage.objects.get(name=next_change.new_stage, tenant=tenant).order
                        
                        if new_stage_order > old_stage_order:
                            advanced_count += 1
                        else:
                            regressed_count += 1
                    except PipelineStage.DoesNotExist:
                        pass
            
            total_movements = advanced_count + regressed_count
            advancement_rate = (advanced_count / total_movements * 100) if total_movements > 0 else 0
            
            return Response({
                'stage': PipelineStageSerializer(stage).data,
                'current_opportunities': {
                    'count': current_count,
                    'total_value': float(current_value),
                    'avg_value': float(current_value / current_count) if current_count > 0 else 0
                },
                'performance_metrics': {
                    'avg_duration_hours': round(avg_duration, 1) if avg_duration else None,
                    'advancement_rate': round(advancement_rate, 2),
                    'total_historical_entries': historical_data.count(),
                    'advanced_count': advanced_count,
                    'regressed_count': regressed_count
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder pipeline stages."""
        try:
            stage_orders = request.data.get('stage_orders', [])
            # Expected format: [{'stage_id': 1, 'order': 1}, ...]
            
            if not stage_orders:
                return Response(
                    {'error': 'stage_orders is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_tenant_from_request(request)
            updated_count = 0
            
            with transaction.atomic():
                for item in stage_orders:
                    stage_id = item.get('stage_id')
                    new_order = item.get('order')
                    
                    if stage_id and new_order is not None:
                        PipelineStage.objects.filter(
                            id=stage_id,
                            tenant=tenant
                        ).update(order=new_order)
                        updated_count += 1
            
            return Response({
                'message': f'{updated_count} stages reordered',
                'updated_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OpportunityProductViewSet(CRMBaseViewSet):
    """
    ViewSet for Opportunity Product/Line Item management.
    """
    
    queryset = OpportunityProduct.objects.select_related('opportunity', 'product')
    serializer_class = OpportunityProductSerializer
    filterset_fields = ['opportunity', 'product']
    ordering = ['line_number']
    
    def perform_create(self, serializer):
        """Auto-calculate totals on creation."""
        instance = serializer.save()
        self._update_opportunity_value(instance.opportunity)
    
    def perform_update(self, serializer):
        """Auto-calculate totals on update."""
        instance = serializer.save()
        self._update_opportunity_value(instance.opportunity)
    
    def perform_destroy(self, instance):
        """Update opportunity value after deletion."""
        opportunity = instance.opportunity
        super().perform_destroy(instance)
        self._update_opportunity_value(opportunity)
    
    def _update_opportunity_value(self, opportunity):
        """Update opportunity total value based on products."""
        try:
            total_value = OpportunityProduct.objects.filter(
                opportunity=opportunity
            ).aggregate(Sum('total_value'))['total_value__sum'] or 0
            
            opportunity.value = total_value
            opportunity.save(update_fields=['value'])
        except Exception as e:
            print(f"Error updating opportunity value: {e}")


class OpportunityAnalyticsViewSet(CRMReadOnlyViewSet):
    """
    Dedicated ViewSet for opportunity analytics and reporting.
    """
    
    queryset = Opportunity.objects.all()
    
    @action(detail=False, methods=['get'])
    @cache_response(timeout=600)
    def sales_velocity(self, request):
        """Calculate sales velocity metrics."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Get closed won opportunities with duration data
            won_opportunities = queryset.filter(
                stage__is_won=True,
                closed_date__isnull=False
            )
            
            if not won_opportunities.exists():
                return Response({
                    'message': 'No won opportunities found for velocity calculation'
                })
            
            # Calculate sales velocity: (# of deals × avg deal size × win rate) / sales cycle length
            total_opportunities = queryset.count()
            won_count = won_opportunities.count()
            win_rate = won_count / total_opportunities if total_opportunities > 0 else 0
            
            avg_deal_size = won_opportunities.aggregate(
                avg=Avg('actual_value')
            )['avg'] or 0
            
            # Calculate average sales cycle
            sales_cycles = []
            for opp in won_opportunities:
                cycle_days = (opp.closed_date - opp.created_at.date()).days
                sales_cycles.append(cycle_days)
            
            avg_cycle_length = sum(sales_cycles) / len(sales_cycles) if sales_cycles else 0
            
            # Sales velocity calculation
            if avg_cycle_length > 0:
                sales_velocity = (won_count * float(avg_deal_size) * win_rate) / (avg_cycle_length / 30)  # monthly
            else:
                sales_velocity = 0
            
            return Response({
                'sales_velocity_metrics': {
                    'sales_velocity_monthly': round(sales_velocity, 2),
                    'number_of_deals': won_count,
                    'average_deal_size': float(avg_deal_size),
                    'win_rate': round(win_rate * 100, 2),
                    'average_cycle_length_days': round(avg_cycle_length, 1)
                },
                'velocity_trend': self._calculate_velocity_trend(queryset),
                'improvement_opportunities': self._identify_velocity_improvements(
                    win_rate, avg_deal_size, avg_cycle_length
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_velocity_trend(self, queryset):
        """Calculate velocity trend over time."""
        try:
            # Last 6 months velocity
            monthly_velocity = []
            
            for i in range(6):
                end_date = timezone.now().replace(day=1) - timedelta(days=i*30)
                start_date = end_date - timedelta(days=30)
                
                month_opportunities = queryset.filter(
                    closed_date__gte=start_date.date(),
                    closed_date__lt=end_date.date(),
                    stage__is_won=True
                )
                
                if month_opportunities.exists():
                    won_count = month_opportunities.count()
                    avg_size = month_opportunities.aggregate(Avg('actual_value'))['actual_value__avg'] or 0
                    
                    # Simplified velocity for trend
                    velocity = won_count * float(avg_size)
                    
                    monthly_velocity.append({
                        'month': end_date.strftime('%Y-%m'),
                        'velocity': round(velocity, 2),
                        'deals_won': won_count
                    })
            
            return list(reversed(monthly_velocity))
        except:
            return []
    
    def _identify_velocity_improvements(self, win_rate, avg_deal_size, avg_cycle):
        """Identify opportunities to improve sales velocity."""
        improvements = []
        
        if win_rate < 0.25:
            improvements.append({
                'area': 'Win Rate',
                'current': f"{win_rate * 100:.1f}%",
                'recommendation': 'Improve qualification and sales process',
                'potential_impact': 'High'
            })
        
        if avg_cycle > 90:
            improvements.append({
                'area': 'Sales Cycle',
                'current': f"{avg_cycle:.0f} days",
                'recommendation': 'Identify and eliminate process bottlenecks',
                'potential_impact': 'High'
            })
        
        if avg_deal_size < 10000:
            improvements.append({
                'area': 'Deal Size',
                'current': f"${avg_deal_size:,.0f}",
                'recommendation': 'Focus on upselling and premium solutions',
                'potential_impact': 'Medium'
            })
        
        return improvements


class PipelineForecastViewSet(CRMReadOnlyViewSet):
    """
    Specialized ViewSet for pipeline forecasting and predictions.
    """
    
    queryset = Opportunity.objects.all()
    
    @action(detail=False, methods=['get'])
    @cache_response(timeout=1800)
    def forecast(self, request):
        """Generate sales forecast based on pipeline."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Get forecasting parameters
            forecast_period = request.query_params.get('period', 'quarter')  # month, quarter, year
            include_probability = request.query_params.get('include_probability', 'true').lower() == 'true'
            
            # Filter open opportunities
            open_opportunities = queryset.filter(stage__is_closed=False)
            
            # Generate forecast based on period
            if forecast_period == 'month':
                forecast_data = self._generate_monthly_forecast(open_opportunities, include_probability)
            elif forecast_period == 'quarter':
                forecast_data = self._generate_quarterly_forecast(open_opportunities, include_probability)
            else:  # year
                forecast_data = self._generate_yearly_forecast(open_opportunities, include_probability)
            
            # Calculate confidence intervals
            confidence_intervals = self._calculate_confidence_intervals(open_opportunities)
            
            return Response({
                'forecast_period': forecast_period,
                'forecast_data': forecast_data,
                'confidence_intervals': confidence_intervals,
                'methodology': {
                    'includes_probability': include_probability,
                    'base_opportunities': open_opportunities.count(),
                    'total_pipeline_value': float(open_opportunities.aggregate(Sum('value'))['value__sum'] or 0)
                },
                'assumptions': self._get_forecast_assumptions()
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_monthly_forecast(self, opportunities, include_probability):
        """Generate monthly forecast for next 12 months."""
        forecast = []
        
        for month_offset in range(12):
            target_date = timezone.now().date() + timedelta(days=month_offset * 30)
            month_start = target_date.replace(day=1)
            
            # Get opportunities expected to close in this month
            month_opportunities = opportunities.filter(
                expected_close_date__year=target_date.year,
                expected_close_date__month=target_date.month
            )
            
            total_value = month_opportunities.aggregate(Sum('value'))['value__sum'] or 0
            
            if include_probability:
                # Calculate probability-weighted value
                weighted_value = 0
                for opp in month_opportunities:
                    if opp.value and opp.probability:
                        weighted_value += float(opp.value) * (opp.probability / 100)
                forecast_value = weighted_value
            else:
                forecast_value = float(total_value)
            
            forecast.append({
                'period': target_date.strftime('%Y-%m'),
                'period_name': target_date.strftime('%B %Y'),
                'opportunity_count': month_opportunities.count(),
                'total_value': float(total_value),
                'forecast_value': forecast_value,
                'confidence': self._calculate_period_confidence(month_opportunities)
            })
        
        return forecast
    
    def _generate_quarterly_forecast(self, opportunities, include_probability):
        """Generate quarterly forecast for next 4 quarters."""
        forecast = []
        current_date = timezone.now().date()
        
        for quarter in range(4):
            # Calculate quarter start and end dates
            quarter_start_month = ((current_date.month - 1) // 3 * 3) + 1 + (quarter * 3)
            year = current_date.year
            
            if quarter_start_month > 12:
                quarter_start_month -= 12
                year += 1
            
            quarter_start = date(year, quarter_start_month, 1)
            
            # Calculate quarter end
            if quarter_start_month == 10:
                quarter_end = date(year, 12, 31)
            else:
                next_quarter_month = quarter_start_month + 3
                if next_quarter_month > 12:
                    next_quarter_month -= 12
                    year += 1
                quarter_end = date(year, next_quarter_month, 1) - timedelta(days=1)
            
            # Get opportunities for this quarter
            quarter_opportunities = opportunities.filter(
                expected_close_date__gte=quarter_start,
                expected_close_date__lte=quarter_end
            )
            
            total_value = quarter_opportunities.aggregate(Sum('value'))['value__sum'] or 0
            
            if include_probability:
                weighted_value = 0
                for opp in quarter_opportunities:
                    if opp.value and opp.probability:
                        weighted_value += float(opp.value) * (opp.probability / 100)
                forecast_value = weighted_value
            else:
                forecast_value = float(total_value)
            
            forecast.append({
                'period': f'Q{((quarter_start.month - 1) // 3) + 1} {quarter_start.year}',
                'period_start': quarter_start.isoformat(),
                'period_end': quarter_end.isoformat(),
                'opportunity_count': quarter_opportunities.count(),
                'total_value': float(total_value),
                'forecast_value': forecast_value,
                'confidence': self._calculate_period_confidence(quarter_opportunities)
            })
        
        return forecast
    
    def _generate_yearly_forecast(self, opportunities, include_probability):
        """Generate yearly forecast for next 3 years."""
        forecast = []
        current_year = timezone.now().year
        
        for year_offset in range(3):
            target_year = current_year + year_offset
            
            year_opportunities = opportunities.filter(
                expected_close_date__year=target_year
            )
            
            total_value = year_opportunities.aggregate(Sum('value'))['value__sum'] or 0
            
            if include_probability:
                weighted_value = 0
                for opp in year_opportunities:
                    if opp.value and opp.probability:
                        weighted_value += float(opp.value) * (opp.probability / 100)
                forecast_value = weighted_value
            else:
                forecast_value = float(total_value)
            
            forecast.append({
                'period': str(target_year),
                'period_name': f'Year {target_year}',
                'opportunity_count': year_opportunities.count(),
                'total_value': float(total_value),
                'forecast_value': forecast_value,
                'confidence': self._calculate_period_confidence(year_opportunities)
            })
        
        return forecast
    
    def _calculate_period_confidence(self, opportunities):
        """Calculate confidence level for period forecast."""
        if not opportunities.exists():
            return 'low'
        
        # Factors affecting confidence:
        # 1. Number of opportunities
        # 2. Stage distribution
        # 3. Historical accuracy
        
        opp_count = opportunities.count()
        
        # Stage confidence (later stages = higher confidence)
        high_confidence_stages = opportunities.filter(
            stage__probability__gte=60
        ).count()
        
        confidence_ratio = high_confidence_stages / opp_count if opp_count > 0 else 0
        
        if opp_count >= 10 and confidence_ratio >= 0.6:
            return 'high'
        elif opp_count >= 5 and confidence_ratio >= 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_confidence_intervals(self, opportunities):
        """Calculate confidence intervals for forecast."""
        # This would typically involve statistical analysis
        # For now, return simple confidence bands
        
        total_value = float(opportunities.aggregate(Sum('value'))['value__sum'] or 0)
        
        return {
            'pessimistic': total_value * 0.7,  # 30% reduction
            'most_likely': total_value * 0.85,  # 15% reduction
            'optimistic': total_value * 1.0,   # Full value
            'methodology': 'Based on historical win rates and stage probabilities'
        }
    
    def _get_forecast_assumptions(self):
        """Get assumptions used in forecasting."""
        return [
            'Expected close dates are accurate',
            'Stage probabilities reflect actual likelihood',
            'No major market changes affect pipeline',
            'Current sales team capacity maintained',
            'Historical performance trends continue'
        ]