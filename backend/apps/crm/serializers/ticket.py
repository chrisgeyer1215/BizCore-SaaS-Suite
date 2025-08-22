# ============================================================================
# backend/apps/crm/serializers/ticket.py - Customer Service & Ticket Management
# ============================================================================

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from ..models import TicketCategory, SLA, Ticket, TicketComment, KnowledgeBase
from .user import UserBasicSerializer
from .account import AccountSerializer, ContactBasicSerializer


class TicketCategorySerializer(serializers.ModelSerializer):
    """Ticket category serializer with performance metrics"""
    
    parent_category_name = serializers.CharField(source='parent_category.name', read_only=True)
    subcategories_count = serializers.SerializerMethodField()
    average_resolution_time = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketCategory
        fields = [
            'id', 'name', 'description', 'color', 'icon', 'parent_category',
            'parent_category_name', 'level', 'is_public', 'restricted_access',
            'allowed_users', 'max_file_size_mb', 'allowed_file_types',
            'require_approval', 'total_tickets', 'resolved_tickets',
            'average_resolution_hours', 'is_active', 'sort_order',
            'subcategories_count', 'average_resolution_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_category_name', 'level', 'total_tickets',
            'resolved_tickets', 'average_resolution_hours', 'subcategories_count',
            'average_resolution_time', 'created_at', 'updated_at'
        ]
    
    def get_subcategories_count(self, obj):
        """Get count of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    
    def get_average_resolution_time(self, obj):
        """Get human-readable resolution time"""
        hours = obj.average_resolution_hours
        if hours < 24:
            return f"{hours:.1f} hours"
        else:
            days = hours / 24
            return f"{days:.1f} days"


class SLASerializer(serializers.ModelSerializer):
    """SLA serializer with compliance tracking"""
    
    compliance_rate = serializers.SerializerMethodField()
    violations_this_month = serializers.SerializerMethodField()
    
    class Meta:
        model = SLA
        fields = [
            'id', 'name', 'description', 'priority_level', 'response_time_hours',
            'resolution_time_hours', 'escalation_time_hours', 'business_hours_only',
            'is_active', 'auto_escalate', 'escalation_email_template',
            'total_tickets', 'met_response_time', 'met_resolution_time',
            'compliance_rate', 'violations_this_month',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_tickets', 'met_response_time', 'met_resolution_time',
            'compliance_rate', 'violations_this_month', 'created_at', 'updated_at'
        ]
    
    def get_compliance_rate(self, obj):
        """Calculate SLA compliance rate"""
        if obj.total_tickets > 0:
            return (obj.met_response_time / obj.total_tickets) * 100
        return 100
    
    def get_violations_this_month(self, obj):
        """Get SLA violations this month"""
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return obj.tickets.filter(
            created_at__gte=start_of_month,
            sla_violated=True
        ).count()


class TicketCommentSerializer(serializers.ModelSerializer):
    """Ticket comment serializer"""
    
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    time_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketComment
        fields = [
            'id', 'comment', 'is_internal', 'is_solution', 'created_by',
            'created_by_details', 'time_since_created', 'attachments',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by_details', 'time_since_created', 'created_at', 'updated_at'
        ]
    
    def get_time_since_created(self, obj):
        """Get human-readable time since created"""
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class TicketSerializer(serializers.ModelSerializer):
    """Comprehensive ticket serializer with SLA tracking"""
    
    category_details = TicketCategorySerializer(source='category', read_only=True)
    sla_details = SLASerializer(source='sla', read_only=True)
    assigned_to_details = UserBasicSerializer(source='assigned_to', read_only=True)
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    resolved_by_details = UserBasicSerializer(source='resolved_by', read_only=True)
    
    # Related entities
    account_details = AccountSerializer(source='account', read_only=True)
    contact_details = ContactBasicSerializer(source='contact', read_only=True)
    
    # Comments
    comments = TicketCommentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    
    # SLA and time tracking
    sla_status = serializers.SerializerMethodField()
    time_to_response = serializers.SerializerMethodField()
    time_to_resolution = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    # Status indicators
    urgency_level = serializers.SerializerMethodField()
    satisfaction_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'subject', 'description', 'status', 'priority',
            'source', 'channel',
            # Classification
            'category', 'category_details', 'subcategory', 'issue_type',
            # Assignment
            'assigned_to', 'assigned_to_details', 'assigned_date', 'team',
            # SLA
            'sla', 'sla_details', 'sla_status', 'sla_violated',
            # Related entities
            'account', 'account_details', 'contact', 'contact_details',
            # Resolution
            'resolution', 'resolution_time_minutes', 'resolved_by',
            'resolved_by_details', 'resolved_date',
            # Time tracking
            'first_response_date', 'time_to_response', 'time_to_resolution',
            'time_remaining', 'is_overdue',
            # Customer feedback
            'customer_satisfaction', 'customer_feedback',
            'satisfaction_rating', 'feedback_date',
            # Escalation
            'escalated', 'escalated_date', 'escalated_to', 'escalation_reason',
            # Reopening
            'reopened', 'reopen_count', 'last_reopen_date', 'reopen_reason',
            # Additional
            'tags', 'custom_fields', 'attachments', 'urgency_level',
            # Comments
            'comments', 'comments_count',
            # Audit
            'created_by', 'created_by_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'ticket_number', 'category_details', 'sla_details',
            'assigned_to_details', 'created_by_details', 'resolved_by_details',
            'account_details', 'contact_details', 'comments', 'comments_count',
            'sla_status', 'time_to_response', 'time_to_resolution', 'time_remaining',
            'is_overdue', 'urgency_level', 'satisfaction_rating',
            'resolution_time_minutes', 'created_at', 'updated_at'
        ]
    
    def get_comments_count(self, obj):
        """Get comments count"""
        return obj.comments.count()
    
    def get_sla_status(self, obj):
        """Get SLA compliance status"""
        if not obj.sla:
            return 'No SLA'
        
        if obj.status == 'RESOLVED':
            if obj.sla_violated:
                return 'Violated'
            else:
                return 'Met'
        
        # For open tickets, check if we're close to violation
        now = timezone.now()
        if obj.sla.response_time_hours and not obj.first_response_date:
            response_deadline = obj.created_at + timedelta(hours=obj.sla.response_time_hours)
            if now > response_deadline:
                return 'Response Overdue'
            elif now > response_deadline - timedelta(hours=2):
                return 'Response Due Soon'
        
        if obj.sla.resolution_time_hours:
            resolution_deadline = obj.created_at + timedelta(hours=obj.sla.resolution_time_hours)
            if now > resolution_deadline:
                return 'Resolution Overdue'
            elif now > resolution_deadline - timedelta(hours=4):
                return 'Resolution Due Soon'
        
        return 'On Track'
    
    def get_time_to_response(self, obj):
        """Get time to first response in minutes"""
        if obj.first_response_date:
            duration = obj.first_response_date - obj.created_at
            return int(duration.total_seconds() / 60)
        return None
    
    def get_time_to_resolution(self, obj):
        """Get time to resolution in minutes"""
        if obj.resolved_date:
            duration = obj.resolved_date - obj.created_at
            return int(duration.total_seconds() / 60)
        return None
    
    def get_time_remaining(self, obj):
        """Get time remaining until SLA violation"""
        if obj.status == 'RESOLVED' or not obj.sla:
            return None
        
        now = timezone.now()
        
        # Check response time remaining
        if obj.sla.response_time_hours and not obj.first_response_date:
            response_deadline = obj.created_at + timedelta(hours=obj.sla.response_time_hours)
            if now < response_deadline:
                remaining = response_deadline - now
                return {
                    'type': 'response',
                    'minutes': int(remaining.total_seconds() / 60),
                    'formatted': self._format_duration(remaining)
                }
        
        # Check resolution time remaining
        if obj.sla.resolution_time_hours:
            resolution_deadline = obj.created_at + timedelta(hours=obj.sla.resolution_time_hours)
            if now < resolution_deadline:
                remaining = resolution_deadline - now
                return {
                    'type': 'resolution',
                    'minutes': int(remaining.total_seconds() / 60),
                    'formatted': self._format_duration(remaining)
                }
        
        return None
    
    def get_is_overdue(self, obj):
        """Check if ticket is overdue"""
        return obj.sla_violated or self.get_sla_status(obj) in ['Response Overdue', 'Resolution Overdue']
    
    def get_urgency_level(self, obj):
        """Calculate urgency level"""
        score = 0
        
        # Priority factor
        priority_scores = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}
        score += priority_scores.get(obj.priority, 1)
        
        # SLA factor
        sla_status = self.get_sla_status(obj)
        if sla_status in ['Response Overdue', 'Resolution Overdue']:
            score += 3
        elif sla_status in ['Response Due Soon', 'Resolution Due Soon']:
            score += 2
        
        # Age factor
        age_days = (timezone.now() - obj.created_at).days
        if age_days > 7:
            score += 2
        elif age_days > 3:
            score += 1
        
        # Customer factor
        if obj.account and obj.account.account_type in ['CUSTOMER', 'PARTNER']:
            score += 1
        
        if score >= 8:
            return 'Critical'
        elif score >= 6:
            return 'High'
        elif score >= 4:
            return 'Medium'
        else:
            return 'Low'
    
    def get_satisfaction_rating(self, obj):
        """Get satisfaction rating description"""
        if obj.customer_satisfaction:
            rating_map = {1: 'Very Unsatisfied', 2: 'Unsatisfied', 3: 'Neutral', 4: 'Satisfied', 5: 'Very Satisfied'}
            return rating_map.get(obj.customer_satisfaction, 'Unknown')
        return None
    
    def _format_duration(self, duration):
        """Format duration as human-readable string"""
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def validate(self, data):
        """Validate ticket data"""
        # Ensure contact belongs to account if both are provided
        account = data.get('account')
        contact = data.get('contact')
        
        if account and contact:
            if contact.account != account:
                raise serializers.ValidationError({
                    'contact': 'Contact must belong to the selected account'
                })
        
        return data


class TicketDetailSerializer(TicketSerializer):
    """Detailed ticket serializer with complete information"""
    
    related_tickets = serializers.SerializerMethodField()
    activity_timeline = serializers.SerializerMethodField()
    escalation_history = serializers.SerializerMethodField()
    
    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + [
            'related_tickets', 'activity_timeline', 'escalation_history'
        ]
    
    def get_related_tickets(self, obj):
        """Get related tickets"""
        related = []
        
        if obj.account:
            recent_tickets = obj.account.tickets.filter(
                is_active=True
            ).exclude(id=obj.id).order_by('-created_at')[:5]
            
            for ticket in recent_tickets:
                related.append({
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'created_at': ticket.created_at
                })
        
        return related
    
    def get_activity_timeline(self, obj):
        """Get ticket activity timeline"""
        timeline = []
        
        # Creation
        timeline.append({
            'type': 'created',
            'datetime': obj.created_at,
            'user': obj.created_by.get_full_name() if obj.created_by else 'System',
            'description': f'Ticket created with priority {obj.priority}'
        })
        
        # Assignment
        if obj.assigned_date:
            timeline.append({
                'type': 'assigned',
                'datetime': obj.assigned_date,
                'user': 'System',
                'description': f'Assigned to {obj.assigned_to.get_full_name()}'
            })
        
        # First response
        if obj.first_response_date:
            timeline.append({
                'type': 'responded',
                'datetime': obj.first_response_date,
                'user': obj.assigned_to.get_full_name() if obj.assigned_to else 'Support',
                'description': 'First response provided'
            })
        
        # Escalation
        if obj.escalated_date:
            timeline.append({
                'type': 'escalated',
                'datetime': obj.escalated_date,
                'user': 'System',
                'description': f'Escalated: {obj.escalation_reason}'
            })
        
        # Resolution
        if obj.resolved_date:
            timeline.append({
                'type': 'resolved',
                'datetime': obj.resolved_date,
                'user': obj.resolved_by.get_full_name() if obj.resolved_by else 'System',
                'description': 'Ticket resolved'
            })
        
        # Comments
        for comment in obj.comments.all():
            timeline.append({
                'type': 'comment',
                'datetime': comment.created_at,
                'user': comment.created_by.get_full_name(),
                'description': f'{"Internal note" if comment.is_internal else "Comment"} added',
                'comment_id': comment.id
            })
        
        return sorted(timeline, key=lambda x: x['datetime'])
    
    def get_escalation_history(self, obj):
        """Get escalation history"""
        # This would track escalation history if stored separately
        history = []
        
        if obj.escalated:
            history.append({
                'date': obj.escalated_date,
                'reason': obj.escalation_reason,
                'escalated_to': obj.escalated_to.get_full_name() if obj.escalated_to else 'Manager'
            })
        
        return history


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    """Knowledge base article serializer"""
    
    category_details = TicketCategorySerializer(source='category', read_only=True)
    author_details = UserBasicSerializer(source='author', read_only=True)
    
    # Usage metrics
    usage_stats = serializers.SerializerMethodField()
    helpfulness_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = KnowledgeBase
        fields = [
            'id', 'title', 'content', 'summary', 'article_type',
            'category', 'category_details', 'tags', 'keywords',
            # Visibility
            'is_public', 'is_featured', 'is_published',
            # Authoring
            'author', 'author_details', 'reviewed_by', 'reviewed_date',
            # Usage
            'view_count', 'helpful_votes', 'not_helpful_votes',
            'usage_stats', 'helpfulness_rating',
            # SEO
            'slug', 'meta_description',
            # Attachments
            'attachments', 'related_articles',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'category_details', 'author_details', 'view_count',
            'helpful_votes', 'not_helpful_votes', 'usage_stats',
            'helpfulness_rating', 'slug', 'created_at', 'updated_at'
        ]
    
    def get_usage_stats(self, obj):
        """Get usage statistics"""
        return {
            'total_views': obj.view_count,
            'monthly_views': self._get_monthly_views(obj),
            'avg_daily_views': obj.view_count / max((timezone.now() - obj.created_at).days, 1)
        }
    
    def get_helpfulness_rating(self, obj):
        """Calculate helpfulness rating"""
        total_votes = obj.helpful_votes + obj.not_helpful_votes
        if total_votes > 0:
            return (obj.helpful_votes / total_votes) * 100
        return None
    
    def _get_monthly_views(self, obj):
        """Get views in the last 30 days"""
        # This would require storing view logs with timestamps
        # For now, return an estimate
        return int(obj.view_count * 0.3)  # Assume 30% of views are recent


class TicketBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk ticket updates"""
    
    ticket_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    # Fields that can be bulk updated
    status = serializers.ChoiceField(
        choices=Ticket.STATUS_CHOICES,
        required=False
    )
    priority = serializers.ChoiceField(
        choices=Ticket.PRIORITY_CHOICES,
        required=False
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.all(),
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_ticket_ids(self, value):
        """Validate ticket IDs"""
        tenant = self.context['request'].user.tenant
        existing_tickets = Ticket.objects.filter(
            tenant=tenant,
            id__in=value,
            is_active=True,
            status__in=['OPEN', 'IN_PROGRESS', 'WAITING_CUSTOMER']
        ).count()
        
        if existing_tickets != len(value):
            raise serializers.ValidationError("Some ticket IDs are invalid or cannot be updated")
        
        return value


class TicketEscalationSerializer(serializers.Serializer):
    """Serializer for ticket escalation"""
    
    escalation_reason = serializers.CharField(max_length=500)
    escalated_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    priority = serializers.ChoiceField(
        choices=Ticket.PRIORITY_CHOICES,
        required=False
    )
    internal_note = serializers.CharField(max_length=1000, required=False)
    
    def validate_escalation_reason(self, value):
        """Validate escalation reason"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Escalation reason must be at least 10 characters")
        return value