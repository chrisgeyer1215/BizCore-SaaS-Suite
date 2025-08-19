from rest_framework import permissions
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from apps.core.permissions import TenantPermissionMixin


class EcommercePermission(permissions.BasePermission):
    """Base permission for e-commerce operations"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has access to tenant
        if not hasattr(request, 'tenant'):
            return False
        
        return True


class ProductPermission(EcommercePermission):
    """Permissions for product management"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions require specific roles
        return request.user.has_perm('ecommerce.change_ecommerceproduct')
    
    def has_object_permission(self, request, view, obj):
        # Check tenant ownership
        if obj.tenant != request.tenant:
            return False
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user.has_perm('ecommerce.change_ecommerceproduct')


class OrderPermission(EcommercePermission):
    """Permissions for order management"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Customers can view their own orders
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Staff can manage orders
        return request.user.is_staff or request.user.has_perm('ecommerce.change_order')
    
    def has_object_permission(self, request, view, obj):
        if obj.tenant != request.tenant:
            return False
        
        # Customers can only view their own orders
        if not request.user.is_staff:
            return obj.customer and obj.customer.user == request.user
        
        return True


class CartPermission(EcommercePermission):
    """Permissions for cart operations"""
    
    def has_object_permission(self, request, view, obj):
        if obj.tenant != request.tenant:
            return False
        
        # Users can only access their own carts
        if obj.customer:
            return obj.customer.user == request.user
        
        # Guest carts are accessible via session
        return obj.session_key == request.session.session_key


class CouponPermission(EcommercePermission):
    """Permissions for coupon management"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Anyone can apply coupons (read-only)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Only staff can manage coupons
        return request.user.is_staff or request.user.has_perm('ecommerce.change_coupon')


class ReviewPermission(EcommercePermission):
    """Permissions for review management"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Read permissions for all
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Authenticated users can create reviews
        return True
    
    def has_object_permission(self, request, view, obj):
        if obj.tenant != request.tenant:
            return False
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Users can only modify their own reviews
        return obj.customer.user == request.user or request.user.is_staff


# Django mixins for class-based views
class EcommerceMixin(TenantPermissionMixin):
    """Mixin for e-commerce views"""
    pass


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Require staff access for e-commerce management"""
    
    def test_func(self):
        return self.request.user.is_staff


class ProductManagerMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Require product management permissions"""
    
    def test_func(self):
        return (self.request.user.is_staff or 
                self.request.user.has_perm('ecommerce.change_ecommerceproduct'))


class OrderManagerMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Require order management permissions"""
    
    def test_func(self):
        return (self.request.user.is_staff or 
                self.request.user.has_perm('ecommerce.change_order'))


class CustomerAccessMixin(LoginRequiredMixin):
    """Allow customers to access their own data"""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if self.request.user.is_staff:
            return queryset
        
        # Filter to customer's own data
        if hasattr(queryset.model, 'customer'):
            return queryset.filter(customer__user=self.request.user)
        
        return queryset.none()
