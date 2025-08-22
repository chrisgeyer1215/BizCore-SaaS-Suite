# ============================================================================
# backend/apps/crm/serializers/__init__.py - Serializer Registration
# ============================================================================

# Base serializers
from .base import CRMConfigurationSerializer

# User management
from .user import (
    CRMRoleSerializer, UserBasicSerializer, CRMUserProfileSerializer
)

# Account management
from .account import (
    IndustrySerializer, AccountSerializer, ContactSerializer,
    ContactBasicSerializer, AccountDetailSerializer, ContactDetailSerializer
)

# Lead management
from .lead import (
    LeadSourceSerializer, LeadScoringRuleSerializer, LeadSerializer,
    LeadDetailSerializer, LeadConversionSerializer, LeadBulkUpdateSerializer
)

# Activity management
from .activity import (
    ActivityTypeSerializer, ActivitySerializer, ActivityParticipantSerializer,
    NoteSerializer, EmailTemplateSerializer, EmailLogSerializer,
    CallLogSerializer, SMSLogSerializer
)

# Opportunity management
from .opportunity import (
    PipelineSerializer, PipelineStageSerializer, OpportunitySerializer,
    OpportunityTeamMemberSerializer, OpportunityProductSerializer,
    OpportunityDetailSerializer, OpportunityCloseSerializer,
    OpportunityBulkUpdateSerializer
)

# Campaign management
from .campaign import (
    CampaignSerializer, CampaignTeamMemberSerializer, CampaignMemberSerializer,
    CampaignEmailSerializer, CampaignDetailSerializer, CampaignCreateSerializer,
    CampaignAnalyticsSerializer
)

# Ticket management
from .ticket import (
    TicketCategorySerializer, SLASerializer, TicketSerializer,
    TicketCommentSerializer, TicketDetailSerializer, KnowledgeBaseSerializer,
    TicketBulkUpdateSerializer, TicketEscalationSerializer
)

# Analytics & reporting
from .analytics import (
    ReportCategorySerializer, ReportSerializer, ReportShareSerializer,
    DashboardSerializer, DashboardWidgetSerializer, DashboardShareSerializer,
    ForecastSerializer, PerformanceMetricSerializer, MetricHistorySerializer,
    AnalyticsConfigurationSerializer, AlertRuleSerializer
)

# Territory management
from .territory import (
    TerritoryTypeSerializer, TerritorySerializer, TerritoryAssignmentSerializer,
    TeamSerializer, TeamMembershipSerializer, TerritoryAnalyticsSerializer,
    TeamAnalyticsSerializer
)

# Product management
from .product import (
    ProductCategorySerializer, ProductSerializer, ProductVariantSerializer,
    PricingModelSerializer, ProductBundleSerializer, ProductBundleItemSerializer,
    ProductAnalyticsSerializer, ProductBulkUpdateSerializer
)

# Document management
from .document import (
    DocumentCategorySerializer, DocumentSerializer, DocumentShareSerializer,
    DocumentDetailSerializer, DocumentUploadSerializer, DocumentBulkActionSerializer
)

# Workflow management
from .workflow import (
    WorkflowRuleSerializer, WorkflowExecutionSerializer,
    WorkflowAnalyticsSerializer, WorkflowTestSerializer
)

# System management
from .system import (
    CustomFieldSerializer, AuditTrailSerializer, DataExportLogSerializer,
    APIUsageLogSerializer, SyncLogSerializer, SystemAnalyticsSerializer,
    SystemHealthSerializer
)

# Export all serializers for easy importing
__all__ = [
    # Base
    'CRMConfigurationSerializer',
    
    # User management
    'CRMRoleSerializer', 'UserBasicSerializer', 'CRMUserProfileSerializer',
    
    # Account management
    'IndustrySerializer', 'AccountSerializer', 'ContactSerializer',
    'ContactBasicSerializer', 'AccountDetailSerializer', 'ContactDetailSerializer',
    
    # Lead management
    'LeadSourceSerializer', 'LeadScoringRuleSerializer', 'LeadSerializer',
    'LeadDetailSerializer', 'LeadConversionSerializer', 'LeadBulkUpdateSerializer',
    
    # Activity management
    'ActivityTypeSerializer', 'ActivitySerializer', 'ActivityParticipantSerializer',
    'NoteSerializer', 'EmailTemplateSerializer', 'EmailLogSerializer',
    'CallLogSerializer', 'SMSLogSerializer',
    
    # Opportunity management
    'PipelineSerializer', 'PipelineStageSerializer', 'OpportunitySerializer',
    'OpportunityTeamMemberSerializer', 'OpportunityProductSerializer',
    'OpportunityDetailSerializer', 'OpportunityCloseSerializer',
    'OpportunityBulkUpdateSerializer',
    
    # Campaign management
    'CampaignSerializer', 'CampaignTeamMemberSerializer', 'CampaignMemberSerializer',
    'CampaignEmailSerializer', 'CampaignDetailSerializer', 'CampaignCreateSerializer',
    'CampaignAnalyticsSerializer',
    
    # Ticket management
    'TicketCategorySerializer', 'SLASerializer', 'TicketSerializer',
    'TicketCommentSerializer', 'TicketDetailSerializer', 'KnowledgeBaseSerializer',
    'TicketBulkUpdateSerializer', 'TicketEscalationSerializer',
    
    # Analytics & reporting
    'ReportCategorySerializer', 'ReportSerializer', 'ReportShareSerializer',
    'DashboardSerializer', 'DashboardWidgetSerializer', 'DashboardShareSerializer',
    'ForecastSerializer', 'PerformanceMetricSerializer', 'MetricHistorySerializer',
    'AnalyticsConfigurationSerializer', 'AlertRuleSerializer',
    
    # Territory management
    'TerritoryTypeSerializer', 'TerritorySerializer', 'TerritoryAssignmentSerializer',
    'TeamSerializer', 'TeamMembershipSerializer', 'TerritoryAnalyticsSerializer',
    'TeamAnalyticsSerializer',
    
    # Product management
    'ProductCategorySerializer', 'ProductSerializer', 'ProductVariantSerializer',
    'PricingModelSerializer', 'ProductBundleSerializer', 'ProductBundleItemSerializer',
    'ProductAnalyticsSerializer', 'ProductBulkUpdateSerializer',
    
    # Document management
    'DocumentCategorySerializer', 'DocumentSerializer', 'DocumentShareSerializer',
    'DocumentDetailSerializer', 'DocumentUploadSerializer', 'DocumentBulkActionSerializer',
    
    # Workflow management
    'WorkflowRuleSerializer', 'WorkflowExecutionSerializer',
    'WorkflowAnalyticsSerializer', 'WorkflowTestSerializer',
    
    # System management
    'CustomFieldSerializer', 'AuditTrailSerializer', 'DataExportLogSerializer',
    'APIUsageLogSerializer', 'SyncLogSerializer', 'SystemAnalyticsSerializer',
    'SystemHealthSerializer',
]