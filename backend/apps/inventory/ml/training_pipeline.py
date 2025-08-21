# apps/inventory/ml/training_pipeline.py

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing
import logging
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from django.core.cache import cache

from .feature_engineering import FeatureEngineer
from .model_registry import ModelRegistry, ModelMetadata
from .models.random_forest import RandomForestForecaster
from .models.xgboost_model import XGBoostForecaster
from .models.lstm_model import LSTMForecaster
from .models.prophet_model import ProphetForecaster
from .models.ensemble_model import EnsembleForecaster
from ..models.stock.movements import StockMovement
from ..models.catalog.products import Product
from ..models.warehouse.warehouses import Warehouse
from ..services.analytics.data_quality import DataQualityChecker

logger = logging.getLogger(__name__)

@dataclass
class TrainingConfig:
    """Configuration for training pipeline."""
    tenant_id: int
    algorithms: List[str] = None
    products: List[int] = None  # Product IDs to train on
    warehouses: List[int] = None  # Warehouse IDs
    training_period_months: int = 24
    validation_split: float = 0.2
    test_split: float = 0.1
    hyperparameter_optimization: bool = True
    ensemble_enabled: bool = True
    parallel_training: bool = True
    max_workers: Optional[int] = None
    retrain_threshold_days: int = 30
    performance_threshold: float = 0.8  # R² score threshold
    
    def __post_init__(self):
        if self.algorithms is None:
            self.algorithms = ['RandomForest', 'XGBoost', 'Prophet']
        
        if self.max_workers is None:
            self.max_workers = min(4, multiprocessing.cpu_count())

class TrainingPipeline:
    """Automated ML training pipeline for demand forecasting."""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.feature_engineer = FeatureEngineer(config.tenant_id)
        self.model_registry = ModelRegistry()
        self.data_quality_checker = DataQualityChecker()
        
        # Model classes mapping
        self.model_classes = {
            'RandomForest': RandomForestForecaster,
            'XGBoost': XGBoostForecaster,
            'LSTM': LSTMForecaster,
            'Prophet': ProphetForecaster,
            'Ensemble': EnsembleForecaster
        }
        
        # Training results
        self.training_results = {}
        self.trained_models = {}
    
    def run_training_pipeline(self) -> Dict[str, Any]:
        """Execute complete training pipeline."""
        logger.info("Starting ML training pipeline")
        
        try:
            # Step 1: Data extraction and preparation
            logger.info("Step 1: Data extraction and preparation")
            training_data = self._extract_training_data()
            
            if training_data.empty:
                raise ValueError("No training data available")
            
            # Step 2: Data quality assessment
            logger.info("Step 2: Data quality assessment")
            quality_report = self._assess_data_quality(training_data)
            
            # Step 3: Feature engineering
            logger.info("Step 3: Feature engineering")
            processed_data = self._engineer_features(training_data)
            
            # Step 4: Train models
            logger.info("Step 4: Model training")
            training_results = self._train_models(processed_data)
            
            # Step 5: Model evaluation and selection
            logger.info("Step 5: Model evaluation")
            evaluation_results = self._evaluate_models(training_results)
            
            # Step 6: Register best models
            logger.info("Step 6: Model registration")
            registration_results = self._register_models(training_results)
            
            # Step 7: Generate training report
            logger.info("Step 7: Generate training report")
            training_report = self._generate_training_report(
                quality_report, training_results, evaluation_results, registration_results
            )
            
            logger.info("Training pipeline completed successfully")
            return training_report
            
        except Exception as e:
            logger.error(f"Training pipeline failed: {str(e)}")
            raise
    
    def _extract_training_data(self) -> pd.DataFrame:
        """Extract and prepare training data from database."""
        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=self.config.training_period_months * 30)
        
        # Base query for stock movements
        movements_query = StockMovement.objects.filter(
            tenant_id=self.config.tenant_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            movement_type__in=['SALE', 'TRANSFER_OUT', 'ADJUSTMENT_OUT']  # Outbound movements
        )
        
        # Apply product filter
        if self.config.products:
            movements_query = movements_query.filter(product_id__in=self.config.products)
        
        # Apply warehouse filter
        if self.config.warehouses:
            movements_query = movements_query.filter(warehouse_id__in=self.config.warehouses)
        
        # Extract data
        movements = movements_query.select_related('product', 'warehouse').values(
            'product_id', 'warehouse_id', 'created_at__date', 'quantity', 'unit_cost'
        )
        
        if not movements:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(movements)
        df.rename(columns={'created_at__date': 'date'}, inplace=True)
        
        # Aggregate daily demand by product and warehouse
        demand_data = df.groupby(['product_id', 'warehouse_id', 'date']).agg({
            'quantity': 'sum',
            'unit_cost': 'mean'
        }).reset_index()
        
        demand_data.rename(columns={'quantity': 'demand'}, inplace=True)
        
        # Create complete date range for each product-warehouse combination
        complete_data = []
        
        for (product_id, warehouse_id), group in demand_data.groupby(['product_id', 'warehouse_id']):
            # Create complete date range
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            complete_df = pd.DataFrame({'date': date_range})
            complete_df['product_id'] = product_id
            complete_df['warehouse_id'] = warehouse_id
            
            # Merge with actual demand data
            merged = complete_df.merge(group, on=['product_id', 'warehouse_id', 'date'], how='left')
            merged['demand'] = merged['demand'].fillna(0)  # Fill missing days with 0 demand
            merged['unit_cost'] = merged['unit_cost'].fillna(method='ffill').fillna(method='bfill')
            
            complete_data.append(merged)
        
        iffinal_df = pd.concat(complete_data, ignore_index=True)
        
        logger.info(f"Extracted training, "
                   f"{final_df['product_id'].nunique()} products, "
                   f"{final_df['warehouse_id'].nunique()} warehouses")
        
        return final_df
    
    def _assess_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Assess data quality and generate report."""
        return self.data_quality_checker.assess_data_quality(data)
    
    def _engineer_features( -> Dict[int, pd.DataFrame]:
        """Engineer features for each product."""
        processed_data = {}
        
        # Process each product separately
        for product_id, product_data in data.groupby('product_id'):
            try:
                # Sort by date
                product_data = product_data.sort_values('date')
                
                # Engineer features
                engineered_data = self.feature_engineer.engineer_features(
                    product_data, 
                    target_column='demand',
                    include_lags=True,
                    include_product=True,
                    include_seasonal=True,
                    include_external=True,
                    k_best=30  # Limit features for efficiency
                )
                
                # Remove rows with insufficient data (due to lags)
                engineered_data = engineered_data.dropna()
                
                if len(engineered_data) > 30:  # Minimum data points required
                    processed_data[product_id] = engineered_data
                else:
                    logger.warning(f"Insufficient data for product {product_id}: {len(engineered_data)} records")
                    
            except Exception as e:
                logger.warning(f"Error processing product {product_id}: {str(e)}")
                continue
        
        logger.info(f"Feature engineering completed for {len(processed_data)} products")
        return processed_data
    
    def _train_models(self, processed_DataFrame]) -> Dict[str, Any]:
        """Train models for all products."""
        training_results = {
            'product_models': {},
            'global_models': {},
            'training_summary': {}
        }
        
        # Train individual product models
        if self.config.parallel_training:
            training_results['product_models'] = self._train_product_models_parallel(processed_data)
        else:
            training_results['product_models'] = self._train_product_models_sequential(processed_data)
        
        # Train global models (if we have enough data)
        if len(processed_data) >= 5:  # Minimum products for global model
            training_results['global_models'] = self._train_global_models(processed_data)
        
        # Generate training summary
        training_results['training_summary'] = self._summarize_training_results(training_results)
        
        return training_results
    
    def _train_product_models_parallel[int, pd.DataFrame]) -> Dict[int, Dict]:
        """Train product models in parallel."""
        product_models = {}
        
        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit training jobs
            future_to_product = {
                executor.submit(self._train_single_product_models, product_id, data): product_id
                for product_id, data in processed_data.items()
            }
            
            # Collect results
            for future in future_to_product:
                product_id = future_to_product[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per product
                    product_models[product_id] = result
                except Exception as e:
                    logger.error(f"Error training models for product {product_id}: {str(e)}")
                    continue
        
        return product_models
    
    def _train_product_models_sequential(self, pd.DataFrame]) -> Dict[int, Dict]:
        """Train product models sequentially."""
        product_models = {}
        
        for product_id, data in processed_data.items():
            try:
                result = self._train_single_product_models(product_id, data)
                product_models[product_id] = result
            except Exception as e:
                logger.error(f"Error training models for product {product_id}: {str(e)}")
                continue
        
        return product_models
    
    def _train_singled.DataFrame) -> Dict[str, Any]:
        """Train all specified algorithms for a single product."""
        models = {}
        
        # Prepare data splits
        n_samples = len(data)
        test_size = int(n_samples * self.config.test_split)
        val_size = int(n_samples * self.config.validation_split)
        train_size = n_samples - test_size - val_size
        
        if train_size < 20:  # Minimum training samples
            raise ValueError(
        
        # Split data
        train_data = data.iloc[:train_size]
        val_data = data.iloc[train_size:train_size + val_size]
        test_data = data.iloc[train_size + val_size:]
        
        # Prepare features and target
        feature_columns = [col for col in data.columns if col not in ['demand', 'date', 'product_id', 'warehouse_id']]
        
        X_train = train_data[feature_columns]
        y_train = train_data['demand']
        X_val = val_data[feature_columns]
        y_val = val_data['demand']
        X_test = test_data[feature_columns]
        y_test = test_data['demand']
        
        # Train each algorithm
        for algorithm in self.config.algorithms:
            try:
                model_class = self.model_classes.get(algorithm)
                if not model_class:
                    logger.warning(f"Unknown algorithm: {algorithm}")
                    continue
                
                # Initialize model
                model = model_class()
                
                # Hyperparameter optimization
                if self.config.hyperparameter_optimization:
                    try:
                        best_params = model.optimize_hyperparameters(X_train, y_train)
                        logger.info(f"Optimized hyperparameters for {algorithm}: {best_params}")
                    except Exception as e:
                        logger.warning(f"Hyperparameter optimization failed for {algorithm}: {str(e)}")
                
                # Train model
                model.fit(X_train, y_train)
                
                # Validate model
                val_metrics = model.validate(X_val, y_val)
                
                # Test model
                y_test_pred = model.predict(X_test)
                test_metrics = model._calculate_metrics(y_test, y_test_pred)
                
                models[algorithm] = {
                    'model': model,
                    'validation_metrics': val_metrics,
                    'test_metrics': test_metrics,
                    'feature_importance': model.get_feature_importance() if hasattr(model, 'get_feature_importance') else None
                }
                
                logger.info(f"Trained {algorithm} for product {product_id}: "
                           f"Test MAE = {test_metrics['mae']:.4f}")
                
            except Exception as e:
                logger.error(f"Error training {algorithm} for product {product_id}: {str(e)}")
                continue
        
        # Train ensemble if enabled and we have multiple models
        if self.config.ensemble_enabled and len(models) >= 2:
            try:
                ensemble_algorithms = list(models.keys())
                ensemble_model = EnsembleForecaster(
                    models=ensemble_algorithms,
                    ensemble_method='weighted_average'
                )
                
                ensemble_model.fit(X_train, y_train)
                val_metrics = ensemble_model.validate(X_val, y_val)
                
                y_test_pred = ensemble_model.predict(X_test)
                test_metrics = ensemble_model._calculate_metrics(y_test, y_test_pred)
                
                models['Ensemble'] = {
                    'model': ensemble_model,
                    'validation_metrics': val_metrics,
                    'test_metrics': test_metrics,
                    'model_weights': ensemble_model.model_weights
                }
                
                logger.info(f"Trained Ensemble for product {product_id}: "
                           f"Test MAE = {test_metrics['mae']:.4f}")
                
            except Exception as e:
                logger.error(f"Error training ensemble for product {product_id}: {str(e)}")
        
        return {
            'product_id': product_id,
            'models': models,
            'data_info': {
                'train_samples': len(X_train),
                'val_samples': len(X_val),
                'test_samples': len(X_test),
                'features': len(feature_columns)
            }
        }
    
    def _train_global_models(self, processe, Any]:
        """Train global models using data from all products."""
        logger.info("Training global models")
        
        # Combine data from all products
        all_data = []
        for product_id, data in processed_data.items():
            # Add product_id as a feature
            data_copy = data.copy()
            data_copy['product_encoded'] = product_id  # Simple encoding
            all_data.append(data_copy)
        
        combined_data = pd.concat(all_data, ignore_index=True)
        
        # Train global model using the same process as individual products
        global_models = self._train_single_product_models('global', combined_data)
        global_models['product_id'] = 'global'
        
        return global_models
    
    def _evaluate_models(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate and compare trained models."""
        evaluation_results = {
            'best_models_per_product': {},
            'algorithm_performance': {},
            'overall_best_algorithm': None
        }
        
        algorithm_scores = {}
        
        # Evaluate product models
        for product_id, product_result in training_results['product_models'].items():
            best_model = None
            best_score = float('inf')
            
            for algorithm, model_info in product_result['models'].items():
                mae_score = model_info['test_metrics']['mae']
                
                # Track algorithm performance
                if algorithm not in algorithm_scores:
                    algorithm_scores[algorithm] = []
                algorithm_scores[algorithm].append(mae_score)
                
                # Track best model for product
                if mae_score < best_score:
                    best_score = mae_score
                    best_model = {
                        'algorithm': algorithm,
                        'mae': mae_score,
                        'r2': model_info['test_metrics']['r2'],
                        'model_info': model_info
                    }
            
            if best_model:
                evaluation_results['best_models_per_product'][product_id] = best_model
        
        # Calculate algorithm averages
        for algorithm, scores in algorithm_scores.items():
            evaluation_results['algorithm_performance'][algorithm] = {
                'mean_mae': np.mean(scores),
                'median_mae': np.median(scores),
                'std_mae': np.std(scores),
                'min_mae': np.min(scores),
                'max_mae': np.max(scores),
                'count': len(scores)
            }
        
        # Determine overall best algorithm
        if evaluation_results['algorithm_performance']:
            best_algo = min(
                evaluation_results['algorithm_performance'].items(),
                key=lambda x: x[1]['mean_mae']
            )[0]
            evaluation_results['overall_best_algorithm'] = best_algo
        
        return evaluation_results
    
    def _register_models(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Register trained models in the model registry."""
        registration_results = {
            'registered_models': [],
            'failed_registrations': []
        }
        
        # Register product models
        for product_id, product_result in training_results['product_models'].items():
            for algorithm, model_info in product_result['models'].items():
                try:
                    # Create metadata
                    metadata = ModelMetadata(
                        model_id='',  # Will be generated
                        model_name=f"{algorithm}_product_{product_id}",
                        version='1.0.0',
                        algorithm=algorithm,
                        parameters=model_info['model'].hyperparameters if hasattr(model_info['model'], 'hyperparameters') else {},
                        training_data_hash=self._calculate_data_hash(product_result['data_info']),
                        feature_names=model_info['model'].feature_names if hasattr(model_info['model'], 'feature_names') else [],
                        performance_metrics=model_info['test_metrics'],
                        training_timestamp=datetime.now(),
                        model_size_bytes=0,  # Will be calculated during registration
                        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                        dependencies=self._get_dependencies(),
                        created_by=f"training_pipeline_{self.config.tenant_id}",
                        tags=[f"product_{product_id}", algorithm.lower(), 'automated_training'],
                        description=f"Demand forecasting model for product {product_id} using {algorithm}",
                        status='training'
                    )
                    
                    # Register model
                    model_id = self.model_registry.register_model(model_info['model'], metadata)
                    
                    registration_results['registered_models'].append({
                        'model_id': model_id,
                        'product_id': product_id,
                        'algorithm': algorithm,
                        'performance': model_info['test_metrics']
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to register {algorithm} model for product {product_id}: {str(e)}")
                    registration_results['failed_registrations'].append({
                        'product_id': product_id,
                        'algorithm': algorithm,
                        'error': str(e)
                    })
        
        # Register global models if available
        if 'global_models' in training_results and training_results['global_models']:
            global_result = training_results['global_models']
            for algorithm, model_info in global_result['models'].items():
                try:
                    metadata = ModelMetadata(
                        model_id='',
                        model_name=f"{algorithm}_global",
                        version='1.0.0',
                        algorithm=algorithm,
                        parameters=model_info['model'].hyperparameters if hasattr(model_info['model'], 'hyperparameters') else {},
                        training_data_hash=self._calculate_data_hash(global_result['data_info']),
                        feature_names=model_info['model'].feature_names if hasattr(model_info['model'], 'feature_names') else [],
                        performance_metrics=model_info['test_metrics'],
                        training_timestamp=datetime.now(),
                        model_size_bytes=0,
                        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                        dependencies=self._get_dependencies(),
                        created_by=f"training_pipeline_{self.config.tenant_id}",
                        tags=['global_model', algorithm.lower(), 'automated_training'],
                        description=f"Global demand forecasting model using {algorithm}",
                        status='training'
                    )
                    
                    model_id = self.model_registry.register_model(model_info['model'], metadata)
                    
                    registration_results['registered_models'].append({
                        'model_id': model_id,
                        'product_id': 'global',
                        'algorithm': algorithm,
                        'performance': model_info['test_metrics']
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to register global {algorithm} model: {str(e)}")
                    registration_results['failed_registrations'].append({
                        'product_id': 'global',
                        'algorithm': algorithm,
                        'error': str(e)
                    })
        
        return registration_results
    
    def _summarize_training_results(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate training summary statistics."""
        summary = {
            'total_products_trained': len(training_results.get('product_models', {})),
            'algorithms_used': list(self.config.algorithms),
            'training_time': datetime.now().isoformat(),
            'success_rate': 0,
            'average_performance': {},
            'feature_importance_global': {}
        }
        
        # Calculate success rate and average performance
        successful_trainings = 0
        algorithm_maes = {}
        
        for product_result in training_results.get('product_models', {}).values():
            if product_result.get('models'):
                successful_trainings += 1
                
                for algorithm, model_info in product_result['models'].items():
                    if algorithm not in algorithm_maes:
                        algorithm_maes[algorithm] = []
                    algorithm_maes[algorithm].append(model_info['test_metrics']['mae'])
        
        summary['success_rate'] = (successful_trainings / max(1, summary['total_products_trained'])) * 100
        
        for algorithm, maes in algorithm_maes.items():
            summary['average_performance'][algorithm] = {
                'mean_mae': np.mean(maes),
                'count': len(maes)
            }
        
        return summary
    
    def _generate_training_report(self, quality_report: Dict, training_results: Dict,
                                 evaluation_results: Dict, registration_results: Dict) -> Dict[str, Any]:
        """Generate comprehensive training report."""
        report = {
            'pipeline_info': {
                'tenant_id': self.config.tenant_id,
                'training_timestamp': datetime.now().isoformat(),
                'config': {
                    'algorithms': self.config.algorithms,
                    'training_period_months': self.config.training_period_months,
                    'parallel_training': self.config.parallel_training,
                    'ensemble_enabled': self.config.ensemble_enabled
                }
            },
            'data_quality': quality_report,
            'training_summary': training_results.get('training_summary', {}),
            'model_evaluation': evaluation_results,
            'model_registration': registration_results,
            'recommendations': []
        }
        
        # Generate recommendations
        if evaluation_results.get('overall_best_algorithm'):
            report['recommendations'].append(
                f"Best performing algorithm: {evaluation_results['overall_best_algorithm']}"
            )
        
        if registration_results.get('failed_registrations'):
            report['recommendations'].append(
                f"Address {len(registration_results['failed_registrations'])} failed model registrations"
            )
        
        success_rate = training_results.get('training_summary', {}).get('success_rate', 0)
        if success_rate < 80:
            report['recommendations'].append(
                f"Training success rate is {success_rate:.1f}%. Consider data quality improvements"
            )
        
        return report
    
    def _calculate_data_hash(self, data_info: Dict) -> str:
        """Calculate hash of training data information."""
        import hashlib
        content = json.dumps(data_info, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_dependencies(self) -> Dict[str, str]:
        """Get current package versions."""
        import sys
        import sklearn
        import pandas
        import numpy
        
        dependencies = {
            'python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'scikit-learn': sklearn.__version__,
            'pandas': pandas.__version__,
            'numpy': numpy.__version__
        }
        
        # Add optional dependencies
        try:
            import xgboost
            dependencies['xgboost'] = xgboost.__version__
        except ImportError:
            pass
        
        try:
            import tensorflow
            dependencies['tensorflow'] = tensorflow.__version__
        except ImportError:
            pass
        
        return dependencies

# Training scheduler and automation
class TrainingScheduler:
    """Automated training scheduler for ML models."""
    
    def __init__(self):
        self.model_registry = ModelRegistry()
    
    def check_retrain_requirements(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Check which models need retraining."""
        retrain_candidates = []
        
        # Get all active models for tenant
        models = self.model_registry.list_models(status='active')
        tenant_models = [m for m in models if f"training_pipeline_{tenant_id}" in m.created_by]
        
        for model_metadata in tenant_models:
            # Check age
            model_age = (datetime.now() - model_metadata.training_timestamp).days
            
            # Check performance drift
            current_performance = self._check_model_performance(model_metadata.model_id)
            
            retrain_needed = False
            reasons = []
            
            if model_age > 30:  # 30 days old
                retrain_needed = True
                reasons.append(f"Model is {model_age} days old")
            
            if current_performance and current_performance < model_metadata.performance_metrics.get('r2', 0) * 0.9:
                retrain_needed = True
                reasons.append("Performance degradation detected")
            
            if retrain_needed:
                retrain_candidates.append({
                    'model_id': model_metadata.model_id,
                    'algorithm': model_metadata.algorithm,
                    'reasons': reasons,
                    'current_performance': current_performance,
                    'original_performance': model_metadata.performance_metrics
                })
        
        return retrain_candidates
    
    def _check_model_performance(self, model_id: str) -> Optional[float]:
        """Check current model performance (placeholder for production monitoring)."""
        # In production, this would check actual prediction accuracy
        # against recent ground truth data
        return None