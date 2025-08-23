from abc import ABC
from typing import Any


class ValueObject(ABC):
    """Base class for all value objects"""
    
    def __init__(self, **kwargs):
        # Make value objects immutable
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)
    
    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, '_initialized'):
            raise AttributeError(f"Cannot modify immutable value object {self.__class__.__name__}")
        super().__setattr__(name, value)
    
    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"Cannot delete from immutable value object {self.__class__.__name__}")
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self):
        attrs = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'{self.__class__.__name__}({attrs})'
    
    def to_dict(self) -> dict:
        """Convert value object to dictionary"""
        return self.__dict__.copy()
    
    @classmethod
    def from_dict("""
        return cls(**data)