"""
Base use case class
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

from ...services.base import BaseEcommerceService, ValidationError, ServiceError


class BaseUseCase(BaseEcommerceService):
    """Base class for all use cases"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the use case"""
        pass
    
    def validate_preconditions(self, *args, **kwargs) -> bool:
        """Validate preconditions before execution"""
        return True
    
    def validate_postconditions(self, result: Any) -> bool:
        """Validate postconditions after execution"""
        return True
    
    def log_use_case_execution(self, use_case_name: str, input case execution"""
        self.log_info(f"Use case executed: {use_case_name}", {
            'input': input_data,
            'result_type': type(result).__name__,
            'success': True
        })