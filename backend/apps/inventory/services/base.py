from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

@dataclass
class ServiceResult:
    """
    Standardized result object for service operations
    """
     Any = None
    message: str = ""
    errors: Dict[str, List[str]] = None
    warnings: List[str] = None
    meta: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = {}
        if self.warnings is None:
            self.warnings = []
        if self.meta is None:
            self.meta = {}
    
    @property
    def is_success(self) -> bool:
        return self.status == ServiceStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.status == ServiceStatus.ERROR
    
    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)
    
    @classmethod
    def success(cls, data=None, message="Operation completed successfully", **kwargs):
        return cls(status=ServiceStatus.SUCCESS, data=data, message=message, **kwargs)
    
    @classmethod
    def error(cls, message="Operation failed", errors=None, **kwargs):
        return cls(status=ServiceStatus.ERROR, message=message, errors=errors or {}, **kwargs)
    
    @classmethod
    def warning(cls, message="Operation completed with warnings", warnings=None, **kwargs):
        return cls(status=ServiceStatus.WARNING, message=message, warnings=warnings or [], **kwargs)

class BaseService:
    """
    Base service class with common functionality
    """
    
    def __init__(self, tenant=None, user=None):
        self.tenant = tenant
        self.user = user
        self.logger = logger.getChild(self.__class__.__name__)
    
    def validate_tenant(self, obj=None):
        """Validate tenant access"""
        if self.tenant is None:
            raise ValidationError("Tenant is required")
        
        if obj and hasattr(obj, 'tenant') and obj.tenant != self.tenant:
            raise ValidationError("Object does not belong to the current tenant")
    
    def log_operation(self, operation: Any] = None, success: bool = True):
        """Log service operations"""
        log_data = {
            'operation': operation,
            'tenant': self.tenant.name if self.tenant else 'Unknown',
            'user': self.user.username if self.user else 'System',
            'timestamp': timezone.now().isoformat(),
            'success': success
        }
        ifupdate(data)
        
        if success:
            self.logger.info(f"Operation completed: {operation}", extra=log_data)
        else:
            self.logger.error(f"Operation failed: {operation}", extra=log_data)
    
    def validate_permissions(self, permission: str) -> bool:
        """Check if user has required permission"""
        if not self.user:
            return False
        return self.user.has_perm(permission)
    
    def handle_exceptions(self, operation_name: str):
        """Decorator for handling service exceptions"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except ValidationError as e:
                    self.log_operation(operation_name, {'error': str(e)}, success=False)
                    return ServiceResult.error(
                        message=f"Validation error in {operation_name}",
                        errors={'validation': [str(e)]}
                    )
                except Exception as e:
                    self.log_operation(operation_name, {'error': str(e)}, success=False)
                    return ServiceResult.error(
                        message=f"Unexpected error in {operation_name}",
                        errors={'system': [str(e)]}
                    )
            return wrapper
        return decorator