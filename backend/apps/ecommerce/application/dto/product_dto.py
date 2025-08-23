"""
Product Data Transfer Objects
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime

from ...domain.entities.product import Product
from .base import BaseDTO


@dataclass
class CreateProductDTO(BaseDTO):
    """DTO for creating products"""
    title: str
    description: str
    price: float
    sku: Optional[str] = None
    brand: Optional[str] = None
    product_type: Optional[str] = None
    currency: str = 'USD'
    compare_at_price: Optional[float] = None
    weight: Optional[float] = None
    requires_shipping: bool = True
    track_quantity: bool = True
    stock_quantity: int = 0
    tags: List[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    enable_ai_features: bool = True
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class UpdateProductDTO(BaseDTO):
    """DTO for updating products"""
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    brand: Optional[str] = None
    product_type: Optional[str] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


@dataclass
class ProductResponseDTO(BaseDTO):
    """DTO for product responses"""
    id: str
    title: str
    description: str
    sku: str
    price: float
    currency: str
    compare_at_price: Optional[float]
    brand: Optional[str]
    product_type: Optional[str]
    is_active: bool
    is_published: bool
    stock_quantity: int
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_entity(cls, product: Product) -> 'ProductResponseDTO':
        """Create DTO from product entity"""
        return cls(
            id=str(product.id),
            title=product.title,
            description=product.description,
            sku=str(product.sku),
            price=float(product.price.amount),
            currency=product.price.currency,
            compare_at_price=float(product.compare_at_price.amount) if product.compare_at_price else None,
            brand=product.brand,
            product_type=product.product_type,
            is_active=product.is_active,
            is_published=product.is_published,
            stock_quantity=product.stock_quantity,
            created_at=product.created_at,
            updated_at=product.updated_at
        )


@dataclass
class ProductListDTO(BaseDTO):
    """DTO for product lists"""
    products: List[ProductResponseDTO]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
    
    @property
    def total_pages(self) -> int:
        """Calculate total pages"""
        return (self.total_count + self.page_size - 1) // self.page_size


@dataclass
class ProductDetailDTO(ProductResponseDTO):
    """DTO for detailed product information"""
    variants: Optional[List[Dict]] = None
    images: Optional[List[Dict]] = None
    reviews: Optional[List[Dict]] = None
    ai_features: Optional[Dict] = None
    specifications: Optional[Dict] = None
    
    @classmethod
    def from_entity(cls, product: Product, include_variants=True, 
                   include_images=True, include_reviews=True) -> 'ProductDetailDTO':
        """Create detailed DTO from product entity"""
        base_dto = ProductResponseDTO.from_entity(product)
        
        detail_data = asdict(base_dto)
        
        if include_variants and hasattr(product, 'variants'):
            detail_data['variants'] = [
                {
                    'id': str(variant.id),
                    'title': variant.title,
                    'sku': str(variant.sku),
                    'price': float(variant.price.amount),
                    'stock_quantity': variant.stock_quantity
                }
                for variant in product.variants
            ]
        
        if include_images and hasattr(product, 'images'):
            detail_data['images'] = [
                {
                    'id': str(image.id),
                    'url': image.url,
                    'alt_text': image.alt_text
                }
                for image in product.images
            ]
        
        if hasattr(product, 'ai_features'):
            detail_data['ai_features'] = {
                'performance_score': product.ai_features.performance_score,
                'recommendation_tags': product.ai_features.recommendation_tags,
                'demand_forecast': product.ai_features.demand_forecast
            }
        
        return cls(**detail_data)