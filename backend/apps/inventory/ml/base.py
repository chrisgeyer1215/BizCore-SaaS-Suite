# apps/inventory/ml/base.py

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
from sklearn.base import BaseEstimator
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import logging
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class BaseForecaster(ABC):
    """Abstract base class for all forecasting models."""
    
    def __init__(self, model_name: str, hyperparameters: Dict = None):
        self.model_name = model_name
        self.hyperparameters = hyperparameters or {}
        self.model = None
        self.is_trained = False
        self.feature_names = []
        self.scaler = None
        self.training_metrics = {}
        self.validation_metrics = {}
        
    @abstractmethod
    def build_model(self) -> BaseEstimator:
        """Build and return the ML model."""
        pass
    
    @abstractmethod
    def prepare_features"""Prepare features for the specific model."""
        pass
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'BaseForecaster':
        """Train the model on provided data."""
        try:
            # Prepare features
            X_prepared = self.prepare_features(X)
            
            # Build model if not exists
            if self.model is None:
                self.model = self.build_model()
            
            # Train model
            self.model.fit(X_prepared, y)
            self.is_trained = True
            self.feature_names = list(X_prepared.columns)
            
            # Calculate training metrics
            y_pred = self.model.predict(X_prepared)
            self.training_metrics = self._calculate_metrics(y, y_pred)
            
            logger.info(f"Model {self.model_name} trained successfully")
            return self
            
        except Exception as e:
            logger.error(f"Error training model {self.model_name}: {str(e)}")
            raise
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using the trained model."""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} is not trained yet")
        
        X_prepared = self.prepare_features(X)
        return self.model.predict(X_prepared)
    
    def predict_with_confidence(self, X: pd.DataFrame, confidence_level: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Make predictions with confidence intervals."""
        predictions = self.predict(X)
        
        # For models that don't natively support confidence intervals,
        # estimate using historical prediction errors
        prediction_std = np.std(predictions) if len(predictions) > 1 else predictions.std()
        
        from scipy import stats
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        margin_of_error = z_score * prediction_std
        
        lower_bound = predictions - margin_of_error
        upper_bound = predictions + margin_of_error
        
        return predictions, lower_bound, upper_bound
    
    def validate(self, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
        """Validate model performance on validation set."""
        y_pred = self.predict(X_val)
        self.validation_metrics = self._calculate_metrics(y_val, y_pred)
        return self.validation_metrics
    
    def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate performance metrics."""
        return {
            'mae': mean_absolute_error(y_true, y_pred),
            'mse': mean_squared_error(y_true, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mape': np.mean(np.abs((y_true - y_pred) / y_true)) * 100,
            'r2': r2_score(y_true, y_pred)
        }
    
    def save_model(self, filepath: str) -> None:
        """Save trained model to disk."""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_data = {
            'model': self.model,
            'model_name': self.model_name,
            'hyperparameters': self.hyperparameters,
            'feature_names': self.feature_names,
            'scaler': self.scaler,
            'training_metrics': self.training_metrics,
            'validation_metrics': self.validation_metrics
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Model {self.model_name} saved to {filepath}")
    
    @classmethod
    def load_model(cls, filepath: str) -> 'BaseForecaster':
        """Load trained model from disk."""
        model_data = joblib.load(filepath)
        
        instance = cls(
            model_name=model_data['model_name'],
            hyperparameters=model_data['hyperparameters']
        )
        
        instance.model = model_data['model']
        instance.feature_names = model_data['feature_names']
        instance.scaler = model_data['scaler']
        instance.training_metrics = model_data['training_metrics']
        instance.validation_metrics = model_data['validation_metrics']
        instance.is_trained = True
        
        return instance

class ModelPerformanceTracker:
    """Track and compare model performance over time."""
    
    def __init__(self):
        self.performance_history = {}
    
    def log_performance(self, model_name: str, metrics: Dict[str, float], 
                       timestamp: datetime = None) -> None:
        """Log model performance metrics."""
        if timestamp is None:
            timestamp = datetime.now()
        
        if model_name not in self.performance_history:
            self.performance_history[model_name] = []
        
        self.performance_history[model_name].append({
            'timestamp': timestamp,
            'metrics': metrics
        })
    
    def get_best_model(self, models: List[str], metric: str = 'mae') -> str:
        """Get the best performing model based on specified metric."""
        best_model = None
        best_score = float('inf') if metric in ['mae', 'mse', 'rmse', 'mape'] else float('-inf')
        
        for model_name in models:
            if model_name not in self.performance_history:
                continue
            
            latest_metrics = self.performance_history[model_name][-1]['metrics']
            score = latest_metrics.get(metric, float('inf'))
            
            if metric in ['mae', 'mse', 'rmse', 'mape']:
                if score < best_score:
                    best_score = score
                    best_model = model_name
            else:  # r2 score
                if score > best_score:
                    best_score = score
                    best_model = model_name
        
        return best_model
    
    def compare_models(self, models: List[str], metric: str = 'mae') -> Dict[str, float]:
        """Compare multiple models on specified metric."""
        comparison = {}
        
        for model_name in models:
            if model_name in self.performance_history:
                latest_metrics = self.performance_history[model_name][-1]['metrics']
                comparison[model_name] = latest_metrics.get(metric, None)
        
        return comparison