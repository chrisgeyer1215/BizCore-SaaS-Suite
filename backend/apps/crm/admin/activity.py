# ============================================================================
# backend/apps/crm/admin/activity.py - Comprehensive Activity Management Admin
# ============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

from .base import TenantAwareAdmin, EnhancedTabularInline, AdvancedDateRangeFilter
from ..models import (
    Activity, ActivityType, EmailLog, CallLog, SMSLog, Note,
    ActivityParticipant, Lead, Account, Contact, Opportunity
)


class ActivityParticipantInline(EnhancedTabularInline):
    """Inline admin for activity participants"""
    model = ActivityParticipant
    fields = ['participant_type', 'contact', 'email', 'response_status']
    extra = 0


class ActivityAdmin(TenantAwareAdmin):
    """Comprehensive activity management admin"""
    
    list_display = [
        'subject', 'activity_type', 'status', 'priority', 'start_datetime',
        'assigned_to', 'related_to_display', 'completion_status', 'status_indicator'
    ]
    
    list_filter = [
        'activity_type', 'status', 'priority', 'assigned_to',
        AdvancedDateRangeFilter, 'is_completed', 'is_high_priority'
    ]
    
    search_fields = [
        'subject', 'description', 'assigned_to__username',
        'related_lead__first_name', 'related_lead__last_name',
        'related_account__name', 'related_contact__first_name'
    ]
    
    list_editable = ['status', 'priority', 'assigned_to']
    list_select_related = [
        'activity_type', 'assigned_to', 'related_lead', 
        'related_account', 'related_contact', 'related_opportunity'
    ]
    
    fieldsets = (
        ('Activity Information', {
            'fields': (
                ('subject', 'activity_type'),
                ('status', 'priority'),
                ('start_datetime', 'end_datetime'),
                ('assigned_to', 'owner')
            )
        }),
        ('Related Records', {
            'fields': (
                ('related_lead', 'related_account'),
                ('related_contact', 'related_opportunity'),
                'related_campaign'
            )
        }),
        ('Details', {
            'fields': (
                'description', 'location', 'meeting_link',
                'outcome', 'follow_up_required'
            )
        }),
        ('Completion', {
            'fields': (
                ('is_completed', 'completed_at'),
                ('completion_notes', 'actual_duration'),
                'next_activity_due'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                ('created_at', 'updated_at'),
                ('created_by', 'updated_by'),
                ('reminder_sent', 'last_reminder_sent')
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'completed_at', 'reminder_sent', 'last_reminder_sent'
    ]
    
    inlines = [ActivityParticipantInline]
    
    actions = [
        'assign_to_me', 'mark_completed', 'mark_high_priority',
        'schedule_follow_up', 'send_reminders', 'bulk_reschedule'
    ]
    
    def related_to_display(self, obj):
        """Display related record with link"""
        if obj.related_lead:
            url = reverse('admin:crm_lead_change', args=[obj.related_lead.id])
            return format_html(
                '<a href="{}">👤 {} {}</a>',
                url, obj.related_lead.first_name, obj.related_lead.last_name
            )
        elif obj.related_account:
            url = reverse('admin:crm_account_change', args=[obj.related_account.id])
            return format_html(
                '<a href="{}">🏢 {}</a>',
                url, obj.related_account.name
            )
        elif obj.related_opportunity:
            url = reverse('admin:crm_opportunity_change', args=[obj.related_opportunity.id])
            return format_html(
                '<a href="{}">💼 {}</a>',
                url, obj.related_opportunity.name
            )
        elif obj.related_contact:
            url = reverse('admin:crm_contact_change', args=[obj.related_contact.id])
            return format_html(
                '<a href="{}">📞 {} {}</a>',
                url, obj.related_contact.first_name, obj.related_contact.last_name
            )
        return 'No relation'
    
    related_to_display.short_description = 'Related To'
    
    def completion_status(self, obj):
        """Display completion status with visual indicators"""
        if obj.is_completed:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Completed</span>'
            )
        elif obj.start_datetime and obj.start_datetime < timezone.now():
            return format_html(
                '<span style="color: red; font-weight: bold;">⏰ Overdue</span>'
            )
        elif obj.start_datetime:
            days_until = (obj.start_datetime - timezone.now()).days
            if days_until == 0:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">📅 Today</span>'
                )
            elif days_until == 1:
                return format_html(
                    '<span style="color: blue; font-weight: bold;">📅 Tomorrow</span>'
                )
            else:
                return format_html(
                    '<span style="color: gray;">📅 In {} days</span>',
                    days_until
                )
        return 'Not scheduled'
    
    completion_status.short_description = 'Status'
    
    # Admin Actions
    def assign_to_me(self, request, queryset):
        """Assign selected activities to current user"""
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} activities assigned to you.')
    
    assign_to_me.short_description = "Assign to me"
    
    def mark_completed(self, request, queryset):
        """Mark activities as completed"""
        updated = queryset.update(
            is_completed=True,
            completed_at=timezone.now(),
            status='completed'
        )
        self.message_user(request, f'{updated} activities marked as completed.')
    
    mark_completed.short_description = "Mark as completed"
    
    def mark_high_priority(self, request, queryset):
        """Mark activities as high priority"""
        updated = queryset.update(
            priority='high',
            is_high_priority=True
        )
        self.message_user(request, f'{updated} activities marked as high priority.')
    
    mark_high_priority.short_description = "Mark as high priority"
    
    def schedule_follow_up(self, request, queryset):
        """Schedule follow-up activities"""
        from ..tasks.activity_tasks import create_follow_up_activity
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for activity in queryset:
            create_follow_up_activity.delay(
                original_activity_id=activity.id,
                days_offset=7,
                security_context=security_context
            )
        
        self.message_user(request, f'Follow-up activities scheduled for {queryset.count()} items.')
    
    schedule_follow_up.short_description = "Schedule follow-up"
    
    def send_reminders(self, request, queryset):
        """Send reminders for selected activities"""
        from ..tasks.activity_tasks import send_activity_reminders
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        activity_ids = list(queryset.values_list('id', flat=True))
        send_activity_reminders.delay(
            activity_ids=activity_ids,
            security_context=security_context
        )
        
        self.message_user(request, f'Reminders queued for {len(activity_ids)} activities.')
    
    send_reminders.short_description = "Send reminders"


class ActivityTypeAdmin(TenantAwareAdmin):
    """Activity type management admin"""
    
    list_display = [
        'name', 'category', 'icon', 'default_duration', 'is_system',
        'activity_count', 'completion_rate', 'status_indicator'
    ]
    
    list_filter = ['category', 'is_system', 'is_active']
    search_fields = ['name', 'description']
    
    fieldsets = (
        ('Type Information', {
            'fields': ('name', 'description', 'category', 'icon')
        }),
        ('Configuration', {
            'fields': (
                ('default_duration', 'reminder_minutes'),
                ('is_system', 'is_active'),
                ('color_code', 'sort_order')
            )
        }),
        ('Automation', {
            'fields': (
                'auto_complete_rules', 'follow_up_template',
                'notification_template'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Add activity count annotation"""
        return super().get_queryset(request).annotate(
            total_activities=Count('activities'),
            completed_activities=Count('activities', filter=Q(activities__is_completed=True))
        )
    
    def activity_count(self, obj):
        """Display total activity count"""
        return obj.total_activities
    
    activity_count.short_description = 'Activities'
    activity_count.admin_order_field = 'total_activities'
    
    def completion_rate(self, obj):
        """Calculate completion rate"""
        if obj.total_activities > 0:
            rate = (obj.completed_activities / obj.total_activities) * 100
            color = 'green' if rate >= 80 else 'orange' if rate >= 60 else 'red'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return '0%'
    
    completion_rate.short_description = 'Completion Rate'


class EmailLogAdmin(TenantAwareAdmin):
    """Email log management admin"""
    
    list_display = [
        'subject', 'to_email', 'email_type', 'status', 'sent_at',
        'opened_at', 'clicked_at', 'bounce_status', 'status_indicator'
    ]
    
    list_filter = [
        'status', 'email_type', 'bounce_status',
        AdvancedDateRangeFilter, 'is_opened', 'is_clicked'
    ]
    
    search_fields = ['subject', 'to_email', 'from_email', 'message_id']
    readonly_fields = [
        'sent_at', 'opened_at', 'clicked_at', 'bounced_at',
        'message_id', 'provider_response'
    ]
    
    fieldsets = (
        ('Email Information', {
            'fields': (
                ('subject', 'email_type'),
                ('from_email', 'to_email'),
                ('cc_emails', 'bcc_emails')
            )
        }),
        ('Content', {
            'fields': ('html_content', 'text_content', 'attachments')
        }),
        ('Tracking', {
            'fields': (
                ('status', 'sent_at'),
                ('opened_at', 'clicked_at'),
                ('bounce_status', 'bounced_at'),
                'tracking_pixel_url'
            ),
            'classes': ('collapse',)
        }),
        ('Related Records', {
            'fields': (
                ('related_activity', 'related_campaign'),
                ('related_lead', 'related_contact')
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                ('message_id', 'provider_response'),
                ('created_at', 'updated_at'),
                ('created_by', 'tenant')
            ),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Email logs are created automatically"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Email logs are read-only"""
        return False


class CallLogAdmin(TenantAwareAdmin):
    """Call log management admin"""
    
    list_display = [
        'phone_number', 'call_type', 'duration_display', 'status',
        'start_time', 'assigned_to', 'outcome', 'status_indicator'
    ]
    
    list_filter = [
        'call_type', 'status', 'outcome', 'assigned_to',
        AdvancedDateRangeFilter
    ]
    
    search_fields = ['phone_number', 'notes', 'assigned_to__username']
    
    fieldsets = (
        ('Call Information', {
            'fields': (
                ('phone_number', 'call_type'),
                ('start_time', 'end_time'),
                ('assigned_to', 'status')
            )
        }),
        ('Call Details', {
            'fields': (
                ('duration_seconds', 'outcome'),
                'notes', 'recording_url'
            )
        }),
        ('Related Records', {
            'fields': (
                ('related_activity', 'related_lead'),
                ('related_contact', 'related_account')
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['duration_seconds']
    
    def duration_display(self, obj):
        """Format call duration for display"""
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f'{minutes}:{seconds:02d}'
        return 'Unknown'
    
    duration_display.short_description = 'Duration'
    duration_display.admin_order_field = 'duration_seconds'