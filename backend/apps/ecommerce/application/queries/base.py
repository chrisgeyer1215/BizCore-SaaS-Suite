"""
Base Query Handler
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from ...services.base import BaseEcommerceService


class BaseQueryHandler(BaseEcommerceService):
    """Base class for all query handlers"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def paginate_results(self, queryset, page: int, page_size: int) -> Dict[str, Any]:
        """Paginate query results"""
        offset = (page - 1) * page_size
        items = queryset[offset:offset + page_size]
        total = len(queryset)
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_next': offset + page_size < total,
            'has_previous': page > 1,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    def build_search_filter(self, search_term: str, search_fields: List[str]) -> Dict[str, Any]:
        """Build search filter for multiple fields"""
        if not search_term:
            return {}
        
        # This would build appropriate search filters for the repository
        return {
            'search': search_term,
            'search_fields': search_fields
        }
    
    def validate_pagination(self, page: int, page_size: int):
        """Validate pagination parameters"""
        if page < 1:
            raise ValidationError("Page must be >= 1")
        
        if page_size < 1 or page_size > 1000:
            raise ValidationError("Page size must be between 1 and 1000")