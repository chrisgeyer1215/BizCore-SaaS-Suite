# apps/inventory/tests/integration/test_api_endpoints.py
import pytest
import json
from decimal import Decimal
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User

from ..factories import *

@pytest.mark.django_db
class TestProductAPI:
    """Test Product API endpoints."""
    
    def test_list_products(self, authenticated_client, tenant):
        """Test product listing endpoint."""
        # Create test products
        ProductFactory.create_batch(5, tenant=tenant)
        
        url = reverse('api:v1:product-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 5
    
    def test_create_product(self, authenticated_client, tenant):
        """Test product creation endpoint."""
        category = CategoryFactory(tenant=tenant)
        brand = BrandFactory(tenant=tenant)
        uom = UnitOfMeasureFactory(tenant=tenant)
        
        url = reverse('api:v1:product-list')
        data = {
            'name': 'Test Product API',
            'sku': 'TESTAPI001',
            'description': 'Test product created via API',
            'category': category.id,
            'brand': brand.id,
            'uom': uom.id,
            'cost_price': '50.00',
            'selling_price': '75.00',
            'reorder_level': '10.0000',
            'max_stock_level': '100.0000'
        }
        
        response = authenticated_client.post(
            url, 
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Product API'
        assert response.data['sku'] == 'TESTAPI001'
    
    def test_get_product_detail(self, authenticated_client, tenant):
        """Test product detail endpoint."""
        product = ProductFactory(tenant=tenant)
        
        url = reverse('api:v1:product-detail', kwargs={'pk': product.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == product.id
        assert response.data['name'] == product.name
    
    def test_update_product(self, authenticated_client, tenant):
        """Test product update endpoint."""
        product = ProductFactory(tenant=tenant)
        
        url = reverse('api:v1:product-detail', kwargs={'pk': product.id})
        data = {
            'name': 'Updated Product Name',
            'selling_price': '99.99'
        }
        
        response = authenticated_client.patch(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Product Name'
        assert Decimal(response.data['selling_price']) == Decimal('99.99')
    
    def test_delete_product(self, authenticated_client, tenant):
        """Test product deletion endpoint."""
        product = ProductFactory(tenant=tenant)
        
        url = reverse('api:v1:product-detail', kwargs={'pk': product.id})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify product is deleted
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_product_filtering(self, authenticated_client, tenant):
        """Test product filtering functionality."""
        category1 = CategoryFactory(tenant=tenant, name='Electronics')
        category2 = CategoryFactory(tenant=tenant, name='Books')
        
        # Create products in different categories
        ProductFactory.create_batch(3, tenant=tenant, category=category1)
        ProductFactory.create_batch(2, tenant=tenant, category=category2)
        
        url = reverse('api:v1:product-list')
        
        # Filter by category
        response = authenticated_client.get(f"{url}?category={category1.id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3
        
        # Search by name
        response = authenticated_client.get(f"{url}?search=Electronics")
        assert response.status_code == status.HTTP_200_OK
    
    def test_product_ordering(self, authenticated_client, tenant):
        """Test product ordering functionality."""
        # Create products with different names
        ProductFactory(tenant=tenant, name='Apple Product')
        ProductFactory(tenant=tenant, name='Banana Product') 
        ProductFactory(tenant=tenant, name='Cherry Product')
        
        url = reverse('api:v1:product-list')
        
        # Test ascending order
        response = authenticated_client.get(f"{url}?ordering=name")
        assert response.status_code == status.HTTP_200_OK
        names = [item['name'] for item in response.data['results']]
        assert names == sorted(names)
        
        # Test descending order
        response = authenticated_client.get(f"{url}?ordering=-name")
        assert response.status_code == status.HTTP_200_OK
        names = [item['name'] for item in response.data['results']]
        assert names == sorted(names, reverse=True)

@pytest.mark.django_db
class TestStockMovementAPI:
    """Test Stock Movement API endpoints."""
    
    def test_create_stock_movement(self, authenticated_client, tenant, user):
        """Test stock movement creation via API."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create initial stock item
        StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity_on_hand=Decimal('50.0000')
        )
        
        url = reverse('api:v1:stockmovement-list')
        data = {
            'product': product.id,
            'warehouse': warehouse.id,
            'location': location.id,
            'movement_type': 'RECEIPT',
            'quantity': '25.0000',
            'unit_cost': '15.00',
            'reference': 'API-TEST-001'
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Decimal(response.data['quantity']) == Decimal('25.0000')
        
        # Verify stock was updated
        stock_item = product.stock_items.first()
        assert stock_item.quantity_on_hand == Decimal('75.0000')
    
    def test_bulk_stock_movements(self, authenticated_client, tenant, user):
        """Test bulk stock movements via API."""
        products = ProductFactory.create_batch(3, tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create stock items
        for product in products:
            StockItemFactory(
                tenant=tenant,
                product=product,
                warehouse=warehouse,
                location=location,
                quantity_on_hand=Decimal('100.0000')
            )
        
        url = reverse('api:v1:stockmovement-bulk-create')
        data = {
            'movements': [
                {
                    'product': product.id,
                    'warehouse': warehouse.id,
                    'location': location.id,
                    'movement_type': 'SALE',
                    'quantity': '10.0000',
                    'unit_cost': '20.00',
                    'reference': f'BULK-{i+1:03d}'
                }
                for i, product in enumerate(products)
            ]
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data['created']) == 3
        
        # Verify all stock items were updated
        for product in products:
            stock_item = product.stock_items.first()
            assert stock_item.quantity_on_hand == Decimal('90.0000')

@pytest.mark.django_db
class TestMLForecastingAPI:
    """Test ML Forecasting API endpoints."""
    
    @patch('apps.inventory.ml.production_serving.ModelServingService.predict')
    def test_demand_forecasting_endpoint(self, mock_predict, authenticated_client, tenant):
        """Test AI demand forecasting endpoint."""
        products = ProductFactory.create_batch(3, tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        # Mock the prediction service response
        mock_predict.return_value = {
            'status': 'success',
            'predictions': {
                str(products[0].id): {
                    'status': 'success',
                    'forecast': [
                        {
                            'date': '2024-01-16',
                            'predicted_demand': 12.5,
                            'confidence_lower': 8.2,
                            'confidence_upper': 16.8
                        }
                    ],
                    'summary': {
                        'total_forecasted_demand': 375.0,
                        'average_daily_demand': 12.5,
                        'peak_demand': 18.2
                    }
                }
            }
        }
        
        url = reverse('api:v1:ml-forecast')
        data = {
            'tenant_id': tenant.id,
            'products': [product.id for product in products],
            'warehouses': [warehouse.id],
            'forecast_horizon': 30,
            'confidence_level': 0.95
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'success'
        assert 'predictions' in response.data
    
    def test_ml_model_info_endpoint(self, authenticated_client, tenant):
        """Test ML model information endpoint."""
        url = reverse('api:v1:ml-models-info')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'models' in response.data

@pytest.mark.django_db
class TestWorkflowAPI:
    """Test Workflow Management API endpoints."""
    
    def test_purchase_order_approval_workflow(self, authenticated_client, tenant, user):
        """Test PO approval workflow via API."""
        supplier = SupplierFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        # Create PO
        po = PurchaseOrderFactory(
            tenant=tenant,
            supplier=supplier,
            warehouse=warehouse,
            status='PENDING_APPROVAL',
            total_amount=Decimal('5000.00')
        )
        
        url = reverse('api:v1:purchase-order-approve', kwargs={'pk': po.id})
        data = {
            'comments': 'Approved for procurement'
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'APPROVED'
        
        # Verify PO was updated
        po.refresh_from_db()
        assert po.status == 'APPROVED'
    
    def test_abc_analysis_workflow(self, authenticated_client, tenant):
        """Test ABC analysis workflow via API."""
        # Create products with movement data
        products = ProductFactory.create_batch(10, tenant=tenant)
        
        for i, product in enumerate(products):
            StockMovementFactory.create_batch(
                i + 1,
                tenant=tenant,
                product=product,
                movement_type='SALE',
                quantity=Decimal('10.0000')
            )
        
        url = reverse('api:v1:abc-analysis-run')
        data = {
            'analysis_name': 'API Test Analysis',
            'analysis_period_start': '2024-01-01',
            'analysis_period_end': '2024-12-31',
            'analysis_method': 'SALES_VALUE',
            'class_a_threshold': 80.0,
            'class_b_threshold': 95.0
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'analysis_id' in response.data

@pytest.mark.django_db
class TestAPIAuthentication:
    """Test API authentication and permissions."""
    
    def test_unauthenticated_access_denied(self, api_client):
        """Test that unauthenticated requests are denied."""
        url = reverse('api:v1:product-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_cross_tenant_access_denied(self, authenticated_client):
        """Test that cross-tenant access is denied."""
        # Create product in different tenant
        other_tenant = TenantFactory()
        product = ProductFactory(tenant=other_tenant)
        
        url = reverse('api:v1:product-detail', kwargs={'pk': product.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_admin_permissions(self, api_client, admin_user):
        """Test admin user permissions."""
        api_client.force_authenticate(user=admin_user)
        
        url = reverse('api:v1:product-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
class TestAPIValidation:
    """Test API input validation."""
    
    def test_product_creation_validation(self, authenticated_client, tenant):
        """Test product creation validation."""
        url = reverse('api:v1:product-list')
        
        # Test missing required fields
        data = {'name': 'Test Product'}
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'sku' in response.data
    
    def test_duplicate_sku_validation(self, authenticated_client, tenant):
        """Test duplicate SKU validation."""
        existing_product = ProductFactory(tenant=tenant, sku='DUPLICATE001')
        
        url = reverse('api:v1:product-list')
        data = {
            'name': 'Another Product',
            'sku': 'DUPLICATE001',
            'cost_price': '50.00',
            'selling_price': '75.00'
        }
        
        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST