# apps/inventory/tests/conftest.py
import pytest
import numpy as np
import pandas as pd
from decimal import Decimal
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from apps.core.models import Tenant
from ..factories import *
from ..ml.model_registry import ModelRegistry
from ..services.stock.movement_service import StockMovementService

@pytest.fixture(scope='session')
def django_db_setup():
    """Setup test database."""
    pass

@pytest.fixture
def tenant():
    """Create test tenant."""
    return TenantFactory()

@pytest.fixture
def user(tenant):
    """Create test user."""
    return UserFactory(tenant=tenant)

@pytest.fixture
def admin_user(tenant):
    """Create admin user."""
    return UserFactory(tenant=tenant, is_staff=True, is_superuser=True)

@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()

@pytest.fixture
def authenticated_client(api_client, user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def sample_products(tenant):
    """Create sample products for testing."""
    category = CategoryFactory(tenant=tenant)
    brand = BrandFactory(tenant=tenant)
    supplier = SupplierFactory(tenant=tenant)
    
    products = []
    for i in range(10):
        product = ProductFactory(
            tenant=tenant,
            category=category,
            brand=brand,
            supplier=supplier,
            name=f"Test Product {i+1}",
            sku=f"TEST{i+1:03d}",
            cost_price=Decimal(f"{50 + i * 10}.00"),
            selling_price=Decimal(f"{75 + i * 15}.00")
        )
        products.append(product)
    
    return products

@pytest.fixture
def sample_stock_items(sample_products):
    """Create sample stock items."""
    warehouse = WarehouseFactory(tenant=sample_products[0].tenant)
    location = StockLocationFactory(warehouse=warehouse)
    
    stock_items = []
    for product in sample_products:
        stock_item = StockItemFactory(
            tenant=product.tenant,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity_on_hand=Decimal(f"{100 + np.random.randint(0, 200)}")
        )
        stock_items.append(stock_item)
    
    return stock_items

@pytest.fixture
def ml_test_data():
    """Create ML test data."""
    # Generate synthetic demand data
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    np.random.seed(42)  # Reproducible results
    
    # Simulate seasonal demand with trend and noise
    base_demand = 50
    trend = np.linspace(0, 20, len(dates))
    seasonal = 10 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    noise = np.random.normal(0, 5, len(dates))
    
    demand = base_demand + trend + seasonal + noise
    demand = np.maximum(demand, 0)  # No negative demand
    
    return pd.DataFrame({
        'date': dates,
        'product_id': 1,
        'warehouse_id': 1,
        'demand': demand
    })

@pytest.fixture
def mock_ml_model():
    """Mock ML model for testing."""
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([10.5, 11.2, 9.8, 12.1, 10.0])
    mock_model.predict_with_confidence.return_value = (
        np.array([10.5, 11.2, 9.8, 12.1, 10.0]),  # predictions
        np.array([8.0, 8.5, 7.5, 9.2, 7.8]),      # lower bounds
        np.array([13.0, 13.9, 12.1, 15.0, 12.2])  # upper bounds
    )
    mock_model.is_trained = True
    mock_model.model_name = 'MockModel'
    mock_model.performance_metrics = {
        'mae': 2.15,
        'mse': 6.43,
        'rmse': 2.54,
        'mape': 8.7,
        'r2': 0.89
    }
    return mock_model

@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing."""
    with patch('django.utils.timezone.now') as mock_now:
        mock_now.return_value = timezone.make_aware(
            datetime(2024, 1, 15, 12, 0, 0)
        )
        yield mock_now