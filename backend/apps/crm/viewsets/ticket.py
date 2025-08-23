# crm/viewsets/ticket.py
"""
Ticket Management ViewSets

Provides REST API endpoints for:
- Customer support ticket management with SLA tracking
- Ticket category and priority management
- SLA management and monitoring
- Knowledge base article management
- Ticket analytics and reporting
- Customer satisfaction tracking
- Escalation and assignment workflows
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from django.db.models import Count, Sum, Avg, Q, F, Case, When, DurationField
from django.db.models.functions import TruncDate, TruncHour, Extract
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from crm.models.ticket import (
    Ticket, TicketCategory, TicketComment, SLA, 
    KnowledgeBase, TicketAttachment, TicketEscalation
)
from crm.serializers.ticket import (
    TicketSerializer, TicketDetailSerializer, TicketCreateSerializer,
    TicketCategorySerializer, TicketCommentSerializer, SLASerializer,
    KnowledgeBaseSerializer, TicketAttachmentSerializer, TicketEscalationSerializer
)
from crm.permissions.ticket import TicketPermission, KnowledgeBasePermission
from crm.utils.tenant_utils import get_tenant_from_request, check_tenant_limits
from crm.utils.email_utils import send_crm_email
from crm.utils.formatters import format_duration, format_percentage, format_date_display
from .base import CRMBaseViewSet, CRMReadOnlyViewSet, cache_response, require_tenant_limits


class TicketFilter(filters.FilterSet):
    """Advanced filtering for Ticket ViewSet."""
    
    subject = filters.CharFilter(lookup_expr='icontains')
    category = filters.ModelChoiceFilter(queryset=TicketCategory.objects.all())
    priority = filters.ChoiceFilter(choices=Ticket.PRIORITY_CHOICES)
    status = filters.ChoiceFilter(choices=Ticket.STATUS_CHOICES)
    assigned_to = filters.NumberFilter(field_name='assigned_to__id')
    created_by = filters.NumberFilter(field_name='created_by__id')
    customer_email = filters.CharFilter(lookup_expr='icontains')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    due_date_from = filters.DateTimeFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = filters.DateTimeFilter(field_name='due_date', lookup_expr='lte')
    is_overdue = filters.BooleanFilter(method='filter_is_overdue')
    sla_breached = filters.BooleanFilter(method='filter_sla_breached')
    satisfaction_rating_min = filters.NumberFilter(field_name='satisfaction_rating', lookup_expr='gte')
    satisfaction_rating_max = filters.NumberFilter(field_name='satisfaction_rating', lookup_expr='lte')
    has_escalation = filters.BooleanFilter(method='filter_has_escalation')
    source = filters.ChoiceFilter(choices=Ticket.SOURCE_CHOICES)
    tags = filters.CharFilter(method='filter_tags')
    
    class Meta:
        model = Ticket
        fields = ['category', 'priority', 'status', 'assigned_to', 'source']
    
    def filter_is_overdue(self, queryset, name, value):
        """Filter overdue tickets."""
        if value:
            return queryset.filter(
                due_date__lt=timezone.now(),
                status__in=['OPEN', 'IN_PROGRESS', 'WAITING_CUSTOMER']
            )
        return queryset
    
    def filter_sla_breached(self, queryset, name, value):
        """Filter tickets with SLA breaches."""
        if value:
            return queryset.filter(
                Q(first_response_sla_breached=True) |
                Q(resolution_sla_breached=True)
            )
        return queryset
    
    def filter_has_escalation(self, queryset, name, value):
        """Filter tickets with escalations."""
        if value:
            return queryset.filter(escalations__isnull=False).distinct()
        else:
            return queryset.filter(escalations__isnull=True)
    
    def filter_tags(self, queryset, name, value):
        """Filter by tags (comma-separated)."""
        if value:
            tag_list = [tag.strip() for tag in value.split(',')]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)
        return queryset


class TicketViewSet(CRMBaseViewSet):
    """
    ViewSet for Ticket management with comprehensive functionality.
    
    Provides CRUD operations, SLA tracking, and support analytics.
    """
    
    queryset = Ticket.objects.select_related(
        'category', 'assigned_to', 'created_by', 'sla'
    ).prefetch_related('comments', 'attachments', 'escalations')
    
    serializer_class = TicketSerializer
    filterset_class = TicketFilter
    search_fields = [
        'subject', 'description', 'customer_name', 'customer_email', 
        'tags', 'ticket_id'
    ]
    ordering_fields = [
        'subject', 'priority', 'status', 'created_at', 'due_date', 
        'first_response_at', 'resolved_at', 'satisfaction_rating'
    ]
    ordering = ['-priority', 'due_date', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TicketCreateSerializer
        elif self.action == 'retrieve':
            return TicketDetailSerializer
        return TicketSerializer
    
    def get_model_permission(self):
        """Get ticket-specific permission class."""
        return TicketPermission
    
    @require_tenant_limits('tickets')
    def create(self, request, *args, **kwargs):
        """Create new ticket with automatic SLA assignment."""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            ticket_id = response.data['id']
            try:
                ticket = Ticket.objects.get(id=ticket_id)
                
                # Auto-assign SLA based on category and priority
                self._assign_sla_to_ticket(ticket)
                
                # Auto-assign ticket based on category/skills
                self._auto_assign_ticket(ticket)
                
                # Send customer acknowledgment email
                self._send_ticket_acknowledgment(ticket)
                
                # Create initial activity log
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=ticket.tenant,
                    type='TICKET_CREATED',
                    subject=f'Support Ticket Created: {ticket.subject}',
                    description=f'Ticket #{ticket.ticket_id} created with {ticket.get_priority_display()} priority',
                    assigned_to=ticket.assigned_to or request.user,
                    due_date=ticket.due_date.date() if ticket.due_date else None,
                    related_object_type='ticket',
                    related_to_id=ticket.id
                )
                
                # Refresh response data with updated fields
                ticket.refresh_from_db()
                response.data = TicketSerializer(ticket).data
                
            except Exception as e:
                print(f"Error initializing ticket: {e}")
        
        return response
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign ticket to agent.
        
        Expected payload:
        {
            "assigned_to_id": integer,
            "assignment_notes": "string",
            "notify_assignee": boolean
        }
        """
        try:
            ticket = self.get_object()
            assigned_to_id = request.data.get('assigned_to_id')
            assignment_notes = request.data.get('assignment_notes', '')
            notify_assignee = request.data.get('notify_assignee', True)
            
            if not assigned_to_id:
                return Response(
                    {'error': 'assigned_to_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                assigned_user = User.objects.get(id=assigned_to_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            old_assignee = ticket.assigned_to
            
            with transaction.atomic():
                # Update ticket
                ticket.assigned_to = assigned_user
                ticket.status = 'ASSIGNED' if ticket.status == 'OPEN' else ticket.status
                ticket.save()
                
                # Add assignment comment
                TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"Ticket assigned to {assigned_user.get_full_name()}. {assignment_notes}".strip(),
                    is_internal=True,
                    comment_type='ASSIGNMENT',
                    tenant=ticket.tenant
                )
                
                # Send notification to assignee
                if notify_assignee:
                    self._send_assignment_notification(ticket, assigned_user, request.user)
                
                # Update SLA if first assignment
                if not old_assignee and ticket.sla:
                    self._update_first_response_sla(ticket)
                
                return Response({
                    'message': f'Ticket assigned to {assigned_user.get_full_name()}',
                    'ticket': TicketSerializer(ticket).data,
                    'assigned_to': assigned_user.get_full_name()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """
        Add comment to ticket.
        
        Expected payload:
        {
            "content": "string",
            "is_internal": boolean,
            "notify_customer": boolean,
            "time_spent": integer (minutes)
        }
        """
        try:
            ticket = self.get_object()
            content = request.data.get('content')
            is_internal = request.data.get('is_internal', False)
            notify_customer = request.data.get('notify_customer', not is_internal)
            time_spent = request.data.get('time_spent', 0)
            
            if not content:
                return Response(
                    {'error': 'Content is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Create comment
                comment = TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=content,
                    is_internal=is_internal,
                    time_spent=time_spent,
                    tenant=ticket.tenant
                )
                
                # Update ticket timestamps
                ticket.last_updated_at = timezone.now()
                if not is_internal and not ticket.first_response_at:
                    ticket.first_response_at = timezone.now()
                    # Check first response SLA
                    self._check_first_response_sla(ticket)
                
                ticket.save()
                
                # Update total time spent
                if time_spent > 0:
                    ticket.total_time_spent = (ticket.total_time_spent or 0) + time_spent
                    ticket.save(update_fields=['total_time_spent'])
                
                # Send customer notification if requested
                if notify_customer and not is_internal:
                    self._send_comment_notification(ticket, comment)
                
                return Response({
                    'message': 'Comment added successfully',
                    'comment': TicketCommentSerializer(comment).data,
                    'ticket_updated': TicketSerializer(ticket).data
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve ticket.
        
        Expected payload:
        {
            "resolution_notes": "string",
            "resolution_category": "string",
            "notify_customer": boolean,
            "request_feedback": boolean
        }
        """
        try:
            ticket = self.get_object()
            
            if ticket.status in ['RESOLVED', 'CLOSED']:
                return Response(
                    {'error': 'Ticket is already resolved/closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            resolution_notes = request.data.get('resolution_notes', '')
            resolution_category = request.data.get('resolution_category', '')
            notify_customer = request.data.get('notify_customer', True)
            request_feedback = request.data.get('request_feedback', True)
            
            with transaction.atomic():
                # Update ticket
                ticket.status = 'RESOLVED'
                ticket.resolved_at = timezone.now()
                ticket.resolved_by = request.user
                ticket.resolution_notes = resolution_notes
                ticket.resolution_category = resolution_category
                ticket.save()
                
                # Add resolution comment
                TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"Ticket resolved. {resolution_notes}".strip(),
                    is_internal=False,
                    comment_type='RESOLUTION',
                    tenant=ticket.tenant
                )
                
                # Check resolution SLA
                self._check_resolution_sla(ticket)
                
                # Send customer notification
                if notify_customer:
                    self._send_resolution_notification(ticket, request_feedback)
                
                # Create resolution activity
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=ticket.tenant,
                    type='TICKET_RESOLVED',
                    subject=f'Support Ticket Resolved: {ticket.subject}',
                    description=f'Ticket #{ticket.ticket_id} resolved by {request.user.get_full_name()}',
                    assigned_to=request.user,
                    due_date=timezone.now().date(),
                    related_object_type='ticket',
                    related_to_id=ticket.id
                )
                
                return Response({
                    'message': 'Ticket resolved successfully',
                    'ticket': TicketSerializer(ticket).data,
                    'resolution_time': self._calculate_resolution_time(ticket)
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        Close resolved ticket.
        
        Expected payload:
        {
            "close_reason": "string",
            "close_notes": "string"
        }
        """
        try:
            ticket = self.get_object()
            
            if ticket.status != 'RESOLVED':
                return Response(
                    {'error': 'Only resolved tickets can be closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            close_reason = request.data.get('close_reason', 'RESOLVED')
            close_notes = request.data.get('close_notes', '')
            
            with transaction.atomic():
                # Update ticket
                ticket.status = 'CLOSED'
                ticket.closed_at = timezone.now()
                ticket.closed_by = request.user
                ticket.close_reason = close_reason
                ticket.close_notes = close_notes
                ticket.save()
                
                # Add close comment
                TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"Ticket closed. Reason: {close_reason}. {close_notes}".strip(),
                    is_internal=True,
                    comment_type='CLOSURE',
                    tenant=ticket.tenant
                )
                
                return Response({
                    'message': 'Ticket closed successfully',
                    'ticket': TicketSerializer(ticket).data,
                    'total_resolution_time': self._calculate_total_resolution_time(ticket)
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        """
        Reopen closed/resolved ticket.
        
        Expected payload:
        {
            "reopen_reason": "string",
            "reopen_notes": "string",
            "reset_sla": boolean
        }
        """
        try:
            ticket = self.get_object()
            
            if ticket.status not in ['RESOLVED', 'CLOSED']:
                return Response(
                    {'error': 'Only resolved/closed tickets can be reopened'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            reopen_reason = request.data.get('reopen_reason', '')
            reopen_notes = request.data.get('reopen_notes', '')
            reset_sla = request.data.get('reset_sla', False)
            
            with transaction.atomic():
                # Update ticket
                ticket.status = 'IN_PROGRESS'
                ticket.reopened_at = timezone.now()
                ticket.reopened_by = request.user
                ticket.reopen_count = (ticket.reopen_count or 0) + 1
                
                # Reset resolution fields
                ticket.resolved_at = None
                ticket.resolved_by = None
                ticket.closed_at = None
                ticket.closed_by = None
                
                # Reset SLA if requested
                if reset_sla and ticket.sla:
                    self._reset_ticket_sla(ticket)
                
                ticket.save()
                
                # Add reopen comment
                TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"Ticket reopened. Reason: {reopen_reason}. {reopen_notes}".strip(),
                    is_internal=False,
                    comment_type='REOPEN',
                    tenant=ticket.tenant
                )
                
                # Notify assigned agent
                if ticket.assigned_to:
                    self._send_reopen_notification(ticket)
                
                return Response({
                    'message': 'Ticket reopened successfully',
                    'ticket': TicketSerializer(ticket).data,
                    'reopen_count': ticket.reopen_count
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """
        Escalate ticket to higher level.
        
        Expected payload:
        {
            "escalation_level": integer,
            "escalation_reason": "string",
            "escalated_to_id": integer,
            "escalation_notes": "string"
        }
        """
        try:
            ticket = self.get_object()
            escalation_level = request.data.get('escalation_level', 1)
            escalation_reason = request.data.get('escalation_reason', '')
            escalated_to_id = request.data.get('escalated_to_id')
            escalation_notes = request.data.get('escalation_notes', '')
            
            escalated_to = None
            if escalated_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    escalated_to = User.objects.get(id=escalated_to_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Escalated user not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            with transaction.atomic():
                # Create escalation record
                escalation = TicketEscalation.objects.create(
                    ticket=ticket,
                    escalation_level=escalation_level,
                    escalation_reason=escalation_reason,
                    escalated_by=request.user,
                    escalated_to=escalated_to,
                    escalation_notes=escalation_notes,
                    escalated_at=timezone.now(),
                    tenant=ticket.tenant
                )
                
                # Update ticket
                ticket.escalation_level = escalation_level
                ticket.priority = self._increase_priority(ticket.priority)
                if escalated_to:
                    ticket.assigned_to = escalated_to
                ticket.save()
                
                # Add escalation comment
                escalation_msg = f"Ticket escalated to level {escalation_level}. Reason: {escalation_reason}"
                if escalated_to:
                    escalation_msg += f" Assigned to: {escalated_to.get_full_name()}"
                
                TicketComment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"{escalation_msg}. {escalation_notes}".strip(),
                    is_internal=True,
                    comment_type='ESCALATION',
                    tenant=ticket.tenant
                )
                
                # Send escalation notifications
                self._send_escalation_notifications(ticket, escalation)
                
                return Response({
                    'message': f'Ticket escalated to level {escalation_level}',
                    'ticket': TicketSerializer(ticket).data,
                    'escalation': TicketEscalationSerializer(escalation).data
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def rate_satisfaction(self, request, pk=None):
        """
        Rate customer satisfaction.
        
        Expected payload:
        {
            "rating": integer (1-5),
            "feedback": "string",
            "customer_email": "string" (for verification)
        }
        """
        try:
            ticket = self.get_object()
            rating = request.data.get('rating')
            feedback = request.data.get('feedback', '')
            customer_email = request.data.get('customer_email')
            
            if not rating or rating < 1 or rating > 5:
                return Response(
                    {'error': 'Rating must be between 1 and 5'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify customer email (simple verification)
            if customer_email and customer_email.lower() != ticket.customer_email.lower():
                return Response(
                    {'error': 'Invalid customer email'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update ticket
            ticket.satisfaction_rating = rating
            ticket.satisfaction_feedback = feedback
            ticket.satisfaction_rated_at = timezone.now()
            ticket.save()
            
            # Add feedback comment
            TicketComment.objects.create(
                ticket=ticket,
                author_name=ticket.customer_name or 'Customer',
                content=f"Customer satisfaction rating: {rating}/5. Feedback: {feedback}".strip(),
                is_internal=False,
                comment_type='SATISFACTION',
                tenant=ticket.tenant
            )
            
            return Response({
                'message': 'Satisfaction rating submitted successfully',
                'rating': rating,
                'feedback': feedback,
                'thank_you_message': self._get_satisfaction_thank_you_message(rating)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        """Get current user's assigned tickets with smart categorization."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            user_tickets = queryset.filter(assigned_to=request.user)
            
            # Categorize tickets
            categories = {
                'urgent': user_tickets.filter(
                    priority__in=['CRITICAL', 'HIGH'],
                    status__in=['OPEN', 'IN_PROGRESS']
                ).order_by('due_date'),
                
                'overdue': user_tickets.filter(
                    due_date__lt=timezone.now(),
                    status__in=['OPEN', 'IN_PROGRESS', 'WAITING_CUSTOMER']
                ).order_by('due_date'),
                
                'due_today': user_tickets.filter(
                    due_date__date=timezone.now().date(),
                    status__in=['OPEN', 'IN_PROGRESS']
                ).order_by('priority'),
                
                'in_progress': user_tickets.filter(
                    status='IN_PROGRESS'
                ).order_by('due_date'),
                
                'waiting_customer': user_tickets.filter(
                    status='WAITING_CUSTOMER'
                ).order_by('-last_updated_at'),
                
                'recently_resolved': user_tickets.filter(
                    status='RESOLVED',
                    resolved_at__gte=timezone.now() - timedelta(days=7)
                ).order_by('-resolved_at')[:5]
            }
            
            # Serialize categories
            response_data = {}
            for category, tickets in categories.items():
                response_data[category] = {
                    'count': tickets.count(),
                    'tickets': TicketSerializer(tickets[:10], many=True).data  # Limit to 10 per category
                }
            
            # Add summary stats
            response_data['summary'] = {
                'total_assigned': user_tickets.count(),
                'overdue_count': categories['overdue'].count(),
                'urgent_count': categories['urgent'].count(),
                'resolution_rate_this_week': self._calculate_weekly_resolution_rate(request.user),
                'avg_satisfaction_rating': user_tickets.filter(
                    satisfaction_rating__isnull=False
                ).aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg'] or 0
            }
            
            return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def sla_dashboard(self, request):
        """Get SLA performance dashboard."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            tenant = get_tenant_from_request(request)
            
            # SLA metrics
            total_tickets = queryset.count()
            tickets_with_sla = queryset.filter(sla__isnull=False)
            
            # First response SLA
            first_response_breached = tickets_with_sla.filter(
                first_response_sla_breached=True
            ).count()
            first_response_met = tickets_with_sla.filter(
                first_response_at__isnull=False,
                first_response_sla_breached=False
            ).count()
            
            # Resolution SLA
            resolution_breached = tickets_with_sla.filter(
                resolution_sla_breached=True
            ).count()
            resolution_met = tickets_with_sla.filter(
                resolved_at__isnull=False,
                resolution_sla_breached=False
            ).count()
            
            # Calculate percentages
            first_response_rate = (
                first_response_met / (first_response_met + first_response_breached) * 100
            ) if (first_response_met + first_response_breached) > 0 else 0
            
            resolution_rate = (
                resolution_met / (resolution_met + resolution_breached) * 100
            ) if (resolution_met + resolution_breached) > 0 else 0
            
            # SLA performance by category
            category_performance = self._get_sla_performance_by_category(tickets_with_sla)
            
            # Tickets at risk of SLA breach
            at_risk_tickets = self._get_at_risk_tickets(queryset)
            
            return Response({
                'sla_overview': {
                    'total_tickets': total_tickets,
                    'tickets_with_sla': tickets_with_sla.count(),
                    'first_response_rate': round(first_response_rate, 2),
                    'resolution_rate': round(resolution_rate, 2),
                    'first_response_breached': first_response_breached,
                    'resolution_breached': resolution_breached
                },
                'category_performance': category_performance,
                'at_risk_tickets': TicketSerializer(at_risk_tickets, many=True).data,
                'recommendations': self._generate_sla_recommendations(
                    first_response_rate, resolution_rate
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def analytics_overview(self, request):
        """Get comprehensive ticket analytics overview."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Basic metrics
            total_tickets = queryset.count()
            open_tickets = queryset.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
            resolved_tickets = queryset.filter(status='RESOLVED').count()
            closed_tickets = queryset.filter(status='CLOSED').count()
            
            # Resolution rate
            resolution_rate = (
                (resolved_tickets + closed_tickets) / total_tickets * 100
            ) if total_tickets > 0 else 0
            
            # Average resolution time
            resolved_with_time = queryset.filter(
                resolved_at__isnull=False,
                created_at__isnull=False
            )
            
            avg_resolution_hours = 0
            if resolved_with_time.exists():
                resolution_times = []
                for ticket in resolved_with_time:
                    hours = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                    resolution_times.append(hours)
                avg_resolution_hours = sum(resolution_times) / len(resolution_times)
            
            # Priority distribution
            priority_dist = queryset.values('priority').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Status distribution
            status_dist = queryset.values('status').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Category performance
            category_stats = queryset.values('category__name').annotate(
                count=Count('id'),
                avg_resolution_hours=Avg(
                    Case(
                        When(resolved_at__isnull=False, 
                             then=(F('resolved_at') - F('created_at'))),
                        output_field=DurationField()
                    )
                )
            ).order_by('-count')
            
            # Customer satisfaction
            satisfaction_stats = queryset.filter(
                satisfaction_rating__isnull=False
            ).aggregate(
                avg_rating=Avg('satisfaction_rating'),
                total_ratings=Count('satisfaction_rating')
            )
            
            # Monthly trends (last 12 months)
            monthly_trends = self._get_monthly_ticket_trends(queryset)
            
            return Response({
                'overview_metrics': {
                    'total_tickets': total_tickets,
                    'open_tickets': open_tickets,
                    'resolved_tickets': resolved_tickets,
                    'closed_tickets': closed_tickets,
                    'resolution_rate': round(resolution_rate, 2),
                    'avg_resolution_hours': round(avg_resolution_hours, 1)
                },
                'priority_distribution': list(priority_dist),
                'status_distribution': list(status_dist),
                'category_performance': list(category_stats),
                'satisfaction': {
                    'average_rating': round(satisfaction_stats['avg_rating'] or 0, 2),
                    'total_ratings': satisfaction_stats['total_ratings']
                },
                'monthly_trends': monthly_trends
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Bulk assign tickets to users."""
        try:
            ticket_ids = request.data.get('ticket_ids', [])
            assigned_to_id = request.data.get('assigned_to_id')
            assignment_notes = request.data.get('assignment_notes', '')
            
            if not ticket_ids or not assigned_to_id:
                return Response(
                    {'error': 'ticket_ids and assigned_to_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                assigned_user = User.objects.get(id=assigned_to_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            tenant = get_tenant_from_request(request)
            tickets = Ticket.objects.filter(
                id__in=ticket_ids,
                tenant=tenant
            )
            
            updated_count = 0
            
            with transaction.atomic():
                for ticket in tickets:
                    ticket.assigned_to = assigned_user
                    if ticket.status == 'OPEN':
                        ticket.status = 'ASSIGNED'
                    ticket.save()
                    
                    # Add assignment comment
                    TicketComment.objects.create(
                        ticket=ticket,
                        author=request.user,
                        content=f"Bulk assigned to {assigned_user.get_full_name()}. {assignment_notes}".strip(),
                        is_internal=True,
                        comment_type='ASSIGNMENT',
                        tenant=tenant
                    )
                    
                    updated_count += 1
            
            return Response({
                'message': f'{updated_count} tickets assigned to {assigned_user.get_full_name()}',
                'assigned_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Helper methods
    def _assign_sla_to_ticket(self, ticket):
        """Auto-assign SLA to ticket based on category and priority."""
        try:
            # Find matching SLA
            sla = SLA.objects.filter(
                tenant=ticket.tenant,
                is_active=True,
                Q(category=ticket.category) | Q(category__isnull=True),
                Q(priority=ticket.priority) | Q(priority__isnull=True)
            ).order_by('-priority', '-category').first()
            
            if sla:
                ticket.sla = sla
                # Calculate due dates
                if sla.first_response_hours:
                    ticket.first_response_due = ticket.created_at + timedelta(hours=sla.first_response_hours)
                if sla.resolution_hours:
                    ticket.due_date = ticket.created_at + timedelta(hours=sla.resolution_hours)
                ticket.save()
        except Exception as e:
            print(f"Error assigning SLA: {e}")
    
    def _auto_assign_ticket(self, ticket):
        """Auto-assign ticket based on category and agent skills."""
        try:
            # This would implement skill-based routing
            # For now, just assign to least busy agent in category
            if ticket.category:
                # Find agents with least assigned tickets in this category
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                agents = User.objects.filter(
                    is_active=True,
                    groups__name='Support Agent',  # Assuming role-based groups
                ).annotate(
                    ticket_count=Count('assigned_tickets', filter=Q(
                        assigned_tickets__status__in=['OPEN', 'IN_PROGRESS'],
                        assigned_tickets__tenant=ticket.tenant
                    ))
                ).order_by('ticket_count')
                
                if agents.exists():
                    ticket.assigned_to = agents.first()
                    ticket.status = 'ASSIGNED'
                    ticket.save()
        except Exception as e:
            print(f"Error auto-assigning ticket: {e}")
    
    def _send_ticket_acknowledgment(self, ticket):
        """Send acknowledgment email to customer."""
        try:
            send_crm_email(
                recipient_email=ticket.customer_email,
                subject=f'Support Ticket Created - #{ticket.ticket_id}',
                template_name='ticket_acknowledgment',
                context_data={
                    'ticket': ticket,
                    'ticket_url': f'/support/tickets/{ticket.ticket_id}'
                },
                recipient_data={
                    'first_name': ticket.customer_name or 'Valued Customer',
                    'email': ticket.customer_email
                },
                tenant=ticket.tenant
            )
        except Exception as e:
            print(f"Error sending acknowledgment email: {e}")
    
    def _send_assignment_notification(self, ticket, assigned_user, assigned_by):
        """Send assignment notification to agent."""
        try:
            send_crm_email(
                recipient_email=assigned_user.email,
                subject=f'Ticket Assigned: #{ticket.ticket_id} - {ticket.subject}',
                template_name='ticket_assignment',
                context_data={
                    'ticket': ticket,
                    'assigned_by': assigned_by,
                    'ticket_url': f'/support/tickets/{ticket.ticket_id}'
                },
                recipient_data={
                    'first_name': assigned_user.first_name,
                    'email': assigned_user.email
                },
                tenant=ticket.tenant
            )
        except Exception as e:
            print(f"Error sending assignment notification: {e}")
    
    def _send_comment_notification(self, ticket, comment):
        """Send comment notification to customer."""
        try:
            send_crm_email(
                recipient_email=ticket.customer_email,
                subject=f'Update on Ticket #{ticket.ticket_id}',
                template_name='ticket_comment',
                context_data={
                    'ticket': ticket,
                    'comment': comment,
                    'ticket_url': f'/support/tickets/{ticket.ticket_id}'
                },
                recipient_data={
                    'first_name': ticket.customer_name or 'Valued Customer',
                    'email': ticket.customer_email
                },
                tenant=ticket.tenant
            )
        except Exception as e:
            print(f"Error sending comment notification: {e}")
    
    def _send_resolution_notification(self, ticket, request_feedback):
        """Send resolution notification to customer."""
        try:
            template_name = 'ticket_resolved_with_feedback' if request_feedback else 'ticket_resolved'
            
            send_crm_email(
                recipient_email=ticket.customer_email,
                subject=f'Ticket Resolved: #{ticket.ticket_id}',
                template_name=template_name,
                context_data={
                    'ticket': ticket,
                    'feedback_url': f'/support/feedback/{ticket.ticket_id}' if request_feedback else None
                },
                recipient_data={
                    'first_name': ticket.customer_name or 'Valued Customer',
                    'email': ticket.customer_email
                },
                tenant=ticket.tenant
            )
        except Exception as e:
            print(f"Error sending resolution notification: {e}")
    
    def _send_escalation_notifications(self, ticket, escalation):
        """Send escalation notifications."""
        try:
            # Notify escalated user
            if escalation.escalated_to:
                send_crm_email(
                    recipient_email=escalation.escalated_to.email,
                    subject=f'Ticket Escalated: #{ticket.ticket_id} - Level {escalation.escalation_level}',
                    template_name='ticket_escalation',
                    context_data={
                        'ticket': ticket,
                        'escalation': escalation,
                        'ticket_url': f'/support/tickets/{ticket.ticket_id}'
                    },
                    recipient_data={
                        'first_name': escalation.escalated_to.first_name,
                        'email': escalation.escalated_to.email
                    },
                    tenant=ticket.tenant
                )
        except Exception as e:
            print(f"Error sending escalation notifications: {e}")
    
    def _send_reopen_notification(self, ticket):
        """Send reopen notification to assigned agent."""
        try:
            send_crm_email(
                recipient_email=ticket.assigned_to.email,
                subject=f'Ticket Reopened: #{ticket.ticket_id}',
                template_name='ticket_reopened',
                context_data={
                    'ticket': ticket,
                    'ticket_url': f'/support/tickets/{ticket.ticket_id}'
                },
                recipient_data={
                    'first_name': ticket.assigned_to.first_name,
                    'email': ticket.assigned_to.email
                },
                tenant=ticket.tenant
            )
        except Exception as e:
            print(f"Error sending reopen notification: {e}")
    
    def _update_first_response_sla(self, ticket):
        """Update first response SLA when ticket is first assigned."""
        if ticket.sla and not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
            self._check_first_response_sla(ticket)
            ticket.save()
    
    def _check_first_response_sla(self, ticket):
        """Check if first response SLA is breached."""
        if ticket.sla and ticket.first_response_due and ticket.first_response_at:
            if ticket.first_response_at > ticket.first_response_due:
                ticket.first_response_sla_breached = True
                ticket.save()
    
    def _check_resolution_sla(self, ticket):
        """Check if resolution SLA is breached."""
        if ticket.sla and ticket.due_date and ticket.resolved_at:
            if ticket.resolved_at > ticket.due_date:
                ticket.resolution_sla_breached = True
                ticket.save()
    
    def _reset_ticket_sla(self, ticket):
        """Reset SLA timers for reopened ticket."""
        if ticket.sla:
            now = timezone.now()
            if ticket.sla.first_response_hours:
                ticket.first_response_due = now + timedelta(hours=ticket.sla.first_response_hours)
                ticket.first_response_at = None
                ticket.first_response_sla_breached = False
            
            if ticket.sla.resolution_hours:
                ticket.due_date = now + timedelta(hours=ticket.sla.resolution_hours)
                ticket.resolution_sla_breached = False
            
            ticket.save()
    
    def _increase_priority(self, current_priority):
        """Increase ticket priority for escalation."""
        priority_order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        try:
            current_index = priority_order.index(current_priority)
            if current_index < len(priority_order) - 1:
                return priority_order[current_index + 1]
        except ValueError:
            pass
        return current_priority
    
    def _calculate_resolution_time(self, ticket):
        """Calculate resolution time for ticket."""
        if ticket.resolved_at and ticket.created_at:
            duration = ticket.resolved_at - ticket.created_at
            return {
                'hours': duration.total_seconds() / 3600,
                'human_readable': format_duration(int(duration.total_seconds()))
            }
        return None
    
    def _calculate_total_resolution_time(self, ticket):
        """Calculate total time from creation to closure."""
        if ticket.closed_at and ticket.created_at:
            duration = ticket.closed_at - ticket.created_at
            return {
                'hours': duration.total_seconds() / 3600,
                'human_readable': format_duration(int(duration.total_seconds()))
            }
        return None
    
    def _calculate_weekly_resolution_rate(self, user):
        """Calculate user's weekly resolution rate."""
        try:
            week_start = timezone.now() - timedelta(days=7)
            user_tickets = Ticket.objects.filter(
                assigned_to=user,
                tenant=get_tenant_from_request(self.request),
                created_at__gte=week_start
            )
            
            total = user_tickets.count()
            resolved = user_tickets.filter(status__in=['RESOLVED', 'CLOSED']).count()
            
            return (resolved / total * 100) if total > 0 else 0
        except:
            return 0
    
    def _get_satisfaction_thank_you_message(self, rating):
        """Get thank you message based on rating."""
        if rating >= 4:
            return "Thank you for your positive feedback! We're glad we could help."
        elif rating >= 3:
            return "Thank you for your feedback. We'll continue to improve our service."
        else:
            return "Thank you for your feedback. We take your concerns seriously and will work to improve."
    
    def _get_sla_performance_by_category(self, tickets):
        """Get SLA performance broken down by category."""
        try:
            category_performance = {}
            
            categories = tickets.values_list('category__name', flat=True).distinct()
            
            for category_name in categories:
                category_tickets = tickets.filter(category__name=category_name)
                
                first_response_met = category_tickets.filter(
                    first_response_at__isnull=False,
                    first_response_sla_breached=False
                ).count()
                
                first_response_total = category_tickets.filter(
                    first_response_at__isnull=False
                ).count()
                
                resolution_met = category_tickets.filter(
                    resolved_at__isnull=False,
                    resolution_sla_breached=False
                ).count()
                
                resolution_total = category_tickets.filter(
                    resolved_at__isnull=False
                ).count()
                
                category_performance[category_name] = {
                    'first_response_rate': (
                        first_response_met / first_response_total * 100
                    ) if first_response_total > 0 else 0,
                    'resolution_rate': (
                        resolution_met / resolution_total * 100
                    ) if resolution_total > 0 else 0,
                    'total_tickets': category_tickets.count()
                }
            
            return category_performance
        except:
            return {}
    
    def _get_at_risk_tickets(self, queryset):
        """Get tickets at risk of SLA breach."""
        try:
            now = timezone.now()
            at_risk = queryset.filter(
                status__in=['OPEN', 'IN_PROGRESS'],
                sla__isnull=False
            ).filter(
                Q(first_response_due__lte=now + timedelta(hours=2), first_response_at__isnull=True) |
                Q(due_date__lte=now + timedelta(hours=4), resolved_at__isnull=True)
            ).order_by('due_date')[:10]
            
            return at_risk
        except:
            return []
    
    def _generate_sla_recommendations(self, first_response_rate, resolution_rate):
        """Generate SLA improvement recommendations."""
        recommendations = []
        
        if first_response_rate < 80:
            recommendations.append({
                'type': 'urgent',
                'message': f'First response rate is {first_response_rate:.1f}% (target: 90%+)',
                'action': 'Review agent workloads and consider auto-assignment rules'
            })
        
        if resolution_rate < 85:
            recommendations.append({
                'type': 'important',
                'message': f'Resolution rate is {resolution_rate:.1f}% (target: 95%+)',
                'action': 'Analyze common resolution delays and improve processes'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'success',
                'message': 'SLA performance is meeting targets',
                'action': 'Continue monitoring and maintain current processes'
            })
        
        return recommendations
    
    def _get_monthly_ticket_trends(self, queryset):
        """Get monthly ticket creation trends."""
        try:
            twelve_months_ago = timezone.now() - timedelta(days=365)
            
            monthly_data = queryset.filter(
                created_at__gte=twelve_months_ago
            ).extra(
                select={'month': "DATE_TRUNC('month', created_at)"}
            ).values('month').annotate(
                created_count=Count('id'),
                resolved_count=Count('id', filter=Q(status__in=['RESOLVED', 'CLOSED']))
            ).order_by('month')
            
            return list(monthly_data)
        except:
            return []


class TicketCategoryViewSet(CRMBaseViewSet):
    """
    ViewSet for Ticket Category management.
    """
    
    queryset = TicketCategory.objects.all()
    serializer_class = TicketCategorySerializer
    search_fields = ['name', 'description']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    @cache_response(timeout=1800)
    def performance_stats(self, request, pk=None):
        """Get performance statistics for this category."""
        try:
            category = self.get_object()
            tenant = get_tenant_from_request(request)
            
            category_tickets = Ticket.objects.filter(
                category=category,
                tenant=tenant
            )
            
            total_tickets = category_tickets.count()
            resolved_tickets = category_tickets.filter(status__in=['RESOLVED', 'CLOSED']).count()
            avg_resolution_time = 0
            
            # Calculate average resolution time
            resolved_with_time = category_tickets.filter(
                resolved_at__isnull=False
            )
            
            if resolved_with_time.exists():
                resolution_times = []
                for ticket in resolved_with_time:
                    hours = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                    resolution_times.append(hours)
                avg_resolution_time = sum(resolution_times) / len(resolution_times)
            
            # Priority distribution
            priority_dist = category_tickets.values('priority').annotate(
                count=Count('id')
            )
            
            # Satisfaction scores
            satisfaction_stats = category_tickets.filter(
                satisfaction_rating__isnull=False
            ).aggregate(
                avg_rating=Avg('satisfaction_rating'),
                total_ratings=Count('satisfaction_rating')
            )
            
            return Response({
                'category': TicketCategorySerializer(category).data,
                'performance': {
                    'total_tickets': total_tickets,
                    'resolved_tickets': resolved_tickets,
                    'resolution_rate': (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0,
                    'avg_resolution_hours': round(avg_resolution_time, 1),
                    'avg_satisfaction': round(satisfaction_stats['avg_rating'] or 0, 2),
                    'satisfaction_responses': satisfaction_stats['total_ratings']
                },
                'priority_distribution': list(priority_dist)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SLAViewSet(CRMBaseViewSet):
    """
    ViewSet for SLA management and monitoring.
    """
    
    queryset = SLA.objects.all()
    serializer_class = SLASerializer
    filterset_fields = ['category', 'priority', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['priority', 'name']
    
    @action(detail=True, methods=['get'])
    def performance_report(self, request, pk=None):
        """Get detailed performance report for this SLA."""
        try:
            sla = self.get_object()
            tenant = get_tenant_from_request(request)
            
            # Get tickets using this SLA
            sla_tickets = Ticket.objects.filter(
                sla=sla,
                tenant=tenant
            )
            
            total_tickets = sla_tickets.count()
            
            # First response metrics
            first_response_tickets = sla_tickets.filter(first_response_at__isnull=False)
            first_response_met = first_response_tickets.filter(first_response_sla_breached=False).count()
            first_response_breached = first_response_tickets.filter(first_response_sla_breached=True).count()
            
            # Resolution metrics
            resolved_tickets = sla_tickets.filter(resolved_at__isnull=False)
            resolution_met = resolved_tickets.filter(resolution_sla_breached=False).count()
            resolution_breached = resolved_tickets.filter(resolution_sla_breached=True).count()
            
            # Calculate percentages
            first_response_rate = (
                first_response_met / first_response_tickets.count() * 100
            ) if first_response_tickets.count() > 0 else 0
            
            resolution_rate = (
                resolution_met / resolved_tickets.count() * 100
            ) if resolved_tickets.count() > 0 else 0
            
            # Recent trends (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_tickets = sla_tickets.filter(created_at__gte=thirty_days_ago)
            
            return Response({
                'sla': SLASerializer(sla).data,
                'performance_metrics': {
                    'total_tickets': total_tickets,
                    'first_response_rate': round(first_response_rate, 2),
                    'resolution_rate': round(resolution_rate, 2),
                    'first_response_breached': first_response_breached,
                    'resolution_breached': resolution_breached,
                    'recent_tickets_30_days': recent_tickets.count()
                },
                'targets': {
                    'first_response_hours': sla.first_response_hours,
                    'resolution_hours': sla.resolution_hours
                },
                'recommendations': self._generate_sla_performance_recommendations(
                    sla, first_response_rate, resolution_rate
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_sla_performance_recommendations(self, sla, first_response_rate, resolution_rate):
        """Generate SLA performance recommendations."""
        recommendations = []
        
        if first_response_rate < 90:
            recommendations.append({
                'priority': 'high',
                'message': f'First response rate ({first_response_rate:.1f}%) below target',
                'action': f'Consider reducing first response target from {sla.first_response_hours}h or adding more agents'
            })
        
        if resolution_rate < 85:
            recommendations.append({
                'priority': 'high',
                'message': f'Resolution rate ({resolution_rate:.1f}%) below target',
                'action': f'Review resolution process or adjust {sla.resolution_hours}h target'
            })
        
        if first_response_rate >= 95 and resolution_rate >= 95:
            recommendations.append({
                'priority': 'optimization',
                'message': 'Excellent SLA performance',
                'action': 'Consider tightening SLA targets to improve service further'
            })
        
        return recommendations


class KnowledgeBaseViewSet(CRMBaseViewSet):
    """
    ViewSet for Knowledge Base article management.
    """
    
    queryset = KnowledgeBase.objects.filter(is_published=True)
    serializer_class = KnowledgeBaseSerializer
    filterset_fields = ['category', 'tags', 'is_featured']
    search_fields = ['title', 'content', 'summary', 'tags']
    ordering = ['-is_featured', '-view_count', '-created_at']
    
    def get_model_permission(self):
        """Get knowledge base-specific permission class."""
        return KnowledgeBasePermission
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # Public articles are visible to all
        # Internal articles only to authenticated users
        if self.request.user.is_authenticated:
            return queryset
        else:
            return queryset.filter(is_internal=False)
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Track article view."""
        try:
            article = self.get_object()
            
            # Increment view count
            article.view_count = (article.view_count or 0) + 1
            article.last_viewed_at = timezone.now()
            article.save(update_fields=['view_count', 'last_viewed_at'])
            
            return Response({
                'message': 'View tracked',
                'view_count': article.view_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def rate_helpfulness(self, request, pk=None):
        """Rate article helpfulness."""
        try:
            article = self.get_object()
            helpful = request.data.get('helpful')  # True/False
            
            if helpful is None:
                return Response(
                    {'error': 'helpful parameter is required (true/false)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if helpful:
                article.helpful_count = (article.helpful_count or 0) + 1
            else:
                article.not_helpful_count = (article.not_helpful_count or 0) + 1
            
            article.save()
            
            return Response({
                'message': 'Thank you for your feedback',
                'helpful_count': article.helpful_count,
                'not_helpful_count': article.not_helpful_count,
                'helpfulness_ratio': (
                    article.helpful_count / (article.helpful_count + article.not_helpful_count) * 100
                ) if (article.helpful_count + article.not_helpful_count) > 0 else 0
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most popular knowledge base articles."""
        try:
            popular_articles = self.get_queryset().order_by(
                '-view_count'
            )[:10]
            
            serializer = self.get_serializer(popular_articles, many=True)
            
            return Response({
                'popular_articles': serializer.data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search knowledge base articles."""
        try:
            query = request.query_params.get('q', '').strip()
            
            if not query:
                return Response({
                    'message': 'Search query is required',
                    'results': []
                })
            
            # Search in title, content, and tags
            results = self.get_queryset().filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(tags__icontains=query) |
                Q(summary__icontains=query)
            ).distinct().order_by(
                '-is_featured', '-view_count'
            )
            
            # Paginate results
            page = self.paginate_queryset(results)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(results, many=True)
            
            return Response({
                'query': query,
                'results_count': results.count(),
                'results': serializer.data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TicketAnalyticsViewSet(CRMReadOnlyViewSet):
    """
    Dedicated ViewSet for ticket analytics and reporting.
    """
    
    queryset = Ticket.objects.all()
    
    @action(detail=False, methods=['get'])
    @cache_response(timeout=1800)
    def agent_performance(self, request):
        """Get agent performance analytics."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            tenant = get_tenant_from_request(request)
            
            # Get agents with ticket assignments
            agents = User.objects.filter(
                assigned_tickets__tenant=tenant
            ).distinct()
            
            agent_stats = []
            
            for agent in agents:
                agent_tickets = Ticket.objects.filter(
                    assigned_to=agent,
                    tenant=tenant
                )
                
                total_tickets = agent_tickets.count()
                resolved_tickets = agent_tickets.filter(status__in=['RESOLVED', 'CLOSED']).count()
                
                # Calculate resolution rate
                resolution_rate = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0
                
                # Calculate average resolution time
                resolved_with_time = agent_tickets.filter(
                    resolved_at__isnull=False
                )
                
                avg_resolution_hours = 0
                if resolved_with_time.exists():
                    resolution_times = []
                    for ticket in resolved_with_time:
                        hours = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                        resolution_times.append(hours)
                    avg_resolution_hours = sum(resolution_times) / len(resolution_times)
                
                # Customer satisfaction
                satisfaction_avg = agent_tickets.filter(
                    satisfaction_rating__isnull=False
                ).aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg'] or 0
                
                agent_stats.append({
                    'agent_id': agent.id,
                    'agent_name': agent.get_full_name(),
                    'total_tickets': total_tickets,
                    'resolved_tickets': resolved_tickets,
                    'resolution_rate': round(resolution_rate, 2),
                    'avg_resolution_hours': round(avg_resolution_hours, 1),
                    'avg_satisfaction': round(satisfaction_avg, 2),
                    'current_open_tickets': agent_tickets.filter(
                        status__in=['OPEN', 'IN_PROGRESS']
                    ).count()
                })
            
            # Sort by resolution rate descending
            agent_stats.sort(key=lambda x: x['resolution_rate'], reverse=True)
            
            return Response({
                'agent_performance': agent_stats,
                'team_averages': {
                    'avg_resolution_rate': sum(a['resolution_rate'] for a in agent_stats) / len(agent_stats) if agent_stats else 0,
                    'avg_resolution_time': sum(a['avg_resolution_hours'] for a in agent_stats) / len(agent_stats) if agent_stats else 0,
                    'avg_satisfaction': sum(a['avg_satisfaction'] for a in agent_stats) / len(agent_stats) if agent_stats else 0
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def customer_satisfaction_analysis(self, request):
        """Detailed customer satisfaction analysis."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Tickets with satisfaction ratings
            rated_tickets = queryset.filter(satisfaction_rating__isnull=False)
            
            if not rated_tickets.exists():
                return Response({
                    'message': 'No satisfaction ratings found',
                    'satisfaction_analysis': {}
                })
            
            # Rating distribution
            rating_dist = rated_tickets.values('satisfaction_rating').annotate(
                count=Count('id')
            ).order_by('satisfaction_rating')
            
            # Calculate NPS-like score (ratings 4-5 = promoters, 1-2 = detractors)
            promoters = rated_tickets.filter(satisfaction_rating__gte=4).count()
            detractors = rated_tickets.filter(satisfaction_rating__lte=2).count()
            total_ratings = rated_tickets.count()
            
            nps_score = ((promoters - detractors) / total_ratings * 100) if total_ratings > 0 else 0
            
            # Satisfaction by category
            category_satisfaction = rated_tickets.values('category__name').annotate(
                avg_rating=Avg('satisfaction_rating'),
                rating_count=Count('satisfaction_rating')
            ).order_by('-avg_rating')
            
            # Satisfaction trends (last 6 months)
            six_months_ago = timezone.now() - timedelta(days=180)
            monthly_satisfaction = rated_tickets.filter(
                satisfaction_rated_at__gte=six_months_ago
            ).extra(
                select={'month': "DATE_TRUNC('month', satisfaction_rated_at)"}
            ).values('month').annotate(
                avg_rating=Avg('satisfaction_rating'),
                rating_count=Count('id')
            ).order_by('month')
            
            # Top feedback themes (from satisfaction_feedback)
            feedback_tickets = rated_tickets.exclude(
                satisfaction_feedback__isnull=True
            ).exclude(satisfaction_feedback__exact='')
            
            return Response({
                'satisfaction_overview': {
                    'total_ratings': total_ratings,
                    'average_rating': round(rated_tickets.aggregate(
                        Avg('satisfaction_rating')
                    )['satisfaction_rating__avg'], 2),
                    'nps_score': round(nps_score, 1),
                    'promoters': promoters,
                    'detractors': detractors,
                    'promoter_percentage': round(promoters / total_ratings * 100, 1) if total_ratings > 0 else 0
                },
                'rating_distribution': list(rating_dist),
                'category_satisfaction': list(category_satisfaction),
                'monthly_trends': list(monthly_satisfaction),
                'feedback_count': feedback_tickets.count(),
                'improvement_opportunities': self._generate_satisfaction_improvements(
                    category_satisfaction, nps_score
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_satisfaction_improvements(self, category_satisfaction, nps_score):
        """Generate satisfaction improvement recommendations."""
        recommendations = []
        
        if nps_score < 0:
            recommendations.append({
                'priority': 'critical',
                'message': f'NPS score is negative ({nps_score:.1f})',
                'action': 'Immediate review of support processes and customer feedback'
            })
        elif nps_score < 30:
            recommendations.append({
                'priority': 'high',
                'message': f'NPS score is low ({nps_score:.1f})',
                'action': 'Focus on reducing resolution times and improving communication'
            })
        
        # Identify lowest performing categories
        if category_satisfaction:
            lowest_category = min(category_satisfaction, key=lambda x: x['avg_rating'])
            if lowest_category['avg_rating'] < 3.5:
                recommendations.append({
                    'priority': 'medium',
                    'message': f'Category "{lowest_category["category__name"]}" has low satisfaction ({lowest_category["avg_rating"]:.1f})',
                    'action': 'Provide additional training for this category'
                })
        
        return recommendations