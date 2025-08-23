# backend/apps/crm/admin/__init__.py - Complete Admin Module Initialization
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _

# Import all admin classes
from .base import CRMAdminSite, BaseModelAdmin, TenantAwareAdmin
from .users import CRMUserProfileAdmin, TeamAdmin, TeamMembershipAdmin
from .account import AccountAdmin, ContactAdmin, IndustryAdmin
from .lead import LeadAdmin, LeadSourceAdmin, LeadScoringRuleAdmin
from .opportunity import OpportunityAdmin, PipelineAdmin, PipelineStageAdmin
from .activity import ActivityAdmin, ActivityTypeAdmin, EmailLogAdmin, CallLogAdmin
from .campaign import CampaignAdmin, CampaignMemberAdmin, EmailTemplateAdmin
# from .ticket import TicketAdmin, TicketCategoryAdmin, SLAAdmin, KnowledgeBaseAdmin
# from .document import DocumentAdmin, DocumentCategoryAdmin, DocumentShareAdmin
# from .territory import TerritoryAdmin, TerritoryAssignmentAdmin, TerritoryBoundaryAdmin
# from .product import ProductAdmin, ProductCategoryAdmin, PricingModelAdmin, ProductBundleAdmin
from .analytics import ReportAdmin, DashboardAdmin  # , AuditLogAdmin
# from .workflow import WorkflowRuleAdmin, WorkflowExecutionAdmin, IntegrationAdmin
# from .system import TaskExecutionAdmin, SecurityLogAdmin, DataAccessLogAdmin

# Create custom admin site
crm_admin = CRMAdminSite(name='crm_admin')

# Register all models with the custom admin site
crm_admin.register_models()

# Make all admin classes available for import
__all__ = [
    # Base classes
    'crm_admin', 'CRMAdminSite', 'BaseModelAdmin', 'TenantAwareAdmin',
    
    # User management
    'CRMUserProfileAdmin', 'TeamAdmin', 'TeamMembershipAdmin',
    
    # Account management
    'AccountAdmin', 'ContactAdmin', 'IndustryAdmin',
    
    # Lead management
    'LeadAdmin', 'LeadSourceAdmin', 'LeadScoringRuleAdmin',
    
    # Opportunity management
    'OpportunityAdmin', 'PipelineAdmin', 'PipelineStageAdmin',
    
    # Activity management
    'ActivityAdmin', 'ActivityTypeAdmin', 'EmailLogAdmin', 'CallLogAdmin',
    
    # Campaign management
    'CampaignAdmin', 'CampaignMemberAdmin', 'EmailTemplateAdmin',
    
    # Analytics
    'ReportAdmin', 'DashboardAdmin',  # 'AuditLogAdmin',
]