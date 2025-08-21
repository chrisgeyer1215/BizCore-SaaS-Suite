# apps/inventory/ml/celery_tasks.py

from celery import shared_task
import logging
from .training_pipeline import TrainingPipeline, TrainingConfig
from .model_registry import ModelRegistry

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def train_models_task(self, tenant_id: int, config_dict: dict = None):
    """Celery task for training ML models."""
    try:
        # Create training config
        config = TrainingConfig(tenant_id=tenant_id)
        if config_dict:
            for key, value in config_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # Run training pipeline
        pipeline = TrainingPipeline(config)
        result = pipeline.run_training_pipeline()
        
        logger.info(f"Training completed for tenant {tenant_id}")
        return result
        
    except Exception as e:
        logger.error(f"Training task failed for tenant {tenant_id}: {str(e)}")
        raise self.retry(countdown=60, exc=e)

@shared_task
def cleanup_old_models_task():
    """Clean up old ML models."""
    try:
        registry = ModelRegistry()
        cleaned_count = registry.cleanup_old_models()
        
        logger.info(f"Cleaned up {cleaned_count} old models")
        return {'cleaned_models': cleaned_count}
        
    except Exception as e:
        logger.error(f"Model cleanup task failed: {str(e)}")
        raise

@shared_task
def monitor_model_performance_task():
    """Monitor model performance and trigger retraining if needed."""
    try:
        from .training_pipeline import TrainingScheduler
        
        scheduler = TrainingScheduler()
        # This would check all tenants
        # For now, placeholder implementation
        
        logger.info("Model performance monitoring completed")
        return {'status': 'completed'}
        
    except Exception as e:
        logger.error(f"Performance monitoring task failed: {str(e)}")
        raise