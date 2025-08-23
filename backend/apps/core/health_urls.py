# backend/apps/core/health_urls.py - System Health URLs
from django.urls import path
from .views import (
    HealthCheckView, DatabaseHealthView, CacheHealthView, 
    TenantHealthView, CeleryHealthView, SystemStatsView
)

app_name = 'health'

urlpatterns = [
    path('', HealthCheckView.as_view(), name='health-check'),
    path('database/', DatabaseHealthView.as_view(), name='database-health'),
    path('cache/', CacheHealthView.as_view(), name='cache-health'), 
    path('tenant/', TenantHealthView.as_view(), name='tenant-health'),
    path('celery/', CeleryHealthView.as_view(), name='celery-health'),
    path('stats/', SystemStatsView.as_view(), name='system-stats'),
    
    # Detailed health endpoints
    path('detailed/', HealthCheckView.as_view(), {'detailed': True}, name='detailed-health'),
    path('monitoring/', HealthCheckView.as_view(), {'format': 'prometheus'}, name='monitoring-health'),
]