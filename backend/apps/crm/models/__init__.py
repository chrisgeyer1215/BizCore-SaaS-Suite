# ============================================================================
# backend/apps/crm/models/__init__.py - Model Registration and Imports
# ============================================================================

# Import all models to make them available at package level
from .base import *
from .user import *
from .account import *
from .lead import *
from .opportunity import *
from .activity import *
from .campaign import *
from .ticket import *
from .analytics import *
from .workflow import *
from .document import *
from .territory import *
from .product import *
from .system import *

# Model registration for Django admin and API exposure
__all__ = [
    # Base Models
    'CRMConfiguration',
    
    # User Management
    'CRMRole', 'CRMUserProfile',
    
    # Account Management  
    'Industry', 'Account', 'Contact',
    
    # Lead Management
    'LeadSource', 'Lead', 'LeadScoringRule',
    
    # Opportunity Management
    'Pipeline', 'PipelineStage', 'Opportunity', 'OpportunityTeamMember', 'OpportunityProduct',
    
    # Activity Management
    'ActivityType', 'Activity', 'ActivityParticipant', 'Note', 
    'EmailTemplate', 'EmailLog', 'CallLog', 'SMSLog',
    
    # Campaign Management
    'Campaign', 'CampaignTeamMember', 'CampaignMember', 'CampaignEmail',
    
    # Customer Service
    'TicketCategory', 'SLA', 'Ticket', 'TicketComment', 'KnowledgeBase',
    
    # Analytics & Reporting
    'Report', 'ReportShare', 'Dashboard', 'DashboardShare', 'Forecast', 'PerformanceMetric',
    
    # Workflow & Integration
    'WorkflowRule', 'WorkflowExecution', 'Integration', 'WebhookConfiguration',
    
    # Document Management
    'DocumentCategory', 'Document', 'DocumentShare',
    
    # Territory Management
    'Territory', 'Team', 'TeamMembership',
    
    # Product Management
    'ProductCategory', 'Product', 'PricingModel', 'ProductBundle', 'ProductBundleItem',
    
    # System Management
    'CustomField', 'AuditTrail', 'DataExportLog', 'APIUsageLog', 'SyncLog',
]