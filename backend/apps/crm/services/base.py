# ============================================================================
# backend/apps/crm/services/base.py - Enhanced Base Service with Advanced Features
# ============================================================================

from django.db import transaction, connection
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from typing import Dict, List, Any, Optional, Union, Tuple
import logging
import json
import hashlib
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ServiceException(Exception):
    """Enhanced exception for service layer errors with detailed context"""
    def __init__(self, message: str, code: str = None, details: Dict = None, 
                 severity: str = 'error', retry_after: int = None):
        super().__init__(message)
        self.message = message
        self.code = code or 'SERVICE_ERROR'
        self.details = details or {}
        self.severity = severity  # 'critical', 'error', 'warning', 'info'
        self.retry_after = retry_after
        self.timestamp = timezone.now()
        self.request_id = str(uuid.uuid4())


class ServiceMetrics:
    """Service performance and usage metrics tracking"""
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.start_time = time.time()
        self.operations = []
        
    def track_operation(self, operation: str, duration: float, success: bool = True):
        self.operations.append({
            'operation': operation,
            'duration': duration,
            'success': success,
            'timestamp': timezone.now()
        })
    
    def get_summary(self) -> Dict:
        total_duration = time.time() - self.start_time
        successful_ops = sum(1 for op in self.operations if op['success'])
        
        return {
            'service': self.service_name,
            'total_duration': total_duration,
            'total_operations': len(self.operations),
            'successful_operations': successful_ops,
            'success_rate': successful_ops / len(self.operations) if self.operations else 0,
            'avg_operation_time': sum(op['duration'] for op in self.operations) / len(self.operations) if self.operations else 0
        }


@dataclass
class ServiceContext:
    """Enhanced service context with request tracking and metadata"""
    tenant_id: int
    user_id: int
    request_id: str
    operation: str
    metadata: Dict = None
    start_time: datetime = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = timezone.now()
        if self.metadata is None:
            self.metadata = {}


class CacheManager:
    """Advanced caching manager for service layer"""
    
    def __init__(self, tenant_id: int, service_name: str):
        self.tenant_id = tenant_id
        self.service_name = service_name
        self.default_timeout = 3600  # 1 hour
    
    def get_cache_key(self, key: str, *args) -> str:
        """Generate tenant-aware cache key"""
        cache_parts = [self.service_name, str(self.tenant_id), key]
        if args:
            cache_parts.extend(str(arg) for arg in args)
        return ':'.join(cache_parts)
    
    def get(self, key: str, *args, default=None):
        """Get cached value with tenant isolation"""
        cache_key = self.get_cache_key(key, *args)
        return cache.get(cache_key, default)
    
    def set(self, key: str, value: Any, timeout: int = None, *args):
        """Set cached value with tenant isolation"""
        cache_key = self.get_cache_key(key, *args)
        cache.set(cache_key, value, timeout or self.default_timeout)
    
    def delete(self, key: str, *args):
        """Delete cached value"""
        cache_key = self.get_cache_key(key, *args)
        cache.delete(cache_key)
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        # This would require Redis or similar cache backend with pattern support
        cache_pattern = self.get_cache_key(pattern)
        # Implementation depends on cache backend
        pass


class DataValidator:
    """Advanced data validation with business rules"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format and domain"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        import re
        # Remove all non-digit characters
        digits_only = re.sub(r'[^\d]', '', phone)
        return len(digits_only) >= 10
    
    @staticmethod
    def sanitize_inputSanitize input data"""
        if not isinstance(data, str):
            return data
        
        # Remove potentially dangerous characters
        import html
        sanitized = html.escape(data.strip())
        return sanitized
    
    @staticmethod
    def validate_business rules: Dict) -> List[str]:
        """Validate against custom business rules"""
        errors = []
        
        for field, rule_set in rules.items():
            if
            value = data[field]
            
            # Required validation
            if rule_set.get('required') and not value:
                errors.append(f"{field} is required")
            
            # Length validation
            if 'min_length' in rule_set and len(str(value)) < rule_set['min_length']:
                errors.append(f"{field} must be at least {rule_set['min_length']} characters")
            
            # Custom validator functions
            if 'validator' in rule_set:
                validator = rule_set['validator']
                if callable(validator) and not validator(value):
                    errors.append(f"{field} validation failed")
        
        return errors


class BaseService:
    """Enhanced base service class with comprehensive functionality"""
    
    def __init__(self, tenant=None, user=None, context: ServiceContext = None):
        self.tenant = tenant
        self.user = user
        self.context = context or ServiceContext(
            tenant_id=tenant.id if tenant else 0,
            user_id=user.id if user else 0,
            request_id=str(uuid.uuid4()),
            operation='unknown'
        )
        
        # Initialize components
        self.cache = CacheManager(self.tenant.id if tenant else 0, self.__class__.__name__)
        self.metrics = ServiceMetrics(self.__class__.__name__)
        self.validator = DataValidator()
        
        # Performance tracking
        self._query_count_start = None
        self._performance_thresholds = {
            'query_count_warning': 50,
            'execution_time_warning': 5.0,  # seconds
            'memory_usage_warning': 100 * 1024 * 1024  # 100MB
        }
    
    def __enter__(self):
        """Context manager entry for performance tracking"""
        self._query_count_start = self._get_query_count()
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with performance analysis"""
        execution_time = time.time() - self._start_time
        query_count = self._get_query_count() - (self._query_count_start or 0)
        
        # Log performance metrics
        self._log_performance_metrics(execution_time, query_count, exc_type is None)
        
        # Check performance thresholds
        self._check_performance_thresholds(execution_time, query_count)
    
    def _get_query_count(self) -> int:
        """Get current database query count"""
        return len(connection.queries) if settings.DEBUG else 0
    
    def _log_performance_metrics(self, execution_time: float, query_count: int, success: bool):
        """Log detailed performance metrics"""
        metrics = {
            'service': self.__class__.__name__,
            'tenant_id': self.tenant.id if self.tenant else None,
            'user_id': self.user.id if self.user else None,
            'execution_time': execution_time,
            'query_count': query_count,
            'success': success,
            'timestamp': timezone.now().isoformat(),
            'request_id': self.context.request_id
        }
        
        logger.info(f"Service Performance: {json.dumps(metrics)}")
    
    def _check_performance_thresholds(self, execution_time: float, query_count: int):
        """Check and warn about performance threshold violations"""
        warnings = []
        
        if query_count > self._performance_thresholds['query_count_warning']:
            warnings.append(f"High query count: {query_count}")
        
        if execution_time > self._performance_thresholds['execution_time_warning']:
            warnings.append(f"Slow execution: {execution_time:.2f}s")
        
        if warnings:
            logger.warning(f"Performance warnings for {self.__class__.__name__}: {', '.join(warnings)}")
    
    def validate_tenant_access(self, obj):
        """Enhanced tenant access validation with detailed logging"""
        if not self.tenant:
            raise ServiceException(
                "No tenant context available",
                code='NO_TENANT_CONTEXT',
                severity='critical'
            )
        
        if hasattr(obj, 'tenant') and obj.tenant != self.tenant:
            self.log_security_event('TENANT_ACCESS_VIOLATION', {
                'attempted_tenant': obj.tenant.id if obj.tenant else None,
                'user_tenant': self.tenant.id,
                'object_type': obj.__class__.__name__,
                'object_id': getattr(obj, 'id', None)
            })
            
            raise ServiceException(
                "Access denied: Object belongs to different tenant",
                code='TENANT_ACCESS_DENIED',
                severity='critical',
                details={
                    'object_tenant': obj.tenant.id if obj.tenant else None,
                    'user_tenant': self.tenant.id
                }
            )
    
    def validate_user_permission(self, permission: str, obj=None):
        """Enhanced permission validation with context"""
        if not self.user:
            raise ServiceException(
                "No user context available",
                code='NO_USER_CONTEXT',
                severity='critical'
            )
        
        # Check basic permission
        if not self.user.has_perm(permission):
            self.log_security_event('PERMISSION_DENIED', {
                'permission': permission,
                'user_id': self.user.id,
                'object_type': obj.__class__.__name__ if obj else None
            })
            
            raise ServiceException(
                f"Permission denied: {permission}",
                code='PERMISSION_DENIED',
                severity='error',
                details={'required_permission': permission}
            )
        
        # Additional object-level checks
        if obj and hasattr(self, '_check_object_permission'):
            if not self._check_object_permission(permission, obj):
                raise ServiceException(
                    f"Object-level permission denied: {permission}",
                    code='OBJECT_PERMISSION_DENIED',
                    severity='error'
                )
    
    def log_activity(self, action: str, model_name: str, object_id: int, 
                    detailsd activity logging with rich context"""
        try:
            from ..models import AuditTrail
            
            # Prepare activity data
            activity_data = {
                'user': self.user,
                'tenant': self.tenant,
                'action_type': action,
                'model_name': model_name,
                'object_id': object_id,
                'changes': details or {},
                'metadata': {
                    'request_id': self.context.request_id,
                    'operation': self.context.operation,
                    'timestamp': timezone.now().isoformat(),
                    'user_agent': metadata.get('user_agent') if metadata else None,
                    'ip_address': metadata.get('ip_address') if metadata else None,
                    **(metadata or {})
                },
                'timestamp': timezone.now()
            }
            
            # Create audit trail entry
            audit_entry = AuditTrail.objects.create(**activity_data)
            
            # Cache recent activity for quick access
            cache_key = f"recent_activity_{self.user.id if self.user else 'system'}"
            recent_activities = self.cache.get(cache_key, [])
            recent_activities.insert(0, {
                'id': audit_entry.id,
                'action': action,
                'model': model_name,
                'timestamp': timezone.now().isoformat()
            })
            
            # Keep only recent 20 activities in cache
            recent_activities = recent_activities[:20]
            self.cache.set(cache_key, recent_activities, 1800)  # 30 minutes
            
        except Exception as e:
            logger.error(f"Failed to log activity: {e}", exc_info=True)
    
    def log_security_event(self, event_type: str, details: Dict = None):
        """Log security-related events for monitoring"""
        security_event = {
            'event_type': event_type,
            'tenant_id': self.tenant.id if self.tenant else None,
            'user_id': self.user.id if self.user else None,
            'request_id': self.context.request_id,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        logger.warning(f"Security Event: {json.dumps(security_event)}")
        
        # Store in cache for security monitoring
        cache_key = f"security_events_{self.tenant.id if self.tenant else 'global'}"
        events = self.cache.get(cache_key, [])
        events.insert(0, security_event)
        events = events[:100]  # Keep recent 100 events
        self.cache.set(cache_key, events, 3600)  # 1 hour
    
    @transaction.atomic
    def bulk_update_optimized(self, queryset, updates: Dict, batch_size: int = 1000):
        """Optimized bulk updates with progress tracking"""
        total_count = queryset.count()
        updated_count = 0
        
        if total_count == 0:
            return {'updated_count': 0, 'batches': 0}
        
        # Calculate number of batches
        batches = (total_count + batch_size - 1) // batch_size
        
        for i, batch in enumerate(self._batch_queryset(queryset, batch_size)):
            batch_start = time.time()
            
            # Add metadata to updates
            updates_with_meta = {
                **updates,
                'updated_by': self.user,
                'updated_at': timezone.now()
            }
            
            batch_updated = batch.update(**updates_with_meta)
            updated_count += batch_updated
            
            batch_duration = time.time() - batch_start
            
            # Log batch progress
            logger.debug(f"Bulk update batch {i+1}/{batches}: {batch_updated} records in {batch_duration:.2f}s")
            
            # Track metrics
            self.metrics.track_operation(f'bulk_update_batch_{i+1}', batch_duration, True)
        
        return {
            'updated_count': updated_count,
            'batches': batches,
            'total_records': total_count
        }
    
    def _batch_queryset(self, queryset, batch_size: int):
        """Efficiently batch queryset with memory optimization"""
        # Use iterator to reduce memory usage for large querysets
        current_batch = []
        
        for item in queryset.iterator():
            current_batch.append(item.pk)
            
            if len(current_batch) >= batch_size:
                yield queryset.filter(pk__in=current_batch)
                current_batch = []
        
        # Yield remaining items
        if current_batch:
            yield queryset.filter(pk__in=current_batch)
    
    def send_notification(self, recipients: List, message: str, notification_type: str = 'info',
                         priority: str = 'normal', data: Dict = None):
        """Enhanced notification system with delivery tracking"""
        try:
            from ..tasks import send_notification_task
            
            notification_id = str(uuid.uuid4())
            
            # Prepare notification data
            notification_data = {
                'id': notification_id,
                'tenant_id': self.tenant.id if self.tenant else None,
                'sender_id': self.user.id if self.user else None,
                'recipient_ids': [r.id if hasattr(r, 'id') else r for r in recipients],
                'message': message,
                'notification_type': notification_type,
                'priority': priority,
                'data': data or {},
                'request_id': self.context.request_id,
                'created_at': timezone.now().isoformat()
            }
            
            # Queue notification for delivery
            send_notification_task.delay(notification_data)
            
            # Cache notification for tracking
            cache_key = f"notifications_sent_{self.user.id if self.user else 'system'}"
            sent_notifications = self.cache.get(cache_key, [])
            sent_notifications.insert(0, notification_id)
            sent_notifications = sent_notifications[:50]  # Keep recent 50
            self.cache.set(cache_key, sent_notifications, 3600)
            
            return notification_id
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)
            raise ServiceException(f"Notification failed: {str(e)}")
    
    def get_cached_or_compute(self, cache_key: str, compute_function: callable,
                             timeout: int = 3600, force_refresh: bool = False):
        """Get cached result or compute and cache"""
        if not force_refresh:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        # Compute result
        start_time = time.time()
        result = compute_function()
        computation_time = time.time() - start_time
        
        # Cache result
        self.cache.set(cache_key, result, timeout)
        
        # Track performance
        self.metrics.track_operation(f'cache_compute_{cache_key}', computation_time)
        
        return result
    
    def execute_with_retry(self, operation: callable, max_retries: int = 3,
                          delay: float = 1.0, backoff: float = 2.0):
        """Execute operation with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                result = operation()
                duration = time.time() - start_time
                
                self.metrics.track_operation(f'retry_operation_attempt_{attempt}', duration, True)
                return result
                
            except Exception as e:
                last_exception = e
                duration = time.time() - start_time
                self.metrics.track_operation(f'retry_operation_attempt_{attempt}', duration, False)
                
                if attempt < max_retries:
                    sleep_time = delay * (backoff ** attempt)
                    logger.warning(f"Operation failed, retrying in {sleep_time}s: {e}")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Operation failed after {max_retries + 1} attempts: {e}")
        
        raise ServiceException(
            f"Operation failed after {max_retries + 1} attempts",
            code='MAX_RETRIES_EXCEEDED',
            details={'last_error': str(last_exception)},
            retry_after=int(delay * (backoff ** max_retries))
        )
    
    def validate schema: Dict = None) -> Tuple[bool, List[str]]:
        """Comprehensive data integrity validation"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Data must be a dictionary")
            return False, errors
        
        # Schema validation if provided
        if schema:
            schema_errors = self.validator.validate_business_rules(data, schema)
            errors.extend(schema_errors)
        
        # Common field validations
        if 'email' in data and data['email']:
            if not self.validator.validate_email(data['email']):
                errors.append("Invalid email format")
        
        if 'phone' in data and data['phone']:
            if not self.validator.validate_phone(data['phone']):
                errors.append("Invalid phone format")
        
        # Sanitize string inputs
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = self.validator.sanitize_input(value)
        
        return len(errors) == 0, errors
    
    def get_service_health(self) -> Dict:
        """Get comprehensive service health metrics"""
        try:
            # Database connectivity check
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_healthy = True
        except Exception:
            db_healthy = False
        
        # Cache connectivity check
        try:
            test_key = f"health_check_{self.tenant.id if self.tenant else 'global'}"
            self.cache.set(test_key, "ok", 10)
            cache_healthy = self.cache.get(test_key) == "ok"
        except Exception:
            cache_healthy = False
        
        # Get performance metrics
        metrics_summary = self.metrics.get_summary()
        
        return {
            'service_name': self.__class__.__name__,
            'tenant_id': self.tenant.id if self.tenant else None,
            'timestamp': timezone.now().isoformat(),
            'database_healthy': db_healthy,
            'cache_healthy': cache_healthy,
            'performance_metrics': metrics_summary,
            'overall_health': 'healthy' if db_healthy and cache_healthy else 'degraded'
        }
    
    def cleanup_resources(self):
        """Clean up service resources and temporary data"""
        try:
            # Clear temporary cache entries
            if hasattr(self, '_temp_cache_keys'):
                for key in self._temp_cache_keys:
                    self.cache.delete(key)
            
            # Log final metrics
            final_metrics = self.metrics.get_summary()
            logger.info(f"Service cleanup - Final metrics: {json.dumps(final_metrics)}")
            
        except Exception as e:
            logger.error(f"Error during service cleanup: {e}")