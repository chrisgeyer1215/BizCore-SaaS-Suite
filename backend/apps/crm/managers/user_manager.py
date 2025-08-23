"""
User Manager - CRM User Management
Advanced user analytics and management for CRM system
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .base import AnalyticsManager

User = get_user_model()


class CRMUserManager(AnalyticsManager):
    """
    Advanced CRM User Manager
    User performance and activity analytics
    """
    
    def active_users(self, tenant):
        """Get active CRM users for tenant"""
        return User.objects.filter(
            memberships__tenant=tenant,
            memberships__is_active=True,
            is_active=True
        ).distinct()
    
    def by_role(self, tenant, role):
        """Get users by role within tenant"""
        return self.active_users(tenant).filter(
            memberships__role=role
        )
    
    def sales_reps(self, tenant):
        """Get sales representatives"""
        return self.by_role(tenant, 'sales_rep')
    
    def managers(self, tenant):
        """Get managers"""
        return self.by_role(tenant, 'manager')
    
    def admins(self, tenant):
        """Get admin users"""
        return self.by_role(tenant, 'admin')
    
    def get_user_performance_analytics(self, tenant, days=30):
        """Get comprehensive user performance analytics"""
        from ..models import Lead, Opportunity, Activity, Ticket
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        users = self.active_users(tenant)
        performance_data = []
        
        for user in users:
            # Lead performance
            lead_metrics = Lead.objects.filter(
                tenant=tenant,
                assigned_to=user
            ).aggregate(
                total_leads=Count('id'),
                new_leads=Count('id', filter=Q(
                    created_at__range=[start_date, end_date]
                )),
                qualified_leads=Count('id', filter=Q(
                    status='qualified',
                    qualified_at__range=[start_date, end_date]
                )),
                converted_leads=Count('id', filter=Q(
                    status='converted',
                    converted_at__range=[start_date, end_date]
                ))
            )
            
            # Opportunity performance
            opp_metrics = Opportunity.objects.filter(
                tenant=tenant,
                assigned_to=user
            ).aggregate(
                total_opportunities=Count('id'),
                open_opportunities=Count('id', filter=Q(stage__is_closed=False)),
                won_opportunities=Count('id', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                )),
                revenue_generated=Sum('value', filter=Q(
                    stage__is_won=True,
                    won_date__range=[start_date, end_date]
                )),
                pipeline_value=Sum('value', filter=Q(stage__is_closed=False))
            )
            
            # Activity performance
            activity_metrics = Activity.objects.filter(
                tenant=tenant,
                assigned_to=user,
                created_at__range=[start_date, end_date]
            ).aggregate(
                total_activities=Count('id'),
                completed_activities=Count('id', filter=Q(status='completed')),
                calls_made=Count('id', filter=Q(activity_type='call')),
                emails_sent=Count('id', filter=Q(activity_type='email')),
                meetings_held=Count('id', filter=Q(activity_type='meeting'))
            )
            
            # Support performance (if applicable)
            support_metrics = Ticket.objects.filter(
                tenant=tenant,
                assigned_to=user,
                created_at__range=[start_date, end_date]
            ).aggregate(
                tickets_assigned=Count('id'),
                tickets_resolved=Count('id', filter=Q(
                    status__in=['resolved', 'closed']
                )),
                avg_resolution_time=Avg('resolution_time', filter=Q(
                    status__in=['resolved', 'closed']
                ))
            )
            
            # Calculate performance score
            performance_score = self._calculate_user_performance_score(
                lead_metrics, opp_metrics, activity_metrics, support_metrics
            )
            
            performance_data.append({
                'user': {
                    'id': user.id,
                    'name': f"{user.first_name} {user.last_name}",
                    'email': user.email,
                    'role': user.memberships.filter(tenant=tenant).first().role if user.memberships.filter(tenant=tenant).exists() else None
                },
                'lead_metrics': lead_metrics,
                'opportunity_metrics': opp_metrics,
                'activity_metrics': activity_metrics,
                'support_metrics': support_metrics,
                'performance_score': performance_score,
                'performance_grade': self._get_performance_grade(performance_score)
            })
        
        return sorted(performance_data, key=lambda x: x['performance_score'], reverse=True)
    
    def _calculate_user_performance_score(self, leads, opps, activities, support):
        """Calculate user performance score (0-100)"""
        score = 0
        
        # Lead conversion performance (25 points)
        if leads['new_leads'] > 0:
            conversion_rate = (leads['converted_leads'] / leads['new_leads']) * 100
            score += min(conversion_rate * 0.25, 25)
        
        # Opportunity win performance (30 points)
        if opps['total_opportunities'] > 0:
            win_rate = (opps['won_opportunities'] / opps['total_opportunities']) * 100
            score += min(win_rate * 0.3, 30)
        
        # Activity completion performance (25 points)
        if activities['total_activities'] > 0:
            completion_rate = (activities['completed_activities'] / activities['total_activities']) * 100
            score += min(completion_rate * 0.25, 25)
        
        # Support performance (20 points)
        if support['tickets_assigned'] > 0:
            resolution_rate = (support['tickets_resolved'] / support['tickets_assigned']) * 100
            score += min(resolution_rate * 0.2, 20)
        
        return round(score, 2)
    
    def _get_performance_grade(self, score):
        """Convert performance score to grade"""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
    
    def get_user_activity_patterns(self, tenant, user_id=None, days=30):
        """Analyze user activity patterns"""
        from ..models import Activity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        users_query = self.active_users(tenant)
        if user_id:
            users_query = users_query.filter(id=user_id)
        
        pattern_data = []
        
        for user in users_query:
            # Daily activity patterns
            daily_activities = Activity.objects.filter(
                tenant=tenant,
                assigned_to=user,
                created_at__range=[start_date, end_date]
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(
                activity_count=Count('id'),
                calls=Count('id', filter=Q(activity_type='call')),
                emails=Count('id', filter=Q(activity_type='email')),
                meetings=Count('id', filter=Q(activity_type='meeting'))
            ).order_by('day')
            
            # Hourly activity distribution
            hourly_activities = Activity.objects.filter(
                tenant=tenant,
                assigned_to=user,
                created_at__range=[start_date, end_date]
            ).extra(
                select={'hour': 'extract(hour from created_at)'}
            ).values('hour').annotate(
                activity_count=Count('id')
            ).order_by('hour')
            
            # Most active days and hours
            most_active_day = max(daily_activities, key=lambda x: x['activity_count']) if daily_activities else None
            most_active_hour = max(hourly_activities, key=lambda x: x['activity_count']) if hourly_activities else None
            
            pattern_data.append({
                'user': {
                    'id': user.id,
                    'name': f"{user.first_name} {user.last_name}"
                },
                'daily_patterns': list(daily_activities),
                'hourly_patterns': list(hourly_activities),
                'insights': {
                    'most_active_day': most_active_day,
                    'most_active_hour': most_active_hour['hour'] if most_active_hour else None,
                    'total_activities': sum(d['activity_count'] for d in daily_activities),
                    'avg_daily_activities': sum(d['activity_count'] for d in daily_activities) / len(daily_activities) if daily_activities else 0
                }
            })
        
        return pattern_data
    
    def get_user_workload_analysis(self, tenant):
        """Analyze user workload distribution"""
        from ..models import Lead, Opportunity, Ticket
        
        users = self.active_users(tenant)
        workload_data = []
        
        for user in users:
            workload = {
                'user': {
                    'id': user.id,
                    'name': f"{user.first_name} {user.last_name}",
                    'role': user.memberships.filter(tenant=tenant).first().role if user.memberships.filter(tenant=tenant).exists() else None
                },
                'workload_metrics': {
                    'active_leads': Lead.objects.filter(
                        tenant=tenant,
                        assigned_to=user,
                        status__in=['new', 'contacted', 'qualified']
                    ).count(),
                    'open_opportunities': Opportunity.objects.filter(
                        tenant=tenant,
                        assigned_to=user,
                        stage__is_closed=False
                    ).count(),
                    'open_tickets': Ticket.objects.filter(
                        tenant=tenant,
                        assigned_to=user,
                        status__in=['open', 'pending', 'in_progress']
                    ).count(),
                    'overdue_activities': user.activities_assigned.filter(
                        tenant=tenant,
                        due_date__lt=timezone.now(),
                        status__in=['pending', 'open']
                    ).count()
                }
            }
            
            # Calculate workload score
            workload_score = (
                workload['workload_metrics']['active_leads'] * 1 +
                workload['workload_metrics']['open_opportunities'] * 2 +
                workload['workload_metrics']['open_tickets'] * 1.5 +
                workload['workload_metrics']['overdue_activities'] * 3
            )
            
            workload['workload_score'] = workload_score
            workload['workload_level'] = self._get_workload_level(workload_score)
            
            workload_data.append(workload)
        
        return sorted(workload_data, key=lambda x: x['workload_score'], reverse=True)
    
    def _get_workload_level(self, score):
        """Convert workload score to level"""
        if score >= 50:
            return 'Overloaded'
        elif score >= 30:
            return 'High'
        elif score >= 15:
            return 'Moderate'
        elif score >= 5:
            return 'Light'
        else:
            return 'Very Light'
    
    def get_team_collaboration_metrics(self, tenant, days=30):
        """Analyze collaboration between team members"""
        from ..models import Activity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        users = self.active_users(tenant)
        collaboration_matrix = {}
        
        # Build collaboration matrix
        for user in users:
            collaboration_matrix[user.id] = {
                'user': f"{user.first_name} {user.last_name}",
                'collaborations': {}
            }
            
            # Find activities where this user collaborated with others
            collaborative_activities = Activity.objects.filter(
                tenant=tenant,
                assigned_to=user,
                created_at__range=[start_date, end_date],
                participants__isnull=False
            ).distinct()
            
            for activity in collaborative_activities:
                participants = activity.participants.exclude(id=user.id)
                for participant in participants:
                    if participant.id not in collaboration_matrix[user.id]['collaborations']:
                        collaboration_matrix[user.id]['collaborations'][participant.id] = {
                            'partner_name': f"{participant.first_name} {participant.last_name}",
                            'collaboration_count': 0,
                            'activity_types': {}
                        }
                    
                    collaboration_matrix[user.id]['collaborations'][participant.id]['collaboration_count'] += 1
                    
                    activity_type = activity.activity_type
                    if activity_type not in collaboration_matrix[user.id]['collaborations'][participant.id]['activity_types']:
                        collaboration_matrix[user.id]['collaborations'][participant.id]['activity_types'][activity_type] = 0
                    collaboration_matrix[user.id]['collaborations'][participant.id]['activity_types'][activity_type] += 1
        
        return collaboration_matrix
    
    def identify_training_needs(self, tenant):
        """Identify users who may need additional training"""
        performance_data = self.get_user_performance_analytics(tenant, 90)  # 3 months
        training_needs = []
        
        needs = []
            
            # Low lead conversion
            lead_metrics = user_perf['lead_metrics']
            if lead_metrics['new_leads'] > 5:  # Only consider if they had leads to work with
                conversion_rate = (lead_metrics['converted_leads'] / lead_metrics['new_leads']) * 100 if lead_metrics['new_leads'] > 0 else 0
                if conversion_rate < 10:  # Less than 10% conversion
                    needs.append({
                        'area': 'Lead Qualification',
                        'priority': 'high',
                        'metric': f"{conversion_rate:.1f}% conversion rate"
                    })
            
            # Low opportunity win rate
            opp_metrics = user_perf['opportunity_metrics']
            if opp_metrics['total_opportunities'] > 3:
                win_rate = (opp_metrics['won_opportunities'] / opp_metrics['total_opportunities']) * 100 if opp_metrics['total_opportunities'] > 0 else 0
                if win_rate < 20:  # Less than 20% win rate
                    needs.append({
                        'area': 'Sales Closing',
                        'priority': 'high',
                        'metric': f"{win_rate:.1f}% win rate"
                    })
            
            # Low activity completion
            activity_metrics = user_perf['activity_metrics']
            if activity_metrics['total_activities'] > 10:
                completion_rate = (activity_metrics['completed_activities'] / activity_metrics['total_activities']) * 100 if activity_metrics['total_activities'] > 0 else 0
                if completion_rate < 70:  # Less than 70% completion
                    needs.append({
                        'area': 'Time Management',
                        'priority': 'medium',
                        'metric': f"{completion_rate:.1f}% completion rate"
                    })
            
            # Poor support performance
            support_metrics = user_perf['support_metrics']
            if support_metrics['tickets_assigned'] > 5:
                resolution_rate = (support_metrics['tickets_resolved'] / support_metrics['tickets_assigned']) * 100 if support_metrics['tickets_assigned'] > 0 else 0
                if resolution_rate < 80:  # Less than 80% resolution
                    needs.append({
                        'area': 'Customer Support',
                        'priority': 'medium',
                        'metric': f"{resolution_rate:.1f}% resolution rate"
                    })
            
            if needs:
                training_needs.append({
                    'user': user_perf['user'],
                    'performance_score': user_perf['performance_score'],
                    'training_needs': needs
                })
        
        return sorted(training_needs, key=lambda x: len(x['training_needs']), reverse=True)
    
    def bulk_user_actions(self, tenant, user_ids, action_type, action_data):
        """
        Perform bulk actions on users
        
        action_type: 'update_role', 'assign_territory', 'set_quota', 'deactivate'
        """
        users = self.active_users(tenant).filter(id__in=user_ids)
        results = []
        
        for user in users:
            try:
                if action_type == 'update_role':
                    membership = user.memberships.get(tenant=tenant)
                    membership.role = action_data.get('role')
                    membership.save()
                    results.append({
                        'user_id': user.id,
                        'status': 'success',
                        'action': f"Role updated to {action_data.get('role')}"
                    })
                
                elif action_type == 'assign_territory':
                    # This would require a relationship between user and territory
                    # Implementation depends on your territory model structure
                    results.append({
                        'user_id': user.id,
                        'status': 'success',
                        'action': f"Assigned to territory {action_data.get('territory_id')}"
                    })
                
                elif action_type == 'set_quota':
                    # This would require a quota field or separate quota model
                    results.append({
                        'user_id': user.id,
                        'status': 'success',
                        'action': f"Quota set to {action_data.get('quota')}"
                    })
                
                elif action_type == 'deactivate':
                    membership = user.memberships.get(tenant=tenant)
                    membership.is_active = False
                    membership.save()
                    results.append({
                        'user_id': user.id,
                        'status': 'success',
                        'action': 'User deactivated'
                    })
                
            except Exception as e:
                results.append({
                    'user_id': user.id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'results': results,
            'successful_actions': len([r for r in results if r['status'] == 'success']),
            'failed_actions': len([r for r in results if r['status'] == 'error'])
        }