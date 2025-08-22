# ============================================================================
# backend/apps/crm/serializers/activity.py - Activity Management Serializers
# ============================================================================

from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ..models import (
    ActivityType, Activity, ActivityParticipant, Note, 
    EmailTemplate, EmailLog, CallLog, SMSLog
)
from .user import UserBasicSerializer


class ActivityTypeSerializer(serializers.ModelSerializer):
    """Activity type serializer with usage statistics"""
    
    usage_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityType
        fields = [
            'id', 'name', 'description', 'category', 'icon', 'color',
            'requires_duration', 'requires_outcome', 'auto_complete',
            'score_impact', 'default_duration_minutes', 'default_reminder_minutes',
            'total_activities', 'average_duration', 'usage_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_activities', 'average_duration', 'usage_summary',
            'created_at', 'updated_at'
        ]
    
    def get_usage_summary(self, obj):
        """Get usage summary"""
        return {
            'total_activities': obj.total_activities,
            'average_duration': obj.average_duration,
            'last_30_days': obj.activities.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
        }


class ActivityParticipantSerializer(serializers.ModelSerializer):
    """Activity participant serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    attendance_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityParticipant
        fields = [
            'id', 'user', 'user_details', 'participant_type', 'response',
            'response_datetime', 'response_note', 'external_email', 'external_name',
            'attended', 'check_in_time', 'check_out_time', 'attendance_duration'
        ]
        read_only_fields = ['id', 'user_details', 'attendance_duration']
    
    def get_attendance_duration(self, obj):
        """Calculate attendance duration in minutes"""
        if obj.check_in_time and obj.check_out_time:
            duration = obj.check_out_time - obj.check_in_time
            return int(duration.total_seconds() / 60)
        return None


class ActivitySerializer(serializers.ModelSerializer):
    """Comprehensive activity serializer"""
    
    activity_type_details = ActivityTypeSerializer(source='activity_type', read_only=True)
    assigned_to_details = UserBasicSerializer(source='assigned_to', read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    completed_by_details = UserBasicSerializer(source='completed_by', read_only=True)
    
    # Generic relation fields
    related_to_type = serializers.CharField(source='content_type.model', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    
    # Participants
    participants = ActivityParticipantSerializer(many=True, read_only=True)
    participants_count = serializers.SerializerMethodField()
    
    # Status and progress
    is_overdue = serializers.SerializerMethodField()
    duration_actual = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Activity
        fields = [
            'id', 'activity_number', 'subject', 'description',
            # Classification
            'activity_type', 'activity_type_details', 'status', 'priority',
            # Scheduling
            'start_datetime', 'end_datetime', 'duration_minutes', 'all_day',
            'duration_actual', 'is_overdue',
            # Assignment
            'assigned_to', 'assigned_to_details', 'owner', 'owner_details',
            # Related entity
            'content_type', 'object_id', 'related_to_type', 'related_to_name',
            # Location & meeting
            'location', 'meeting_url', 'meeting_password',
            # Outcome
            'outcome', 'result', 'completion_percentage',
            # Follow-up
            'follow_up_required', 'follow_up_date', 'follow_up_activity',
            # Reminders
            'reminder_set', 'reminder_minutes', 'reminder_sent',
            # Completion
            'completed_date', 'completed_by', 'completed_by_details',
            # Participants
            'participants', 'participants_count',
            # Additional
            'tags', 'attachments',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'activity_number', 'activity_type_details', 'assigned_to_details',
            'owner_details', 'completed_by_details', 'related_to_type', 'related_to_name',
            'participants', 'participants_count', 'duration_actual', 'is_overdue',
            'completion_percentage', 'created_at', 'updated_at'
        ]
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            if hasattr(obj.related_to, 'name'):
                return obj.related_to.name
            elif hasattr(obj.related_to, 'full_name'):
                return obj.related_to.full_name
            elif hasattr(obj.related_to, '__str__'):
                return str(obj.related_to)
        return None
    
    def get_participants_count(self, obj):
        """Get participants count"""
        return obj.participants.count()
    
    def get_is_overdue(self, obj):
        """Check if activity is overdue"""
        if obj.status in ['PLANNED', 'IN_PROGRESS'] and obj.end_datetime:
            return timezone.now() > obj.end_datetime
        return False
    
    def get_duration_actual(self, obj):
        """Get actual duration if completed"""
        if obj.completed_date and obj.start_datetime:
            duration = obj.completed_date - obj.start_datetime
            return int(duration.total_seconds() / 60)
        return None
    
    def get_completion_percentage(self, obj):
        """Calculate completion percentage"""
        if obj.status == 'COMPLETED':
            return 100
        elif obj.status == 'IN_PROGRESS':
            if obj.start_datetime and obj.end_datetime:
                now = timezone.now()
                if now >= obj.start_datetime:
                    total_duration = obj.end_datetime - obj.start_datetime
                    elapsed_duration = now - obj.start_datetime
                    if elapsed_duration >= total_duration:
                        return 100
                    return int((elapsed_duration.total_seconds() / total_duration.total_seconds()) * 100)
        return 0
    
    def validate(self, data):
        """Validate activity data"""
        start_datetime = data.get('start_datetime')
        end_datetime = data.get('end_datetime')
        
        if start_datetime and end_datetime:
            if start_datetime >= end_datetime:
                raise serializers.ValidationError({
                    'end_datetime': 'End datetime must be after start datetime'
                })
        
        return data


class NoteSerializer(serializers.ModelSerializer):
    """Note serializer with rich content support"""
    
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    last_edited_by_details = UserBasicSerializer(source='last_edited_by', read_only=True)
    activity_details = serializers.SerializerMethodField()
    
    # Generic relation fields
    related_to_type = serializers.CharField(source='content_type.model', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    
    # Sharing info
    shared_with_details = UserBasicSerializer(source='shared_with', many=True, read_only=True)
    is_shared = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'note_type', 'is_html',
            # Relations
            'content_type', 'object_id', 'related_to_type', 'related_to_name',
            'activity', 'activity_details',
            # Privacy & sharing
            'is_private', 'shared_with', 'shared_with_details', 'is_shared',
            # Metadata
            'tags', 'created_by_details', 'last_edited_by', 'last_edited_by_details',
            'edit_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by_details', 'last_edited_by_details', 'activity_details',
            'related_to_type', 'related_to_name', 'shared_with_details', 'is_shared',
            'edit_history', 'created_at', 'updated_at'
        ]
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            if hasattr(obj.related_to, 'name'):
                return obj.related_to.name
            elif hasattr(obj.related_to, 'full_name'):
                return obj.related_to.full_name
            return str(obj.related_to)
        return None
    
    def get_activity_details(self, obj):
        """Get activity details if linked"""
        if obj.activity:
            return {
                'id': obj.activity.id,
                'subject': obj.activity.subject,
                'activity_type': obj.activity.activity_type.name
            }
        return None
    
    def get_is_shared(self, obj):
        """Check if note is shared"""
        return obj.shared_with.exists()


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Email template serializer with usage tracking"""
    
    usage_stats = serializers.SerializerMethodField()
    preview_data = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'subject',
            'body_text', 'body_html', 'available_variables', 'merge_tags',
            'is_active', 'is_system_template', 'usage_count', 'last_used',
            'sender_name', 'sender_email', 'reply_to_email', 'default_attachments',
            'usage_stats', 'preview_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'usage_count', 'last_used', 'usage_stats', 'preview_data',
            'created_at', 'updated_at'
        ]
    
    def get_usage_stats(self, obj):
        """Get usage statistics"""
        return {
            'total_usage': obj.usage_count,
            'last_30_days': obj.email_logs.filter(
                sent_datetime__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
            'success_rate': self._calculate_success_rate(obj)
        }
    
    def get_preview_data(self, obj):
        """Get preview with sample data"""
        sample_context = {
            'first_name': 'John',
            'last_name': 'Doe',
            'company': 'Sample Company',
            'email': 'john.doe@example.com'
        }
        
        try:
            rendered = obj.render_content(sample_context)
            return {
                'subject': rendered['subject'][:100] + '...' if len(rendered['subject']) > 100 else rendered['subject'],
                'body_preview': rendered['body'][:200] + '...' if len(rendered['body']) > 200 else rendered['body']
            }
        except:
            return {'subject': obj.subject, 'body_preview': 'Preview unavailable'}
    
    def _calculate_success_rate(self, obj):
        """Calculate email success rate"""
        total_emails = obj.email_logs.count()
        if total_emails == 0:
            return 0
        
        successful_emails = obj.email_logs.filter(
            status__in=['SENT', 'DELIVERED', 'OPENED', 'CLICKED']
        ).count()
        
        return (successful_emails / total_emails) * 100


class EmailLogSerializer(serializers.ModelSerializer):
    """Email log serializer with tracking details"""
    
    template_details = EmailTemplateSerializer(source='template', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    
    # Engagement metrics
    engagement_score = serializers.SerializerMethodField()
    time_to_open = serializers.SerializerMethodField()
    time_to_click = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'subject', 'sender_email', 'sender_name', 'recipient_email',
            'recipient_name', 'cc_emails', 'bcc_emails', 'body_text', 'body_html',
            # Template and campaign
            'template', 'template_details', 'campaign', 'campaign_name',
            # Status and tracking
            'status', 'sent_datetime', 'delivered_datetime', 'opened_datetime',
            'clicked_datetime', 'replied_datetime', 'open_count', 'click_count',
            # Relations
            'content_type', 'object_id', 'related_to_name',
            # Technical details
            'message_id', 'provider', 'provider_message_id', 'error_message',
            'bounce_reason', 'attachments',
            # Engagement metrics
            'engagement_score', 'time_to_open', 'time_to_click',
            'created_at'
        ]
        read_only_fields = [
            'id', 'template_details', 'campaign_name', 'related_to_name',
            'engagement_score', 'time_to_open', 'time_to_click', 'created_at'
        ]
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            return str(obj.related_to)
        return None
    
    def get_engagement_score(self, obj):
        """Calculate engagement score"""
        score = 0
        if obj.opened_datetime:
            score += 20
        if obj.clicked_datetime:
            score += 30
        if obj.replied_datetime:
            score += 50
        return score
    
    def get_time_to_open(self, obj):
        """Get time to open in minutes"""
        if obj.sent_datetime and obj.opened_datetime:
            duration = obj.opened_datetime - obj.sent_datetime
            return int(duration.total_seconds() / 60)
        return None
    
    def get_time_to_click(self, obj):
        """Get time to click in minutes"""
        if obj.sent_datetime and obj.clicked_datetime:
            duration = obj.clicked_datetime - obj.sent_datetime
            return int(duration.total_seconds() / 60)
        return None


class CallLogSerializer(serializers.ModelSerializer):
    """Call log serializer with outcome tracking"""
    
    caller_details = UserBasicSerializer(source='caller', read_only=True)
    recipient_details = UserBasicSerializer(source='recipient', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    
    # Call metrics
    call_quality_score = serializers.SerializerMethodField()
    follow_up_status = serializers.SerializerMethodField()
    
    class Meta:
        model = CallLog
        fields = [
            'id', 'call_type', 'phone_number', 'caller_name',
            # Timing
            'start_time', 'end_time', 'duration_seconds',
            # Participants
            'caller', 'caller_details', 'recipient', 'recipient_details',
            # Status and outcome
            'status', 'outcome', 'call_quality_score',
            # Relations
            'content_type', 'object_id', 'related_to_name',
            # Notes and follow-up
            'notes', 'agenda', 'follow_up_required', 'follow_up_date',
            'follow_up_notes', 'follow_up_status',
            # Recording
            'recording_url', 'transcription',
            # Integration
            'phone_system_id', 'external_call_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'caller_details', 'recipient_details', 'related_to_name',
            'call_quality_score', 'follow_up_status', 'created_at', 'updated_at'
        ]
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            return str(obj.related_to)
        return None
    
    def get_call_quality_score(self, obj):
        """Calculate call quality score based on outcome"""
        quality_mapping = {
            'SUCCESSFUL': 90,
            'APPOINTMENT_SET': 95,
            'FOLLOW_UP_REQUIRED': 70,
            'NOT_INTERESTED': 30,
            'WRONG_NUMBER': 10,
            'CALLBACK_REQUESTED': 60
        }
        return quality_mapping.get(obj.outcome, 50)
    
    def get_follow_up_status(self, obj):
        """Get follow-up status"""
        if not obj.follow_up_required:
            return 'Not Required'
        elif obj.follow_up_date:
            if obj.follow_up_date < timezone.now().date():
                return 'Overdue'
            elif obj.follow_up_date == timezone.now().date():
                return 'Due Today'
            else:
                return 'Scheduled'
        else:
            return 'Not Scheduled'


class SMSLogSerializer(serializers.ModelSerializer):
    """SMS log serializer"""
    
    sender_details = UserBasicSerializer(source='sender', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    
    class Meta:
        model = SMSLog
        fields = [
            'id', 'sms_type', 'phone_number', 'message', 'sender',
            'sender_details', 'recipient_name', 'status', 'sent_datetime',
            'delivered_datetime', 'delivery_status',
            # Relations
            'content_type', 'object_id', 'related_to_name',
            # Provider details
            'provider', 'provider_message_id', 'cost', 'error_message',
            'created_at'
        ]
        read_only_fields = [
            'id', 'sender_details', 'related_to_name', 'delivery_status',
            'created_at'
        ]
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            return str(obj.related_to)
        return None
    
    def get_delivery_status(self, obj):
        """Get delivery status description"""
        status_mapping = {
            'SENT': 'Message sent successfully',
            'DELIVERED': 'Message delivered to recipient',
            'FAILED': f'Delivery failed: {obj.error_message}' if obj.error_message else 'Delivery failed',
            'RECEIVED': 'Message received'
        }
        return status_mapping.get(obj.status, 'Unknown status')