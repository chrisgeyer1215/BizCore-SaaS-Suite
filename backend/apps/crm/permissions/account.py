# backend/apps/crm/permissions/account.py
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Account, Contact, Industry

class AccountPermission(CRMPermission):
    """Permission class for Account model."""
    
    MODEL_PERMS = {
        'view_account': 'Can view accounts',
        'add_account': 'Can add accounts',
        'change_account': 'Can change accounts',
        'delete_account': 'Can delete accounts',
        'export_account': 'Can export accounts',
        'import_account': 'Can import accounts',
        'merge_account': 'Can merge accounts',
        'transfer_account': 'Can transfer accounts',
    }
    
    def has_permission(self, request, view):
        """Check basic permissions."""
        if not super().has_permission(request, view):
            return False
        
        # Check action-specific permissions
        if view.action == 'list':
            return self.has_perm(request.user, 'view_account')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_account')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_account')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_account')
        elif view.action in ['bulk_export', 'export']:
            return self.has_perm(request.user, 'export_account')
        elif view.action in ['bulk_import', 'import']:
            return self.has_perm(request.user, 'import_account')
        elif view.action == 'merge':
            return self.has_perm(request.user, 'merge_account')
        elif view.action == 'transfer':
            return self.has_perm(request.user, 'transfer_account')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check ownership and territory restrictions
        if hasattr(obj, 'owner') and obj.owner:
            # Owner can perform most actions
            if obj.owner.user == request.user:
                return True
        
        # Check territory permissions
        if hasattr(request.user, 'crm_profile'):
            user_territory = request.user.crm_profile.territory
            if hasattr(obj, 'territory') and obj.territory:
                if obj.territory != user_territory:
                    # Check if user can access other territories
                    if not self.has_cross_territory_access(request.user):
                        return False
        
        # Check data access level
        return self.check_data_access_level(request.user, obj)
    
    def check_data_access_level(self, user, obj):
        """Check user's data access level."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        access_level = user.crm_profile.data_access_level
        
        if access_level == 'all':
            return True
        elif access_level == 'territory':
            return self.has_territory_access(user, obj)
        elif access_level == 'team':
            return self.has_team_access(user, obj)
        elif access_level == 'own':
            return self.has_ownership_access(user, obj)
        
        return False
    
    def has_cross_territory_access(self, user):
        """Check if user can access across territories."""
        return user.has_perm('crm.access_all_territories')
    
    def has_territory_access(self, user, obj):
        """Check territory-based access."""
        if not hasattr(user, 'crm_profile') or not hasattr(obj, 'territory'):
            return False
        
        user_territory = user.crm_profile.territory
        return obj.territory == user_territory
    
    def has_team_access(self, user, obj):
        """Check team-based access."""
        if not hasattr(user, 'crm_profile') or not hasattr(obj, 'owner'):
            return False
        
        user_team = user.crm_profile.team
        if hasattr(obj.owner, 'team'):
            return obj.owner.team == user_team
        
        return False
    
    def has_ownership_access(self, user, obj):
        """Check ownership-based access."""
        if not hasattr(obj, 'owner'):
            return False
        
        return obj.owner.user == user

class ContactPermission(AccountPermission):
    """Permission class for Contact model."""
    
    MODEL_PERMS = {
        'view_contact': 'Can view contacts',
        'add_contact': 'Can add contacts',
        'change_contact': 'Can change contacts',
        'delete_contact': 'Can delete contacts',
        'export_contact': 'Can export contacts',
        'import_contact': 'Can import contacts',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check contact-specific permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check account-level permissions
        if hasattr(obj, 'account') and obj.account:
            # Use AccountPermission to check account access
            account_permission = AccountPermission()
            return account_permission.has_object_permission(request, view, obj.account)
        
        return True

class IndustryPermission(CRMPermission):
    """Permission class for Industry model."""
    
    MODEL_PERMS = {
        'view_industry': 'Can view industries',
        'add_industry': 'Can add industries',
        'change_industry': 'Can change industries',
        'delete_industry': 'Can delete industries',
    }
    
    def has_permission(self, request, view):
        """Industry permissions - typically admin only for modifications."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all authenticated users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_industry')
        
        # Modification permissions typically require admin access
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return request.user.is_staff or self.has_perm(request.user, f'{view.action}_industry')
        
        return True