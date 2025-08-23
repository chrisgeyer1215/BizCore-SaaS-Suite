# ============================================================================
# backend/apps/crm/permissions/mixins.py - Permission Mixins for Views and Serializers
# ============================================================================

from typing import Dict, List, Any, Optional
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
import logging

from .field_level import SensitiveDataPermission
from .role_based import DynamicRolePermission


logger = logging.getLogger(__name__)


class PermissionMixin:
    """
    Mixin to add comprehensive permission handling to views
    """
    
    permission_classes = [DynamicRolePermission]
    field_permission_class = SensitiveDataPermission
    
    def get_permissions(self):
        """
        Enhanced permission instantiation with context
        """
        permission_classes = self.permission_classes
        
        # Add context-specific permissions
        if hasattr(self, 'get_context_permissions'):
            context_permissions = self.get_context_permissions()
            permission_classes.extend(context_permissions)
        
        return [permission() for permission in permission_classes]
    
    def get_serializer(self, *args, **kwargs):
        """
        Enhanced serializer with field-level permissions
        """
        serializer = super().get_serializer(*args, **kwargs)
        
        # Apply field-level permissions
        if hasattr(self, 'request') and self.request:
            field_permission = self.field_permission_class()
            obj = kwargs.get('instance')
            serializer = field_permission.filter_serializer_fields(
                serializer, self.request, obj
            )
        
        return serializer
    
    def get_queryset(self):
        """
        Enhanced queryset with permission-based filtering
        """
        queryset = super().get_queryset()
        
        if hasattr(self, 'request') and self.request:
            # Apply user-based filtering
            queryset = self._apply_user_based_filtering(queryset)
            
            # Apply role-based filtering
            queryset = self._apply_role_based_filtering(queryset)
            
            # Apply time-based filtering
            queryset = self._apply_time_based_filtering(queryset)
        
        return queryset
    
    def _apply_user_based_filtering(self, queryset):
        """Apply user-based object filtering"""
        try:
            user = self.request.user
            user_roles = getattr(self.request, 'user_roles', [])
            
            # Admin users see everything
            if 'SYSTEM_ADMIN' in user_roles or 'TENANT_ADMIN' in user_roles:
                return queryset
            
            # Managers see team data
            if any(role.endswith('_MANAGER') for role in user_roles):
                return queryset  # Managers can see all team data
            
            # Regular users see own data + assigned data
            from django.db.models import Q
            user_filter = Q()
            
            if hasattr(queryset.model, 'created_by'):
                user_filter |= Q(created_by=user)
            
            if hasattr(queryset.model, 'assigned_to'):
                user_filter |= Q(assigned_to=user)
            
            if hasattr(queryset.model, 'owner'):
                user_filter |= Q(owner=user)
            
            return queryset.filter(user_filter) if user_filter else queryset
            
        except Exception as e:
            logger.error(f"User-based filtering failed: {e}")
            return queryset
    
    def _apply_role_based_filtering(self, queryset):
        """Apply role-based object filtering"""
        try:
            user_roles = getattr(self.request, 'user_roles', [])
            
            # Example: Marketing users only see marketing-related data
            if 'MARKETING_USER' in user_roles and 'MARKETING_MANAGER' not in user_roles:
                if hasattr(queryset.model, 'source') and queryset.model.__name__ == 'Lead':
                    # Marketing users only see leads from marketing sources
                    marketing_sources = ['Website', 'Email Campaign', 'Social Media', 'Advertisement']
                    queryset = queryset.filter(source__name__in=marketing_sources)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Role-based filtering failed: {e}")
            return queryset
    
    def _apply_time_based_filtering(self, queryset):
        """Apply time-based filtering for data access"""
        try:
            # Example: Some users can only see recent data
            user_roles = getattr(self.request, 'user_roles', [])
            
            if 'VIEWER' in user_roles:
                # Viewers only see data from last 30 days
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=30)
                
                if hasattr(queryset.model, 'created_at'):
                    queryset = queryset.filter(created_at__gte=cutoff_date)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Time-based filtering failed: {e}")
            return queryset
    
    @action(detail=False, methods=['get'])
    def permissions(self, request):
        """
        API endpoint to get current user's effective permissions
        """
        try:
            user_permissions = getattr(request, 'user_permissions', [])
            user_roles = getattr(request, 'user_roles', [])
            
            # Get field-level permissions
            model_name = getattr(self, 'queryset', None)
            if model_name:
                model_name = model_name.model.__name__
            
            field_permissions = self._get_field_permissions(request, model_name)
            
            return Response({
                'user_id': request.user.id,
                'roles': user_roles,
                'permissions': user_permissions,
                'field_permissions': field_permissions,
                'effective_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Permission endpoint failed: {e}")
            return Response({
                'error': 'Failed to retrieve permissions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_field_permissions(self, request, model_name: str) -> Dict:
        """Get field-level permissions for model"""
        try:
            field_permission = self.field_permission_class()
            user_roles = getattr(request, 'user_roles', [])
            
            # Get accessible security levels
            accessible_levels = set()
            for role in user_roles:
                role_access = field_permission.ROLE_FIELD_ACCESS.get(role, ['PUBLIC'])
                accessible_levels.update(role_access)
            
            # Get field classifications
            model_fields = field_permission.FIELD_SECURITY_CONFIG.get(model_name, {})
            
            field_permissions = {}
            for field, security_level in model_fields.items():
                field_permissions[field] = {
                    'security_level': security_level,
                    'accessible': security_level in accessible_levels
                }
            
            return field_permissions
            
        except Exception as e:
            logger.error(f"Field permission retrieval failed: {e}")
            return {}


class AuditMixin:
    """
    Mixin to add comprehensive auditing to views
    """
    
    def create(self, request, *args, **kwargs):
        """Enhanced create with audit logging"""
        try:
            response = super().create(request, *args, **kwargs)
            
            if response.status_code == status.HTTP_201_CREATED:
                self._log_audit_event('CREATE', request, response.data)
            
            return response
            
        except Exception as e:
            self._log_audit_event('CREATE_ERROR', request, error=str(e))
            raise
    
    def update(self, request, *args, **kwargs):
        """Enhanced update with audit logging"""
        try:
            # Get original object for change tracking
            original_obj = self.get_object()
            original_data = self._serialize_for_audit(original_obj)
            
            response = super().update(request, *args, **kwargs)
            
            if response.status_code == status.HTTP_200_OK:
                self._log_audit_event('UPDATE', request, response.data, 
                                    original_data=original_data)
            
            return response
            
        except Exception as e:
            self._log_audit_event('UPDATE_ERROR', request, error=str(e))
            raise
    
    def destroy(self, request, *args, **kwargs):
        """Enhanced delete with audit logging"""
        try:
            # Get object data before deletion
            obj = self.get_object()
            obj_data = self._serialize_for_audit(obj)
            
            response = super().destroy(request, *args, **kwargs)
            
            if response.status_code == status.HTTP_204_NO_CONTENT:
                self._log_audit_event('DELETE', request, obj_data)
            
            return response
            
        except Exception as e:
            self._log_audit_event('DELETE_ERROR', request, error=str(e))
            raise
    
    def _log_audit_event(self, event_type: str, request, data=None, 
                        original_data=None, error: str = None):
        """Log audit event"""
        try:
            from ..models import AuditLog
            
            audit_data = {
                'event_type': event_type,
                'user': request.user,
                'tenant': getattr(request, 'tenant', None),
                'model_name': getattr(self, 'queryset', None).model.__name__ if hasattr(self, 'queryset') else 'Unknown',
                'object_id': data.get('id') if data and isinstance(data, dict) else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now(),
                'changes': self._calculate_changes(original_data, data) if original_data else {},
                'error_message': error
            }
            
            AuditLog.objects.create(**audit_data)
            
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")
    
    def _serialize_for_audit(self, obj) -> Dict:
        """Serialize object for audit purposes"""
        try:
            # Use the same serializer as the view
            serializer = self.get_serializer(obj)
            return serializer.data
            
        except Exception as e:
            logger.error(f"Audit serialization failed: {e}")
            return {'error': 'serialization_failed'}
    
    def _calculate_changes(self, original_data, new_data) -> Dict:
        """Calculate changes between original and new data"""
        try:
            changes = {}
            
            if not original_data or not new_data:
                return changes
            
            # Find changed fields
            for field, new_value in new_data.items():
                original_value = original_data.get(field)
                
                if original_value != new_value:
                    changes[field] = {
                        'from': original_value,
                        'to': new_value
                    }
            
            return changes
            
        except Exception as e:
            logger.error(f"Change calculation failed: {e}")
            return {}
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityMixin:
    """
    Mixin to add additional security measures to views
    """
    
    def dispatch(self, request, *args, **kwargs):
        """Enhanced dispatch with security checks"""
        try:
            # Security headers
            response = super().dispatch(request, *args, **kwargs)
            
            # Add security headers
            if hasattr(response, 'headers'):
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['X-XSS-Protection'] = '1; mode=block'
                response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            return response
            
        except Exception as e:
            logger.error(f"Security dispatch failed: {e}")
            raise
    
    def perform_create(self, serializer):
        """Enhanced create with security validation"""
        try:
            # Input validation
            self._validate_input_security(serializer.validated_data)
            
            # Rate limiting check
            self._check_creation_rate_limit()
            
            super().perform_create(serializer)
            
        except Exception as e:
            logger.error(f"Secure create failed: {e}")
            raise
    
    def _validate_input_security(self, data):
        """Validate input data for security issues"""
        try:
            # Check for potential XSS
            for field, value in data.items():
                if isinstance(value, str):
                    if self._contains_xss_patterns(value):
                        raise PermissionDenied(f"Invalid content detected in field: {field}")
            
            # Check for SQL injection patterns
            for field, value in data.items():
                if isinstance(value, str):
                    if self._contains_sql_injection_patterns(value):
                        raise PermissionDenied(f"Invalid content detected in field: {field}")
            
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(f"Input security validation failed: {e}")
    
    def _contains_xss_patterns(self, value: str) -> bool:
        """Check for XSS patterns"""
        xss_patterns = [
            '<script',
            'javascript:',
            'onload=',
            'onerror=',
            'onclick='
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in xss_patterns)
    
    def _contains_sql_injection_patterns(self, value: str) -> bool:
        """Check for SQL injection patterns"""
        sql_patterns = [
            "'; drop table",
            "'; delete from",
            "union select",
            "1=1--",
            "' or '1'='1"
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in sql_patterns)
    
    def _check_creation_rate_limit(self):
        """Check if user exceeds creation rate limit"""
        try:
            from django.core.cache import cache
            
            user_id = self.request.user.id
            rate_key = f"create_rate_limit_{user_id}_{self.__class__.__name__}"
            
            current_count = cache.get(rate_key, 0)
            max_creates_per_hour = getattr(self, 'max_creates_per_hour', 100)
            
            if current_count >= max_creates_per_hour:
                raise PermissionDenied("Creation rate limit exceeded")
            
            cache.set(rate_key, current_count + 1, 3600)  # 1 hour
            
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")