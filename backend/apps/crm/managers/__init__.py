"""
CRM Managers Package
Custom model managers for optimized queries and business logic
"""

from .base import *
from .lead_manager import *
from .opportunity_manager import *
from .activity_manager import *
from .campaign_manager import *
from .ticket_manager import *
from .analytics_manager import *
from .account_manager import *
from .document_manager import *
from .territory_manager import *
from .product_manager import *
from .workflow_manager import *
from .user_manager import *

__all__ = [
    # Base managers
    'TenantAwareManager', 'SoftDeleteManager', 'TimestampedManager',
    
    # CRM module managers
    'LeadManager', 'OpportunityManager', 'ActivityManager',
    'CampaignManager', 'TicketManager', 'AnalyticsManager',
    'AccountManager', 'DocumentManager', 'TerritoryManager',
    'ProductManager', 'WorkflowManager', 'CRMUserManager'
]