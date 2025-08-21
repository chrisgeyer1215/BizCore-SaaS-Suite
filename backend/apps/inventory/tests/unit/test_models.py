# apps/inventory/tests/unit/test_models.py
import pytest
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from ...models.catalog.products import Product
from ...models.stock.items import StockItem
from ...models.stock.movements import StockMovement
from ..factories import *

@pytest.mark.django_db
class TestProduct:
    """Test Product model functionality."""
    
    def test_product_creation(self, tenant):
        """Test basic product creation."""
        category = CategoryFactory(tenant=tenant)
        product = ProductFactory(
            tenant=tenant,
            category=category,
            name="Test Product",
            sku="TEST001",
            cost_price=Decimal('50.00'),
            selling_price=Decimal('75.00')
        )
        
        assert product.tenant == tenant
        assert product.name == "Test Product"
        assert product.sku == "TEST001"
        assert product.profit_margin == Decimal('25.00')
        assert product.margin_percentage == Decimal('33.33')
    
    def test_sku_uniqueness_per_tenant(self, tenant):
        """Test SKU uniqueness within tenant."""
        category = CategoryFactory(tenant=tenant)
        
        # First product should create successfully
        product1 = ProductFactory(
            tenant=tenant,
            category=category,
            sku="UNIQUE001"
        )
        
        # Second product with same SKU should fail
        with pytest.raises(IntegrityError):
            ProductFactory(
                tenant=tenant,
                category=category,
                sku="UNIQUE001"
            )
    
    def test_sku_can_be_same_across_tenants(self):
        """Test SKU can be same across different tenants."""
        tenant1 = TenantFactory()
        tenant2 = TenantFactory()
        
        category1 = CategoryFactory(tenant=tenant1)
        category2 = CategoryFactory(tenant=tenant2)
        
        # Same SKU in different tenants should work
        product1 = ProductFactory(
            tenant=tenant1,
            category=category1,
            sku="SHARED001"
        )
        
        product2 = ProductFactory(
            tenant=tenant2,
            category=category2,
            sku="SHARED001"
        )
        
        assert product1.sku == product2.sku
        assert product1.tenant != product2.tenant
    
    def test_profit_calculations(self, tenant):
        """Test profit margin calculations."""
        product = ProductFactory(
            tenant=tenant,
            cost_price=Decimal('100.00'),
            selling_price=Decimal('150.00')
        )
        
        assert product.profit_margin == Decimal('50.00')
        assert product.margin_percentage == Decimal('33.33')
        
        # Test zero selling price
        product.selling_price = Decimal('0.00')
        assert product.margin_percentage == Decimal('0.00')
    
    def test_product_validation(self, tenant):
        """Test product field validation."""
        category = CategoryFactory(tenant=tenant)
        
        # Test negative prices
        with pytest.raises(ValidationError):
            product = ProductFactory.build(
                tenant=tenant,
                category=category,
                cost_price=Decimal('-10.00')
            )
            product.full_clean()
        
        # Test selling price lower than cost
        product = ProductFactory.build(
            tenant=tenant,
            category=category,
            cost_price=Decimal('100.00'),
            selling_price=Decimal('50.00')
        )
        # Should not raise error but might trigger warnings
        product.full_clean()
    
    def test_product_str_representation(self, tenant):
        """Test string representation."""
        product = ProductFactory(
            tenant=tenant,
            name="Test Product",
            sku="TEST001"
        )
        
        expected = "Test Product (TEST001)"
        assert str(product) == expected
    
    def test_product_total_stock_calculation(self, tenant):
        """Test total stock calculation across warehouses."""
        product = ProductFactory(tenant=tenant)
        warehouse1 = WarehouseFactory(tenant=tenant)
        warehouse2 = WarehouseFactory(tenant=tenant)
        
        # Create stock items in different warehouses
        StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse1,
            quantity_on_hand=Decimal('50.0000')
        )
        
        StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse2,
            quantity_on_hand=Decimal('30.0000')
        )
        
        assert product.total_stock == Decimal('80.0000')
    
    @pytest.mark.parametrize("abc_class,expected_priority", [
        ('A', 1),
        ('B', 2),
        ('C', 3),
        (None, 4)
    ])
    def test_abc_classification_priority(self, tenant, abc_class, expected_priority):
        """Test ABC classification priority ordering."""
        product = ProductFactory(
            tenant=tenant,
            abc_classification=abc_class
        )
        
        assert product.get_priority_score() == expected_priority

@pytest.mark.django_db
class TestStockItem:
    """Test StockItem model functionality."""
    
    def test_stock_item_creation(self, tenant):
        """Test basic stock item creation."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        stock_item = StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            quantity_on_hand=Decimal('100.0000')
        )
        
        assert stock_item.quantity_available == Decimal('100.0000')
        assert stock_item.total_value == stock_item.quantity_on_hand * stock_item.unit_cost
    
    def test_quantity_available_calculation(self, tenant):
        """Test available quantity calculation."""
        stock_item = StockItemFactory(
            tenant=tenant,
            quantity_on_hand=Decimal('100.0000'),
            quantity_reserved=Decimal('25.0000')
        )
        
        assert stock_item.quantity_available == Decimal('75.0000')
    
    def test_stock_item_uniqueness(self, tenant):
        """Test stock item uniqueness per product-warehouse-location."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # First stock item should create successfully
        stock_item1 = StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            location=location
        )
        
        # Second stock item for same combination should fail
        with pytest.raises(IntegrityError):
            StockItemFactory(
                tenant=tenant,
                product=product,
                warehouse=warehouse,
                location=location
            )
    
    def test_negative_quantity_validation(self, tenant):
        """Test negative quantity validation."""
        stock_item = StockItemFactory.build(
            tenant=tenant,
            quantity_on_hand=Decimal('-10.0000')
        )
        
        with pytest.raises(ValidationError):
            stock_item.full_clean()
    
    def test_stock_valuation_methods(self, tenant):
        """Test different stock valuation methods."""
        stock_item = StockItemFactory(
            tenant=tenant,
            valuation_method='FIFO',
            unit_cost=Decimal('10.00'),
            average_cost=Decimal('12.00')
        )
        
        # FIFO should use unit_cost
        assert stock_item.get_valuation_cost() == Decimal('10.00')
        
        # Change to average cost
        stock_item.valuation_method = 'AVERAGE'
        assert stock_item.get_valuation_cost() == Decimal('12.00')

@pytest.mark.django_db
class TestStockMovement:
    """Test StockMovement model functionality."""
    
    def test_stock_movement_creation(self, tenant):
        """Test basic stock movement creation."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        user = UserFactory(tenant=tenant)
        
        movement = StockMovementFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            movement_type='RECEIPT',
            quantity=Decimal('50.0000'),
            unit_cost=Decimal('10.00'),
            user=user
        )
        
        assert movement.total_cost == Decimal('500.00')
        assert movement.is_inbound_movement() is True
        assert movement.is_outbound_movement() is False
    
    @pytest.mark.parametrize("movement_type,is_inbound", [
        ('RECEIPT', True),
        ('ADJUSTMENT_IN', True),
        ('TRANSFER_IN', True),
        ('SALE', False),
        ('ADJUSTMENT_OUT', False),
        ('TRANSFER_OUT', False),
    ])
    def test_movement_direction(self, tenant, movement_type, is_inbound):
        """Test movement direction classification."""
        movement = StockMovementFactory(
            tenant=tenant,
            movement_type=movement_type
        )
        
        assert movement.is_inbound_movement() == is_inbound
        assert movement.is_outbound_movement() == (not is_inbound)
    
    def test_movement_reference_generation(self, tenant):
        """Test automatic reference generation."""
        movement = StockMovementFactory(tenant=tenant)
        
        # Reference should be auto-generated if not provided
        assert movement.reference is not None
        assert len(movement.reference) > 0
    
    def test_movement_cost_calculation(self, tenant):
        """Test total cost calculation."""
        movement = StockMovementFactory(
            tenant=tenant,
            quantity=Decimal('25.5000'),
            unit_cost=Decimal('12.50')
        )
        
        expected_cost = Decimal('318.75')
        assert movement.total_cost == expected_cost