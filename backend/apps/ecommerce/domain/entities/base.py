from abc import ABC
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class DomainEntity(ABC):
    """Base class for all domain entities"""
    
    def __init__(self, entity_id: Optional[str] = None):
        self.id = entity_id or str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._domain_events = []
    
    def add_domain_event(self, event):
        """Add domain event to be published"""
        self._domain_events.append(event)
    
    def clear_domain_events(self):
        """Clear domain events after publishing"""
        self._domain_events.clear()
    
    def get_domain_events(self):
        """Get all domain events"""
        return self._domain_events.copy()
    
    def update_timestamp(self):
        """Update the modified timestamp"""
        self.updated_at = datetime.utcnow()
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)


class AggregateRoot(DomainEntity):
    """Base class for aggregate roots"""
    
    def __init__(self, entity_id: Optional[str] = None):
        super().__init__(entity_id)
        self._version = 0
    
    @property
    def version(self):
        return self._version
    
    def increment_version(self):
        """Increment version for optimistic locking"""
        self._version += 1
        self.update_timestamp()