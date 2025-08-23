# backend/apps/crm/permissions/product.py
from rest_framework import permissions
from decimal import Decimal
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Product, ProductCategory, PricingModel, ProductBundle

class ProductPermission(CRMPermission):
    """Permission class for Product model."""
    
    MODEL_PERMS = {
        'view_product': 'Can view products',
        'add_product': 'Can add products',
        'change_product': 'Can change products',
        'delete_product': 'Can delete products',
        'manage_pricing': 'Can manage product pricing',
        'approve_pricing': 'Can approve pricing changes',
        'view_cost_information': 'Can view product costs',
        'manage_product_lifecycle': 'Can manage product lifecycle',
    }
    
    # Price change approval thresholds
    PRICING_APPROVAL_THRESHOLDS = {
        'product_manager': Decimal('10.0'),    # 10% price change
        'sales_manager': Decimal('20.0'),      # 20% price change  
        'sales_director': Decimal('35.0'),     # 35% price change
        'vp_sales': Decimal('50.0'),          # 50% price change
    }
    
    def has_permission(self, request, view):
        """Check product permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_product')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_product')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_product')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_product')
        elif view.action in ['update_pricing', 'bulk_pricing']:
            return self.has_perm(request.user, 'manage_pricing')
        elif view.action in ['lifecycle_change', 'discontinue']:
            return self.has_perm(request.user, 'manage_product_lifecycle')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check product object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Pricing changes require approval
        if view.action in ['update_pricing', 'bulk_pricing']:
            return self.can_change_pricing(request.user, obj, request.data)
        
        # Cost information access
        if self.involves_cost_data(request.data):
            if not self.has_perm(request.user, 'view_cost_information'):
                return False
        
        # Lifecycle management
        if view.action in ['lifecycle_change', 'discontinue']:
            return self.can_manage_lifecycle(request.user, obj)
        
        # Product management access
        return self.has_product_access(request.user, obj)
    
    def can_change_pricing(self, user, product, request_data):
        """Check if user can change pricing."""
        if not self.has_perm(user, 'manage_pricing'):
            return False
        
        # Calculate price change percentage
        new_price = request_data.get('price')
        if not new_price:
            return True  # No price change
        
        current_price = getattr(product, 'price', 0) or Decimal('0')
        if current_price == 0:
            return True  # New product pricing
        
        price_change_percent = abs(
            (Decimal(str(new_price)) - current_price) / current_price * 100
        )
        
        # Check approval threshold
        user_role = self.get_user_role(user)
        max_change = self.PRICING_APPROVAL_THRESHOLDS.get(user_role, Decimal('0'))
        
        if price_change_percent <= max_change:
            return True
        
        # Check if user has approval permission for larger changes
        return self.has_perm(user, 'approve_pricing')
    
    def involves_cost_data(self, request_data):
        """Check if request involves cost data."""
        cost_fields = ['cost', 'cost_price', 'margin', 'markup']
        return any(field in request_data for field in cost_fields)
    
    def can_manage_lifecycle(self, user, product):
        """Check if user can manage product lifecycle."""
        if not self.has_perm(user, 'manage_product_lifecycle'):
            return False
        
        # Product managers and above can manage lifecycle
        user_role = self.get_user_role(user)
        return user_role in [
            'product_manager', 'sales_manager', 'sales_director', 'vp_sales'
        ]
    
    def has_product_access(self, user, product):
        """Check general product access."""
        # Check product line assignment
        if hasattr(user, 'crm_profile') and hasattr(product, 'product_line'):
            user_product_lines = getattr(user.crm_profile, 'product_lines', None)
            if user_product_lines:
                return product.product_line in user_product_lines.all()
        
        # Check department access
        if hasattr(user, 'crm_profile') and hasattr(product, 'department'):
            user_department = user.crm_profile.department
            return user_department == product.department
        
        # Default to allowing access for valid CRM users
        return hasattr(user, 'crm_profile')
    
    def get_user_role(self, user):
        """Get user's role for permission checking."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role
        return 'sales_rep'  # Default role

class ProductCategoryPermission(CRMPermission):
    """Permission class for ProductCategory model."""
    
    MODEL_PERMS = {
        'view_productcategory': 'Can view product categories',
        'add_productcategory': 'Can add product categories',
        'change_productcategory': 'Can change product categories',
        'delete_productcategory': 'Can delete product categories',
    }
    
    def has_permission(self, request, view):
        """Product category permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_productcategory')
        
        # Modification requires product management role
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (self.has_product_manager_role(request.user) or 
                   request.user.is_staff or
                   self.has_perm(request.user, f'{view.action}_productcategory'))
        
        return True
    
    def has_product_manager_role(self, user):
        """Check if user has product manager role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['product_manager', 'sales_director']
        return False

class PricingModelPermission(CRMPermission):
    """Permission class for PricingModel model."""
    
    MODEL_PERMS = {
        'view_pricingmodel': 'Can view pricing models',
        'add_pricingmodel': 'Can add pricing models',
        'change_pricingmodel': 'Can change pricing models',
        'delete_pricingmodel': 'Can delete pricing models',
    }
    
    def has_permission(self, request, view):
        """Pricing model permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for sales and product teams
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_pricingmodel')
        
        # Modification requires senior roles
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (self.has_pricing_admin_role(request.user) or 
                   request.user.is_staff or
                   self.has_perm(request.user, f'{view.action}_pricingmodel'))
        
        return True
    
    def has_pricing_admin_role(self, user):
        """Check if user has pricing admin role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in [
                'pricing_manager', 'product_manager', 'sales_director', 'vp_sales'
            ]
        return False

class ProductBundlePermission(CRMPermission):
    """Permission class for ProductBundle model."""
    
    MODEL_PERMS = {
        'view_productbundle': 'Can view product bundles',
        'add_productbundle': 'Can add product bundles',
        'change_productbundle': 'Can change product bundles',
        'delete_productbundle': 'Can delete product bundles',
        'configure_bundle_pricing': 'Can configure bundle pricing',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check product bundle permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check access to all products in bundle
        if hasattr(obj, 'products'):
            product_permission = ProductPermission()
            for product in obj.products.all():
                if not product_permission.has_object_permission(
                    request, view, product
                ):
                    return False
        
        return True