# ============================================================================
# backend/apps/crm/services/territory_service.py - Advanced Territory Management Service
# ============================================================================

import json
import math
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.contrib.gis.measure import Distance
from django.contrib.gis.db.models.functions import Distance as DistanceFunction
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField
import logging

from .base import BaseService, ServiceException
from ..models import (
    Territory, Team, TeamMembership, Account, Lead, Opportunity,
    Activity, TerritoryAssignment, TerritoryPerformance, TerritoryBoundary,
    GeographicRegion, SalesQuota, TerritoryBalance
)

logger = logging.getLogger(__name__)


class TerritoryException(ServiceException):
    """Territory management specific errors"""
    pass


class TerritoryOptimizationEngine:
    """Advanced territory optimization using geographic and business data"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def optimize_territories(self, criteria: Dict) -> Dict:
        """Optimize territory boundaries based on various criteria"""
        try:
            optimization_type = criteria.get('type', 'revenue_balance')
            
            if optimization_type == 'revenue_balance':
                return self._optimize_by_revenue_balance(criteria)
            elif optimization_type == 'geographic_efficiency':
                return self._optimize_by_geographic_efficiency(criteria)
            elif optimization_type == 'workload_balance':
                return self._optimize_by_workload_balance(criteria)
            elif optimization_type == 'skill_match':
                return self._optimize_by_skill_matching(criteria)
            else:
                raise TerritoryException(f"Unknown optimization type: {optimization_type}")
                
        except Exception as e:
            logger.error(f"Territory optimization failed: {e}", exc_info=True)
            raise TerritoryException(f"Optimization failed: {str(e)}")
    
    def _optimize_by_revenue_balance(self, criteria: Dict) -> Dict:
        """Optimize territories for balanced revenue potential"""
        target_balance_threshold = criteria.get('balance_threshold', 0.15)  # 15% variance
        
        territories = Territory.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).prefetch_related('accounts', 'leads', 'opportunities')
        
        territory_metrics = []
        total_revenue = 0
        
        # Calculate current revenue distribution
        for territory in territories:
            revenue = territory.opportunities.filter(
                is_won=True,
                closed_date__gte=timezone.now() - timedelta(days=365)
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            potential_revenue = territory.opportunities.filter(
                is_closed=False
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            territory_metrics.append({
                'territory': territory,
                'current_revenue': revenue,
                'potential_revenue': potential_revenue,
                'total_value': revenue + potential_revenue,
                'account_count': territory.accounts.filter(is_active=True).count(),
                'lead_count': territory.leads.filter(status='NEW').count()
            })
            
            total_revenue += revenue + potential_revenue
        
        # Calculate target revenue per territory
        territory_count = len(territory_metrics)
        target_revenue = total_revenue / territory_count if territory_count > 0 else 0
        
        # Identify imbalances
        recommendations = []
        for metric in territory_metrics:
            variance = abs(metric['total_value'] - target_revenue) / target_revenue if target_revenue > 0 else 0
            
            if variance > target_balance_threshold:
                status = 'over_assigned' if metric['total_value'] > target_revenue else 'under_assigned'
                recommendations.append({
                    'territory_id': metric['territory'].id,
                    'territory_name': metric['territory'].name,
                    'current_value': metric['total_value'],
                    'target_value': target_revenue,
                    'variance_percentage': round(variance * 100, 2),
                    'status': status,
                    'suggested_actions': self._get_rebalancing_suggestions(metric, target_revenue)
                })
        
        return {
            'optimization_type': 'revenue_balance',
            'total_territories': territory_count,
            'total_revenue': total_revenue,
            'target_revenue_per_territory': target_revenue,
            'balanced_territories': territory_count - len(recommendations),
            'imbalanced_territories': len(recommendations),
            'recommendations': recommendations,
            'generated_at': timezone.now().isoformat()
        }
    
    def _get_rebalancing_suggestions(self, metric: Dict, target_revenue: float) -> List[str]:
        """Generate specific suggestions for territory rebalancing"""
        suggestions = []
        territory = metric['territory']
        current_value = metric['total_value']
        
        if current_value > target_revenue * 1.15:  # Over-assigned
            suggestions.extend([
                f"Consider splitting territory - current value {current_value:.0f} vs target {target_revenue:.0f}",
                f"Move {metric['account_count'] // 4} accounts to neighboring territories",
                "Evaluate high-value accounts for potential reassignment"
            ])
        elif current_value < target_revenue * 0.85:  # Under-assigned
            suggestions.extend([
                f"Consider merging with adjacent territory or acquiring accounts",
                f"Territory has capacity for {int((target_revenue - current_value) / 50000)} more accounts",
                "Focus on lead generation in this territory"
            ])
        
        return suggestions


class TerritoryService(BaseService):
    """Comprehensive territory management service with optimization"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.optimizer = TerritoryOptimizationEngine(self.tenant)
        self.geo_analyzer = GeographicAnalyzer()
    
    # ============================================================================
    # TERRITORY MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_territory(self, territory boundaries: List[Dict] = None,
                        team_assignments: List[Dict] = None) -> Territory:
        """
        Create territory with geographic boundaries and team assignments
        
         Territory information
            boundaries: List of geographic boundary definitions
            team_assignments: List of team member assignments
        
        Returns:
            Territory instance
        """
        self.context.operation = 'create_territory'
        
        try:
            self.validate_user_permission('crm.add_territory')
            
            # Validate required fields
            required_fields = ['name', 'territory_type']
            is_valid, errors = self.validate_data(territory_data, {
                field: {'required': True} for field in required_fields
            })
            
            if not is_valid:
                raise TerritoryException(f"Validation failed: {', '.join(errors)}")
            
            # Check for duplicate territory names
            if Territory.objects.filter(
                name__iexact=territory_data['name'],
                tenant=self.tenant
            ).exists():
                raise TerritoryException(f"Territory '{territory_data['name']}' already exists")
            
            # Create territory
            territory = Territory.objects.create(
                tenant=self.tenant,
                name=territory_data['name'],
                description=territory_data.get('description', ''),
                territory_type=territory_data['territory_type'],
                parent_id=territory_data.get('parent_id'),
                manager_id=territory_data.get('manager_id'),
                is_active=territory_data.get('is_active', True),
                settings={
                    'auto_assignment_enabled': territory_data.get('auto_assignment_enabled', True),
                    'lead_assignment_method': territory_data.get('lead_assignment_method', 'round_robin'),
                    'opportunity_threshold': territory_data.get('opportunity_threshold', 10000),
                    'activity_reminder_days': territory_data.get('activity_reminder_days', 7)
                },
                created_by=self.user
            )
            
            # Create geographic boundaries if provided
            if boundaries:
                self._create_territory_boundaries(territory, boundaries)
            
            # Assign team members if provided
            if team_assignments:
                self._assign_team_members(territory, team_assignments)
            
            # Initialize performance tracking
            self._initialize_territory_performance(territory)
            
            # Set up initial quotas
            self._setup_initial_quotas(territory, territory_data.get('quotas', {}))
            
            self.log_activity(
                'territory_created',
                'Territory',
                territory.id,
                {
                    'name': territory.name,
                    'type': territory.territory_type,
                    'boundaries_count': len(boundaries) if boundaries else 0,
                    'team_assignments': len(team_assignments) if team_assignments else 0
                }
            )
            
            return territory
            
        except Exception as e:
            logger.error(f"Territory creation failed: {e}", exc_info=True)
            raise TerritoryException(f"Territory creation failed: {str(e)}")
    
    def get_territory_hierarchy(self, root_territory_id: int = None) -> Dict:
        """
        Get hierarchical territory structure with performance metrics
        
        Args:
            root_territory_id: Root territory ID (all territories if None)
        
        Returns:
            Nested dictionary with territory hierarchy
        """
        try:
            # Build query
            queryset = Territory.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).select_related('manager', 'parent').prefetch_related(
                'children', 'team_memberships__user'
            )
            
            if root_territory_id:
                queryset = queryset.filter(
                    Q(id=root_territory_id) | Q(parent_id=root_territory_id)
                )
            else:
                queryset = queryset.filter(parent__isnull=True)
            
            # Build hierarchy
            territories_dict = {}
            for territory in queryset:
                territory_data = {
                    'id': territory.id,
                    'name': territory.name,
                    'description': territory.description,
                    'territory_type': territory.territory_type,
                    'manager': {
                        'id': territory.manager.id,
                        'name': territory.manager.get_full_name()
                    } if territory.manager else None,
                    'team_members': [
                        {
                            'id': member.user.id,
                            'name': member.user.get_full_name(),
                            'role': member.role,
                            'is_active': member.is_active
                        }
                        for member in territory.team_memberships.filter(is_active=True)
                    ],
                    'performance': self._get_territory_performance_summary(territory),
                    'children': []
                }
                territories_dict[territory.id] = territory_data
            
            # Build nested structure
            hierarchy = []
            for territory_id, territory_data in territories_dict.items():
                territory = queryset.get(id=territory_id)
                if territory.parent_id and territory.parent_id in territories_dict:
                    territories_dict[territory.parent_id]['children'].append(territory_data)
                else:
                    hierarchy.append(territory_data)
            
            return {
                'hierarchy': hierarchy,
                'total_territories': len(territories_dict),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Territory hierarchy retrieval failed: {e}", exc_info=True)
            raise TerritoryException(f"Hierarchy retrieval failed: {str(e)}")
    
    # ============================================================================
    # TERRITORY ASSIGNMENTS
    # ============================================================================
    
    @transaction.atomic
    def assign_accounts_to_territory(self, territory_id: int, account_ids: List[int],
                                   assignment_method: str = 'manual',
                                   effective_date: datetime = None) -> Dict:
        """
        Assign accounts to territory with business rules validation
        
        Args:
            territory_id: Territory ID
            account_ids: List of account IDs to assign
            assignment_method: Assignment method ('manual', 'auto', 'geographic')
            effective_date: When assignment becomes effective
        
        Returns:
            Assignment results
        """
        try:
            territory = Territory.objects.get(id=territory_id, tenant=self.tenant)
            self.validate_user_permission('crm.change_territory')
            
            # Get accounts to assign
            accounts = Account.objects.filter(
                id__in=account_ids,
                tenant=self.tenant,
                is_active=True
            )
            
            if not accounts.exists():
                raise TerritoryException("No valid accounts found for assignment")
            
            assignment_results = {
                'successful_assignments': [],
                'failed_assignments': [],
                'reassignments': [],
                'total_processed': 0
            }
            
            effective_date = effective_date or timezone.now()
            
            for account in accounts:
                try:
                    # Check for existing assignment
                    existing_assignment = TerritoryAssignment.objects.filter(
                        account=account,
                        is_active=True
                    ).first()
                    
                    if existing_assignment:
                        # Handle reassignment
                        if existing_assignment.territory_id != territory_id:
                            # Deactivate old assignment
                            existing_assignment.is_active = False
                            existing_assignment.end_date = effective_date
                            existing_assignment.save()
                            
                            assignment_results['reassignments'].append({
                                'account_id': account.id,
                                'account_name': account.name,
                                'old_territory': existing_assignment.territory.name,
                                'new_territory': territory.name
                            })
                    
                    # Create new assignment
                    assignment = TerritoryAssignment.objects.create(
                        territory=territory,
                        account=account,
                        assignment_method=assignment_method,
                        assigned_by=self.user,
                        effective_date=effective_date,
                        is_active=True,
                        tenant=self.tenant,
                        metadata={
                            'assignment_reason': f'Assigned via {assignment_method} method',
                            'previous_territory': existing_assignment.territory.name if existing_assignment else None
                        }
                    )
                    
                    assignment_results['successful_assignments'].append({
                        'account_id': account.id,
                        'account_name': account.name,
                        'assignment_id': assignment.id
                    })
                    
                    # Update account territory reference
                    account.territory = territory
                    account.save(update_fields=['territory'])
                    
                except Exception as e:
                    assignment_results['failed_assignments'].append({
                        'account_id': account.id,
                        'account_name': account.name,
                        'error': str(e)
                    })
                
                assignment_results['total_processed'] += 1
            
            # Update territory metrics
            self._update_territory_metrics(territory)
            
            self.log_activity(
                'accounts_assigned_to_territory',
                'Territory',
                territory.id,
                {
                    'assignment_method': assignment_method,
                    'successful_count': len(assignment_results['successful_assignments']),
                    'reassignment_count': len(assignment_results['reassignments']),
                    'failed_count': len(assignment_results['failed_assignments'])
                }
            )
            
            return assignment_results
            
        except Territory.DoesNotExist:
            raise TerritoryException("Territory not found")
        except Exception as e:
            logger.error(f"Account assignment failed: {e}", exc_info=True)
            raise TerritoryException(f"Assignment failed: {str(e)}")
    
    def auto_assign_leads_to_territories(self, criteria: Dict = None) -> Dict:
        """
        Automatically assign unassigned leads to territories based on rules
        
        Args:
            criteria: Assignment criteria and filters
        
        Returns:
            Assignment results
        """
        try:
            # Get unassigned leads
            unassigned_leads = Lead.objects.filter(
                tenant=self.tenant,
                territory__isnull=True,
                status='NEW',
                is_active=True
            ).select_related('source')
            
            # Apply criteria filters
            if criteria:
                if 'lead_source' in criteria:
                    unassigned_leads = unassigned_leads.filter(source_id=criteria['lead_source'])
                
                if 'date_range' in criteria:
                    start_date, end_date = criteria['date_range']
                    unassigned_leads = unassigned_leads.filter(
                        created_at__range=[start_date, end_date]
                    )
                
                if 'lead_score_threshold' in criteria:
                    unassigned_leads = unassigned_leads.filter(
                        score__gte=criteria['lead_score_threshold']
                    )
            
            assignment_results = {
                'total_leads': unassigned_leads.count(),
                'assigned_leads': [],
                'unassigned_leads': [],
                'assignment_summary': {}
            }
            
            # Get active territories
            territories = Territory.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).prefetch_related('boundaries')
            
            for lead in unassigned_leads:
                assigned_territory = self._find_best_territory_for_lead(lead, territories, criteria)
                
                if assigned_territory:
                    # Assign lead to territory
                    lead.territory = assigned_territory
                    lead.save(update_fields=['territory'])
                    
                    # Create assignment record
                    TerritoryAssignment.objects.create(
                        territory=assigned_territory,
                        lead=lead,
                        assignment_method='auto',
                        assigned_by=self.user,
                        effective_date=timezone.now(),
                        is_active=True,
                        tenant=self.tenant,
                        metadata={
                            'auto_assignment_criteria': criteria or {},
                            'assignment_score': self._calculate_assignment_score(lead, assigned_territory)
                        }
                    )
                    
                    assignment_results['assigned_leads'].append({
                        'lead_id': lead.id,
                        'lead_name': lead.full_name,
                        'territory_id': assigned_territory.id,
                        'territory_name': assigned_territory.name,
                        'assignment_reason': self._get_assignment_reason(lead, assigned_territory)
                    })
                    
                    # Update summary
                    territory_name = assigned_territory.name
                    if territory_name not in assignment_results['assignment_summary']:
                        assignment_results['assignment_summary'][territory_name] = 0
                    assignment_results['assignment_summary'][territory_name] += 1
                    
                else:
                    assignment_results['unassigned_leads'].append({
                        'lead_id': lead.id,
                        'lead_name': lead.full_name,
                        'reason': 'No suitable territory found'
                    })
            
            self.log_activity(
                'leads_auto_assigned',
                'Territory',
                None,
                {
                    'total_processed': assignment_results['total_leads'],
                    'successfully_assigned': len(assignment_results['assigned_leads']),
                    'criteria': criteria or {}
                }
            )
            
            return assignment_results
            
        except Exception as e:
            logger.error(f"Auto assignment failed: {e}", exc_info=True)
            raise TerritoryException(f"Auto assignment failed: {str(e)}")
    
    # ============================================================================
    # TERRITORY PERFORMANCE ANALYTICS
    # ============================================================================
    
    def get_territory_performance_report(self, territory_id: int = None,
                                       period: str = '30d',
                                       include_forecasts: bool = True) -> Dict:
        """
        Generate comprehensive territory performance report
        
        Args:
            territory_id: Specific territory (all territories if None)
            period: Analysis period ('7d', '30d', '90d', '1y')
            include_forecasts: Include performance forecasts
        
        Returns:
            Performance report data
        """
        try:
            # Calculate date range
            period_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = period_days.get(period, 30)
            start_date = timezone.now() - timedelta(days=days)
            
            # Build territory query
            territories_query = Territory.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).select_related('manager').prefetch_related('team_memberships__user')
            
            if territory_id:
                territories_query = territories_query.filter(id=territory_id)
            
            performance_data = []
            
            for territory in territories_query:
                # Core metrics
                metrics = self._calculate_territory_metrics(territory, start_date)
                
                # Performance trends
                trends = self._calculate_territory_trends(territory, start_date, days)
                
                # Team performance
                team_performance = self._analyze_team_performance(territory, start_date)
                
                # Geographic analysis
                geographic_analysis = self._analyze_territory_geography(territory)
                
                # Forecasts (if requested)
                forecasts = {}
                if include_forecasts:
                    forecasts = self._generate_territory_forecasts(territory, metrics, trends)
                
                territory_data = {
                    'territory_id': territory.id,
                    'territory_name': territory.name,
                    'territory_type': territory.territory_type,
                    'manager': {
                        'id': territory.manager.id,
                        'name': territory.manager.get_full_name()
                    } if territory.manager else None,
                    'period': period,
                    'metrics': metrics,
                    'trends': trends,
                    'team_performance': team_performance,
                    'geographic_analysis': geographic_analysis,
                    'forecasts': forecasts
                }
                
                performance_data.append(territory_data)
            
            # Calculate summary statistics
            summary = self._calculate_performance_summary(performance_data)
            
            return {
                'territories': performance_data,
                'summary': summary,
                'period': period,
                'generated_at': timezone.now().isoformat(),
                'total_territories': len(performance_data)
            }
            
        except Exception as e:
            logger.error(f"Performance report generation failed: {e}", exc_info=True)
            raise TerritoryException(f"Performance report failed: {str(e)}")
    
    def optimize_territory_boundaries(self, optimization_criteria: Dict) -> Dict:
        """
        Optimize territory boundaries using AI and business rules
        
        Args:
            optimization_criteria: Optimization parameters
        
        Returns:
            Optimization results and recommendations
        """
        try:
            self.validate_user_permission('crm.change_territory')
            
            # Run optimization analysis
            optimization_results = self.optimizer.optimize_territories(optimization_criteria)
            
            # Generate actionable recommendations
            recommendations = self._generate_optimization_recommendations(optimization_results)
            
            # Calculate impact projections
            impact_projections = self._calculate_optimization_impact(
                optimization_results, 
                optimization_criteria
            )
            
            # Store optimization analysis
            self._store_optimization_analysis(optimization_results, recommendations)
            
            self.log_activity(
                'territory_optimization_analyzed',
                'Territory',
                None,
                {
                    'optimization_type': optimization_criteria.get('type', 'unknown'),
                    'territories_analyzed': optimization_results.get('total_territories', 0),
                    'recommendations_count': len(recommendations)
                }
            )
            
            return {
                'optimization_results': optimization_results,
                'recommendations': recommendations,
                'impact_projections': impact_projections,
                'next_steps': self._get_optimization_next_steps(optimization_results),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Territory optimization failed: {e}", exc_info=True)
            raise TerritoryException(f"Optimization failed: {str(e)}")
    
    # ============================================================================
    # TEAM MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_sales_team(self, team_assignments: List[Dict] = None) -> Team:
        """
        Create sales team with member assignments and performance tracking
        
        Args:
            member_assignments: List of member assignments with roles
        
        Returns:
            Team instance
        """
        try:
            self.validate_user_permission('crm.add_team')
            
            # Create team
            team = Team.objects.create(
                tenant=self.tenant,
                name=team_data['name'],
                description=team_data.get('description', ''),
                team_type=team_data.get('team_type', 'SALES'),
                manager_id=team_data.get('manager_id'),
                is_active=team_data.get('is_active', True),
                settings={
                    'collaboration_enabled': team_data.get('collaboration_enabled', True),
                    'performance_tracking': team_data.get('performance_tracking', True),
                    'shared_leads': team_data.get('shared_leads', False),
                    'commission_sharing': team_data.get('commission_sharing', False)
                },
                created_by=self.user
            )
            
            # Add team members
            if member_assignments:
                for assignment in member_assignments:
                    TeamMembership.objects.create(
                        team=team,
                        user_id=assignment['user_id'],
                        role=assignment.get('role', 'MEMBER'),
                        joined_date=assignment.get('joined_date', timezone.now().date()),
                        is_active=True,
                        tenant=self.tenant
                    )
            
            # Initialize team performance tracking
            self._initialize_team_performance_tracking(team)
            
            self.log_activity(
                'sales_team_created',
                'Team',
                team.id,
                {
                    'name': team.name,
                    'team_type': team.team_type,
                    'member_count': len(member_assignments) if member_assignments else 0
                }
            )
            
            return team
            
        except Exception as e:
            logger.error(f"Team creation failed: {e}", exc_info=True)
            raise TerritoryException(f"Team creation failed: {str(e)}")
    
    def get_team_performance_analytics(self, team_id: int, period: str = '30d') -> Dict:
        """
        Get comprehensive team performance analytics
        
        Args:
            team_id: Team ID
            period: Analysis period
        
        Returns:
            Team performance data
        """
        try:
            team = Team.objects.get(id=team_id, tenant=self.tenant)
            
            # Calculate date range
            period_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = period_days.get(period, 30)
            start_date = timezone.now() - timedelta(days=days)
            
            # Get team members
            team_members = team.memberships.filter(
                is_active=True
            ).select_related('user')
            
            # Calculate team metrics
            team_metrics = {
                'member_count': team_members.count(),
                'total_revenue': 0,
                'total_opportunities': 0,
                'total_activities': 0,
                'average_deal_size': 0,
                'conversion_rate': 0,
                'activity_completion_rate': 0
            }
            
            member_performance = []
            
            for membership in team_members:
                user = membership.user
                
                # User opportunities in period
                user_opportunities = Opportunity.objects.filter(
                    owner=user,
                    tenant=self.tenant,
                    created_at__gte=start_date
                )
                
                won_opportunities = user_opportunities.filter(is_won=True)
                revenue = won_opportunities.aggregate(Sum('amount'))['amount__sum'] or 0
                
                # User activities
                user_activities = Activity.objects.filter(
                    assigned_to=user,
                    tenant=self.tenant,
                    created_at__gte=start_date
                )
                
                completed_activities = user_activities.filter(status='COMPLETED').count()
                total_activities = user_activities.count()
                
                member_data = {
                    'user_id': user.id,
                    'name': user.get_full_name(),
                    'role': membership.role,
                    'revenue': revenue,
                    'opportunities_count': user_opportunities.count(),
                    'won_opportunities': won_opportunities.count(),
                    'activities_completed': completed_activities,
                    'activities_total': total_activities,
                    'completion_rate': (completed_activities / total_activities * 100) if total_activities > 0 else 0,
                    'average_deal_size': revenue / won_opportunities.count() if won_opportunities.count() > 0 else 0
                }
                
                member_performance.append(member_data)
                
                # Update team totals
                team_metrics['total_revenue'] += revenue
                team_metrics['total_opportunities'] += user_opportunities.count()
                team_metrics['total_activities'] += total_activities
            
            # Calculate team averages
            if team_members.count() > 0:
                team_metrics['average_deal_size'] = team_metrics['total_revenue'] / team_members.count()
            
            # Team collaboration metrics
            collaboration_metrics = self._calculate_team_collaboration_metrics(team, start_date)
            
            return {
                'team_id': team.id,
                'team_name': team.name,
                'period': period,
                'team_metrics': team_metrics,
                'member_performance': member_performance,
                'collaboration_metrics': collaboration_metrics,
                'generated_at': timezone.now().isoformat()
            }
            
        except Team.DoesNotExist:
            raise TerritoryException("Team not found")
        except Exception as e:
            logger.error(f"Team performance analytics failed: {e}", exc_info=True)
            raise TerritoryException(f"Team analytics failed: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _create_territory_boundaries(self, territory: Territory, boundaries: List[Dict]):
        """Create geographic boundaries for territory"""
        try:
            for boundary_data in boundaries:
                boundary_type = boundary_data.get('type', 'polygon')
                
                if boundary_type == 'polygon':
                    # Create polygon from coordinates
                    coordinates = boundary_data['coordinates']
                    polygon = Polygon(coordinates)
                    
                    TerritoryBoundary.objects.create(
                        territory=territory,
                        boundary_type='POLYGON',
                        geometry=polygon,
                        name=boundary_data.get('name', f"{territory.name} Boundary"),
                        description=boundary_data.get('description', ''),
                        tenant=self.tenant
                    )
                
                elif boundary_type == 'circle':
                    # Create circular boundary
                    center = Point(boundary_data['center']['lng'], boundary_data['center']['lat'])
                    radius = boundary_data['radius']  # in meters
                    
                    # Create approximate polygon for circle
                    circle_polygon = center.buffer(radius / 111320)  # Rough conversion to degrees
                    
                    TerritoryBoundary.objects.create(
                        territory=territory,
                        boundary_type='CIRCLE',
                        geometry=circle_polygon,
                        name=boundary_data.get('name', f"{territory.name} Circle"),
                        description=f"Circular boundary with radius {radius}m",
                        metadata={'center': boundary_data['center'], 'radius': radius},
                        tenant=self.tenant
                    )
                
        except Exception as e:
            logger.error(f"Boundary creation failed: {e}")
            raise TerritoryException(f"Boundary creation failed: {str(e)}")
    
    def _assign_team_members(self, territory: Territory, assignments: List[Dict]):
        """Assign team members to territory"""
        for assignment in assignments:
            TeamMembership.objects.create(
                team=territory,  # Territory can act as a team
                user_id=assignment['user_id'],
                role=assignment.get('role', 'SALES_REP'),
                territory=territory,
                is_active=True,
                tenant=self.tenant
            )
    
    def _find_best_territory_for_lead(self, lead: 'Lead', territories, criteria: Dict) -> Optional[Territory]:
        """Find the best territory for a lead using multiple factors"""
        best_territory = None
        best_score = 0
        
        for territory in territories:
            score = 0
            
            # Geographic proximity (if lead has location)
            if hasattr(lead, 'latitude') and hasattr(lead, 'longitude') and lead.latitude and lead.longitude:
                if territory.boundaries.exists():
                    lead_point = Point(lead.longitude, lead.latitude)
                    for boundary in territory.boundaries.filter(is_active=True):
                        if boundary.geometry.contains(lead_point):
                            score += 50  # High score for geographic match
                            break
            
            # Workload balance
            territory_lead_count = Lead.objects.filter(territory=territory).count()
            if territory_lead_count < 20:  # Adjust threshold as needed
                score += (20 - territory_lead_count)
            
            # Lead source affinity
            if criteria and 'preferred_sources' in criteria:
                if lead.source_id in criteria['preferred_sources'].get(territory.id, []):
                    score += 25
            
            # Manager availability
            if territory.manager and hasattr(territory.manager, 'crm_profile'):
                if territory.manager.crm_profile.is_active:
                    score += 10
            
            if score > best_score:
                best_score = score
                best_territory = territory
        
        return best_territory
    
    def _calculate_territory_metrics(self, territory: Territory, start_date: datetime) -> Dict:
        """Calculate comprehensive territory metrics"""
        # Accounts
        total_accounts = territory.accounts.filter(is_active=True).count()
        new_accounts = territory.accounts.filter(created_at__gte=start_date).count()
        
        # Opportunities
        opportunities = territory.opportunities.filter(created_at__gte=start_date)
        total_opportunities = opportunities.count()
        won_opportunities = opportunities.filter(is_won=True)
        revenue = won_opportunities.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Leads
        leads = territory.leads.filter(created_at__gte=start_date)
        total_leads = leads.count()
        converted_leads = leads.filter(converted_opportunity__isnull=False).count()
        
        # Activities
        activities = Activity.objects.filter(
            territory=territory,
            created_at__gte=start_date
        )
        total_activities = activities.count()
        completed_activities = activities.filter(status='COMPLETED').count()
        
        return {
            'accounts': {
                'total': total_accounts,
                'new_in_period': new_accounts
            },
            'opportunities': {
                'total': total_opportunities,
                'won': won_opportunities.count(),
                'revenue': revenue,
                'average_deal_size': revenue / won_opportunities.count() if won_opportunities.count() > 0 else 0,
                'win_rate': (won_opportunities.count() / total_opportunities * 100) if total_opportunities > 0 else 0
            },
            'leads': {
                'total': total_leads,
                'converted': converted_leads,
                'conversion_rate': (converted_leads / total_leads * 100) if total_leads > 0 else 0
            },
            'activities': {
                'total': total_activities,
                'completed': completed_activities,
                'completion_rate': (completed_activities / total_activities * 100) if total_activities > 0 else 0
            }
        }
    
    def _get_territory_performance_summary(self, territory: Territory) -> Dict:
        """Get quick performance summary for territory"""
        last_30_days = timezone.now() - timedelta(days=30)
        
        return {
            'accounts_count': territory.accounts.filter(is_active=True).count(),
            'opportunities_count': territory.opportunities.filter(is_closed=False).count(),
            'pipeline_value': territory.opportunities.filter(is_closed=False).aggregate(
                Sum('amount'))['amount__sum'] or 0,
            'monthly_revenue': territory.opportunities.filter(
                is_won=True,
                closed_date__gte=last_30_days
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'team_size': territory.team_memberships.filter(is_active=True).count()
        }