from abc import ABC
from datetime import datetime
from typing import Dict, Any
import uuid


class DomainEvent(ABC):
    """Base class for all domain events"""
    
    def __init__(self, aggregate_id: str, **kwargs):
        self.event_id = str(uuid.uuid4())
        self.aggregate_id = aggregate_id
        self.occurred_at = datetime.utcnow()
        self.event_version = 1
        self.event_data = kwargs
    
    @property
    def event_type(self) -> str:
        """Get event type from class name"""
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'aggregate_id': self.aggregate_id,
            'occurred_at': self.occurred_at.isoformat(),
            'event_version': self.event_version,
            'event_data': self.event_data
        }
    
    def __repr__(self):
        return f'{self.event_type}(id={self.event_id}, aggregate_id={self.aggregate_id})'