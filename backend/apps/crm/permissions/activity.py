# backend/apps/crm/permissions/activity.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Activity, ActivityType

class ActivityPermission(CRMPermission):
    """Permission class for Activity model."""
    
    MODEL_PERMS = {
        'view_activity': 'Can view activities',
        'add_activity': 'Can add activities',
        'change_activity': 'Can change activities',
        'delete_activity': 'Can delete activities',
        'view_all_activities': 'Can view all team activities',
        'assign_activity': 'Can assign activities to others',
    }
    
    def has_permission(self, request, view):
        """Check activity permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_activity')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_activity')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_activity')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_activity')
        elif view.action == 'assign':
            return self.has_perm(request.user, 'assign_activity')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check activity object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Activity assignment requires special permission
        if view.action == 'assign':
            return self.can_assign_activity(request.user, obj)
        
        # Check ownership
        if hasattr(obj, 'assigned_to') and obj.assigned_to:
            # Assigned user can view/modify their activities
            if obj.assigned_to.user == request.user:
                return True
        
        # Check created by
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Check related object access
        if hasattr(obj, 'related_to') and obj.related_to:
            return self.can_access_related_object(request.user, obj)
        
        # Managers can access team activities
        return self.can_access_team_activities(request.user, obj)
    
    def can_assign_activity(self, user, activity):
        """Check if user can assign activities."""
        if not self.has_perm(user, 'assign_activity'):
            return False
        
        # Can assign own activities
        if hasattr(activity, 'created_by') and activity.created_by == user:
            return True
        
        # Managers can reassign team activities
        return self.is_team_manager(user) or self.has_manager_role(user)
    
    def can_access_related_object(self, user, activity):
        """Check access to related object."""
        related_object = activity.related_to
        if not related_object:
            return True
        
        # Import permission classes to avoid circular imports
        from .account import AccountPermission
        from .lead import LeadPermission
        from .opportunity import OpportunityPermission
        
        # Check permission based on related object type
        if hasattr(related_object, '_meta'):
            model_name = related_object._meta.model_name
            
            if model_name == 'account':
                permission = AccountPermission()
                return permission.has_object_permission(None, None, related_object)
            elif model_name == 'lead':
                permission = LeadPermission()
                return permission.has_object_permission(None, None, related_object)
            elif model_name == 'opportunity':
                permission = OpportunityPermission()
                return permission.has_object_permission(None, None, related_object)
        
        return True
    
    def can_access_team_activities(self, user, activity):
        """Check if user can access team activities."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        # Check if user has permission to view all activities
        if self.has_perm(user, 'view_all_activities'):
            return True
        
        # Check team-based access
        user_team = user.crm_profile.team
        if not user_team:
            return False
        
        # Check if activity belongs to team member
        if hasattr(activity, 'assigned_to') and activity.assigned_to:
            assigned_team = getattr(activity.assigned_to, 'team', None)
            return assigned_team == user_team
        
        return False

class ActivityTypePermission(CRMPermission):
    """Permission class for ActivityType model."""
    
    MODEL_PERMS = {
        'view_activitytype': 'Can view activity types',
        'add_activitytype': 'Can add activity types',
        'change_activitytype': 'Can change activity types',
        'delete_activitytype': 'Can delete activity types',
    }
    
    def has_permission(self, request, view):
        """Activity type permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_activitytype')
        
        # Modification requires admin access
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (request.user.is_staff or 
                   self.has_admin_role(request.user) or
                   self.has_perm(request.user, f'{view.action}_activitytype'))
        
        return True