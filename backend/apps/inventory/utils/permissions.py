# apps/inventory/utils/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated
from django.contrib.auth.models import Permission
from apps.core.models import Tenant, User

class InventoryBasePermission(BasePermission):
    """Base permission class for inventory operations."""
    
    def has_permission(self, request, view):
        """Check if user has basic inventory access."""
        return (
            request.user.is_authenticated and 
            hasattr(request.user, 'tenant') and
            request.user.tenant.is_active
        )

class TenantIsolationPermission(InventoryBasePermission):
    """Ensures complete tenant isolation."""
    
    def has_object_permission(self, request, view, obj):
        """Check if object belongs to user's tenant."""
        return (
            hasattr(obj, 'tenant') and 
            obj.tenant == request.user.tenant
        )

class InventoryPermissionMixin:
    """Mixin providing inventory-specific permission methods."""
    
    def check_inventory_permission(self, permission_code):
        """Check if user has specific inventory permission."""
        return self.request.user.has_perm(f'inventory.{permission_code}')
    
    def check_warehouse_access(self, warehouse):
        """Check if user has access to specific warehouse."""
        if not hasattr(self.request.user, 'warehouse_access'):
            return True  # Super admin access
        return warehouse in self.request.user.warehouse_access.all()
    
    def check_value_approval_limit(self, amount):
        """Check if user can approve transactions of given amount."""
        user_limit = getattr(self.request.user, 'approval_limit', None)
        return user_limit is None or amount <= user_limit

class StockManagementPermission(InventoryBasePermission):
    """Permissions for stock management operations."""
    
    permission_map = {
        'GET': 'view_stockitem',
        'POST': 'add_stockitem',
        'PUT': 'change_stockitem',
        'PATCH': 'change_stockitem',
        'DELETE': 'delete_stockitem'
    }
    
    adjustment_permissions = {
        'adjust_stock': 'can_adjust_stock',
        'bulk_adjust': 'can_bulk_adjust_stock',
        'write_off': 'can_write_off_stock'
    }
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check basic CRUD permissions
        if request.method in self.permission_map:
            return request.user.has_perm(
                f'inventory.{self.permission_map[request.method]}'
            )
        
        # Check action-specific permissions
        if hasattr(view, 'action') and view.action in self.adjustment_permissions:
            return request.user.has_perm(
                f'inventory.{self.adjustment_permissions[view.action]}'
            )
        
        return True

class PurchasingPermission(InventoryBasePermission):
    """Permissions for purchasing operations."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action_permissions = {
            'create': 'add_purchaseorder',
            'approve': 'can_approve_purchase_orders',
            'reject': 'can_approve_purchase_orders',
            'cancel': 'can_cancel_purchase_orders'
        }
        
        if hasattr(view, 'action') and view.action in action_permissions:
            return request.user.has_perm(
                f'inventory.{action_permissions[view.action]}'
            )
        
        return True
    
    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Additional checks for PO approval based on amount
        if view.action == 'approve':
            return self.check_approval_authority(request.user, obj)
        
        return True
    
    def check_approval_authority(self, user, purchase_order):
        """Check if user can approve this specific PO."""
        user_limit = getattr(user, 'po_approval_limit', None)
        if user_limit is None:
            return True  # No limit (super admin)
        return purchase_order.total_amount <= user_limit

class ReportingPermission(InventoryBasePermission):
    """Permissions for reporting and analytics."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check basic reporting access
        if not request.user.has_perm('inventory.view_reports'):
            return False
        
        # Check specific report permissions
        sensitive_actions = [
            'generate_valuation_report',
            'generate_supplier_performance',
            'export_data'
        ]
        
        if (hasattr(view, 'action') and 
            view.action in sensitive_actions):
            return request.user.has_perm('inventory.view_sensitive_reports')
        
        return True

class AlertManagementPermission(InventoryBasePermission):
    """Permissions for alert management."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action_permissions = {
            'acknowledge': 'can_acknowledge_alerts',
            'resolve': 'can_resolve_alerts',
            'dismiss': 'can_dismiss_alerts',
            'bulk_action': 'can_bulk_manage_alerts'
        }
        
        if hasattr(view, 'action') and view.action in action_permissions:
            return request.user.has_perm(
                f'inventory.{action_permissions[view.action]}'
            )
        
        return True

class WarehouseAccessPermission(InventoryBasePermission):
    """Permissions based on warehouse access rights."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check if user has warehouse restrictions
        if hasattr(request.user, 'warehouse_restrictions'):
            # Filter operations based on accessible warehouses
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check warehouse access for objects with warehouse association
        if hasattr(obj, 'warehouse'):
            return self.check_warehouse_access(request.user, obj.warehouse)
        
        return True
    
    def check_warehouse_access(self, user, warehouse):
        """Check if user has access to specific warehouse."""
        if not hasattr(user, 'accessible_warehouses'):
            return True  # No restrictions
        
        return warehouse in user.accessible_warehouses.all()