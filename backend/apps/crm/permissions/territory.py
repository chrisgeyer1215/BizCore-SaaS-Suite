# backend/apps/crm/permissions/territory.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Territory, TerritoryAssignment, Team

class TerritoryPermission(CRMPermission):
    """Permission class for Territory model."""
    
    MODEL_PERMS = {
        'view_territory': 'Can view territories',
        'add_territory': 'Can add territories',
        'change_territory': 'Can change territories',
        'delete_territory': 'Can delete territories',
        'assign_territory': 'Can assign territories',
        'manage_territory_hierarchy': 'Can manage territory hierarchy',
        'view_all_territories': 'Can view all territories',
    }
    
    def has_permission(self, request, view):
        """Check territory permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_territory')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_territory')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_territory')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_territory')
        elif view.action == 'assign':
            return self.has_perm(request.user, 'assign_territory')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check territory object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Territory assignment requires special permission
        if view.action == 'assign':
            return self.can_assign_territory(request.user, obj)
        
        # Check if user can view all territories
        if self.has_perm(request.user, 'view_all_territories'):
            return True
        
        # Check if user belongs to this territory
        if self.belongs_to_territory(request.user, obj):
            return True
        
        # Check if user manages this territory
        if self.manages_territory(request.user, obj):
            return True
        
        # Territory hierarchy access
        return self.has_hierarchy_access(request.user, obj)
    
    def can_assign_territory(self, user, territory):
        """Check if user can assign territory."""
        if not self.has_perm(user, 'assign_territory'):
            return False
        
        # Sales managers can assign territories
        if self.has_sales_manager_role(user):
            return True
        
        # Territory managers can assign within their territory
        if self.manages_territory(user, territory):
            return True
        
        return False
    
    def belongs_to_territory(self, user, territory):
        """Check if user belongs to territory."""
        if hasattr(user, 'crm_profile'):
            user_territory = user.crm_profile.territory
            return user_territory == territory
        return False
    
    def manages_territory(self, user, territory):
        """Check if user manages territory."""
        if hasattr(territory, 'manager'):
            return territory.manager and territory.manager.user == user
        return False
    
    def has_hierarchy_access(self, user, territory):
        """Check hierarchy-based access."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_territory = user.crm_profile.territory
        if not user_territory:
            return False
        
        # Check if territory is parent or child of user's territory
        if hasattr(territory, 'parent'):
            if territory.parent == user_territory:
                return True
        
        # Check if user's territory is parent
        if hasattr(user_territory, 'children'):
            return territory in user_territory.children.all()
        
        return False
    
    def has_sales_manager_role(self, user):
        """Check if user has sales manager role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in [
                'sales_manager', 'sales_director', 'territory_manager'
            ]
        return False

class TerritoryAssignmentPermission(CRMPermission):
    """Permission class for TerritoryAssignment model."""
    
    MODEL_PERMS = {
        'view_territoryassignment': 'Can view territory assignments',
        'add_territoryassignment': 'Can add territory assignments',
        'change_territoryassignment': 'Can change territory assignments',
        'delete_territoryassignment': 'Can delete territory assignments',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check territory assignment permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check access to parent territory
        if hasattr(obj, 'territory'):
            territory_permission = TerritoryPermission()
            return territory_permission.has_object_permission(
                request, view, obj.territory
            )
        
        return True

class TeamPermission(CRMPermission):
    """Permission class for Team model."""
    
    MODEL_PERMS = {
        'view_team': 'Can view teams',
        'add_team': 'Can add teams',
        'change_team': 'Can change teams',
        'delete_team': 'Can delete teams',
        'manage_team_members': 'Can manage team members',
        'assign_team_goals': 'Can assign team goals',
        'view_team_performance': 'Can view team performance',
    }
    
    def has_permission(self, request, view):
        """Check team permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_team')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_team')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_team')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_team')
        elif view.action in ['add_member', 'remove_member']:
            return self.has_perm(request.user, 'manage_team_members')
        elif view.action == 'set_goals':
            return self.has_perm(request.user, 'assign_team_goals')
        elif view.action in ['performance', 'analytics']:
            return self.has_perm(request.user, 'view_team_performance')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check team object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Team management actions
        if view.action in ['add_member', 'remove_member', 'set_goals']:
            return self.can_manage_team(request.user, obj)
        
        # Team manager can access their team
        if hasattr(obj, 'manager') and obj.manager:
            if obj.manager.user == request.user:
                return True
        
        # Team members can view their team
        if self.is_team_member(request.user, obj):
            return True
        
        # HR and admin access
        return self.has_hr_admin_access(request.user)
    
    def can_manage_team(self, user, team):
        """Check if user can manage team."""
        # Team manager
        if hasattr(team, 'manager') and team.manager:
            if team.manager.user == user:
                return True
        
        # HR managers
        if self.has_hr_manager_role(user):
            return True
        
        # Department heads
        return self.is_department_head(user, team)
    
    def is_team_member(self, user, team):
        """Check if user is team member."""
        if hasattr(team, 'memberships'):
            return team.memberships.filter(
                user_profile__user=user,
                is_active=True
            ).exists()
        return False
    
    def has_hr_admin_access(self, user):
        """Check HR admin access."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['hr_manager', 'system_admin']
        return user.is_staff
    
    def has_hr_manager_role(self, user):
        """Check if user has HR manager role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role == 'hr_manager'
        return False
    
    def is_department_head(self, user, team):
        """Check if user is department head for team's department."""
        if not hasattr(user, 'crm_profile') or not hasattr(team, 'department'):
            return False
        
        user_department = user.crm_profile.department
        team_department = team.department
        
        return (user_department == team_department and 
                user.crm_profile.role in ['department_head', 'director'])