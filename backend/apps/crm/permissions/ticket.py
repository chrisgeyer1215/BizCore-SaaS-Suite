# backend/apps/crm/permissions/ticket.py
from rest_framework import permissions
from django.utils import timezone
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Ticket, TicketCategory, SLA

class TicketPermission(CRMPermission):
    """Permission class for Ticket model."""
    
    MODEL_PERMS = {
        'view_ticket': 'Can view tickets',
        'add_ticket': 'Can add tickets',
        'change_ticket': 'Can change tickets',
        'delete_ticket': 'Can delete tickets',
        'assign_ticket': 'Can assign tickets',
        'escalate_ticket': 'Can escalate tickets',
        'resolve_ticket': 'Can resolve tickets',
        'reopen_ticket': 'Can reopen tickets',
        'view_customer_tickets': 'Can view customer tickets',
        'access_sensitive_tickets': 'Can access sensitive tickets',
    }
    
    def has_permission(self, request, view):
        """Check ticket permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_ticket')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_ticket')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_ticket')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_ticket')
        elif view.action == 'assign':
            return self.has_perm(request.user, 'assign_ticket')
        elif view.action == 'escalate':
            return self.has_perm(request.user, 'escalate_ticket')
        elif view.action == 'resolve':
            return self.has_perm(request.user, 'resolve_ticket')
        elif view.action == 'reopen':
            return self.has_perm(request.user, 'reopen_ticket')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check ticket object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check sensitive ticket access
        if hasattr(obj, 'is_sensitive') and obj.is_sensitive:
            if not self.has_perm(request.user, 'access_sensitive_tickets'):
                return False
        
        # Ticket resolution requires special checks
        if view.action == 'resolve':
            return self.can_resolve_ticket(request.user, obj)
        
        # Ticket escalation requires approval
        if view.action == 'escalate':
            return self.can_escalate_ticket(request.user, obj)
        
        # Check assignment permissions
        if view.action == 'assign':
            return self.can_assign_ticket(request.user, obj)
        
        # Check ownership and team access
        if hasattr(obj, 'assigned_to') and obj.assigned_to:
            # Assigned agent can access
            if obj.assigned_to.user == request.user:
                return True
        
        # Check if user created the ticket
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Check customer access (if ticket belongs to customer)
        if self.is_customer_ticket(request.user, obj):
            return self.has_perm(request.user, 'view_customer_tickets')
        
        # Check support team access
        return self.has_support_team_access(request.user, obj)
    
    def can_resolve_ticket(self, user, ticket):
        """Check if user can resolve ticket."""
        if not self.has_perm(user, 'resolve_ticket'):
            return False
        
        # Assigned agent can resolve
        if hasattr(ticket, 'assigned_to') and ticket.assigned_to:
            if ticket.assigned_to.user == user:
                return True
        
        # Support managers can resolve any ticket
        if self.has_support_manager_role(user):
            return True
        
        # Check if ticket is in resolvable status
        if hasattr(ticket, 'status'):
            return ticket.status in ['open', 'in_progress', 'pending']
        
        return False
    
    def can_escalate_ticket(self, user, ticket):
        """Check if user can escalate ticket."""
        if not self.has_perm(user, 'escalate_ticket'):
            return False
        
        # Check SLA breach for automatic escalation
        if self.is_sla_breached(ticket):
            return True
        
        # Check escalation conditions
        return self.check_escalation_conditions(user, ticket)
    
    def can_assign_ticket(self, user, ticket):
        """Check if user can assign ticket."""
        if not self.has_perm(user, 'assign_ticket'):
            return False
        
        # Support managers can assign any ticket
        if self.has_support_manager_role(user):
            return True
        
        # Check if user is team lead
        return self.is_support_team_lead(user)
    
    def is_customer_ticket(self, user, ticket):
        """Check if this is customer's own ticket."""
        if hasattr(ticket, 'customer') and ticket.customer:
            # Check if user is associated with the customer
            if hasattr(user, 'crm_profile'):
                user_account = getattr(user.crm_profile, 'account', None)
                return user_account == ticket.customer
        return False
    
    def has_support_team_access(self, user, ticket):
        """Check support team access."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_team = user.crm_profile.team
        if not user_team or user_team.team_type != 'support':
            return False
        
        # Check ticket assignment to team
        if hasattr(ticket, 'assigned_team'):
            return ticket.assigned_team == user_team
        
        # Check if assigned user is in same team
        if hasattr(ticket, 'assigned_to') and ticket.assigned_to:
            assigned_team = getattr(ticket.assigned_to, 'team', None)
            return assigned_team == user_team
        
        return True
    
    def is_sla_breached(self, ticket):
        """Check if ticket SLA is breached."""
        if hasattr(ticket, 'sla') and ticket.sla:
            if hasattr(ticket, 'created_at'):
                time_elapsed = timezone.now() - ticket.created_at
                return time_elapsed > ticket.sla.response_time
        return False
    
    def check_escalation_conditions(self, user, ticket):
        """Check various escalation conditions."""
        # Priority-based escalation
        if hasattr(ticket, 'priority'):
            if ticket.priority == 'critical':
                return True
            elif ticket.priority == 'high' and self.has_senior_support_role(user):
                return True
        
        # Time-based escalation
        if hasattr(ticket, 'created_at'):
            hours_open = (timezone.now() - ticket.created_at).total_seconds() / 3600
            if hours_open > 24:  # 24 hours without resolution
                return True
        
        return False
    
    def has_support_manager_role(self, user):
        """Check if user has support manager role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['support_manager', 'customer_success_manager']
        return False
    
    def has_senior_support_role(self, user):
        """Check if user has senior support role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['senior_support', 'support_manager']
        return False
    
    def is_support_team_lead(self, user):
        """Check if user is support team lead."""
        if hasattr(user, 'crm_profile'):
            user_team = user.crm_profile.team
            if user_team and user_team.team_type == 'support':
                return user_team.manager and user_team.manager.user == user
        return False

class TicketCategoryPermission(CRMPermission):
    """Permission class for TicketCategory model."""
    
    MODEL_PERMS = {
        'view_ticketcategory': 'Can view ticket categories',
        'add_ticketcategory': 'Can add ticket categories',
        'change_ticketcategory': 'Can change ticket categories',
        'delete_ticketcategory': 'Can delete ticket categories',
    }
    
    def has_permission(self, request, view):
        """Ticket category permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_ticketcategory')
        
        # Modification requires admin or support manager access
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (request.user.is_staff or 
                   self.has_support_manager_role(request.user) or
                   self.has_perm(request.user, f'{view.action}_ticketcategory'))
        
        return True