"""
Create Product Use Case
"""

from typing import Dict, Any, Optional
from decimal import Decimal

from ...domain.entities.product import Product
from ...domain.value_objects.sku import SKU
from ...domain.value_objects.money import Money
from ...domain.events.product_events import ProductCreatedEvent
from ...domain.services.product_catalog_service import ProductCatalogService
from ...infrastructure.persistence.repositories.product_repository_impl import ProductRepositoryImpl
from ...infrastructure.messaging.publishers import EventPublisher
from ..dto.product_dto import CreateProductDTO, ProductResponseDTO
from .base import BaseUseCase


class CreateProductUseCase(BaseUseCase):
    """Use case for creating new products"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.product_repository = ProductRepositoryImpl(tenant)
        self.catalog_service = ProductCatalogService(tenant)
        self.event_publisher = EventPublisher(tenant)
    
    def execute(self, request user_id: Optional[str] = None) -> ProductResponseDTO:
        """Execute product creation use case"""
        try:
            # Create and validate DTO
            create_dto = CreateProductDTO(request_data)
            self.validate_input(create_dto)
            
            # Check business rules
            self.validate_business_rules(create_dto)
            
            # Create product entity
            product = self.create_product_entity(create_dto)
            
            # Save product
            saved_product = self.product_repository.save(product)
            
            # Publish domain event
            self.publish_product_created_event(saved_product, user_id)
            
            # Initialize AI features if requested
            if create_dto.enable_ai_features:
                self.initialize_ai_features(saved_product)
            
            return ProductResponseDTO.from_entity(saved_product)
            
        except Exception as e:
            self.log_error("Failed to create product", e, {
                'request_data': request_data,
                'user_id': user_id
            })
            raise self.handle_service_error(e, "create_product")
    
    def validate_input(self, dto: CreateProductDTO):
        """Validate input data"""
        errors = []
        
        # Required fields
        if not dto.title:
            errors.append("Title is required")
        
        if not dto.price or dto.price <= 0:
            errors.append("Price must be greater than 0")
        
        if dto.sku and not self.is_sku_unique(dto.sku):
            errors.append("SKU must be unique")
        
        if errors:
            raise ValidationError("Invalid product data", details={'errors': errors})
    
    def validate_business_rules(self, dto: CreateProductDTO):
        """Validate business rules"""
        # Check product limits for tenant
        if not self.catalog_service.can_add_product():
            raise ValidationError("Product limit exceeded for current plan")
        
        # Validate pricing rules
        if dto.compare_at_price and dto.compare_at_price <= dto.price:
            raise ValidationError("Compare at price must be greater than selling price")
    
    def create_product_entity(self, dto: CreateProductDTO) -> Product:
        """Create product domain entity"""
        # Generate SKU if not provided
        sku = SKU(dto.sku) if dto.sku else self.generate_unique_sku(dto.title)
        
        # Create money objects
        price = Money(dto.price, dto.currency or 'USD')
        compare_at_price = Money(dto.compare_at_price, dto.currency or 'USD') if dto.compare_at_price else None
        
        # Create product entity
        product = Product.create(
            title=dto.title,
            description=dto.description,
            sku=sku,
            price=price,
            compare_at_price=compare_at_price,
            brand=dto.brand,
            product_type=dto.product_type,
            weight=dto.weight,
            requires_shipping=dto.requires_shipping,
            track_quantity=dto.track_quantity,
            stock_quantity=dto.stock_quantity,
            tags=dto.tags,
            meta_title=dto.meta_title,
            meta_description=dto.meta_description
        )
        
        return product
    
    def is_sku_unique(self, sku: str) -> bool:
        """Check if SKU is unique"""
        existing = self.product_repository.find_by_sku(SKU(sku))
        return existing is None
    
    def generate_unique_sku(self, title: str) -> SKU:
        """Generate unique SKU from title"""
        base_sku = self.catalog_service.generate_sku_from_title(title)
        counter = 1
        
        while not self.is_sku_unique(base_sku):
            base_sku = f"{base_sku}-{counter}"
            counter += 1
        
        return SKU(base_sku)
    
    def publish_product_created_event(self, product: Product, user_id: Optional[str]):
        """Publish product created event"""
        event = ProductCreatedEvent(
            product_id=product.id,
            tenant_id=str(self.tenant.id),
            title=product.title,
            sku=str(product.sku),
            price=float(product.price.amount),
            user_id=user_id,
            timestamp=self.get_current_timestamp()
        )
        
        self.event_publisher.publish(event)
    
    def initialize_ai_features(self, product: Product):
        """Initialize AI features for new product"""
        # This would trigger AI analysis workflows
        from ...infrastructure.ai.recommendations.content_based import ContentBasedRecommender
        
        recommender = ContentBasedRecommender(self.tenant)
        recommender.analyze_new_product(product.id)