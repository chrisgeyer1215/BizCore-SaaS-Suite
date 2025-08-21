# apps/inventory/ml/model_registry.py

import os
import json
import pickle
import joblib
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

@dataclass
class Model model registry entries."""
    model_id: str
    model_name: str
    version: str
    algorithm: str
    parameters: Dict[str, Any]
    training_data_hash: str
    feature_names: List[str]
    performance_metrics: Dict[str, float]
    training_timestamp: datetime
    model_size_bytes: int
    python_version: str
    dependencies: Dict[str, str]
    created_by: str
    tags: List[str]
    description: str
    status: str  # 'training', 'active', 'archived', 'deprecated'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['training_timestamp'] = data['training_timestamp'].isoformat()
        return data
    
    @classmethod
    adata':
        """Create from dictionary."""
        data['training_timestamp'] = datetime.fromisoformat(data['training_timestamp'])
        return cls(**data)

class ModelRegistry:
    """Production-ready model registry for ML model management."""
    
    def __init__(self, registry_path: str = None):
        self.registry_path = Path(registry_path or os.path.join(settings.MEDIA_ROOT, 'ml_models'))
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.metadata_path = self.registry_path / 'metadata'
        self.models_path = self.registry_path / 'models'
        self.metadata_path.mkdir(exist_ok=True)
        self.models_path.mkdir(exist_ok=True)
        
        self.cache_prefix = 'ml_registry'
        self.cache_timeout = 3600  # 1 hour
    
    def register_model(self, model:_file: Optional[str] = None) -> str:
        """Register a new model in the registry."""
        try:
            # Generate unique model ID
            model_id = self._generate_model_id(metadata)
            metadata.model_id = model_id
            
            # Save model file
            if model_file is None:
                model_file = f"{model_id}.pkl"
            
            model_path = self.models_path / model_file
            
            # Save model based on type
            if hasattr(model, 'save_model'):
                # Custom model with save method
                model.save_model(str(model_path))
            else:
                # Use joblib for sklearn-compatible models
                joblib.dump(model, model_path)
            
            # Update metadata with file info
            metadata.model_size_bytes = model_path.stat().st_size
            
            # Save metadata
            metadata_file = self.metadata_path / f"{model_id}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata.to_dict(), f, indent=2)
            
            # Update cache
            self._update_cache(model_id, metadata)
            
            logger.info(f"Model registered successfully: {model_id}")
            return model_id
            
        except Exception as e:
            logger.error(f"Error registering model: {str(e)}")
            raise
    
    def get_model(self, model_id: str) -> Tuple[Any, ModelMetadata]:
        """Load model and metadata by ID."""
        try:
            # Check cache first
            cached_metadata = cache.get(f"{self.cache_prefix}_{model_id}")
            metadata = ModelMetadata.from_dict(cached_metadata)
            else:
                # Load from disk
                metadata_file = self.metadata_path / f"{model_id}.json"
                if not metadata_file.exists():
                    raise ValueError(f"Model {model_id} not found in registry")
                
                with open(metadata_file, 'r') as f:
                    metadata_dict = json.load(f)
                
                metadata = ModelMetadata.from_dict(metadata_dict)
                
                # Cache metadata
                cache.set(f"{self.cache_prefix}_{model_id}", 
                         metadata.to_dict(), self.cache_timeout)
            
            # Load model
            model_file = f"{model_id}.pkl"
            model_path = self.models_path / model_file
            
            if not model_path.exists():
                raise ValueError(f"Model file {model_file} not found")
            
            # Load based on algorithm
            if metadata.algorithm in ['RandomForest', 'XGBoost', 'Ensemble']:
                model = joblib.load(model_path)
            else:
                # For custom models, use their load method
                from .base import BaseForecaster
                model = BaseForecaster.load_model(str(model_path))
            
            return model, metadata
            
        except Exception as e:
            logger.error(f"Error loading model {model_id}: {str(e)}")
            raise
    
    def list_models(self, algorithm: str = None, status: str = None, 
                   tags: List[str] = None) -> List[ModelMetadata]:
        """List models with optional filtering."""
        models = []
        
        for metadata_file in self.metadata_path.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata_dict = json.load(f)
                
                metadata = ModelMetadata.from_dict(metadata_dict)
                
                # Apply filters
                if algorithm and metadata.algorithm != algorithm:
                    continue
                
                if status and metadata.status != status:
                    continue
                
                if tags:
                    if not any(tag in metadata.tags for tag in tags):
                        continue
                
                models.append(metadata)
                
            except Exception as e:
                logger.warning(f"Error loading metadata from {metadata_file}: {str(e)}")
                continue
        
        # Sort by training timestamp (newest first)
        models.sort(key=lambda x: x.training_timestamp, reverse=True)
        return models
    
    def get_latest_model(self, algorithm: str = None, status: str = 'active') -> Tuple[str, ModelMetadata]:
        """Get the latest model for given algorithm."""
        models = self.list_models(algorithm=algorithm, status=status)
        
        if not models:
            raise ValueError(f"No {status} models found for algorithm {algorithm}")
        
        latest = models[0]  # Already sorted by timestamp
        return latest.model_id, latest
    
    def promote_model(self, model_id: str, from_status: str = 'training', 
                     to_status: str = 'active') -> None:
        """Promote model to different status (e.g., training -> active)."""
        try:
            _, metadata = self.get_model(model_id)
            
            if metadata.status != from_status:
                raise ValueError(f"Model status is {metadata.status}, expected {from_status}")
            
            # If promoting to active, demote current active models
            if to_status == 'active':
                self._demote_active_models(metadata.algorithm)
            
            # Update status
            metadata.status = to_status
            
            # Save updated metadata
            metadata_file = self.metadata_path / f"{model_id}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata.to_dict(), f, indent=2)
            
            # Update cache
            self._update_cache(model_id, metadata)
            
            logger.info(f"Model {model_id} promoted to {to_status}")
            
        except Exception as e:
            logger.error(f"Error promoting model {model_id}: {str(e)}")
            raise
    
    def archive_model(self, model_id: str) -> None:
        """Archive a model (keep metadata, remove model file)."""
        try:
            _, metadata = self.get_model(model_id)
            
            # Update status
            metadata.status = 'archived'
            
            # Save updated metadata
            metadata_file = self.metadata_path / f"{model_id}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata.to_dict(), f, indent=2)
            
            # Remove model file to save space
            model_file = self.models_path / f"{model_id}.pkl"
            if model_file.exists():
                model_file.unlink()
            
            # Update cache
            self._update_cache(model_id, metadata)
            
            logger.info(f"Model {model_id} archived")
            
        except Exception as e:
            logger.error(f"Error archiving model {model_id}: {str(e)}")
            raise
    
    def delete_model(self, model_id: str) -> None:
        """Completely delete a model and its metadata."""
        try:
            # Remove model file
            model_file = self.models_path / f"{model_id}.pkl"
            if model_file.exists():
                model_file.unlink()
            
            # Remove metadata file
            metadata_file = self.metadata_path / f"{model_id}.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            # Remove from cache
            cache.delete(f"{self.cache_prefix}_{model_id}")
            
            logger.info(f"Model {model_id} deleted")
            
        except Exception as e:
            logger.error(f"Error deleting model {model_id}: {str(e)}")
            raise
    
    def compare_models(self, model_ids: List[str], 
                      metric: str = 'mae') -> Dict[str, float]:
        """Compare models on specified metric."""
        comparison = {}
        
        for model_id in model_ids:
            try:
                _, metadata = self.get_model(model_id)
                if metric in metadata.performance_metrics:
                    comparison[model_id] = metadata.performance_metrics[metric]
            except Exception as e:
                logger.warning(f"Error getting metrics for model {model_id}: {str(e)}")
                continue
        
        return comparison
    
    def get_model_lineage(self, model_id: str) -> Dict[str, Any]:
        """Get model lineage and versioning information."""
        try:
            _, metadata = self.get_model(model_id)
            
            # Find related models (same algorithm, similar parameters)
            related_models = []
            all_models = self.list_models(algorithm=metadata.algorithm)
            
            for model in all_models:
                if model.model_id != model_id:
                    # Simple similarity check based on parameter overlap
                    param_overlap = len(set(metadata.parameters.keys()) & 
                                     set(model.parameters.keys()))
                    if param_overlap > len(metadata.parameters) * 0.5:
                        related_models.append({
                            'model_id': model.model_id,
                            'version': model.version,
                            'training_timestamp': model.training_timestamp.isoformat(),
                            'performance': model.performance_metrics.get('mae', None)
                        })
            
            return {
                'model_id': model_id,
                'algorithm': metadata.algorithm,
                'version': metadata.version,
                'related_models': related_models,
                'created_by': metadata.created_by,
                'training_timestamp': metadata.training_timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting lineage for model {model_id}: {str(e)}")
            raise
    
    def cleanup_old_models(self, keep_latest: int = 5, 
                          older_than_days: int = 30) -> int:
        """Cleanup old models to manage storage."""
        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        # Group models by algorithm
        models_by_algo = {}
        for model in self.list_models():
            if model.algorithm not in models_by_algo:
                models_by_algo[model.algorithm] = []
            models_by_algo[model.algorithm].append(model)
        
        for algorithm, models in models_by_algo.items():
            # Sort by training timestamp
            models.sort(key=lambda x: x.training_timestamp, reverse=True)
            
            # Keep the latest N models and active models
            for i, model in enumerate(models):
                should_delete = (
                    i >= keep_latest and  # Not in latest N
                    model.status not in ['active', 'training'] and  # Not active/training
                    model.training_timestamp < cutoff_date  # Older than threshold
                )
                
                if should_delete:
                    try:
                        self.delete_model(model.model_id)
                        cleaned_count += 1
                        logger.info(f"Cleaned up old model: {model.model_id}")
                    except Exception as e:
                        logger.warning(f"Error cleaning model {model.model_id}: {str(e)}")
        
        return cleaned_count
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        models = self.list_models()
        
        stats = {
            'total_models': len(models),
            'models_by_algorithm': {},
            'models_by_status': {},
            'total_size_mb': 0,
            'oldest_model': None,
            'newest_model': None
        }
        
        for model in models:
            # Count by algorithm
            algo = model.algorithm
            stats['models_by_algorithm'][algo] = stats['models_by_algorithm'].get(algo, 0) + 1
            
            # Count by status
            status = model.status
            stats['models_by_status'][status] = stats['models_by_status'].get(status, 0) + 1
            
            # Size calculation
            stats['total_size_mb'] += model.model_size_bytes / (1024 * 1024)
            
            # Age tracking
            if stats['oldest_model'] is None or model.training_timestamp < stats['oldest_model']:
                stats['oldest_model'] = model.training_timestamp
            
            if stats['newest_model'] is None or model.training_timestamp > stats['newest_model']:
                stats['newest_model'] = model.training_timestamp
        
        # Convert timestamps to ISO format
        if stats['oldest_model']:
            stats['oldest_model'] = stats['oldest_model'].isoformat()
        if stats['newest_model']:
            stats['newest_model'] = stats['newest_model'].isoformat()
        
        return stats
    
    def _generate_model_id(self ID."""
        # Create hash from algorithm, parameters, and timestamp
        content = f"{metadata.algorithm}_{metadata.parameters}_{metadata.training_timestamp}"
        model_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        return f"{metadata.algorithm.lower()}_{metadata.version}_{model_hash}"
    
    def _update_cache(self, model_id: str, metadata: ModelMetadata) -> None:
        """Update cache with model metadata."""
        cache.set(f"{self.cache_prefix}_{model_id}", 
                 metadata.to_dict(), self.cache_timeout)
    
    def _demote_active_models(self, algorithm: str) -> None:
        """Demote current active models for given algorithm."""
        active_models = self.list_models(algorithm=algorithm, status='active')
        
        for model in active_models:
            try:
                model.status = 'deprecated'
                
                metadata_file = self.metadata_path / f"{model.model_id}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(model.to_dict(), f, indent=2)
                
                self._update_cache(model.model_id, model)
                
            except Exception as e:
                logger.warning(f"Error demoting model {model.model_id}: {str(e)}")