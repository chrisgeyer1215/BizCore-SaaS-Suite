# backend/apps/crm/admin_urls.py - Admin Interface URLs
from django.urls import path, include
from django.contrib import admin
from .admin.base import crm_admin_site

app_name = 'crm_admin'

urlpatterns = [
    # Main admin interface
    path('', crm_admin_site.urls),
    
    # Custom admin views
    path('analytics/', crm_admin_site.analytics_view, name='analytics'),
    path('system-health/', crm_admin_site.system_health_view, name='system_health'),
    path('audit-logs/', crm_admin_site.audit_logs_view, name='audit_logs'),
    path('performance/', crm_admin_site.performance_view, name='performance'),
    path('security-monitor/', crm_admin_site.security_monitor_view, name='security_monitor'),
    path('bulk-operations/', crm_admin_site.bulk_operations_view, name='bulk_operations'),
    path('export-data/', crm_admin_site.export_data_view, name='export_data'),
    path('import-data/', crm_admin_site.import_data_view, name='import_data'),
    
    # API endpoints for admin
    path('api/dashboard-stats/', crm_admin_site.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/system-status/', crm_admin_site.system_status_api, name='system_status_api'),
]