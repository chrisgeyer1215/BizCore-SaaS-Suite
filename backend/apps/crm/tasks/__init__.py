# ============================================================================
# backend/apps/crm/tasks/__init__.py - Tasks Module Initialization
# ============================================================================

from .base import BaseTask, PermissionAwareTask, AuditableTask
from .email_tasks import (
    send_email_campaign, send_single_email, send_email_sequence,
    process_email_bounce, send_email_notification
)
from .lead_tasks import (
    calculate_lead_scores, auto_assign_leads, process_lead_import,
    lead_nurturing_sequence, duplicate_lead_detection
)
from .opportunity_tasks import (
    update_opportunity_stages, generate_sales_forecast,
    opportunity_reminder_notifications, calculate_pipeline_health
)
from .activity_tasks import (
    send_activity_reminders, process_activity_automation,
    generate_productivity_reports, sync_calendar_activities
)
from .analytics_tasks import (
    generate_dashboard_data, calculate_performance_metrics,
    export_analytics_report, refresh_data_warehouse
)
from .campaign_tasks import (
    execute_campaign_automation, process_campaign_responses,
    calculate_campaign_roi, segment_audience
)
from .data_tasks import (
    bulk_data_import, bulk_data_export, data_cleanup,
    sync_external_data, backup_tenant_data
)
from .notification_tasks import (
    send_push_notification, send_sms_notification,
    process_notification_queue, send_security_alert
)
from .maintenance_tasks import (
    cleanup_old_data, optimize_database, generate_system_reports,
    perform_security_scan, update_search_indices
)

__all__ = [
    'BaseTask', 'PermissionAwareTask', 'AuditableTask',
    'send_email_campaign', 'send_single_email', 'send_email_sequence',
    'calculate_lead_scores', 'auto_assign_leads', 'process_lead_import',
    'update_opportunity_stages', 'generate_sales_forecast',
    'send_activity_reminders', 'process_activity_automation',
    'generate_dashboard_data', 'calculate_performance_metrics',
    'execute_campaign_automation', 'process_campaign_responses',
    'bulk_data_import', 'bulk_data_export', 'data_cleanup',
    'send_push_notification', 'send_sms_notification',
    'cleanup_old_data', 'optimize_database', 'generate_system_reports'
]