"""
Product Query Handlers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ...domain.specifications.product_specifications import (
    ActiveProductsSpecification, PublishedProductsSpecification,
    InStockProductsSpecification, PriceRangeSpecification
)
from ...infrastructure.persistence.repositories.product_repository_impl import ProductRepositoryImpl
from ..dto.product_dto import ProductListDTO, ProductDetailDTO
from .base import BaseQueryHandler


@dataclass
class ProductListQuery:
    """Query for product list"""
    page: int = 1
    page_size: int = 24
    search: Optional[str] = None
    category_id: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort_by: str = 'created_at'
    sort_order: str = 'desc'
    in_stock_only: bool = False
    published_only: bool = True


@dataclass
class ProductDetailQuery:
    """Query for product detail"""
    product_id: Optional[str] = None
    sku: Optional[str] = None
    slug: Optional[str] = None
    include_variants: bool = True
    include_images: bool = True
    include_reviews: bool = True


class ProductQueryHandler(BaseQueryHandler):
    """Handler for product queries"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.repository = ProductRepositoryImpl(tenant)
    
    def handle_product_list(self, query: ProductListQuery) -> ProductListDTO:
        """Handle product list query"""
        try:
            # Build specifications
            specs = []
            
            if query.published_only:
                specs.append(PublishedProductsSpecification())
            
            if query.in_stock_only:
                specs.append(InStockProductsSpecification())
            
            if query.min_price or query.max_price:
                specs.append(PriceRangeSpecification(query.min_price, query.max_price))
            
            # Apply search and filters
            products = self.repository.find_by_criteria({
                'search': query.search,
                'category_id': query.category_id,
                'brand': query.brand,
                'specifications': specs,
                'sort_by': query.sort_by,
                'sort_order': query.sort_order,
                'page': query.page,
                'page_size': query.page_size
            })
            
            return ProductListDTO(
                products=products['items'],
                total_count=products['total'],
                page=query.page,
                page_size=query.page_size,
                has_next=products['has_next'],
                has_previous=products['has_previous']
            )
            
        except Exception as e:
            self.log_error("Failed to fetch product list", e)
            raise
    
    def handle_product_detail(self, query: ProductDetailQuery) -> ProductDetailDTO:
        """Handle product detail query"""
        try:
            # Find product by ID, SKU, or slug
            if query.product_id:
                product = self.repository.find_by_id(query.product_id)
            elif query.sku:
                product = self.repository.find_by_sku(query.sku)
            elif query.slug:
                product = self.repository.find_by_slug(query.slug)
            else:
                raise ValidationError("Product identifier required")
            
            if not product:
                raise NotFoundError("Product not found")
            
            # Build detailed DTO
            return ProductDetailDTO.from_entity(
                product,
                include_variants=query.include_variants,
                include_images=query.include_images,
                include_reviews=query.include_reviews
            )
            
        except Exception as e:
            self.log_error("Failed to fetch product detail", e)
            raise