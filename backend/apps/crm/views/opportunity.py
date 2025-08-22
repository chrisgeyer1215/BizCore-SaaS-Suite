# ============================================================================
# backend/apps/crm/views/opportunity.py - Opportunity Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, Case, When
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
import json
from datetime import datetime, timedelta

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import (
    Opportunity, Pipeline, PipelineStage, Account, Contact, 
    OpportunityTeamMember, OpportunityProduct, Product, Territory
)
from ..serializers import (
    OpportunitySerializer, OpportunityDetailSerializer, PipelineSerializer,
    PipelineStageSerializer, OpportunityProductSerializer
)
from ..filters import OpportunityFilter
from ..permissions import OpportunityPermission
from ..services import OpportunityService, ForecastService


class PipelineManagementView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Pipeline management and configuration"""
    
    permission_required = 'crm.manage_pipeline'
    
    def get(self, request):
        pipelines = Pipeline.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).prefetch_related('stages').annotate(
            opportunities_count=Count('opportunities'),
            total_value=Sum('opportunities__amount'),
            avg_deal_size=Avg('opportunities__amount')
        ).order_by('-is_default', 'name')
        
        # Pipeline performance
        pipeline_performance = []
        for pipeline in pipelines:
            stages_data = []
            for stage in pipeline.stages.filter(is_active=True).order_by('sort_order'):
                stage_opps = stage.opportunities.filter(is_active=True, is_closed=False)
                stages_data.append({
                    'stage': stage,
                    'count': stage_opps.count(),
                    'value': stage_opps.aggregate(Sum('amount'))['amount__sum'] or 0,
                    'avg_time': stage.average_time_in_stage or 0,
                    'conversion_rate': stage.conversion_rate
                })
            
            pipeline_performance.append({
                'pipeline': pipeline,
                'stages': stages_data,
                'win_rate': pipeline.win_rate,
                'avg_sales_cycle': pipeline.average_sales_cycle
            })
        
        context = {
            'pipelines': pipelines,
            'pipeline_performance': pipeline_performance,
            'total_pipeline_value': pipelines.aggregate(Sum('total_value'))['total_value__sum'] or 0,
        }
        
        return render(request, 'crm/opportunity/pipeline_management.html', context)
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'create_pipeline':
            return self.create_pipeline(request)
        elif action == 'update_pipeline':
            return self.update_pipeline(request)
        elif action == 'create_stage':
            return self.create_stage(request)
        elif action == 'update_stage':
            return self.update_stage(request)
        elif action == 'reorder_stages':
            return self.reorder_stages(request)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def create_pipeline(self, request):
        """Create new pipeline"""
        try:
            pipeline = Pipeline.objects.create(
                tenant=request.tenant,
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                pipeline_type=request.POST.get('pipeline_type', 'SALES'),
                created_by=request.user
            )
            
            # Create default stages
            default_stages = [
                {'name': 'Prospecting', 'probability': 10, 'sort_order': 1},
                {'name': 'Qualification', 'probability': 25, 'sort_order': 2},
                {'name': 'Proposal', 'probability': 50, 'sort_order': 3},
                {'name': 'Negotiation', 'probability': 75, 'sort_order': 4},
                {'name': 'Closed Won', 'probability': 100, 'sort_order': 5, 'is_won': True, 'is_closed': True},
                {'name': 'Closed Lost', 'probability': 0, 'sort_order': 6, 'is_closed': True, 'stage_type': 'LOST'},
            ]
            
            for stage_data in default_stages:
                PipelineStage.objects.create(
                    tenant=request.tenant,
                    pipeline=pipeline,
                    created_by=request.user,
                    **stage_data
                )
            
            return JsonResponse({
                'success': True,
                'message': f'Pipeline "{pipeline.name}" created successfully',
                'pipeline_id': pipeline.id
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def create_stage(self, request):
        """Create new pipeline stage"""
        try:
            pipeline_id = request.POST.get('pipeline_id')
            pipeline = get_object_or_404(Pipeline, id=pipeline_id, tenant=request.tenant)
            
            # Get next sort order
            max_order = pipeline.stages.aggregate(Max('sort_order'))['sort_order__max'] or 0
            
            stage = PipelineStage.objects.create(
                tenant=request.tenant,
                pipeline=pipeline,
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                probability=float(request.POST.get('probability', 0)),
                sort_order=max_order + 1,
                stage_type=request.POST.get('stage_type', 'OPEN'),
                is_won=request.POST.get('is_won') == 'true',
                is_closed=request.POST.get('is_closed') == 'true',
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Stage "{stage.name}" created successfully',
                'stage_id': stage.id
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def reorder_stages(self, request):
        """Reorder pipeline stages"""
        try:
            stage_orders = json.loads(request.POST.get('stage_orders', '[]'))
            
            for item in stage_orders:
                PipelineStage.objects.filter(
                    id=item['stage_id'],
                    tenant=request.tenant
                ).update(sort_order=item['order'])
            
            return JsonResponse({
                'success': True,
                'message': 'Stage order updated successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class OpportunityListView(CRMBaseMixin, ListView):
    """Enhanced opportunity listing with pipeline view"""
    
    model = Opportunity
    template_name = 'crm/opportunity/list.html'
    context_object_name = 'opportunities'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Opportunity.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'account', 'primary_contact', 'pipeline', 'stage', 
            'owner', 'territory', 'campaign'
        ).prefetch_related(
            'products', 'team_members'
        ).annotate(
            products_count=Count('products'),
            team_size=Count('team_members'),
            days_in_stage=Case(
                When(stage_changed_date__isnull=True, then=F('days_in_pipeline')),
                default=timezone.now() - F('stage_changed_date')
            )
        )
        
        # Apply filters
        opp_filter = OpportunityFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_opportunities'):
            opp_filter.qs = opp_filter.qs.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        # View type ordering
        view_type = self.request.GET.get('view', 'list')
        if view_type == 'pipeline':
            return opp_filter.qs.order_by('pipeline__name', 'stage__sort_order', '-amount')
        else:
            return opp_filter.qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = OpportunityFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # View type
        context['view_type'] = self.request.GET.get('view', 'list')
        
        # Opportunity statistics
        queryset = self.get_queryset()
        context['stats'] = self.get_opportunity_stats(queryset)
        
        # Pipeline view data
        if context['view_type'] == 'pipeline':
            context['pipeline_data'] = self.get_pipeline_view_data(queryset)
        
        # Sales forecast
        context['forecast_summary'] = self.get_forecast_summary(queryset)
        
        # Quick filters
        context['quick_filters'] = self.get_quick_filters()
        
        return context
    
    def get_opportunity_stats(self, queryset):
        """Get opportunity statistics"""
        total_opportunities = queryset.count()
        open_opportunities = queryset.filter(is_closed=False)
        
        stats = {
            'total_count': total_opportunities,
            'open_count': open_opportunities.count(),
            'won_count': queryset.filter(is_won=True).count(),
            'lost_count': queryset.filter(is_closed=True, is_won=False).count(),
            'total_value': queryset.aggregate(Sum('amount'))['amount__sum'] or 0,
            'weighted_value': queryset.aggregate(
                weighted=Sum(F('amount') * F('probability') / 100)
            )['weighted'] or 0,
            'average_deal_size': queryset.aggregate(Avg('amount'))['amount__avg'] or 0,
            'average_probability': open_opportunities.aggregate(Avg('probability'))['probability__avg'] or 0,
        }
        
        # Win rate calculation
        closed_opportunities = queryset.filter(is_closed=True).count()
        if closed_opportunities > 0:
            stats['win_rate'] = (stats['won_count'] / closed_opportunities) * 100
        else:
            stats['win_rate'] = 0
        
        # By stage distribution
        stats['by_stage'] = list(
            open_opportunities.values('stage__name').annotate(
                count=Count('id'),
                value=Sum('amount'),
                avg_probability=Avg('probability')
            ).order_by('stage__sort_order')
        )
        
        # By owner distribution
        stats['by_owner'] = list(
            queryset.filter(owner__isnull=False).values(
                'owner__first_name', 'owner__last_name'
            ).annotate(
                count=Count('id'),
                value=Sum('amount')
            ).order_by('-value')[:10]
        )
        
        return stats
    
    def get_pipeline_view_data(self, queryset):
        """Get data for pipeline view"""
        pipeline_data = []
        
        # Get all active pipelines
        pipelines = Pipeline.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).prefetch_related('stages').order_by('-is_default', 'name')
        
        for pipeline in pipelines:
            stages_data = []
            pipeline_opportunities = queryset.filter(pipeline=pipeline)
            
            for stage in pipeline.stages.filter(is_active=True).order_by('sort_order'):
                stage_opportunities = pipeline_opportunities.filter(stage=stage)
                
                stages_data.append({
                    'stage': stage,
                    'opportunities': stage_opportunities,
                    'count': stage_opportunities.count(),
                    'total_value': stage_opportunities.aggregate(Sum('amount'))['amount__sum'] or 0,
                    'weighted_value': stage_opportunities.aggregate(
                        weighted=Sum(F('amount') * F('probability') / 100)
                    )['weighted'] or 0,
                    'avg_probability': stage_opportunities.aggregate(Avg('probability'))['probability__avg'] or 0,
                })
            
            pipeline_data.append({
                'pipeline': pipeline,
                'stages': stages_data,
                'total_opportunities': pipeline_opportunities.count(),
                'total_value': pipeline_opportunities.aggregate(Sum('amount'))['amount__sum'] or 0,
            })
        
        return pipeline_data
    
    def get_forecast_summary(self, queryset):
        """Get sales forecast summary"""
        today = timezone.now().date()
        
        # Current quarter
        current_quarter_start = today.replace(month=((today.month-1)//3)*3+1, day=1)
        next_quarter_start = (current_quarter_start + timedelta(days=92)).replace(day=1)
        
        current_quarter_opps = queryset.filter(
            close_date__gte=current_quarter_start,
            close_date__lt=next_quarter_start,
            is_closed=False
        )
        
        forecast = {
            'current_quarter': {
                'count': current_quarter_opps.count(),
                'total_value': current_quarter_opps.aggregate(Sum('amount'))['amount__sum'] or 0,
                'weighted_value': current_quarter_opps.aggregate(
                    weighted=Sum(F('amount') * F('probability') / 100)
                )['weighted'] or 0,
            }
        }
        
        # Best case vs worst case
        high_probability_opps = current_quarter_opps.filter(probability__gte=75)
        forecast['best_case'] = high_probability_opps.aggregate(Sum('amount'))['amount__sum'] or 0
        
        medium_probability_opps = current_quarter_opps.filter(probability__gte=50)
        forecast['likely_case'] = medium_probability_opps.aggregate(Sum('amount'))['amount__sum'] or 0
        
        return forecast
    
    def get_quick_filters(self):
        """Get quick filter options"""
        return [
            {'name': 'My Opportunities', 'filter': 'owner=me'},
            {'name': 'High Value', 'filter': 'amount__gte=100000'},
            {'name': 'Closing This Month', 'filter': 'closing_this_month=true'},
            {'name': 'High Probability', 'filter': 'probability__gte=75'},
            {'name': 'Overdue', 'filter': 'overdue=true'},
            {'name': 'New This Week', 'filter': 'created_this_week=true'},
        ]


class OpportunityDetailView(CRMBaseMixin, DetailView):
    """Comprehensive opportunity detail view"""
    
    model = Opportunity
    template_name = 'crm/opportunity/detail.html'
    context_object_name = 'opportunity'
    
    def get_queryset(self):
        return Opportunity.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'account', 'primary_contact', 'pipeline', 'stage', 
            'owner', 'territory', 'campaign', 'original_lead'
        ).prefetch_related(
            'products__product',
            'team_memberships__user',
            'activities__activity_type',
            'activities__assigned_to'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opportunity = self.get_object()
        
        # Products and pricing
        context['products'] = opportunity.products.filter(is_active=True).select_related('product')
        context['products_total'] = context['products'].aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        # Team members
        context['team_members'] = opportunity.team_memberships.filter(
            is_active=True
        ).select_related('user', 'user__crm_profile')
        
        # Activities
        context['recent_activities'] = opportunity.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')[:10]
        
        context['activity_stats'] = {
            'total_activities': opportunity.activities.filter(is_active=True).count(),
            'completed_activities': opportunity.activities.filter(
                is_active=True, status='COMPLETED'
            ).count(),
            'overdue_activities': opportunity.activities.filter(
                is_active=True, 
                status__in=['PLANNED', 'IN_PROGRESS'],
                end_datetime__lt=timezone.now()
            ).count(),
        }
        
        # Stage progression
        context['stage_history'] = opportunity.stage_history or []
        context['days_in_current_stage'] = self.get_days_in_current_stage(opportunity)
        context['stage_progression'] = self.get_stage_progression(opportunity)
        
        # Competition analysis
        context['competitors'] = opportunity.competitors or []
        
        # Probability insights
        context['probability_insights'] = self.get_probability_insights(opportunity)
        
        # Similar opportunities
        context['similar_opportunities'] = self.get_similar_opportunities(opportunity)
        
        # Financial summary
        context['financial_summary'] = self.get_financial_summary(opportunity)
        
        # Next actions
        context['suggested_actions'] = self.get_suggested_actions(opportunity)
        
        # Documents and attachments
        context['documents'] = self.get_related_documents(opportunity)
        
        return context
    
    def get_days_in_current_stage(self, opportunity):
        """Calculate days in current stage"""
        stage_changed_date = opportunity.stage_changed_date
        if stage_changed_date:
            return (timezone.now() - stage_changed_date).days
        return opportunity.days_in_pipeline
    
    def get_stage_progression(self, opportunity):
        """Get stage progression data"""
        pipeline_stages = opportunity.pipeline.stages.filter(
            is_active=True
        ).order_by('sort_order')
        
        progression = []
        current_stage_reached = False
        
        for stage in pipeline_stages:
            is_current = (stage == opportunity.stage)
            is_completed = stage.sort_order < opportunity.stage.sort_order
            
            progression.append({
                'stage': stage,
                'is_current': is_current,
                'is_completed': is_completed,
                'is_future': not is_current and not is_completed,
            })
            
            if is_current:
                current_stage_reached = True
        
        return progression
    
    def get_probability_insights(self, opportunity):
        """Get probability insights and recommendations"""
        stage_probability = opportunity.stage.probability if opportunity.stage else 0
        current_probability = opportunity.probability
        
        insights = {
            'stage_probability': stage_probability,
            'current_probability': current_probability,
            'variance': current_probability - stage_probability,
            'recommendation': '',
            'factors': []
        }
        
        # Analyze probability factors
        if insights['variance'] > 10:
            insights['recommendation'] = 'Opportunity probability is higher than typical for this stage'
            insights['factors'].append('Strong customer engagement')
        elif insights['variance'] < -10:
            insights['recommendation'] = 'Opportunity probability is lower than typical for this stage'
            insights['factors'].append('May need additional qualification')
        
        # Check for risk factors
        if opportunity.close_date < timezone.now().date():
            insights['factors'].append('Past due close date')
        
        if not opportunity.primary_contact:
            insights['factors'].append('No primary contact assigned')
        
        if not opportunity.products.exists():
            insights['factors'].append('No products/services defined')
        
        return insights
    
    def get_similar_opportunities(self, opportunity):
        """Find similar opportunities"""
        similar = Opportunity.objects.filter(
            tenant=self.request.tenant,
            is_active=True,
            account=opportunity.account
        ).exclude(id=opportunity.id).select_related(
            'stage', 'owner'
        ).order_by('-created_at')[:5]
        
        return similar
    
    def get_financial_summary(self, opportunity):
        """Get financial summary"""
        products = opportunity.products.filter(is_active=True)
        
        summary = {
            'base_amount': products.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0,
            'discount_amount': products.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0,
            'total_amount': products.aggregate(Sum('total_price'))['total_price__sum'] or 0,
            'weighted_amount': (opportunity.amount * opportunity.probability / 100),
            'products_count': products.count(),
            'recurring_revenue': products.filter(
                revenue_type='RECURRING'
            ).aggregate(Sum('total_price'))['total_price__sum'] or 0,
        }
        
        # Calculate margins if cost data available
        total_cost = products.aggregate(
            total=Sum(F('quantity') * F('unit_price') * 0.6)  # Assuming 60% cost ratio
        )['total'] or 0
        
        if total_cost > 0:
            summary['estimated_cost'] = total_cost
            summary['estimated_margin'] = summary['total_amount'] - total_cost
            summary['margin_percentage'] = (summary['estimated_margin'] / summary['total_amount']) * 100
        
        return summary
    
    def get_suggested_actions(self, opportunity):
        """Get suggested next actions"""
        actions = []
        
        # Based on stage
        if opportunity.stage and opportunity.stage.name.lower() == 'prospecting':
            actions.append({
                'type': 'qualify',
                'title': 'Qualify Opportunity',
                'description': 'Conduct discovery call to understand needs',
                'priority': 'high'
            })
        
        # Based on close date
        days_to_close = (opportunity.close_date - timezone.now().date()).days
        if days_to_close <= 7:
            actions.append({
                'type': 'urgent',
                'title': 'Follow Up Immediately',
                'description': f'Opportunity closes in {days_to_close} days',
                'priority': 'urgent'
            })
        elif days_to_close <= 30:
            actions.append({
                'type': 'follow_up',
                'title': 'Schedule Check-in',
                'description': f'Opportunity closes in {days_to_close} days',
                'priority': 'high'
            })
        
        # Based on probability
        if opportunity.probability < 25 and opportunity.stage.probability > 25:
            actions.append({
                'type': 'risk',
                'title': 'Address Risk Factors',
                'description': 'Probability below stage average',
                'priority': 'medium'
            })
        
        # Based on missing information
        if not opportunity.primary_contact:
            actions.append({
                'type': 'contact',
                'title': 'Assign Primary Contact',
                'description': 'Add decision maker contact',
                'priority': 'medium'
            })
        
        if not opportunity.products.exists():
            actions.append({
                'type': 'products',
                'title': 'Define Products/Services',
                'description': 'Add products to the opportunity',
                'priority': 'medium'
            })
        
        return actions
    
    def get_related_documents(self, opportunity):
        """Get related documents"""
        from ..models import Document
        
        documents = Document.objects.filter(
            tenant=self.request.tenant,
            content_type=ContentType.objects.get_for_model(Opportunity),
            object_id=str(opportunity.id),
            is_active=True
        ).order_by('-created_at')
        
        return documents


class OpportunityCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new opportunity"""
    
    model = Opportunity
    template_name = 'crm/opportunity/form.html'
    permission_required = 'crm.add_opportunity'
    fields = [
        'name', 'description', 'opportunity_type', 'account', 'primary_contact',
        'pipeline', 'stage', 'amount', 'probability', 'close_date',
        'owner', 'lead_source', 'campaign', 'territory', 'competitors',
        'next_step', 'next_step_date', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter choices
        form.fields['account'].queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['pipeline'].queryset = Pipeline.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['territory'].queryset = Territory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Pre-populate from account if specified
        account_id = self.request.GET.get('account_id')
        if account_id:
            try:
                account = Account.objects.get(
                    id=account_id,
                    tenant=self.request.tenant
                )
                form.initial['account'] = account
                form.fields['primary_contact'].queryset = account.contacts.filter(is_active=True)
            except Account.DoesNotExist:
                pass
        
        # Pre-populate from lead conversion
        lead_id = self.request.GET.get('lead_id')
        if lead_id:
            try:
                from ..models import Lead
                lead = Lead.objects.get(
                    id=lead_id,
                    tenant=self.request.tenant
                )
                form.initial.update({
                    'name': f"{lead.company} - {lead.job_title}" if lead.company else f"{lead.full_name} Opportunity",
                    'description': lead.description,
                    'lead_source': lead.source.name if lead.source else '',
                    'campaign': lead.campaign,
                })
            except:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        # Set default pipeline if not specified
        if not form.instance.pipeline:
            default_pipeline = Pipeline.objects.filter(
                tenant=self.request.tenant,
                is_default=True
            ).first()
            form.instance.pipeline = default_pipeline
        
        # Set default stage if not specified
        if not form.instance.stage and form.instance.pipeline:
            first_stage = form.instance.pipeline.stages.filter(
                is_active=True
            ).order_by('sort_order').first()
            form.instance.stage = first_stage
        
        # Calculate expected revenue
        if form.instance.amount and form.instance.probability:
            form.instance.expected_revenue = (
                form.instance.amount * form.instance.probability / 100
            )
        
        with transaction.atomic():
            response = super().form_valid(form)
            
            # Add creator as team member
            OpportunityTeamMember.objects.create(
                tenant=self.request.tenant,
                opportunity=self.object,
                user=self.request.user,
                role='OWNER',
                can_edit=True,
                can_view_financials=True,
                created_by=self.request.user
            )
            
            # Log creation activity
            self.log_opportunity_creation()
        
        messages.success(
            self.request,
            f'Opportunity "{form.instance.name}" created successfully.'
        )
        
        return response
    
    def log_opportunity_creation(self):
        """Log opportunity creation activity"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Opportunity Created',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Opportunity "{self.object.name}" created',
            description=f'New opportunity worth ${self.object.amount:,.2f} created for {self.object.account.name}',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Opportunity),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:opportunity-detail', kwargs={'pk': self.object.pk})


class OpportunityUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update opportunity with stage change tracking"""
    
    model = Opportunity
    template_name = 'crm/opportunity/form.html'
    permission_required = 'crm.change_opportunity'
    fields = [
        'name', 'description', 'opportunity_type', 'account', 'primary_contact',
        'stage', 'amount', 'probability', 'close_date', 'owner',
        'competitors', 'competitive_analysis', 'next_step', 'next_step_date',
        'tags'
    ]
    
    def get_queryset(self):
        return Opportunity.objects.filter(tenant=self.request.tenant)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Track stage changes
        old_stage = None
        if self.object.pk:
            old_opportunity = Opportunity.objects.get(pk=self.object.pk)
            old_stage = old_opportunity.stage
        
        response = super().form_valid(form)
        
        # Handle stage change
        if old_stage and old_stage != form.instance.stage:
            self.handle_stage_change(old_stage, form.instance.stage)
        
        # Recalculate expected revenue
        if form.instance.amount and form.instance.probability:
            form.instance.expected_revenue = (
                form.instance.amount * form.instance.probability / 100
            )
            form.instance.save(update_fields=['expected_revenue'])
        
        messages.success(
            self.request,
            f'Opportunity "{form.instance.name}" updated successfully.'
        )
        
        return response
    
    def handle_stage_change(self, old_stage, new_stage):
        """Handle opportunity stage change"""
        # Update stage history
        stage_history = self.object.stage_history or []
        stage_history.append({
            'from_stage': old_stage.name,
            'to_stage': new_stage.name,
            'changed_date': timezone.now().isoformat(),
            'changed_by': self.request.user.id,
        })
        
        # Update opportunity
        self.object.stage_history = stage_history
        self.object.stage_changed_date = timezone.now()
        
        # If moved to closed won/lost, update close status
        if new_stage.is_closed:
            self.object.is_closed = True
            self.object.closed_date = timezone.now()
            
            if new_stage.is_won:
                self.object.is_won = True
            else:
                self.object.is_won = False
        else:
            self.object.is_closed = False
            self.object.is_won = False
            self.object.closed_date = None
        
        self.object.save()
        
        # Log stage change activity
        self.log_stage_change(old_stage, new_stage)
    
    def log_stage_change(self, old_stage, new_stage):
        """Log stage change activity"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Stage Changed',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Stage changed from {old_stage.name} to {new_stage.name}',
            description=f'Opportunity "{self.object.name}" moved from {old_stage.name} to {new_stage.name}',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Opportunity),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:opportunity-detail', kwargs={'pk': self.object.pk})


class OpportunityProductsView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage opportunity products and pricing"""
    
    permission_required = 'crm.change_opportunity'
    
    def get(self, request, pk):
        opportunity = get_object_or_404(
            Opportunity,
            pk=pk,
            tenant=request.tenant
        )
        
        products = opportunity.products.filter(is_active=True).select_related('product')
        available_products = Product.objects.filter(
            tenant=request.tenant,
            status='ACTIVE',
            is_active=True
        ).order_by('name')
        
        context = {
            'opportunity': opportunity,
            'opportunity_products': products,
            'available_products': available_products,
            'total_amount': products.aggregate(Sum('total_price'))['total_price__sum'] or 0,
        }
        
        return render(request, 'crm/opportunity/products.html', context)
    
    def post(self, request, pk):
        opportunity = get_object_or_404(
            Opportunity,
            pk=pk,
            tenant=request.tenant
        )
        
        action = request.POST.get('action')
        
        if action == 'add_product':
            return self.add_product(request, opportunity)
        elif action == 'update_product':
            return self.update_product(request, opportunity)
        elif action == 'remove_product':
            return self.remove_product(request, opportunity)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def add_product(self, request, opportunity):
        """Add product to opportunity"""
        try:
            product_id = request.POST.get('product_id')
            quantity = Decimal(request.POST.get('quantity', 1))
            unit_price = Decimal(request.POST.get('unit_price', 0))
            discount_percent = Decimal(request.POST.get('discount_percent', 0))
            
            product = Product.objects.get(
                id=product_id,
                tenant=request.tenant
            )
            
            # Check if product already exists
            existing = OpportunityProduct.objects.filter(
                opportunity=opportunity,
                product_id=product_id,
                is_active=True
            ).first()
            
            if existing:
                return JsonResponse({
                    'success': False,
                    'message': 'Product already added to opportunity'
                })
            
            # Get next line number
            max_line = opportunity.products.aggregate(
                max_line=Max('line_number')
            )['max_line'] or 0
            
            opp_product = OpportunityProduct.objects.create(
                tenant=request.tenant,
                opportunity=opportunity,
                product=product,
                product_name=product.name,
                product_code=product.code,
                quantity=quantity,
                unit_price=unit_price or product.base_price,
                discount_percent=discount_percent,
                line_number=max_line + 1,
                created_by=request.user
            )
            
            # Update opportunity amount
            self.update_opportunity_amount(opportunity)
            
            return JsonResponse({
                'success': True,
                'message': f'Added {product.name} to opportunity',
                'product_id': opp_product.id,
                'total_price': float(opp_product.total_price)
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def update_product(self, request, opportunity):
        """Update opportunity product"""
        try:
            product_id = request.POST.get('product_id')
            quantity = Decimal(request.POST.get('quantity', 1))
            unit_price = Decimal(request.POST.get('unit_price', 0))
            discount_percent = Decimal(request.POST.get('discount_percent', 0))
            
            opp_product = OpportunityProduct.objects.get(
                id=product_id,
                opportunity=opportunity,
                tenant=request.tenant
            )
            
            opp_product.quantity = quantity
            opp_product.unit_price = unit_price
            opp_product.discount_percent = discount_percent
            opp_product.updated_by = request.user
            opp_product.save()
            
            # Update opportunity amount
            self.update_opportunity_amount(opportunity)
            
            return JsonResponse({
                'success': True,
                'message': 'Product updated successfully',
                'total_price': float(opp_product.total_price)
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def remove_product(self, request, opportunity):
        """Remove product from opportunity"""
        try:
            product_id = request.POST.get('product_id')
            
            OpportunityProduct.objects.filter(
                id=product_id,
                opportunity=opportunity,
                tenant=request.tenant
            ).update(is_active=False, updated_by=request.user)
            
            # Update opportunity amount
            self.update_opportunity_amount(opportunity)
            
            return JsonResponse({
                'success': True,
                'message': 'Product removed from opportunity'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def update_opportunity_amount(self, opportunity):
        """Update opportunity total amount based on products"""
        total = opportunity.products.filter(is_active=True).aggregate(
            Sum('total_price')
        )['total_price__sum'] or 0
        
        opportunity.amount = total
        opportunity.expected_revenue = (total * opportunity.probability / 100)
        opportunity.save(update_fields=['amount', 'expected_revenue'])


class OpportunityCloseView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Close opportunity as won or lost"""
    
    permission_required = 'crm.change_opportunity'
    
    def post(self, request, pk):
        opportunity = get_object_or_404(
            Opportunity,
            pk=pk,
            tenant=request.tenant
        )
        
        if opportunity.is_closed:
            return JsonResponse({
                'success': False,
                'message': 'Opportunity is already closed'
            })
        
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        close_date = request.POST.get('close_date')
        
        try:
            with transaction.atomic():
                if action == 'close_won':
                    opportunity.close_as_won(
                        user=request.user,
                        close_date=datetime.strptime(close_date, '%Y-%m-%d').date() if close_date else None
                    )
                    message = f'Opportunity "{opportunity.name}" closed as won!'
                    
                elif action == 'close_lost':
                    opportunity.close_as_lost(
                        user=request.user,
                        reason=reason,
                        close_date=datetime.strptime(close_date, '%Y-%m-%d').date() if close_date else None
                    )
                    message = f'Opportunity "{opportunity.name}" closed as lost'
                
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid action'
                    })
                
                # Update account metrics
                opportunity.account.update_revenue_metrics()
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'redirect_url': reverse_lazy('crm:opportunity-detail', kwargs={'pk': pk})
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class OpportunityForecastView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Sales forecasting and pipeline analysis"""
    
    permission_required = 'crm.view_forecasts'
    
    def get(self, request):
        # Time periods
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        next_month_start = (current_month_start + timedelta(days=32)).replace(day=1)
        current_quarter_start = today.replace(month=((today.month-1)//3)*3+1, day=1)
        next_quarter_start = (current_quarter_start + timedelta(days=92)).replace(day=1)
        
        # Base queryset
        opportunities = Opportunity.objects.filter(
            tenant=request.tenant,
            is_active=True,
            is_closed=False
        ).select_related('stage', 'owner', 'account')
        
        # User filtering
        user = request.user
        if not user.has_perm('crm.view_all_opportunities'):
            opportunities = opportunities.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        # Time-based forecasts
        current_month_opps = opportunities.filter(
            close_date__gte=current_month_start,
            close_date__lt=next_month_start
        )
        
        current_quarter_opps = opportunities.filter(
            close_date__gte=current_quarter_start,
            close_date__lt=next_quarter_start
        )
        
        # Calculate forecasts
        forecast_data = {
            'current_month': self.calculate_forecast(current_month_opps),
            'current_quarter': self.calculate_forecast(current_quarter_opps),
            'by_owner': self.calculate_owner_forecast(current_quarter_opps),
            'by_stage': self.calculate_stage_forecast(current_quarter_opps),
            'pipeline_health': self.calculate_pipeline_health(opportunities),
        }
        
        # Trending analysis
        forecast_data['trending'] = self.calculate_trending_analysis(opportunities)
        
        context = {
            'forecast_data': forecast_data,
            'opportunities_count': opportunities.count(),
            'total_pipeline_value': opportunities.aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        return render(request, 'crm/opportunity/forecast.html', context)
    
    def calculate_forecast(self, opportunities):
        """Calculate forecast for opportunity set"""
        total_value = opportunities.aggregate(Sum('amount'))['amount__sum'] or 0
        weighted_value = opportunities.aggregate(
            weighted=Sum(F('amount') * F('probability') / 100)
        )['weighted'] or 0
        
        # Best/worst case scenarios
        high_prob_opps = opportunities.filter(probability__gte=75)
        medium_prob_opps = opportunities.filter(probability__gte=50)
        low_prob_opps = opportunities.filter(probability__lt=50)
        
        return {
            'total_value': float(total_value),
            'weighted_value': float(weighted_value),
            'best_case': float(high_prob_opps.aggregate(Sum('amount'))['amount__sum'] or 0),
            'likely_case': float(medium_prob_opps.aggregate(Sum('amount'))['amount__sum'] or 0),
            'worst_case': float(low_prob_opps.aggregate(Sum('amount'))['amount__sum'] or 0),
            'count': opportunities.count(),
            'average_deal_size': float(opportunities.aggregate(Avg('amount'))['amount__avg'] or 0),
        }
    
    def calculate_owner_forecast(self, opportunities):
        """Calculate forecast by owner"""
        owner_data = opportunities.filter(
            owner__isnull=False
        ).values(
            'owner__first_name',
            'owner__last_name',
            'owner__id'
        ).annotate(
            count=Count('id'),
            total_value=Sum('amount'),
            weighted_value=Sum(F('amount') * F('probability') / 100),
            avg_probability=Avg('probability')
        ).order_by('-weighted_value')
        
        return list(owner_data)
    
    def calculate_stage_forecast(self, opportunities):
        """Calculate forecast by stage"""
        stage_data = opportunities.values(
            'stage__name',
            'stage__probability',
            'stage__id'
        ).annotate(
            count=Count('id'),
            total_value=Sum('amount'),
            weighted_value=Sum(F('amount') * F('probability') / 100)
        ).order_by('stage__sort_order')
        
        return list(stage_data)
    
    def calculate_pipeline_health(self, opportunities):
        """Calculate pipeline health metrics"""
        total_opps = opportunities.count()
        
        if total_opps == 0:
            return {
                'health_score': 0,
                'velocity': 0,
                'conversion_rate': 0,
                'average_cycle': 0
            }
        
        # Stage distribution health
        early_stage_count = opportunities.filter(stage__probability__lt=50).count()
        late_stage_count = opportunities.filter(stage__probability__gte=50).count()
        
        # Overdue opportunities
        overdue_count = opportunities.filter(close_date__lt=timezone.now().date()).count()
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Penalize for too many early stage
        if early_stage_count / total_opps > 0.7:
            health_score -= 20
        
        # Penalize for overdue opportunities
        if overdue_count > 0:
            overdue_penalty = min(30, (overdue_count / total_opps) * 100)
            health_score -= overdue_penalty
        
        # Reward for good stage distribution
        if 0.3 <= early_stage_count / total_opps <= 0.6:
            health_score += 10
        
        return {
            'health_score': max(0, health_score),
            'early_stage_ratio': early_stage_count / total_opps * 100,
            'late_stage_ratio': late_stage_count / total_opps * 100,
            'overdue_count': overdue_count,
            'overdue_ratio': overdue_count / total_opps * 100,
        }
    
    def calculate_trending_analysis(self, opportunities):
        """Calculate trending analysis"""
        # Compare current period vs previous period
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        
        current_month_created = opportunities.filter(
            created_at__date__gte=current_month_start
        ).count()
        
        last_month_created = opportunities.filter(
            created_at__date__gte=last_month_start,
            created_at__date__lte=last_month_end
        ).count()
        
        # Calculate trend
        if last_month_created > 0:
            creation_trend = ((current_month_created - last_month_created) / last_month_created) * 100
        else:
            creation_trend = 100 if current_month_created > 0 else 0
        
        return {
            'creation_trend': creation_trend,
            'current_month_created': current_month_created,
            'last_month_created': last_month_created,
        }


# ============================================================================
# API ViewSets
# ============================================================================

class OpportunityViewSet(CRMBaseViewSet):
    """Opportunity API ViewSet with comprehensive functionality"""
    
    queryset = Opportunity.objects.all()
    permission_classes = [OpportunityPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OpportunityFilter
    search_fields = ['name', 'description', 'account__name', 'primary_contact__first_name', 'primary_contact__last_name']
    ordering_fields = ['amount', 'probability', 'close_date', 'created_at', 'stage__sort_order']
    ordering = ['-amount']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OpportunityDetailSerializer
        return OpportunitySerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'account', 'primary_contact', 'pipeline', 'stage', 
            'owner', 'territory', 'campaign'
        ).prefetch_related(
            'products', 'team_memberships__user'
        ).annotate(
            products_count=Count('products', filter=Q(products__is_active=True)),
            team_size=Count('team_memberships', filter=Q(team_memberships__is_active=True))
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_opportunities'):
            queryset = queryset.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def change_stage(self, request, pk=None):
        """Change opportunity stage"""
        opportunity = self.get_object()
        new_stage_id = request.data.get('stage_id')
        
        if not new_stage_id:
            return Response(
                {'error': 'stage_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_stage = PipelineStage.objects.get(
                id=new_stage_id,
                tenant=request.tenant,
                pipeline=opportunity.pipeline
            )
            
            old_stage = opportunity.stage
            opportunity.stage = new_stage
            opportunity.probability = new_stage.probability
            opportunity.stage_changed_date = timezone.now()
            
            # Update stage history
            stage_history = opportunity.stage_history or []
            stage_history.append({
                'from_stage': old_stage.name if old_stage else None,
                'to_stage': new_stage.name,
                'changed_date': timezone.now().isoformat(),
                'changed_by': request.user.id,
            })
            opportunity.stage_history = stage_history
            
            # Handle closed stages
            if new_stage.is_closed:
                opportunity.is_closed = True
                opportunity.closed_date = timezone.now()
                opportunity.is_won = new_stage.is_won
            else:
                opportunity.is_closed = False
                opportunity.is_won = False
                opportunity.closed_date = None
            
            opportunity.save()
            
            return Response({
                'success': True,
                'message': f'Stage changed to {new_stage.name}',
                'stage': {
                    'id': new_stage.id,
                    'name': new_stage.name,
                    'probability': new_stage.probability
                }
            })
        
        except PipelineStage.DoesNotExist:
            return Response(
                {'error': 'Invalid stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def close_won(self, request, pk=None):
        """Close opportunity as won"""
        opportunity = self.get_object()
        
        if opportunity.is_closed:
            return Response(
                {'error': 'Opportunity is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            close_date = request.data.get('close_date')
            if close_date:
                close_date = datetime.strptime(close_date, '%Y-%m-%d').date()
            
            opportunity.close_as_won(request.user, close_date)
            
            return Response({
                'success': True,
                'message': 'Opportunity closed as won',
                'closed_date': opportunity.closed_date,
                'amount': opportunity.amount
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def close_lost(self, request, pk=None):
        """Close opportunity as lost"""
        opportunity = self.get_object()
        
        if opportunity.is_closed:
            return Response(
                {'error': 'Opportunity is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reason = request.data.get('reason', '')
            close_date = request.data.get('close_date')
            
            if close_date:
                close_date = datetime.strptime(close_date, '%Y-%m-%d').date()
            
            opportunity.close_as_lost(request.user, reason, close_date)
            
            return Response({
                'success': True,
                'message': 'Opportunity closed as lost',
                'closed_date': opportunity.closed_date,
                'lost_reason': opportunity.lost_reason
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get', 'post'])
    def products(self, request, pk=None):
        """Manage opportunity products"""
        opportunity = self.get_object()
        
        if request.method == 'GET':
            products = opportunity.products.filter(is_active=True)
            serializer = OpportunityProductSerializer(products, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = OpportunityProductSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(
                    tenant=request.tenant,
                    opportunity=opportunity,
                    created_by=request.user
                )
                
                # Update opportunity amount
                total_amount = opportunity.products.filter(is_active=True).aggregate(
                    Sum('total_price')
                )['total_price__sum'] or 0
                
                opportunity.amount = total_amount
                opportunity.expected_revenue = (total_amount * opportunity.probability / 100)
                opportunity.save(update_fields=['amount', 'expected_revenue'])
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def pipeline_view(self, request):
        """Get opportunities organized by pipeline stages"""
        opportunities = self.filter_queryset(self.get_queryset())
        
        # Group by pipeline and stage
        pipeline_data = {}
        
        for opp in opportunities:
            pipeline_name = opp.pipeline.name if opp.pipeline else 'No Pipeline'
            stage_name = opp.stage.name if opp.stage else 'No Stage'
            
            if pipeline_name not in pipeline_pipeline_name] = {}
            
            if stage_name not in pipeline_data[pipeline_name]:
                pipeline_data[pipeline_name][stage_name] = []
            
            serializer = OpportunitySerializer(opp, context={'request': request})
            pipeline_data[pipeline_name][stage_name].append(serializer.data)
        
        return Response(pipeline_data)
    
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        """Get sales forecast data"""
        opportunities = self.filter_queryset(self.get_queryset()).filter(is_closed=False)
        
        # Time periods
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        next_month_start = (current_month_start + timedelta(days=32)).replace(day=1)
        current_quarter_start = today.replace(month=((today.month-1)//3)*3+1, day=1)
        
        # Current month forecast
        current_month_opps = opportunities.filter(
            close_date__gte=current_month_start,
            close_date__lt=next_month_start
        )
        
        # Current quarter forecast
        current_quarter_opps = opportunities.filter(
            close_date__gte=current_quarter_start
        )
        
        forecast_data = {
            'current_month': {
                'count': current_month_opps.count(),
                'total_value': float(current_month_opps.aggregate(Sum('amount'))['amount__sum'] or 0),
                'weighted_value': float(current_month_opps.aggregate(
                    weighted=Sum(F('amount') * F('probability') / 100)
                )['weighted'] or 0),
            },
            'current_quarter': {
                'count': current_quarter_opps.count(),
                'total_value': float(current_quarter_opps.aggregate(Sum('amount'))['amount__sum'] or 0),
                'weighted_value': float(current_quarter_opps.aggregate(
                    weighted=Sum(F('amount') * F('probability') / 100)
                )['weighted'] or 0),
            }
        }
        
        return Response(forecast_data)


class PipelineViewSet(CRMBaseViewSet):
    """Pipeline API ViewSet"""
    
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = [OpportunityPermission]
    
    def get_queryset(self):
        return super().get_queryset().prefetch_related('stages').annotate(
            opportunities_count=Count('opportunities'),
            total_value=Sum('opportunities__amount')
        )
    
    @action(detail=True, methods=['get'])
    def opportunities(self, request, pk=None):
        """Get opportunities in this pipeline"""
        pipeline = self.get_object()
        opportunities = pipeline.opportunities.filter(is_active=True)
        
        page = self.paginate_queryset(opportunities)
        if page is not None:
            serializer = OpportunitySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = OpportunitySerializer(opportunities, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get pipeline performance metrics"""
        pipeline = self.get_object()
        
        opportunities = pipeline.opportunities.filter(is_active=True)
        
        return Response({
            'total_opportunities': opportunities.count(),
            'open_opportunities': opportunities.filter(is_closed=False).count(),
            'won_opportunities': opportunities.filter(is_won=True).count(),
            'total_value': float(opportunities.aggregate(Sum('amount'))['amount__sum'] or 0),
            'won_value': float(opportunities.filter(is_won=True).aggregate(Sum('amount'))['amount__sum'] or 0),
            'win_rate': pipeline.win_rate,
            'average_deal_size': pipeline.average_deal_size,
            'average_sales_cycle': pipeline.average_sales_cycle,
        })


class PipelineStageViewSet(CRMBaseViewSet):
    """Pipeline Stage API ViewSet"""
    
    queryset = PipelineStage.objects.all()
    serializer_class = PipelineStageSerializer
    permission_classes = [OpportunityPermission]
    
    def get_queryset(self):
        return super().get_queryset().select_related('pipeline').annotate(
            opportunities_count=Count('opportunities')
        )
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder pipeline stages"""
        stage_orders = request.data.get('stage_orders', [])
        
        try:
            with transaction.atomic():
                for item in stage_orders:
                    PipelineStage.objects.filter(
                        id=item['stage_id'],
                        tenant=request.tenant
                    ).update(sort_order=item['order'])
            
            return Response({
                'success': True,
                'message': 'Stage order updated successfully'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )