# apps/core/permissions.py

from rest_framework import permissions


class TenantPermission(permissions.BasePermission):
    """
    Permission class for tenant-aware operations.
    In a real implementation, this would check if the user has access to the requested tenant.
    """
    
    def has_permission(self, request, view):
        # For now, just check if user is authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # In a real implementation, check if obj belongs to user's tenant
        # For now, just allow if user is authenticated
        return request.user and request.user.is_authenticated


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission class for tenant admin operations.
    """
    
    def has_permission(self, request, view):
        # For now, just check if user is staff
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsTenantOwner(permissions.BasePermission):
    """
    Permission class for tenant owner operations.
    """
    
    def has_permission(self, request, view):
        # For now, just check if user is authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # In a real implementation, check if user is the tenant owner
        # For now, just allow if user is authenticated
        return request.user and request.user.is_authenticated