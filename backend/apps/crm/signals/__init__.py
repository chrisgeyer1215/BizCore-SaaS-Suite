"""
CRM Signals Package
Event-driven automation and business logic triggers
"""

from django.apps import AppConfig


class CRMConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm'
    
    def ready(self):
        """Import all signals when Django starts"""
        from . import (
            lead_signals,
            opportunity_signals, 
            activity_signals,
            campaign_signals,
            ticket_signals,
            workflow_signals
        )


# Import all signal handlers
from .lead_signals import *
from .opportunity_signals import *
from .activity_signals import *
from .campaign_signals import *
from .ticket_signals import *
from .workflow_signals import *

__all__ = [
    # Lead signals
    'lead_created', 'lead_updated', 'lead_status_changed', 'lead_assigned',
    'lead_scored', 'lead_converted', 'lead_qualified',
    
    # Opportunity signals  
    'opportunity_created', 'opportunity_updated', 'opportunity_stage_changed',
    'opportunity_assigned', 'opportunity_won', 'opportunity_lost',
    'opportunity_probability_changed',
    
    # Activity signals
    'activity_created', 'activity_completed', 'activity_overdue',
    'activity_assigned', 'activity_reminder_sent',
    
    # Campaign signals
    'campaign_started', 'campaign_completed', 'campaign_member_added',
    'campaign_email_sent', 'campaign_email_opened', 'campaign_email_clicked',
    
    # Ticket signals
    'ticket_created', 'ticket_assigned', 'ticket_status_changed',
    'ticket_escalated', 'ticket_resolved', 'ticket_sla_breached',
    
    # Workflow signals
    'workflow_triggered', 'workflow_executed', 'workflow_completed',
    'workflow_failed', 'integration_synced'
]