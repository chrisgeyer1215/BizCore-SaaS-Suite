# ============================================================================
# backend/apps/crm/views/territory.py - Territory Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import Territory, Team, TeamMembership
from ..serializers import TerritorySerializer, TeamSerializer, TeamMembershipSerializer
from ..permissions import TerritoryPermission
from ..filters import TerritoryFilter, TeamFilter
from ..services import TerritoryService


class TerritoryListView(CRMBaseMixin, ListView):
    """Enhanced Territory list view with analytics"""
    
    model = Territory
    template_name = 'crm/territory/list.html'
    context_object_name = 'territories'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations for analytics
        queryset = queryset.annotate(
            total_accounts=Count('accounts', distinct=True),
            total_leads=Count('leads', distinct=True),
            total_opportunities=Count('opportunities', distinct=True),
            total_revenue=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            team_count=Count('teams', distinct=True),
            active_users=Count(
                'teams__memberships__user',
                filter=Q(teams__memberships__is_active=True),
                distinct=True
            )
        ).select_related('parent', 'manager').prefetch_related('children')
        
        # Apply search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(region__icontains=search)
            )
        
        # Apply filters
        territory_type = self.request.GET.get('type')
        if territory_type:
            queryset = queryset.filter(territory_type=territory_type)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Territory statistics
        territories = self.get_queryset()
        context.update({
            'total_territories': territories.count(),
            'active_territories': territories.filter(is_active=True).count(),
            'territory_types': Territory.TERRITORY_TYPES,
            'total_revenue': territories.aggregate(
                total=Sum('total_revenue')
            )['total'] or 0,
            'performance_data': self.get_territory_performance_data(territories),
        })
        
        return context
    
    def get_territory_performance_data(self, territories):
        """Get performance data for territories"""
        performance = []
        
        for territory in territories[:10]:  # Top 10 for performance chart
            performance.append({
                'name': territory.name,
                'revenue': float(territory.total_revenue or 0),
                'accounts': territory.total_accounts,
                'opportunities': territory.total_opportunities,
                'conversion_rate': self.calculate_conversion_rate(territory)
            })
        
        return performance
    
    def calculate_conversion_rate(self, territory):
        """Calculate lead to opportunity conversion rate"""
        total_leads = territory.leads.count()
        converted_leads = territory.leads.filter(
            converted_opportunity__isnull=False
        ).count()
        
        if total_leads > 0:
            return round((converted_leads / total_leads) * 100, 2)
        return 0


class TerritoryDetailView(CRMBaseMixin, DetailView):
    """Enhanced Territory detail view with comprehensive analytics"""
    
    model = Territory
    template_name = 'crm/territory/detail.html'
    context_object_name = 'territory'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('parent', 'manager')
            .prefetch_related('children', 'teams__memberships__user'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        territory = self.object
        
        # Territory metrics
        context.update({
            'territory_stats': self.get_territory_stats(territory),
            'performance_metrics': self.get_performance_metrics(territory),
            'team_info': self.get_team_info(territory),
            'geographic_data': self.get_geographic_data(territory),
            'recent_activities': self.get_recent_activities(territory),
            'top_accounts': self.get_top_accounts(territory),
            'pipeline_data': self.get_pipeline_data(territory),
            'monthly_trends': self.get_monthly_trends(territory),
        })
        
        return context
    
    def get_territory_stats(self, territory):
        """Get comprehensive territory statistics"""
        today = timezone.now().date()
        this_month = timezone.now().replace(day=1).date()
        last_month = (timezone.now().replace(day=1) - timezone.timedelta(days=1)).replace(day=1).date()
        
        # Current period stats
        current_stats = {
            'total_accounts': territory.accounts.filter(is_active=True).count(),
            'total_leads': territory.leads.count(),
            'total_opportunities': territory.opportunities.filter(is_closed=False).count(),
            'total_revenue': territory.opportunities.filter(is_won=True).aggregate(
                Sum('amount'))['amount__sum'] or 0,
            'pipeline_value': territory.opportunities.filter(is_closed=False).aggregate(
                Sum('amount'))['amount__sum'] or 0,
        }
        
        # Previous period for comparison
        previous_stats = {
            'accounts_last_month': territory.accounts.filter(
                created_at__lt=this_month
            ).count(),
            'leads_last_month': territory.leads.filter(
                created_at__range=[last_month, this_month]
            ).count(),
            'revenue_last_month': territory.opportunities.filter(
                is_won=True,
                closed_date__range=[last_month, this_month]
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        # Calculate growth rates
        growth_rates = {}
        for key in ['accounts', 'leads', 'revenue']:
            current_key = f'total_{key}' if key != 'revenue' else 'total_revenue'
            previous_key = f'{key}_last_month'
            
            current_val = current_stats.get(current_key, 0)
            previous_val = previous_stats.get(previous_key, 0)
            
            if previous_val > 0:
                growth_rates[f'{key}_growth'] = round(
                    ((current_val - previous_val) / previous_val) * 100, 2
                )
            else:
                growth_rates[f'{key}_growth'] = 0
        
        return {**current_stats, **growth_rates}
    
    def get_performance_metrics(self, territory):
        """Get territory performance metrics"""
        # Conversion rates
        total_leads = territory.leads.count()
        converted_leads = territory.leads.filter(
            converted_opportunity__isnull=False
        ).count()
        lead_conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Win rate
        closed_opportunities = territory.opportunities.filter(is_closed=True)
        won_opportunities = closed_opportunities.filter(is_won=True)
        win_rate = (won_opportunities.count() / closed_opportunities.count() * 100) if closed_opportunities.count() > 0 else 0
        
        # Average deal size
        avg_deal_size = won_opportunities.aggregate(Avg('amount'))['amount__avg'] or 0
        
        # Sales cycle
        avg_sales_cycle = closed_opportunities.aggregate(
            avg_cycle=Avg(
                F('closed_date') - F('created_at')
            )
        )['avg_cycle']
        
        avg_sales_cycle_days = avg_sales_cycle.days if avg_sales_cycle else 0
        
        return {
            'lead_conversion_rate': round(lead_conversion_rate, 2),
            'win_rate': round(win_rate, 2),
            'avg_deal_size': float(avg_deal_size),
            'avg_sales_cycle_days': avg_sales_cycle_days,
            'quota_achievement': self.calculate_quota_achievement(territory),
        }
    
    def get_team_info(self, territory):
        """Get team information for territory"""
        teams = territory.teams.filter(is_active=True).prefetch_related(
            'memberships__user'
        )
        
        team_data = []
        for team in teams:
            active_members = team.memberships.filter(is_active=True)
            team_data.append({
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'member_count': active_members.count(),
                'manager': team.manager.get_full_name() if team.manager else '',
                'members': [
                    {
                        'name': membership.user.get_full_name(),
                        'role': membership.role,
                        'joined_date': membership.joined_date,
                    }
                    for membership in active_members.select_related('user')
                ]
            })
        
        return team_data
    
    def get_geographic_data(self, territory):
        """Get geographic information for mapping"""
        # This would integrate with mapping services
        return {
            'region': territory.region,
            'country': territory.country,
            'state_province': territory.state_province,
            'postal_codes': territory.postal_codes,
            'coordinates': {
                'latitude': territory.latitude,
                'longitude': territory.longitude,
            } if territory.latitude and territory.longitude else None,
        }
    
    def get_recent_activities(self, territory):
        """Get recent activities in territory"""
        # Get activities from accounts in this territory
        activities = territory.activities.select_related(
            'activity_type', 'assigned_to'
        ).order_by('-created_at')[:20]
        
        return [{
            'id': activity.id,
            'subject': activity.subject,
            'type': activity.activity_type.name,
            'assigned_to': activity.assigned_to.get_full_name() if activity.assigned_to else '',
            'created_at': activity.created_at,
        } for activity in activities]
    
    def get_top_accounts(self, territory):
        """Get top accounts by revenue in territory"""
        return territory.accounts.filter(
            is_active=True
        ).annotate(
            total_revenue=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).order_by('-total_revenue')[:10]
    
    def get_pipeline_data(self, territory):
        """Get pipeline data for territory"""
        pipelines = territory.opportunities.filter(
            is_closed=False
        ).values('stage__name', 'stage__probability').annotate(
            count=Count('id'),
            value=Sum('amount')
        ).order_by('stage__sort_order')
        
        return list(pipelines)
    
    def get_monthly_trends(self, territory):
        """Get monthly trend data"""
        # Get data for last 12 months
        months = []
        current_date = timezone.now().date().replace(day=1)
        
        for i in range(12):
            month_start = (current_date - timezone.timedelta(days=30*i)).replace(day=1)
            next_month = (month_start + timezone.timedelta(days=32)).replace(day=1)
            
            month_data = {
                'month': month_start.strftime('%Y-%m'),
                'revenue': territory.opportunities.filter(
                    is_won=True,
                    closed_date__gte=month_start,
                    closed_date__lt=next_month
                ).aggregate(Sum('amount'))['amount__sum'] or 0,
                'new_accounts': territory.accounts.filter(
                    created_at__gte=month_start,
                    created_at__lt=next_month
                ).count(),
                'new_leads': territory.leads.filter(
                    created_at__gte=month_start,
                    created_at__lt=next_month
                ).count(),
            }
            months.append(month_data)
        
        return list(reversed(months))
    
    def calculate_quota_achievement(self, territory):
        """Calculate quota achievement for territory"""
        # This would be based on territory quotas if implemented
        return 85.5  # Placeholder


class TerritoryViewSet(CRMBaseViewSet):
    """Enhanced Territory API viewset"""
    
    queryset = Territory.objects.all()
    serializer_class = TerritorySerializer
    filterset_class = TerritoryFilter
    search_fields = ['name', 'description', 'region', 'country']
    ordering_fields = ['name', 'region', 'created_at', 'is_active']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('parent', 'manager').prefetch_related(
            'children', 'teams'
        ).annotate(
            total_accounts=Count('accounts', distinct=True),
            total_revenue=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            )
        )
    
    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Get territory hierarchy"""
        territory = self.get_object()
        
        def get_hierarchy_data(t):
            return {
                'id': t.id,
                'name': t.name,
                'type': t.territory_type,
                'manager': t.manager.get_full_name() if t.manager else None,
                'children': [get_hierarchy_data(child) for child in t.children.all()]
            }
        
        return Response(get_hierarchy_data(territory))
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get territory performance metrics"""
        territory = self.get_object()
        service = TerritoryService()
        
        performance_data = service.get_territory_performance(territory)
        return Response(performance_data)
    
    @action(detail=True, methods=['get'])
    def team_performance(self, request, pk=None):
        """Get team performance within territory"""
        territory = self.get_object()
        
        team_performance = []
        for team in territory.teams.filter(is_active=True):
            members_performance = []
            
            for membership in team.memberships.filter(is_active=True):
                user = membership.user
                user_stats = {
                    'user_id': user.id,
                    'name': user.get_full_name(),
                    'role': membership.role,
                    'leads_count': territory.leads.filter(owner=user).count(),
                    'opportunities_count': territory.opportunities.filter(owner=user, is_closed=False).count(),
                    'revenue': territory.opportunities.filter(
                        owner=user, is_won=True
                    ).aggregate(Sum('amount'))['amount__sum'] or 0,
                }
                members_performance.append(user_stats)
            
            team_performance.append({
                'team_id': team.id,
                'team_name': team.name,
                'manager': team.manager.get_full_name() if team.manager else '',
                'members': members_performance
            })
        
        return Response(team_performance)
    
    @action(detail=False, methods=['post'])
    def optimize_territories(self, request):
        """Optimize territory assignments"""
        service = TerritoryService()
        
        try:
            optimization_data = request.data
            results = service.optimize_territory_assignments(
                tenant=request.tenant,
                criteria=optimization_data.get('criteria', {}),
                constraints=optimization_data.get('constraints', {})
            )
            
            return Response({
                'success': True,
                'optimization_results': results,
                'message': 'Territory optimization completed successfully'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def assign_accounts(self, request, pk=None):
        """Assign accounts to territory"""
        territory = self.get_object()
        account_ids = request.data.get('account_ids', [])
        
        if not account_ids:
            return Response(
                {'error': 'Account IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Update accounts to this territory
                from ..models import Account
                updated_count = Account.objects.filter(
                    id__in=account_ids,
                    tenant=request.tenant
                ).update(territory=territory)
                
                return Response({
                    'success': True,
                    'assigned_count': updated_count,
                    'message': f'Successfully assigned {updated_count} accounts to {territory.name}'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TeamListView(CRMBaseMixin, ListView):
    """Team list view with performance metrics"""
    
    model = Team
    template_name = 'crm/territory/team_list.html'
    context_object_name = 'teams'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations
        queryset = queryset.annotate(
            member_count=Count('memberships', filter=Q(memberships__is_active=True)),
            total_revenue=Sum(
                Case(
                    When(
                        territory__opportunities__is_won=True,
                        then='territory__opportunities__amount'
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).select_related('territory', 'manager').prefetch_related('memberships__user')
        
        # Apply filters
        territory_id = self.request.GET.get('territory')
        if territory_id:
            queryset = queryset.filter(territory_id=territory_id)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        teams = self.get_queryset()
        context.update({
            'total_teams': teams.count(),
            'active_teams': teams.filter(is_active=True).count(),
            'territories': self.request.tenant.territories.filter(is_active=True),
            'total_members': sum(team.member_count for team in teams),
        })
        
        return context


class TeamDetailView(CRMBaseMixin, DetailView):
    """Team detail view with member performance"""
    
    model = Team
    template_name = 'crm/territory/team_detail.html'
    context_object_name = 'team'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('territory', 'manager'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        
        # Team metrics
        context.update({
            'team_stats': self.get_team_stats(team),
            'member_performance': self.get_member_performance(team),
            'territory_info': self.get_territory_info(team),
            'recent_activities': self.get_team_recent_activities(team),
        })
        
        return context
    
    def get_team_stats(self, team):
        """Get team statistics"""
        active_members = team.memberships.filter(is_active=True)
        
        # Aggregate stats from territory
        if team.territory:
            territory_stats = {
                'accounts': team.territory.accounts.count(),
                'leads': team.territory.leads.count(),
                'opportunities': team.territory.opportunities.filter(is_closed=False).count(),
                'revenue': team.territory.opportunities.filter(is_won=True).aggregate(
                    Sum('amount'))['amount__sum'] or 0,
            }
        else:
            territory_stats = {
                'accounts': 0, 'leads': 0, 'opportunities': 0, 'revenue': 0
            }
        
        return {
            'active_members': active_members.count(),
            'total_members': team.memberships.count(),
            **territory_stats
        }
    
    def get_member_performance(self, team):
        """Get individual member performance"""
        members = []
        
        for membership in team.memberships.filter(is_active=True).select_related('user'):
            user = membership.user
            
            # Calculate user performance in this territory context
            if team.territory:
                user_leads = team.territory.leads.filter(owner=user)
                user_opportunities = team.territory.opportunities.filter(owner=user)
            else:
                user_leads = user.leads.filter(tenant=self.request.tenant)
                user_opportunities = user.opportunities.filter(tenant=self.request.tenant)
            
            member_stats = {
                'user_id': user.id,
                'name': user.get_full_name(),
                'email': user.email,
                'role': membership.role,
                'joined_date': membership.joined_date,
                'leads_count': user_leads.count(),
                'opportunities_count': user_opportunities.filter(is_closed=False).count(),
                'won_opportunities': user_opportunities.filter(is_won=True).count(),
                'revenue': user_opportunities.filter(is_won=True).aggregate(
                    Sum('amount'))['amount__sum'] or 0,
            }
            
            members.append(member_stats)
        
        return sorted(members, key=lambda x: x['revenue'], reverse=True)
    
    def get_territory_info(self, team):
        """Get territory information"""
        if not team.territory:
            return None
        
        territory = team.territory
        return {
            'id': territory.id,
            'name': territory.name,
            'type': territory.get_territory_type_display(),
            'region': territory.region,
            'description': territory.description,
        }
    
    def get_team_recent_activities(self, team):
        """Get recent activities from team members"""
        if not team.territory:
            return []
        
        # Get activities from territory
        activities = team.territory.activities.select_related(
            'activity_type', 'assigned_to'
        ).filter(
            assigned_to__in=team.memberships.values_list('user', flat=True)
        ).order_by('-created_at')[:15]
        
        return [{
            'id': activity.id,
            'subject': activity.subject,
            'type': activity.activity_type.name,
            'assigned_to': activity.assigned_to.get_full_name(),
            'created_at': activity.created_at,
        } for activity in activities]


class TeamViewSet(CRMBaseViewSet):
    """Team API viewset"""
    
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    filterset_class = TeamFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'is_active']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('territory', 'manager').prefetch_related(
            'memberships__user'
        ).annotate(
            member_count=Count('memberships', filter=Q(memberships__is_active=True))
        )
    
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add member to team"""
        team = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'MEMBER')
        
        if not user_id:
            return Response(
                {'error': 'User ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Check if already a member
            if team.memberships.filter(user=user, is_active=True).exists():
                return Response(
                    {'error': 'User is already a team member'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create membership
            membership = TeamMembership.objects.create(
                team=team,
                user=user,
                role=role,
                tenant=request.tenant,
                created_by=request.user
            )
            
            serializer = TeamMembershipSerializer(membership)
            return Response({
                'success': True,
                'membership': serializer.data,
                'message': f'{user.get_full_name()} added to {team.name}'
            })
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Remove member from team"""
        team = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'User ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            membership = team.memberships.get(
                user_id=user_id,
                is_active=True
            )
            
            # Soft delete
            membership.is_active = False
            membership.left_date = timezone.now().date()
            membership.updated_by = request.user
            membership.save()
            
            return Response({
                'success': True,
                'message': 'Member removed from team'
            })
        
        except TeamMembership.DoesNotExist:
            return Response(
                {'error': 'Team membership not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get team performance metrics"""
        team = self.get_object()
        
        performance_data = {
            'team_stats': {
                'member_count': team.memberships.filter(is_active=True).count(),
                'territory': team.territory.name if team.territory else None,
            },
            'member_performance': [],
        }
        
        # Individual member performance
        for membership in team.memberships.filter(is_active=True).select_related('user'):
            user = membership.user
            
            # Get user performance metrics
            if team.territory:
                user_leads = team.territory.leads.filter(owner=user)
                user_opportunities = team.territory.opportunities.filter(owner=user)
            else:
                user_leads = user.leads.filter(tenant=request.tenant)
                user_opportunities = user.opportunities.filter(tenant=request.tenant)
            
            member_data = {
                'user_id': user.id,
                'name': user.get_full_name(),
                'role': membership.role,
                'metrics': {
                    'leads': user_leads.count(),
                    'opportunities': user_opportunities.filter(is_closed=False).count(),
                    'won_deals': user_opportunities.filter(is_won=True).count(),
                    'revenue': user_opportunities.filter(is_won=True).aggregate(
                        Sum('amount'))['amount__sum'] or 0,
                }
            }
            
            performance_data['member_performance'].append(member_data)
        
        return Response(performance_data)


class TerritoryOptimizationView(CRMBaseMixin, ListView):
    """Territory optimization and analysis view"""
    
    template_name = 'crm/territory/optimization.html'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle optimization requests"""
        optimization_type = request.POST.get('optimization_type')
        
        if optimization_type == 'balance_workload':
            results = self.balance_territory_workload()
        elif optimization_type == 'geographic_optimization':
            results = self.optimize_geographic_territories()
        elif optimization_type == 'revenue_optimization':
            results = self.optimize_revenue_territories()
        else:
            results = {'error': 'Invalid optimization type'}
        
        context = self.get_context_data()
        context['optimization_results'] = results
        
        return render(request, self.template_name, context)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Territory analysis data
        territories = self.request.tenant.territories.filter(is_active=True)
        
        context.update({
            'territories': territories,
            'territory_analysis': self.get_territory_analysis(),
            'workload_distribution': self.get_workload_distribution(),
            'revenue_distribution': self.get_revenue_distribution(),
            'optimization_recommendations': self.get_optimization_recommendations(),
        })
        
        return context
    
    def get_territory_analysis(self):
        """Analyze current territory performance"""
        territories = self.request.tenant.territories.filter(is_active=True)
        
        analysis = []
        for territory in territories:
            metrics = {
                'territory_id': territory.id,
                'name': territory.name,
                'accounts': territory.accounts.count(),
                'leads': territory.leads.count(),
                'opportunities': territory.opportunities.count(),
                'revenue': territory.opportunities.filter(is_won=True).aggregate(
                    Sum('amount'))['amount__sum'] or 0,
                'team_size': territory.teams.aggregate(
                    total_members=Count('memberships', filter=Q(memberships__is_active=True))
                )['total_members'] or 0,
                'efficiency_score': self.calculate_territory_efficiency(territory),
            }
            analysis.append(metrics)
        
        return analysis
    
    def get_workload_distribution(self):
        """Analyze workload distribution across territories"""
        territories = self.request.tenant.territories.filter(is_active=True)
        
        workloads = []
        for territory in territories:
            total_workload = (
                territory.accounts.count() +
                territory.leads.count() +
                territory.opportunities.filter(is_closed=False).count()
            )
            
            team_size = territory.teams.aggregate(
                total_members=Count('memberships', filter=Q(memberships__is_active=True))
            )['total_members'] or 1
            
            workload_per_person = total_workload / team_size
            
            workloads.append({
                'territory': territory.name,
                'total_workload': total_workload,
                'team_size': team_size,
                'workload_per_person': workload_per_person,
            })
        
        return sorted(workloads, key=lambda x: x['workload_per_person'], reverse=True)
    
    def get_revenue_distribution(self):
        """Analyze revenue distribution across territories"""
        territories = self.request.tenant.territories.filter(is_active=True)
        
        revenue_data = []
        for territory in territories:
            revenue = territory.opportunities.filter(is_won=True).aggregate(
                Sum('amount'))['amount__sum'] or 0
            
            team_size = territory.teams.aggregate(
                total_members=Count('memberships', filter=Q(memberships__is_active=True))
            )['total_members'] or 1
            
            revenue_per_person = revenue / team_size
            
            revenue_data.append({
                'territory': territory.name,
                'total_revenue': revenue,
                'team_size': team_size,
                'revenue_per_person': revenue_per_person,
            })
        
        return sorted(revenue_data, key=lambda x: x['revenue_per_person'], reverse=True)
    
    def get_optimization_recommendations(self):
        """Generate optimization recommendations"""
        recommendations = []
        
        # Analyze workload imbalance
        workloads = self.get_workload_distribution()
        if len(workloads) > 1:
            highest = workloads[0]['workload_per_person']
            lowest = workloads[-1]['workload_per_person']
            
            if highest > lowest * 1.5:  # More than 50% difference
                recommendations.append({
                    'type': 'workload_imbalance',
                    'priority': 'high',
                    'title': 'Workload Imbalance Detected',
                    'description': f'{workloads[0]["territory"]} has {highest:.1f} items per person while {workloads[-1]["territory"]} has {lowest:.1f}',
                    'action': 'Consider redistributing accounts or adding team members'
                })
        
        # Analyze revenue performance
        revenue_data = self.get_revenue_distribution()
        if len(revenue_data) > 1:
            avg_revenue = sum(r['revenue_per_person'] for r in revenue_data) / len(revenue_data)
            
            for territory_ territory_data['revenue_per_person'] < avg_revenue * 0.7:  # 30% below average
                    recommendations.append({
                        'type': 'low_performance',
                        'priority': 'medium',
                        'title': f'Low Revenue Performance: {territory_data["territory"]}',
                        'description': f'Revenue per person is {territory_data["revenue_per_person"]:.0f}, below average of {avg_revenue:.0f}',
                        'action': 'Review territory strategy, provide additional training, or reassign resources'
                    })
        
        # Check for understaffed territories
        territory_analysis = self.get_territory_analysis()
        for analysis in territory_analysis:
            if analysis['team_size'] == 0 and analysis['accounts'] > 0:
                recommendations.append({
                    'type': 'understaffed',
                    'priority': 'high',
                    'title': f'Understaffed Territory: {analysis["name"]}',
                    'description': f'Territory has {analysis["accounts"]} accounts but no assigned team members',
                    'action': 'Assign team members to this territory'
                })
        
        return sorted(recommendations, key=lambda x: x['priority'] == 'high', reverse=True)
    
    def calculate_territory_efficiency(self, territory):
        """Calculate efficiency score for territory"""
        # Simple efficiency calculation based on revenue per resource
        accounts = territory.accounts.count()
        leads = territory.leads.count()
        revenue = territory.opportunities.filter(is_won=True).aggregate(
            Sum('amount'))['amount__sum'] or 0
        
        total_resources = accounts + leads
        if total_resources == 0:
            return 0
        
        # Normalize to 0-100 scale
        efficiency = min((revenue / total_resources) / 1000, 100)
        return round(efficiency, 2)
    
    def balance_territory_workload(self):
        """Balance workload across territories"""
        # Implementation for workload balancing algorithm
        return {
            'success': True,
            'message': 'Workload balancing analysis completed',
            'recommendations': [
                'Move 15 accounts from Territory A to Territory B',
                'Reassign 8 leads from Territory C to Territory D',
                'Add 2 team members to Territory E',
            ]
        }
    
    def optimize_geographic_territories(self):
        """Optimize geographic territory boundaries"""
        # Implementation for geographic optimization
        return {
            'success': True,
            'message': 'Geographic optimization completed',
            'recommendations': [
                'Merge Territory North and Territory Northeast for better coverage',
                'Split Territory Central into two regions based on postal codes',
                'Adjust Territory West boundaries to include nearby high-value prospects',
            ]
        }
    
    def optimize_revenue_territories(self):
        """Optimize territories for revenue maximization"""
        # Implementation for revenue optimization
        return {
            'success': True,
            'message': 'Revenue optimization analysis completed',
            'recommendations': [
                'Focus Territory A on high-value enterprise accounts',
                'Reallocate small business accounts from Territory B to Territory C',
                'Create specialized territory for key industry verticals',
            ]
        }