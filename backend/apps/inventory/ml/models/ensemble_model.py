# apps/inventory/ml/models/ensemble_model.py

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from ..base import BaseForecaster, ModelPerformanceTracker
from .random_forest import RandomForestForecaster
from .xgboost_model import XGBoostForecaster
from .lstm_model import LSTMForecaster
from .prophet_model import ProphetForecaster

class EnsembleForecaster(BaseForecaster):
    """Ensemble forecaster combining multiple models."""
    
    def __init__(self, models: List[str] = None, ensemble_method: str = 'weighted_average'):
        self.models = models or ['RandomForest', 'XGBoost', 'Prophet']
        self.ensemble_method = ensemble_method
        self.base_models = {}
        self.model_weights = {}
        self.meta_model = None
        
        super().__init__(f'Ensemble_{ensemble_method}', {})
        
    def build_model(self):
        """Build ensemble of base models."""
        model_classes = {
            'RandomForest': RandomForestForecaster,
            'XGBoost': XGBoostForecaster,
            'LSTM': LSTMForecaster,
            'Prophet': ProphetForecaster
        }
        
        for model_name in self.models:
            if model_name in model_classes:
                try:
                    self.base_models[model_name] = model_classes[model_name]()
                except ImportError as e:
                    logger.warning(f"Skipping {model_name} due to import error: {e}")
                    continue
        
        # Initialize equal weights
        n_models = len(self.base_models)
        self.model_weights = {name: 1.0/n_models for name in self.base_models.keys()}
        
        return self  # Return self as the ensemble is the "model"
    
    def prepare_features"""Features are prepared by individual base models."""
        return data
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'EnsembleForecaster':
        """Train all base models and determine ensemble weights."""
        try:
            if not self.base_models:
                self.build_model()
            
            # Train base models
            model_predictions = {}
            model_scores = {}
            
            # Split data for validation
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
            
            for model_name, model in self.base_models.items():
                try:
                    logger.info(f"Training {model_name} model...")
                    
                    # Train model
                    model.fit(X_train, y_train)
                    
                    # Validate model
                    if len(X_val) > 0:
                        y_pred = model.predict(X_val)
                        score = mean_absolute_error(y_val, y_pred)
                        model_scores[model_name] = score
                        model_predictions[model_name] = y_pred
                        
                        logger.info(f"{model_name} validation MAE: {score:.4f}")
                    
                except Exception as e:
                    logger.error(f"Error training {model_name}: {str(e)}")
                    # Remove failed model
                    del self.base_models[model_name]
                    continue
            
            # Calculate ensemble weights based on performance
            if self.ensemble_method == 'weighted_average':
                self._calculate_performance_weights(model_scores)
            elif self.ensemble_method == 'stacking':
                self._train_meta_model(model_predictions, y_val)
            
            self.is_trained = True
            
            # Calculate ensemble training metrics
            if len(X_val) > 0:
                ensemble_pred = self._ensemble_predict(X_val)
                self.training_metrics = self._calculate_metrics(y_val, ensemble_pred)
            
            logger.info(f"Ensemble training completed with {len(self.base_models)} models")
            return self
            
        except Exception as e:
            logger.error(f"Error training ensemble: {str(e)}")
            raise
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make ensemble predictions."""
        if not self.is_trained:
            raise ValueError("Ensemble model is not trained yet")
        
        return self._ensemble_predict(X)
    
    def _ensemble_predict(self, X: pd.DataFrame) -> np.ndarray:
        """Internal method for ensemble prediction."""
        predictions = {}
        
        # Get predictions from all base models
        for model_name, model in self.base_models.items():
            try:
                pred = model.predict(X)
                predictions[model_name] = pred
            except Exception as e:
                logger.warning(f"Error getting prediction from {model_name}: {str(e)}")
                continue
        
        if not predictions:
            raise ValueError("No base models available for prediction")
        
        # Combine predictions based on ensemble method
        if self.ensemble_method == 'simple_average':
            return np.mean(list(predictions.values()), axis=0)
        
        elif self.ensemble_method == 'weighted_average':
            ensemble_pred = np.zeros(len(list(predictions.values())[0]))
            total_weight = 0
            
            for model_name, pred in predictions.items():
                weight = self.model_weights.get(model_name, 0)
                ensemble_pred += weight * pred
                total_weight += weight
            
            return ensemble_pred / total_weight if total_weight > 0 else ensemble_pred
        
        elif self.ensemble_method == 'stacking' and self.meta_model is not None:
            # Create feature matrix for meta-model
            pred_matrix = np.column_stack(list(predictions.values()))
            return self.meta_model.predict(pred_matrix)
        
        else:
            # Fallback to simple average
            return np.mean(list(predictions.values()), axis=0)
    
    def _calculate_performance_weights(self, model_scores: Dict[str, float]):
        """Calculate weights based on inverse of error scores."""
        if not model_scores:
            return
        
        # Use inverse of MAE as weight (better models get higher weights)
        inverse_scores = {name: 1.0 / (score + 1e-8) for name, score in model_scores.items()}
        total_inverse = sum(inverse_scores.values())
        
        self.model_weights = {
            name: score / total_inverse 
            for name, score in inverse_scores.items()
        }
        
        logger.info(f"Performance-based weights: {self.model_weights}")
    
    def _train_meta_model(self, model_predictions: Dict[str, np.ndarray], y_true: pd.Series):
        """Train meta-model for stacking ensemble."""
        if len(model_predictions) < 2:
            logger.warning("Not enough models for stacking, falling back to weighted average")
            self.ensemble_method = 'weighted_average'
            return
        
        # Create feature matrix from base model predictions
        pred_matrix = np.column_stack(list(model_predictions.values()))
        
        # Train linear regression as meta-model
        self.meta_model = LinearRegression()
        self.meta_model.fit(pred_matrix, y_true)
        
        logger.info("Meta-model trained for stacking ensemble")
    
    def predict_with_confidence(self, X: pd.DataFrame, confidence_level: float = 0.95):
        """Ensemble confidence intervals using prediction variance."""
        if not self.is_trained:
            raise ValueError("Ensemble model is not trained yet")
        
        # Get predictions from all models
        all_predictions = []
        for model_name, model in self.base_models.items():
            try:
                pred = model.predict(X)
                all_predictions.append(pred)
            except Exception as e:
                logger.warning(f"Error getting prediction from {model_name}: {str(e)}")
                continue
        
        if not all_predictions:
            raise ValueError("No base models available for prediction")
        
        # Calculate ensemble prediction
        ensemble_pred = self._ensemble_predict(X)
        
        # Calculate confidence intervals using prediction variance
        pred_array = np.array(all_predictions)
        pred_std = np.std(pred_array, axis=0)
        
        from scipy import stats
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        margin_of_error = z_score * pred_std
        
        lower_bound = ensemble_pred - margin_of_error
        upper_bound = ensemble_pred + margin_of_error
        
        return ensemble_pred, lower_bound, upper_bound
    
    def get_model_contributions(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Get individual model contributions to ensemble prediction."""
        contributions = {}
        
        for model_name, model in self.base_models.items():
            try:
                pred = model.predict(X)
                weight = self.model_weights.get(model_name, 0)
                contributions[model_name] = {
                    'prediction': pred,
                    'weight': weight,
                    'weighted_prediction': pred * weight
                }
            except Exception as e:
                logger.warning(f"Error getting contribution from {model_name}: {str(e)}")
                continue
        
        return contributions
    
    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Get feature importance from models that support it."""
        importance_dict = {}
        
        for model_name, model in self.base_models.items():
            try:
                if hasattr(model, 'get_feature_importance'):
                    importance_dict[model_name] = model.get_feature_importance()
            except Exception as e:
                logger.warning(f"Error getting feature importance from {model_name}: {str(e)}")
                continue
        
        return importance_dict