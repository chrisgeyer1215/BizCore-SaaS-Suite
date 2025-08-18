# middlewares/tenant_middleware.py

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import get_tenant_model, get_tenant_domain_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from apps.auth.models import Membership
import logging

logger = logging.getLogger(__name__)

Tenant = get_tenant_model()
Domain = get_tenant_domain_model()


class TenantContextMiddleware(MiddlewareMixin):
    """
    Middleware to add tenant context to request based on:
    1. Subdomain in request
    2. JWT token tenant_id claim
    3. HTTP header X-Tenant-Slug
    """
    
    def process_request(self, request):
        """
        Add tenant context to request
        """
        tenant = None
        
        # Skip for public schema URLs
        if self.is_public_schema_url(request.path):
            return None
        
        # Try to get tenant from various sources
        tenant = self.get_tenant_from_domain(request) or \
                 self.get_tenant_from_jwt(request) or \
                 self.get_tenant_from_header(request)
        
        if tenant:
            # Validate tenant status
            if tenant.status not in ['active', 'trial']:
                return JsonResponse({
                    'error': 'Tenant is not active',
                    'code': 'TENANT_INACTIVE'
                }, status=403)
            
            # Check if trial is expired
            if tenant.status == 'trial' and tenant.is_trial_expired:
                return JsonResponse({
                    'error': 'Trial period has expired',
                    'code': 'TRIAL_EXPIRED'
                }, status=403)
            
            # Add tenant to request
            request.tenant = tenant
            
            # Validate user has access to tenant if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                if not self.validate_user_tenant_access(request.user, tenant):
                    return JsonResponse({
                        'error': 'User does not have access to this tenant',
                        'code': 'ACCESS_DENIED'
                    }, status=403)
        
        return None
    
    def is_public_schema_url(self, path):
        """
        Check if URL belongs to public schema (no tenant required)
        """
        public_urls = [
            '/api/auth/register/',
            '/api/auth/login/',
            '/api/auth/password-reset-request/',
            '/api/auth/password-reset/',
            '/api/auth/verify-email/',
            '/api/auth/handoff/',
            '/api/auth/consume-handoff/',
            '/api/tenants/create/',
            '/api/docs/',
            '/api/schema/',
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        return any(path.startswith(url) for url in public_urls)
    
    def get_tenant_from_domain(self, request):
        """
        Get tenant from subdomain
        """
        try:
            host = request.get_host().split(':')[0]  # Remove port
            
            # Check if it's a subdomain pattern (subdomain.domain.com)
            parts = host.split('.')
            if len(parts) >= 3:
                subdomain = parts[0]
                
                # Skip common subdomains
                if subdomain in ['www', 'api', 'admin']:
                    return None
                
                # Look for tenant with this subdomain
                try:
                    domain = Domain.objects.get(domain=host, is_primary=True)
                    return domain.tenant
                except Domain.DoesNotExist:
                    # Try to find by tenant slug
                    try:
                        return Tenant.objects.get(slug=subdomain, status__in=['active', 'trial'])
                    except Tenant.DoesNotExist:
                        pass
            
        except Exception as e:
            logger.warning(f"Error getting tenant from domain: {e}")
        
        return None
    
    def get_tenant_from_jwt(self, request):
        """
        Get tenant from JWT token
        """
        try:
            # Use JWTAuthentication to get user and token
            jwt_auth = JWTAuthentication()
            auth_result = jwt_auth.authenticate(request)
            
            if auth_result:
                user, validated_token = auth_result
                tenant_id = validated_token.payload.get('tenant_id')
                
                if tenant_id:
                    try:
                        return Tenant.objects.get(id=tenant_id, status__in=['active', 'trial'])
                    except Tenant.DoesNotExist:
                        pass
        
        except (InvalidToken, Exception) as e:
            logger.debug(f"Error getting tenant from JWT: {e}")
        
        return None
    
    def get_tenant_from_header(self, request):
        """
        Get tenant from X-Tenant-Slug header
        """
        try:
            tenant_slug = request.META.get('HTTP_X_TENANT_SLUG')
            if tenant_slug:
                return Tenant.objects.get(slug=tenant_slug, status__in=['active', 'trial'])
        except Tenant.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"Error getting tenant from header: {e}")
        
        return None
    
    def validate_user_tenant_access(self, user, tenant):
        """
        Validate if user has access to the tenant
        """
        try:
            membership = Membership.objects.get(
                user=user,
                tenant_id=tenant.id,
                is_active=True,
                status='active'
            )
            
            # Check if membership is expired
            if membership.is_expired:
                return False
            
            # Update last access
            from django.utils import timezone
            membership.last_access = timezone.now()
            membership.save(update_fields=['last_access'])
            
            # Add membership to request for later use
            user.current_membership = membership
            
            return True
            
        except Membership.DoesNotExist:
            return False


class TenantDatabaseRoutingMiddleware(MiddlewareMixin):
    """
    Middleware to route database queries to correct tenant schema
    """
    
    def process_request(self, request):
        """
        Set database routing based on tenant
        """
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Set the tenant for django-tenants
            request.tenant = tenant
        
        return None


class TenantUsageTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track tenant usage for billing
    """
    
    def process_request(self, request):
        """
        Track API calls and other usage metrics
        """
        tenant = getattr(request, 'tenant', None)
        
        if tenant and request.path.startswith('/api/'):
            # Track API call
            self.track_api_call(tenant, request)
        
        return None
    
    def track_api_call(self, tenant, request):
        """
        Track API call for billing
        """
        try:
            from apps.core.models import TenantUsage
            from django.utils import timezone
            from datetime import datetime
            
            # Get current billing period
            now = timezone.now()
            period_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            
            if now.month == 12:
                next_year = now.year + 1
                next_month = 1
            else:
                next_year = now.year
                next_month = now.month + 1
            
            period_end = datetime(next_year, next_month, 1, tzinfo=now.tzinfo)
            
            # Get or create usage record
            usage, created = TenantUsage.objects.get_or_create(
                tenant=tenant,
                billing_period_start=period_start,
                defaults={
                    'billing_period_end': period_end,
                    'api_calls_count': 0
                }
            )
            
            # Increment API call count
            usage.api_calls_count += 1
            usage.save(update_fields=['api_calls_count'])
            
            # Check if tenant is exceeding limits
            if usage.api_calls_count > tenant.max_api_calls_per_month:
                logger.warning(f"Tenant {tenant.slug} exceeded API call limit")
                # Could implement rate limiting here
        
        except Exception as e:
            logger.error(f"Error tracking API usage: {e}")


class TenantSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for tenant isolation
    """
    
    def process_request(self, request):
        """
        Add security headers and validate tenant access
        """
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Add tenant-specific security headers
            request.META['X-Tenant-ID'] = str(tenant.id)
            request.META['X-Tenant-Slug'] = tenant.slug
        
        return None
    
    def process_response(self, request, response):
        """
        Add security headers to response
        """
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            response['X-Tenant-Context'] = tenant.slug
            
            # Add CORS headers for tenant-specific domains
            allowed_origins = []
            for domain in tenant.domains.all():
                allowed_origins.extend([
                    f"https://{domain.domain}",
                    f"http://{domain.domain}",  # For development
                ])
            
            if allowed_origins:
                origin = request.META.get('HTTP_ORIGIN')
                if origin in allowed_origins:
                    response['Access-Control-Allow-Origin'] = origin
                    response['Access-Control-Allow-Credentials'] = 'true'
        
        return response