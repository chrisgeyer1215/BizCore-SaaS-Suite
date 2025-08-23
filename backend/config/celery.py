# backend/config/celery.py
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

app = Celery('saas_aice')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Configuration
app.conf.update(
    # Task Routing
    task_routes={
        # CRM Tasks
        'apps.crm.tasks.email_tasks.*': {'queue': 'email'},
        'apps.crm.tasks.campaign_tasks.*': {'queue': 'campaigns'},
        'apps.crm.tasks.scoring_tasks.*': {'queue': 'analytics'},
        'apps.crm.tasks.workflow_tasks.*': {'queue': 'workflows'},
        
        # System Tasks
        'apps.core.tasks.*': {'queue': 'system'},
        'apps.auth.tasks.*': {'queue': 'auth'},
        
        # Heavy Processing
        'apps.ai.tasks.*': {'queue': 'ai_processing'},
        'apps.crm.tasks.analytics_tasks.*': {'queue': 'analytics'},
        'apps.crm.tasks.import_tasks.*': {'queue': 'data_processing'},
        'apps.crm.tasks.export_tasks.*': {'queue': 'data_processing'},
    },
)

# Initialize CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {}

# Add to CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE.update({
    # E-commerce specific tasks
    'process-abandoned-carts': {
        'task': 'apps.ecommerce.tasks.process_abandoned_carts',
        'schedule': crontab(minute=0),  # Every hour
    },
    'sync-product-inventory': {
        'task': 'apps.ecommerce.tasks.sync_product_inventory',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
    'cleanup-expired-carts': {
        'task': 'apps.ecommerce.tasks.cleanup_expired_carts',
        'schedule': crontab(minute=0, hour=3),  # Daily at 3 AM
    },
    'update-product-metrics': {
        'task': 'apps.ecommerce.tasks.update_product_metrics',
        'schedule': crontab(minute=0, hour=4),  # Daily at 4 AM
    },
    'calculate-lead-scores': {
        'task': 'apps.crm.tasks.scoring_tasks.calculate_lead_scores',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
    'send-campaign-emails': {
        'task': 'apps.crm.tasks.campaign_tasks.process_scheduled_campaigns',
        'schedule': crontab(minute=0, hour=9),  # 9 AM daily
    },
    'process-workflow-triggers': {
        'task': 'apps.crm.tasks.workflow_tasks.process_pending_workflows',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'send-activity-reminders': {
        'task': 'apps.crm.tasks.reminder_tasks.send_due_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'update-opportunity-probabilities': {
        'task': 'apps.crm.tasks.analytics_tasks.update_opportunity_probabilities',
        'schedule': crontab(minute=0, hour=1),  # 1 AM daily
    },
    'cleanup-old-activities': {
        'task': 'apps.crm.tasks.cleanup_tasks.cleanup_old_activities',
        'schedule': crontab(minute=0, hour=2, day_of_week=1),  # Monday 2 AM
    },
    'generate-daily-reports': {
        'task': 'apps.crm.tasks.analytics_tasks.generate_daily_reports',
        'schedule': crontab(minute=0, hour=8),  # 8 AM daily
    },
    'sync-tenant-usage': {
        'task': 'apps.core.tasks.sync_tenant_usage',
        'schedule': crontab(minute=0, hour=0),  # Midnight daily
    },
    'backup-tenant-data': {
        'task': 'apps.core.tasks.backup_tenant_data',
        'schedule': crontab(minute=0, hour=3),  # 3 AM daily
    },
    
    # Weekly Tasks
    'generate-weekly-analytics': {
        'task': 'apps.crm.tasks.analytics_tasks.generate_weekly_analytics',
        'schedule': crontab(minute=0, hour=6, day_of_week=1),  # Monday 6 AM
    },
    'cleanup-old-logs': {
        'task': 'apps.crm.tasks.cleanup_tasks.cleanup_old_logs',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),  # Sunday 3 AM
    },
    
    # Monthly Tasks
    'generate-monthly-reports': {
        'task': 'apps.crm.tasks.analytics_tasks.generate_monthly_reports',
        'schedule': crontab(minute=0, hour=4, day_of_month=1),  # 1st day of month, 4 AM
    },
    'archive-old-data': {
        'task': 'apps.crm.tasks.cleanup_tasks.archive_old_data',
        'schedule': crontab(minute=0, hour=2, day_of_month=1),  # 1st day of month, 2 AM
    },
})

# Apply the beat schedule to the Celery app
app.conf.beat_schedule = CELERY_BEAT_SCHEDULE

# Queue Configuration (Note: This overwrites the earlier task_routes)
app.conf.task_routes = {
    # High Priority
    'apps.auth.tasks.*': {'queue': 'high_priority'},
    'apps.crm.tasks.notification_tasks.*': {'queue': 'high_priority'},
    
    # Normal Priority
    'apps.crm.tasks.email_tasks.*': {'queue': 'emails'},
    'apps.crm.tasks.workflow_tasks.*': {'queue': 'workflows'},
    
    # Low Priority
    'apps.crm.tasks.analytics_tasks.*': {'queue': 'analytics'},
    'apps.crm.tasks.cleanup_tasks.*': {'queue': 'maintenance'},
    
    # Bulk Operations
    'apps.crm.tasks.import_tasks.*': {'queue': 'bulk_operations'},
    'apps.crm.tasks.export_tasks.*': {'queue': 'bulk_operations'},
    
    # Add the earlier routes that got overwritten
    'apps.crm.tasks.campaign_tasks.*': {'queue': 'campaigns'},
    'apps.crm.tasks.scoring_tasks.*': {'queue': 'analytics'},
    'apps.core.tasks.*': {'queue': 'system'},
    'apps.ai.tasks.*': {'queue': 'ai_processing'},
    'apps.crm.tasks.import_tasks.*': {'queue': 'data_processing'},
    'apps.crm.tasks.export_tasks.*': {'queue': 'data_processing'},
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')