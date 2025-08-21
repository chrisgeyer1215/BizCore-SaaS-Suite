# apps/inventory/ml/feature_engineering.py

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_selection import SelectKBest, f_regression
import holidays
from django.db.models import Sum, Avg, Count, Q
from ..models.stock.movements import StockMovement
from ..models.catalog.products import Product
from ..models.purchasing.orders import PurchaseOrder
import logging

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """Advanced feature engineering for demand forecasting."""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.scalers = {}
        self.encoders = {}
        self.feature_selectors = {}
        
    def create_time_features(self, df: pd.DataFrame, date_column: str = 'date') -> pd.DataFrame:
        """Create comprehensive time-based features."""
        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column])
        
        # Basic time features
        df['year'] = df[date_column].dt.year
        df['month'] = df[date_column].dt.month
        df['day'] = df[date_column].dt.day
        df['day_of_week'] = df[date_column].dt.dayofweek
        df['day_of_year'] = df[date_column].dt.dayofyear
        df['week_of_year'] = df[date_column].dt.isocalendar().week
        df['quarter'] = df[date_column].dt.quarter
        
        # Cyclical encoding for periodic features
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        df['day_of_week_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_of_week_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['day_of_year_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
        df['day_of_year_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
        
        # Business calendar features
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_month_start'] = df[date_column].dt.is_month_start.astype(int)
        df['is_month_end'] = df[date_column].dt.is_month_end.astype(int)
        df['is_quarter_start'] = df[date_column].dt.is_quarter_start.astype(int)
        df['is_quarter_end'] = df[date_column].dt.is_quarter_end.astype(int)
        
        # Holiday features (US holidays by default)
        us_holidays = holidays.US()
        df['is_holiday'] = df[date_column].dt.date.apply(lambda x: x in us_holidays).astype(int)
        
        # Days to/from holidays
        df['days_to_next_holiday'] = df[date_column].apply(self._days_to_next_holiday)
        df['days_from_last_holiday'] = df[date_column].apply(self._days_from_last_holiday)
        
        logger.info(f"Created {len([col for col in df.columns if col not in [date_column]])} time features")
        return df
    
    def create_lag_features(self, df: pd.DataFrame, target_column: str, 
                           lags: List[int] = [1, 2, 3, 7, 14, 30]) -> pd.DataFrame:
        """Create lag features for time series forecasting."""
        df = df.copy().sort_values('date')
        
        for lag in lags:
            df[f'{target_column}_lag_{lag}'] = df[target_column].shift(lag)
        
        # Rolling window statistics
        windows = [7, 14, 30, 90]
        for window in windows:
            df[f'{target_column}_rolling_mean_{window}'] = df[target_column].rolling(window=window).mean()
            df[f'{target_column}_rolling_std_{window}'] = df[target_column].rolling(window=window).std()
            df[f'{target_column}_rolling_min_{window}'] = df[target_column].rolling(window=window).min()
            df[f'{target_column}_rolling_max_{window}'] = df[target_column].rolling(window=window).max()
            df[f'{target_column}_rolling_median_{window}'] = df[target_column].rolling(window=window).median()
        
        # Exponentially weighted features
        alphas = [0.1, 0.3, 0.5]
        for alpha in alphas:
            df[f'{target_column}_ewm_{alpha}'] = df[target_column].ewm(alpha=alpha).mean()
        
        logger.info(f"Created lag features with {len(lags)} lags and {len(windows)} rolling windows")
        return df
    
    def create_product_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create product-specific features."""
        df = df.copy()
        
        # Get product information
        products = Product.objects.filter(tenant_id=self.tenant_id)
        product_features = {}
        
        for product in products:
            product_features[product.id] = {
                'cost_price': float(product.cost_price or 0),
                'selling_price': float(product.selling_price or 0),
                'weight': float(product.weight or 0),
                'abc_classification': product.abc_classification or 'C',
                'lead_time_days': product.lead_time_days or 0,
                'shelf_life_days': product.shelf_life_days or 0,
                'reorder_level': float(product.reorder_level or 0),
                'max_stock_level': float(product.max_stock_level or 0)
            }
        
        # Map features to dataframe
        if 'product_id' in df.columns:
            for feature, values in zip(
                ['cost_price', 'selling_price', 'weight', 'abc_classification', 
                 'lead_time_days', 'shelf_life_days', 'reorder_level', 'max_stock_level'],
                ['cost_price', 'selling_price', 'weight', 'abc_classification',
                 'lead_time_days', 'shelf_life_days', 'reorder_level', 'max_stock_level']
            ):
                df[f'product_{feature}'] = df['product_id'].map(
                    {pid: features[feature] for pid, features in product_features.items()}
                )
            
            # Derived product features
            df['profit_margin'] = (df['product_selling_price'] - df['product_cost_price']) / df['product_selling_price']
            df['turnover_ratio'] = df.get('demand', 0) / (df['product_reorder_level'] + 1)  # Avoid division by zero
            df['stock_coverage_days'] = df['product_max_stock_level'] / (df.get('demand', 0) / 30 + 1)  # Monthly to daily
        
        # Encode categorical features
        if 'product_abc_classification' in df.columns:
            le = LabelEncoder()
            df['product_abc_encoded'] = le.fit_transform(df['product_abc_classification'].fillna('C'))
            self.encoders['abc_classification'] = le
        
        logger.info("Created product-specific features")
        return df
    
    def create_seasonal_features(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        """Create advanced seasonality features."""
        df = df.copy()
        
        # Decompose seasonality using moving averages
        # Monthly seasonality
        monthly_avg = df.groupby('month')[target_column].transform('mean')
        df['monthly_seasonality'] = df[target_column] / (monthly_avg + 1e-8)
        
        # Weekly seasonality
        weekly_avg = df.groupby('day_of_week')[target_column].transform('mean')
        df['weekly_seasonality'] = df[target_column] / (weekly_avg + 1e-8)
        
        # Yearly trend
        yearly_avg = df.groupby('year')[target_column].transform('mean')
        df['yearly_trend'] = df[target_column] / (yearly_avg + 1e-8)
        
        # Fourier features for complex seasonality
        n_fourier = 4
        for k in range(1, n_fourier + 1):
            # Annual cycle
            df[f'fourier_annual_sin_{k}'] = np.sin(2 * np.pi * k * df['day_of_year'] / 365.25)
            df[f'fourier_annual_cos_{k}'] = np.cos(2 * np.pi * k * df['day_of_year'] / 365.25)
            
            # Weekly cycle
            df[f'fourier_weekly_sin_{k}'] = np.sin(2 * np.pi * k * df['day_of_week'] / 7)
            df[f'fourier_weekly_cos_{k}'] = np.cos(2 * np.pi * k * df['day_of_week'] / 7)
        
        logger.info(f"Created seasonal features with {n_fourier} Fourier components")
        return df
    
    def create_external_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create features from external data sources."""
        df = df.copy()
        
        # Economic indicators (placeholder - would integrate with real APIs)
        # For demo purposes, we'll create simulated economic features
        np.random.seed(42)  # For reproducible results
        
        df['economic_index'] = 100 + np.random.normal(0, 5, len(df))  # Simulated economic index
        df['consumer_confidence'] = 50 + 30 * np.sin(2 * np.pi * df['day_of_year'] / 365) + np.random.normal(0, 2, len(df))
        df['inflation_rate'] = 2 + 0.5 * np.sin(2 * np.pi * df['day_of_year'] / 365) + np.random.normal(0, 0.1, len(df))
        
        # Weather features (placeholder)
        df['temperature'] = 20 + 10 * np.sin(2 * np.pi * (df['day_of_year'] - 80) / 365) + np.random.normal(0, 3, len(df))
        df['precipitation'] = np.abs(np.random.normal(2, 1, len(df)))
        
        # Marketing/promotional features
        if 'date' in df.columns:
            df['is_promotion_period'] = 0  # Placeholder for promotional periods
            # You would populate this based on your marketing calendar
        
        logger.info("Created external features")
        return df
    
    def create_competitor_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create features related to competitive landscape."""
        df = df.copy()
        
        # Market share indicators (placeholder)
        df['market_share_index'] = 0.3 + 0.1 * np.sin(2 * np.pi * df.get('day_of_year', 0) / 365)
        df['competitor_price_ratio'] = 1.0 + np.random.normal(0, 0.05, len(df))
        df['new_competitor_entry'] = 0  # Indicator for new competitor entries
        
        logger.info("Created competitor features")
        return df
    
    def create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features between different variables."""
        df = df.copy()
        
        # Price-related interactions
        if 'product_cost_price' in df.columns and 'product_selling_price' in df.columns:
            df['price_elasticity_proxy'] = df['product_selling_price'] / df['product_cost_price']
        
        # Seasonality interactions
        if 'monthly_seasonality' in df.columns and 'is_holiday' in df.columns:
            df['holiday_month_interaction'] = df['monthly_seasonality'] * df['is_holiday']
        
        # Product category and time interactions
        if 'product_abc_encoded' in df.columns:
            df['abc_month_interaction'] = df['product_abc_encoded'] * df.get('month', 1)
            df['abc_quarter_interaction'] = df['product_abc_encoded'] * df.get('quarter', 1)
        
        logger.info("Created interaction features")
        return df
    
    def select_features(self, X: pd.DataFrame, y: pd.Series, 
                       method: str = 'k_best', k: int = 50) -> pd.DataFrame:
        """Select the most important features."""
        if method == 'k_best':
            selector = SelectKBest(score_func=f_regression, k=min(k, X.shape[1]))
            X_selected = selector.fit_transform(X, y)
            selected_features = X.columns[selector.get_support()]
            
            self.feature_selectors['k_best'] = selector
            
            logger.info(f"Selected {len(selected_features)} features using K-best selection")
            return pd.DataFrame(X_selected, columns=selected_features, index=X.index)
        
        return X
    
    def scale_features(self, X: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """Scale numerical features."""
        X_scaled = X.copy()
        
        # Identify numerical columns
        numerical_columns = X_scaled.select_dtypes(include=[np.number]).columns
        
        if fit:
            scaler = StandardScaler()
            X_scaled[numerical_columns] = scaler.fit_transform(X_scaled[numerical_columns])
            self.scalers['standard'] = scaler
        else:
            if 'standard' in self.scalers:
                X_scaled[numerical_columns] = self.scalers['standard'].transform(X_scaled[numerical_columns])
        
        logger.info(f"Scaled {len(numerical_columns)} numerical features")
        return X_scaled
    
    def engineer_features(self, df: pd.DataFrame, target_column: str = 'demand',
                         include_lags: bool = True, include_product: bool = True,
                         include_seasonal: bool = True, include_external: bool = True,
                         include_interactions: bool = True, 
                         select_features: bool = True, k_best: int = 50) -> pd.DataFrame:
        """Complete feature engineering pipeline."""
        logger.info("Starting feature engineering pipeline")
        
        # Create time features
        df = self.create_time_features(df)
        
        # Create lag features
        if include_lags and target_column in df.columns:
            df = self.create_lag_features(df, target_column)
        
        # Create product features
        if include_product:
            df = self.create_product_features(df)
        
        # Create seasonal features
        if include_seasonal and target_column in df.columns:
            df = self.create_seasonal_features(df, target_column)
        
        # Create external features
        if include_external:
            df = self.create_external_features(df)
            df = self.create_competitor_features(df)
        
        # Create interaction features
        if include_interactions:
            df = self.create_interaction_features(df)
        
        # Handle missing values
        df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        # Feature selection
        if select_features and target_column in df.columns:
            feature_columns = [col for col in df.columns if col not in [target_column, 'date', 'product_id']]
            X = df[feature_columns]
            y = df[target_column]
            
            X_selected = self.select_features(X, y, k=k_best)
            
            # Reconstruct dataframe
            df = pd.concat([
                df[['date', 'product_id', target_column]] if 'date' in df.columns else df[['product_id', target_column]],
                X_selected
            ], axis=1)
        
        logger.info(f"Feature engineering completed. Final shape: {df.shape}")
        return df
    
    def _days_to_next_holiday(self, date: datetime) -> int:
        """Calculate days to next holiday."""
        us_holidays = holidays.US()
        current_date = date.date() if hasattr(date, 'date') else date
        
        # Check next 365 days for holidays
        for i in range(1, 366):
            check_date = current_date + timedelta(days=i)
            if check_date in us_holidays:
                return i
        
        return 365  # Default if no holiday found
    
    def _days_from_last_holiday(self, date: datetime) -> int:
        """Calculate days from last holiday."""
        us_holidays = holidays.US()
        current_date = date.date() if hasattr(date, 'date') else date
        
        # Check previous 365 days for holidays
        for i in range(1, 366):
            check_date = current_date - timedelta(days=i)
            if check_date in us_holidays:
                return i
        
        return 365  # Default if no holiday found