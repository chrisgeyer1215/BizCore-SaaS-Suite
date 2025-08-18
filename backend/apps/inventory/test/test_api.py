"""
API endpoint tests for inventory management
"""

import pytest
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal
import json

from apps.tenants.models import Tenant
from apps.auth.models import Membership
from apps.inventory.models import (
    InventorySettings, UnitOfMeasure, Department, Category,
    Brand, Supplier, Warehouse, Product, StockItem
)

User = get_user_model()


@pytest.mark.django_db
class TestInventoryAPI(APITestCase):
    
    def setUp(self):
        """Set up test data"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="API Test Tenant",
            schema_name="api_test"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123"
        )
        
        # Create membership
        self.membership = Membership.objects.create(
            user=self.user,
            tenant=self.tenant,
            role='ADMIN',
            is_active=True
        )
        
        # Create basic test data
        self.unit = UnitOfMeasure.objects.create(
            tenant=self.tenant,
            name="Each",
            abbreviation="EA",
            unit_type="COUNT"
        )
        
        self.department = Department.objects.create(
            tenant=self.tenant,
            name="Electronics",
            code="ELEC"
        )
        
        self.category = Category.objects.create(
            tenant=self.tenant,
            department=self.department,
            name="Computers",
            code="COMP"
        )
        
        self.brand = Brand.objects.create(
            tenant=self.tenant,
            name="TechBrand",
            code="TB"
        )
        
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name="Main Warehouse",
            code="WH001",
            address_line1="123 Test St",
            city="Test City",
            state="TS",
            country="USA",
            postal_code="12345"
        )
        
        # Set tenant in request
        self.client.defaults['HTTP_HOST'] = f"{self.tenant.schema_name}.testserver"
    
    def authenticate(self):
        """Authenticate the test client"""
        self.client.force_authenticate(user=self.user)
        # Mock tenant middleware
        self.client.defaults['HTTP_X_TENANT_ID'] = str(self.tenant.id)
    
    def test_products_list_api(self):
        """Test products list API endpoint"""
        self.authenticate()
        
        # Create test products
        Product.objects.create(
            tenant=self.tenant,
            name="Test Laptop",
            sku="LAPTOP001",
            department=self.department,
            category=self.category,
            brand=self.brand,
            unit=self.unit,
            cost_price=Decimal('500.00'),
            selling_price=Decimal('800.00')
        )
        
        # Test GET request
        url = '/api/v1/inventory/products/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Laptop')
        self.assertEqual(response.data[0]['sku'], 'LAPTOP001')
    
    def test_products_create_api(self):
        """Test product creation via API"""
        self.authenticate()
        
        url = '/api/v1/inventory/products/'
        data = {
            'name': 'New Test Product',
            'sku': 'NEWPROD001',
            'department': self.department.id,
            'category': self.category.id,
            'brand': self.brand.id,
            'unit': self.unit.id,
            'cost_price': '100.00',
            'selling_price': '150.00',
            'description': 'Test product description',
            'status': 'ACTIVE',
            'is_saleable': True,
            'is_purchasable': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Test Product')
        self.assertEqual(response.data['sku'], 'NEWPROD001')
        
        # Verify product was created in database
        product = Product.objects.get(tenant=self.tenant, sku='NEWPROD001')
        self.assertEqual(product.name, 'New Test Product')
    
    def test_products_update_api(self):
        """Test product update via API"""
        self.authenticate()
        
        # Create product
        product = Product.objects.create(
            tenant=self.tenant,
            name="Update Test Product",
            sku="UPDATE001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('200.00'),
            selling_price=Decimal('300.00')
        )
        
        url = f'/api/v1/inventory/products/{product.id}/'
        data = {
            'name': 'Updated Product Name',
            'cost_price': '250.00',
            'selling_price': '350.00'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Product Name')
        
        # Verify database update
        product.refresh_from_db()
        self.assertEqual(product.name, 'Updated Product Name')
        self.assertEqual(product.cost_price, Decimal('250.00'))
    
    def test_products_stock_summary_api(self):
        """Test product stock summary API"""
        self.authenticate()
        
        # Create product and stock
        product = Product.objects.create(
            tenant=self.tenant,
            name="Stock Test Product",
            sku="STOCK001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('50.00'),
            selling_price=Decimal('75.00')
        )
        
        StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('100'),
            quantity_available=Decimal('80'),
            quantity_reserved=Decimal('20'),
            unit_cost=Decimal('50.00'),
            average_cost=Decimal('50.00'),
            total_value=Decimal('5000.00')
        )
        
        url = f'/api/v1/inventory/products/{product.id}/stock_summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('warehouse_stock', response.data)
        self.assertEqual(len(response.data['warehouse_stock']), 1)
        
        warehouse_stock = response.data['warehouse_stock'][0]
        self.assertEqual(warehouse_stock['total_stock'], 100)
        self.assertEqual(warehouse_stock['available_stock'], 80)
    
    def test_stock_adjustment_api(self):
        """Test stock adjustment API"""
        self.authenticate()
        
        # Create product and stock
        product = Product.objects.create(
            tenant=self.tenant,
            name="Adjust Test Product",
            sku="ADJUST001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('25.00'),
            selling_price=Decimal('40.00')
        )
        
        StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('50'),
            quantity_available=Decimal('50'),
            unit_cost=Decimal('25.00'),
            average_cost=Decimal('25.00')
        )
        
        url = f'/api/v1/inventory/products/{product.id}/adjust_stock/'
        data = {
            'warehouse_id': self.warehouse.id,
            'adjustment_type': 'INCREASE',
            'quantity': '25',
            'reason': 'Test adjustment'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['new_quantity'], 75)
        self.assertEqual(response.data['adjustment'], 25)
    
    def test_warehouses_api(self):
        """Test warehouses API endpoints"""
        self.authenticate()
        
        # Test list
        url = '/api/v1/inventory/warehouses/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Main Warehouse')
        
        # Test create
        data = {
            'name': 'Secondary Warehouse',
            'code': 'WH002',
            'warehouse_type': 'PHYSICAL',
            'address_line1': '456 Secondary St',
            'city': 'Second City',
            'state': 'SC',
            'country': 'USA',
            'postal_code': '54321',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Secondary Warehouse')
        self.assertEqual(response.data['code'], 'WH002')
    
    def test_warehouse_summary_api(self):
        """Test warehouse summary API"""
        self.authenticate()
        
        # Create product and stock in warehouse
        product = Product.objects.create(
            tenant=self.tenant,
            name="Warehouse Test Product",
            sku="WH_TEST001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('30.00'),
            selling_price=Decimal('45.00')
        )
        
        StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('200'),
            quantity_available=Decimal('200'),
            unit_cost=Decimal('30.00'),
            average_cost=Decimal('30.00'),
            total_value=Decimal('6000.00')
        )
        
        url = f'/api/v1/inventory/warehouses/{self.warehouse.id}/summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('stock_summary', response.data)
        self.assertEqual(response.data['stock_summary']['total_items'], 1)
        self.assertEqual(response.data['stock_summary']['total_value'], 6000)
    
    def test_dashboard_summary_api(self):
        """Test dashboard summary API"""
        self.authenticate()
        
        # Create test data
        product = Product.objects.create(
            tenant=self.tenant,
            name="Dashboard Test Product",
            sku="DASH001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('40.00'),
            selling_price=Decimal('60.00')
        )
        
        StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('150'),
            quantity_available=Decimal('150'),
            unit_cost=Decimal('40.00'),
            average_cost=Decimal('40.00'),
            total_value=Decimal('6000.00')
        )
        
        url = '/api/v1/inventory/dashboard/summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_products', response.data)
        self.assertIn('active_products', response.data)
        self.assertIn('total_stock_value', response.data)
        self.assertEqual(response.data['total_products'], 1)
        self.assertEqual(response.data['active_products'], 1)
        self.assertEqual(response.data['total_stock_value'], 6000)
    
    def test_low_stock_products_api(self):
        """Test low stock products API"""
        self.authenticate()
        
        # Create product with low stock
        product = Product.objects.create(
            tenant=self.tenant,
            name="Low Stock Product",
            sku="LOW001",
            department=self.department,
            category=self.category,
            unit=self.unit,
            cost_price=Decimal('20.00'),
            selling_price=Decimal('35.00'),
            reorder_point=Decimal('50')  # Set high reorder point
        )
        
        StockItem.objects.create(
            tenant=self.tenant,
            product=product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('30'),  # Below reorder point
            quantity_available=Decimal('30'),
            unit_cost=Decimal('20.00'),
            average_cost=Decimal('20.00')
        )
        
        url = '/api/v1/inventory/products/low_stock/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'LOW001')
    
    def test_stock_movements_api(self):
        """Test stock movements API"""
        self.authenticate()
        
        url = '/api/v1/inventory/stock-movements/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return empty list initially
        self.assertEqual(len(response.data), 0)
    
    def test_api_permissions(self):
        """Test API permissions without authentication"""
        # Don't authenticate - should get 401
        url = '/api/v1/inventory/products/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_tenant_isolation(self):
        """Test that API properly isolates tenant data"""
        self.authenticate()
        
        # Create another tenant with data
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            schema_name="other_tenant"
        )
        
        other_unit = UnitOfMeasure.objects.create(
            tenant=other_tenant,
            name="Each",
            abbreviation="EA",
            unit_type="COUNT"
        )
        
        other_department = Department.objects.create(
            tenant=other_tenant,
            name="Other Dept",
            code="OTHER"
        )
        
        other_category = Category.objects.create(
            tenant=other_tenant,
            department=other_department,
            name="Other Cat",
            code="OTHER"
        )
        
        # Create product in other tenant
        Product.objects.create(
            tenant=other_tenant,
            name="Other Tenant Product",
            sku="OTHER001",
            department=other_department,
            category=other_category,
            unit=other_unit,
            cost_price=Decimal('100.00'),
            selling_price=Decimal('150.00')
        )
        
        # Request products - should only see current tenant's data
        url = '/api/v1/inventory/products/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not see the other tenant's productself.assertNotEqual(product['sku'], 'OTHER001')


if __name__ == '__main__':
    pytest.main([__file__])
