# ============================================================================
# backend/apps/crm/permissions/base.py - Core Permission Classes
# ============================================================================

import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import permissions
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from django.db.models import Q

logger = logging.getLogger(__name__)
User = get_user_model()


class CRMPermission(BasePermission):
    """
    Enhanced base permission class for CRM with comprehensive security
    """
    
    # Permission levels
    PERMISSION_LEVELS = {
        'NONE': 0,
        'READ': 1,
        'WRITE': 2,
        'DELETE': 4,
        'ADMIN': 8,
        'OWNER': 16
    }
    
    # Security contexts
    SECURITY_CONTEXTS = [
        'authentication',
        'authorization',
        'data_access',
        'field_level',
        'time_based',
        'location_based',
        'device_based'
    ]
    
    def __init__(self):
        self.security_log = []
        self.permission_cache = {}
        
    def has_permission(self, request: Request, view) -> bool:
        """
        Enhanced permission checking with comprehensive security validation
        """
        try:
            # Basic authentication check
            if not request.user or not request.user.is_authenticated:
                self._log_security_event('authentication_failed', request, view)
                return False
            
            # Tenant validation
            if not self._validate_tenant_access(request, view):
                self._log_security_event('tenant_access_denied', request, view)
                return False
            
            # Rate limiting check
            if not self._check_rate_limiting(request, view):
                self._log_security_event('rate_limit_exceeded', request, view)
                return False
            
            # Time-based access check
            if not self._check_time_based_access(request, view):
                self._log_security_event('time_based_access_denied', request, view)
                return False
            
            # IP-based access check
            if not self._check_ip_based_access(request, view):
                self._log_security_event('ip_based_access_denied', request, view)
                return False
            
            # Device-based access check
            if not self._check_device_based_access(request, view):
                self._log_security_event('device_based_access_denied', request, view)
                return False
            
            # Core permission logic (to be implemented by subclasses)
            permission_result = self._check_core_permission(request, view)
            
            if permission_result:
                self._log_security_event('permission_granted', request, view)
            else:
                self._log_security_event('permission_denied', request, view)
            
            return permission_result
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}", exc_info=True)
            self._log_security_event('permission_error', request, view, error=str(e))
            return False
    
    def has_object_permission(self, request: Request, view, obj) -> bool:
        """
        Enhanced object-level permission checking
        """
        try:
            # Basic permission check first
            if not self.has_permission(request, view):
                return False
            
            # Object ownership check
            if not self._check_object_ownership(request, view, obj):
                self._log_security_event('object_ownership_denied', request, view, obj=obj)
                return False
            
            # Object-level security context
            if not self._check_object_security_context(request, view, obj):
                self._log_security_event('object_security_denied', request, view, obj=obj)
                return False
            
            # Field-level access validation
            if not self._validate_field_level_access(request, view, obj):
                self._log_security_event('field_access_denied', request, view, obj=obj)
                return False
            
            # Core object permission logic
            object_permission_result = self._check_core_object_permission(request, view, obj)
            
            if object_permission_result:
                self._log_security_event('object_permission_granted', request, view, obj=obj)
            else:
                self._log_security_event('object_permission_denied', request, view, obj=obj)
            
            return object_permission_result
            
        except Exception as e:
            logger.error(f"Object permission check failed: {e}", exc_info=True)
            self._log_security_event('object_permission_error', request, view, obj=obj, error=str(e))
            return False
    
    def _validate_tenant_access(self, request: Request, view) -> bool:
        """Validate tenant-based access"""
        try:
            # Check if request has tenant context
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return False
            
            # Check user membership in tenant
            if hasattr(request.user, 'memberships'):
                user_tenants = request.user.memberships.filter(
                    tenant=tenant, is_active=True
                ).exists()
                return user_tenants
            
            return True  # Default to allow if no tenant system
            
        except Exception as e:
            logger.error(f"Tenant validation failed: {e}")
            return False
    
    def _check_rate_limiting(self, request: Request, view) -> bool:
        """Advanced rate limiting with user and IP tracking"""
        try:
            from django.core.cache import cache
            
            # Get rate limit configuration
            rate_limit_config = getattr(view, 'rate_limit_config', {
                'requests_per_minute': 60,
                'requests_per_hour': 1000,
                'burst_limit': 10
            })
            
            user_id = request.user.id
            client_ip = self._get_client_ip(request)
            current_minute = timezone.now().strftime('%Y-%m-%d-%H-%M')
            current_hour = timezone.now().strftime('%Y-%m-%d-%H')
            
            # Check per-minute limit
            minute_key = f"rate_limit_minute_{user_id}_{client_ip}_{current_minute}"
            minute_count = cache.get(minute_key, 0)
            
            if minute_count >= rate_limit_config['requests_per_minute']:
                return False
            
            # Check per-hour limit
            hour_key = f"rate_limit_hour_{user_id}_{client_ip}_{current_hour}"
            hour_count = cache.get(hour_key, 0)
            
            if hour_count >= rate_limit_config['requests_per_hour']:
                return False
            
            # Update counters
            cache.set(minute_key, minute_count + 1, 60)
            cache.set(hour_key, hour_count + 1, 3600)
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiting check failed: {e}")
            return True  # Default to allow on error
    
    def _check_time_based_access(self, request: Request, view) -> bool:
        """Time-based access control"""
        try:
            # Check if view has time-based restrictions
            time_restrictions = getattr(view, 'time_restrictions', None)
            if not time_restrictions:
                return True
            
            # Check user's timezone and current time
            user_timezone = getattr(request.user, 'timezone', 'UTC')
            current_time = timezone.now()
            
            # Validate business hours
            if 'business_hours' in time_restrictions:
                business_hours = time_restrictions['business_hours']
                current_hour = current_time.hour
                
                if not (business_hours['start'] <= current_hour <= business_hours['end']):
                    return False
            
            # Validate allowed days
            if 'allowed_days' in time_restrictions:
                allowed_days = time_restrictions['allowed_days']
                current_day = current_time.weekday()  # 0 = Monday
                
                if current_day not in allowed_days:
                    return False
            
            # Check session expiry
            session_timeout = time_restrictions.get('session_timeout_minutes', 480)  # 8 hours
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                last_activity_time = datetime.fromisoformat(last_activity)
                if (current_time - last_activity_time).total_seconds() > (session_timeout * 60):
                    return False
            
            # Update last activity
            request.session['last_activity'] = current_time.isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Time-based access check failed: {e}")
            return True
    
    def _check_ip_based_access(self, request: Request, view) -> bool:
        """IP-based access control with whitelist/blacklist"""
        try:
            # Check if view has IP restrictions
            ip_restrictions = getattr(view, 'ip_restrictions', None)
            if not ip_restrictions:
                return True
            
            client_ip = self._get_client_ip(request)
            
            # Check whitelist
            if 'whitelist' in ip_restrictions:
                whitelist = ip_restrictions['whitelist']
                if whitelist and client_ip not in whitelist:
                    return False
            
            # Check blacklist
            if 'blacklist' in ip_restrictions:
                blacklist = ip_restrictions['blacklist']
                if blacklist and client_ip in blacklist:
                    return False
            
            # Geographic restrictions
            if 'allowed_countries' in ip_restrictions:
                country_code = self._get_country_from_ip(client_ip)
                allowed_countries = ip_restrictions['allowed_countries']
                
                if country_code and country_code not in allowed_countries:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"IP-based access check failed: {e}")
            return True
    
    def _check_device_based_access(self, request: Request, view) -> bool:
        """Device-based access control"""
        try:
            device_restrictions = getattr(view, 'device_restrictions', None)
            if not device_restrictions:
                return True
            
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Check allowed user agents
            if 'allowed_user_agents' in device_restrictions:
                allowed_agents = device_restrictions['allowed_user_agents']
                if not any(agent in user_agent for agent in allowed_agents):
                    return False
            
            # Check blocked user agents
            if 'blocked_user_agents' in device_restrictions:
                blocked_agents = device_restrictions['blocked_user_agents']
                if any(agent in user_agent for agent in blocked_agents):
                    return False
            
            # Mobile device restrictions
            if 'mobile_access' in device_restrictions:
                is_mobile = self._is_mobile_device(user_agent)
                if not device_restrictions['mobile_access'] and is_mobile:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Device-based access check failed: {e}")
            return True
    
    def _check_core_permission(self, request: Request, view) -> bool:
        """Core permission logic - to be implemented by subclasses"""
        return True
    
    def _check_core_object_permission(self, request: Request, view, obj) -> bool:
        """Core object permission logic - to be implemented by subclasses"""
        return True
    
    def _check_object_ownership(self, request: Request, view, obj) -> bool:
        """Check object ownership"""
        try:
            # Check if object has owner/created_by field
            if hasattr(obj, 'created_by') and obj.created_by == request.user:
                return True
            
            if hasattr(obj, 'owner') and obj.owner == request.user:
                return True
            
            # Check if object has assigned_to field
            if hasattr(obj, 'assigned_to') and obj.assigned_to == request.user:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Object ownership check failed: {e}")
            return False
    
    def _log_security_event(self, event_type: str, request: Request, 
                          view, obj=None, error: str = None):
        """Log security events for auditing"""
        try:
            security_event = {
                'event_type': event_type,
                'timestamp': timezone.now().isoformat(),
                'user_id': request.user.id if request.user else None,
                'username': request.user.username if request.user else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'view_name': view.__class__.__name__,
                'method': request.method,
                'path': request.path,
                'tenant_id': getattr(request, 'tenant', {}).id if hasattr(request, 'tenant') else None,
                'object_type': obj.__class__.__name__ if obj else None,
                'object_id': obj.id if obj and hasattr(obj, 'id') else None,
                'error': error
            }
            
            # Store in security log
            self.security_log.append(security_event)
            
            # Log to file/external system
            if event_type in ['permission_denied', 'rate_limit_exceeded', 'ip_based_access_denied']:
                logger.warning(f"Security Event: {json.dumps(security_event)}")
            elif 'error' in event_type:
                logger.error(f"Security Error: {json.dumps(security_event)}")
            else:
                logger.info(f"Security Event: {event_type}")
            
        except Exception as e:
            logger.error(f"Security event logging failed: {e}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_country_from_ip(self, ip_address: str) -> Optional[str]:
        """Get country code from IP address (placeholder for GeoIP)"""
        # This would integrate with a GeoIP service
        return None
    
    def _is_mobile_device(self, user_agent: str) -> bool:
        """Check if request is from mobile device"""
        mobile_indicators = ['Mobile', 'Android', 'iPhone', 'iPad', 'BlackBerry']
        return any(indicator in user_agent for indicator in mobile_indicators)


class TenantPermission(CRMPermission):
    """
    Tenant-aware permission class with multi-tenancy security
    """
    
    def _check_core_permission(self, request: Request, view) -> bool:
        """Core tenant permission logic"""
        try:
            # Ensure tenant context exists
            if not hasattr(request, 'tenant'):
                return False
            
            # Check user membership in tenant
            if hasattr(request.user, 'memberships'):
                membership = request.user.memberships.filter(
                    tenant=request.tenant,
                    is_active=True
                ).first()
                
                if not membership:
                    return False
                
                # Store membership in request for later use
                request.membership = membership
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Tenant permission check failed: {e}")
            return False
    
    def _check_core_object_permission(self, request: Request, view, obj) -> bool:
        """Core tenant object permission logic"""
        try:
            # Ensure object belongs to same tenant
            if hasattr(obj, 'tenant') and obj.tenant != request.tenant:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Tenant object permission check failed: {e}")
            return False


class ObjectLevelPermission(TenantPermission):
    """
    Object-level permission with granular access control
    """
    
    # Permission matrices for different object types
    OBJECT_PERMISSIONS = {
        'Lead': {
            'view': ['lead.view_lead', 'lead.view_own_lead'],
            'change': ['lead.change_lead', 'lead.change_own_lead'],
            'delete': ['lead.delete_lead', 'lead.delete_own_lead'],
            'assign': ['lead.assign_lead'],
            'convert': ['lead.convert_lead']
        },
        'Account': {
            'view': ['account.view_account', 'account.view_own_account'],
            'change': ['account.change_account', 'account.change_own_account'],
            'delete': ['account.delete_account', 'account.delete_own_account'],
            'manage_contacts': ['account.manage_contacts']
        },
        'Opportunity': {
            'view': ['opportunity.view_opportunity', 'opportunity.view_own_opportunity'],
            'change': ['opportunity.change_opportunity', 'opportunity.change_own_opportunity'],
            'delete': ['opportunity.delete_opportunity', 'opportunity.delete_own_opportunity'],
            'close': ['opportunity.close_opportunity'],
            'reopen': ['opportunity.reopen_opportunity']
        }
    }
    
    def _check_core_object_permission(self, request: Request, view, obj) -> bool:
        """Enhanced object-level permission checking"""
        try:
            # Get object type
            object_type = obj.__class__.__name__
            
            # Get required action
            action = self._get_action_from_view(view, request.method)
            
            # Check if user has required permissions
            required_permissions = self.OBJECT_PERMISSIONS.get(object_type, {}).get(action, [])
            
            for permission in required_permissions:
                if self._user_has_permission(request.user, permission, obj):
                    return True
            
            # Check ownership-based permissions
            if self._check_ownership_based_permission(request.user, obj, action):
                return True
            
            # Check role-based permissions
            if self._check_role_based_permission(request, obj, action):
                return True
            
            # Check sharing permissions
            if self._check_sharing_permissions(request.user, obj, action):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Object permission check failed: {e}")
            return False
    
    def _get_action_from_view(self, view, method: str) -> str:
        """Determine action from view and HTTP method"""
        action_mapping = {
            'GET': 'view',
            'POST': 'add',
            'PUT': 'change',
            'PATCH': 'change',
            'DELETE': 'delete'
        }
        
        # Check for specific view actions
        if hasattr(view, 'action'):
            view_action = view.action
            if view_action in ['retrieve', 'list']:
                return 'view'
            elif view_action in ['create']:
                return 'add'
            elif view_action in ['update', 'partial_update']:
                return 'change'
            elif view_action in ['destroy']:
                return 'delete'
            else:
                return view_action
        
        return action_mapping.get(method, 'view')
    
    def _user_has_permission(self, user: User, permission: str, obj) -> bool:
        """Check if user has specific permission"""
        try:
            # Django's built-in permission system
            if user.has_perm(permission):
                return True
            
            # Check object-level permissions via django-guardian or similar
            if hasattr(user, 'has_perm') and len(permission.split('.')) > 1:
                return user.has_perm(permission, obj)
            
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False
    
    def _check_ownership_based_permission(self, user: User, obj, action: str) -> bool:
        """Check ownership-based permissions"""
        try:
            # Owner can perform most actions on their objects
            if hasattr(obj, 'created_by') and obj.created_by == user:
                return action in ['view', 'change', 'delete']
            
            # Assigned user can view and update
            if hasattr(obj, 'assigned_to') and obj.assigned_to == user:
                return action in ['view', 'change']
            
            # Owner field check
            if hasattr(obj, 'owner') and obj.owner == user:
                return action in ['view', 'change', 'delete']
            
            return False
            
        except Exception as e:
            logger.error(f"Ownership permission check failed: {e}")
            return False
    
    def _check_role_based_permission(self, request: Request, obj, action: str) -> bool:
        """Check role-based permissions"""
        try:
            if not hasattr(request, 'membership'):
                return False
            
            membership = request.membership
            user_role = membership.role
            
            # Role hierarchy
            role_hierarchy = {
                'ADMIN': ['view', 'add', 'change', 'delete', 'assign', 'manage'],
                'MANAGER': ['view', 'add', 'change', 'assign'],
                'SUPERVISOR': ['view', 'add', 'change'],
                'USER': ['view', 'add'],
                'VIEWER': ['view']
            }
            
            allowed_actions = role_hierarchy.get(user_role, [])
            return action in allowed_actions
            
        except Exception as e:
            logger.error(f"Role-based permission check failed: {e}")
            return False
    
    def _check_sharing_permissions(self, user: User, obj, action: str) -> bool:
        """Check if object has been shared with user"""
        try:
            # Check if object has sharing model
            if hasattr(obj, 'shares'):
                user_shares = obj.shares.filter(
                    shared_with_user=user,
                    is_active=True
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
                )
                
                for share in user_shares:
                    if action in share.permissions:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Sharing permission check failed: {e}")
            return False