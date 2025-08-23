"""
Activity Manager - Communication and Task Management
Advanced activity tracking and engagement analytics
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When
from django.utils import timezone
from datetime import timedelta
from .base import AnalyticsManager


class ActivityManager(AnalyticsManager):
    """
    Advanced Activity Manager
    Communication tracking and engagement analytics
    """
    
    def calls(self):
        """Get call activities"""
        return self.filter(activity_type='call')
    
    def emails(self):
        """Get email activities"""
        return self.filter(activity_type='email')
    
    def meetings(self):
        """Get meeting activities"""
        return self.filter(activity_type='meeting')
    
    def tasks(self):
        """Get task activities"""
        return self.filter(activity_type='task')
    
    def completed_activities(self):
        """Get completed activities"""
        return self.filter(status='completed')
    
    def pending_activities(self):
        """Get pending/open activities"""
        return self.filter(status__in=['pending', 'open', 'in_progress'])
    
    def overdue_activities(self):
        """Get overdue activities"""
        return self.filter(
            due_date__lt=timezone.now(),
            status__in=['pending', 'open', 'in_progress']
        )
    
    def today_activities(self):
        """Get today's activities"""
        today = timezone.now().date()
        return self.filter(
            Q(due_date__date=today) | Q(scheduled_at__date=today)
        )
    
    def upcoming_activities(self, days: int = 7):
        """Get upcoming activities"""
        end_date = timezone.now() + timedelta(days=days)
        return self.filter(
            Q(due_date__range=[timezone.now(), end_date]) |
            Q(scheduled_at__range=[timezone.now(), end_date])
        ).filter(
            status__in=['pending', 'open', 'scheduled']
        )
    
    def by_user(self, user):
        """Get activities for specific user"""
        return self.filter(assigned_to=user)
    
    def for_lead(self, lead):
        """Get activities for specific lead"""
        return self.filter(
            entity_type='lead',
            entity_id=lead.id
        )
    
    def for_opportunity(self, opportunity):
        """Get activities for specific opportunity"""
        return self.filter(
            entity_type='opportunity',
            entity_id=opportunity.id
        )
    
    def for_account(self, account):
        """Get activities for specific account"""
        return self.filter(
            entity_type='account',
            entity_id=account.id
        )
    
    def get_activity_summary(self, tenant, days: int = 30):
        """Get comprehensive activity summary"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).aggregate(
            # Total activities
            total_activities=Count('id'),
            completed_activities=Count('id', filter=Q(status='completed')),
            pending_activities=Count('id', filter=Q(status__in=['pending', 'open'])),
            overdue_activities=Count('id', filter=Q(
                due_date__lt=timezone.now(),
                status__in=['pending', 'open']
            )),
            
            # By type
            total_calls=Count('id', filter=Q(activity_type='call')),
            total_emails=Count('id', filter=Q(activity_type='email')),
            total_meetings=Count('id', filter=Q(activity_type='meeting')),
            total_tasks=Count('id', filter=Q(activity_type='task')),
            
            # Completion rates
            call_completion_rate=Avg(Case(
                When(activity_type='call', status='completed', then=1),
                When(activity_type='call', then=0),
                default=0
            )) * 100,
            
            # Duration metrics
            avg_call_duration=Avg('duration', filter=Q(
                activity_type='call',
                duration__isnull=False
            )),
            total_call_time=Sum('duration', filter=Q(activity_type='call')),
            
            # Response times
            avg_response_time=Avg('response_time', filter=Q(
                activity_type='email',
                response_time__isnull=False
            ))
        )
    
    def get_user_activity_stats(self, tenant, user=None, days: int = 30):
        """Get activity statistics by user"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        queryset = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        if user:
            queryset = queryset.filter(assigned_to=user)
            
        return queryset.values(
            'assigned_to__first_name',
            'assigned_to__last_name',
            'assigned_to__id'
        ).annotate(
            # Activity counts
            total_activities=Count('id'),
            completed_activities=Count('id', filter=Q(status='completed')),
            calls_made=Count('id', filter=Q(activity_type='call')),
            emails_sent=Count('id', filter=Q(activity_type='email')),
            meetings_held=Count('id', filter=Q(activity_type='meeting')),
            
            # Performance metrics
            completion_rate=Case(
                When(id__isnull=False, then=Avg(Case(
                    When(status='completed', then=1),
                    default=0
                )) * 100),
                default=0
            ),
            
            # Time metrics
            avg_call_duration=Avg('duration', filter=Q(
                activity_type='call',
                duration__isnull=False
            )),
            total_activity_time=Sum('duration', filter=Q(
                duration__isnull=False
            ))
        ).order_by('-total_activities')
    
    def get_engagement_metrics(self, tenant, entity_type: str = None, days: int = 30):
        """Get engagement metrics by entity type"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        queryset = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        return queryset.values('entity_type', 'entity_id').annotate(
            activity_count=Count('id'),
            last_activity=Max('created_at'),
            first_activity=Min('created_at'),
            call_count=Count('id', filter=Q(activity_type='call')),
            email_count=Count('id', filter=Q(activity_type='email')),
            meeting_count=Count('id', filter=Q(activity_type='meeting')),
            engagement_score=Case(
                When(activity_count__gt=10, then=100),
                When(activity_count__gt=5, then=75),
                When(activity_count__gt=2, then=50),
                default=25
            )
        ).order_by('-activity_count')
    
    def get_communication_frequency(self, tenant, days: int = 30):
        """Analyze communication frequency patterns"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get daily activity counts
        daily_activities = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            total_activities=Count('id'),
            calls=Count('id', filter=Q(activity_type='call')),
            emails=Count('id', filter=Q(activity_type='email')),
            meetings=Count('id', filter=Q(activity_type='meeting'))
        ).order_by('day')
        
        return list(daily_activities)
    
    def get_response_time_analysis(self, tenant, days: int = 30):
        """Analyze email and call response times"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date],
            activity_type__in=['email', 'call'],
            response_time__isnull=False
        ).aggregate(
            avg_response_time=Avg('response_time'),
            min_response_time=Min('response_time'),
            max_response_time=Max('response_time'),
            
            # Response time buckets
            responses_under_1h=Count('id', filter=Q(response_time__lt=60)),
            responses_1_4h=Count('id', filter=Q(response_time__range=[60, 240])),
            responses_4_24h=Count('id', filter=Q(response_time__range=[240, 1440])),
            responses_over_24h=Count('id', filter=Q(response_time__gt=1440)),
            
            total_responses=Count('id')
        )
    
    def get_activity_outcomes(self, tenant, days: int = 30):
        """Analyze activity outcomes and effectiveness"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date],
            status='completed'
        ).values('activity_type', 'outcome').annotate(
            count=Count('id'),
            avg_duration=Avg('duration')
        ).order_by('activity_type', '-count')
    
    def create_follow_up_activities(self, parent_activity, follow_up_rules: list):
        """
        Create follow-up activities based on rules
        
        follow_up_rules format:
        [
            {
                'activity_type': 'call',
                'days_offset': 3,
                'subject': 'Follow-up call',
                'assigned_to': user_id
            },
            ...
        ]
        """
        created_activities = []
        
        for rule in follow_up_rules:
            follow_up_date = timezone.now() + timedelta(days=rule.get('days_offset', 1))
            
            follow_up_activity = self.create(
                tenant=parent_activity.tenant,
                activity_type=rule['activity_type'],
                subject=rule.get('subject', f"Follow-up {rule['activity_type']}"),
                due_date=follow_up_date,
                assigned_to_id=rule.get('assigned_to', parent_activity.assigned_to_id),
                entity_type=parent_activity.entity_type,
                entity_id=parent_activity.entity_id,
                parent_activity=parent_activity,
                status='pending',
                priority=rule.get('priority', 'medium'),
                created_by=parent_activity.created_by
            )
            
            created_activities.append(follow_up_activity)
        
        return created_activities
    
    def bulk_reschedule_activities(self, activity_ids: list, new_date, user=None):
        """Bulk reschedule activities to new date"""
        updated_count = self.filter(
            id__in=activity_ids,
            status__in=['pending', 'scheduled']
        ).update(
            scheduled_at=new_date,
            due_date=new_date,
            modified_at=timezone.now(),
            modified_by=user
        )
        
        return updated_count
    
    def get_activity_pipeline(self, tenant, entity_type: str, entity_id: int):
        """Get activity timeline/pipeline for specific entity"""
        activities = self.for_tenant(tenant).filter(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by('-created_at')
        
        # Group activities by type and calculate metrics
        pipeline_data = {
            'total_activities': activities.count(),
            'completed_activities': activities.filter(status='completed').count(),
            'pending_activities': activities.filter(status__in=['pending', 'open']).count(),
            'activity_timeline': list(activities.values(
                'id', 'activity_type', 'subject', 'status',
                'created_at', 'due_date', 'assigned_to__first_name'
            )[:50]),  # Last 50 activities
            'next_activity': activities.filter(
                due_date__gte=timezone.now(),
                status__in=['pending', 'scheduled']
            ).order_by('due_date').first(),
            'last_completed_activity': activities.filter(
                status='completed'
            ).order_by('-completed_at').first()
        }
        
        return pipeline_data