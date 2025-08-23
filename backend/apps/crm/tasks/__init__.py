"""
CRM Tasks Package
Celery background tasks for automation and processing
"""

from .base import *
from .email_tasks import *
from .campaign_tasks import *
from .scoring_tasks import *
from .reminder_tasks import *
from .cleanup_tasks import *
from .import_tasks import *
from .export_tasks import *
from .workflow_tasks import *
from .analytics_tasks import *
from .notification_tasks import *

__all__ = [
    # Base tasks
    'BaseTask', 'TenantAwareTask', 'RetryableTask',
    
    # Email tasks
    'send_email_task', 'send_bulk_emails_task', 'process_email_bounces_task',
    'send_campaign_emails_task', 'process_email_replies_task',
    
    # Campaign tasks
    'execute_campaign_task', 'process_campaign_analytics_task',
    'optimize_campaign_performance_task', 'schedule_campaign_emails_task',
    
    # Scoring tasks
    'calculate_lead_scores_task', 'update_opportunity_probabilities_task',
    'refresh_customer_health_scores_task', 'update_product_scores_task',
    
    # Reminder tasks
    'send_activity_reminders_task', 'send_follow_up_reminders_task',
    'send_sla_breach_notifications_task', 'process_scheduled_activities_task',
    
    # Cleanup tasks
    'cleanup_old_activities_task', 'cleanup_old_documents_task',
    'cleanup_workflow_executions_task', 'optimize_database_task',
    
    # Import/Export tasks
    'import_leads_task', 'import_contacts_task', 'export_data_task',
    'process_bulk_upload_task', 'generate_report_task',
    
    # Workflow tasks
    'execute_workflow_task', 'process_workflow_triggers_task',
    'optimize_workflows_task', 'sync_integration_data_task',
    
    # Analytics tasks
    'generate_analytics_reports_task', 'refresh_dashboard_data_task',
    'calculate_forecasts_task', 'process_predictive_analytics_task',
    
    # Notification tasks
    'send_notification_task', 'process_webhook_deliveries_task',
    'send_system_alerts_task', 'process_escalations_task'
]