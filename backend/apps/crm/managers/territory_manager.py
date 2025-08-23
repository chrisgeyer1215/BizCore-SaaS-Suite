"""
Territory Manager - Sales Territory Management
Advanced territory and team performance management
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class TerritoryManager(AnalyticsManager):
    """
    Advanced Territory Manager
    Territory management and performance analytics
    """
    
    def active_territories(self):
        """Get active territories"""
        return self.filter(is_active=True)
    
    def by_manager(self, manager):
        """Get territories managed by specific user"""
        return self.filter(manager=manager)
    
    def by_parent_territory(self, parent):
        """Get child territories of parent territory"""
        return self.filter(parent_territory=parent)
    
    def root_territories(self):
        """Get root level territories (no parent)"""
        return self.filter(parent_territory__isnull=True)
    
    def get_territory_hierarchy(self, tenant):
        """Get complete territory hierarchy"""
        territories = self.for_tenant(tenant).filter(is_active=True)
        
        hierarchy = {}
        for territory in territories:
            if not territory.parent_territory:
                # Root territory
                hierarchy[territory.id] = {
                    'territory': territory,
                    'children': [],
                    'level': 0
                }
        
        # Build hierarchy recursively
        def add_children(parent_id, level):
            children = territories.filter(parent_territory_id=parent_id)
            child_data = []
            
            for child in children:
                child_info = {
                    'territory': child,
                    'children': add_children(child.id, level + 1),
                    'level': level + 1
                }
                child_data.append(child_info)
            
            return child_data
        
        # Add children to each root territory
        for root_id in hierarchy:
            hierarchy[root_id]['children'] = add_children(root_id, 1)
        
        return hierarchy
    
    def get_territory_performance(self, tenant, days=30):
        """Get performance metrics for all territories"""
        from ..models import Lead, Opportunity, Activity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        territories = self.for_tenant(tenant).filter(is_active=True)
        
        performance_data = []
        for territory in territories:
            # Get users in this territory
            territory_users = territory.teams.filter(is_active=True).values_list(
                'members__user_id', flat=True
            ).distinct()
            
            # Lead metrics
            lead_metrics = Lead.objects.filter(
                tenant=tenant,
                assigned_to__in=territory_users,
                created_at__range=[start_date, end_date]
            ).aggregate(
                total_leads=Count('id'),
                qualified_leads=Count('id', filter=Q(status='qualified')),
                converted_leads=Count('id', filter=Q(status='converted'))
            )
            
            # Opportunity metrics
            opp_metrics = Opportunity.objects.filter(
                tenant=tenant,
                assigned_to__in=territory_users
            ).aggregate(
                total_opportunities=Count('id'),
                open_opportunities=Count('id', filter=Q(stage__is_closed=False)),
                won_opportunities=Count('id', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                )),
                pipeline_value=Sum('value', filter=Q(stage__is_closed=False)),
                won_revenue=Sum('value', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                ))
            )
            
            # Activity metrics
            activity_metrics = Activity.objects.filter(
                tenant=tenant,
                assigned_to__in=territory_users,
                created_at__range=[start_date, end_date]
            ).aggregate(
                total_activities=Count('id'),
                completed_activities=Count('id', filter=Q(status='completed'))
            )
            
            # Team metrics
            team_count = territory.teams.filter(is_active=True).count()
            total_members = territory.teams.filter(is_active=True).aggregate(
                member_count=Count('members', filter=Q(members__is_active=True))
            )['member_count'] or 0
            
            performance_data.append({
                'territory': {
                    'id': territory.id,
                    'name': territory.name,
                    'manager': territory.manager.get_full_name() if territory.manager else None
                },
                'team_metrics': {
                    'team_count': team_count,
                    'total_members': total_members
                },
                'lead_metrics': lead_metrics,
                'opportunity_metrics': opp_metrics,
                'activity_metrics': activity_metrics,
                'performance_score': self._calculate_territory_performance_score(
                    lead_metrics, opp_metrics, activity_metrics
                )
            })
        
        return performance_data
    
    def _calculate_territory_performance_score(self, leads, opps, activities):
        """Calculate performance score for territory (0-100)"""
        score = 0
        
        # Lead performance (30 points)
        if leads['total_leads'] > 0:
            lead_conversion_rate = (leads['converted_leads'] / leads['total_leads']) * 100
            score += min(lead_conversion_rate * 0.3, 30)
        
        # Opportunity performance (40 points) 
        if opps['total_opportunities'] > 0:
            win_rate = (opps['won_opportunities'] / opps['total_opportunities']) * 100
            score += min(win_rate * 0.4, 40)
        
        # Activity performance (30 points)
        if activities['total_activities'] > 0:
            completion_rate = (activities['completed_activities'] / activities['total_activities']) * 100
            score += min(completion_rate * 0.3, 30)
        
        return round(score, 2)
    
    def get_territory_coverage_analysis(self, tenant):
        """Analyze territory coverage and gaps"""
        from ..models import Lead, Account
        
        # Get all territories with their assigned accounts/leads
        coverage_data = []
        territories = self.for_tenant(tenant).filter(is_active=True)
        
        for territory in territories:
            # Get users in territory
            territory_users = territory.teams.filter(is_active=True).values_list(
                'members__user_id', flat=True
            ).distinct()
            
            # Assigned accounts
            assigned_accounts = Account.objects.filter(
                tenant=tenant,
                assigned_to__in=territory_users
            ).count()
            
            # Assigned leads
            assigned_leads = Lead.objects.filter(
                tenant=tenant,
                assigned_to__in=territory_users
            ).count()
            
            # Territory geographic info (if available)
            geographic_info = {
                'countries': territory.countries.split(',') if territory.countries else [],
                'states': territory.states.split(',') if territory.states else [],
                'cities': territory.cities.split(',') if territory.cities else []
            }
            
            coverage_data.append({
                'territory': {
                    'id': territory.id,
                    'name': territory.name,
                    'manager': territory.manager.get_full_name() if territory.manager else None
                },
                'coverage': {
                    'assigned_accounts': assigned_accounts,
                    'assigned_leads': assigned_leads,
                    'team_size': len(territory_users),
                    'geographic_coverage': geographic_info
                },
                'workload_ratio': {
                    'accounts_per_rep': assigned_accounts / len(territory_users) if territory_users else 0,
                    'leads_per_rep': assigned_leads / len(territory_users) if territory_users else 0
                }
            })
        
        # Identify coverage gaps
        unassigned_accounts = Account.objects.filter(
            tenant=tenant,
            assigned_to__isnull=True
        ).count()
        
        unassigned_leads = Lead.objects.filter(
            tenant=tenant,
            assigned_to__isnull=True
        ).count()
        
        return {
            'territory_coverage': coverage_data,
            'coverage_gaps': {
                'unassigned_accounts': unassigned_accounts,
                'unassigned_leads': unassigned_leads
            }
        }
    
    def optimize_territory_assignments(self, tenant, optimization_rules):
        """
        Optimize territory assignments based on rules
        
        optimization_rules format:
        {
            'max_accounts_per_rep': 50,
            'max_leads_per_rep': 100,
            'rebalance_threshold': 0.3,  # 30% imbalance triggers rebalancing
            'geographic_priority': True
        }
        """
        from ..models import Account, Lead
        
        territories = self.for_tenant(tenant).filter(is_active=True)
        recommendations = []
        
        for territory in territories:
            territory_users = list(territory.teams.filter(is_active=True).values_list(
                'members__user_id', flat=True
            ).distinct())
            
            if not territory_users:
                continue
            
            # Current workload per user
            workloads = {}
            for user_id in territory_users:
                accounts = Account.objects.filter(
                    tenant=tenant,
                    assigned_to_id=user_id
                ).count()
                leads = Lead.objects.filter(
                    tenant=tenant,
                    assigned_to_id=user_id
                ).count()
                
                workloads[user_id] = {
                    'accounts': accounts,
                    'leads': leads,
                    'total_workload': accounts + leads
                }
            
            # Check for imbalances
            workload_values = [w['total_workload'] for w in workloads.values()]
            if workload_values:
                max_workload = max(workload_values)
                min_workload = min(workload_values)
                avg_workload = sum(workload_values) / len(workload_values)
                
                # Calculate imbalance ratio
                if avg_workload > 0:
                    imbalance_ratio = (max_workload - min_workload) / avg_workload
                else:
                    imbalance_ratio = 0
                
                if imbalance_ratio > optimization_rules.get('rebalance_threshold', 0.3):
                    # Find overloaded and underloaded users
                    overloaded_users = [
                        user_id for user_id, workload in workloads.items()
                        if workload['total_workload'] > avg_workload * 1.2
                    ]
                    underloaded_users = [
                        user_id for user_id, workload in workloads.items()
                        if workload['total_workload'] < avg_workload * 0.8
                    ]
                    
                    recommendations.append({
                        'territory_id': territory.id,
                        'territory_name': territory.name,
                        'issue': 'workload_imbalance',
                        'imbalance_ratio': round(imbalance_ratio, 3),
                        'overloaded_users': overloaded_users,
                        'underloaded_users': underloaded_users,
                        'recommended_action': 'redistribute_assignments'
                    })
        
        return {
            'optimization_recommendations': recommendations,
            'territories_analyzed': len(territories)
        }
    
    def bulk_reassign_territories(self, tenant, reassignment_rules):
        """
        Bulk reassign accounts/leads to different territories
        
        reassignment_rules format:
        {
            'source_territory_id': 1,
            'target_territory_id': 2,
            'criteria': {
                'account_type': 'standard',
                'country': 'US',
                'max_accounts': 20
            }
        }
        """
        from ..models import Account, Lead
        
        reassignment_results = []
        
        for rule in reassignment_rules:
            source_territory = self.get(id=rule['source_territory_id'])
            target_territory = self.get(id=rule['target_territory_id'])
            
            # Get target territory users for assignment
            target_users = list(target_territory.teams.filter(is_active=True).values_list(
                'members__user_id', flat=True
            ).distinct())
            
            if not target_users:
                reassignment_results.append({
                    'rule': rule,
                    'status': 'failed',
                    'reason': 'No users in target territory'
                })
                continue
            
            # Find accounts to reassign based on criteria
            source_users = list(source_territory.teams.filter(is_active=True).values_list(
                'members__user_id', flat=True
            ).distinct())
            
            accounts_query = Account.objects.filter(
                tenant=tenant,
                assigned_to__in=source_users
            )
            
            # Apply criteria filters
            criteria = rule.get('criteria', {})
            if 'account_type' in criteria:
                accounts_query = accounts_query.filter(account_type=criteria['account_type'])
            if 'country' in criteria:
                accounts_query = accounts_query.filter(billing_country=criteria['country'])
            
            # Limit number of accounts
            max_accounts = criteria.get('max_accounts', 999999)
            accounts_to_reassign = list(accounts_query[:max_accounts])
            
            # Reassign accounts using round-robin
            reassigned_count = 0
            for i, account in enumerate(accounts_to_reassign):
                target_user_id = target_users[i % len(target_users)]
                account.assigned_to_id = target_user_id
                account.save(update_fields=['assigned_to', 'modified_at'])
                reassigned_count += 1
            
            reassignment_results.append({
                'rule': rule,
                'status': 'success',
                'accounts_reassigned': reassigned_count,
                'source_territory': source_territory.name,
                'target_territory': target_territory.name
            })
        
        return {
            'reassignment_results': reassignment_results,
            'total_rules_processed': len(reassignment_rules)
        }


class TeamManager(AnalyticsManager):
    """
    Team Manager for CRM Teams
    Team performance and management
    """
    
    def active_teams(self):
        """Get active teams"""
        return self.filter(is_active=True)
    
    def by_territory(self, territory):
        """Get teams in specific territory"""
        return self.filter(territory=territory)
    
    def by_manager(self, manager):
        """Get teams managed by specific user"""
        return self.filter(manager=manager)
    
    def get_team_performance_summary(self, tenant, days=30):
        """Get performance summary for all teams"""
        from ..models import Lead, Opportunity, Activity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        teams = self.for_tenant(tenant).filter(is_active=True)
        team_performance = []
        
        for team in teams:
            # Get team members
            team_members = team.members.filter(is_active=True).values_list(
                'user_id', flat=True
            )
            
            if not team_members:
                continue
            
            # Performance metrics
            performance = {
                'team': {
                    'id': team.id,
                    'name': team.name,
                    'manager': team.manager.get_full_name() if team.manager else None,
                    'territory': team.territory.name if team.territory else None,
                    'member_count': len(team_members)
                },
                'metrics': Lead.objects.filter(
                    tenant=tenant,
                    assigned_to__in=team_members,
                    created_at__range=[start_date, end_date]
                ).aggregate(
                    leads_created=Count('id'),
                    leads_qualified=Count('id', filter=Q(status='qualified')),
                    leads_converted=Count('id', filter=Q(status='converted'))
                )
            }
            
            # Add opportunity metrics
            opp_metrics = Opportunity.objects.filter(
                tenant=tenant,
                assigned_to__in=team_members
            ).aggregate(
                opportunities_created=Count('id', filter=Q(
                    created_at__range=[start_date, end_date]
                )),
                opportunities_won=Count('id', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                )),
                revenue_generated=Sum('value', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                ))
            )
            performance['metrics'].update(opp_metrics)
            
            # Add activity metrics
            activity_metrics = Activity.objects.filter(
                tenant=tenant,
                assigned_to__in=team_members,
                created_at__range=[start_date, end_date]
            ).aggregate(
                activities_completed=Count('id', filter=Q(status='completed')),
                calls_made=Count('id', filter=Q(activity_type='call')),
                emails_sent=Count('id', filter=Q(activity_type='email'))
            )
            performance['metrics'].update(activity_metrics)
            
            team_performance.append(performance)
        
        return team_performance
    
    def get_team_collaboration_metrics(self, tenant, team_id=None):
        """Analyze team collaboration patterns"""
        from ..models import Activity
        
        teams_query = self.for_tenant(tenant).filter(is_active=True)
        if team_id:
            teams_query = teams_query.filter(id=team_id)
        
        collaboration_data = []
        
        for team in teams_query:
            team_members = list(team.members.filter(is_active=True).values_list(
                'user_id', flat=True
            ))
            
            # Shared activities (activities involving multiple team members)
            shared_activities = Activity.objects.filter(
                tenant=tenant,
                assigned_to__in=team_members,
                participants__in=team_members
            ).distinct().count()
            
            # Cross-team activities
            cross_team_activities = Activity.objects.filter(
                tenant=tenant,
                assigned_to__in=team_members
            ).exclude(
                participants__in=team_members
            ).distinct().count()
            
            collaboration_data.append({
                'team': {
                    'id': team.id,
                    'name': team.name,
                    'member_count': len(team_members)
                },
                'collaboration_metrics': {
                    'shared_activities': shared_activities,
                    'cross_team_activities': cross_team_activities,
                    'collaboration_ratio': shared_activities / (shared_activities + cross_team_activities) if (shared_activities + cross_team_activities) > 0 else 0
                }
            })
        
        return collaboration_data
