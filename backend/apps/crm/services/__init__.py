# ============================================================================
# backend/apps/crm/services/__init__.py
# ============================================================================

from .base import BaseService, ServiceException
from .lead_service import LeadService
from .account_service import AccountService
from .opportunity_service import OpportunityService
from .activity_service import ActivityService
from .campaign_service import CampaignService
from .ticket_service import TicketService
from .document_service import DocumentService
from .territory_service import TerritoryService
from .product_service import ProductService
from .analytics_service import AnalyticsService
from .workflow_service import WorkflowService
from .integration_service import IntegrationService
from .system_service import SystemService

__all__ = [
    'BaseService', 'ServiceException',
    'LeadService', 'AccountService', 'OpportunityService',
    'ActivityService', 'CampaignService', 'TicketService',
    'DocumentService', 'TerritoryService', 'ProductService',
    'AnalyticsService', 'WorkflowService', 'IntegrationService',
    'SystemService'
]