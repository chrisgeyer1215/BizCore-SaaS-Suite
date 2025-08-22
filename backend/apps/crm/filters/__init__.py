# ============================================================================
# backend/apps/crm/filters/__init__.py
# ============================================================================

from .account import AccountFilter, ContactFilter, IndustryFilter
from .lead import LeadFilter, LeadSourceFilter
from .opportunity import OpportunityFilter, PipelineFilter, PipelineStageFilter
from .activity import ActivityFilter, ActivityTypeFilter
from .campaign import CampaignFilter, CampaignMemberFilter
from .ticket import TicketFilter, TicketCategoryFilter
from .document import DocumentFilter, DocumentCategoryFilter
from .territory import TerritoryFilter, TeamFilter
from .product import ProductFilter, ProductCategoryFilter, ProductBundleFilter
from .analytics import ReportFilter, DashboardFilter
from .workflow import WorkflowRuleFilter, WorkflowExecutionFilter
from .user import CRMUserProfileFilter

__all__ = [
    'AccountFilter', 'ContactFilter', 'IndustryFilter',
    'LeadFilter', 'LeadSourceFilter',
    'OpportunityFilter', 'PipelineFilter', 'PipelineStageFilter',
    'ActivityFilter', 'ActivityTypeFilter',
    'CampaignFilter', 'CampaignMemberFilter',
    'TicketFilter', 'TicketCategoryFilter',
    'DocumentFilter', 'DocumentCategoryFilter',
    'TerritoryFilter', 'TeamFilter',
    'ProductFilter', 'ProductCategoryFilter', 'ProductBundleFilter',
    'ReportFilter', 'DashboardFilter',
    'WorkflowRuleFilter', 'WorkflowExecutionFilter',
    'CRMUserProfileFilter',
]