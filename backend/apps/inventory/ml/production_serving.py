# apps/inventory/ml/production_serving.py

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import redis
import pickle
import json
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import time

from .model_registry import ModelRegistry
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)

class ModelServingError(Exception):
    """Custom exception for model serving errors."""
    pass

class PredictionRequest:
    """Request object for predictions."""
    
    def __init__(self, data: Dict[str, Any]):
        self.tenant_id = data.get('tenant_id')
        self.products = data.get('products', [])  # List of product IDs
        self.warehouses = data.get('warehouses', [])  # List of warehouse IDs
        self.forecast_horizon = data.get('forecast_horizon', 30)  # Days
        self.confidence_level = data.get('confidence_level', 0.95)
        self.include_features = data.get('include_features', False)
        self.model_preference = data.get('model_preference', 'best')  # 'best', 'ensemble', specific algorithm
        
        self.validate()
    
    def validate(self):
        """Validate prediction request."""
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        
        if not self.products:
            raise ValueError("At least one product ID is required")
        
        if self.forecast_horizon <= 0 or self.forecast_horizon > 365:
            raise ValueError("forecast_horizon must be between 1 and 365 days")
        
        if not 0.5 <= self.confidence_level <= 0.99:
            raise ValueError("confidence_level must be between 0.5 and 0.99")

class ModelServingService:
    """Production model serving service with caching and load balancing."""
    
    def __init__(self):
        self.model_registry = ModelRegistry()
        self.feature_engineers = {}  # Cached per tenant
        self.loaded_models = {}  # Model cache
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL) if hasattr(settings, 'REDIS_URL') else None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Performance monitoring
        self.prediction_metrics = {
            'total_predictions': 0,
            'avg_latency_ms': 0,
            'error_count': 0,
            'cache_hit_rate': 0
        }
    
    async def predict(self, request: PredictionRequest) -> Dict[str, Any]:
        """Main prediction endpoint."""
        start_time = time.time()
        
        try:
            # Get feature engineer
            feature_engineer = self._get_feature_engineer(request.tenant_id)
            
            # Generate predictions for each product
            predictions = {}
            
            # Process in batches for efficiency
            batch_size = 10
            product_batches = [
                request.products[i:i + batch_size] 
                for i in range(0, len(request.products), batch_size)
            ]
            
            for batch in product_batches:
                batch_predictions = await self._predict_batch(
                    request, batch, feature_engineer
                )
                predictions.update(batch_predictions)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Update metrics
            self._update_metrics(latency_ms, success=True)
            
            return {
                'status': 'success',
                'predictions': predictions,
                'metadata': {
                    'forecast_horizon_days': request.forecast_horizon,
                    'confidence_level': request.confidence_level,
                    'latency_ms': round(latency_ms, 2),
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            self._update_metrics(time.time() - start_time, success=False)
            
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _predict_batch(self, request: PredictionRequest, 
                           product_ids: List[int], 
                           feature_engineer: FeatureEngineer) -> Dict[int, Dict]:
        """Process a batch of products."""
        batch_predictions = {}
        
        # Create async tasks for each product
        tasks = [
            self._predict_single_product(
                request, product_id, feature_engineer
            )
            for product_id in product_ids
        ]
        
        # Execute tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for product_id, result in zip(product_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Error predicting for product {product_id}: {str(result)}")
                batch_predictions[product_id] = {
                    'status': 'error',
                    'error': str(result)
                }
            else:
                batch_predictions[product_id] = result
        
        return batch_predictions
    
    async def _predict_single_product(self, request: PredictionRequest, 
                                    product_id: int, 
                                    feature_engineer: FeatureEngineer) -> Dict[str, Any]:
        """Predict for a single product."""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request, product_id)
            cached_result = await self._get_from_cache(cache_key)
            
            if cached_result:
                return cached_result
            
            # Get the best model for this product
            model, model_metadata = await self._get_best_model(
                request.tenant_id, product_id, request.model_preference
            )
            
            # Prepare input data
            input_data = await self._prepare_input_data(
                request, product_id, feature_engineer
            )
            
            # Make prediction
            if hasattr(model, 'predict_with_confidence'):
                predictions, lower_bound, upper_bound = model.predict_with_confidence(
                    input_data, request.confidence_level
                )
            else:
                predictions = model.predict(input_data)
                lower_bound = upper_bound = None
            
            # Format results
            result = self._format_prediction_result(
                predictions, lower_bound, upper_bound, 
                model_metadata, request.forecast_horizon
            )
            
            # Cache result
            await self._cache_result(cache_key, result, ttl=3600)  # 1 hour
            
            return result
            
        except Exception as e:
            logger.error(f"Error predicting for product {product_id}: {str(e)}")
            raise ModelServingError(f"Prediction failed for product {product_id}: {str(e)}")
    
    async def _get_best_model(self, tenant_id: int, product_id: int, 
                            preference: str) -> Tuple[Any, Any]:
        """Get the best model for prediction."""
        # Look for product-specific model first
        models = self.model_registry.list_models(status='active')
        
        # Filter models for this tenant
        tenant_models = [
            m for m in models 
            if f"training_pipeline_{tenant_id}" in m.created_by
        ]
        
        # Look for product-specific model
        product_models = [
            m for m in tenant_models 
            if f"product_{product_id}" in m.tags
        ]
        
        if product_models:
            # Get best product-specific model
            if preference == 'ensemble':
                best_model_meta = next(
                    (m for m in product_models if m.algorithm == 'Ensemble'), 
                    product_models[0]
                )
            else:
                # Get model with best performance
                best_model_meta = min(
                    product_models, 
                    key=lambda m: m.performance_metrics.get('mae', float('inf'))
                )
        else:
            # Fall back to global model
            global_models = [
                m for m in tenant_models 
                if 'global_model' in m.tags
            ]
            
            if not global_models:
                raise ModelServingError(f"No trained models found for tenant {tenant_id}")
            
            best_model_meta = min(
                global_models,
                key=lambda m: m.performance_metrics.get('mae', float('inf'))
            )
        
        # Load model (with caching)
        model_id = best_model_meta.model_id
        
        if model_id not in self.loaded_models:
            model, _ = self.model_registry.get_model(model_id)
            self.loaded_models[model_id] = model
        
        return self.loaded_models[model_id], best_model_meta
    
    async def _prepare_input_data(self, request: PredictionRequest, 
                                product_id: int, 
                                feature_engineer: FeatureEngineer) -> pd.DataFrame:
        """Prepare input data for prediction."""
        # Get historical data for feature engineering
        # This would typically fetch recent data from database
        
        # For now, create a simple input with future dates
        future_dates = pd.date_range(
            start=datetime.now().date(),
            periods=request.forecast_horizon,
            freq='D'
        )
        
        input_data = pd.DataFrame({
            'date': future_dates,
            'product_id': product_id
        })
        
        # Add any additional context data
        # In production, you'd fetch recent historical data for lag features
        
        # Engineer features (simplified for production)
        # Note: This would use the same feature engineering pipeline as training
        featured_data = feature_engineer.create_time_features(input_data)
        
        # Fill missing features with defaults
        for col in featured_data.columns:
            if featured_data[col].dtype in ['float64', 'int64']:
                featured_data[col] = featured_data[col].fillna(0)
            else:
                featured_data[col] = featured_data[col].fillna('')
        
        return featured_data
    
    def _format_prediction_result(self, predictions: np.ndarray, 
                                lower_bound: Optional[np.ndarray],
                                upper_bound: Optional[np.ndarray],
                ) -> Dict[str, Any]:
        """Format prediction results."""
        # Create time series
        start_date = datetime.now().date()
        dates = [
            (start_date + timedelta(days=i)).isoformat() 
            for i in range(len(predictions))
        ]
        
        # Ensure non-negative predictions for demand
        predictions = np.maximum(predictions, 0)
        if lower_bound is not None:
            lower_bound = np.maximum(lower_bound, 0)
        if upper_bound is not None:
            upper_bound = np.maximum(upper_bound, 0)
        
        result = {
            'status': 'success',
            'forecast': [
                {
                    'date': date,
                    'predicted_demand': max(0, float(pred)),
                    'confidence_lower': max(0, float(lower)) if lower_bound is not None else None,
                    'confidence_upper': max(0, float(upper)) if upper_bound is not None else None
                }
                for date, pred, lower, upper in zip(
                    dates, predictions,
                    lower_bound if lower_bound is not None else [None] * len(predictions),
                    upper_bound if upper_bound is not None else [None] * len(predictions)
                )
            ],
            'summary': {
                'total_forecasted_demand': float(np.sum(predictions)),
                'average_daily_demand': float(np.mean(predictions)),
                'peak_demand': float(np.max(predictions)),
                'peak_demand_date': dates[np.argmax(predictions)]
            },
            'model_info': {
                'model_id': model_metadata.model_id,
                'algorithm': model_metadata.algorithm,
                'version': model_metadata.version,
                'training_date': model_metadata.training_timestamp.isoformat(),
                'performance_mae': model_metadata.performance_metrics.get('mae', None)
            }
        }
        
        return result
    
    def _get_feature_engineer(self, tenant_id: int) -> FeatureEngineer:
        """Get or create feature engineer for tenant."""
        if tenant_id not in self.feature_engineers:
            self.feature_engineers[tenant_id] = FeatureEngineer(tenant_id)
        
        return self.feature_engineers[tenant_id]
    
    def _generate_cache_key(self, request: PredictionRequest, product_id: int) -> str:
        """Generate cache key for prediction."""
        key_parts = [
            'prediction',
            str(request.tenant_id),
            str(product_id),
            str(request.forecast_horizon),
            str(request.confidence_level),
            datetime.now().strftime('%Y-%m-%d-%H')  # Cache per hour
        ]
        return ':'.join(key_parts)
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get cached result."""
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if pickle.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache get error: {str(e)}")
        
        return None
    
    async def _cache_result(self, cache_key: str, result: Dict, ttl: int = 3600):
        """Cache prediction result."""
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key, 
                    ttl, 
                    pickle.dumps(result)
                )
            except Exception as e:
                logger.warning(f"Cache set error: {str(e)}")
    
    def _update_metrics(self, latency_ms: float, success: bool = True):
        """Update performance metrics."""
        self.prediction_metrics['total_predictions'] += 1
        
        # Update rolling average latency
        current_avg = self.prediction_metrics['avg_latency_ms']
        total_predictions = self.prediction_metrics['total_predictions']
        
        self.prediction_metrics['avg_latency_ms'] = (
            (current_avg * (total_predictions - 1) + latency_ms) / total_predictions
        )
        
        if not success:
            self.prediction_metrics['error_count'] += 1
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status."""
        error_rate = (
            self.prediction_metrics['error_count'] / 
            max(1, self.prediction_metrics['total_predictions']) * 100
        )
        
        health_status = 'healthy'
        if error_rate > 10:
            health_status = 'unhealthy'
        elif error_rate > 5:
            health_status = 'degraded'
        
        return {
            'status': health_status,
            'metrics': self.prediction_metrics,
            'error_rate_percent': round(error_rate, 2),
            'loaded_models_count': len(self.loaded_models),
            'timestamp': datetime.now().isoformat()
        }

# Django views for API endpoints
@method_decorator(csrf_exempt, name='dispatch')
class MLPredictionView(View):
    """REST API endpoint for ML predictions."""
    
    def __init__(self):
        super().__init__()
        self.serving_service = ModelServingService()
    
    async def post(self, request):
        """Handle prediction requests."""
        try:
            # Parse request data
            request_data = json.loads(request.body)
            prediction_request = PredictionRequest(request_data)
            
            # Get predictions
            result = await self.serving_service.predict(prediction_request)
            
            return JsonResponse(result)
            
        except ValueError as e:
            return JsonResponse({
                'status': 'error',
                'error': f'Invalid request: {str(e)}'
            }, status=400)
        
        except Exception as e:
            logger.error(f"Prediction API error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'error': 'Internal server error'
            }, status=500)
    
    def get(self, request):
        """Health check endpoint."""
        health_status = self.serving_service.get_health_status()
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return JsonResponse(health_status, status=status_code)

# Monitoring and observability
class MLMonitoringService:
    """Monitor ML model performance in production."""
    
    def __init__(self):
        self.model_registry = ModelRegistry()
        self.performance_data = {}
    
    def log_prediction(self, model_id: str, inputency_ms: float):
        """Log prediction for monitoring."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'model_id': model_id,
            'input_hash': self._hash_input(input_data),
            'prediction_summary': {
                'total_demand': prediction.get('summary', {}).get('total_forecasted_demand', 0),
                'avg_demand': prediction.get('summary', {}).get('average_daily_demand', 0)
            },
            'latency_ms': latency_ms
        }
        
        # Store in time-series database or logging system
        logger.info(f"ML_PREDICTION: {json.dumps(log_entry)}")
    
    def detect_model_drift(self, model_id: str) -> Dict[str, Any]:
        """Detect if model performance is degrading."""
        # This would analyze recent predictions vs actuals
        # For now, return a placeholder
        return {
            'model_id': model_id,
            'drift_detected': False,
            'confidence': 0.95,
            'recommendation': 'continue_monitoring'
        }
    
    def _hash_input(self,
        """Create hash of input data for tracking."""
        import hashlib
        content = json.dumps(input_data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:8]