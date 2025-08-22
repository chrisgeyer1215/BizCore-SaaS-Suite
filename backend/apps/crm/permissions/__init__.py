# ============================================================================
# backend/apps/crm/permissions/__init__.py
# ============================================================================

from .base import CRMPermission, TenantObjectPermission, OwnershipPermission
from .account import AccountPermission, ContactPermission, IndustryPermission
from .lead import LeadPermission, LeadSourcePermission
from .opportunity import OpportunityPermission, PipelinePermission
from .activity import ActivityPermission, ActivityTypePermission
from .campaign import CampaignPermission, CampaignMemberPermission
from .ticket import TicketPermission, TicketCategoryPermission
from .document import DocumentPermission, DocumentCategoryPermission
from .territory import TerritoryPermission, TeamPermission
from .product import ProductPermission, ProductCategoryPermission
from .analytics import AnalyticsPermission, ReportPermission, DashboardPermission
from .workflow import WorkflowPermission, IntegrationPermission
from .system import SystemAdminPermission, AuditPermission

__all__ = [
    'CRMPermission', 'TenantObjectPermission', 'OwnershipPermission',
    'AccountPermission', 'ContactPermission', 'IndustryPermission',
    'LeadPermission', 'LeadSourcePermission',
    'OpportunityPermission', 'PipelinePermission',
    'ActivityPermission', 'ActivityTypePermission',
    'CampaignPermission', 'CampaignMemberPermission',
    'TicketPermission', 'TicketCategoryPermission',
    'DocumentPermission', 'DocumentCategoryPermission',
    'TerritoryPermission', 'TeamPermission',
    'ProductPermission', 'ProductCategoryPermission',
    'AnalyticsPermission', 'ReportPermission', 'DashboardPermission',
    'WorkflowPermission', 'IntegrationPermission',
    'SystemAdminPermission', 'AuditPermission',
]