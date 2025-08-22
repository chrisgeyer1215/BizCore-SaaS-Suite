# ============================================================================
# backend/apps/crm/urls.py - Complete CRM URLs
# ============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import all view modules
from .views import (
    base, account, lead, opportunity, activity, campaign, ticket,
    document, territory, product, analytics, workflow, system
)

# Create API router
router = DefaultRouter()

# Register all ViewSets
router.register(r'accounts', account.AccountViewSet)
router.register(r'contacts', account.ContactViewSet)
router.register(r'industries', account.IndustryViewSet)

router.register(r'leads', lead.LeadViewSet)
router.register(r'lead-sources', lead.LeadSourceViewSet)

router.register(r'opportunities', opportunity.OpportunityViewSet)
router.register(r'pipelines', opportunity.PipelineViewSet)
router.register(r'pipeline-stages', opportunity.PipelineStageViewSet)

router.register(r'activities', activity.ActivityViewSet)
router.register(r'activity-types', activity.ActivityTypeViewSet)

router.register(r'campaigns', campaign.CampaignViewSet)
router.register(r'campaign-members', campaign.CampaignMemberViewSet)

router.register(r'tickets', ticket.TicketViewSet)
router.register(r'ticket-categories', ticket.TicketCategoryViewSet)

router.register(r'documents', document.DocumentViewSet)
router.register(r'document-categories', document.DocumentCategoryViewSet)

router.register(r'territories', territory.TerritoryViewSet)
router.register(r'teams', territory.TeamViewSet)

router.register(r'products', product.ProductViewSet)
router.register(r'product-categories', product.ProductCategoryViewSet)
router.register(r'product-bundles', product.ProductBundleViewSet)

router.register(r'reports', analytics.ReportViewSet)
router.register(r'dashboards', analytics.DashboardViewSet)
router.register(r'forecasts', analytics.ForecastViewSet)

router.register(r'workflow-rules', workflow.WorkflowRuleViewSet)
router.register(r'workflow-executions', workflow.WorkflowExecutionViewSet)
router.register(r'integrations', workflow.IntegrationViewSet)
router.register(r'webhooks', workflow.WebhookConfigurationViewSet)
router.register(r'custom-fields', workflow.CustomFieldViewSet)

router.register(r'audit-trails', system.AuditTrailViewSet)
router.register(r'export-logs', system.DataExportLogViewSet)
router.register(r'api-logs', system.APIUsageLogViewSet)
router.register(r'sync-logs', system.SyncLogViewSet)

app_name = 'crm'

urlpatterns = [
    # Dashboard and Base Views
    path('', base.CRMDashboardView.as_view(), name='dashboard'),
    path('configuration/', base.CRMConfigurationView.as_view(), name='configuration'),
    path('health/', base.CRMHealthCheckView.as_view(), name='health-check'),
    
    # Account Management URLs
    path('accounts/', account.AccountListView.as_view(), name='account-list'),
    path('accounts/<int:pk>/', account.AccountDetailView.as_view(), name='account-detail'),
    path('accounts/create/', account.AccountCreateView.as_view(), name='account-create'),
    path('accounts/<int:pk>/update/', account.AccountUpdateView.as_view(), name='account-update'),
    path('contacts/', account.ContactListView.as_view(), name='contact-list'),
    path('contacts/<int:pk>/', account.ContactDetailView.as_view(), name='contact-detail'),
    
    # Lead Management URLs
    path('leads/', lead.LeadListView.as_view(), name='lead-list'),
    path('leads/<int:pk>/', lead.LeadDetailView.as_view(), name='lead-detail'),
    path('leads/create/', lead.LeadCreateView.as_view(), name='lead-create'),
    path('leads/<int:pk>/update/', lead.LeadUpdateView.as_view(), name='lead-update'),
    path('leads/import/', lead.LeadImportView.as_view(), name='lead-import'),
    path('leads/scoring/', lead.LeadScoringView.as_view(), name='lead-scoring'),
    
    # Opportunity Management URLs
    path('opportunities/', opportunity.OpportunityListView.as_view(), name='opportunity-list'),
    path('opportunities/<int:pk>/', opportunity.OpportunityDetailView.as_view(), name='opportunity-detail'),
    path('opportunities/create/', opportunity.OpportunityCreateView.as_view(), name='opportunity-create'),
    path('opportunities/<int:pk>/update/', opportunity.OpportunityUpdateView.as_view(), name='opportunity-update'),
    path('opportunities/pipeline/', opportunity.PipelineManagementView.as_view(), name='pipeline-management'),
    path('opportunities/forecasting/', opportunity.ForecastingView.as_view(), name='forecasting'),
    
    # Activity Management URLs
    path('activities/', activity.ActivityListView.as_view(), name='activity-list'),
    path('activities/<int:pk>/', activity.ActivityDetailView.as_view(), name='activity-detail'),
    path('activities/create/', activity.ActivityCreateView.as_view(), name='activity-create'),
    path('activities/<int:pk>/update/', activity.ActivityUpdateView.as_view(), name='activity-update'),
    path('activities/calendar/', activity.ActivityCalendarView.as_view(), name='activity-calendar'),
    path('activities/dashboard/', activity.ActivityDashboardView.as_view(), name='activity-dashboard'),
    
    # Campaign Management URLs
    path('campaigns/', campaign.CampaignListView.as_view(), name='campaign-list'),
    path('campaigns/<int:pk>/', campaign.CampaignDetailView.as_view(), name='campaign-detail'),
    path('campaigns/create/', campaign.CampaignCreateView.as_view(), name='campaign-create'),
    path('campaigns/<int:pk>/update/', campaign.CampaignUpdateView.as_view(), name='campaign-update'),
    path('campaigns/dashboard/', campaign.CampaignDashboardView.as_view(), name='campaign-dashboard'),
    
    # Customer Service URLs
    path('tickets/', ticket.TicketListView.as_view(), name='ticket-list'),
    path('tickets/<int:pk>/', ticket.TicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/create/', ticket.TicketCreateView.as_view(), name='ticket-create'),
    path('tickets/<int:pk>/update/', ticket.TicketUpdateView.as_view(), name='ticket-update'),
    path('tickets/dashboard/', ticket.SupportDashboardView.as_view(), name='support-dashboard'),
    path('knowledge-base/', ticket.KnowledgeBaseView.as_view(), name='knowledge-base'),
    
    # Document Management URLs
    path('documents/', document.DocumentListView.as_view(), name='document-list'),
    path('documents/<int:pk>/', document.DocumentDetailView.as_view(), name='document-detail'),
    path('documents/upload/', document.DocumentUploadView.as_view(), name='document-upload'),
    path('documents/<int:pk>/download/', document.DocumentDownloadView.as_view(), name='document-download'),
    
    # Territory Management URLs
    path('territories/', territory.TerritoryListView.as_view(), name='territory-list'),
    path('territories/<int:pk>/', territory.TerritoryDetailView.as_view(), name='territory-detail'),
    path('territories/optimization/', territory.TerritoryOptimizationView.as_view(), name='territory-optimization'),
    path('teams/', territory.TeamListView.as_view(), name='team-list'),
    path('teams/<int:pk>/', territory.TeamDetailView.as_view(), name='team-detail'),
    
    # Product Management URLs
    path('products/', product.ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', product.ProductDetailView.as_view(), name='product-detail'),
    path('product-categories/', product.ProductCategoryListView.as_view(), name='product-category-list'),
    path('product-bundles/', product.ProductBundleListView.as_view(), name='product-bundle-list'),
    path('product-bundles/<int:pk>/', product.ProductBundleDetailView.as_view(), name='product-bundle-detail'),
    
    # Analytics & Reporting URLs
    path('analytics/', analytics.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('reports/', analytics.ReportListView.as_view(), name='report-list'),
    path('reports/<int:pk>/', analytics.ReportDetailView.as_view(), name='report-detail'),
    path('reports/builder/', analytics.ReportBuilderView.as_view(), name='report-builder'),
    path('dashboards/', analytics.DashboardListView.as_view(), name='dashboard-list'),
    path('dashboards/<int:pk>/', analytics.DashboardDetailView.as_view(), name='dashboard-detail'),
    path('forecasting/', analytics.ForecastingView.as_view(), name='forecasting'),
    
    # Workflow & Automation URLs
    path('workflows/', workflow.WorkflowRuleListView.as_view(), name='workflow-rule-list'),
    path('workflows/<int:pk>/', workflow.WorkflowRuleDetailView.as_view(), name='workflow-rule-detail'),
    path('workflows/create/', workflow.WorkflowRuleCreateView.as_view(), name='workflow-rule-create'),
    path('workflows/<int:pk>/update/', workflow.WorkflowRuleUpdateView.as_view(), name='workflow-rule-update'),
    path('workflows/executions/', workflow.WorkflowExecutionListView.as_view(), name='workflow-execution-list'),
    path('integrations/', workflow.IntegrationListView.as_view(), name='integration-list'),
    path('integrations/<int:pk>/', workflow.IntegrationDetailView.as_view(), name='integration-detail'),
    path('custom-fields/', workflow.CustomFieldListView.as_view(), name='custom-field-list'),
    
    # System Administration URLs
    path('system/', system.SystemDashboardView.as_view(), name='system-dashboard'),
    path('system/audit-trail/', system.AuditTrailListView.as_view(), name='audit-trail'),
    path('system/export/', system.DataExportView.as_view(), name='data-export'),
    path('system/import/', system.DataImportView.as_view(), name='data-import'),
    path('system/configuration/', system.SystemConfigurationView.as_view(), name='system-configuration'),
    path('system/maintenance/', system.SystemMaintenanceView.as_view(), name='system-maintenance'),
    
    # API URLs
    path('api/', include(router.urls)),
]