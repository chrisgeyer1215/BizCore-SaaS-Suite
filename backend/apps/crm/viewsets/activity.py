# crm/viewsets/activity.py
"""
Activity Management ViewSets

Provides REST API endpoints for:
- Activity/task management with automated tracking
- Email template management and sending
- Call log tracking and analytics
- Note management with rich content
- Communication history and timeline
- Activity analytics and reporting
- Task automation and reminders
"""

from datetime import datetime, timedelta, date, time
from django.db.models import Count, Sum, Avg, Q, F, Case, When
from django.db.models.functions import TruncDate, TruncHour, Extract
from django.utils import timezone
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from crm.models.activity import (
    Activity, ActivityType, Note, EmailTemplate, EmailLog, 
    CallLog, SMSLog, Task
)
from crm.serializers.activity import (
    ActivitySerializer, ActivityDetailSerializer, ActivityCreateSerializer,
    ActivityTypeSerializer, NoteSerializer, EmailTemplateSerializer,
    EmailLogSerializer, CallLogSerializer, SMSLogSerializer, TaskSerializer
)
from crm.permissions.activity import ActivityPermission, EmailTemplatePermission
from crm.utils.tenant_utils import get_tenant_from_request
from crm.utils.email_utils import (
    send_crm_email, render_email_template, validate_email_template,
    track_email_open, track_email_click
)
from crm.utils.formatters import format_duration, format_date_display
from .base import CRMBaseViewSet, CRMReadOnlyViewSet, cache_response, require_tenant_limits


class ActivityFilter(filters.FilterSet):
    """Advanced filtering for Activity ViewSet."""
    
    type = filters.ModelChoiceFilter(queryset=ActivityType.objects.all())
    status = filters.ChoiceFilter(choices=Activity.STATUS_CHOICES)
    priority = filters.ChoiceFilter(choices=Activity.PRIORITY_CHOICES)
    assigned_to = filters.NumberFilter(field_name='assigned_to__id')
    created_by = filters.NumberFilter(field_name='created_by__id')
    due_date_from = filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = filters.DateFilter(field_name='due_date', lookup_expr='lte')
    scheduled_from = filters.DateTimeFilter(field_name='scheduled_at', lookup_expr='gte')
    scheduled_to = filters.DateTimeFilter(field_name='scheduled_at', lookup_expr='lte')
    completed_after = filters.DateTimeFilter(field_name='completed_at', lookup_expr='gte')
    completed_before = filters.DateTimeFilter(field_name='completed_at', lookup_expr='lte')
    is_overdue = filters.BooleanFilter(method='filter_is_overdue')
    is_today = filters.BooleanFilter(method='filter_is_today')
    is_this_week = filters.BooleanFilter(method='filter_is_this_week')
    has_related_object = filters.BooleanFilter(method='filter_has_related_object')
    related_object_type = filters.CharFilter(method='filter_related_object_type')
    
    class Meta:
        model = Activity
        fields = ['type', 'status', 'priority', 'assigned_to', 'is_completed']
    
    def filter_is_overdue(self, queryset, name, value):
        """Filter overdue activities."""
        if value:
            return queryset.filter(
                due_date__lt=timezone.now().date(),
                is_completed=False
            )
        return queryset
    
    def filter_is_today(self, queryset, name, value):
        """Filter activities due today."""
        if value:
            today = timezone.now().date()
            return queryset.filter(due_date=today)
        return queryset
    
    def filter_is_this_week(self, queryset, name, value):
        """Filter activities due this week."""
        if value:
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            return queryset.filter(due_date__range=[week_start, week_end])
        return queryset
    
    def filter_has_related_object(self, queryset, name, value):
        """Filter activities with/without related objects."""
        if value:
            return queryset.exclude(related_to_id__isnull=True)
        else:
            return queryset.filter(related_to_id__isnull=True)
    
    def filter_related_object_type(self, queryset, name, value):
        """Filter by related object type."""
        if value:
            # Map string to model names
            type_mapping = {
                'lead': 'lead',
                'opportunity': 'opportunity', 
                'account': 'account',
                'contact': 'contact'
            }
            
            model_name = type_mapping.get(value.lower())
            if model_name:
                return queryset.filter(related_object_type__icontains=model_name)
        return queryset


class ActivityViewSet(CRMBaseViewSet):
    """
    ViewSet for Activity management with comprehensive functionality.
    
    Provides CRUD operations, task management, and activity analytics.
    """
    
    queryset = Activity.objects.select_related('type', 'assigned_to', 'created_by').prefetch_related('notes')
    serializer_class = ActivitySerializer
    filterset_class = ActivityFilter
    search_fields = ['subject', 'description', 'notes__content']
    ordering_fields = [
        'subject', 'due_date', 'scheduled_at', 'priority', 'created_at', 'completed_at'
    ]
    ordering = ['-priority', 'due_date', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ActivityCreateSerializer
        elif self.action == 'retrieve':
            return ActivityDetailSerializer
        return ActivitySerializer
    
    def get_model_permission(self):
        """Get activity-specific permission class."""
        return ActivityPermission
    
    def perform_create(self, serializer):
        """Set created_by and auto-schedule reminders."""
        activity = serializer.save(created_by=self.request.user)
        
        # Auto-schedule reminder if due date is set
        if activity.due_date and not activity.is_completed:
            self._schedule_reminder(activity)
        
        # Create initial note if description is provided
        if activity.description:
            Note.objects.create(
                activity=activity,
                content=activity.description,
                created_by=self.request.user,
                tenant=activity.tenant
            )
    
    def update(self, request, *args, **kwargs):
        """Enhanced update with completion tracking."""
        activity = self.get_object()
        was_completed = activity.is_completed
        
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            activity.refresh_from_db()
            
            # Handle completion status change
            if not was_completed and activity.is_completed:
                activity.completed_at = timezone.now()
                activity.completed_by = request.user
                activity.save(update_fields=['completed_at', 'completed_by'])
                
                # Send completion notification
                self._send_completion_notification(activity)
                
            elif was_completed and not activity.is_completed:
                activity.completed_at = None
                activity.completed_by = None
                activity.save(update_fields=['completed_at', 'completed_by'])
        
        return response
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark activity as completed.
        
        Expected payload:
        {
            "completion_notes": "string",
            "actual_duration": integer (minutes),
            "outcome": "string"
        }
        """
        try:
            activity = self.get_object()
            
            if activity.is_completed:
                return Response(
                    {'error': 'Activity is already completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            completion_notes = request.data.get('completion_notes', '')
            actual_duration = request.data.get('actual_duration')
            outcome = request.data.get('outcome', '')
            
            with transaction.atomic():
                # Update activity
                activity.is_completed = True
                activity.completed_at = timezone.now()
                activity.completed_by = request.user
                activity.outcome = outcome
                if actual_duration:
                    activity.actual_duration = actual_duration
                activity.save()
                
                # Add completion note
                if completion_notes:
                    Note.objects.create(
                        activity=activity,
                        content=f"Activity completed: {completion_notes}",
                        note_type='COMPLETION',
                        created_by=request.user,
                        tenant=activity.tenant
                    )
                
                # Update related object's last activity timestamp
                self._update_related_object_activity(activity)
                
                # Send notification
                self._send_completion_notification(activity)
                
                return Response({
                    'message': 'Activity marked as completed',
                    'activity': ActivitySerializer(activity).data,
                    'completed_at': activity.completed_at.isoformat()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def snooze(self, request, pk=None):
        """
        Snooze activity to a later date/time.
        
        Expected payload:
        {
            "snooze_until": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS",
            "snooze_reason": "string"
        }
        """
        try:
            activity = self.get_object()
            
            if activity.is_completed:
                return Response(
                    {'error': 'Cannot snooze completed activity'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            snooze_until = request.data.get('snooze_until')
            snooze_reason = request.data.get('snooze_reason', '')
            
            if not snooze_until:
                return Response(
                    {'error': 'snooze_until is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Parse snooze date/time
            try:
                if 'T' in snooze_until:
                    # DateTime format
                    snooze_datetime = datetime.fromisoformat(snooze_until.replace('Z', '+00:00'))
                    activity.scheduled_at = snooze_datetime
                    activity.due_date = snooze_datetime.date()
                else:
                    # Date only format
                    snooze_date = datetime.strptime(snooze_until, '%Y-%m-%d').date()
                    activity.due_date = snooze_date
                    if activity.scheduled_at:
                        # Keep same time, change date
                        activity.scheduled_at = datetime.combine(
                            snooze_date, 
                            activity.scheduled_at.time()
                        )
            except ValueError:
                return Response(
                    {'error': 'Invalid date/time format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            activity.save()
            
            # Add snooze note
            Note.objects.create(
                activity=activity,
                content=f"Activity snoozed until {snooze_until}. Reason: {snooze_reason}",
                note_type='SYSTEM',
                created_by=request.user,
                tenant=activity.tenant
            )
            
            # Reschedule reminder
            self._schedule_reminder(activity)
            
            return Response({
                'message': f'Activity snoozed until {snooze_until}',
                'activity': ActivitySerializer(activity).data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_note(self, request, pk=None):
        """
        Add note to activity.
        
        Expected payload:
        {
            "content": "string",
            "note_type": "GENERAL|FOLLOW_UP|COMPLETION|SYSTEM",
            "is_private": boolean
        }
        """
        try:
            activity = self.get_object()
            
            note_data = request.data.copy()
            note_data['activity'] = activity.id
            note_data['created_by'] = request.user.id
            note_data['tenant'] = activity.tenant.id
            
            serializer = NoteSerializer(data=note_data)
            if serializer.is_valid():
                note = serializer.save()
                return Response(
                    NoteSerializer(note).data,
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
    def timeline(self, request, pk=None):
        """Get activity timeline with all related events."""
        try:
            activity = self.get_object()
            
            timeline_events = []
            
            # Add activity creation
            timeline_events.append({
                'timestamp': activity.created_at.isoformat(),
                'type': 'creation',
                'description': f'Activity created: {activity.subject}',
                'user': activity.created_by.get_full_name() if activity.created_by else 'System',
                'details': {
                    'priority': activity.get_priority_display(),
                    'due_date': activity.due_date.isoformat() if activity.due_date else None
                }
            })
            
            # Add notes
            notes = Note.objects.filter(
                activity=activity,
                tenant=activity.tenant
            ).order_by('created_at')
            
            for note in notes:
                timeline_events.append({
                    'timestamp': note.created_at.isoformat(),
                    'type': 'note',
                    'description': note.content[:100] + '...' if len(note.content) > 100 else note.content,
                    'user': note.created_by.get_full_name() if note.created_by else 'System',
                    'details': {
                        'note_type': note.note_type,
                        'is_private': note.is_private,
                        'full_content': note.content
                    }
                })
            
            # Add completion event
            if activity.is_completed and activity.completed_at:
                timeline_events.append({
                    'timestamp': activity.completed_at.isoformat(),
                    'type': 'completion',
                    'description': f'Activity completed',
                    'user': activity.completed_by.get_full_name() if activity.completed_by else 'System',
                    'details': {
                        'outcome': activity.outcome,
                        'actual_duration': activity.actual_duration
                    }
                })
            
            # Sort timeline by timestamp
            timeline_events.sort(key=lambda x: x['timestamp'])
            
            return Response({
                'activity_id': activity.id,
                'activity_subject': activity.subject,
                'timeline': timeline_events
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """Get current user's activities with smart filtering."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            user_activities = queryset.filter(assigned_to=request.user)
            
            # Categorize activities
            today = timezone.now().date()
            
            categories = {
                'overdue': user_activities.filter(
                    due_date__lt=today,
                    is_completed=False
                ).order_by('due_date'),
                
                'due_today': user_activities.filter(
                    due_date=today,
                    is_completed=False
                ).order_by('priority', 'scheduled_at'),
                
                'upcoming': user_activities.filter(
                    due_date__gt=today,
                    is_completed=False
                ).order_by('due_date', 'priority')[:10],
                
                'completed_today': user_activities.filter(
                    completed_at__date=today
                ).order_by('-completed_at')[:5],
                
                'no_due_date': user_activities.filter(
                    due_date__isnull=True,
                    is_completed=False
                ).order_by('-priority', '-created_at')[:5]
            }
            
            # Serialize each category
            response_data = {}
            for category, activities in categories.items():
                page = self.paginate_queryset(activities)
                if page is not None:
                    serializer = ActivitySerializer(page, many=True)
                    response_data[category] = {
                        'count': activities.count(),
                        'activities': serializer.data
                    }
                else:
                    serializer = ActivitySerializer(activities, many=True)
                    response_data[category] = {
                        'count': activities.count(),
                        'activities': serializer.data
                    }
            
            # Add summary stats
            response_data['summary'] = {
                'total_assigned': user_activities.count(),
                'completed_today': categories['completed_today'].count(),
                'overdue_count': categories['overdue'].count(),
                'due_today_count': categories['due_today'].count(),
                'completion_rate_this_week': self._calculate_weekly_completion_rate(request.user)
            }
            
            return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def team_activities(self, request):
        """Get team activities overview."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Get team members (same tenant)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            tenant = get_tenant_from_request(request)
            team_users = User.objects.filter(
                assigned_activities__tenant=tenant
            ).distinct()
            
            team_stats = []
            today = timezone.now().date()
            
            for user in team_users:
                user_activities = queryset.filter(assigned_to=user)
                
                stats = {
                    'user_id': user.id,
                    'user_name': user.get_full_name(),
                    'total_activities': user_activities.count(),
                    'overdue': user_activities.filter(
                        due_date__lt=today,
                        is_completed=False
                    ).count(),
                    'due_today': user_activities.filter(
                        due_date=today,
                        is_completed=False
                    ).count(),
                    'completed_this_week': user_activities.filter(
                        completed_at__gte=today - timedelta(days=7)
                    ).count(),
                    'completion_rate': self._calculate_weekly_completion_rate(user)
                }
                
                team_stats.append(stats)
            
            # Sort by activity level
            team_stats.sort(key=lambda x: x['total_activities'], reverse=True)
            
            return Response({
                'team_overview': team_stats,
                'team_totals': {
                    'total_team_members': len(team_stats),
                    'total_activities': sum(s['total_activities'] for s in team_stats),
                    'total_overdue': sum(s['overdue'] for s in team_stats),
                    'total_due_today': sum(s['due_today'] for s in team_stats),
                    'avg_completion_rate': sum(s['completion_rate'] for s in team_stats) / len(team_stats) if team_stats else 0
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_complete(self, request):
        """Bulk complete multiple activities."""
        try:
            activity_ids = request.data.get('activity_ids', [])
            completion_notes = request.data.get('completion_notes', '')
            
            if not activity_ids:
                return Response(
                    {'error': 'activity_ids are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_tenant_from_request(request)
            activities = Activity.objects.filter(
                id__in=activity_ids,
                tenant=tenant,
                is_completed=False
            )
            
            completed_count = 0
            
            with transaction.atomic():
                for activity in activities:
                    activity.is_completed = True
                    activity.completed_at = timezone.now()
                    activity.completed_by = request.user
                    activity.save()
                    
                    # Add completion note if provided
                    if completion_notes:
                        Note.objects.create(
                            activity=activity,
                            content=f"Bulk completed: {completion_notes}",
                            note_type='COMPLETION',
                            created_by=request.user,
                            tenant=tenant
                        )
                    
                    completed_count += 1
            
            return Response({
                'message': f'{completed_count} activities marked as completed',
                'completed_count': completed_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def activity_calendar(self, request):
        """Get activities in calendar format."""
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if not start_date or not end_date:
                # Default to current month
                today = timezone.now().date()
                start_date = today.replace(day=1)
                next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
                end_date = next_month - timedelta(days=1)
            else:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Get activities in date range
            queryset = self.filter_queryset(self.get_queryset())
            calendar_activities = queryset.filter(
                Q(due_date__range=[start_date, end_date]) |
                Q(scheduled_at__date__range=[start_date, end_date])
            ).order_by('due_date', 'scheduled_at')
            
            # Group by date
            calendar_data = {}
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.isoformat()
                
                # Get activities for this date
                day_activities = calendar_activities.filter(
                    Q(due_date=current_date) |
                    Q(scheduled_at__date=current_date)
                )
                
                calendar_data[date_str] = {
                    'date': date_str,
                    'activity_count': day_activities.count(),
                    'activities': ActivitySerializer(day_activities, many=True).data,
                    'has_overdue': day_activities.filter(
                        due_date__lt=timezone.now().date(),
                        is_completed=False
                    ).exists()
                }
                
                current_date += timedelta(days=1)
            
            return Response({
                'calendar_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'calendar_data': calendar_data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _schedule_reminder(self, activity):
        """Schedule reminder for activity."""
        try:
            # This would integrate with a task queue like Celery
            # For now, just log the reminder scheduling
            print(f"Reminder scheduled for activity {activity.id} on {activity.due_date}")
        except Exception as e:
            print(f"Failed to schedule reminder: {e}")
    
    def _send_completion_notification(self, activity):
        """Send notification when activity is completed."""
        try:
            # Notify creator if different from completer
            if activity.created_by and activity.created_by != activity.completed_by:
                from crm.utils.email_utils import send_crm_email
                
                send_crm_email(
                    recipient_email=activity.created_by.email,
                    subject=f'Activity Completed: {activity.subject}',
                    template_name='activity_completed',
                    context_data={
                        'activity': activity,
                        'completed_by': activity.completed_by
                    },
                    recipient_data={
                        'first_name': activity.created_by.first_name,
                        'email': activity.created_by.email
                    },
                    tenant=activity.tenant
                )
        except Exception as e:
            print(f"Failed to send completion notification: {e}")
    
    def _update_related_object_activity(self, activity):
        """Update last activity timestamp on related object."""
        try:
            if activity.related_to_id:
                # Update based on related object type
                if 'lead' in activity.related_object_type.lower():
                    from crm.models.lead import Lead
                    Lead.objects.filter(
                        id=activity.related_to_id,
                        tenant=activity.tenant
                    ).update(last_contacted=timezone.now())
                
                elif 'opportunity' in activity.related_object_type.lower():
                    from crm.models.opportunity import Opportunity
                    Opportunity.objects.filter(
                        id=activity.related_to_id,
                        tenant=activity.tenant
                    ).update(last_activity=timezone.now())
        except Exception as e:
            print(f"Failed to update related object: {e}")
    
    def _calculate_weekly_completion_rate(self, user):
        """Calculate user's completion rate for this week."""
        try:
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
            
            weekly_activities = Activity.objects.filter(
                assigned_to=user,
                tenant=get_tenant_from_request(self.request),
                created_at__date__gte=week_start
            )
            
            total = weekly_activities.count()
            completed = weekly_activities.filter(is_completed=True).count()
            
            return (completed / total * 100) if total > 0 else 0
        except:
            return 0


class ActivityTypeViewSet(CRMBaseViewSet):
    """
    ViewSet for Activity Type management.
    """
    
    queryset = ActivityType.objects.all()
    serializer_class = ActivityTypeSerializer
    search_fields = ['name', 'description']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    @cache_response(timeout=1800)
    def usage_stats(self, request, pk=None):
        """Get usage statistics for this activity type."""
        try:
            activity_type = self.get_object()
            tenant = get_tenant_from_request(request)
            
            # Get activities of this type
            type_activities = Activity.objects.filter(
                type=activity_type,
                tenant=tenant
            )
            
            total_activities = type_activities.count()
            completed_activities = type_activities.filter(is_completed=True).count()
            
            completion_rate = (completed_activities / total_activities * 100) if total_activities > 0 else 0
            
            # Average duration for completed activities
            completed_with_duration = type_activities.filter(
                is_completed=True,
                actual_duration__isnull=False
            )
            
            avg_duration = completed_with_duration.aggregate(
                Avg('actual_duration')
            )['actual_duration__avg'] or 0
            
            # Most active users
            top_users = type_activities.values(
                'assigned_to__first_name', 
                'assigned_to__last_name'
            ).annotate(
                activity_count=Count('id')
            ).order_by('-activity_count')[:5]
            
            return Response({
                'activity_type': ActivityTypeSerializer(activity_type).data,
                'usage_stats': {
                    'total_activities': total_activities,
                    'completed_activities': completed_activities,
                    'completion_rate': round(completion_rate, 2),
                    'avg_duration_minutes': round(avg_duration, 1),
                    'top_users': list(top_users)
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NoteViewSet(CRMBaseViewSet):
    """
    ViewSet for Note management.
    """
    
    queryset = Note.objects.select_related('activity', 'created_by')
    serializer_class = NoteSerializer
    filterset_fields = ['activity', 'note_type', 'is_private']
    search_fields = ['content']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter notes by privacy settings."""
        queryset = super().get_queryset()
        
        # Users can see their own private notes and all public notes
        return queryset.filter(
            Q(is_private=False) | Q(created_by=self.request.user)
        )


class EmailTemplateViewSet(CRMBaseViewSet):
    """
    ViewSet for Email Template management with testing and analytics.
    """
    
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'subject', 'description']
    ordering = ['category', 'name']
    
    def get_model_permission(self):
        """Get email template-specific permission class."""
        return EmailTemplatePermission
    
    @action(detail=True, methods=['post'])
    def test_template(self, request, pk=None):
        """
        Test email template with sample data.
        
        Expected payload:
        {
            "test_email": "string",
            "sample_data": {
                "recipient_name": "string",
                "company_name": "string",
                ...
            }
        }
        """
        try:
            template = self.get_object()
            test_email = request.data.get('test_email')
            sample_data = request.data.get('sample_data', {})
            
            if not test_email:
                return Response(
                    {'error': 'test_email is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate template
            validation_result = validate_email_template(template.html_content)
            
            if not validation_result['is_valid']:
                return Response({
                    'template_valid': False,
                    'validation_errors': validation_result['issues']
                })
            
            # Render template with sample data
            rendered = render_email_template(
                template.name,
                context_data=sample_data,
                recipient_data={
                    'email': test_email,
                    'first_name': sample_data.get('recipient_name', 'Test User')
                },
                tenant=template.tenant
            )
            
            # Send test email
            result = send_crm_email(
                recipient_email=test_email,
                subject=f"[TEST] {rendered['subject']}",
                html_content=rendered['html_content'],
                text_content=rendered['text_content'],
                tenant=template.tenant
            )
            
            return Response({
                'template_valid': True,
                'test_sent': result['success'],
                'rendered_content': {
                    'subject': rendered['subject'],
                    'html_preview': rendered['html_content'][:500] + '...',
                    'text_preview': rendered['text_content'][:500] + '...'
                },
                'send_result': result
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """
        Send email using this template.
        
        Expected payload:
        {
            "recipients": ["email1@example.com", "email2@example.com"],
            "context_data": {},
            "recipient_data": {},
            "schedule_at": "optional datetime"
        }
        """
        try:
            template = self.get_object()
            recipients = request.data.get('recipients', [])
            context_data = request.data.get('context_data', {})
            recipient_data = request.data.get('recipient_data', {})
            schedule_at = request.data.get('schedule_at')
            
            if not recipients:
                return Response(
                    {'error': 'recipients are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            sent_results = []
            failed_results = []
            
            for recipient_email in recipients:
                try:
                    # Get recipient-specific data
                    recipient_info = recipient_data.get(recipient_email, {
                        'email': recipient_email
                    })
                    
                    if schedule_at:
                        # Schedule email (would integrate with task queue)
                        sent_results.append({
                            'recipient': recipient_email,
                            'status': 'scheduled',
                            'scheduled_for': schedule_at
                        })
                    else:
                        # Send immediately
                        result = send_crm_email(
                            recipient_email=recipient_email,
                            template_name=template.name,
                            context_data=context_data,
                            recipient_data=recipient_info,
                            tenant=template.tenant
                        )
                        
                        if result['success']:
                            sent_results.append({
                                'recipient': recipient_email,
                                'status': 'sent',
                                'tracking_id': result.get('tracking_id')
                            })
                        else:
                            failed_results.append({
                                'recipient': recipient_email,
                                'error': result.get('error')
                            })
                
                except Exception as e:
                    failed_results.append({
                        'recipient': recipient_email,
                        'error': str(e)
                    })
            
            return Response({
                'template_name': template.name,
                'total_recipients': len(recipients),
                'sent_count': len(sent_results),
                'failed_count': len(failed_results),
                'sent_results': sent_results,
                'failed_results': failed_results
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    @cache_response(timeout=600)
    def analytics(self, request, pk=None):
        """Get analytics for email template usage."""
        try:
            template = self.get_object()
            tenant = get_tenant_from_request(request)
            
            # Get email logs for this template
            email_logs = EmailLog.objects.filter(
                template_name=template.name,
                tenant=tenant
            )
            
            total_sent = email_logs.count()
            total_opened = email_logs.filter(opened_at__isnull=False).count()
            total_clicked = email_logs.filter(click_count__gt=0).count()
            total_bounced = email_logs.filter(bounced_at__isnull=False).count()
            
            # Calculate rates
            open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
            click_rate = (total_clicked / total_sent * 100) if total_sent > 0 else 0
            bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0
            
            # Usage over time (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_usage = email_logs.filter(
                sent_at__gte=thirty_days_ago
            ).extra(
                select={'day': "DATE(sent_at)"}
            ).values('day').annotate(
                count=Count('id')
            ).order_by('day')
            
            return Response({
                'template': EmailTemplateSerializer(template).data,
                'usage_stats': {
                    'total_sent': total_sent,
                    'total_opened': total_opened,
                    'total_clicked': total_clicked,
                    'total_bounced': total_bounced,
                    'open_rate': round(open_rate, 2),
                    'click_rate': round(click_rate, 2),
                    'bounce_rate': round(bounce_rate, 2)
                },
                'recent_usage': list(recent_usage),
                'performance_rating': self._calculate_template_performance(
                    open_rate, click_rate, bounce_rate
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_template_performance(self, open_rate, click_rate, bounce_rate):
        """Calculate overall template performance rating."""
        score = 0
        
        # Open rate scoring (industry average ~20%)
        if open_rate >= 30:
            score += 40
        elif open_rate >= 20:
            score += 25
        elif open_rate >= 15:
            score += 15
        
        # Click rate scoring (industry average ~3%)
        if click_rate >= 5:
            score += 30
        elif click_rate >= 3:
            score += 20
        elif click_rate >= 2:
            score += 10
        
        # Bounce rate penalty (should be < 2%)
        if bounce_rate > 5:
            score -= 20
        elif bounce_rate > 2:
            score -= 10
        
        # Base score for having data
        if open_rate > 0 or click_rate > 0:
            score += 30
        
        score = max(0, min(100, score))
        
        if score >= 80:
            return {'rating': 'Excellent', 'score': score}
        elif score >= 60:
            return {'rating': 'Good', 'score': score}
        elif score >= 40:
            return {'rating': 'Average', 'score': score}
        else:
            return {'rating': 'Needs Improvement', 'score': score}


class EmailLogViewSet(CRMReadOnlyViewSet):
    """
    Read-only ViewSet for Email Log analytics and tracking.
    """
    
    queryset = EmailLog.objects.select_related('campaign').order_by('-sent_at')
    serializer_class = EmailLogSerializer
    filterset_fields = ['status', 'template_name', 'campaign']
    search_fields = ['recipient_email', 'subject']
    ordering = ['-sent_at']
    
    @action(detail=True, methods=['get'])
    def track_open(self, request, pk=None):
        """Track email open (usually called by tracking pixel)."""
        try:
            email_log = self.get_object()
            
            # Track the open
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')
            
            track_email_open(
                tracking_id=email_log.tracking_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Return 1x1 transparent pixel
            from django.http import HttpResponse
            pixel_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x12IDATx\x9cc```bPPP\x00\x82\x02\x00\x00\x10\x00\x01\x1e\'\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            
            response = HttpResponse(pixel_data, content_type='image/png')
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        
        except Exception as e:
            # Return pixel even if tracking fails
            pixel_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x12IDATx\x9cc```bPPP\x00\x82\x02\x00\x00\x10\x00\x01\x1e\'\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            return HttpResponse(pixel_data, content_type='image/png')
    
    @action(detail=True, methods=['get'])
    def track_click(self, request, pk=None):
        """Track email click and redirect to target URL."""
        try:
            email_log = self.get_object()
            target_url = request.GET.get('url')
            
            if not target_url:
                return Response(
                    {'error': 'URL parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Track the click
            ip_address = request.META.get('REMOTE_ADDR')
            
            track_email_click(
                tracking_id=email_log.tracking_id,
                clicked_url=target_url,
                ip_address=ip_address
            )
            
            # Redirect to target URL
            from django.shortcuts import redirect
            return redirect(target_url)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CallLogViewSet(CRMBaseViewSet):
    """
    ViewSet for Call Log management and analytics.
    """
    
    queryset = CallLog.objects.select_related('contact', 'created_by')
    serializer_class = CallLogSerializer
    filterset_fields = ['call_type', 'outcome', 'contact']
    search_fields = ['notes', 'contact__first_name', 'contact__last_name']
    ordering = ['-call_date']
    
    @action(detail=False, methods=['get'])
    def call_analytics(self, request):
        """Get call analytics and metrics."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Basic metrics
            total_calls = queryset.count()
            
            # Call type distribution
            call_types = queryset.values('call_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Outcome distribution
            outcomes = queryset.values('outcome').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Duration analytics
            duration_stats = queryset.aggregate(
                avg_duration=Avg('duration'),
                total_duration=Sum('duration')
            )
            
            # Daily call volume (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            daily_volume = queryset.filter(
                call_date__gte=thirty_days_ago
            ).extra(
                select={'day': "DATE(call_date)"}
            ).values('day').annotate(
                call_count=Count('id'),
                total_duration=Sum('duration')
            ).order_by('day')
            
            # Top performers
            top_callers = queryset.values(
                'created_by__first_name',
                'created_by__last_name'
            ).annotate(
                call_count=Count('id'),
                total_duration=Sum('duration')
            ).order_by('-call_count')[:5]
            
            return Response({
                'call_metrics': {
                    'total_calls': total_calls,
                    'avg_duration_minutes': round(duration_stats['avg_duration'] or 0, 1),
                    'total_duration_hours': round((duration_stats['total_duration'] or 0) / 60, 1)
                },
                'call_type_distribution': list(call_types),
                'outcome_distribution': list(outcomes),
                'daily_volume': list(daily_volume),
                'top_callers': list(top_callers)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TaskViewSet(CRMBaseViewSet):
    """
    ViewSet for Task management (subset of activities focused on to-dos).
    """
    
    queryset = Task.objects.select_related('assigned_to', 'created_by', 'activity')
    serializer_class = TaskSerializer
    filterset_fields = ['status', 'priority', 'assigned_to', 'is_completed']
    search_fields = ['title', 'description']
    ordering = ['-priority', 'due_date', '-created_at']
    
    @action(detail=False, methods=['get'])
    def productivity_dashboard(self, request):
        """Get productivity dashboard for tasks."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            user_tasks = queryset.filter(assigned_to=request.user)
            
            today = timezone.now().date()
            this_week_start = today - timedelta(days=today.weekday())
            
            # Productivity metrics
            metrics = {
                'tasks_completed_today': user_tasks.filter(
                    completed_at__date=today
                ).count(),
                
                'tasks_completed_this_week': user_tasks.filter(
                    completed_at__date__gte=this_week_start
                ).count(),
                
                'tasks_due_today': user_tasks.filter(
                    due_date=today,
                    is_completed=False
                ).count(),
                
                'overdue_tasks': user_tasks.filter(
                    due_date__lt=today,
                    is_completed=False
                ).count(),
                
                'completion_streak': self._calculate_completion_streak(request.user),
                'weekly_completion_rate': self._calculate_weekly_completion_rate(request.user)
            }
            
            # Upcoming tasks
            upcoming_tasks = user_tasks.filter(
                due_date__gte=today,
                is_completed=False
            ).order_by('due_date', 'priority')[:10]
            
            return Response({
                'productivity_metrics': metrics,
                'upcoming_tasks': TaskSerializer(upcoming_tasks, many=True).data,
                'recommendations': self._generate_productivity_recommendations(metrics)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_completion_streak(self, user):
        """Calculate consecutive days with completed tasks."""
        try:
            current_date = timezone.now().date()
            streak = 0
            
            while True:
                day_tasks = Task.objects.filter(
                    assigned_to=user,
                    completed_at__date=current_date,
                    tenant=get_tenant_from_request(self.request)
                )
                
                if day_tasks.exists():
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
            
            return streak
        except:
            return 0
    
    def _generate_productivity_recommendations(self, metrics):
        """Generate productivity recommendations based on metrics."""
        recommendations = []
        
        if metrics['overdue_tasks'] > 0:
            recommendations.append({
                'type': 'urgent',
                'message': f"You have {metrics['overdue_tasks']} overdue tasks",
                'action': 'Prioritize completing overdue tasks today'
            })
        
        if metrics['weekly_completion_rate'] < 70:
            recommendations.append({
                'type': 'improvement',
                'message': f"Weekly completion rate is {metrics['weekly_completion_rate']:.1f}%",
                'action': 'Consider breaking large tasks into smaller ones'
            })
        
        if metrics['completion_streak'] >= 7:
            recommendations.append({
                'type': 'success',
                'message': f"Great job! {metrics['completion_streak']} day completion streak",
                'action': 'Keep up the excellent productivity'
            })
        
        if metrics['tasks_due_today'] > 5:
            recommendations.append({
                'type': 'warning',
                'message': f"{metrics['tasks_due_today']} tasks due today",
                'action': 'Consider rescheduling some tasks to maintain quality'
            })
        
        return recommendations