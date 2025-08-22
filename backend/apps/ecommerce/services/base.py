"""
Base service classes for e-commerce functionality
"""

import logging
from typing import Any, Dict, List, Optional, Union
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from decimal import Decimal

from apps.core.mixins import TenantMixin


class ServiceError(Exception):
    """Base exception for service layer errors"""
    
    def __init__(self, message: str, details: Optional[Dict] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)


class ValidationError(ServiceError):
    """Exception for validation errors in services"""
    pass


class NotFoundError(ServiceError):
    """Exception for when requested resource is not found"""
    pass


class PermissionError(ServiceError):
    """Exception for permission-related errors"""
    pass


class BaseEcommerceService(TenantMixin):
    """Base service class for all e-commerce services"""
    
    def __init__(self, tenant=None):
        super().__init__()
        self.tenant = tenant
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self._cache = {}
    
    def log_info(self, message: str, context: Optional[Dict] = None):
        """Log informational message with context"""
        self.logger.info(message, extra={'tenant': str(self.tenant), 'context': context or {}})
    
    def log_warning(self, message: str, context: Optional[Dict] = None):
        """Log warning message with context"""
        self.logger.warning(message, extra={'tenant': str(self.tenant), 'context': context or {}})
    
    def log_error(self, message: str, error: Optional[Exception] = None, context: Optional[Dict] = None):
        """Log error message with context"""
        self.logger.error(
            message, 
            extra={
                'tenant': str(self.tenant), 
                'context': context or {},
                'error': str(error) if error else None
            },
            exc_info=bool(error)
        )
    
    def validate_tenant(self, obj: Any) -> bool:
        """Validate that an object belongs to the current tenant"""
        if hasattr(obj, 'tenant') and obj.tenant != self.tenant:
            raise PermissionError(f"Object does not belong to tenant {self.tenant}")
        return True
    
    def get_cached_value(self, key: str, default: Any = None) -> Any:
        """Get value from service cache"""
        return self._cache.get(key, default)
    
    def set_cached_value(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in service cache with optional TTL"""
        self._cache[key] = value
        # TODO: Implement TTL functionality
    
    def clear_cache(self):
        """Clear service cache"""
        self._cache.clear()
    
    def format_currency(self, amount: Decimal, currency: str = 'USD') -> str:
        """Format currency amount for display"""
        if currency == 'USD':
            return f"${amount:,.2f}"
        elif currency == 'EUR':
            return f"€{amount:,.2f}"
        elif currency == 'GBP':
            return f"£{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    
    def parse_currency(self, amount_str: str) -> Decimal:
        """Parse currency string to Decimal"""
        try:
            # Remove currency symbols and commas
            cleaned = amount_str.replace('$', '').replace('€', '').replace('£', '').replace(',', '')
            return Decimal(cleaned)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid currency amount: {amount_str}")
    
    def get_current_timestamp(self) -> timezone.datetime:
        """Get current timestamp in tenant's timezone"""
        return timezone.now()
    
    def validate_required_fields(self, data: Dict, required_fields: List[str]) -> bool:
        """Validate that required fields are present in data"""
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        return True
    
    def validate_field_types(self, data: Dict, field_types: Dict[str, type]) -> bool:
        """Validate field types in data"""
        for field, expected_type in field_types.items():
            if field in data and not isinstance(data[field], expected_type):
                raise ValidationError(f"Field {field} must be of type {expected_type.__name__}")
        return True
    
    def sanitize_string(self, value: str, max_length: Optional[int] = None) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")
        
        # Remove leading/trailing whitespace
        sanitized = value.strip()
        
        # Truncate if max_length specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    def validate_email(self, email: str) -> str:
        """Validate and normalize email address"""
        if not email or '@' not in email:
            raise ValidationError("Invalid email address")
        
        # Basic email validation
        email = email.lower().strip()
        if len(email) > 254:  # RFC 5321 limit
            raise ValidationError("Email address too long")
        
        return email
    
    def validate_phone(self, phone: str) -> str:
        """Validate and normalize phone number"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone))
        
        if len(digits_only) < 10:
            raise ValidationError("Phone number must have at least 10 digits")
        
        return digits_only
    
    def create_audit_log(self, action: str, resource_type: str, resource_id: str, 
                         user_id: Optional[str] = None, details: Optional[Dict] = None):
        """Create audit log entry"""
        # TODO: Implement audit logging
        self.log_info(f"Audit: {action} on {resource_type} {resource_id}", {
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'user_id': user_id,
            'details': details
        })
    
    def handle_service_error(self, error: Exception, context: str) -> ServiceError:
        """Handle and transform various exceptions to ServiceError"""
        if isinstance(error, ServiceError):
            return error
        elif isinstance(error, DjangoValidationError):
            return ValidationError(str(error), details={'field_errors': error.message_dict})
        elif isinstance(error, PermissionDenied):
            return PermissionError("Permission denied", details={'context': context})
        else:
            self.log_error(f"Unexpected error in {context}", error)
            return ServiceError(f"An unexpected error occurred: {str(error)}")
    
    def with_transaction(self, func, *args, **kwargs):
        """Execute function within database transaction"""
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception as e:
            self.log_error(f"Transaction failed for {func.__name__}", e)
            raise


class CacheableService(BaseEcommerceService):
    """Service with enhanced caching capabilities"""
    
    def __init__(self, tenant=None, cache_ttl: int = 300):
        super().__init__(tenant)
        self.cache_ttl = cache_ttl
    
    def get_cached_or_fetch(self, key: str, fetch_func, *args, **kwargs):
        """Get cached value or fetch using provided function"""
        cached = self.get_cached_value(key)
        if cached is not None:
            return cached
        
        result = fetch_func(*args, **kwargs)
        self.set_cached_value(key, result, self.cache_ttl)
        return result
    
    def invalidate_cache_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        keys_to_remove = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_remove:
            del self._cache[key]


class AsyncService(BaseEcommerceService):
    """Base service for asynchronous operations"""
    
    async def async_operation(self, operation_func, *args, **kwargs):
        """Execute async operation with error handling"""
        try:
            return await operation_func(*args, **kwargs)
        except Exception as e:
            self.log_error(f"Async operation failed: {operation_func.__name__}", e)
            raise self.handle_service_error(e, f"async_operation_{operation_func.__name__}")
