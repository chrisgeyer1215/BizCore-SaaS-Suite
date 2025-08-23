# backend/apps/crm/urls.py - Complete CRM URL Configuration
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

# Import ViewSets
from .viewsets import (
    # Core CRM ViewSets
    AccountViewSet, ContactViewSet, IndustryViewSet,
    LeadViewSet, LeadSourceViewSet, LeadScoringRuleViewSet,
    OpportunityViewSet, PipelineViewSet, PipelineStageViewSet,
    ActivityViewSet, ActivityTypeViewSet, EmailLogViewSet, CallLogViewSet,
    CampaignViewSet, CampaignMemberViewSet, EmailTemplateViewSet,
    TicketViewSet, TicketCategoryViewSet, SLAViewSet, KnowledgeBaseViewSet,
    DocumentViewSet, DocumentCategoryViewSet, DocumentShareViewSet,
    TerritoryViewSet, TerritoryAssignmentViewSet, TeamViewSet, TeamMembershipViewSet,
    ProductViewSet, ProductCategoryViewSet, PricingModelViewSet, ProductBundleViewSet,
    ReportViewSet, DashboardViewSet, AnalyticsViewSet,
    WorkflowRuleViewSet, WorkflowExecutionViewSet, IntegrationViewSet,
    TaskExecutionViewSet, AuditLogViewSet, SecurityLogViewSet,
    CRMUserProfileViewSet, CRMConfigurationViewSet,
)

# Import Views
from .views import (
    # Dashboard Views
    DashboardView, AnalyticsDashboardView, 
    # Account Views
    AccountListCreateView, AccountRetrieveUpdateDestroyView, AccountAnalyticsView,
    # Lead Views
    LeadListCreateView, LeadRetrieveUpdateDestroyView, LeadConversionView,
    # Opportunity Views
    OpportunityListCreateView, OpportunityRetrieveUpdateDestroyView,
    OpportunityPipelineView, OpportunityForecastView,
    # Activity Views
    ActivityTimelineView, ActivityReminderView,
    # Campaign Views
    CampaignPerformanceView, CampaignLaunchView,
    # Support Views
    TicketDashboardView, SupportMetricsView,
    # Analytics Views
    SalesPipelineAnalyticsView, LeadConversionAnalyticsView,
    CampaignAnalyticsView, CustomerAnalyticsView,
    # System Views
    SystemHealthView, AuditTrailView,
    # Bulk Operations
    BulkImportView, BulkExportView, BulkUpdateView,
    # Integration Views
    WebhookView, APIStatsView,
)

app_name = 'crm'

# Main API Router
router = DefaultRouter()

# Core CRM Resources
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'industries', IndustryViewSet, basename='industry')

router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'lead-sources', LeadSourceViewSet, basename='leadsource')
router.register(r'lead-scoring-rules', LeadScoringRuleViewSet, basename='leadscoringrule')

router.register(r'opportunities', OpportunityViewSet, basename='opportunity')
router.register(r'pipelines', PipelineViewSet, basename='pipeline')
router.register(r'pipeline-stages', PipelineStageViewSet, basename='pipelinestage')

router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'activity-types', ActivityTypeViewSet, basename='activitytype')
router.register(r'email-logs', EmailLogViewSet, basename='emaillog')
router.register(r'call-logs', CallLogViewSet, basename='calllog')

router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'campaign-members', CampaignMemberViewSet, basename='campaignmember')
router.register(r'email-templates', EmailTemplateViewSet, basename='emailtemplate')

router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'ticket-categories', TicketCategoryViewSet, basename='ticketcategory')
router.register(r'slas', SLAViewSet, basename='sla')
router.register(r'knowledge-base', KnowledgeBaseViewSet, basename='knowledgebase')

router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'document-categories', DocumentCategoryViewSet, basename='documentcategory')
router.register(r'document-shares', DocumentShareViewSet, basename='documentshare')

router.register(r'territories', TerritoryViewSet, basename='territory')
router.register(r'territory-assignments', TerritoryAssignmentViewSet, basename='territoryassignment')
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'team-memberships', TeamMembershipViewSet, basename='teammembership')

router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-categories', ProductCategoryViewSet, basename='productcategory')
router.register(r'pricing-models', PricingModelViewSet, basename='pricingmodel')
router.register(r'product-bundles', ProductBundleViewSet, basename='productbundle')

router.register(r'reports', ReportViewSet, basename='report')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

router.register(r'workflows', WorkflowRuleViewSet, basename='workflowrule')
router.register(r'workflow-executions', WorkflowExecutionViewSet, basename='workflowexecution')
router.register(r'integrations', IntegrationViewSet, basename='integration')

router.register(r'tasks', TaskExecutionViewSet, basename='taskexecution')
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')
router.register(r'security-logs', SecurityLogViewSet, basename='securitylog')

router.register(r'user-profiles', CRMUserProfileViewSet, basename='crmuserprofile')
router.register(r'configurations', CRMConfigurationViewSet, basename='crmconfiguration')

# Nested Routers for Related Resources
accounts_router = routers.NestedDefaultRouter(router, r'accounts', lookup='account')
accounts_router.register(r'contacts', ContactViewSet, basename='account-contacts')
accounts_router.register(r'opportunities', OpportunityViewSet, basename='account-opportunities')
accounts_router.register(r'activities', ActivityViewSet, basename='account-activities')
accounts_router.register(r'documents', DocumentViewSet, basename='account-documents')
accounts_router.register(r'tickets', TicketViewSet, basename='account-tickets')

leads_router = routers.NestedDefaultRouter(router, r'leads', lookup='lead')
leads_router.register(r'activities', ActivityViewSet, basename='lead-activities')
leads_router.register(r'notes', ActivityViewSet, basename='lead-notes')

opportunities_router = routers.NestedDefaultRouter(router, r'opportunities', lookup='opportunity')
opportunities_router.register(r'activities', ActivityViewSet, basename='opportunity-activities')
opportunities_router.register(r'products', ProductViewSet, basename='opportunity-products')
opportunities_router.register(r'documents', DocumentViewSet, basename='opportunity-documents')

campaigns_router = routers.NestedDefaultRouter(router, r'campaigns', lookup='campaign')
campaigns_router.register(r'members', CampaignMemberViewSet, basename='campaign-members')
campaigns_router.register(r'emails', EmailLogViewSet, basename='campaign-emails')
campaigns_router.register(r'analytics', AnalyticsViewSet, basename='campaign-analytics')

tickets_router = routers.NestedDefaultRouter(router, r'tickets', lookup='ticket')
tickets_router.register(r'comments', ActivityViewSet, basename='ticket-comments')
tickets_router.register(r'attachments', DocumentViewSet, basename='ticket-attachments')

teams_router = routers.NestedDefaultRouter(router, r'teams', lookup='team')
teams_router.register(r'members', TeamMembershipViewSet, basename='team-members')

urlpatterns = [
    # API ViewSets (DRF Router)
    path('api/', include(router.urls)),
    path('api/', include(accounts_router.urls)),
    path('api/', include(leads_router.urls)),
    path('api/', include(opportunities_router.urls)),
    path('api/', include(campaigns_router.urls)),
    path('api/', include(tickets_router.urls)),
    path('api/', include(teams_router.urls)),

    # Dashboard URLs
    path('', DashboardView.as_view(), name='dashboard'),
    path('dashboard/', DashboardView.as_view(), name='crm-dashboard'),
    path('analytics-dashboard/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),

    # Account Management URLs
    path('accounts/', AccountListCreateView.as_view(), name='account-list'),
    path('accounts/<int:pk>/', AccountRetrieveUpdateDestroyView.as_view(), name='account-detail'),
    path('accounts/<int:pk>/analytics/', AccountAnalyticsView.as_view(), name='account-analytics'),
    path('accounts/<int:pk>/merge/', AccountViewSet.as_view({'post': 'merge_accounts'}), name='account-merge'),
    path('accounts/<int:pk>/transfer/', AccountViewSet.as_view({'post': 'transfer_ownership'}), name='account-transfer'),

    # Lead Management URLs
    path('leads/', LeadListCreateView.as_view(), name='lead-list'),
    path('leads/<int:pk>/', LeadRetrieveUpdateDestroyView.as_view(), name='lead-detail'),
    path('leads/<int:pk>/convert/', LeadConversionView.as_view(), name='lead-convert'),
    path('leads/<int:pk>/score/', LeadViewSet.as_view({'post': 'calculate_score'}), name='lead-score'),
    path('leads/<int:pk>/assign/', LeadViewSet.as_view({'post': 'assign_lead'}), name='lead-assign'),

    # Opportunity Management URLs
    path('opportunities/', OpportunityListCreateView.as_view(), name='opportunity-list'),
    path('opportunities/<int:pk>/', OpportunityRetrieveUpdateDestroyView.as_view(), name='opportunity-detail'),
    path('opportunities/<int:pk>/close-won/', OpportunityViewSet.as_view({'post': 'close_won'}), name='opportunity-close-won'),
    path('opportunities/<int:pk>/close-lost/', OpportunityViewSet.as_view({'post': 'close_lost'}), name='opportunity-close-lost'),
    path('opportunities/<int:pk>/reopen/', OpportunityViewSet.as_view({'post': 'reopen'}), name='opportunity-reopen'),
    path('opportunities/pipeline/', OpportunityPipelineView.as_view(), name='opportunity-pipeline'),
    path('opportunities/forecast/', OpportunityForecastView.as_view(), name='opportunity-forecast'),

    # Activity Management URLs
    path('activities/timeline/', ActivityTimelineView.as_view(), name='activity-timeline'),
    path('activities/reminders/', ActivityReminderView.as_view(), name='activity-reminders'),
    path('activities/<int:pk>/complete/', ActivityViewSet.as_view({'post': 'mark_complete'}), name='activity-complete'),

    # Campaign Management URLs
    path('campaigns/<int:pk>/launch/', CampaignLaunchView.as_view(), name='campaign-launch'),
    path('campaigns/<int:pk>/pause/', CampaignViewSet.as_view({'post': 'pause'}), name='campaign-pause'),
    path('campaigns/<int:pk>/performance/', CampaignPerformanceView.as_view(), name='campaign-performance'),
    path('campaigns/<int:pk>/clone/', CampaignViewSet.as_view({'post': 'clone'}), name='campaign-clone'),

    # Support Management URLs
    path('tickets/dashboard/', TicketDashboardView.as_view(), name='ticket-dashboard'),
    path('tickets/<int:pk>/assign/', TicketViewSet.as_view({'post': 'assign'}), name='ticket-assign'),
    path('tickets/<int:pk>/escalate/', TicketViewSet.as_view({'post': 'escalate'}), name='ticket-escalate'),
    path('tickets/<int:pk>/resolve/', TicketViewSet.as_view({'post': 'resolve'}), name='ticket-resolve'),
    path('support/metrics/', SupportMetricsView.as_view(), name='support-metrics'),

    # Analytics URLs
    path('analytics/sales-pipeline/', SalesPipelineAnalyticsView.as_view(), name='analytics-sales-pipeline'),
    path('analytics/lead-conversion/', LeadConversionAnalyticsView.as_view(), name='analytics-lead-conversion'),
    path('analytics/campaigns/', CampaignAnalyticsView.as_view(), name='analytics-campaigns'),
    path('analytics/customers/', CustomerAnalyticsView.as_view(), name='analytics-customers'),
    path('analytics/revenue-forecast/', AnalyticsViewSet.as_view({'get': 'revenue_forecast'}), name='analytics-revenue-forecast'),
    path('analytics/performance-metrics/', AnalyticsViewSet.as_view({'get': 'performance_metrics'}), name='analytics-performance'),

    # Document Management URLs
    path('documents/<int:pk>/download/', DocumentViewSet.as_view({'get': 'download'}), name='document-download'),
    path('documents/<int:pk>/share/', DocumentViewSet.as_view({'post': 'share'}), name='document-share'),
    path('documents/<int:pk>/versions/', DocumentViewSet.as_view({'get': 'versions'}), name='document-versions'),

    # Territory & Team Management URLs
    path('territories/<int:pk>/assign/', TerritoryViewSet.as_view({'post': 'assign_users'}), name='territory-assign'),
    path('teams/<int:pk>/performance/', TeamViewSet.as_view({'get': 'performance_metrics'}), name='team-performance'),

    # Workflow & Automation URLs
    path('workflows/<int:pk>/execute/', WorkflowRuleViewSet.as_view({'post': 'execute'}), name='workflow-execute'),
    path('workflows/<int:pk>/test/', WorkflowRuleViewSet.as_view({'post': 'test'}), name='workflow-test'),

    # Bulk Operations URLs
    path('bulk/import/', BulkImportView.as_view(), name='bulk-import'),
    path('bulk/export/', BulkExportView.as_view(), name='bulk-export'),
    path('bulk/update/', BulkUpdateView.as_view(), name='bulk-update'),
    path('bulk/leads/import/', LeadViewSet.as_view({'post': 'bulk_import'}), name='bulk-leads-import'),
    path('bulk/accounts/import/', AccountViewSet.as_view({'post': 'bulk_import'}), name='bulk-accounts-import'),
    path('bulk/contacts/import/', ContactViewSet.as_view({'post': 'bulk_import'}), name='bulk-contacts-import'),

    # System Management URLs
    path('system/health/', SystemHealthView.as_view(), name='system-health'),
    path('system/audit/', AuditTrailView.as_view(), name='audit-trail'),
    path('system/stats/', APIStatsView.as_view(), name='api-stats'),

    # Webhook & Integration URLs
    path('webhooks/', WebhookView.as_view(), name='webhooks'),
    path('webhooks/<str:webhook_id>/', WebhookView.as_view(), name='webhook-handler'),
    path('integrations/<int:pk>/test/', IntegrationViewSet.as_view({'post': 'test_connection'}), name='integration-test'),
    path('integrations/<int:pk>/sync/', IntegrationViewSet.as_view({'post': 'sync_data'}), name='integration-sync'),

    # Search URLs
    path('search/', include([
        path('global/', AccountViewSet.as_view({'get': 'global_search'}), name='global-search'),
        path('accounts/', AccountViewSet.as_view({'get': 'search'}), name='search-accounts'),
        path('leads/', LeadViewSet.as_view({'get': 'search'}), name='search-leads'),
        path('opportunities/', OpportunityViewSet.as_view({'get': 'search'}), name='search-opportunities'),
        path('activities/', ActivityViewSet.as_view({'get': 'search'}), name='search-activities'),
    ])),

    # Configuration URLs
    path('settings/', include([
        path('', CRMConfigurationViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='crm-settings'),
        path('lead-scoring/', LeadScoringRuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='lead-scoring-settings'),
        path('pipelines/', PipelineViewSet.as_view({'get': 'list', 'post': 'create'}), name='pipeline-settings'),
        path('email-templates/', EmailTemplateViewSet.as_view({'get': 'list', 'post': 'create'}), name='email-template-settings'),
    ])),

    # Mobile API URLs
    path('mobile/', include([
        path('dashboard/', DashboardViewSet.as_view({'get': 'mobile_dashboard'}), name='mobile-dashboard'),
        path('accounts/', AccountViewSet.as_view({'get': 'mobile_list'}), name='mobile-accounts'),
        path('leads/', LeadViewSet.as_view({'get': 'mobile_list'}), name='mobile-leads'),
        path('activities/', ActivityViewSet.as_view({'get': 'mobile_activities'}), name='mobile-activities'),
    ])),

    # Report URLs
    path('reports/', include([
        path('', ReportViewSet.as_view({'get': 'list'}), name='reports-list'),
        path('<int:pk>/', ReportViewSet.as_view({'get': 'retrieve'}), name='report-detail'),
        path('<int:pk>/run/', ReportViewSet.as_view({'post': 'run_report'}), name='report-run'),
        path('<int:pk>/schedule/', ReportViewSet.as_view({'post': 'schedule'}), name='report-schedule'),
        path('<int:pk>/export/', ReportViewSet.as_view({'get': 'export'}), name='report-export'),
    ])),

    # Advanced Features URLs
    path('advanced/', include([
        # AI & ML Features
        path('ai/lead-scoring/', LeadViewSet.as_view({'post': 'ai_score_leads'}), name='ai-lead-scoring'),
        path('ai/opportunity-prediction/', OpportunityViewSet.as_view({'post': 'predict_outcome'}), name='ai-opportunity-prediction'),
        path('ai/next-best-action/', AnalyticsViewSet.as_view({'get': 'next_best_action'}), name='ai-next-best-action'),
        
        # Advanced Analytics
        path('analytics/cohort-analysis/', AnalyticsViewSet.as_view({'get': 'cohort_analysis'}), name='cohort-analysis'),
        path('analytics/customer-lifetime-value/', AnalyticsViewSet.as_view({'get': 'customer_lifetime_value'}), name='customer-ltv'),
        path('analytics/churn-prediction/', AnalyticsViewSet.as_view({'get': 'churn_prediction'}), name='churn-prediction'),
        
        # Automation
        path('automation/rules/', WorkflowRuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='automation-rules'),
        path('automation/triggers/', WorkflowRuleViewSet.as_view({'get': 'available_triggers'}), name='automation-triggers'),
    ])),
]

# URL patterns for different API versions
v1_patterns = [
    path('v1/crm/', include(urlpatterns)),
]

# Export patterns for main urls.py
api_patterns = [
    path('api/', include(v1_patterns)),
]










# # ============================================================================
# # backend/apps/crm/urls.py - Complete CRM URLs
# # ============================================================================

# from django.urls import path, include
# from rest_framework.routers import DefaultRouter

# # Import all view modules
# from .views import (
#     base, account, lead, opportunity, activity, campaign, ticket,
#     document, territory, product, analytics, workflow, system
# )

# # Create API router
# router = DefaultRouter()

# # Register all ViewSets
# router.register(r'accounts', account.AccountViewSet)
# router.register(r'contacts', account.ContactViewSet)
# router.register(r'industries', account.IndustryViewSet)

# router.register(r'leads', lead.LeadViewSet)
# router.register(r'lead-sources', lead.LeadSourceViewSet)

# router.register(r'opportunities', opportunity.OpportunityViewSet)
# router.register(r'pipelines', opportunity.PipelineViewSet)
# router.register(r'pipeline-stages', opportunity.PipelineStageViewSet)

# router.register(r'activities', activity.ActivityViewSet)
# router.register(r'activity-types', activity.ActivityTypeViewSet)

# router.register(r'campaigns', campaign.CampaignViewSet)
# router.register(r'campaign-members', campaign.CampaignMemberViewSet)

# router.register(r'tickets', ticket.TicketViewSet)
# router.register(r'ticket-categories', ticket.TicketCategoryViewSet)

# router.register(r'documents', document.DocumentViewSet)
# router.register(r'document-categories', document.DocumentCategoryViewSet)

# router.register(r'territories', territory.TerritoryViewSet)
# router.register(r'teams', territory.TeamViewSet)

# router.register(r'products', product.ProductViewSet)
# router.register(r'product-categories', product.ProductCategoryViewSet)
# router.register(r'product-bundles', product.ProductBundleViewSet)

# router.register(r'reports', analytics.ReportViewSet)
# router.register(r'dashboards', analytics.DashboardViewSet)
# router.register(r'forecasts', analytics.ForecastViewSet)

# router.register(r'workflow-rules', workflow.WorkflowRuleViewSet)
# router.register(r'workflow-executions', workflow.WorkflowExecutionViewSet)
# router.register(r'integrations', workflow.IntegrationViewSet)
# router.register(r'webhooks', workflow.WebhookConfigurationViewSet)
# router.register(r'custom-fields', workflow.CustomFieldViewSet)

# router.register(r'audit-trails', system.AuditTrailViewSet)
# router.register(r'export-logs', system.DataExportLogViewSet)
# router.register(r'api-logs', system.APIUsageLogViewSet)
# router.register(r'sync-logs', system.SyncLogViewSet)

# app_name = 'crm'

# urlpatterns = [
#     # Dashboard and Base Views
#     path('', base.CRMDashboardView.as_view(), name='dashboard'),
#     path('configuration/', base.CRMConfigurationView.as_view(), name='configuration'),
#     path('health/', base.CRMHealthCheckView.as_view(), name='health-check'),
    
#     # Account Management URLs
#     path('accounts/', account.AccountListView.as_view(), name='account-list'),
#     path('accounts/<int:pk>/', account.AccountDetailView.as_view(), name='account-detail'),
#     path('accounts/create/', account.AccountCreateView.as_view(), name='account-create'),
#     path('accounts/<int:pk>/update/', account.AccountUpdateView.as_view(), name='account-update'),
#     path('contacts/', account.ContactListView.as_view(), name='contact-list'),
#     path('contacts/<int:pk>/', account.ContactDetailView.as_view(), name='contact-detail'),
    
#     # Lead Management URLs
#     path('leads/', lead.LeadListView.as_view(), name='lead-list'),
#     path('leads/<int:pk>/', lead.LeadDetailView.as_view(), name='lead-detail'),
#     path('leads/create/', lead.LeadCreateView.as_view(), name='lead-create'),
#     path('leads/<int:pk>/update/', lead.LeadUpdateView.as_view(), name='lead-update'),
#     path('leads/import/', lead.LeadImportView.as_view(), name='lead-import'),
#     path('leads/scoring/', lead.LeadScoringView.as_view(), name='lead-scoring'),
    
#     # Opportunity Management URLs
#     path('opportunities/', opportunity.OpportunityListView.as_view(), name='opportunity-list'),
#     path('opportunities/<int:pk>/', opportunity.OpportunityDetailView.as_view(), name='opportunity-detail'),
#     path('opportunities/create/', opportunity.OpportunityCreateView.as_view(), name='opportunity-create'),
#     path('opportunities/<int:pk>/update/', opportunity.OpportunityUpdateView.as_view(), name='opportunity-update'),
#     path('opportunities/pipeline/', opportunity.PipelineManagementView.as_view(), name='pipeline-management'),
#     path('opportunities/forecasting/', opportunity.ForecastingView.as_view(), name='forecasting'),
    
#     # Activity Management URLs
#     path('activities/', activity.ActivityListView.as_view(), name='activity-list'),
#     path('activities/<int:pk>/', activity.ActivityDetailView.as_view(), name='activity-detail'),
#     path('activities/create/', activity.ActivityCreateView.as_view(), name='activity-create'),
#     path('activities/<int:pk>/update/', activity.ActivityUpdateView.as_view(), name='activity-update'),
#     path('activities/calendar/', activity.ActivityCalendarView.as_view(), name='activity-calendar'),
#     path('activities/dashboard/', activity.ActivityDashboardView.as_view(), name='activity-dashboard'),
    
#     # Campaign Management URLs
#     path('campaigns/', campaign.CampaignListView.as_view(), name='campaign-list'),
#     path('campaigns/<int:pk>/', campaign.CampaignDetailView.as_view(), name='campaign-detail'),
#     path('campaigns/create/', campaign.CampaignCreateView.as_view(), name='campaign-create'),
#     path('campaigns/<int:pk>/update/', campaign.CampaignUpdateView.as_view(), name='campaign-update'),
#     path('campaigns/dashboard/', campaign.CampaignDashboardView.as_view(), name='campaign-dashboard'),
    
#     # Customer Service URLs
#     path('tickets/', ticket.TicketListView.as_view(), name='ticket-list'),
#     path('tickets/<int:pk>/', ticket.TicketDetailView.as_view(), name='ticket-detail'),
#     path('tickets/create/', ticket.TicketCreateView.as_view(), name='ticket-create'),
#     path('tickets/<int:pk>/update/', ticket.TicketUpdateView.as_view(), name='ticket-update'),
#     path('tickets/dashboard/', ticket.SupportDashboardView.as_view(), name='support-dashboard'),
#     path('knowledge-base/', ticket.KnowledgeBaseView.as_view(), name='knowledge-base'),
    
#     # Document Management URLs
#     path('documents/', document.DocumentListView.as_view(), name='document-list'),
#     path('documents/<int:pk>/', document.DocumentDetailView.as_view(), name='document-detail'),
#     path('documents/upload/', document.DocumentUploadView.as_view(), name='document-upload'),
#     path('documents/<int:pk>/download/', document.DocumentDownloadView.as_view(), name='document-download'),
    
#     # Territory Management URLs
#     path('territories/', territory.TerritoryListView.as_view(), name='territory-list'),
#     path('territories/<int:pk>/', territory.TerritoryDetailView.as_view(), name='territory-detail'),
#     path('territories/optimization/', territory.TerritoryOptimizationView.as_view(), name='territory-optimization'),
#     path('teams/', territory.TeamListView.as_view(), name='team-list'),
#     path('teams/<int:pk>/', territory.TeamDetailView.as_view(), name='team-detail'),
    
#     # Product Management URLs
#     path('products/', product.ProductListView.as_view(), name='product-list'),
#     path('products/<int:pk>/', product.ProductDetailView.as_view(), name='product-detail'),
#     path('product-categories/', product.ProductCategoryListView.as_view(), name='product-category-list'),
#     path('product-bundles/', product.ProductBundleListView.as_view(), name='product-bundle-list'),
#     path('product-bundles/<int:pk>/', product.ProductBundleDetailView.as_view(), name='product-bundle-detail'),
    
#     # Analytics & Reporting URLs
#     path('analytics/', analytics.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
#     path('reports/', analytics.ReportListView.as_view(), name='report-list'),
#     path('reports/<int:pk>/', analytics.ReportDetailView.as_view(), name='report-detail'),
#     path('reports/builder/', analytics.ReportBuilderView.as_view(), name='report-builder'),
#     path('dashboards/', analytics.DashboardListView.as_view(), name='dashboard-list'),
#     path('dashboards/<int:pk>/', analytics.DashboardDetailView.as_view(), name='dashboard-detail'),
#     path('forecasting/', analytics.ForecastingView.as_view(), name='forecasting'),
    
#     # Workflow & Automation URLs
#     path('workflows/', workflow.WorkflowRuleListView.as_view(), name='workflow-rule-list'),
#     path('workflows/<int:pk>/', workflow.WorkflowRuleDetailView.as_view(), name='workflow-rule-detail'),
#     path('workflows/create/', workflow.WorkflowRuleCreateView.as_view(), name='workflow-rule-create'),
#     path('workflows/<int:pk>/update/', workflow.WorkflowRuleUpdateView.as_view(), name='workflow-rule-update'),
#     path('workflows/executions/', workflow.WorkflowExecutionListView.as_view(), name='workflow-execution-list'),
#     path('integrations/', workflow.IntegrationListView.as_view(), name='integration-list'),
#     path('integrations/<int:pk>/', workflow.IntegrationDetailView.as_view(), name='integration-detail'),
#     path('custom-fields/', workflow.CustomFieldListView.as_view(), name='custom-field-list'),
    
#     # System Administration URLs
#     path('system/', system.SystemDashboardView.as_view(), name='system-dashboard'),
#     path('system/audit-trail/', system.AuditTrailListView.as_view(), name='audit-trail'),
#     path('system/export/', system.DataExportView.as_view(), name='data-export'),
#     path('system/import/', system.DataImportView.as_view(), name='data-import'),
#     path('system/configuration/', system.SystemConfigurationView.as_view(), name='system-configuration'),
#     path('system/maintenance/', system.SystemMaintenanceView.as_view(), name='system-maintenance'),
    
#     # API URLs
#     path('api/', include(router.urls)),
# ]