import logging
from django.db.models.signals import (
    pre_save, post_save, pre_delete, post_delete,
    m2m_changed
)
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from typing import Any, Optional

logger = logging.getLogger(__name__)

class BaseSignalHandler:
    """Base class for signal handlers with common functionality"""
    
    @staticmethod
    def log_signal(signal_name: str, sender_name: str, instance_id: Any, 
                  action: str = '', user: Optional[Any] = None):
        """Log signal execution for audit trail"""
        log_data = {
            'signal': signal_name,
            'model': sender_name,
            'instance_id': instance_id,
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'user': getattr(user, 'username', 'system') if user else 'system'
        }
        logger.info(f"Signal executed: {signal_name}", extra=log_data)
    
    @staticmethod
    def invalidate_cache_patterns(patterns: list):
        """Invalidate cache keys matching patterns"""
        try:
            for pattern in patterns:
                # This would depend on your cache backend
                # For Redis: cache.delete_pattern(pattern)
                # For basic cache, you'd need to track keys
                cache.delete(pattern)
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {str(e)}")
    
    @staticmethod
    def safe_signal_execution(func):
        """Decorator for safe signal execution"""
        def wrapper(sender, instance, **kwargs):
            try:
                return func(sender, instance, **kwargs)
            except Exception as e:
                logger.error(
                    f"Signal handler error in {func.__name__}: {str(e)}",
                    extra={
                        'sender': sender.__name__ if sender else 'Unknown',
                        'instance_id': getattr(instance, 'id', 'Unknown'),
                        'error': str(e)
                    },
                    exc_info=True
                )
                # Don't re-raise to prevent breaking the main operation
        return wrapper

class TenantSignalMixin:
    """Mixin for tenant-aware signal operations"""
    
    @staticmethod
    def get_tenant_from_instance(instance):
        """Extract tenant from instance"""
        if hasattr(instance, 'tenant'):
            return instance.tenant
        elif hasattr(instance, 'tenant_id'):
            return instance.tenant_id
        return None
    
    @staticmethod
    def is_tenant_active(instance) -> bool:
        """Check if tenant is active"""
        tenant = TenantSignalMixin.get_tenant_from_instance(instance)
        if tenant:
            return getattr(tenant, 'is_active', True)
        return True

class AuditSignalMixin:
    """Mixin for audit trail operations"""
    
    @staticmethod
    def create_audit_record(instance, action: str, user: Optional[Any] = None,
                          changes: Optional[dict] = None):
        """Create audit trail record"""
        try:
            from ..models import AuditLog
            from django.contrib.contenttypes.models import ContentType
            
            tenant = TenantSignalMixin.get_tenant_from_instance(instance)
            if not tenant:
                return
            
            AuditLog.objects.create(
                tenant=tenant,
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.pk,
                action=action,
                changes=changes or {},
                user=user,
                timestamp=timezone.now()
            )
        except Exception as e:
            logger.error(f"Failed to create audit record: {str(e)}")
    
    @staticmethod
    def track_field_changes(instance, original_instance=None) -> dict:
        """Track changes in model fields"""
        if not original_instance:
            return {}
        
        changes = {}
        for field in instance._meta.fields:
            field_name = field.name
            old_value = getattr(original_instance, field_name, None)
            new_value = getattr(instance, field_name, None)
            
            if old_value != new_value:
                changes[field_name] = {
                    'old': str(old_value) if old_value is not None else None,
                    'new': str(new_value) if new_value is not None else None
                }
        
        return changes

class NotificationSignalMixin:
    """Mixin for notification operations"""
    
    @staticmethod
    def queue_notification(notification_type: str, instance, 
                          recipients: list =Queue notification for async processing"""
        try:
            from ..tasks.celery import send_notification_task
            
            tenant = TenantSignalMixin.get_tenant_from_instance(instance)
            if not tenant:
                return
            
            notification_data = {
                'type': notification_type,
                'tenant_id': tenant.id,
                'instance_id': instance.pk,
                'model_name': instance._meta.label,
                'recipients': recipients or [],
                'data': data or {},
                'created_at': timezone.now().isoformat()
            }
            
            # Queue for async processing
            send_notification_task.delay(notification_data)
            
        except Exception as e:
            logger.error(f"Failed to queue notification: {str(e)}")

class IntegrationSignalMixin:
    """Mixin for integration operations"""
    
    @staticmethod
    def queue_integration_sync(integration_type: str, instance, 
                             action: str = 'update', priority: str = 'normal'):
        """Queue integration sync for async processing"""
        try:
            from ..tasks.celery import sync_integration_task
            
            tenant = TenantSignalMixin.get_tenant_from_instance(instance)
            if not tenant:
                return
            
            sync_data = {
                'integration_type': integration_type,
                'tenant_id': tenant.id,
                'instance_id': instance.pk,
                'model_name': instance._meta.label,
                'action': action,
                'priority': priority,
                'created_at': timezone.now().isoformat()
            }
            
            # Queue for async processing
            sync_integration_task.delay(sync_data)
            
        except Exception as e:
            logger.error(f"Failed to queue integration sync: {str(e)}")

class CacheInvalidationMixin:
    """Mixin for cache invalidation operations"""
    
    @staticmethod
    def invalidate_related_cache(instance, cache_patterns: list = None):
        """Invalidate cache related to instance"""
        if not cache_patterns:
            cache_patterns = []
        
        tenant = TenantSignalMixin.get_tenant_from_instance(instance)
        if tenant:
            # Add tenant-specific cache patterns
            model_name = instance._meta.label_lower.replace('.', '_')
            tenant_patterns = [
                f"tenant_{tenant.id}_{model_name}_*",
                f"tenant_{tenant.id}_dashboard_*",
                f"tenant_{tenant.id}_reports_*",
                f"tenant_{tenant.id}_analytics_*"
            ]
            cache_patterns.extend(tenant_patterns)
        
        BaseSignalHandler.invalidate_cache_patterns(cache_patterns)

# Global signal handlers for common operations
@receiver(post_save)
@BaseSignalHandler.safe_signal_execution
def global_post_save_handler(sender, instance, created, **kwargs):
    """Global post-save handler for all inventory models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Skip if this is a migration or fixture loading
    if kwargs.get('raw', False):
        return
    
    # Log the operation
    action = 'CREATE' if created else 'UPDATE'
    BaseSignalHandler.log_signal(
        'post_save',
        sender.__name__,
        getattr(instance, 'pk', 'Unknown'),
        action
    )
    
    # Invalidate related cache
    CacheInvalidationMixin.invalidate_related_cache(instance)
    
    # Update last_modified timestamp if available
    if hasattr(instance, 'updated_at') and not created:
        # Avoid recursive saves by checking if updated_at was just set
        if instance.updated_at < timezone.now() - timezone.timedelta(seconds=1):
            sender.objects.filter(pk=instance.pk).update(updated_at=timezone.now())

@receiver(pre_save)
@BaseSignalHandler.safe_signal_execution
def global_pre_save_handler(sender, instance, **kwargs):
    """Global pre-save handler for all inventory models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Skip if this is a migration or fixture loading
    if kwargs.get('raw', False):
        return
    
    # Set tenant from user context if available
    if hasattr(instance, 'tenant') and not instance.tenant:
        # Try to get tenant from thread-local storage or current user
        # This would be set by middleware
        current_tenant = getattr(instance, '_current_tenant', None)
        if current_tenant:
            instance.tenant = current_tenant
    
    # Set created_by/updated_by from user context
    current_user = getattr(instance, '_current_user', None)
    if current_user:
        if not instance.pk and hasattr(instance, 'created_by'):
            instance.created_by = current_user
        if hasattr(instance, 'updated_by'):
            instance.updated_by = current_user

@receiver(post_delete)
@BaseSignalHandler.safe_signal_execution
def global_post_delete_handler(sender, instance, **kwargs):
    """Global post-delete handler for all inventory models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Log the operation
    BaseSignalHandler.log_signal(
        'post_delete',
        sender.__name__,
        getattr(instance, 'pk', 'Unknown'),
        'DELETE'
    )
    
    # Create audit record
    AuditSignalMixin.create_audit_record(instance, 'DELETE')
    
    # Invalidate related cache
    CacheInvalidationMixin.invalidate_related_cache(instance)

# Tenant-specific signal handlers
@receiver(pre_save)
@BaseSignalHandler.safe_signal_execution
def enforce_tenant_isolation(sender, instance, **kwargs):
    """Ensure tenant isolation is maintained"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    if not hasattr(instance, 'tenant'):
        return
    
    # Check tenant is active
    if not TenantSignalMixin.is_tenant_active(instance):
        raise ValueError("Cannot save data for inactive tenant")
    
    # For updates, ensure tenant hasn't changed
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            if hasattr(original, 'tenant') and original.tenant != instance.tenant:
                raise ValueError("Cannot change tenant on existing record")
        except sender.DoesNotExist:
            pass

# Business rule enforcement signals
@receiver(pre_save)
@BaseSignalHandler.safe_signal_execution
def enforce_business_rules(sender, instance, **kwargs):
    """Enforce business rules across all inventory models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Skip if this is a migration or fixture loading
    if kwargs.get('raw', False):
        return
    
    # Validate required fields based on model type
    if hasattr(instance, 'is_active') and instance.is_active is None:
        instance.is_active = True
    
    # Set default values
    if hasattr(instance, 'created_at') and not instance.created_at:
        instance.created_at = timezone.now()
    
    if hasattr(instance, 'updated_at'):
        instance.updated_at = timezone.now()

# Performance monitoring signals
@receiver(post_save)
@receiver(post_delete)
@BaseSignalHandler.safe_signal_execution
def monitor_model_performance(sender, instance, **kwargs):
    """Monitor model operation performance"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    try:
        # Record performance metrics
        operation = 'delete' if 'post_delete' in str(kwargs) else 'save'
        
        # You could send to monitoring service like DataDog, Prometheus, etc.
        logger.info(
            f"Model operation completed",
            extra={
                'model': sender.__name__,
                'operation': operation,
                'instance_id': getattr(instance, 'pk', 'Unknown'),
                'tenant_id': getattr(instance, 'tenant_id', None),
                'timestamp': timezone.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Performance monitoring error: {str(e)}")

# Data consistency signals
@receiver(pre_save)
@BaseSignalHandler.safe_signal_execution
def ensure_data_consistency(sender, instance, **kwargs):
    """Ensure data consistency across related models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Skip if this is a migration or fixture loading
    if kwargs.get('raw', False):
        return
    
    try:
        # Model-specific consistency checks
        model_name = sender.__name__
        
        # Example: Ensure product is active when creating stock items
        if model_name == 'StockItem' and hasattr(instance, 'product'):
            if not instance.product.is_active:
                raise ValueError("Cannot create stock item for inactive product")
        
        # Example: Ensure warehouse is active
        if hasattr(instance, 'warehouse') and instance.warehouse:
            if not instance.warehouse.is_active:
                raise ValueError("Cannot use inactive warehouse")
        
    except Exception as e:
        logger.error(f"Data consistency check failed: {str(e)}")
        raise

# Integration signals
@receiver(post_save)
@BaseSignalHandler.safe_signal_execution
def trigger_integrations(sender, instance, created, **kwargs):
    """Trigger integration syncs for relevant models"""
    # Only handle inventory models
    if not sender._meta.app_label == 'inventory':
        return
    
    # Skip if this is a migration or fixture loading
    if kwargs.get('raw', False):
        return
    
    model_name = sender.__name__
    
    # Define which models trigger which integrations
    integration_triggers = {
        'StockItem': ['ecommerce', 'erp'],
        'Product': ['ecommerce', 'crm'],
        'PurchaseOrder': ['finance', 'erp'],
        'StockMovement': ['finance', 'analytics'],
        'Supplier': ['finance', 'crm'],
    }
    
    integrations = integration_triggers.get(model_name, [])
    action = 'create' if created else 'update'
    
    for integration in integrations:
        IntegrationSignalMixin.queue_integration_sync(
            integration, instance, action
        )