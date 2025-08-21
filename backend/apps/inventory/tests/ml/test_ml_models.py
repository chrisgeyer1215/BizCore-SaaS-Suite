# apps/inventory/tests/ml/test_ml_models.py
import pytest
import numpy as np
import pandas as pd
from decimal import Decimal
from unittest.mock import patch, MagicMock
from sklearn.metrics import mean_absolute_error, mean_squared_error
import tempfile
import os

from ...ml.models.random_forest import RandomForestForecaster
from ...ml.models.xgboost_model import XGBoostForecaster
from ...ml.models.ensemble_model import EnsembleForecaster
from ...ml.feature_engineering import FeatureEngineer
from ...ml.model_registry import ModelRegistry, ModelMetadata
from ...ml.training_pipeline import TrainingPipeline, TrainingConfig
from ..factories import *

@pytest.mark.ml
class TestMLModels:
    """Test individual ML model functionality."""
    
    @pytest.fixture
    def sample_training_data(self):
        """Create sample training data for ML models."""
        np.random.seed(42)
        
        # Generate synthetic time series data
        dates = pd.date_range(start='2023-01-01', periods=365, freq='D')
        
        # Base demand with trend and seasonality
        base_demand = 50
        trend = np.linspace(0, 10, len(dates))
        seasonal = 15 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
        weekly_seasonal = 5 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
        noise = np.random.normal(0, 3, len(dates))
        
        demand = np.maximum(base_demand + trend + seasonal + weekly_seasonal + noise, 0)
        
        return pd.DataFrame({
            'date': dates,
            'demand': demand,
            'product_id': 1,
            'warehouse_id': 1
        })
    
    @pytest.fixture
    def engineered_features(self, sample_training_data, tenant):
        """Create engineered features for testing."""
        feature_engineer = FeatureEngineer(tenant.id)
        
        # Engineer features
        featured_data = feature_engineer.engineer_features(
            sample_training_data,
            target_column='demand',
            include_lags=True,
            include_seasonal=True,
            include_external=True,
            k_best=20
        )
        
        # Remove rows with NaN (due to lag features)
        featured_data = featured_data.dropna()
        
        return featured_data
    
    def test_random_forest_training_and_prediction(self, engineered_features):
        """Test Random Forest model training and prediction."""
        # Prepare data
        feature_columns = [col for col in engineered_features.columns 
                          if col not in ['demand', 'date', 'product_id', 'warehouse_id']]
        X = engineered_features[feature_columns]
        y = engineered_features['demand']
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Train model
        model = RandomForestForecaster()
        model.fit(X_train, y_train)
        
        assert model.is_trained is True
        assert len(model.feature_names) == len(feature_columns)
        
        # Make predictions
        predictions = model.predict(X_test)
        
        assert len(predictions) == len(X_test)
        assert all(pred >= 0 for pred in predictions)  # No negative demand
        
        # Check prediction accuracy
        mae = mean_absolute_error(y_test, predictions)
        assert mae < 20  # Should be reasonably accurate for synthetic data
        
        # Test feature importance
        importance = model.get_feature_importance()
        assert len(importance) == len(feature_columns)
        assert all(0 <= imp <= 1 for imp in importance.values())
    
    def test_xgboost_training_and_prediction(self, engineered_features):
        """Test XGBoost model training and prediction."""
        feature_columns = [col for col in engineered_features.columns 
                          if col not in ['demand', 'date', 'product_id', 'warehouse_id']]
        X = engineered_features[feature_columns]
        y = engineered_features['demand']
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Train XGBoost model
        model = XGBoostForecaster()
        model.fit(X_train, y_train)
        
        assert model.is_trained is True
        
        # Make predictions
        predictions = model.predict(X_test)
        
        assert len(predictions) == len(X_test)
        
        # Test prediction accuracy
        mae = mean_absolute_error(y_test, predictions)
        assert mae < 25  # XGBoost should also be reasonably accurate
    
    def test_ensemble_model_training(self, engineered_features):
        """Test Ensemble model combining multiple algorithms."""
        feature_columns = [col for col in engineered_features.columns 
                          if col not in ['demand', 'date', 'product_id', 'warehouse_id']]
        X = engineered_features[feature_columns]
        y = engineered_features['demand']
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Train ensemble model
        ensemble = EnsembleForecaster(
            models=['RandomForest', 'XGBoost'],
            ensemble_method='weighted_average'
        )
        
        ensemble.fit(X_train, y_train)
        
        assert ensemble.is_trained is True
        assert len(ensemble.base_models) >= 1  # At least one model should train
        
        # Make predictions
        predictions = ensemble.predict(X_test)
        
        assert len(predictions) == len(X_test)
        
        # Test prediction with confidence intervals
        pred, lower, upper = ensemble.predict_with_confidence(X_test, confidence_level=0.95)
        
        assert len(pred) == len(X_test)
        assert len(lower) == len(X_test)
        assert len(upper) == len(X_test)
        assert all(l <= p <= u for l, p, u in zip(lower, pred, upper))
        
        # Test model contributions
        contributions = ensemble.get_model_contributions(X_test)
        assert len(contributions) >= 1
    
    @patch('apps.inventory.ml.models.prophet_model.PROPHET_AVAILABLE', True)
    def test_prophet_model_training(self, sample_training_data):
        """Test Prophet model training."""
        from ...ml.models.prophet_model import ProphetForecaster
        
        # Prophet requires specific data format
        prophet_data = sample_training_data[['date', 'demand']].copy()
        
        model = ProphetForecaster()
        
        # Train model
        X = prophet_data[['date']]
        y = prophet_data['demand']
        
        model.fit(X, y)
        
        assert model.is_trained is True
        
        # Make predictions
        future_dates = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=30, freq='D')
        })
        
        predictions = model.predict(future_dates)
        
        assert len(predictions) == 30
        assert all(pred >= 0 for pred in predictions)
        
        # Test confidence intervals
        pred, lower, upper = model.predict_with_confidence(future_dates)
        
        assert all(l <= p <= u for l, p, u in zip(lower, pred, upper))

@pytest.mark.ml
class TestFeatureEngineering:
    """Test feature engineering functionality."""
    
    @pytest.fixture
    def raw_demand_data(self):
        """Create raw demand data for feature engineering."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        demand = 50 + 10 * np.sin(2 * np.pi * np.arange(len(dates)) / 7) + np.random.normal(0, 5, len(dates))
        demand = np.maximum(demand, 0)
        
        return pd.DataFrame({
            'date': dates,
            'product_id': 1,
            'warehouse_id': 1,
            'demand': demand
        })
    
    def test_time_feature_creation(self, raw_demand_data, tenant):
        """Test time-based feature creation."""
        feature_engineer = FeatureEngineer(tenant.id)
        
        # Create time features
        featured_data = feature_engineer.create_time_features(raw_demand_data)
        
        # Check that time features were added
        expected_features = [
            'year', 'month', 'day', 'day_of_week', 'day_of_year',
            'week_of_year', 'quarter', 'is_weekend', 'is_month_start',
            'is_month_end', 'is_holiday', 'month_sin', 'month_cos',
            'day_of_week_sin', 'day_of_week_cos'
        ]
        
        for feature in expected_features:
            assert feature in featured_data.columns
        
        # Validate feature ranges
        assert featured_data['month'].min() >= 1
        assert featured_data['month'].max() <= 12
        assert featured_data['day_of_week'].min() >= 0
        assert featured_data['day_of_week'].max() <= 6
        assert featured_data['is_weekend'].isin([0, 1]).all()
    
    def test_lag_feature_creation(self, raw_demand_data, tenant):
        """Test lag feature creation."""
        feature_engineer = FeatureEngineer(tenant.id)
        
        # Create lag features
        featured_data = feature_engineer.create_lag_features(
            raw_demand_data, 
            target_column='demand',
            lags=[1, 7, 14]
        )
        
        # Check lag features were created
        assert 'demand_lag_1' in featured_data.columns
        assert 'demand_lag_7' in featured_data.columns
        assert 'demand_lag_14' in featured_data.columns
        
        # Check rolling window features
        assert 'demand_rolling_mean_7' in featured_data.columns
        assert 'demand_rolling_std_7' in featured_data.columns
        
        # Validate lag relationships (where not NaN)
        valid_idx = ~featured_data['demand_lag_1'].isna()
        assert (featured_data.loc[valid_idx, 'demand_lag_1'] == 
                featured_data.loc[valid_idx, 'demand'].shift(1).dropna()).all()
    
    def test_seasonal_feature_creation(self, raw_demand_data, tenant):
        """Test seasonal feature creation."""
        feature_engineer = FeatureEngineer(tenant.id)
        
        # Add required time features first
        featured_data = feature_engineer.create_time_features(raw_demand_data)
        
        # Create seasonal features
        seasonal_data = feature_engineer.create_seasonal_features(
            featured_data, 
            target_column='demand'
        )
        
        # Check seasonal features were created
        assert 'monthly_seasonality' in seasonal_data.columns
        assert 'weekly_seasonality' in seasonal_data.columns
        assert 'yearly_trend' in seasonal_data.columns
        
        # Check Fourier features
        fourier_features = [col for col in seasonal_data.columns 
                          if 'fourier' in col]
        assert len(fourier_features) > 0
    
    def test_feature_scaling(self, raw_demand_data, tenant):
        """Test feature scaling functionality."""
        feature_engineer = FeatureEngineer(tenant.id)
        
        # Create some features first
        featured_data = feature_engineer.create_time_features(raw_demand_data)
        
        # Scale features
        scaled_data = feature_engineer.scale_features(featured_data, fit=True)
        
        # Check that numerical features were scaled
        numerical_columns = featured_data.select_dtypes(include=[np.number]).columns
        
        for col in numerical_columns:
            if col in scaled_data.columns:
                # Scaled features should have mean ~0 and std ~1
                assert abs(scaled_data[col].mean()) < 0.1
                assert abs(scaled_data[col].std() - 1.0) < 0.1
    
    def test_feature_selection(self, engineered_features):
        """Test feature selection functionality."""
        feature_columns = [col for col in engineered_features.columns 
                          if col not in ['demand', 'date', 'product_id', 'warehouse_id']]
        X = engineered_features[feature_columns]
        y = engineered_features['demand']
        
        # Mock FeatureEngineer for this test
        feature_engineer = FeatureEngineer(1)
        
        # Select top features
        selected_X = feature_engineer.select_features(X, y, method='k_best', k=10)
        
        assert selected_X.shape[1] == 10
        assert selected_X.shape[0] == X.shape[0]

@pytest.mark.ml
class TestModelRegistry:
    """Test ML model registry functionality."""
    
    @pytest.fixture
    def temp_registry(self):
        """Create temporary model registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ModelRegistry(temp_dir)
            yield registry
    
    @pytest.fixture
    def sample_model(self):
        """Create a sample trained model."""
        model = RandomForestForecaster()
        
        # Create mock training data
        X = pd.DataFrame(np.random.rand(100, 5), columns=[f'feature_{i}' for i in range(5)])
        y = pd.Series(np.random.rand(100) * 50 + 25)
        
        model.fit(X, y)
        return model
    
    def test_model_registration(self, temp_registry, sample_model):
        """Test model registration in registry."""
        metadata = ModelMetadata(
            model_id='',
            model_name='test_random_forest',
            version='1.0.0',
            algorithm='RandomForest',
            parameters={'n_estimators': 100},
            training_data_hash='abc123',
            feature_names=['feature_0', 'feature_1', 'feature_2', 'feature_3', 'feature_4'],
            performance_metrics={'mae': 2.5, 'r2': 0.85},
            training_timestamp=datetime.now(),
            model_size_bytes=0,
            python_version='3.9.0',
            dependencies={'scikit-learn': '1.0.0'},
            created_by='test_user',
            tags=['test', 'random_forest'],
            description='Test model',
            status='training'
        )
        
        # Register model
        model_id = temp_registry.register_model(sample_model, metadata)
        
        assert model_id is not None
        assert len(model_id) > 0
        
        # Verify model can be retrieved
        loaded_model, loaded_metadata = temp_registry.get_model(model_id)
        
        assert loaded_metadata.model_name == 'test_random_forest'
        assert loaded_metadata.algorithm == 'RandomForest'
        assert loaded_model.is_trained is True
    
    def test_model_versioning(self, temp_registry, sample_model):
        """Test model versioning functionality."""
        # Register first version
        metadata_v1 = ModelMetadata(
            model_id='',
            model_name='versioned_model',
            version='1.0.0',
            algorithm='RandomForest',
            parameters={'n_estimators': 50},
            training_data_hash='abc123',
            feature_names=['feature_0'],
            performance_metrics={'mae': 3.0},
            training_timestamp=datetime.now(),
            model_size_bytes=0,
            python_version='3.9.0',
            dependencies={'scikit-learn': '1.0.0'},
            created_by='test_user',
            tags=['v1'],
            description='Version 1',
            status='training'
        )
        
        model_id_v1 = temp_registry.register_model(sample_model, metadata_v1)
        
        # Register second version with better performance
        metadata_v2 = metadata_v1
        metadata_v2.version = '2.0.0'
        metadata_v2.parameters = {'n_estimators': 100}
        metadata_v2.performance_metrics = {'mae': 2.0}
        metadata_v2.tags = ['v2']
        
        model_id_v2 = temp_registry.register_model(sample_model, metadata_v2)
        
        assert model_id_v1 != model_id_v2
        
        # List models
        models = temp_registry.list_models()
        assert len(models) == 2
        
        # Compare models
        comparison = temp_registry.compare_models([model_id_v1, model_id_v2], 'mae')
        assert comparison[model_id_v2] < comparison[model_id_v1]  # v2 should be better
    
    def test_model_promotion(self, temp_registry, sample_model):
        """Test model promotion workflow."""
        metadata = ModelMetadata(
            model_id='',
            model_name='promotion_test',
            version='1.0.0',
            algorithm='RandomForest',
            parameters={},
            training_data_hash='abc123',
            feature_names=[],
            performance_metrics={'mae': 2.5},
            training_timestamp=datetime.now(),
            model_size_bytes=0,
            python_version='3.9.0',
            dependencies={},
            created_by='test_user',
            tags=[],
            description='Test promotion',
            status='training'
        )
        
        model_id = temp_registry.register_model(sample_model, metadata)
        
        # Promote to active
        temp_registry.promote_model(model_id, 'training', 'active')
        
        # Verify status change
        _, updated_metadata = temp_registry.get_model(model_id)
        assert updated_metadata.status == 'active'
        
        # Get latest active model
        latest_id, latest_metadata = temp_registry.get_latest_model(
            algorithm='RandomForest', 
            status='active'
        )
        assert latest_id == model_id
    
    def test_registry_cleanup(self, temp_registry, sample_model):
        """Test registry cleanup functionality."""
        # Register multiple old models
        for i in range(10):
            metadata = ModelMetadata(
                model_id='',
                model_name=f'cleanup_test_{i}',
                version='1.0.0',
                algorithm='RandomForest',
                parameters={},
                training_data_hash=f'hash_{i}',
                feature_names=[],
                performance_metrics={'mae': 2.5 + i},
                training_timestamp=datetime.now() - timedelta(days=40 + i),  # Old models
                model_size_bytes=0,
                python_version='3.9.0',
                dependencies={},
                created_by='test_user',
                tags=[],
                description=f'Test model {i}',
                status='training'
            )
            
            temp_registry.register_model(sample_model, metadata)
        
        # Cleanup old models (keep latest 5, older than 30 days)
        cleaned_count = temp_registry.cleanup_old_models(keep_latest=5, older_than_days=30)
        
        assert cleaned_count > 0
        
        # Verify models were cleaned up
        remaining_models = temp_registry.list_models()
        assert len(remaining_models) <= 5

@pytest.mark.ml  
class TestTrainingPipeline:
    """Test ML training pipeline functionality."""
    
    @pytest.fixture
    def training_config(self, tenant):
        """Create training configuration."""
        return TrainingConfig(
            tenant_id=tenant.id,
            algorithms=['RandomForest', 'XGBoost'],
            training_period_months=12,
            validation_split=0.2,
            test_split=0.1,
            hyperparameter_optimization=False,  # Skip for speed
            ensemble_enabled=True,
            parallel_training=False,  # Sequential for deterministic tests
            max_workers=1
        )
    
    @patch('apps.inventory.ml.training_pipeline.TrainingPipeline._extract_training_data')
    def test_training_pipeline_execution(self, mock_extract_data, training_config, ml_test_data):
        """Test complete training pipeline execution."""
        # Mock the data extraction
        mock_extract_data.return_value = ml_test_data
        
        # Create training pipeline
        pipeline = TrainingPipeline(training_config)
        
        # Run training pipeline
        result = pipeline.run_training_pipeline()
        
        assert result is not None
        assert 'pipeline_info' in result
        assert 'training_summary' in result
        assert result['pipeline_info']['tenant_id'] == training_config.tenant_id
    
    def test_feature_engineering_pipeline(self, training_config, ml_test_data):
        """Test feature engineering in training pipeline."""
        pipeline = TrainingPipeline(training_config)
        
        # Test feature engineering step
        processed_data = pipeline._engineer_features(ml_test_data)
        
        assert len(processed_data) > 0
        
        # Check that features were added
        product_data = list(processed_data.values())[0]
        assert 'demand' in product_data.columns
        
        # Should have time-based features
        time_features = [col for col in product_data.columns if any(
            keyword in col for keyword in ['month', 'day', 'week', 'year', 'seasonal']
        )]
        assert len(time_features) > 0
    
    @patch('apps.inventory.ml.training_pipeline.TrainingPipeline._train_single_product_models')
    def test_model_training_with_mock(self, mock_train_single, training_config):
        """Test model training with mocked individual training."""
        # Mock the single product training
        mock_train_single.return_value = {
            'product_id': 1,
            'models': {
                'RandomForest': {
                    'model': MagicMock(),
                    'validation_metrics': {'mae': 2.5, 'r2': 0.85},
                    'test_metrics': {'mae': 2.7, 'r2': 0.83}
                }
            },
            'data_info': {
                'train_samples': 200,
                'val_samples': 50,
                'test_samples': 25,
                'features': 15
            }
        }
        
        pipeline = TrainingPipeline(training_config)
        
        # Test model training
        processed_data = {1: pd.DataFrame({'dummy': [1, 2, 3]})}  # Mock data
        training_results = pipeline._train_models(processed_data)
        
        assert 'product_models' in training_results
        assert 1 in training_results['product_models']
        assert 'RandomForest' in training_results['product_models'][1]['models']

@pytest.mark.ml
class TestMLIntegration:
    """Test ML integration with inventory system."""
    
    @pytest.mark.django_db
    def test_ml_prediction_with_real_data(self, tenant, sample_products, sample_stock_items):
        """Test ML prediction using real inventory data."""
        # Create some stock movements for training data
        for product in sample_products[:3]:  # Use first 3 products
            for i in range(30):  # 30 days of movements
                StockMovementFactory(
                    tenant=tenant,
                    product=product,
                    warehouse=sample_stock_items[0].warehouse,
                    movement_type='SALE',
                    quantity=Decimal(f'{10 + np.random.randint(0, 10)}.0000'),
                    created_at=timezone.now() - timedelta(days=i)
                )
        
        # Test feature engineering with real data
        feature_engineer = FeatureEngineer(tenant.id)
        
        # This would typically extract from database
        # For test, we'll create sample data
        sample_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=90, freq='D'),
            'product_id': sample_products[0].id,
            'warehouse_id': sample_stock_items[0].warehouse.id,
            'demand': np.random.poisson(15, 90)  # Poisson demand
        })
        
        # Engineer features
        featured_data = feature_engineer.engineer_features(
            sample_data,
            target_column='demand',
            k_best=15
        )
        
        assert len(featured_data) > 0
        assert 'demand' in featured_data.columns
    
    @patch('apps.inventory.ml.production_serving.ModelServingService._get_best_model')
    def test_production_serving_integration(self, mock_get_model, tenant, sample_products, mock_ml_model):
        """Test production serving integration."""
        from ...ml.production_serving import ModelServingService, PredictionRequest
        
        # Mock the model loading
        mock_metadata = MagicMock()
        mock_metadata.model_id = 'test_model_123'
        mock_metadata.algorithm = 'RandomForest'
        mock_metadata.performance_metrics = {'mae': 2.5}
        
        mock_get_model.return_value = (mock_ml_model, mock_metadata)
        
        # Create serving service
        serving_service = ModelServingService()
        
        # Create prediction request
        request_data = {
            'tenant_id': tenant.id,
            'products': [p.id for p in sample_products[:2]],
            'forecast_horizon': 7,
            'confidence_level': 0.95
        }
        
        prediction_request = PredictionRequest(request_data)
        
        # This would be async in practice, but we'll test sync
        # result = await serving_service.predict(prediction_request)
        
        # For now, just test request validation
        assert prediction_request.tenant_id == tenant.id
        assert len(prediction_request.products) == 2
        assert prediction_request.forecast_horizon == 7
    
    def test_ml_model_performance_tracking(self, mock_ml_model):
        """Test ML model performance tracking."""
        from ...ml.base import ModelPerformanceTracker
        
        tracker = ModelPerformanceTracker()
        
        # Log performance for different models
        models = ['RandomForest', 'XGBoost', 'Ensemble']
        
        for model_name in models:
            for i in range(5):  # 5 performance records each
                metrics = {
                    'mae': 2.0 + np.random.normal(0, 0.5),
                    'r2': 0.85 + np.random.normal(0, 0.1)
                }
                tracker.log_performance(model_name, metrics)
        
        # Test best model selection
        best_model = tracker.get_best_model(models, 'mae')
        assert best_model in models
        
        # Test model comparison
        comparison = tracker.compare_models(models, 'mae')
        assert len(comparison) == 3
        assert all(isinstance(score, (int, float)) for score in comparison.values())