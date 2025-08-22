# ============================================================================
# backend/apps/crm/views/ticket.py - Customer Service & Support Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, Http404
from django.views import View
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
import json

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import (
    Ticket, TicketCategory, TicketComment, SLA, KnowledgeBase,
    Account, Contact, User
)
from ..serializers import (
    TicketSerializer, TicketDetailSerializer, TicketCategorySerializer,
    TicketCommentSerializer, SLASerializer, KnowledgeBaseSerializer
)
from ..filters import TicketFilter
from ..permissions import TicketPermission
from ..services import TicketService, NotificationService


class SupportDashboardView(CRMBaseMixin, View):
    """Support team dashboard with key metrics"""
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Get tickets based on user permissions
        tickets = Ticket.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).select_related('category', 'assigned_to', 'account', 'contact', 'sla')
        
        # Filter by user access
        if not user.has_perm('crm.view_all_tickets'):
            tickets = tickets.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct()
        
        # Dashboard metrics
        dashboard_stats = self.get_dashboard_stats(tickets)
        
        # Today's tickets
        today_tickets = tickets.filter(created_at__date=today).order_by('-created_at')[:10]
        
        # Overdue tickets
        overdue_tickets = self.get_overdue_tickets(tickets)[:10]
        
        # My tickets
        my_tickets = tickets.filter(assigned_to=user).exclude(
            status__in=['CLOSED', 'RESOLVED']
        ).order_by('priority', 'created_at')[:10]
        
        # SLA performance
        sla_performance = self.get_sla_performance(tickets)
        
        # Recent activity
        recent_activity = self.get_recent_activity(tickets)
        
        # Performance trends
        performance_trends = self.get_performance_trends(tickets)
        
        context = {
            'dashboard_stats': dashboard_stats,
            'today_tickets': today_tickets,
            'overdue_tickets': overdue_tickets,
            'my_tickets': my_tickets,
            'sla_performance': sla_performance,
            'recent_activity': recent_activity,
            'performance_trends': performance_trends,
        }
        
        return render(request, 'crm/ticket/dashboard.html', context)
    
    def get_dashboard_stats(self, tickets):
        """Get dashboard statistics"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        stats = {
            'total_tickets': tickets.count(),
            'open_tickets': tickets.filter(status__in=['OPEN', 'IN_PROGRESS']).count(),
            'closed_tickets': tickets.filter(status='CLOSED').count(),
            'overdue_tickets': self.get_overdue_tickets(tickets).count(),
            'today_created': tickets.filter(created_at__date=today).count(),
            'week_created': tickets.filter(created_at__date__gte=week_start).count(),
            'month_created': tickets.filter(created_at__date__gte=month_start).count(),
            'avg_resolution_time': self.calculate_avg_resolution_time(tickets),
            'by_priority': list(tickets.values('priority').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_status': list(tickets.values('status').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_category': list(tickets.filter(
                category__isnull=False
            ).values(
                'category__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:5]),
        }
        
        # Calculate response rates
        stats['first_response_rate'] = self.calculate_first_response_rate(tickets)
        stats['resolution_rate'] = self.calculate_resolution_rate(tickets)
        
        return stats
    
    def get_overdue_tickets(self, tickets):
        """Get overdue tickets based on SLA"""
        overdue_tickets = []
        now = timezone.now()
        
        for ticket in tickets.filter(status__in=['OPEN', 'IN_PROGRESS']):
            if ticket.sla and ticket.is_overdue():
                overdue_tickets.append(ticket)
        
        return sorted(overdue_tickets, key=lambda t: t.created_at)
    
    def calculate_avg_resolution_time(self, tickets):
        """Calculate average resolution time in hours"""
        resolved_tickets = tickets.filter(
            status='CLOSED',
            resolved_at__isnull=False
        )
        
        if not resolved_tickets.exists():
            return 0
        
        total_time = 0
        count = 0
        
        for ticket in resolved_tickets:
            if ticket.resolved_at and ticket.created_at:
                resolution_time = ticket.resolved_at - ticket.created_at
                total_time += resolution_time.total_seconds()
                count += 1
        
        if count > 0:
            avg_seconds = total_time / count
            return round(avg_seconds / 3600, 1)  # Convert to hours
        
        return 0
    
    def calculate_first_response_rate(self, tickets):
        """Calculate first response rate percentage"""
        tickets_with_response = 0
        total_tickets = tickets.count()
        
        if total_tickets == 0:
            return 100
        
        for ticket in tickets:
            if ticket.comments.exists():
                tickets_with_response += 1
        
        return round((tickets_with_response / total_tickets) * 100, 1)
    
    def calculate_resolution_rate(self, tickets):
        """Calculate resolution rate percentage"""
        total_tickets = tickets.count()
        if total_tickets == 0:
            return 100
        
        resolved_tickets = tickets.filter(status='CLOSED').count()
        return round((resolved_tickets / total_tickets) * 100, 1)
    
    def get_sla_performance(self, tickets):
        """Get SLA performance metrics"""
        sla_performance = {}
        
        # Get all SLAs
        slas = SLA.objects.filter(tenant=self.request.tenant, is_active=True)
        
        for sla in slas:
            sla_tickets = tickets.filter(sla=sla)
            total_tickets = sla_tickets.count()
            
            if total_tickets > 0:
                met_first_response = 0
                met_resolution = 0
                
                for ticket in sla_tickets:
                    # Check first response SLA
                    if ticket.first_response_at:
                        response_time = ticket.first_response_at - ticket.created_at
                        if response_time.total_seconds() <= (sla.first_response_time * 3600):
                            met_first_response += 1
                    
                    # Check resolution SLA
                    if ticket.resolved_at:
                        resolution_time = ticket.resolved_at - ticket.created_at
                        if resolution_time.total_seconds() <= (sla.resolution_time * 3600):
                            met_resolution += 1
                
                sla_performance[sla.name] = {
                    'total_tickets': total_tickets,
                    'first_response_rate': (met_first_response / total_tickets) * 100,
                    'resolution_rate': (met_resolution / total_tickets) * 100,
                }
        
        return sla_performance
    
    def get_recent_activity(self, tickets):
        """Get recent ticket activity"""
        recent_comments = TicketComment.objects.filter(
            ticket__in=tickets,
            is_active=True
        ).select_related(
            'ticket', 'created_by'
        ).order_by('-created_at')[:10]
        
        activity = []
        for comment in recent_comments:
            activity.append({
                'type': 'comment',
                'ticket': comment.ticket,
                'user': comment.created_by,
                'timestamp': comment.created_at,
                'description': f'Added comment to ticket #{comment.ticket.ticket_number}'
            })
        
        return activity
    
    def get_performance_trends(self, tickets):
        """Get performance trends over last 30 days"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        trends = {}
        
        # Daily ticket creation
        daily_tickets = []
        current_date = start_date
        while current_date <= end_date:
            count = tickets.filter(created_at__date=current_date).count()
            daily_tickets.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'count': count
            })
            current_date += timedelta(days=1)
        
        trends['daily_creation'] = daily_tickets
        
        # Weekly resolution rate
        weekly_resolution = []
        for i in range(4):  # Last 4 weeks
            week_start = end_date - timedelta(weeks=i+1)
            week_end = end_date - timedelta(weeks=i)
            
            week_tickets = tickets.filter(
                created_at__date__range=[week_start, week_end]
            )
            resolved = week_tickets.filter(status='CLOSED').count()
            total = week_tickets.count()
            
            rate = (resolved / max(total, 1)) * 100
            
            weekly_resolution.append({
                'week': f'Week {i+1}',
                'rate': round(rate, 1)
            })
        
        trends['weekly_resolution'] = list(reversed(weekly_resolution))
        
        return trends


class TicketListView(CRMBaseMixin, ListView):
    """Ticket list view with advanced filtering"""
    
    model = Ticket
    template_name = 'crm/ticket/list.html'
    context_object_name = 'tickets'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Ticket.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'category', 'assigned_to', 'account', 'contact', 'sla', 'created_by'
        ).prefetch_related(
            'comments'
        ).annotate(
            comments_count=Count('comments', filter=Q(comments__is_active=True)),
            last_comment_date=Max('comments__created_at')
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_tickets'):
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct()
        
        # Apply filters
        ticket_filter = TicketFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        return ticket_filter.qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = TicketFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Ticket statistics
        queryset = self.get_queryset()
        context['stats'] = self.get_ticket_list_stats(queryset)
        
        # Quick filters
        context['quick_filters'] = self.get_quick_filters()
        
        return context
    
    def get_ticket_list_stats(self, queryset):
        """Get statistics for the ticket list"""
        return {
            'total_count': queryset.count(),
            'open_count': queryset.filter(status='OPEN').count(),
            'in_progress_count': queryset.filter(status='IN_PROGRESS').count(),
            'resolved_count': queryset.filter(status='RESOLVED').count(),
            'closed_count': queryset.filter(status='CLOSED').count(),
            'high_priority_count': queryset.filter(priority='HIGH').count(),
            'critical_count': queryset.filter(priority='CRITICAL').count(),
            'unassigned_count': queryset.filter(assigned_to__isnull=True).count(),
            'overdue_count': len([t for t in queryset if t.is_overdue()]),
            'avg_response_time': self.calculate_avg_response_time(queryset),
        }
    
    def calculate_avg_response_time(self, queryset):
        """Calculate average response time"""
        tickets_with_response = queryset.filter(
            first_response_at__isnull=False
        )
        
        if not tickets_with_response.exists():
            return 0
        
        total_time = 0
        count = 0
        
        for ticket in tickets_with_response:
            if ticket.first_response_at:
                response_time = ticket.first_response_at - ticket.created_at
                total_time += response_time.total_seconds()
                count += 1
        
        if count > 0:
            avg_seconds = total_time / count
            return round(avg_seconds / 3600, 1)  # Convert to hours
        
        return 0
    
    def get_quick_filters(self):
        """Get quick filter options"""
        return [
            {'name': 'My Tickets', 'filter': 'assigned_to=me'},
            {'name': 'Unassigned', 'filter': 'assigned_to__isnull=True'},
            {'name': 'Open', 'filter': 'status=OPEN'},
            {'name': 'In Progress', 'filter': 'status=IN_PROGRESS'},
            {'name': 'High Priority', 'filter': 'priority=HIGH'},
            {'name': 'Critical', 'filter': 'priority=CRITICAL'},
            {'name': 'Overdue', 'filter': 'overdue=true'},
            {'name': 'Today', 'filter': 'created_today=true'},
        ]


class TicketDetailView(CRMBaseMixin, DetailView):
    """Comprehensive ticket detail view"""
    
    model = Ticket
    template_name = 'crm/ticket/detail.html'
    context_object_name = 'ticket'
    
    def get_queryset(self):
        return Ticket.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'category', 'assigned_to', 'account', 'contact', 'sla',
            'created_by', 'updated_by'
        ).prefetch_related(
            'comments__created_by',
            'attachments'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = self.get_object()
        
        # Comments and timeline
        context['comments'] = ticket.comments.filter(
            is_active=True
        ).select_related('created_by').order_by('created_at')
        
        # Ticket history
        context['ticket_history'] = self.get_ticket_history(ticket)
        
        # SLA information
        context['sla_info'] = self.get_sla_info(ticket)
        
        # Related tickets
        context['related_tickets'] = self.get_related_tickets(ticket)
        
        # Customer information
        context['customer_info'] = self.get_customer_info(ticket)
        
        # Suggested knowledge base articles
        context['suggested_articles'] = self.get_suggested_articles(ticket)
        
        # Time tracking
        context['time_info'] = self.get_time_info(ticket)
        
        # Available actions
        context['available_actions'] = self.get_available_actions(ticket)
        
        return context
    
    def get_ticket_history(self, ticket):
        """Get ticket change history"""
        # This would typically come from an audit log
        # For now, return basic information
        history = [
            {
                'timestamp': ticket.created_at,
                'action': 'created',
                'user': ticket.created_by,
                'description': 'Ticket created',
            }
        ]
        
        if ticket.assigned_to:
            history.append({
                'timestamp': ticket.updated_at,
                'action': 'assigned',
                'user': ticket.updated_by,
                'description': f'Assigned to {ticket.assigned_to.get_full_name()}',
            })
        
        if ticket.resolved_at:
            history.append({
                'timestamp': ticket.resolved_at,
                'action': 'resolved',
                'user': ticket.updated_by,
                'description': 'Ticket marked as resolved',
            })
        
        return sorted(history, key=lambda x: x['timestamp'])
    
    def get_sla_info(self, ticket):
        """Get SLA compliance information"""
        if not ticket.sla:
            return None
        
        info = {
            'sla': ticket.sla,
            'first_response_due': None,
            'resolution_due': None,
            'first_response_status': 'pending',
            'resolution_status': 'pending',
            'is_overdue': ticket.is_overdue(),
        }
        
        # Calculate due times
        if ticket.sla.first_response_time:
            info['first_response_due'] = ticket.created_at + timedelta(
                hours=ticket.sla.first_response_time
            )
            
            if ticket.first_response_at:
                if ticket.first_response_at <= info['first_response_due']:
                    info['first_response_status'] = 'met'
                else:
                    info['first_response_status'] = 'breached'
            elif timezone.now() > info['first_response_due']:
                info['first_response_status'] = 'overdue'
        
        if ticket.sla.resolution_time:
            info['resolution_due'] = ticket.created_at + timedelta(
                hours=ticket.sla.resolution_time
            )
            
            if ticket.resolved_at:
                if ticket.resolved_at <= info['resolution_due']:
                    info['resolution_status'] = 'met'
                else:
                    info['resolution_status'] = 'breached'
            elif timezone.now() > info['resolution_due']:
                info['resolution_status'] = 'overdue'
        
        return info
    
    def get_related_tickets(self, ticket):
        """Get related tickets for the same customer"""
        related = Ticket.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=ticket.id)
        
        if ticket.account:
            related = related.filter(account=ticket.account)
        elif ticket.contact:
            related = related.filter(contact=ticket.contact)
        else:
            related = related.none()
        
        return related.select_related('category', 'assigned_to').order_by('-created_at')[:5]
    
    def get_customer_info(self, ticket):
        """Get comprehensive customer information"""
        info = {}
        
        if ticket.account:
            account = ticket.account
            info['account'] = account
            info['primary_contact'] = account.primary_contact
            info['total_tickets'] = Ticket.objects.filter(
                tenant=self.request.tenant,
                account=account,
                is_active=True
            ).count()
            info['open_tickets'] = Ticket.objects.filter(
                tenant=self.request.tenant,
                account=account,
                status__in=['OPEN', 'IN_PROGRESS'],
                is_active=True
            ).count()
        
        if ticket.contact:
            contact = ticket.contact
            info['contact'] = contact
            info['contact_tickets'] = Ticket.objects.filter(
                tenant=self.request.tenant,
                contact=contact,
                is_active=True
            ).count()
        
        return info
    
    def get_suggested_articles(self, ticket):
        """Get suggested knowledge base articles"""
        if not ticket.subject:
            return []
        
        # Simple keyword matching
        keywords = ticket.subject.split()[:3]  # First 3 words
        
        articles = KnowledgeBase.objects.filter(
            tenant=self.request.tenant,
            is_active=True,
            is_published=True
        )
        
        for keyword in keywords:
            articles = articles.filter(
                Q(title__icontains=keyword) | Q(content__icontains=keyword)
            )
        
        return articles[:5]
    
    def get_time_info(self, ticket):
        """Get time-related information"""
        now = timezone.now()
        
        info = {
            'age': now - ticket.created_at,
            'age_hours': round((now - ticket.created_at).total_seconds() / 3600, 1),
            'response_time': None,
            'resolution_time': None,
        }
        
        if ticket.first_response_at:
            info['response_time'] = ticket.first_response_at - ticket.created_at
            info['response_time_hours'] = round(info['response_time'].total_seconds() / 3600, 1)
        
        if ticket.resolved_at:
            info['resolution_time'] = ticket.resolved_at - ticket.created_at
            info['resolution_time_hours'] = round(info['resolution_time'].total_seconds() / 3600, 1)
        
        return info
    
    def get_available_actions(self, ticket):
        """Get available actions for the current user"""
        user = self.request.user
        actions = []
        
        if ticket.status == 'OPEN':
            if user.has_perm('crm.change_ticket'):
                actions.append({
                    'name': 'Take Ticket',
                    'action': 'assign_to_me',
                    'class': 'btn-primary',
                    'icon': 'user-check'
                })
                actions.append({
                    'name': 'Start Progress',
                    'action': 'start_progress',
                    'class': 'btn-success',
                    'icon': 'play'
                })
        
        if ticket.status == 'IN_PROGRESS':
            if user == ticket.assigned_to or user.has_perm('crm.change_ticket'):
                actions.append({
                    'name': 'Mark Resolved',
                    'action': 'resolve',
                    'class': 'btn-success',
                    'icon': 'check'
                })
                actions.append({
                    'name': 'Escalate',
                    'action': 'escalate',
                    'class': 'btn-warning',
                    'icon': 'arrow-up'
                })
        
        if ticket.status == 'RESOLVED':
            actions.append({
                'name': 'Close Ticket',
                'action': 'close',
                'class': 'btn-secondary',
                'icon': 'times'
            })
            actions.append({
                'name': 'Reopen',
                'action': 'reopen',
                'class': 'btn-warning',
                'icon': 'redo'
            })
        
        return actions


class TicketCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new support ticket"""
    
    model = Ticket
    template_name = 'crm/ticket/form.html'
    permission_required = 'crm.add_ticket'
    fields = [
        'subject', 'description', 'priority', 'category', 'source',
        'account', 'contact', 'assigned_to', 'due_date', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter categories
        form.fields['category'].queryset = TicketCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Filter accounts and contacts
        form.fields['account'].queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['contact'].queryset = Contact.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Pre-populate from account/contact if specified
        account_id = self.request.GET.get('account_id')
        contact_id = self.request.GET.get('contact_id')
        
        if account_id:
            try:
                account = Account.objects.get(
                    id=account_id,
                    tenant=self.request.tenant
                )
                form.initial['account'] = account
                # Filter contacts for this account
                form.fields['contact'].queryset = account.contacts.filter(is_active=True)
            except Account.DoesNotExist:
                pass
        
        if contact_id:
            try:
                contact = Contact.objects.get(
                    id=contact_id,
                    tenant=self.request.tenant
                )
                form.initial['contact'] = contact
                form.initial['account'] = contact.account
            except Contact.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        # Auto-assign SLA based on category and priority
        if form.instance.category:
            sla = self.get_appropriate_sla(form.instance)
            form.instance.sla = sla
        
        # Auto-assign if configured
        if not form.instance.assigned_to:
            assigned_user = self.get_auto_assigned_user(form.instance)
            form.instance.assigned_to = assigned_user
        
        response = super().form_valid(form)
        
        # Send notifications
        self.send_ticket_notifications()
        
        # Log ticket creation activity
        self.log_ticket_creation()
        
        messages.success(
            self.request,
            f'Ticket #{self.object.ticket_number} created successfully.'
        )
        
        return response
    
    def get_appropriate_sla(self, ticket):
        """Get appropriate SLA based on category and priority"""
        sla = SLA.objects.filter(
            tenant=self.request.tenant,
            is_active=True,
            categories=ticket.category
        ).first()
        
        if not sla:
            # Get default SLA
            sla = SLA.objects.filter(
                tenant=self.request.tenant,
                is_active=True,
                is_default=True
            ).first()
        
        return sla
    
    def get_auto_assigned_user(self, ticket):
        """Auto-assign ticket based on configuration"""
        # Simple round-robin assignment to support team
        support_users = User.objects.filter(
            tenant=self.request.tenant,
            is_active=True,
            groups__name='Support Team'  # Assuming support team group
        ).order_by('id')
        
        if support_users.exists():
            # Get user with least recent assignment
            last_assigned = Ticket.objects.filter(
                tenant=self.request.tenant,
                assigned_to__in=support_users
            ).order_by('-created_at').first()
            
            if last_assigned and last_assigned.assigned_to:
                current_index = list(support_users).index(last_assigned.assigned_to)
                next_index = (current_index + 1) % len(support_users)
                return support_users[next_index]
            else:
                return support_users.first()
        
        return None
    
    def send_ticket_notifications(self):
        """Send ticket creation notifications"""
        try:
            notification_service = NotificationService(self.request.tenant)
            
            # Notify assigned user
            if self.object.assigned_to:
                notification_service.send_ticket_assignment_notification(
                    self.object, self.object.assigned_to
                )
            
            # Notify customer
            if self.object.contact and self.object.contact.email:
                notification_service.send_ticket_confirmation_notification(
                    self.object, self.object.contact.email
                )
        
        except Exception as e:
            # Log error but don't fail ticket creation
            messages.warning(
                self.request,
                f'Ticket created but notifications failed: {str(e)}'
            )
    
    def log_ticket_creation(self):
        """Log ticket creation activity"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Ticket Created',
            defaults={
                'category': 'SUPPORT',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Support ticket #{self.object.ticket_number} created',
            description=f'New support ticket: {self.object.subject}',
            assigned_to=self.object.assigned_to or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Ticket),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:ticket-detail', kwargs={'pk': self.object.pk})


class TicketUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update support ticket"""
    
    model = Ticket
    template_name = 'crm/ticket/form.html'
    permission_required = 'crm.change_ticket'
    fields = [
        'subject', 'description', 'priority', 'category', 'status',
        'assigned_to', 'due_date', 'tags'
    ]
    
    def get_queryset(self):
        return Ticket.objects.filter(tenant=self.request.tenant)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Track status changes
        old_status = None
        old_assigned_to = None
        
        if self.object.pk:
            old_ticket = Ticket.objects.get(pk=self.object.pk)
            old_status = old_ticket.status
            old_assigned_to = old_ticket.assigned_to
        
        response = super().form_valid(form)
        
        # Handle status changes
        if old_status and old_status != form.instance.status:
            self.handle_status_change(old_status, form.instance.status)
        
        # Handle assignment changes
        if old_assigned_to != form.instance.assigned_to:
            self.handle_assignment_change(old_assigned_to, form.instance.assigned_to)
        
        messages.success(
            self.request,
            f'Ticket #{form.instance.ticket_number} updated successfully.'
        )
        
        return response
    
    def handle_status_change(self, old_status, new_status):
        """Handle ticket status change"""
        # Update timestamps based on status
        if new_status == 'IN_PROGRESS' and old_status == 'OPEN':
            self.object.started_at = timezone.now()
        elif new_status == 'RESOLVED':
            self.object.resolved_at = timezone.now()
        elif new_status == 'CLOSED' and old_status == 'RESOLVED':
            self.object.closed_at = timezone.now()
        
        self.object.save()
        
        # Log status change
        self.log_status_change(old_status, new_status)
        
        # Send notifications
        self.send_status_change_notifications(old_status, new_status)
    
    def handle_assignment_change(self, old_assigned_to, new_assigned_to):
        """Handle ticket assignment change"""
        if new_assigned_to:
            # Send assignment notification
            try:
                notification_service = NotificationService(self.request.tenant)
                notification_service.send_ticket_assignment_notification(
                    self.object, new_assigned_to
                )
            except Exception:
                pass  # Fail silently
        
        # Log assignment change
        self.log_assignment_change(old_assigned_to, new_assigned_to)
    
    def log_status_change(self, old_status, new_status):
        """Log status change activity"""
        TicketComment.objects.create(
            tenant=self.request.tenant,
            ticket=self.object,
            comment=f'Status changed from {old_status} to {new_status}',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=self.request.user
        )
    
    def log_assignment_change(self, old_assigned_to, new_assigned_to):
        """Log assignment change"""
        old_name = old_assigned_to.get_full_name() if old_assigned_to else 'Unassigned'
        new_name = new_assigned_to.get_full_name() if new_assigned_to else 'Unassigned'
        
        TicketComment.objects.create(
            tenant=self.request.tenant,
            ticket=self.object,
            comment=f'Assigned from {old_name} to {new_name}',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=self.request.user
        )
    
    def send_status_change_notifications(self, old_status, new_status):
        """Send status change notifications"""
        try:
            notification_service = NotificationService(self.request.tenant)
            
            # Notify customer of status change
            if self.object.contact and self.object.contact.email:
                notification_service.send_ticket_status_notification(
                    self.object, self.object.contact.email, old_status, new_status
                )
        except Exception:
            pass  # Fail silently
    
    def get_success_url(self):
        return reverse_lazy('crm:ticket-detail', kwargs={'pk': self.object.pk})


class TicketCommentView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Add comment to ticket"""
    
    permission_required = 'crm.add_ticketcomment'
    
    def post(self, request, pk):
        ticket = get_object_or_404(
            Ticket,
            pk=pk,
            tenant=request.tenant
        )
        
        comment_text = request.POST.get('comment', '').strip()
        is_internal = request.POST.get('is_internal') == 'true'
        
        if not comment_text:
            return JsonResponse({
                'success': False,
                'message': 'Comment cannot be empty'
            })
        
        try:
            comment = TicketComment.objects.create(
                tenant=request.tenant,
                ticket=ticket,
                comment=comment_text,
                is_internal=is_internal,
                created_by=request.user
            )
            
            # Update first response time if this is the first response
            if not ticket.first_response_at and not is_internal:
                ticket.first_response_at = timezone.now()
                ticket.save(update_fields=['first_response_at'])
            
            # Send notifications
            if not is_internal:
                self.send_comment_notifications(ticket, comment)
            
            return JsonResponse({
                'success': True,
                'message': 'Comment added successfully',
                'comment_id': comment.id,
                'comment_html': self.render_comment_html(comment)
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def send_comment_notifications(self, ticket, comment):
        """Send comment notifications"""
        try:
            notification_service = NotificationService(self.request.tenant)
            
            # Notify customer
            if ticket.contact and ticket.contact.email:
                notification_service.send_ticket_update_notification(
                    ticket, ticket.contact.email, comment.comment
                )
            
            # Notify assigned user if not the commenter
            if ticket.assigned_to and ticket.assigned_to != comment.created_by:
                notification_service.send_ticket_comment_notification(
                    ticket, ticket.assigned_to, comment
                )
        
        except Exception:
            pass  # Fail silently
    
    def render_comment_html(self, comment):
        """Render comment HTML for AJAX response"""
        from django.template.loader import render_to_string
        
        return render_to_string('crm/ticket/comment_item.html', {
            'comment': comment
        })


class TicketActionView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Handle ticket actions (assign, resolve, close, etc.)"""
    
    permission_required = 'crm.change_ticket'
    
    def post(self, request, pk):
        ticket = get_object_or_404(
            Ticket,
            pk=pk,
            tenant=request.tenant
        )
        
        action = request.POST.get('action')
        
        try:
            if action == 'assign_to_me':
                return self.assign_to_me(ticket, request.user)
            elif action == 'start_progress':
                return self.start_progress(ticket, request.user)
            elif action == 'resolve':
                return self.resolve_ticket(ticket, request.user, request.POST)
            elif action == 'close':
                return self.close_ticket(ticket, request.user, request.POST)
            elif action == 'reopen':
                return self.reopen_ticket(ticket, request.user)
            elif action == 'escalate':
                return self.escalate_ticket(ticket, request.user, request.POST)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def assign_to_me(self, ticket, user):
        """Assign ticket to current user"""
        old_assigned_to = ticket.assigned_to
        ticket.assigned_to = user
        ticket.status = 'IN_PROGRESS'
        ticket.started_at = timezone.now()
        ticket.updated_by = user
        ticket.save()
        
        # Log assignment
        TicketComment.objects.create(
            tenant=user.tenant,
            ticket=ticket,
            comment=f'Ticket assigned to {user.get_full_name()}',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Ticket assigned to you',
            'status': ticket.status,
            'assigned_to': user.get_full_name()
        })
    
    def start_progress(self, ticket, user):
        """Start working on ticket"""
        ticket.status = 'IN_PROGRESS'
        ticket.started_at = timezone.now()
        ticket.updated_by = user
        ticket.save()
        
        # Log status change
        TicketComment.objects.create(
            tenant=user.tenant,
            ticket=ticket,
            comment='Work started on ticket',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Ticket status updated to In Progress',
            'status': ticket.status
        })
    
    def resolve_ticket(self, ticket, user, post_data):
        """Resolve ticket"""
        resolution = post_data.get('resolution', '').strip()
        
        ticket.status = 'RESOLVED'
        ticket.resolved_at = timezone.now()
        ticket.resolution = resolution
        ticket.updated_by = user
        ticket.save()
        
        # Add resolution comment
        if resolution:
            TicketComment.objects.create(
                tenant=user.tenant,
                ticket=ticket,
                comment=f'Ticket resolved: {resolution}',
                comment_type='RESOLUTION',
                is_internal=False,
                created_by=user
            )
        
        # Send notification
        try:
            notification_service = NotificationService(user.tenant)
            if ticket.contact and ticket.contact.email:
                notification_service.send_ticket_resolution_notification(
                    ticket, ticket.contact.email, resolution
                )
        except Exception:
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Ticket marked as resolved',
            'status': ticket.status
        })
    
    def close_ticket(self, ticket, user, post_data):
        """Close ticket"""
        closing_notes = post_data.get('closing_notes', '').strip()
        
        ticket.status = 'CLOSED'
        ticket.closed_at = timezone.now()
        ticket.closing_notes = closing_notes
        ticket.updated_by = user
        ticket.save()
        
        # Add closing comment
        if closing_notes:
            TicketComment.objects.create(
                tenant=user.tenant,
                ticket=ticket,
                comment=f'Ticket closed: {closing_notes}',
                comment_type='SYSTEM',
                is_internal=True,
                created_by=user
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Ticket closed',
            'status': ticket.status
        })
    
    def reopen_ticket(self, ticket, user):
        """Reopen ticket"""
        ticket.status = 'OPEN'
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.updated_by = user
        ticket.save()
        
        # Log reopening
        TicketComment.objects.create(
            tenant=user.tenant,
            ticket=ticket,
            comment='Ticket reopened',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Ticket reopened',
            'status': ticket.status
        })
    
    def escalate_ticket(self, ticket, user, post_data):
        """Escalate ticket"""
        escalation_reason = post_data.get('escalation_reason', '').strip()
        escalate_to_id = post_data.get('escalate_to')
        
        old_priority = ticket.priority
        
        # Increase priority
        if ticket.priority == 'LOW':
            ticket.priority = 'MEDIUM'
        elif ticket.priority == 'MEDIUM':
            ticket.priority = 'HIGH'
        elif ticket.priority == 'HIGH':
            ticket.priority = 'CRITICAL'
        
        # Reassign if specified
        if escalate_to_id:
            try:
                escalate_to = User.objects.get(
                    id=escalate_to_id,
                    tenant=user.tenant
                )
                ticket.assigned_to = escalate_to
            except User.DoesNotExist:
                pass
        
        ticket.escalated = True
        ticket.escalated_at = timezone.now()
        ticket.updated_by = user
        ticket.save()
        
        # Log escalation
        escalation_comment = f'Ticket escalated from {old_priority} to {ticket.priority}'
        if escalation_reason:
            escalation_comment += f'. Reason: {escalation_reason}'
        
        TicketComment.objects.create(
            tenant=user.tenant,
            ticket=ticket,
            comment=escalation_comment,
            comment_type='ESCALATION',
            is_internal=True,
            created_by=user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Ticket escalated to {ticket.priority}',
            'priority': ticket.priority
        })


class KnowledgeBaseView(CRMBaseMixin, View):
    """Knowledge base management"""
    
    def get(self, request):
        # Get published articles
        articles = KnowledgeBase.objects.filter(
            tenant=request.tenant,
            is_active=True,
            is_published=True
        ).select_related('category', 'created_by').order_by('-created_at')
        
        # Apply search
        search_query = request.GET.get('search')
        if search_query:
            articles = articles.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(tags__icontains=search_query)
            )
        
        # Pagination
        paginator = Paginator(articles, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Categories
        categories = TicketCategory.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).annotate(
            articles_count=Count('knowledge_articles')
        ).order_by('name')
        
        context = {
            'articles': page_obj,
            'categories': categories,
            'search_query': search_query,
        }
        
        return render(request, 'crm/ticket/knowledge_base.html', context)


# ============================================================================
# API ViewSets
# ============================================================================

class TicketViewSet(CRMBaseViewSet):
    """Ticket API ViewSet with comprehensive functionality"""
    
    queryset = Ticket.objects.all()
    permission_classes = [TicketPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TicketFilter
    search_fields = ['subject', 'description', 'ticket_number']
    ordering_fields = ['created_at', 'priority', 'status', 'due_date']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TicketDetailSerializer
        return TicketSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'category', 'assigned_to', 'account', 'contact', 'sla', 'created_by'
        ).prefetch_related(
            'comments'
        ).annotate(
            comments_count=Count('comments', filter=Q(comments__is_active=True))
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_tickets'):
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct()
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add comment to ticket"""
        ticket = self.get_object()
        
        serializer = TicketCommentSerializer(data=request.data)
        if serializer.is_valid():
            comment = serializer.save(
                tenant=request.tenant,
                ticket=ticket,
                created_by=request.user
            )
            
            # Update first response time
            if not ticket.first_response_at and not serializer.validated_data.get('is_internal', False):
                ticket.first_response_at = timezone.now()
                ticket.save(update_fields=['first_response_at'])
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to user"""
        ticket = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            assignee = User.objects.get(id=user_id, tenant=request.tenant)
            
            old_assigned_to = ticket.assigned_to
            ticket.assigned_to = assignee
            ticket.updated_by = request.user
            
            if ticket.status == 'OPEN':
                ticket.status = 'IN_PROGRESS'
                ticket.started_at = timezone.now()
            
            ticket.save()
            
            # Log assignment
            TicketComment.objects.create(
                tenant=request.tenant,
                ticket=ticket,
                comment=f'Ticket assigned to {assignee.get_full_name()}',
                comment_type='SYSTEM',
                is_internal=True,
                created_by=request.user
            )
            
            return Response({
                'success': True,
                'message': f'Ticket assigned to {assignee.get_full_name()}',
                'assigned_to': assignee.get_full_name(),
                'status': ticket.status
            })
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Change ticket status"""
        ticket = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {'error': 'status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_by = request.user
        
        # Update timestamps based on status
        if new_status == 'IN_PROGRESS' and old_status == 'OPEN':
            ticket.started_at = timezone.now()
        elif new_status == 'RESOLVED':
            ticket.resolved_at = timezone.now()
            # Resolution comment from request data
            resolution = request.data.get('resolution', '')
            if resolution:
                ticket.resolution = resolution
        elif new_status == 'CLOSED':
            ticket.closed_at = timezone.now()
        
        ticket.save()
        
        # Log status change
        TicketComment.objects.create(
            tenant=request.tenant,
            ticket=ticket,
            comment=f'Status changed from {old_status} to {new_status}',
            comment_type='SYSTEM',
            is_internal=True,
            created_by=request.user
        )
        
        return Response({
            'success': True,
            'message': f'Ticket status changed to {new_status}',
            'status': new_status
        })
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics"""
        tickets = self.filter_queryset(self.get_queryset())
        
        stats = {
            'total_tickets': tickets.count(),
            'open_tickets': tickets.filter(status='OPEN').count(),
            'in_progress': tickets.filter(status='IN_PROGRESS').count(),
            'resolved': tickets.filter(status='RESOLVED').count(),
            'closed': tickets.filter(status='CLOSED').count(),
            'high_priority': tickets.filter(priority='HIGH').count(),
            'critical': tickets.filter(priority='CRITICAL').count(),
            'unassigned': tickets.filter(assigned_to__isnull=True).count(),
        }
        
        # Calculate overdue tickets
        overdue_count = 0
        for ticket in tickets.filter(status__in=['OPEN', 'IN_PROGRESS']):
            if ticket.is_overdue():
                overdue_count += 1
        
        stats['overdue'] = overdue_count
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        """Get current user's tickets"""
        my_tickets = self.filter_queryset(
            self.get_queryset()
        ).filter(
            assigned_to=request.user
        ).exclude(
            status__in=['CLOSED']
        ).order_by('priority', 'created_at')
        
        serializer = self.get_serializer(my_tickets, many=True)
        return Response(serializer.data)


class TicketCategoryViewSet(CRMBaseViewSet):
    """Ticket Category API ViewSet"""
    
    queryset = TicketCategory.objects.all()
    serializer_class = TicketCategorySerializer
    permission_classes = [TicketPermission]
    
    def get_queryset(self):
        return super().get_queryset().annotate(
            tickets_count=Count('tickets')
        )


class KnowledgeBaseViewSet(CRMBaseViewSet):
    """Knowledge Base API ViewSet"""
    
    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    permission_classes = [TicketPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('category', 'created_by')
        
        # Only show published articles to non-staff users
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(is_published=True)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search knowledge base articles"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response([])
        
        articles = self.get_queryset().filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__icontains=query)
        )[:10]
        
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)


class SLAViewSet(CRMBaseViewSet):
    """SLA API ViewSet"""
    
    queryset = SLA.objects.all()
    serializer_class = SLASerializer
    permission_classes = [TicketPermission]
    
    def get_queryset(self):
        return super().get_queryset().prefetch_related('categories').annotate(
            tickets_count=Count('tickets')
        )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get SLA performance metrics"""
        sla = self.get_object()
        tickets = sla.tickets.filter(is_active=True)
        
        if not tickets.exists():
            return Response({
                'total_tickets': 0,
                'first_response_rate': 0,
                'resolution_rate': 0
            })
        
        # Calculate performance metrics
        met_first_response = 0
        met_resolution = 0
        
        for ticket in tickets:
            # First response SLA
            if ticket.first_response_at:
                response_time = ticket.first_response_at - ticket.created_at
                if response_time.total_seconds() <= (sla.first_response_time * 3600):
                    met_first_response += 1
            
            # Resolution SLA
            if ticket.resolved_at:
                resolution_time = ticket.resolved_at - ticket.created_at
                if resolution_time.total_seconds() <= (sla.resolution_time * 3600):
                    met_resolution += 1
        
        total_tickets = tickets.count()
        
        return Response({
            'total_tickets': total_tickets,
            'first_response_rate': (met_first_response / total_tickets) * 100,
            'resolution_rate': (met_resolution / total_tickets) * 100,
            'first_response_sla_hours': sla.first_response_time,
            'resolution_sla_hours': sla.resolution_time
        })