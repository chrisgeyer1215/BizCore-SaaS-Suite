# backend/apps/core/tasks.py
from celery import shared_task
from django.core.management import call_command
from django.conf import settings
from django_tenants.utils import schema_context, get_tenant_model
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def sync_tenant_usage(self):
    """Sync tenant usage statistics."""
    try:
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.all()
        
        for tenant in tenants:
            with schema_context(tenant.schema_name):
                # Update tenant usage statistics
                call_command('update_tenant_usage', tenant.schema_name)
                
        logger.info(f"Synced usage for {tenants.count()} tenants")
        return f"Successfully synced {tenants.count()} tenants"
        
    except Exception as e:
        logger.error(f"Error syncing tenant usage: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)

@shared_task(bind=True)
def backup_tenant_data(self):
    """Backup tenant data."""
    try:
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.filter(status='active')
        
        for tenant in tenants:
            with schema_context(tenant.schema_name):
                # Run backup command for tenant
                call_command('backup_tenant', tenant.schema_name)
                
        logger.info(f"Backed up data for {tenants.count()} active tenants")
        return f"Successfully backed up {tenants.count()} tenants"
        
    except Exception as e:
        logger.error(f"Error backing up tenant data: {str(e)}")
        raise self.retry(exc=e, countdown=600, max_retries=2)

@shared_task
def cleanup_expired_sessions():
    """Clean up expired sessions."""
    try:
        call_command('clearsessions')
        logger.info("Cleaned up expired sessions")
        return "Successfully cleaned expired sessions"
    except Exception as e:
        logger.error(f"Error cleaning sessions: {str(e)}")
        raise

@shared_task
def health_check():
    """System health check task."""
    from django.db import connection
    from django.core.cache import cache
    
    try:
        # Database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            
        # Cache check
        cache.set('health_check', 'ok', 30)
        cache_status = cache.get('health_check')
        
        if cache_status != 'ok':
            raise Exception("Cache not working")
            
        return "System healthy"
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise