# backend/apps/crm/permissions/lead.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Lead, LeadSource

class LeadPermission(CRMPermission):
    """Permission class for Lead model."""
    
    MODEL_PERMS = {
        'view_lead': 'Can view leads',
        'add_lead': 'Can add leads',
        'change_lead': 'Can change leads',
        'delete_lead': 'Can delete leads',
        'convert_lead': 'Can convert leads',
        'assign_lead': 'Can assign leads',
        'export_lead': 'Can export leads',
        'import_lead': 'Can import leads',
        'score_lead': 'Can score leads',
    }
    
    def has_permission(self, request, view):
        """Check lead permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_lead')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_lead')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_lead')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_lead')
        elif view.action == 'convert':
            return self.has_perm(request.user, 'convert_lead')
        elif view.action == 'assign':
            return self.has_perm(request.user, 'assign_lead')
        elif view.action in ['export', 'bulk_export']:
            return self.has_perm(request.user, 'export_lead')
        elif view.action in ['import', 'bulk_import']:
            return self.has_perm(request.user, 'import_lead')
        elif view.action == 'score':
            return self.has_perm(request.user, 'score_lead')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check lead object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Lead conversion requires special permissions
        if view.action == 'convert':
            return self.can_convert_lead(request.user, obj)
        
        # Check ownership and assignment rules
        if hasattr(obj, 'owner') and obj.owner:
            if obj.owner.user == request.user:
                return True
        
        # Check if lead is unassigned and user can claim it
        if not hasattr(obj, 'owner') or not obj.owner:
            return self.can_claim_unassigned_lead(request.user, obj)
        
        # Check territory and team access
        return self.check_lead_access_rules(request.user, obj)
    
    def can_convert_lead(self, user, lead):
        """Check if user can convert this lead."""
        # Lead must be qualified
        if lead.status not in ['qualified', 'hot']:
            return False
        
        # User must have convert permission
        if not self.has_perm(user, 'convert_lead'):
            return False
        
        # Check ownership or special conversion permissions
        if hasattr(lead, 'owner') and lead.owner:
            if lead.owner.user == user:
                return True
        
        # Managers can convert team leads
        return self.is_team_manager(user, lead)
    
    def can_claim_unassigned_lead(self, user, lead):
        """Check if user can claim an unassigned lead."""
        if not self.has_perm(user, 'assign_lead'):
            return False
        
        # Check territory restrictions
        if hasattr(lead, 'territory') and hasattr(user, 'crm_profile'):
            user_territory = user.crm_profile.territory
            if lead.territory and lead.territory != user_territory:
                return False
        
        return True
    
    def check_lead_access_rules(self, user, lead):
        """Check lead access based on business rules."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_profile = user.crm_profile
        
        # Check data access level
        if user_profile.data_access_level == 'all':
            return True
        elif user_profile.data_access_level == 'territory':
            return self.has_territory_access(user, lead)
        elif user_profile.data_access_level == 'team':
            return self.has_team_access(user, lead)
        elif user_profile.data_access_level == 'own':
            return hasattr(lead, 'owner') and lead.owner.user == user
        
        return False
    
    def is_team_manager(self, user, lead):
        """Check if user is a team manager for the lead."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_team = user.crm_profile.team
        if not user_team:
            return False
        
        # Check if user is team manager
        if user_team.manager and user_team.manager.user == user:
            # Check if lead belongs to team territory
            if hasattr(lead, 'owner') and lead.owner:
                lead_owner_team = getattr(lead.owner, 'team', None)
                return lead_owner_team == user_team
        
        return False

class LeadSourcePermission(CRMPermission):
    """Permission class for LeadSource model."""
    
    MODEL_PERMS = {
        'view_leadsource': 'Can view lead sources',
        'add_leadsource': 'Can add lead sources',
        'change_leadsource': 'Can change lead sources',
        'delete_leadsource': 'Can delete lead sources',
    }
    
    def has_permission(self, request, view):
        """Lead source permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_leadsource')
        
        # Modification typically requires admin or marketing role
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (self.has_marketing_role(request.user) or 
                   request.user.is_staff or
                   self.has_perm(request.user, f'{view.action}_leadsource'))
        
        return True
    
    def has_marketing_role(self, user):
        """Check if user has marketing role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['marketing_manager', 'marketing_coordinator']
        return False