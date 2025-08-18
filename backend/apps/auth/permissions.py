# apps/auth/permissions.py

from rest_framework import permissions
from .models import Membership
from apps.core.models import Tenant


class IsTenantMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the current tenant
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Get tenant from request (set by middleware)
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Check if user is a member of this tenant
        return Membership.objects.filter(
            user=request.user,
            tenant_id=tenant.id,
            is_active=True,
            status='active'
        ).exists()


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission to check if user is an admin of the current tenant
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Get tenant from request
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Check if user is admin/owner of this tenant
        return Membership.objects.filter(
            user=request.user,
            tenant_id=tenant.id,
            role__in=['admin', 'owner'],
            is_active=True,
            status='active'
        ).exists()


class IsTenantOwner(permissions.BasePermission):
    """
    Permission to check if user is the owner of the current tenant
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        return Membership.objects.filter(
            user=request.user,
            tenant_id=tenant.id,
            role='owner',
            is_active=True,
            status='active'
        ).exists()


class HasTenantPermission(permissions.BasePermission):
    """
    Permission to check if user has specific permission in current tenant
    """
    required_permission = None
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        try:
            membership = Membership.objects.get(
                user=request.user,
                tenant_id=tenant.id,
                is_active=True,
                status='active'
            )
            
            # Check if membership has the required permission
            permission = getattr(self, 'required_permission', None) or getattr(view, 'required_permission', None)
            if permission:
                return membership.has_permission(permission)
            
            return True
            
        except Membership.DoesNotExist:
            return False


# Permission classes for specific actions
class CanCreateUsers(HasTenantPermission):
    required_permission = 'create_user'


class CanEditUsers(HasTenantPermission):
    required_permission = 'edit_user'


class CanDeleteUsers(HasTenantPermission):
    required_permission = 'delete_user'


class CanViewReports(HasTenantPermission):
    required_permission = 'view_reports'


class CanManageSettings(HasTenantPermission):
    required_permission = 'manage_settings'