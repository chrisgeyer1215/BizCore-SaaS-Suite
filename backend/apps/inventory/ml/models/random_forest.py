# apps/inventory/ml/models/random_forest.py

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import RandomizedSearchCV
import pandas as pd
import numpy as np
from typing import Dict
from ..base import BaseForecaster

class RandomForestForecaster(BaseForecaster):
    """Random Forest-based demand forecaster."""
    
    def __init__(self, hyperparameters: Dict = None):
        default_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 2,
            'min_samples_leaf': 1,
            'random_state': 42,
            'n_jobs': -1
        }
        
        if hyperparameters:
            default_params.update(hyperparameters)
            
        super().__init__('RandomForest', default_params)
        
    def build_model(self) -> RandomForestRegressor:
        """Build Random Forest model."""
        return RandomForestRegressor(**self.hyperparameters)
    
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for Random Forest."""
        # Random Forest can handle missing values and doesn't require scaling
        return data.fillna(-999)  # Use -999 as missing value indicator
    
    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, 
                                cv: int = 5, n_iter: int = 50) -> Dict:
        """Optimize hyperparameters using randomized search."""
        param_distributions = {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [5, 10, 15, 20, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2', None]
        }
        
        rf = RandomForestRegressor(random_state=42, n_jobs=-1)
        random_search = RandomizedSearchCV(
            rf, param_distributions, n_iter=n_iter, cv=cv,
            scoring='neg_mean_absolute_error', random_state=42, n_jobs=-1
        )
        
        X_prepared = self.prepare_features(X)
        random_search.fit(X_prepared, y)
        
        self.hyperparameters.update(random_search.best_params_)
        return random_search.best_params_
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if not self.is_trained:
            raise ValueError("Model must be trained first")
        
        importance_scores = self.model.feature_importances_
        return dict(zip(self.feature_names, importance_scores))

# apps/inventory/ml/models/xgboost_model.py

import xgboost as xgb
from sklearn.model_selection import RandomizedSearchCV
import pandas as pd
import numpy as np
from typing import Dict
from ..base import BaseForecaster

class XGBoostForecaster(BaseForecaster):
    """XGBoost-based demand forecaster."""
    
    def __init__(self, hyperparameters: Dict = None):
        default_params = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1
        }
        
        if hyperparameters:
            default_params.update(hyperparameters)
            
        super().__init__('XGBoost', default_params)
        
    def build_model(self) -> xgb.XGBRegressor:
        """Build XGBoost model."""
        return xgb.XGBRegressor(**self.hyperparameters)
    
    def prepare_features"""Prepare features for XGBoost."""
        # XGBoost can handle missing values
        return data.fillna(-999)
    
    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, 
                                cv: int = 5, n_iter: int = 50) -> Dict:
        """Optimize hyperparameters using randomized search."""
        param_distributions = {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [3, 4, 5, 6, 7, 8],
            'learning_rate': [0.01, 0.05, 0.1, 0.15, 0.2],
            'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0]
        }
        
        xgb_model = xgb.XGBRegressor(random_state=42, n_jobs=-1)
        random_search = RandomizedSearchCV(
            xgb_model, param_distributions, n_iter=n_iter, cv=cv,
            scoring='neg_mean_absolute_error', random_state=42, n_jobs=-1
        )
        
        X_prepared = self.prepare_features(X)
        random_search.fit(X_prepared, y)
        
        self.hyperparameters.update(random_search.best_params_)
        return random_search.best_params_
    
    def predict_with_confidence(self, X: pd.DataFrame, confidence_level: float = 0.95):
        """XGBoost with quantile regression for confidence intervals."""
        # For simplicity, using standard prediction + error estimation
        # In production, you might want to use quantile regression
        return super().predict_with_confidence(X, confidence_level)

# apps/inventory/ml/models/lstm_model.py

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import MinMaxScaler
from ..base import BaseForecaster

class LSTMForecaster(BaseForecaster):
    """LSTM Neural Network for time series forecasting."""
    
    def __init__(self, hyperparameters: Dict = None):
        default_params = {
            'sequence_length': 30,
            'lstm_units': [50, 50],
            'dropout_rate': 0.2,
            'learning_rate': 0.001,
            'batch_size': 32,
            'epochs': 100,
            'patience': 10
        }
        
        if hyperparameters:
            default_params.update(hyperparameters)
            
        super().__init__('LSTM', default_params)
        self.sequence_scaler = MinMaxScaler()
        
    def build_model(self) -> Sequential:
        """Build LSTM model."""
        model = Sequential()
        
        lstm_units = self.hyperparameters['lstm_units']
        dropout_rate = self.hyperparameters['dropout_rate']
        
        # First LSTM layer
        model.add(LSTM(
            lstm_units[0], 
            return_sequences=len(lstm_units) > 1,
            input_shape=(self.hyperparameters['sequence_length'], 1)
        ))
        model.add(Dropout(dropout_rate))
        model.add(BatchNormalization())
        
        # Additional LSTM layers
        for i, units in enumerate(lstm_units[1:], 1):
            return_sequences = i < len(lstm_units) - 1
            model.add(LSTM(units, return_sequences=return_sequences))
            model.add(Dropout(dropout_rate))
            model.add(BatchNormalization())
        
        # Dense output layer
        model.add(Dense(1))
        
        # Compile model
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.hyperparameters['learning_rate']),
            loss='mse',
            metrics=['mae']
        )
        
        returnDataFrame) -> pd.DataFrame:
        """Prepare features for LSTM (not used - LSTM uses sequences)."""
        return datad.Series) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training."""
        sequence_length = self.hyperparameters['sequence_length']
        
        # Scale the data
        data_scaled = self.sequence_scaler.fit_transform(data.values.reshape(-1, 1))
        
        X, y = [], []
        for i in range(sequence_length, len(data_scaled)):
            X.append(data_scaled[i-sequence_length:i, 0])
            y.append(data_scaled[i, 0])
        
        return np.array(X), np.array(y)
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'LSTMForecaster':
        """Train LSTM model on time series data."""
        try:
            # Create sequences
            X_seq, y_seq = self.create_sequences(y)
            
            # Reshape for LSTM
            X_seq = X_seq.reshape((X_seq.shape[0], X_seq.shape[1], 1))
            
            # Build model
            if self.model is None:
                self.model = self.build_model()
            
            # Callbacks
            callbacks = [
                EarlyStopping(patience=self.hyperparameters['patience'], restore_best_weights=True),
                ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-6)
            ]
            
            # Train model
            history = self.model.fit(
                X_seq, y_seq,
                batch_size=self.hyperparameters['batch_size'],
                epochs=self.hyperparameters['epochs'],
                callbacks=callbacks,
                validation_split=0.2,
                verbose=0
            )
            
            self.is_trained = True
            
            # Calculate training metrics
            y_pred_scaled = self.model.predict(X_seq)
            y_pred = self.sequence_scaler.inverse_transform(y_pred_scaled).flatten()
            y_actual = self.sequence_scaler.inverse_transform(y_seq.reshape(-1, 1)).flatten()
            
            self.training_metrics = self._calculate_metrics(
                pd.Series(y_actual), 
                y_pred
            )
            
            return self
            
        except Exception as e:
            logger.error(f"Error training LSTM model: {str(e)}")
            raise
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using trained LSTM."""
        if not self.is_trained:
            raise ValueError("LSTM model is not trained yet")
        
        # For prediction, we need the last sequence_length values
        # This is a simplified implementation
        last_sequence = X.iloc[-self.hyperparameters['sequence_length']:].values
        last_sequence_scaled = self.sequence_scaler.transform(last_sequence.reshape(-1, 1))
        
        # Reshape for prediction
        X_pred = last_sequence_scaled.reshape(1, self.hyperparameters['sequence_length'], 1)
        
        # Predict
        y_pred_scaled = self.model.predict(X_pred)
        y_pred = self.sequence_scaler.inverse_transform(y_pred_scaled)
        
        return y_pred.flatten()

# apps/inventory/ml/models/prophet_model.py

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    
import pandas as pd
import numpy as np
from typing import Dict
from ..base import BaseForecaster

class ProphetForecaster(BaseForecaster):
    """Facebook Prophet forecaster for time series with seasonality."""
    
    def __init__(self, hyperparameters: Dict = None):
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet not available. Install with: pip install prophet")
            
        default_params = {
            'growth': 'linear',
            'yearly_seasonality': True,
            'weekly_seasonality': True,
            'daily_seasonality': False,
            'seasonality_mode': 'additive',
            'changepoint_prior_scale': 0.05,
            'seasonality_prior_scale': 10.0
        }
        
        if hyperparameters:
            default_params.update(hyperparameters)
            
        super().__init__('Prophet', default_params)
        
    def build_model(self) -> Prophet:
        """Build Prophet model."""
        return Prophet(**self.hyperparamed.DataFrame) -> pd.DataFrame:
        """Prepare data for Prophet (requires 'ds' and 'y' columns)."""
        # Prophet expects specific column names
        prophet_data = data.copy()
        
        if 'date' in prophet_data.columns and 'demand' in prophet_data.columns:
            prophet_data = prophet_data.rename(columns={'date': 'ds', 'demand': 'y'})
        
        # Prophet requires datetime index
        if 'ds' in prophet_data.columns:
            prophet_data['ds'] = pd.to_datetime(prophet_data['ds'])
        
        return prophet_data[['ds', 'y']]
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'ProphetForecaster':
        """Train Prophet model."""
        try:
            # Prepare data for Prophet
            if 'date' not in X.columns:
                # Assume index is the date
                X = X.reset_index()
                X['date'] = X.index
            
            # Create Prophet dataframe
            prophet_df = pd.DataFrame({
                'ds': pd.to_datetime(X['date']),
                'y': y.values
            })
            
            # Build and train model
            if self.model is None:
                self.model = self.build_model()
            
            self.model.fit(prophet_df)
            self.is_trained = True
            
            # Calculate training metrics
            predictions = self.model.predict(prophet_df)
            y_pred = predictions['yhat'].values
            
            self.training_metrics = self._calculate_metrics(y, y_pred)
            
            return self
            
        except Exception as e:
            logger.error(f"Error training Prophet model: {str(e)}")
            raise
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using Prophet."""
        if not self.is_trained:
            raise ValueError("Prophet model is not trained yet")
        
        # Prepare future dataframe
        if 'date' not in X.columns:
            X = X.reset_index()
            X['date'] = X.index
        
        future_df = pd.DataFrame({'ds': pd.to_datetime(X['date'])})
        
        # Make predictions
        forecast = self.model.predict(future_df)
        return forecast['yhat'].values
    
    def predict_with_confidence(self, X: pd.DataFrame, confidence_level: float = 0.95):
        """Prophet provides built-in confidence intervals."""
        if not self.is_trained:
            raise ValueError("Prophet model is not trained yet")
        
        # Prepare future dataframe
        if 'date' not in X.columns:
            X = X.reset_index()
            X['date'] = X.index
        
        future_df = pd.DataFrame({'ds': pd.to_datetime(X['date'])})
        
        # Make predictions
        forecast = self.model.predict(future_df)
        
        predictions = forecast['yhat'].values
        lower_bound = forecast['yhat_lower'].values
        upper_bound = forecast['yhat_upper'].values
        
        return predictions, lower_bound, upper_bound