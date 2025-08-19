"""
Add these to your existing celery beat schedule
"""

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
})
