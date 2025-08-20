# apps/inventory/api/v1/permissions.py

from rest_framework.permissions import BasePermission
from apps.inventory.utils.permissions import InventoryBasePermission

class DynamicInventoryPermission(InventoryBasePermission):
    """Dynamic permission based on object type and action."""
    
    permission_mapping = {
        # Format: 'model.action': 'required_permission'
        'product.create': 'inventory.add_product',
        'product.update': 'inventory.change_product',
        'product.delete': 'inventory.delete_product',
        'stockitem.adjust': 'inventory.can_adjust_stock',
        'purchaseorder.approve': 'inventory.can_approve_purchase_orders',
        'transfer.approve': 'inventory.can_approve_transfers',
        'adjustment.approve': 'inventory.can_approve_adjustments',
    }
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Build permission key
        model_name = getattr(view, 'queryset', None)
        if model_name:
            model_name = model_name.model._meta.model_name
        else:
            model_name = view.__class__.__name__.lower().replace('viewset', '')
        
        action = getattr(view, 'action', request.method.lower())
        permission_key = f'{model_name}.{action}'
        
        # Check if specific permission is required
        if permission_key in self.permission_mapping:
            required_permission = self.permission_mapping[permission_key]
            return request.user.has_perm(required_permission)
        
        return True

class ConditionalPermission(InventoryBasePermission):
    """Permission that depends on business conditions."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Example: Restrict certain operations during month-end close
        if self.is_month_end_close_period():
            restricted_actions = ['adjust_stock', 'create_adjustment']
            if hasattr(view, 'action') and view.action in restricted_actions:
                return request.user.has_perm('inventory.can_operate_during_close')
        
        # Example: Restrict high-value operations outside business hours
        if self.is_outside_business_hours():
            high_value_actions = ['approve_large_po', 'bulk_adjust']
            if hasattr(view, 'action') and view.action in high_value_actions:
                return request.user.has_perm('inventory.can_operate_after_hours')
        
        return True
    
    def is_month_end_close_period(self):
        """Check if we're in month-end close period."""
        # Implementation would check tenant settings
        return False
    
    def is_outside_business_hours(self):
        """Check if current time is outside business hours."""
        # Implementation would check tenant settings and timezone
        return False

class FieldLevelPermission(InventoryBasePermission):
    """Permission for specific fields within objects."""
    
    sensitive_fields = {
        'product': ['cost_price', 'profit_margin'],
        'stockitem': ['unit_cost', 'total_value'],
        'purchaseorder': ['total_amount', 'discount_amount'],
    }
    
    def has_field_permission(self, request, view, obj, field_name):
        """Check if user can access specific field."""
        model_name = obj._meta.model_name
        
        if (model_name in self.sensitive_fields and 
            field_name in self.sensitive_fields[model_name]):
            return request.user.has_perm('inventory.view_financial_data')
        
        return True

class APIRateLimitPermission(BasePermission):
    """Permission that implements API rate limiting."""
    
    rate_limits = {
        'bulk_operations': {'calls': 10, 'period': 3600},  # 10 per hour
        'export_operations': {'calls': 5, 'period': 3600},  # 5 per hour
        'report_generation': {'calls': 20, 'period': 3600},  # 20 per hour
    }
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check rate limits for specific actions
        if hasattr(view, 'action'):
            for limit_type, action_patterns in self.get_action_patterns().items():
                if any(pattern in view.action for pattern in action_patterns):
                    return self.check_rate_limit(request.user, limit_type)
        
        return True
    
    def get_action_patterns(self):
        return {
            'bulk_operations': ['bulk_', 'mass_', 'batch_'],
            'export_operations': ['export', 'download'],
            'report_generation': ['generate_', 'report']
        }
    
    def check_rate_limit(self, user, limit_type):
        """Check if user has exceeded rate limit."""
        # Implementation would use cache or database to track API calls
        return True  # Placeholder