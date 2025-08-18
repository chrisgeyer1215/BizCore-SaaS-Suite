# apps/auth/tokens.py

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from django.contrib.auth import get_user_model
from .models import Membership
from apps.core.models import Tenant

User = get_user_model()


def create_tokens_for_user(user, tenant_id=None):
    """
    Create JWT tokens for user with optional tenant context
    """
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['user_id'] = user.id
    refresh['email'] = user.email
    refresh['user_type'] = user.user_type
    
    if tenant_id:
        refresh['tenant_id'] = tenant_id
        
        # Add tenant-specific claims
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            membership = Membership.objects.get(
                user=user,
                tenant_id=tenant_id,
                is_active=True,
                status='active'
            )
            
            refresh['tenant_slug'] = tenant.slug
            refresh['tenant_name'] = tenant.name
            refresh['tenant_plan'] = tenant.plan
            refresh['role'] = membership.role
            refresh['permissions'] = membership.permissions
            
        except (Tenant.DoesNotExist, Membership.DoesNotExist):
            pass
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def blacklist_token(refresh_token):
    """
    Blacklist a refresh token
    """
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return True
    except Exception:
        return False


def get_user_from_token(token):
    """
    Get user from JWT token
    """
    try:
        refresh = RefreshToken(token)
        user_id = refresh.payload.get('user_id')
        return User.objects.get(id=user_id)
    except Exception:
        return None


def validate_tenant_access(user, tenant_id):
    """
    Validate if user has access to tenant
    """
    try:
        membership = Membership.objects.get(
            user=user,
            tenant_id=tenant_id,
            is_active=True,
            status='active'
        )
        
        # Check if membership is not expired
        if membership.is_expired:
            return False, None
        
        return True, membership
        
    except Membership.DoesNotExist:
        return False, None


class TenantAwareRefreshToken(RefreshToken):
    """
    Custom refresh token with tenant awareness
    """
    
    @classmethod
    def for_user_and_tenant(cls, user, tenant_id=None):
        """
        Create token for user with tenant context
        """
        token = cls.for_user(user)
        
        if tenant_id:
            # Validate tenant access
            has_access, membership = validate_tenant_access(user, tenant_id)
            if not has_access:
                raise ValueError("User does not have access to this tenant")
            
            # Add tenant claims
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                token['tenant_id'] = tenant_id
                token['tenant_slug'] = tenant.slug
                token['role'] = membership.role
                token['permissions'] = membership.permissions
            except Tenant.DoesNotExist:
                raise ValueError("Tenant does not exist")
        
        return token
    
    def verify_tenant_access(self):
        """
        Verify token's tenant access is still valid
        """
        tenant_id = self.payload.get('tenant_id')
        if tenant_id:
            user_id = self.payload.get('user_id')
            try:
                user = User.objects.get(id=user_id)
                has_access, _ = validate_tenant_access(user, tenant_id)
                return has_access
            except User.DoesNotExist:
                return False
        
        return True