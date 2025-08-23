# backend/apps/crm/permissions/system.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission

class SystemAdminPermission(CRMPermission):
    """Permission class for System Administration."""
    
    MODEL_PERMS = {
        'view_system_settings': 'Can view system settings',
        'change_system_settings': 'Can change system settings',
        'manage_users': 'Can manage users',
        'manage_tenants': 'Can manage tenants',
        'access_system_logs': 'Can access system logs',
        'manage_backups': 'Can manage backups',
        'system_maintenance': 'Can perform system maintenance',
        'security_management': 'Can manage security settings',
    }
    
    def has_permission(self, request, view):
        """System admin permissions require highest access level."""
        if not super().has_permission(request, view):
            return False
        
        # System administration requires staff access
        if not request.user.is_staff:
            return False
        
        if view.action in ['system_settings', 'view_settings']:
            return self.has_perm(request.user, 'view_system_settings')
        elif view.action in ['update_settings', 'change_settings']:
            return self.has_perm(request.user, 'change_system_settings')
        elif view.action in ['user_management', 'manage_users']:
            return self.has_perm(request.user, 'manage_users')
        elif view.action in ['tenant_management', 'manage_tenants']:
            return self.has_perm(request.user, 'manage_tenants')
        elif view.action in ['system_logs', 'access_logs']:
            return self.has_perm(request.user, 'access_system_logs')
        elif view.action in ['backup_management', 'create_backup']:
            return self.has_perm(request.user, 'manage_backups')
        elif view.action in ['maintenance_mode', 'system_health']:
            return self.has_perm(request.user, 'system_maintenance')
        elif view.action in ['security_settings', 'manage_security']:
            return self.has_perm(request.user, 'security_management')
        
        return self.has_system_admin_role(request.user)
    
    def has_system_admin_role(self, user):
        """Check if user has system admin role."""
        if user.is_superuser:
            return True
        
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role == 'system_admin'
        
        return False

class AuditPermission(CRMPermission):
    """Permission class for Audit functionality."""
    
    MODEL_PERMS = {
        'view_audit_logs': 'Can view audit logs',
        'export_audit_logs': 'Can export audit logs',
        'manage_audit_settings': 'Can manage audit settings',
        'access_security_logs': 'Can access security logs',
        'view_data_access_logs': 'Can view data access logs',
    }
    
    def has_permission(self, request, view):
        """Audit permissions for compliance and security."""
        if not super().has_permission(request, view):
            return False
        
        if view.action in ['audit_logs', 'list']:
            return self.has_perm(request.user, 'view_audit_logs')
        elif view.action == 'export':
            return self.has_perm(request.user, 'export_audit_logs')
        elif view.action in ['audit_settings', 'configure']:
            return self.has_perm(request.user, 'manage_audit_settings')
        elif view.action == 'security_logs':
            return self.has_perm(request.user, 'access_security_logs')
        elif view.action == 'data_access_logs':
            return self.has_perm(request.user, 'view_data_access_logs')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check audit object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Audit logs are read-only
        if view.action in ['update', 'partial_update', 'destroy']:
            return False
        
        # Check if user can view audit logs for specific records
        if hasattr(obj, 'object_type') and hasattr(obj, 'object_id'):
            return self.can_audit_object_type(request.user, obj.object_type)
        
        return True
    
    def can_audit_object_type(self, user, object_type):
        """Check if user can audit specific object type."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_role = user.crm_profile.role
        
        # Role-based audit access
        audit_access = {
            'account': ['sales_manager', 'sales_director'],
            'opportunity': ['sales_manager', 'sales_director'],
            'ticket': ['support_manager'],
            'user': ['hr_manager', 'system_admin'],
            'financial': ['finance_manager', 'controller'],
        }
        
        allowed_roles = audit_access.get(object_type, ['system_admin'])
        return user_role in allowed_roles or user.is_staff