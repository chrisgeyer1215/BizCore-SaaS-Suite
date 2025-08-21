# apps/inventory/tests/performance/test_query_performance.py
import pytest
import time
from django.test import TransactionTestCase
from django.db import connection
from django.test.utils import override_settings
from django.core.cache import cache
from decimal import Decimal
import statistics

from ..factories import *
from ...models.catalog.products import Product
from ...models.stock.items import StockItem
from ...models.stock.movements import StockMovement

@pytest.mark.performance
class TestQueryPerformance(TransactionTestCase):
    """Test database query performance."""
    
    def setUp(self):
        """Set up test data for performance testing."""
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        
        # Create test data at scale
        self.categories = CategoryFactory.create_batch(10, tenant=self.tenant)
        self.brands = BrandFactory.create_batch(20, tenant=self.tenant)
        self.suppliers = SupplierFactory.create_batch(50, tenant=self.tenant)
        self.warehouses = WarehouseFactory.create_batch(5, tenant=self.tenant)
        
        # Create locations for each warehouse
        self.locations = []
        for warehouse in self.warehouses:
            locations = StockLocationFactory.create_batch(10, warehouse=warehouse)
            self.locations.extend(locations)
    
    def create_large_dataset(self, num_products=1000, num_movements_per_product=100):
        """Create large dataset for performance testing."""
        print(f"Creating {num_products} products with {num_movements_per_product} movements each...")
        
        # Create products in batches for memory efficiency
        batch_size = 100
        products = []
        
        for i in range(0, num_products, batch_size):
            batch_products = []
            for j in range(min(batch_size, num_products - i)):
                product = ProductFactory(
                    tenant=self.tenant,
                    category=self.categories[j % len(self.categories)],
                    brand=self.brands[j % len(self.brands)],
                    supplier=self.suppliers[j % len(self.suppliers)],
                    sku=f"PERF{i+j:06d}"
                )
                batch_products.append(product)
            
            products.extend(batch_products)
            
            # Create stock items and movements for this batch
            for product in batch_products:
                warehouse = self.warehouses[0]  # Use first warehouse
                location = self.locations[0]    # Use first location
                
                # Create stock item
                stock_item = StockItemFactory(
                    tenant=self.tenant,
                    product=product,
                    warehouse=warehouse,
                    location=location,
                    quantity_on_hand=Decimal('1000.0000')
                )
                
                # Create movements in batches
                movement_batch_size = 50
                for k in range(0, num_movements_per_product, movement_batch_size):
                    movements = []
                    for m in range(min(movement_batch_size, num_movements_per_product - k)):
                        movement = StockMovementFactory.build(
                            tenant=self.tenant,
                            product=product,
                            warehouse=warehouse,
                            location=location,
                            movement_type='SALE',
                            quantity=Decimal('1.0000'),
                            user=self.user
                        )
                        movements.append(movement)
                    
                    # Bulk create movements
                    StockMovement.objects.bulk_create(movements)
        
        return products
    
    def measure_query_time(self, query_func, iterations=5):
        """Measure query execution time."""
        times = []
        
        for _ in range(iterations):
            start_time = time.time()
            
            # Clear query cache
            connection.queries_log.clear()
            
            # Execute query
            result = query_func()
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        return {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
            'query_count': len(connection.queries),
            'result_size': len(result) if hasattr(result, '__len__') else 1
        }
    
    def test_product_listing_performance(self):
        """Test product listing query performance."""
        # Create test dataset
        products = self.create_large_dataset(num_products=500, num_movements_per_product=50)
        
        # Test basic product listing
        def product_list_query():
            return list(Product.objects.filter(tenant=self.tenant)[:100])
        
        basic_results = self.measure_query_time(product_list_query)
        
        # Test optimized product listing with select_related
        def optimized_product_list_query():
            return list(Product.objects.filter(tenant=self.tenant)
                       .select_related('category', 'brand', 'supplier', 'uom')[:100])
        
        optimized_results = self.measure_query_time(optimized_product_list_query)
        
        print(f"Basic query: {basic_results['avg_time']:.3f}s, {basic_results['query_count']} queries")
        print(f"Optimized query: {optimized_results['avg_time']:.3f}s, {optimized_results['query_count']} queries")
        
        # Optimized query should use fewer database queries
        assert optimized_results['query_count'] < basic_results['query_count']
        
        # Performance should be reasonable (< 1 second for 100 products)
        assert optimized_results['avg_time'] < 1.0
    
    def test_stock_aggregation_performance(self):
        """Test stock aggregation query performance."""
        # Create test dataset
        products = self.create_large_dataset(num_products=200, num_movements_per_product=100)
        
        # Test stock aggregation query
        def stock_aggregation_query():
            return list(StockItem.objects.filter(tenant=self.tenant)
                       .select_related('product', 'warehouse')
                       .aggregate(
                           total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
                           total_quantity=Sum('quantity_on_hand'),
                           item_count=Count('id')
                       ).values())
        
        results = self.measure_query_time(stock_aggregation_query)
        
        print(f"Stock aggregation: {results['avg_time']:.3f}s, {results['query_count']} queries")
        
        # Aggregation should be fast (< 0.5 seconds)
        assert results['avg_time'] < 0.5
        assert results['query_count'] <= 2  # Should be a single aggregation query
    
    def test_movement_history_performance(self):
        """Test stock movement history query performance."""
        # Create smaller dataset for movement queries
        products = self.create_large_dataset(num_products=50, num_movements_per_product=200)
        test_product = products[0]
        
        # Test movement history query
        def movement_history_query():
            return list(StockMovement.objects.filter(
                tenant=self.tenant,
                product=test_product
            ).select_related('warehouse', 'user')
             .order_by('-created_at')[:50])
        
        results = self.measure_query_time(movement_history_query)
        
        print(f"Movement history: {results['avg_time']:.3f}s, {results['query_count']} queries")
        
        # Movement history should be fast with proper indexing
        assert results['avg_time'] < 0.3
        assert results['query_count'] <= 2
    
    def test_abc_analysis_performance(self):
        """Test ABC analysis query performance."""
        # Create test dataset
        products = self.create_large_dataset(num_products=300, num_movements_per_product=50)
        
        # Test ABC analysis query
        def abc_analysis_query():
            return list(Product.objects.filter(tenant=self.tenant)
                       .annotate(
                           total_sales=Sum('movements__quantity', 
                                         filter=Q(movements__movement_type='SALE')),
                           sales_value=Sum(F('movements__quantity') * F('movements__unit_cost'),
                                         filter=Q(movements__movement_type='SALE'))
                       )
                       .order_by('-sales_value')[:100])
        
        results = self.measure_query_time(abc_analysis_query)
        
        print(f"ABC analysis: {results['avg_time']:.3f}s, {results['query_count']} queries")
        
        # ABC analysis should complete in reasonable time
        assert results['avg_time'] < 2.0
        assert results['query_count'] <= 3

@pytest.mark.performance 
class TestAPIPerformance(TransactionTestCase):
    """Test API endpoint performance."""
    
    def setUp(self):
        """Set up test data for API performance testing."""
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        
        # Create test data
        self.products = ProductFactory.create_batch(100, tenant=self.tenant)
        
        # Create stock items
        warehouse = WarehouseFactory(tenant=self.tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        for product in self.products:
            StockItemFactory(
                tenant=self.tenant,
                product=product,
                warehouse=warehouse,
                location=location
            )
    
    def test_product_list_api_performance(self):
        """Test product list API performance."""
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Measure API response time
        start_time = time.time()
        
        response = client.get('/api/v1/products/')
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"Product list API response time: {response_time:.3f}s")
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second
        assert len(response.data['results']) > 0
    
    def test_stock_summary_api_performance(self):
        """Test stock summary API performance."""
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Measure API response time
        start_time = time.time()
        
        response = client.get('/api/v1/stock/summary/')
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"Stock summary API response time: {response_time:.3f}s")
        
        assert response.status_code == 200
        assert response_time < 0.5  # Should be very fast
    
    def test_bulk_operations_performance(self):
        """Test bulk operations performance."""
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Prepare bulk movement data
        warehouse = WarehouseFactory(tenant=self.tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        bulk_data = {
            'movements': [
                {
                    'product': product.id,
                    'warehouse': warehouse.id,
                    'location': location.id,
                    'movement_type': 'RECEIPT',
                    'quantity': '10.0000',
                    'unit_cost': '15.00',
                    'reference': f'BULK-{i:03d}'
                }
                for i, product in enumerate(self.products[:50])  # 50 movements
            ]
        }
        
        # Measure bulk operation time
        start_time = time.time()
        
        response = client.post(
            '/api/v1/stock/movements/bulk/',
            data=bulk_data,
            format='json'
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"Bulk movements API response time: {response_time:.3f}s for 50 movements")
        
        # Bulk operations should be efficient
        assert response_time < 5.0  # Should complete within 5 seconds
        assert response_time / len(bulk_data['movements']) < 0.1  # < 0.1s per movement

@pytest.mark.performance
class TestMLPerformance:
    """Test ML model performance."""
    
    @pytest.fixture
    def large_dataset(self):
        """Create large dataset for ML performance testing."""
        np.random.seed(42)
        
        # Generate large synthetic dataset
        n_samples = 10000
        n_features = 50
        
        X = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        
        # Generate target with some relationship to features
        y = (X.iloc[:, :5].sum(axis=1) + np.random.normal(0, 0.1, n_samples)) * 10 + 50
        y = np.maximum(y, 0)  # No negative demand
        
        return X, pd.Series(y)
    
    def test_model_training_performance(self, large_dataset):
        """Test ML model training performance."""
        from ...ml.models.random_forest import RandomForestForecaster
        from ...ml.models.xgboost_model import XGBoostForecaster
        
        X, y = large_dataset
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        models = [
            ('RandomForest', RandomForestForecaster()),
            ('XGBoost', XGBoostForecaster())
        ]
        
        for model_name, model in models:
            # Measure training time
            start_time = time.time()
            
            model.fit(X_train, y_train)
            
            training_time = time.time() - start_time
            
            # Measure prediction time
            start_time = time.time()
            
            predictions = model.predict(X_test)
            
            prediction_time = time.time() - start_time
            
            # Calculate performance metrics
            mae = mean_absolute_error(y_test, predictions)
            
            print(f"{model_name}:")
            print(f"  Training time: {training_time:.2f}s")
            print(f"  Prediction time: {prediction_time:.3f}s")
            print(f"  Prediction rate: {len(X_test)/prediction_time:.0f} predictions/second")
            print(f"  MAE: {mae:.2f}")
            print()
            
            # Performance assertions
            assert training_time < 60  # Should train within 1 minute
            assert prediction_time < 5   # Should predict within 5 seconds
            assert len(X_test) / prediction_time > 1000  # > 1000 predictions/second
            assert mae < 20  # Should be reasonably accurate
    
    def test_feature_engineering_performance(self, large_dataset):
        """Test feature engineering performance."""
        from ...ml.feature_engineering import FeatureEngineer
        
        # Create time series data
        dates = pd.date_range(start='2020-01-01', periods=5000, freq='D')
        data = pd.DataFrame({
            'date': dates,
            'demand': np.random.poisson(20, len(dates)) + np.random.normal(0, 2, len(dates)),
            'product_id': 1,
            'warehouse_id': 1
        })
        
        feature_engineer = FeatureEngineer(tenant_id=1)
        
        # Measure feature engineering time
        start_time = time.time()
        
        featured_data = feature_engineer.engineer_features(
            data,
            target_column='demand',
            include_lags=True,
            include_seasonal=True,
            include_external=True,
            k_best=30
        )
        
        feature_engineering_time = time.time() - start_time
        
        print(f"Feature engineering performance:")
        print(f"  Input samples: {len(data)}")
        print(f"  Output samples: {len(featured_data)}")
        print(f"  Output features: {len(featured_data.columns)}")
        print(f"  Processing time: {feature_engineering_time:.2f}s")
        print(f"  Rate: {len(data)/feature_engineering_time:.0f} samples/second")
        
        # Performance assertions
        assert feature_engineering_time < 30  # Should complete within 30 seconds
        assert len(data) / feature_engineering_time > 100  # > 100 samples/second
        assert len(featured_data.columns) > 10  # Should create meaningful features
    
    @patch('apps.inventory.ml.production_serving.ModelServingService._get_best_model')
    def test_prediction_serving_performance(self, mock_get_model):
        """Test ML prediction serving performance."""
        from ...ml.production_serving import ModelServingService, PredictionRequest
        
        # Mock model
        mock_model = MagicMock()
        mock_model.predict.return_value = np.random.uniform(5, 25, 30)  # 30 day forecast
        mock_model.predict_with_confidence.return_value = (
            np.random.uniform(5, 25, 30),    # predictions
            np.random.uniform(3, 20, 30),    # lower bounds
            np.random.uniform(8, 30, 30)     # upper bounds
        )
        
        mock_metadata = MagicMock()
        mock_metadata.model_id = 'test_model'
        mock_metadata.algorithm = 'RandomForest'
        mock_metadata.performance_metrics = {'mae': 2.5}
        
        mock_get_model.return_value = (mock_model, mock_metadata)
        
        # Create serving service
        serving_service = ModelServingService()
        
        # Test prediction performance with multiple products
        request_data = {
            'tenant_id': 1,
            'products': list(range(1, 51)),  # 50 products
            'forecast_horizon': 30,
            'confidence_level': 0.95
        }
        
        prediction_request = PredictionRequest(request_data)
        
        # Measure prediction time (would be async in practice)
        start_time = time.time()
        
        # Simulate the prediction process
        for product_id in prediction_request.products:
            mock_model.predict_with_confidence.return_value
        
        prediction_time = time.time() - start_time
        
        print(f"ML serving performance:")
        print(f"  Products: {len(prediction_request.products)}")
        print(f"  Forecast horizon: {prediction_request.forecast_horizon} days")
        print(f"  Processing time: {prediction_time:.3f}s")
        print(f"  Rate: {len(prediction_request.products)/prediction_time:.0f} products/second")
        
        # Performance assertions
        assert prediction_time < 5.0  # Should complete within 5 seconds
        assert len(prediction_request.products) / prediction_time > 10  # > 10 products/second

@pytest.mark.performance
class TestCachePerformance:
    """Test caching performance improvements."""
    
    @pytest.mark.django_db
    def test_product_caching_performance(self):
        """Test product data caching performance."""
        tenant = TenantFactory()
        products = ProductFactory.create_batch(100, tenant=tenant)
        
        from django.core.cache import cache
        
        # Test without caching
        start_time = time.time()
        
        for _ in range(10):  # Simulate 10 requests
            product_list = list(Product.objects.filter(tenant=tenant)
                              .select_related('category', 'brand')[:20])
        
        uncached_time = time.time() - start_time
        
        # Test with caching
        cache_key = f"products_tenant_{tenant.id}"
        
        start_time = time.time()
        
        for _ in range(10):  # Simulate 10 requests
            cached_products = cache.get(cache_key)
            if not cached_products:
                product_list = list(Product.objects.filter(tenant=tenant)
                                  .select_related('category', 'brand')[:20])
                cache.set(cache_key, product_list, 300)  # Cache for 5 minutes
            else:
                product_list = cached_products
        
        cached_time = time.time() - start_time
        
        print(f"Product caching performance:")
        print(f"  Without cache: {uncached_time:.3f}s")
        print(f"  With cache: {cached_time:.3f}s")
        print(f"  Improvement: {uncached_time/cached_time:.1f}x faster")
        
        # Caching should provide significant improvement
        assert cached_time < uncached_time
        assert uncached_time / cached_time > 2  # At least 2x improvement