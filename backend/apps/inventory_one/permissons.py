"""
Custom permissions for inventory management
"""

from rest_framework.permissions import BasePermission
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class InventoryPermission(BasePermission):
    """
    Base inventory permission class
    """
    
    def has_permission(self, request, view):
        """Check if user has basic inventory access"""
        if not request.user.is_authenticated:
            return False
        
        # Superusers have all permissions
        if request.user.is_superuser:
            return True
        
        # Check tenant membership
        if not hasattr(request, 'tenant') or not request.tenant:
            return False
        
        # Check if user is member of the tenant
        from apps.auth.models import Membership
        try:
            membership = Membership.objects.get(
                user=request.user,
                tenant=request.tenant,
                is_active=True
            )
            return True
        except Membership.DoesNotExist:
            return False


class ProductPermission(InventoryPermission):
    """
    Product-specific permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = view.action if hasattr(view, 'action') else None
        
        # Read permissions
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.has_read_permission(request)
        
        # Write permissions
        elif request.method in ['POST', 'PUT', 'PATCH']:
            if action in ['create', 'update', 'partial_update']:
                return self.has_write_permission(request)
            elif action == 'adjust_stock':
                return self.has_stock_adjustment_permission(request)
        
        # Delete permissions
        elif request.method == 'DELETE':
            return self.has_delete_permission(request)
        
        return False
    
    def has_read_permission(self, request):
        """Check read permission for products"""
        return request.user.has_perm('inventory.view_product')
    
    def has_write_permission(self, request):
        """Check write permission for products"""
        return request.user.has_perm('inventory.change_product')
    
    def has_delete_permission(self, request):
        """Check delete permission for products"""
        return request.user.has_perm('inventory.delete_product')
    
    def has_stock_adjustment_permission(self, request):
        """Check stock adjustment permission"""
        return (request.user.has_perm('inventory.change_stockitem') and
                request.user.has_perm('inventory.add_stockmovement'))


class WarehousePermission(InventoryPermission):
    """
    Warehouse-specific permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check if user has access to specific warehouses
        if hasattr(view, 'get_object') and request.method != 'POST':
            try:
                warehouse = view.get_object()
                return self.has_warehouse_access(request, warehouse)
            except:
                pass
        
        # General warehouse permissions
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_warehouse')
        elif request.method == 'POST':
            return request.user.has_perm('inventory.add_warehouse')
        elif request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('inventory.change_warehouse')
        elif request.method == 'DELETE':
            return request.user.has_perm('inventory.delete_warehouse')
        
        return False
    
    def has_warehouse_access(self, request, warehouse):
        """Check if user has access to specific warehouse"""
        # Warehouse managers have full access to their warehouses
        if warehouse.manager == request.user:
            return True
        
        # Check user's warehouse assignments (you might have a separate model for this)
        # For now, we'll allow all authenticated users with general warehouse permission
        return request.user.has_perm('inventory.view_warehouse')


class PurchaseOrderPermission(InventoryPermission):
    """
    Purchase order specific permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = view.action if hasattr(view, 'action') else None
        
        # Special actions require specific permissions
        if action == 'approve':
            return self.has_approval_permission(request)
        elif action in ['send_to_supplier', 'cancel']:
            return self.has_management_permission(request)
        
        # Standard CRUD permissions
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_purchaseorder')
        elif request.method == 'POST':
            return request.user.has_perm('inventory.add_purchaseorder')
        elif request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('inventory.change_purchaseorder')
        elif request.method == 'DELETE':
            return request.user.has_perm('inventory.delete_purchaseorder')
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for purchase orders"""
        # Buyers can access their own purchase orders
        if obj.buyer == request.user:
            return True
        
        # Approved users can view approved purchase orders
        if obj.approved_by == request.user and request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Check general permissions
        return super().has_permission(request, view)
    
    def has_approval_permission(self, request):
        """Check if user can approve purchase orders"""
        from apps.auth.models import Membership
        
        try:
            membership = Membership.objects.get(
                user=request.user,
                tenant=request.tenant,
                is_active=True
            )
            # Only owners and admins can approve
            return membership.role in ['OWNER', 'ADMIN']
        except Membership.DoesNotExist:
            return False
    
    def has_management_permission(self, request):
        """Check if user can manage purchase orders (send/cancel)"""
        return (request.user.has_perm('inventory.change_purchaseorder') and
                self.has_approval_permission(request))


class StockMovementPermission(InventoryPermission):
    """
    Stock movement permissions - read-only for most users
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Most stock movements are system-generated, so mainly read access
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_stockmovement')
        
        # Only specific roles can create manual stock movements
        elif request.method == 'POST':
            return (request.user.has_perm('inventory.add_stockmovement') and
                    self.has_manual_movement_permission(request))
        
        # No direct updates/deletes allowed
        return False
    
    def has_manual_movement_permission(self, request):
        """Check if user can create manual stock movements"""
        from apps.auth.models import Membership
        
        try:
            membership = Membership.objects.get(
                user=request.user,
                tenant=request.tenant,
                is_active=True
            )
            # Only owners, admins, and warehouse managers
            return membership.role in ['OWNER', 'ADMIN'] or request.user.has_perm('inventory.add_stockadjustment')
        except Membership.DoesNotExist:
            return False


class AlertPermission(InventoryPermission):
    """
    Alert management permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = view.action if hasattr(view, 'action') else None
        
        # Special actions
        if action in ['acknowledge', 'resolve', 'snooze']:
            return self.has_alert_management_permission(request)
        
        # Read access for all authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_inventoryalert')
        
        # No direct creation/deletion of alerts (system-generated)
        return False
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for alerts"""
        # Users can manage alerts assigned to them
        if obj.assigned_to == request.user:
            return True
        
        # Check general permissions
        return super().has_permission(request, view)
    
    def has_alert_management_permission(self, request):
        """Check if user can manage alerts"""
        return request.user.has_perm('inventory.change_inventoryalert')


class ReportPermission(InventoryPermission):
    """
    Report access permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Read access for reports
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_inventoryreport')
        
        # Report generation
        elif request.method == 'POST':
            return request.user.has_perm('inventory.add_inventoryreport')
        
        return False


# ============================================================================
# PERMISSION GROUPS AND SETUP
# ============================================================================

def create_inventory_permissions():
    """
    Create custom inventory permissions
    """
    from django.contrib.auth.models import Group, Permission
    
    # Get content types
    product_ct = ContentType.objects.get_for_model(Product)
    warehouse_ct = ContentType.objects.get_for_model(Warehouse)
    
    # Create custom permissions
    custom_permissions = [
        # Stock management
        ('can_adjust_stock', 'Can adjust stock levels'),
        ('can_transfer_stock', 'Can transfer stock between warehouses'),
        ('can_reserve_stock', 'Can reserve stock'),
        
        # Purchase orders
        ('can_approve_purchase_orders', 'Can approve purchase orders'),
        ('can_send_purchase_orders', 'Can send purchase orders to suppliers'),
        
        # Reports
        ('can_generate_reports', 'Can generate inventory reports'),
        ('can_view_analytics', 'Can view inventory analytics'),
        
        # Alerts
        ('can_manage_alerts', 'Can manage inventory alerts'),
        
        # System
        ('can_configure_inventory', 'Can configure inventory settings'),
    ]
    
    created_permissions = []
    for codename, name in custom_permissions:
        permission, created = Permission.objects.get_or_create(
            codename=codename,
            content_type=product_ct,
            defaults={'name': name}
        )
        created_permissions.append(permission)
    
    # Create permission groups
    groups_permissions = {
        'Inventory Viewers': [
            'view_product', 'view_stockitem', 'view_warehouse', 'view_stockmovement',
            'view_purchaseorder', 'view_inventoryalert'
        ],
        'Inventory Clerks': [
            'view_product', 'change_product', 'view_stockitem', 'change_stockitem',
            'view_warehouse', 'view_stockmovement', 'can_adjust_stock', 'can_transfer_stock'
        ],
        'Inventory Managers': [
            'view_product', 'add_product', 'change_product', 'delete_product',
            'view_stockitem', 'change_stockitem', 'view_warehouse', 'change_warehouse',
            'view_purchaseorder', 'add_purchaseorder', 'change_purchaseorder',
            'can_adjust_stock', 'can_transfer_stock', 'can_reserve_stock',
            'can_generate_reports', 'can_view_analytics', 'can_manage_alerts'
        ],
        'Inventory Administrators': [
            # All permissions
        ] + [perm.codename for perm in created_permissions]
    }
    
    for group_name, permission_codenames in groups_permissions.items():
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            for codename in permission_codenames:
                try:
                    permission = Permission.objects.get(codename=codename)
                    group.permissions.add(permission)
                except Permission.DoesNotExist:
                    print(f"Permission {codename} not found")
    
    return created_permissions


class RoleBasedPermissionMixin:
    """
    Mixin to check role-based permissions
    """
    
    def check_role_permission(self, user, tenant, required_roles):
        """Check if user has required role in tenant"""
        from apps.auth.models import Membership
        
        try:
            membership = Membership.objects.get(
                user=user,
                tenant=tenant,
                is_active=True
            )
            return membership.role in required_roles
        except Membership.DoesNotExist:
            return False


class DepartmentPermission(InventoryPermission, RoleBasedPermissionMixin):
    """
    Department-level permissions
    """
    
    def has_object_permission(self, request, view, obj):
        # Department managers have full access to their departments
        if obj.manager == request.user:
            return True
        
        # Check if user has role-based access
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True  # All authenticated users can view
        else:
            return self.check_role_permission(
                request.user, 
                request.tenant, 
                ['OWNER', 'ADMIN']
            )


class SupplierPermission(InventoryPermission, RoleBasedPermissionMixin):
    """
    Supplier management permissions
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Viewing suppliers
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.has_perm('inventory.view_supplier')
        
        # Managing suppliers requires admin role
        else:
            return (request.user.has_perm('inventory.change_supplier') and
                    self.check_role_permission(request.user, request.tenant, ['OWNER', 'ADMIN']))
