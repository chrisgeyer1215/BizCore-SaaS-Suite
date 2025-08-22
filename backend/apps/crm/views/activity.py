# ============================================================================
# backend/apps/crm/views/activity.py - Activity Management Views
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
from django.core.paginator import Paginator
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta, time
import json
import calendar

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import (
    Activity, ActivityType, ActivityParticipant, Note, 
    EmailTemplate, EmailLog, CallLog, SMSLog,
    Lead, Account, Contact, Opportunity
)
from ..serializers import (
    ActivitySerializer, ActivityDetailSerializer, ActivityTypeSerializer,
    NoteSerializer, EmailTemplateSerializer, EmailLogSerializer,
    CallLogSerializer, SMSLogSerializer
)
from ..filters import ActivityFilter
from ..permissions import ActivityPermission
from ..services import ActivityService, EmailService, NotificationService


class ActivityDashboardView(CRMBaseMixin, View):
    """Activity dashboard with calendar and metrics"""
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Get activities for current user
        activities = Activity.objects.filter(
            tenant=request.tenant,
            assigned_to=user,
            is_active=True
        ).select_related(
            'activity_type', 'assigned_to', 'content_type'
        ).prefetch_related('participants')
        
        # Today's activities
        today_activities = activities.filter(
            start_datetime__date=today
        ).order_by('start_datetime')
        
        # This week's activities
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_activities = activities.filter(
            start_datetime__date__range=[week_start, week_end]
        )
        
        # Overdue activities
        overdue_activities = activities.filter(
            status__in=['PLANNED', 'IN_PROGRESS'],
            end_datetime__lt=timezone.now()
        ).order_by('end_datetime')
        
        # Upcoming activities (next 7 days)
        upcoming_activities = activities.filter(
            status='PLANNED',
            start_datetime__date__range=[today + timedelta(days=1), today + timedelta(days=7)]
        ).order_by('start_datetime')[:10]
        
        # Activity statistics
        stats = {
            'today_count': today_activities.count(),
            'week_count': week_activities.count(),
            'overdue_count': overdue_activities.count(),
            'completed_today': today_activities.filter(status='COMPLETED').count(),
            'completion_rate': self.calculate_completion_rate(user, today),
            'total_this_month': self.get_month_activity_count(user, today),
            'by_type': self.get_activities_by_type(user, today),
            'productivity_score': self.calculate_productivity_score(user),
        }
        
        # Calendar data for current month
        calendar_data = self.get_calendar_data(request, today.year, today.month)
        
        context = {
            'today_activities': today_activities,
            'overdue_activities': overdue_activities,
            'upcoming_activities': upcoming_activities,
            'stats': stats,
            'calendar_data': calendar_data,
            'current_date': today,
        }
        
        return render(request, 'crm/activity/dashboard.html', context)
    
    def calculate_completion_rate(self, user, date):
        """Calculate completion rate for user on given date"""
        total_activities = Activity.objects.filter(
            tenant=user.tenant,
            assigned_to=user,
            start_datetime__date=date,
            is_active=True
        ).count()
        
        if total_activities == 0:
            return 0
        
        completed_activities = Activity.objects.filter(
            tenant=user.tenant,
            assigned_to=user,
            start_datetime__date=date,
            status='COMPLETED',
            is_active=True
        ).count()
        
        return round((completed_activities / total_activities) * 100, 1)
    
    def get_month_activity_count(self, user, date):
        """Get total activities for current month"""
        month_start = date.replace(day=1)
        next_month = month_start.replace(month=month_start.month + 1 if month_start.month < 12 else 1,
                                       year=month_start.year if month_start.month < 12 else month_start.year + 1)
        
        return Activity.objects.filter(
            tenant=user.tenant,
            assigned_to=user,
            start_datetime__date__gte=month_start,
            start_datetime__date__lt=next_month,
            is_active=True
        ).count()
    
    def get_activities_by_type(self, user, date):
        """Get activity breakdown by type for today"""
        return list(Activity.objects.filter(
            tenant=user.tenant,
            assigned_to=user,
            start_datetime__date=date,
            is_active=True
        ).values(
            'activity_type__name',
            'activity_type__category'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
    
    def calculate_productivity_score(self, user):
        """Calculate productivity score based on activity completion and timing"""
        # Last 7 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        activities = Activity.objects.filter(
            tenant=user.tenant,
            assigned_to=user,
            start_datetime__date__range=[start_date, end_date],
            is_active=True
        )
        
        total_activities = activities.count()
        if total_activities == 0:
            return 0
        
        # Completion score (40%)
        completed_activities = activities.filter(status='COMPLETED').count()
        completion_score = (completed_activities / total_activities) * 40
        
        # On-time score (30%)
        on_time_activities = activities.filter(
            status='COMPLETED',
            completed_date__lte=F('end_datetime')
        ).count()
        on_time_score = (on_time_activities / max(completed_activities, 1)) * 30
        
        # Activity volume score (30%)
        avg_daily_activities = total_activities / 7
        volume_score = min(avg_daily_activities * 5, 30)  # Cap at 30
        
        return round(completion_score + on_time_score + volume_score, 1)
    
    def get_calendar_data(self, request, year, month):
        """Get calendar data for the given month"""
        # Get activities for the month
        month_start = datetime(year, month, 1).date()
        next_month = month_start.replace(
            month=month + 1 if month < 12 else 1,
            year=year if month < 12 else year + 1
        )
        
        activities = Activity.objects.filter(
            tenant=request.tenant,
            assigned_to=request.user,
            start_datetime__date__gte=month_start,
            start_datetime__date__lt=next_month,
            is_active=True
        ).select_related('activity_type')
        
        # Group activities by date
        calendar_activities = {}
        for activity in activities:
            date_key = activity.start_datetime.date()
            if date_key not in calendar_activities:
                calendar_activities[date_key] = []
            calendar_activities[date_key].append(activity)
        
        # Generate calendar structure
        cal = calendar.monthcalendar(year, month)
        calendar_data = []
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    date_obj = datetime(year, month, day).date()
                    day_activities = calendar_activities.get(date_obj, [])
                    week_data.append({
                        'day': day,
                        'date': date_obj,
                        'activities': day_activities,
                        'activity_count': len(day_activities),
                        'has_overdue': any(
                            a.status != 'COMPLETED' and a.end_datetime < timezone.now()
                            for a in day_activities
                        ),
                        'is_today': date_obj == timezone.now().date(),
                    })
            calendar_data.append(week_data)
        
        return {
            'calendar': calendar_data,
            'month_name': calendar.month_name[month],
            'year': year,
            'month': month,
            'prev_month': month - 1 if month > 1 else 12,
            'prev_year': year if month > 1 else year - 1,
            'next_month': month + 1 if month < 12 else 1,
            'next_year': year if month < 12 else year + 1,
        }


class ActivityCalendarView(CRMBaseMixin, View):
    """Calendar view for activities"""
    
    def get(self, request):
        # Get year and month from request, default to current
        today = timezone.now().date()
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        view_type = request.GET.get('view', 'month')  # month, week, day
        
        if view_type == 'month':
            return self.month_view(request, year, month)
        elif view_type == 'week':
            week_date = request.GET.get('date', today.isoformat())
            return self.week_view(request, datetime.strptime(week_date, '%Y-%m-%d').date())
        elif view_type == 'day':
            day_date = request.GET.get('date', today.isoformat())
            return self.day_view(request, datetime.strptime(day_date, '%Y-%m-%d').date())
        else:
            return self.month_view(request, year, month)
    
    def month_view(self, request, year, month):
        """Monthly calendar view"""
        user = request.user
        
        # Date range for the month
        month_start = datetime(year, month, 1).date()
        next_month = month_start.replace(
            month=month + 1 if month < 12 else 1,
            year=year if month < 12 else year + 1
        )
        
        # Get activities for the month
        activities = Activity.objects.filter(
            tenant=request.tenant,
            start_datetime__date__gte=month_start,
            start_datetime__date__lt=next_month,
            is_active=True
        ).select_related(
            'activity_type', 'assigned_to', 'content_type'
        )
        
        # Filter by user if not admin
        if not user.has_perm('crm.view_all_activities'):
            activities = activities.filter(
                Q(assigned_to=user) | Q(participants__user=user)
            ).distinct()
        
        # Apply additional filters
        activity_filter = ActivityFilter(request.GET, queryset=activities, tenant=request.tenant)
        filtered_activities = activity_filter.qs
        
        # Group activities by date
        calendar_activities = {}
        for activity in filtered_activities:
            date_key = activity.start_datetime.date()
            if date_key not in calendar_activities:
                calendar_activities[date_key] = []
            calendar_activities[date_key].append(activity)
        
        # Generate calendar data
        calendar_data = self.generate_calendar_data(year, month, calendar_activities)
        
        context = {
            'calendar_data': calendar_data,
            'view_type': 'month',
            'current_date': datetime(year, month, 1).date(),
            'filter': activity_filter,
            'activities_count': filtered_activities.count(),
        }
        
        return render(request, 'crm/activity/calendar.html', context)
    
    def week_view(self, request, date):
        """Weekly calendar view"""
        # Get week start (Monday)
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Get activities for the week
        activities = Activity.objects.filter(
            tenant=request.tenant,
            start_datetime__date__range=[week_start, week_end],
            is_active=True
        ).select_related(
            'activity_type', 'assigned_to', 'content_type'
        ).order_by('start_datetime')
        
        # Filter by user if not admin
        user = request.user
        if not user.has_perm('crm.view_all_activities'):
            activities = activities.filter(
                Q(assigned_to=user) | Q(participants__user=user)
            ).distinct()
        
        # Group activities by day and hour
        week_data = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_activities = activities.filter(start_datetime__date=day_date)
            
            # Group by hour
            hour_activities = {}
            for activity in day_activities:
                hour = activity.start_datetime.hour
                if hour not in hour_activities:
                    hour_activities[hour] = []
                hour_activities[hour].append(activity)
            
            week_data.append({
                'date': day_date,
                'day_name': day_date.strftime('%A'),
                'activities': day_activities,
                'hour_activities': hour_activities,
                'is_today': day_date == timezone.now().date(),
            })
        
        context = {
            'week_data': week_data,
            'week_start': week_start,
            'week_end': week_end,
            'view_type': 'week',
            'current_date': date,
        }
        
        return render(request, 'crm/activity/calendar_week.html', context)
    
    def day_view(self, request, date):
        """Daily calendar view"""
        # Get activities for the day
        activities = Activity.objects.filter(
            tenant=request.tenant,
            start_datetime__date=date,
            is_active=True
        ).select_related(
            'activity_type', 'assigned_to', 'content_type'
        ).order_by('start_datetime')
        
        # Filter by user if not admin
        user = request.user
        if not user.has_perm('crm.view_all_activities'):
            activities = activities.filter(
                Q(assigned_to=user) | Q(participants__user=user)
            ).distinct()
        
        # Group by hour for timeline view
        timeline_data = []
        for hour in range(24):
            hour_activities = activities.filter(start_datetime__hour=hour)
            timeline_data.append({
                'hour': hour,
                'hour_12': f"{hour % 12 or 12}:00 {'AM' if hour < 12 else 'PM'}",
                'activities': hour_activities,
            })
        
        context = {
            'timeline_data': timeline_data,
            'selected_date': date,
            'view_type': 'day',
            'current_date': date,
            'activities': activities,
            'is_today': date == timezone.now().date(),
        }
        
        return render(request, 'crm/activity/calendar_day.html', context)
    
    def generate_calendar_data(self, year, month, activities_by_date):
        """Generate calendar structure with activities"""
        cal = calendar.monthcalendar(year, month)
        calendar_data = []
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    date_obj = datetime(year, month, day).date()
                    day_activities = activities_by_date.get(date_obj, [])
                    
                    # Categorize activities
                    activity_summary = {
                        'total': len(day_activities),
                        'completed': len([a for a in day_activities if a.status == 'COMPLETED']),
                        'overdue': len([a for a in day_activities if a.status != 'COMPLETED' and a.end_datetime < timezone.now()]),
                        'upcoming': len([a for a in day_activities if a.status == 'PLANNED']),
                    }
                    
                    week_data.append({
                        'day': day,
                        'date': date_obj,
                        'activities': day_activities[:3],  # Show max 3 in calendar
                        'activity_summary': activity_summary,
                        'is_today': date_obj == timezone.now().date(),
                        'is_weekend': date_obj.weekday() >= 5,
                    })
            calendar_data.append(week_data)
        
        return {
            'calendar': calendar_data,
            'month_name': calendar.month_name[month],
            'year': year,
            'month': month,
            'prev_month': month - 1 if month > 1 else 12,
            'prev_year': year if month > 1 else year - 1,
            'next_month': month + 1 if month < 12 else 1,
            'next_year': year if month < 12 else year + 1,
        }


class ActivityListView(CRMBaseMixin, ListView):
    """Activity list view with advanced filtering"""
    
    model = Activity
    template_name = 'crm/activity/list.html'
    context_object_name = 'activities'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Activity.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'activity_type', 'assigned_to', 'owner', 'content_type'
        ).prefetch_related(
            'participants__user'
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_activities'):
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(owner=user) | Q(participants__user=user)
            ).distinct()
        
        # Apply filters
        activity_filter = ActivityFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        return activity_filter.qs.order_by('-start_datetime')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = ActivityFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Activity statistics
        queryset = self.get_queryset()
        context['stats'] = self.get_activity_stats(queryset)
        
        # Quick filters
        context['quick_filters'] = self.get_quick_filters()
        
        return context
    
    def get_activity_stats(self, queryset):
        """Get activity statistics"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        stats = {
            'total_count': queryset.count(),
            'today_count': queryset.filter(start_datetime__date=today).count(),
            'week_count': queryset.filter(start_datetime__date__gte=week_start).count(),
            'month_count': queryset.filter(start_datetime__date__gte=month_start).count(),
            'completed_count': queryset.filter(status='COMPLETED').count(),
            'overdue_count': queryset.filter(
                status__in=['PLANNED', 'IN_PROGRESS'],
                end_datetime__lt=timezone.now()
            ).count(),
            'by_type': list(queryset.values(
                'activity_type__name',
                'activity_type__category'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10]),
            'by_status': list(queryset.values('status').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
        
        # Completion rate
        if stats['total_count'] > 0:
            stats['completion_rate'] = round((stats['completed_count'] / stats['total_count']) * 100, 1)
        else:
            stats['completion_rate'] = 0
        
        return stats
    
    def get_quick_filters(self):
        """Get quick filter options"""
        return [
            {'name': 'My Activities', 'filter': 'assigned_to=me'},
            {'name': 'Today', 'filter': 'date=today'},
            {'name': 'This Week', 'filter': 'date=this_week'},
            {'name': 'Overdue', 'filter': 'status=overdue'},
            {'name': 'Completed', 'filter': 'status=COMPLETED'},
            {'name': 'High Priority', 'filter': 'priority=HIGH'},
            {'name': 'Meetings', 'filter': 'type=MEETING'},
            {'name': 'Calls', 'filter': 'type=COMMUNICATION'},
        ]


class ActivityDetailView(CRMBaseMixin, DetailView):
    """Detailed activity view with related information"""
    
    model = Activity
    template_name = 'crm/activity/detail.html'
    context_object_name = 'activity'
    
    def get_queryset(self):
        return Activity.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'activity_type', 'assigned_to', 'owner', 'content_type'
        ).prefetch_related(
            'participants__user',
            'notes'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_object()
        
        # Participants
        context['participants'] = activity.participants.filter(
            is_active=True
        ).select_related('user')
        
        # Notes
        context['notes'] = activity.notes.filter(
            is_active=True
        ).select_related('created_by').order_by('-created_at')
        
        # Related record information
        if activity.related_to:
            context['related_object'] = activity.related_to
            context['related_type'] = activity.content_type.model
        
        # Time information
        context['time_info'] = self.get_time_info(activity)
        
        # Status information
        context['status_info'] = self.get_status_info(activity)
        
        # Follow-up information
        if activity.follow_up_activity:
            context['follow_up'] = activity.follow_up_activity
        
        # Previous activities for same record
        if activity.related_to:
            context['related_activities'] = Activity.objects.filter(
                tenant=self.request.tenant,
                content_type=activity.content_type,
                object_id=activity.object_id,
                is_active=True
            ).exclude(
                id=activity.id
            ).select_related(
                'activity_type', 'assigned_to'
            ).order_by('-start_datetime')[:5]
        
        return context
    
    def get_time_info(self, activity):
        """Get time-related information"""
        now = timezone.now()
        
        info = {
            'duration_minutes': activity.duration_minutes,
            'is_overdue': activity.status != 'COMPLETED' and activity.end_datetime < now,
            'time_until_start': None,
            'time_since_end': None,
        }
        
        if activity.start_datetime > now:
            info['time_until_start'] = activity.start_datetime - now
        
        if activity.end_datetime < now:
            info['time_since_end'] = now - activity.end_datetime
        
        return info
    
    def get_status_info(self, activity):
        """Get status-related information"""
        status_colors = {
            'PLANNED': 'primary',
            'IN_PROGRESS': 'warning',
            'COMPLETED': 'success',
            'CANCELLED': 'secondary',
            'OVERDUE': 'danger',
        }
        
        current_status = activity.status
        if (current_status in ['PLANNED', 'IN_PROGRESS'] and 
            activity.end_datetime < timezone.now()):
            current_status = 'OVERDUE'
        
        return {
            'current_status': current_status,
            'status_color': status_colors.get(current_status, 'secondary'),
            'can_complete': current_status in ['PLANNED', 'IN_PROGRESS', 'OVERDUE'],
            'can_cancel': current_status in ['PLANNED', 'IN_PROGRESS'],
        }


class ActivityCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new activity"""
    
    model = Activity
    template_name = 'crm/activity/form.html'
    permission_required = 'crm.add_activity'
    fields = [
        'subject', 'description', 'activity_type', 'status', 'priority',
        'start_datetime', 'end_datetime', 'all_day', 'assigned_to',
        'location', 'meeting_url', 'reminder_set', 'reminder_minutes',
        'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter activity types
        form.fields['activity_type'].queryset = ActivityType.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Set default assigned_to
        form.initial['assigned_to'] = self.request.user
        
        # Pre-populate from related record
        content_type_id = self.request.GET.get('content_type_id')
        object_id = self.request.GET.get('object_id')
        
        if content_type_id and object_id:
            try:
                content_type = ContentType.objects.get(id=content_type_id)
                related_object = content_type.get_object_for_this_type(id=object_id)
                
                # Set subject based on related object
                if hasattr(related_object, 'name'):
                    form.initial['subject'] = f"Meeting with {related_object.name}"
                elif hasattr(related_object, 'full_name'):
                    form.initial['subject'] = f"Meeting with {related_object.full_name}"
                
                # Store related object info for form processing
                form.related_content_type = content_type
                form.related_object_id = object_id
                
            except (ContentType.DoesNotExist, AttributeError):
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        form.instance.owner = self.request.user
        
        # Set related object if provided
        if hasattr(form, 'related_content_type') and hasattr(form, 'related_object_id'):
            form.instance.content_type = form.related_content_type
            form.instance.object_id = form.related_object_id
        
        # Calculate duration if not set
        if form.instance.start_datetime and form.instance.end_datetime:
            duration = form.instance.end_datetime - form.instance.start_datetime
            form.instance.duration_minutes = int(duration.total_seconds() / 60)
        
        response = super().form_valid(form)
        
        # Create activity participant for assigned user
        if form.instance.assigned_to:
            ActivityParticipant.objects.create(
                tenant=self.request.tenant,
                activity=form.instance,
                user=form.instance.assigned_to,
                participant_type='REQUIRED',
                response='ACCEPTED' if form.instance.assigned_to == self.request.user else 'PENDING',
                created_by=self.request.user
            )
        
        # Set up reminder if requested
        if form.instance.reminder_set and form.instance.reminder_minutes:
            self.schedule_reminder(form.instance)
        
        messages.success(
            self.request,
            f'Activity "{form.instance.subject}" created successfully.'
        )
        
        return response
    
    def schedule_reminder(self, activity):
        """Schedule activity reminder"""
        try:
            from ..tasks import send_activity_reminder
            
            reminder_time = activity.start_datetime - timedelta(minutes=activity.reminder_minutes)
            
            # Schedule the reminder task
            send_activity_reminder.apply_async(
                args=[activity.id],
                eta=reminder_time
            )
            
        except Exception as e:
            # Log error but don't fail activity creation
            messages.warning(
                self.request,
                f'Activity created but reminder setup failed: {str(e)}'
            )
    
    def get_success_url(self):
        return reverse_lazy('crm:activity-detail', kwargs={'pk': self.object.pk})


class ActivityUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update activity"""
    
    model = Activity
    template_name = 'crm/activity/form.html'
    permission_required = 'crm.change_activity'
    fields = [
        'subject', 'description', 'activity_type', 'status', 'priority',
        'start_datetime', 'end_datetime', 'all_day', 'assigned_to',
        'location', 'meeting_url', 'outcome', 'result',
        'follow_up_required', 'follow_up_date', 'tags'
    ]
    
    def get_queryset(self):
        return Activity.objects.filter(tenant=self.request.tenant)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Handle status changes
        old_status = None
        if self.object.pk:
            old_activity = Activity.objects.get(pk=self.object.pk)
            old_status = old_activity.status
        
        # Auto-complete if marked as completed
        if form.instance.status == 'COMPLETED' and old_status != 'COMPLETED':
            form.instance.completed_date = timezone.now()
            form.instance.completed_by = self.request.user
        
        response = super().form_valid(form)
        
        # Handle follow-up creation
        if (form.instance.follow_up_required and 
            form.instance.follow_up_date and 
            not form.instance.follow_up_activity):
            self.create_follow_up_activity()
        
        messages.success(
            self.request,
            f'Activity "{form.instance.subject}" updated successfully.'
        )
        
        return response
    
    def create_follow_up_activity(self):
        """Create follow-up activity"""
        follow_up = Activity.objects.create(
            tenant=self.request.tenant,
            subject=f"Follow-up: {self.object.subject}",
            description=f"Follow-up activity for: {self.object.subject}",
            activity_type=self.object.activity_type,
            start_datetime=datetime.combine(
                self.object.follow_up_date,
                time(9, 0)  # Default to 9 AM
            ),
            end_datetime=datetime.combine(
                self.object.follow_up_date,
                time(10, 0)  # Default 1 hour duration
            ),
            assigned_to=self.object.assigned_to,
            owner=self.request.user,
            content_type=self.object.content_type,
            object_id=self.object.object_id,
            created_by=self.request.user
        )
        
        # Link back to original activity
        self.object.follow_up_activity = follow_up
        self.object.save(update_fields=['follow_up_activity'])
    
    def get_success_url(self):
        return reverse_lazy('crm:activity-detail', kwargs={'pk': self.object.pk})


class ActivityCompleteView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Complete activity with outcome"""
    
    permission_required = 'crm.change_activity'
    
    def post(self, request, pk):
        activity = get_object_or_404(
            Activity,
            pk=pk,
            tenant=request.tenant
        )
        
        if activity.status == 'COMPLETED':
            return JsonResponse({
                'success': False,
                'message': 'Activity is already completed'
            })
        
        try:
            outcome = request.POST.get('outcome', '')
            result = request.POST.get('result', 'SUCCESSFUL')
            
            activity.mark_completed(request.user, outcome)
            activity.result = result
            activity.save(update_fields=['result'])
            
            return JsonResponse({
                'success': True,
                'message': f'Activity "{activity.subject}" marked as completed',
                'completed_date': activity.completed_date.isoformat() if activity.completed_date else None
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class ActivityTypeManagementView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage activity types"""
    
    permission_required = 'crm.manage_activity_types'
    
    def get(self, request):
        activity_types = ActivityType.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).annotate(
            activities_count=Count('activities'),
            avg_duration=Avg('activities__duration_minutes')
        ).order_by('category', 'name')
        
        # Group by category
        types_by_category = {}
        for activity_type in activity_types:
            category = activity_type.category
            if category not in types_by_category:
                types_by_category[category] = []
            types_by_category[category].append(activity_type)
        
        context = {
            'activity_types': activity_types,
            'types_by_category': types_by_category,
            'categories': ActivityType.ACTIVITY_CATEGORIES,
        }
        
        return render(request, 'crm/activity/activity_types.html', context)
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'create_type':
            return self.create_activity_type(request)
        elif action == 'update_type':
            return self.update_activity_type(request)
        elif action == 'delete_type':
            return self.delete_activity_type(request)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def create_activity_type(self, request):
        """Create new activity type"""
        try:
            activity_type = ActivityType.objects.create(
                tenant=request.tenant,
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                category=request.POST.get('category'),
                icon=request.POST.get('icon', ''),
                color=request.POST.get('color', '#007bff'),
                requires_duration=request.POST.get('requires_duration') == 'true',
                requires_outcome=request.POST.get('requires_outcome') == 'true',
                score_impact=int(request.POST.get('score_impact', 0)),
                default_duration_minutes=int(request.POST.get('default_duration_minutes', 30)),
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Activity type "{activity_type.name}" created successfully',
                'type_id': activity_type.id
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def update_activity_type(self, request):
        """Update activity type"""
        try:
            type_id = request.POST.get('type_id')
            activity_type = get_object_or_404(
                ActivityType,
                id=type_id,
                tenant=request.tenant
            )
            
            activity_type.name = request.POST.get('name', activity_type.name)
            activity_type.description = request.POST.get('description', activity_type.description)
            activity_type.category = request.POST.get('category', activity_type.category)
            activity_type.icon = request.POST.get('icon', activity_type.icon)
            activity_type.color = request.POST.get('color', activity_type.color)
            activity_type.requires_duration = request.POST.get('requires_duration') == 'true'
            activity_type.requires_outcome = request.POST.get('requires_outcome') == 'true'
            activity_type.score_impact = int(request.POST.get('score_impact', activity_type.score_impact))
            activity_type.default_duration_minutes = int(request.POST.get('default_duration_minutes', activity_type.default_duration_minutes))
            activity_type.updated_by = request.user
            activity_type.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Activity type "{activity_type.name}" updated successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class EmailTemplateManagementView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage email templates"""
    
    permission_required = 'crm.manage_email_templates'
    
    def get(self, request):
        templates = EmailTemplate.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).annotate(
            emails_sent=Count('email_logs')
        ).order_by('template_type', 'name')
        
        # Group by type
        templates_by_type = {}
        for template in templates:
            template_type = template.template_type
            if template_type not in templates_by_type:
                templates_by_type[template_type] = []
            templates_by_type[template_type].append(template)
        
        context = {
            'templates': templates,
            'templates_by_type': templates_by_type,
            'template_types': EmailTemplate.TEMPLATE_TYPES,
        }
        
        return render(request, 'crm/activity/email_templates.html', context)


class CommunicationLogView(CRMBaseMixin, View):
    """View communication logs (emails, calls, SMS)"""
    
    def get(self, request):
        # Get communication type
        comm_type = request.GET.get('type', 'all')
        
        # Base context
        context = {
            'comm_type': comm_type,
            'types': ['all', 'email', 'call', 'sms'],
        }
        
        if comm_type == 'email' or comm_type == 'all':
            email_logs = EmailLog.objects.filter(
                tenant=request.tenant
            ).select_related(
                'template', 'campaign', 'content_type'
            ).order_by('-sent_datetime')
            
            if comm_type == 'email':
                email_logs = email_logs[:50]  # Limit for performance
            else:
                email_logs = email_logs[:10]  # Fewer for 'all' view
            
            context['email_logs'] = email_logs
        
        if comm_type == 'call' or comm_type == 'all':
            call_logs = CallLog.objects.filter(
                tenant=request.tenant
            ).select_related(
                'caller', 'recipient', 'content_type'
            ).order_by('-start_time')
            
            if comm_type == 'call':
                call_logs = call_logs[:50]
            else:
                call_logs = call_logs[:10]
            
            context['call_logs'] = call_logs
        
        if comm_type == 'sms' or comm_type == 'all':
            sms_logs = SMSLog.objects.filter(
                tenant=request.tenant
            ).select_related(
                'sender', 'content_type'
            ).order_by('-sent_datetime')
            
            if comm_type == 'sms':
                sms_logs = sms_logs[:50]
            else:
                sms_logs = sms_logs[:10]
            
            context['sms_logs'] = sms_logs
        
        # Communication statistics
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        context['stats'] = {
            'emails_today': EmailLog.objects.filter(
                tenant=request.tenant,
                sent_datetime__date=today
            ).count(),
            'calls_today': CallLog.objects.filter(
                tenant=request.tenant,
                start_time__date=today
            ).count(),
            'emails_week': EmailLog.objects.filter(
                tenant=request.tenant,
                sent_datetime__date__gte=week_start
            ).count(),
            'calls_week': CallLog.objects.filter(
                tenant=request.tenant,
                start_time__date__gte=week_start
            ).count(),
        }
        
        return render(request, 'crm/activity/communication_log.html', context)


# ============================================================================
# API ViewSets
# ============================================================================

class ActivityViewSet(CRMBaseViewSet):
    """Activity API ViewSet with comprehensive functionality"""
    
    queryset = Activity.objects.all()
    permission_classes = [ActivityPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityFilter
    search_fields = ['subject', 'description', 'location']
    ordering_fields = ['start_datetime', 'end_datetime', 'priority', 'status']
    ordering = ['-start_datetime']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ActivityDetailSerializer
        return ActivitySerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'activity_type', 'assigned_to', 'owner', 'content_type'
        ).prefetch_related(
            'participants__user'
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_activities'):
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(owner=user) | Q(participants__user=user)
            ).distinct()
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark activity as completed"""
        activity = self.get_object()
        
        if activity.status == 'COMPLETED':
            return Response(
                {'error': 'Activity is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        outcome = request.data.get('outcome', '')
        result = request.data.get('result', 'SUCCESSFUL')
        
        activity.mark_completed(request.user, outcome)
        activity.result = result
        activity.save(update_fields=['result'])
        
        return Response({
            'success': True,
            'message': 'Activity marked as completed',
            'completed_date': activity.completed_date,
            'status': activity.status
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel activity"""
        activity = self.get_object()
        
        if activity.status == 'COMPLETED':
            return Response(
                {'error': 'Cannot cancel completed activity'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activity.status = 'CANCELLED'
        activity.updated_by = request.user
        activity.save(update_fields=['status', 'updated_by'])
        
        return Response({
            'success': True,
            'message': 'Activity cancelled',
            'status': activity.status
        })
    
    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """Get activities for calendar view"""
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start and end dates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activities = self.filter_queryset(
            self.get_queryset()
        ).filter(
            start_datetime__date__range=[start, end]
        )
        
        # Format for calendar
        calendar_events = []
        for activity in activities:
            calendar_events.append({
                'id': activity.id,
                'title': activity.subject,
                'start': activity.start_datetime.isoformat(),
                'end': activity.end_datetime.isoformat(),
                'color': activity.activity_type.color if activity.activity_type else '#007bff',
                'status': activity.status,
                'priority': activity.priority,
                'assigned_to': activity.assigned_to.get_full_name() if activity.assigned_to else '',
                'location': activity.location,
                'url': f'/crm/activities/{activity.id}/',
            })
        
        return Response(calendar_events)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics"""
        user = request.user
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        
        activities = self.filter_queryset(self.get_queryset())
        
        stats = {
            'today': {
                'total': activities.filter(start_datetime__date=today).count(),
                'completed': activities.filter(
                    start_datetime__date=today,
                    status='COMPLETED'
                ).count(),
                'overdue': activities.filter(
                    start_datetime__date=today,
                    status__in=['PLANNED', 'IN_PROGRESS'],
                    end_datetime__lt=timezone.now()
                ).count(),
            },
            'week': {
                'total': activities.filter(start_datetime__date__gte=week_start).count(),
                'completed': activities.filter(
                    start_datetime__date__gte=week_start,
                    status='COMPLETED'
                ).count(),
            },
            'upcoming': list(activities.filter(
                status='PLANNED',
                start_datetime__gt=timezone.now()
            ).order_by('start_datetime')[:5].values(
                'id', 'subject', 'start_datetime', 'priority'
            )),
            'overdue': list(activities.filter(
                status__in=['PLANNED', 'IN_PROGRESS'],
                end_datetime__lt=timezone.now()
            ).order_by('end_datetime')[:5].values(
                'id', 'subject', 'end_datetime', 'priority'
            )),
        }
        
        return Response(stats)


class ActivityTypeViewSet(CRMBaseViewSet):
    """Activity Type API ViewSet"""
    
    queryset = ActivityType.objects.all()
    serializer_class = ActivityTypeSerializer
    permission_classes = [ActivityPermission]
    
    def get_queryset(self):
        return super().get_queryset().annotate(
            activities_count=Count('activities')
        )


class EmailTemplateViewSet(CRMBaseViewSet):
    """Email Template API ViewSet"""
    
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [ActivityPermission]
    
    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview email template with sample data"""
        template = self.get_object()
        
        # Sample context data
        sample_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'company': 'Sample Company',
            'email': 'john.doe@sample.com',
            'current_date': timezone.now().strftime('%Y-%m-%d'),
            'user_name': request.user.get_full_name(),
        }
        
        try:
            rendered_content = template.render_content(sample_data)
            return Response({
                'subject': rendered_content['subject'],
                'body': rendered_content['body'],
                'is_html': rendered_content['is_html']
            })
        except Exception as e:
            return Response(
                {'error': f'Template rendering failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )