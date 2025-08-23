from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from ..entities.base import AggregateRoot


class Repository(ABC):
    """Base repository interface"""
    
    @abstractmethod
    def save(self, entity: AggregateRoot) -> AggregateRoot:
        """Save entity"""
        pass
    
    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[AggregateRoot]:
        """Find entity by ID"""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete entity"""
        pass
    
    @abstractmethod
    def find_all(self, **filters) -> List[AggregateRoot]:
        """Find all entities with optional filters"""
        pass
    
    @abstractmethod
    def count(self, **filters) -> int:
        """Count entities with optional filters"""
        pass
    
    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """Check if entity exists"""
        pass


class QueryRepository(ABC):
    """Base query repository for read operations"""
    
    @abstractmethod
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find by custom criteria"""
        pass
    
    @abstractmethod
    def paginate(self, page: int, size: int, **filters) -> Dict[str, Any]:
        """Paginated results"""
        pass