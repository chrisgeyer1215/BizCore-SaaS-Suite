from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from decimal import Decimal

from ..entities.product import Product
from ..value_objects.sku import ProductSKU
from .base import Repository


class ProductVariantRepository(Repository):
    """Repository interface for Product Variants"""
    
    @abstractmethod
    def find_by_product_id(self, product_id: str) -> List[Dict[str, Any]]:
        """Find all variants for a product"""
        pass
    
    @abstractmethod
    def find_by_sku(self, sku: ProductSKU) -> Optional[Dict[str, Any]]:
        """Find variant by SKU"""
        pass
    
    @abstractmethod
    def find_available_variants(self, product_id: str) -> List[Dict[str, Any]]:
        """Find available variants for a product"""
        pass
    
    @abstractmethod
    def get_variant_options(self, product_id: str) -> Dict[str, List[str]]:
        """Get all variant options for a product"""
        pass
    
    @abstractmethod
    def find_by_option_combination(
        self,
        product_id: str,
        options: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Find variant by option combination"""
        pass


class ProductImageRepository(ABC):
    """Repository interface for Product Images"""
    
    @abstractmethod
    def find_by_product_id(self, product_id: str) -> List[Dict[str, Any]]:
        """Find all images for a product"""
        pass
    
    @abstractmethod
    def find_featured_image(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Find featured image for product"""
        pass
    
    @abstractmethod
    def save_image_metadata(self, image]) -> str:
        """Save image metadata and return image ID"""
        pass
    
    @abstractmethod
    def update_image_order(self, product_id: str, image_order: List[str]) -> None:
        """Update image display order"""
        pass


class ProductReviewRepository(ABC):
    """Repository interface for Product Reviews"""
    
    @abstractmethod
    def find_by_product_id(self, product_id: str, status: str = "APPROVED") -> List[Dict[str, Any]]:
        """Find reviews for a product"""
        pass
    
    @abstractmethod
    def get_review_statistics(self, product_id: str) -> Dict[str, Any]:
        """Get review statistics for product"""
        pass
    
    @abstractmethod
    def find_recent_reviews(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Find recent reviews across all products"""
        pass