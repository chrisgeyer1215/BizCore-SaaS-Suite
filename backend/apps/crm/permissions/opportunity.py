# backend/apps/crm/permissions/opportunity.py
from rest_framework import permissions
from decimal import Decimal
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Opportunity, Pipeline

class OpportunityPermission(CRMPermission):
    """Permission class for Opportunity model."""
    
    MODEL_PERMS = {
        'view_opportunity': 'Can view opportunities',
        'add_opportunity': 'Can add opportunities', 
        'change_opportunity': 'Can change opportunities',
        'delete_opportunity': 'Can delete opportunities',
        'close_opportunity': 'Can close opportunities',
        'reopen_opportunity': 'Can reopen opportunities',
        'transfer_opportunity': 'Can transfer opportunities',
        'discount_opportunity': 'Can apply discounts',
        'forecast_opportunity': 'Can access forecasting',
    }
    
    # Discount approval thresholds
    DISCOUNT_APPROVAL_THRESHOLDS = {
        'sales_rep': Decimal('5.0'),      # 5% max discount
        'sales_manager': Decimal('15.0'),  # 15% max discount
        'sales_director': Decimal('25.0'), # 25% max discount
        'vp_sales': Decimal('50.0'),      # 50% max discount
    }
    
    def has_permission(self, request, view):
        """Check opportunity permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_opportunity')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_opportunity')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_opportunity')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_opportunity')
        elif view.action in ['close', 'close_won', 'close_lost']:
            return self.has_perm(request.user, 'close_opportunity')
        elif view.action == 'reopen':
            return self.has_perm(request.user, 'reopen_opportunity')
        elif view.action == 'transfer':
            return self.has_perm(request.user, 'transfer_opportunity')
        elif view.action == 'apply_discount':
            return self.has_perm(request.user, 'discount_opportunity')
        elif view.action in ['forecast', 'pipeline_forecast']:
            return self.has_perm(request.user, 'forecast_opportunity')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check opportunity object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Special handling for discounts
        if view.action == 'apply_discount':
            return self.can_apply_discount(request.user, obj, request.data)
        
        # Closing opportunities requires special checks
        if view.action in ['close', 'close_won', 'close_lost']:
            return self.can_close_opportunity(request.user, obj)
        
        # Check ownership and hierarchy
        if hasattr(obj, 'owner') and obj.owner:
            # Owner can perform most actions
            if obj.owner.user == request.user:
                return True
            
            # Manager can access team opportunities
            if self.is_opportunity_manager(request.user, obj):
                return True
        
        # Check data access level
        return self.check_opportunity_access(request.user, obj)
    
    def can_apply_discount(self, user, opportunity, request_data):
        """Check if user can apply requested discount."""
        if not self.has_perm(user, 'discount_opportunity'):
            return False
        
        # Get requested discount percentage
        discount_percent = request_data.get('discount_percent', 0)
        if not discount_percent:
            return True  # No discount requested
        
        # Check user's discount approval authority
        user_role = self.get_user_role(user)
        max_discount = self.DISCOUNT_APPROVAL_THRESHOLDS.get(user_role, Decimal('0'))
        
        if Decimal(str(discount_percent)) <= max_discount:
            return True
        
        # Check if opportunity amount requires higher approval
        opportunity_amount = getattr(opportunity, 'amount', 0) or 0
        
        # Large deals may require additional approval
        if opportunity_amount > 100000:  # $100k+
            return user_role in ['sales_director', 'vp_sales']
        
        return False
    
    def can_close_opportunity(self, user, opportunity):
        """Check if user can close opportunity."""
        if not self.has_perm(user, 'close_opportunity'):
            return False
        
        # Owner can close their opportunities
        if hasattr(opportunity, 'owner') and opportunity.owner:
            if opportunity.owner.user == user:
                return True
        
        # Manager can close team opportunities
        if self.is_opportunity_manager(user, opportunity):
            return True
        
        # Large deals may require manager approval
        opportunity_amount = getattr(opportunity, 'amount', 0) or 0
        if opportunity_amount > 50000:  # $50k+
            return self.has_manager_role(user)
        
        return False
    
    def is_opportunity_manager(self, user, opportunity):
        """Check if user is manager for this opportunity."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        if not hasattr(opportunity, 'owner') or not opportunity.owner:
            return False
        
        # Check if user manages the opportunity owner
        opportunity_owner = opportunity.owner
        if hasattr(opportunity_owner, 'team'):
            owner_team = opportunity_owner.team
            if owner_team and owner_team.manager:
                return owner_team.manager.user == user
        
        return False
    
    def check_opportunity_access(self, user, opportunity):
        """Check opportunity access based on data access level."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_profile = user.crm_profile
        
        if user_profile.data_access_level == 'all':
            return True
        elif user_profile.data_access_level == 'territory':
            return self.has_territory_access(user, opportunity)
        elif user_profile.data_access_level == 'team':
            return self.has_team_access(user, opportunity)
        elif user_profile.data_access_level == 'own':
            return hasattr(opportunity, 'owner') and opportunity.owner.user == user
        
        return False
    
    def get_user_role(self, user):
        """Get user's role for permission checking."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role
        return 'sales_rep'  # Default role
    
    def has_manager_role(self, user):
        """Check if user has manager role."""
        user_role = self.get_user_role(user)
        return user_role in ['sales_manager', 'sales_director', 'vp_sales']

class PipelinePermission(CRMPermission):
    """Permission class for Pipeline model."""
    
    MODEL_PERMS = {
        'view_pipeline': 'Can view pipelines',
        'add_pipeline': 'Can add pipelines',
        'change_pipeline': 'Can change pipelines', 
        'delete_pipeline': 'Can delete pipelines',
        'configure_pipeline': 'Can configure pipeline stages',
    }
    
    def has_permission(self, request, view):
        """Pipeline permissions typically require admin access."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_pipeline')
        
        # Configuration requires admin or sales management
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (request.user.is_staff or 
                   self.has_sales_admin_role(request.user) or
                   self.has_perm(request.user, f'{view.action}_pipeline'))
        
        return True
    
    def has_sales_admin_role(self, user):
        """Check if user has sales admin role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in [
                'sales_director', 'vp_sales', 'crm_admin'
            ]
        return False
