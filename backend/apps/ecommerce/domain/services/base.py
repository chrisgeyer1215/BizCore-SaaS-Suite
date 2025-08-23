import re
from .base import ValueObject


class SKU(ValueObject):
    """Stock Keeping Unit value object"""
    
    def __init__(self, value: str):
        if not value or not isinstance(value, str):
            raise ValueError("SKU value must be a non-empty string")
        
        # Normalize SKU (uppercase, remove extra spaces)
        normalized = value.strip().upper()
        
        if not self._is_valid_format(normalized):
            raise ValueError(f"Invalid SKU format: {value}")
        
        super().__init__(value=normalized)
        object.__setattr__(self, '_initialized', True)
    
    @staticmethod
    def _is_valid_format(sku: str) -> bool:
        """Validate SKU format (customize as needed)"""
        # Allow alphanumeric characters, hyphens, and underscores
        pattern = r'^[A-Z0-9\-_]{3,50}$'
        return re.match(pattern, sku) is not None
    
    @property
    def value(self) -> str:
        return self.__dict__['value']
    
    def __str__(self):
        return self.value
    
    @classmethod
    def generate(cls, prefix: str, category: str, variant: str) -> 'SKU':
        """Generate SKU from components"""
        sku_value = f"{prefix}-{category}-{variant}"
        return cls(sku_value)


class ProductSKU(SKU):
    """Specialized SKU for products with additional validation"""
    
    def __init__(self, value: str):
        super().__init__(value)
        
        if not self._is_product_sku(self.value):
            raise ValueError(f"Invalid product SKU format: {value}")
    
    @staticmethod
    def _is_product_sku(sku: str) -> bool:
        """Additional validation for product SKUs"""
        # Products should have at least one hyphen
        return '-' in sku and len(sku.split('-')) >= 2