"""
Comprehensive tests for inventory models
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta

from apps.tenants.models import Tenant
from apps.inventory.models import (
    InventorySettings, UnitOfMeasure, Department, Category, SubCategory,
    Brand, Supplier, Warehouse, StockLocation, Product, StockItem,
    StockMovement, Batch, PurchaseOrder, PurchaseOrderItem, InventoryAlert
)


@pytest.mark.django_db
class TestInventoryModels(TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            schema_name="test_tenant"
        )
        
        self.settings = InventorySettings.objects.create(
            tenant=self.tenant,
            valuation_method='FIFO',
            enable_batch_tracking=True
        )
        
        self.unit = UnitOfMeasure.objects.create(
            tenant=self.tenant,
            name="Each",
            abbreviation="EA",
            unit_type="COUNT",
            is_base_unit=True
        )
        
        self.department = Department.objects.create(
            tenant=self.tenant,
            name="Electronics",
            code="ELEC",
            is_active=True
        )
        
        self.category = Category.objects.create(
            tenant=self.tenant,
            department=self.department,
            name="Computers",
            code="COMP",
            is_active=True
        )
        
        self.brand = Brand.objects.create(
            tenant=self.tenant,
            name="TechBrand",
            code="TB",
            is_active=True
        )
        
        self.supplier = Supplier.objects.create(
            tenant=self.tenant,
            name="Tech Supplier Inc",
            code="TS001",
            email="supplier@techsupplier.com",
            phone="555-1234",
            address_line1="123 Tech Street",
            city="Tech City",
            state="TS",
            country="USA",
            postal_code="12345"
        )
        
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name="Main Warehouse",
            code="WH001",
            address_line1="456 Warehouse Ave",
            city="Storage City",
            state="SC",
            country="USA",
            postal_code="67890",
            is_default=True
        )
        
        self.location = StockLocation.objects.create(
            tenant=self.tenant,
            warehouse=self.warehouse,
            name="A1-01-01",
            code="A1-01-01",
            zone="A",
            aisle="1",
            rack="01",
            shelf="01"
        )
    
    def test_inventory_settings_creation(self):
        """Test inventory settings creation"""
        self.assertEqual(self.settings.valuation_method, 'FIFO')
        self.assertTrue(self.settings.enable_batch_tracking)
        self.assertEqual(self.settings.tenant, self.tenant)
    
    def test_unit_of_measure_conversion(self):
        """Test unit of measure conversions"""
        # Create base unit (meters)
        base_unit = UnitOfMeasure.objects.create(
            tenant=self.tenant,
            name="Meter",
            abbreviation="M",
            unit_type="LENGTH",
            is_base_unit=True
        )
        
        # Create derived unit (centimeters)
        derived_unit = UnitOfMeasure.objects.create(
            tenant=self.tenant,
            name="Centimeter",
            abbreviation="CM",
            unit_type="LENGTH",
            base_unit=base_unit,
            conversion_factor=Decimal('0.01')
        )
        
        # Test conversion
        self.assertEqual(derived_unit.convert_to_base(100), Decimal('1.00'))
        self.assertEqual(derived_unit.convert_from_base(Decimal('1.00')), Decimal('100'))
    
    def test_department_hierarchy(self):
        """Test department hierarchy"""
        child_dept = Department.objects.create(
            tenant=self.tenant,
            name="Sub Electronics",
            code="SUB_ELEC",
            parent=self.department
        )
        
        self.assertEqual(child_dept.parent, self.department)
        self.assertIn(child_dept, self.department.children.all())
        self.assertIn("Electronics", child_dept.full_path)
    
    def test_product_creation(self):
        """Test product creation with all required fields"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="Test Laptop",
            sku="LAPTOP001",
            department=self.department,
            category=self.category,
            brand=self.brand,
            unit=self.unit,
            cost_price=Decimal('500.00'),
            selling_price=Decimal('800.00'),
            min_stock_level=Decimal('10'),
            reorder_point=Decimal('5'),
            reorder_quantity=Decimal('20')
        )
        
        self.assertEqual(product.name, "Test Laptop")
        self.assertEqual(product.sku, "LAPTOP001")
        self.assertEqual(product.margin_percentage, 37.5)  # (800-500)/800 * 100
        self.assertEqual(product.markup_percentage, 60.0)  # (800-500)/500 * 100
    
    def test_product_sku_uniqueness(self):
        """Test that SKU is unique per tenant"""
        Product.objects.create(
            tenant=self.tenant,
            name="Product 1",
            sku="PROD001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('100.00'),
            selling_price=Decimal('150.00')
        )
        
        # Try to create another product with same SKU - should raise integrity error
        with self.assertRaises(Exception):
            Product.objects.create(
                tenant=self.tenant,
                name="Product 2",
                sku="PROD001",  # Duplicate SKU
                department=self.department,
                category=self.category,
                unit=self.unit,
                cost_price=Decimal('200.00'),
                selling_price=Decimal('300.00')
            )
    
    def test_stock_item_operations(self):
        """Test stock item creation and operations"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="Test Product",
            sku="TEST001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('50.00'),
            selling_price=Decimal('75.00')
        )
        
        stock_item = StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            location=self.location,
            quantity_on_hand=Decimal('100'),
            quantity_available=Decimal('100'),
            unit_cost=Decimal('50.00'),
            average_cost=Decimal('50.00')
        )
        
        # Test stock reservation
        success = stock_item.reserve_stock(Decimal('10'), "Test reservation")
        self.assertTrue(success)
        self.assertEqual(stock_item.quantity_reserved, Decimal('10'))
        self.assertEqual(stock_item.quantity_available, Decimal('90'))
        
        # Test stock release
        success = stock_item.release_reservation(Decimal('5'), "Partial release")
        self.assertTrue(success)
        self.assertEqual(stock_item.quantity_reserved, Decimal('5'))
        self.assertEqual(stock_item.quantity_available, Decimal('95'))
        
        # Test insufficient stock reservation
        success = stock_item.reserve_stock(Decimal('200'), "Too much")
        self.assertFalse(success)
    
    def test_batch_tracking(self):
        """Test batch creation and tracking"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="Perishable Product",
            sku="PERISH001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            is_batch_tracked=True,
            is_perishable=True,
            cost_price=Decimal('25.00'),
            selling_price=Decimal('40.00')
        )
        
        batch = Batch.objects.create(
            tenant=self.tenant,
            product=product,
            batch_number="BATCH001",
            supplier=self.supplier,
            manufacture_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=30),
            initial_quantity=Decimal('50'),
            current_quantity=Decimal('50'),
            unit_cost=Decimal('25.00'),
            total_cost=Decimal('1250.00')
        )
        
        # Test batch properties
        self.assertFalse(batch.is_expired)
        self.assertTrue(batch.is_near_expiry)  # Expires in 30 days
        self.assertEqual(batch.available_quantity, Decimal('50'))
        self.assertEqual(batch.days_until_expiry, 30)
    
    def test_stock_movement_creation(self):
        """Test stock movement creation and tracking"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="Movement Test Product",
            sku="MOVE001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('30.00'),
            selling_price=Decimal('45.00')
        )
        
        stock_item = StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('100'),
            quantity_available=Decimal('100'),
            unit_cost=Decimal('30.00'),
            average_cost=Decimal('30.00')
        )
        
        # Create inbound movement
        movement = StockMovement.objects.create(
            tenant=self.tenant,
            stock_item=stock_item,
            movement_type='RECEIVE',
            movement_reason='PURCHASE_ORDER',
            quantity=Decimal('20'),
            unit_cost=Decimal('30.00'),
            stock_before=Decimal('100'),
            stock_after=Decimal('120')
        )
        
        self.assertTrue(movement.is_inbound)
        self.assertFalse(movement.is_outbound)
        self.assertEqual(movement.total_cost, Decimal('600.00'))
        self.assertEqual(movement.cost_impact, Decimal('600.00'))
    
    def test_purchase_order_workflow(self):
        """Test purchase order creation and workflow"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="PO Test Product",
            sku="PO001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            preferred_supplier=self.supplier,
            cost_price=Decimal('100.00'),
            selling_price=Decimal('150.00')
        )
        
        # Create purchase order
        po = PurchaseOrder.objects.create(
            tenant=self.tenant,
            supplier=self.supplier,
            delivery_warehouse=self.warehouse,
            order_date=date.today(),
            required_date=date.today() + timedelta(days=7),
            status='DRAFT'
        )
        
        # Create PO item
        po_item = PurchaseOrderItem.objects.create(
            tenant=self.tenant,
            purchase_order=po,
            product=product,
            quantity_ordered=Decimal('50'),
            unit=self.unit,
            unit_cost=Decimal('100.00')
        )
        
        # Test PO properties
        self.assertEqual(po.total_items, 1)
        self.assertEqual(po.total_quantity_ordered, Decimal('50'))
        self.assertEqual(po_item.total_amount, Decimal('5000.00'))
        self.assertEqual(po_item.pending_quantity, Decimal('50'))
        
        # Test receiving
        success, message = po_item.receive_quantity(
            quantity=Decimal('30'),
            user=None
        )
        
        self.assertTrue(success)
        self.assertEqual(po_item.quantity_received, Decimal('30'))
        self.assertEqual(po_item.pending_quantity, Decimal('20'))
        self.assertEqual(po_item.status, 'PARTIAL_RECEIVED')
    
    def test_inventory_alerts(self):
        """Test inventory alert creation"""
        product = Product.objects.create(
            tenant=self.tenant,
            name="Alert Test Product",
            sku="ALERT001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('20.00'),
            selling_price=Decimal('35.00'),
            reorder_point=Decimal('10')
        )
        
        # Create low stock alert
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_type='LOW_STOCK',
            severity='HIGH',
            title=f'Low Stock: {product.name}',
            message=f'Product {product.sku} is below reorder point',
            product=product,
            warehouse=self.warehouse
        )
        
        self.assertEqual(alert.alert_type, 'LOW_STOCK')
        self.assertEqual(alert.status, 'ACTIVE')
        self.assertTrue(alert.is_active)
    
    def test_supplier_validation(self):
        """Test supplier model validation"""
        # Test credit utilization
        self.supplier.credit_limit = Decimal('10000.00')
        self.supplier.credit_used = Decimal('7500.00')
        self.supplier.save()
        
        self.assertEqual(self.supplier.credit_available, Decimal('2500.00'))
        self.assertEqual(self.supplier.credit_utilization_percentage, Decimal('75.00'))
    
    def test_warehouse_default_constraint(self):
        """Test that only one warehouse can be default per tenant"""
        # Create another warehouse and set it as default
        new_warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name="Secondary Warehouse",
            code="WH002",
            address_line1="789 Storage Blvd",
            city="Storage City",
            state="SC",
            country="USA",
            postal_code="54321",
            is_default=True  # This should make the first warehouse non-default
        )
        
        # Refresh from database
        self.warehouse.refresh_from_db()
        
        # First warehouse should no longer be default
        self.assertFalse(self.warehouse.is_default)
        self.assertTrue(new_warehouse.is_default)


@pytest.mark.django_db
class TestInventoryBusinessLogic(TestCase):
    
    def setUp(self):
        """Set up test data for business logic tests"""
        self.tenant = Tenant.objects.create(
            name="Business Test Tenant",
            schema_name="business_test"
        )
        
        # Create basic setup
        self.unit = UnitOfMeasure.objects.create(
            tenant=self.tenant,
            name="Each",
            abbreviation="EA",
            unit_type="COUNT"
        )
        
        self.department = Department.objects.create(
            tenant=self.tenant,
            name="Test Dept",
            code="TD"
        )
        
        self.category = Category.objects.create(
            tenant=self.tenant,
            department=self.department,
            name="Test Cat",
            code="TC"
        )
        
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name="Test Warehouse",
            code="TW",
            address_line1="Test Address",
            city="Test City",
            state="TS",
            country="Test Country",
            postal_code="12345"
        )
        
        self.product = Product.objects.create(
            tenant=self.tenant,
            name="Business Test Product",
            sku="BIZ001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('50.00'),
            selling_price=Decimal('100.00'),
            reorder_point=Decimal('20'),
            min_stock_level=Decimal('30')
        )
    
    def test_stock_valuation_fifo(self):
        """Test FIFO stock valuation"""
        stock_item = StockItem.objects.create(
            tenant=self.tenant,
            product=self.product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('0'),
            quantity_available=Decimal('0'),
            unit_cost=Decimal('50.00'),
            average_cost=Decimal('50.00')
        )
        
        # Receive stock at different costs
        stock_item.receive_stock(Decimal('10'), Decimal('45.00'), 'First batch')
        stock_item.receive_stock(Decimal('10'), Decimal('55.00'), 'Second batch')
        
        # Stock should now be 20 units with weighted average cost
        self.assertEqual(stock_item.quantity_on_hand, Decimal('20'))
        self.assertEqual(stock_item.average_cost, Decimal('50.00'))  # (10*45 + 10*55) / 20
    
    def test_abc_classification_calculation(self):
        """Test ABC classification logic"""
        # Create multiple products with different values
        products_data = [
            ('PROD_A1', Decimal('1000')),  # High value - should be A
            ('PROD_A2', Decimal('800')),   # High value - should be A
            ('PROD_B1', Decimal('300')),   # Medium value - should be B
            ('PROD_C1', Decimal('100')),   # Low value - should be C
        ]
        
        products = []
        for sku,product = Product.objects.create(
                tenant=self.tenant,
                name=f"Product {sku}",
                sku=sku,
                department=self.department,
                category=self.category,
                unit=self.unit,
                cost_price=Decimal('50.00'),
                selling_price=Decimal('100.00')
            )
            
            StockItem.objects.create(
                tenant=self.tenant,
                product=product,
                warehouse=self.warehouse,
                quantity_on_hand=Decimal('10'),
                quantity_available=Decimal('10'),
                unit_cost=Decimal('50.00'),
                average_cost=Decimal('50.00'),
                total_value=value
            )
            
            products.append(product)
        
        # Calculate ABC classification
        from apps.inventory.services import AnalyticsService
        analytics = AnalyticsService(self.tenant)
        analytics.calculate_abc_analysis()
        
        # Verify classifications
        for product in products:
            product.refresh_from_db()
            if product.sku.startswith('PROD_A'):
                self.assertEqual(product.abc_classification, 'A')
            elif product.sku.startswith('PROD_B'):
                self.assertEqual(product.abc_classification, 'B')
            elif product.sku.startswith('PROD_C'):
                self.assertEqual(product.abc_classification, 'C')
    
    def test_reorder_point_logic(self):
        """Test reorder point and low stock detection"""
        stock_item = StockItem.objects.create(
            tenant=self.tenant,
            product=self.product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('25'),  # Above reorder point
            quantity_available=Decimal('25'),
            unit_cost=Decimal('50.00'),
            average_cost=Decimal('50.00')
        )
        
        # Should not be low stock
        self.assertFalse(stock_item.is_low_stock)
        
        # Reduce stock below reorder point
        stock_item.quantity_available = Decimal('15')  # Below reorder point of 20
        stock_item.save()
        
        # Should now be low stock
        self.assertTrue(stock_item.is_low_stock)
    
    def test_negative_stock_prevention(self):
        """Test negative stock prevention"""
        self.warehouse.allow_negative_stock = False
        self.warehouse.save()
        
        stock_item = StockItem.objects.create(
            tenant=self.tenant,
            product=self.product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('10'),
            quantity_available=Decimal('10'),
            unit_cost=Decimal('50.00'),
            average_cost=Decimal('50.00')
        )
        
        # Try to reserve more than available
        success = stock_item.reserve_stock(Decimal('15'), 'Over-reservation')
        self.assertFalse(success)
        
        # Try to reduce stock below zero
        with self.assertRaises(Exception):
            stock_item.adjust_stock(Decimal('-5'), 'Negative adjustment')


if __name__ == '__main__':
    pytest.main([__file__])
