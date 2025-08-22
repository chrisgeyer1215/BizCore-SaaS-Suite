# ============================================================================
# backend/apps/crm/services/base.py - Base Service Classes
# ============================================================================

from typing import Any, Dict, List, Optional, Union
from django.db import transaction, models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class CRMServiceException(Exception):
    """Custom exception for CRM service errors"""
    pass


class BaseService:
    """Base service class with common functionality"""
    
    def __init__(self, tenant, user=None):
        self.tenant = tenant
        self.user = user
        self.logger = logger
    
    def get_queryset(self, model_class):
        """Get tenant-filtered queryset"""
        return model_class.objects.filter(tenant=self.tenant, is_active=True)
    
    def check_permission(self, permission: str, obj=None) -> bool:
        """Check if user has permission for operation"""
        if not self.user:
            return False
        
        # Check CRM role permissions
        if hasattr(self.user, 'crm_profile') and self.user.crm_profile.crm_role:
            return self.user.crm_profile.crm_role.has_permission(permission)
        
        return False
    
    def require_permission(self, permission: str, obj=None):
        """Require permission or raise exception"""
        if not self.check_permission(permission, obj):
            raise PermissionDenied(f"Permission denied: {permission}")
    
    @transaction.atomic
    def create_audit_trail(self, action_type: str, obj: models.Model, changes: Dict = None):
        """Create audit trail entry"""
        try:
            from ..models import AuditTrail
            from django.contrib.contenttypes.models import ContentType
            
            AuditTrail.objects.create(
                tenant=self.tenant,
                user=self.user,
                action_type=action_type,
                content_type=ContentType.objects.get_for_model(obj),
                object_id=str(obj.pk),
                object_name=str(obj),
                changes=changes or {}
            )
        except Exception as e:
            self.logger.error(f"Failed to create audit trail: {e}"), required_fields: List[str]) -> Dict:
        """Validate required fields"""
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        return data
    
    def get_or_create_user_metrics(self, user: User) -> Dict:
        """Get or create user performance metrics"""
        try:
            profile = user.crm_profile
            return {
                'total_leads': profile.total_leads_assigned,
                'converted_leads': profile.total_leads_converted,
                'total_revenue': profile.total_revenue_generated,
                'conversion_rate': profile.conversion_rate,
            }
        except AttributeError:
            return {
                'total_leads': 0,
                'converted_leads': 0,
                'total_revenue': Decimal('0.00'),
                'conversion_rate': Decimal('0.00'),
            }


class CacheableMixin:
    """Mixin for services that need caching"""
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        key_parts = [prefix, str(self.tenant.id)] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    def get_from_cache(self, key: str, default=None):
        """Get value from cache"""
        try:
            from django.core.cache import cache
            return cache.get(key, default)
        except Exception:
            return default
    
    def set_cache(self, key: str, value: Any, timeout: int = 3600):
        """Set value in cache"""
        try:
            from django.core.cache import cache
            cache.set(key, value, timeout)
        except Exception as e:
            self.logger.error(f"Cache set failed: {e}")


class NotificationMixin:
    """Mixin for services that send notifications"""
    
    def send_notification(self, recipients: List[User], subject: str, message: str, 
                         notification_type: str = 'EMAIL'):
        """Send notification to users"""
        try:
            from .notification_service import NotificationService
            notification_service = NotificationService(self.tenant)
            return notification_service.send_notification(
                recipients, subject, message, notification_type
            )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")