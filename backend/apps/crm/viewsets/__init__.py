# crm/viewsets/__init__.py
"""
CRM ViewSets Package

This package provides comprehensive REST API ViewSets for the CRM module.
All ViewSets are built on Django REST Framework and include:

- CRUD operations with proper permissions
- Filtering, searching, and ordering
- Bulk operations support
- Tenant-aware data access
- Advanced features like analytics and automation
- Comprehensive error handling
- Performance optimizations

Usage:
    from crm.viewsets import LeadViewSet, OpportunityViewSet
    from crm.viewsets.analytics import LeadAnalyticsViewSet
"""

# Import all ViewSets for easy access
from .base import (
    CRMBaseViewSet,
    CRMReadOnlyViewSet,
    BulkOperationMixin,
    AnalyticsMixin,
    ExportMixin,
    FilterMixin
)

from .account import (
    AccountViewSet,
    ContactViewSet,
    IndustryViewSet,
    AccountAnalyticsViewSet
)

from .lead import (
    LeadViewSet,
    LeadSourceViewSet,
    LeadScoringRuleViewSet,
    LeadAnalyticsViewSet,
    LeadBulkViewSet
)

from .opportunity import (
    OpportunityViewSet,
    PipelineStageViewSet,
    OpportunityProductViewSet,
    OpportunityAnalyticsViewSet,
    PipelineForecastViewSet
)

from .activity import (
    ActivityViewSet,
    ActivityTypeViewSet,
    NoteViewSet,
    EmailTemplateViewSet,
    EmailLogViewSet,
    CallLogViewSet,
    TaskViewSet
)

from .campaign import (
    CampaignViewSet,
    CampaignMemberViewSet,
    CampaignEmailViewSet,
    CampaignAnalyticsViewSet
)

from .ticket import (
    TicketViewSet,
    TicketCategoryViewSet,
    SLAViewSet,
    KnowledgeBaseViewSet,
    TicketAnalyticsViewSet
)

from .analytics import (
    CRMAnalyticsViewSet,
    ReportViewSet,
    DashboardViewSet,
    MetricsViewSet,
    ForecastViewSet
)

from .workflow import (
    WorkflowRuleViewSet,
    WorkflowExecutionViewSet,
    IntegrationViewSet,
    WebhookConfigurationViewSet,
    AutomationViewSet
)

from .document import (
    DocumentViewSet,
    DocumentCategoryViewSet,
    DocumentShareViewSet,
    DocumentAnalyticsViewSet
)

from .territory import (
    TerritoryViewSet,
    TeamViewSet,
    TeamMembershipViewSet,
    TerritoryAnalyticsViewSet
)

from .product import (
    ProductViewSet,
    ProductCategoryViewSet,
    PricingModelViewSet,
    ProductBundleViewSet,
    ProductAnalyticsViewSet
)

from .dashboard import (
    DashboardViewSet,
    DashboardWidgetViewSet,
    PersonalDashboardViewSet,
    TeamDashboardViewSet
)

__all__ = [
    # Base classes
    'CRMBaseViewSet',
    'CRMReadOnlyViewSet',
    'BulkOperationMixin',
    'AnalyticsMixin',
    'ExportMixin',
    'FilterMixin',
    
    # Account ViewSets
    'AccountViewSet',
    'ContactViewSet',
    'IndustryViewSet',
    'AccountAnalyticsViewSet',
    
    # Lead ViewSets
    'LeadViewSet',
    'LeadSourceViewSet',
    'LeadScoringRuleViewSet',
    'LeadAnalyticsViewSet',
    'LeadBulkViewSet',
    
    # Opportunity ViewSets
    'OpportunityViewSet',
    'PipelineStageViewSet',
    'OpportunityProductViewSet',
    'OpportunityAnalyticsViewSet',
    'PipelineForecastViewSet',
    
    # Activity ViewSets
    'ActivityViewSet',
    'ActivityTypeViewSet',
    'NoteViewSet',
    'EmailTemplateViewSet',
    'EmailLogViewSet',
    'CallLogViewSet',
    'TaskViewSet',
    
    # Campaign ViewSets
    'CampaignViewSet',
    'CampaignMemberViewSet',
    'CampaignEmailViewSet',
    'CampaignAnalyticsViewSet',
    
    # Ticket ViewSets
    'TicketViewSet',
    'TicketCategoryViewSet',
    'SLAViewSet',
    'KnowledgeBaseViewSet',
    'TicketAnalyticsViewSet',
    
    # Analytics ViewSets
    'CRMAnalyticsViewSet',
    'ReportViewSet',
    'DashboardViewSet',
    'MetricsViewSet',
    'ForecastViewSet',
    
    # Workflow ViewSets
    'WorkflowRuleViewSet',
    'WorkflowExecutionViewSet',
    'IntegrationViewSet',
    'WebhookConfigurationViewSet',
    'AutomationViewSet',
    
    # Document ViewSets
    'DocumentViewSet',
    'DocumentCategoryViewSet',
    'DocumentShareViewSet',
    'DocumentAnalyticsViewSet',
    
    # Territory ViewSets
    'TerritoryViewSet',
    'TeamViewSet',
    'TeamMembershipViewSet',
    'TerritoryAnalyticsViewSet',
    
    # Product ViewSets
    'ProductViewSet',
    'ProductCategoryViewSet',
    'PricingModelViewSet',
    'ProductBundleViewSet',
    'ProductAnalyticsViewSet',
    
    # Dashboard ViewSets
    'DashboardViewSet',
    'DashboardWidgetViewSet',
    'PersonalDashboardViewSet',
    'TeamDashboardViewSet',
]