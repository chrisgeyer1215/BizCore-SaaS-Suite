# ============================================================================
# backend/apps/crm/permissions/role_based.py - Role-Based Access Control
# ============================================================================

from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

from .base import TenantPermission

logger = logging.getLogger(__name__)
User = get_user_model()


class RoleBasedPermission(TenantPermission):
    """
    Advanced Role-Based Access Control (RBAC) with hierarchical roles
    """
    
    # Role definitions with permissions and hierarchy
    ROLE_DEFINITIONS = {
        'SYSTEM_ADMIN': {
            'level': 100,
            'permissions': ['*'],  # All permissions
            'description': 'System administrator with full access',
            'inherits_from': []
        },
        'TENANT_ADMIN': {
            'level': 90,
            'permissions': [
                'tenant.manage_users',
                'tenant.manage_settings',
                'tenant.view_analytics',
                'tenant.export_data',
                'crm.*'  # All CRM permissions
            ],
            'description': 'Tenant administrator',
            'inherits_from': []
        },
        'SALES_MANAGER': {
            'level': 80,
            'permissions': [
                'lead.*',
                'account.*',
                'opportunity.*',
                'activity.*',
                'territory.view',
                'territory.assign',
                'team.manage',
                'analytics.view_sales'
            ],
            'description': 'Sales team manager',
            'inherits_from': ['SALES_REP']
        },
        'SALES_REP': {
            'level': 60,
            'permissions': [
                'lead.view_own',
                'lead.change_own',
                'lead.add',
                'account.view_assigned',
                'account.change_assigned',
                'opportunity.view_own',
                'opportunity.change_own',
                'opportunity.add',
                'activity.view_own',
                'activity.change_own',
                'activity.add'
            ],
            'description': 'Sales representative',
            'inherits_from': []
        },
        'MARKETING_MANAGER': {
            'level': 75,
            'permissions': [
                'campaign.*',
                'lead.view',
                'lead.assign',
                'analytics.view_marketing',
                'document.manage_marketing'
            ],
            'description': 'Marketing team manager',
            'inherits_from': ['MARKETING_USER']
        },
        'MARKETING_USER': {
            'level': 55,
            'permissions': [
                'campaign.view',
                'campaign.add',
                'campaign.change_own',
                'lead.view',
                'document.view_marketing'
            ],
            'description': 'Marketing team member',
            'inherits_from': []
        },
        'CUSTOMER_SUCCESS': {
            'level': 65,
            'permissions': [
                'account.view',
                'account.change',
                'ticket.*',
                'activity.view',
                'activity.add',
                'document.view_customer'
            ],
            'description': 'Customer success representative',
            'inherits_from': []
        },
        'ANALYST': {
            'level': 50,
            'permissions': [
                'analytics.view',
                'report.create',
                'report.view',
                'dashboard.view',
                'lead.view_analytics',
                'opportunity.view_analytics'
            ],
            'description': 'Business analyst',
            'inherits_from': []
        },
        'VIEWER': {
            'level': 10,
            'permissions': [
                'lead.view_team',
                'account.view_team',
                'opportunity.view_team',
                'activity.view_team'
            ],
            'description': 'Read-only access to team data',
            'inherits_from': []
        }
    }
    
    def _check_core_permission(self, request, view) -> bool:
        """Enhanced role-based permission checking"""
        try:
            # Parent tenant check
            if not super()._check_core_permission(request, view):
                return False
            
            # Get user roles
            user_roles = self._get_user_roles(request.user, request.tenant)
            
            if not user_roles:
                return False
            
            # Get required permission for this view/action
            required_permission = self._get_required_permission(view, request.method)
            
            # Check if any user role has the required permission
            for role in user_roles:
                if self._role_has_permission(role, required_permission):
                    # Store user's effective permissions in request
                    request.user_permissions = self._get_effective_permissions(user_roles)
                    request.user_roles = user_roles
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Role-based permission check failed: {e}")
            return False
    
    def _get_user_roles(self, user: User, tenant) -> List[str]:
        """Get all roles for user in tenant context"""
        try:
            roles = []
            
            # Get roles from membership
            if hasattr(user, 'memberships'):
                membership = user.memberships.filter(
                    tenant=tenant,
                    is_active=True
                ).first()
                
                if membership and membership.role:
                    roles.append(membership.role)
            
            # Get roles from Django groups (tenant-specific)
            user_groups = user.groups.filter(
                name__startswith=f'tenant_{tenant.id}_'
            )
            
            for group in user_groups:
                # Extract role from group name: tenant_{id}_ROLE_NAME
                role_name = group.name.split('_', 2)[-1]
                if role_name in self.ROLE_DEFINITIONS:
                    roles.append(role_name)
            
            return list(set(roles))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Getting user roles failed: {e}")
            return []
    
    def _role_has_permission(self, role: str, permission: str) -> bool:
        """Check if role has specific permission"""
        try:
            role_def = self.ROLE_DEFINITIONS.get(role)
            if not role_def:
                return False
            
            role_permissions = role_def['permissions']
            
            # Check for wildcard permissions
            if '*' in role_permissions:
                return True
            
            # Check for exact match
            if permission in role_permissions:
                return True
            
            # Check for wildcard pattern match
            for role_perm in role_permissions:
                if role_perm.endswith('*'):
                    pattern = role_perm[:-1]  # Remove asterisk
                    if permission.startswith(pattern):
                        return True
            
            # Check inherited permissions
            for inherited_role in role_def.get('inherits_from', []):
                if self._role_has_permission(inherited_role, permission):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Role permission check failed: {e}")
            return False
    
    def _get_required_permission(self, view, method: str) -> str:
        """Determine required permission from view and method"""
        try:
            # Get model name from view
            model_name = getattr(view, 'queryset', None)
            if model_name:
                model_name = model_name.model.__name__.lower()
            else:
                model_name = getattr(view, 'model', 'unknown').__name__.lower()
            
            # Map HTTP methods to actions
            action_mapping = {
                'GET': 'view',
                'POST': 'add',
                'PUT': 'change',
                'PATCH': 'change',
                'DELETE': 'delete'
            }
            
            action = action_mapping.get(method, 'view')
            
            # Check for specific view actions (DRF ViewSet actions)
            if hasattr(view, 'action'):
                if view.action == 'list':
                    action = 'view'
                elif view.action == 'retrieve':
                    action = 'view'
                elif view.action == 'create':
                    action = 'add'
                elif view.action in ['update', 'partial_update']:
                    action = 'change'
                elif view.action == 'destroy':
                    action = 'delete'
                else:
                    action = view.action
            
            return f"{model_name}.{action}"
            
        except Exception as e:
            logger.error(f"Getting required permission failed: {e}")
            return "unknown.unknown"
    
    def _get_effective_permissions(self, roles: List[str]) -> List[str]:
        """Get all effective permissions for user roles"""
        try:
            effective_permissions = set()
            
            for role in roles:
                role_def = self.ROLE_DEFINITIONS.get(role, {})
                role_permissions = role_def.get('permissions', [])
                
                effective_permissions.update(role_permissions)
                
                # Add inherited permissions
                for inherited_role in role_def.get('inherits_from', []):
                    inherited_permissions = self._get_effective_permissions([inherited_role])
                    effective_permissions.update(inherited_permissions)
            
            return list(effective_permissions)
            
        except Exception as e:
            logger.error(f"Getting effective permissions failed: {e}")
            return []


class DynamicRolePermission(RoleBasedPermission):
    """
    Dynamic role-based permissions with runtime role assignment
    """
    
    def __init__(self):
        super().__init__()
        self.dynamic_roles_cache = {}
    
    def _get_user_roles(self, user: User, tenant) -> List[str]:
        """Enhanced user role retrieval with dynamic roles"""
        try:
            # Get base roles
            roles = super()._get_user_roles(user, tenant)
            
            # Add dynamic roles based on user attributes
            dynamic_roles = self._calculate_dynamic_roles(user, tenant)
            roles.extend(dynamic_roles)
            
            # Add context-based roles
            context_roles = self._get_context_based_roles(user, tenant)
            roles.extend(context_roles)
            
            return list(set(roles))
            
        except Exception as e:
            logger.error(f"Dynamic role calculation failed: {e}")
            return super()._get_user_roles(user, tenant)
    
    def _calculate_dynamic_roles(self, user: User, tenant) -> List[str]:
        """Calculate dynamic roles based on user performance and context"""
        try:
            dynamic_roles = []
            
            # Performance-based role elevation
            user_performance = self._get_user_performance_score(user, tenant)
            
            if user_performance >= 90:
                dynamic_roles.append('HIGH_PERFORMER')
            elif user_performance >= 75:
                dynamic_roles.append('GOOD_PERFORMER')
            
            # Experience-based roles
            user_tenure_days = self._get_user_tenure_days(user, tenant)
            
            if user_tenure_days >= 365:
                dynamic_roles.append('SENIOR_USER')
            elif user_tenure_days >= 180:
                dynamic_roles.append('EXPERIENCED_USER')
            else:
                dynamic_roles.append('NEW_USER')
            
            # Activity-based roles
            recent_activity_score = self._get_recent_activity_score(user, tenant)
            
            if recent_activity_score >= 80:
                dynamic_roles.append('ACTIVE_USER')
            elif recent_activity_score <= 20:
                dynamic_roles.append('INACTIVE_USER')
            
            return dynamic_roles
            
        except Exception as e:
            logger.error(f"Dynamic role calculation failed: {e}")
            return []
    
    def _get_context_based_roles(self, user: User, tenant) -> List[str]:
        """Get roles based on current context and time"""
        try:
            context_roles = []
            current_time = timezone.now()
            
            # Time-based roles
            if 9 <= current_time.hour <= 17:  # Business hours
                context_roles.append('BUSINESS_HOURS_USER')
            else:
                context_roles.append('AFTER_HOURS_USER')
            
            # Weekend context
            if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                context_roles.append('WEEKEND_USER')
            
            # Emergency context
            if self._is_emergency_context(user, tenant):
                context_roles.append('EMERGENCY_ACCESS')
            
            return context_roles
            
        except Exception as e:
            logger.error(f"Context-based role calculation failed: {e}")
            return []
    
    def _get_user_performance_score(self, user: User, tenant) -> float:
        """Calculate user performance score"""
        try:
            # This would integrate with your analytics service
            # Placeholder implementation
            return 80.0
            
        except Exception as e:
            logger.error(f"Performance score calculation failed: {e}")
            return 50.0
    
    def _get_user_tenure_days(self, user: User, tenant) -> int:
        """Get user tenure in tenant"""
        try:
            if hasattr(user, 'memberships'):
                membership = user.memberships.filter(tenant=tenant).first()
                if membership:
                    return (timezone.now().date() - membership.joined_date).days
            
            return 0
            
        except Exception as e:
            logger.error(f"Tenure calculation failed: {e}")
            return 0
    
    def _get_recent_activity_score(self, user: User, tenant) -> float:
        """Calculate recent activity score"""
        try:
            # This would analyze user's recent activities
            # Placeholder implementation
            return 70.0
            
        except Exception as e:
            logger.error(f"Activity score calculation failed: {e}")
            return 50.0
    
    def _is_emergency_context(self, user: User, tenant) -> bool:
        """Determine if this is an emergency access context"""
        try:
            # Check for emergency flags in user profile or tenant settings
            # Placeholder implementation
            return False
            
        except Exception as e:
            logger.error(f"Emergency context check failed: {e}")
            return False