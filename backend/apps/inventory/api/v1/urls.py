from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.documentation import include_docs_urls

from .views import (
    # Core views
    core, catalog, warehouse, stock, purchasing, transfers, 
    adjustments, reservations, alerts, reports
)

# Create router for ViewSets
router = DefaultRouter()

# Core endpoints
router.register(r'settings', core.InventorySettingsViewSet, basename='settings')
router.register(r'units', core.UnitOfMeasureViewSet, basename='units')
router.register(r'departments', core.DepartmentViewSet, basename='departments')
router.register(r'categories', core.CategoryViewSet, basename='categories')
router.register(r'brands', core.BrandViewSet, basename='brands')

# Supplier endpoints
router.register(r'suppliers', purchasing.SupplierViewSet, basename='suppliers')

# Warehouse endpoints  
router.register(r'warehouses', warehouse.WarehouseViewSet, basename='warehouses')
router.register(r'locations', warehouse.StockLocationViewSet, basename='locations')

# Product catalog endpoints
router.register(r'products', catalog.ProductViewSet, basename='products')
router.register(r'product-variations', catalog.ProductVariationViewSet, basename='product-variations')

# Stock endpoints
router.register(r'stock-items', stock.StockItemViewSet, basename='stock-items')
router.register(r'stock-movements', stock.StockMovementViewSet, basename='stock-movements')
router.register(r'batches', stock.BatchViewSet, basename='batches')

# Purchasing endpoints
router.register(r'purchase-orders', purchasing.PurchaseOrderViewSet, basename='purchase-orders')
router.register(r'stock-receipts', purchasing.StockReceiptViewSet, basename='stock-receipts')

# Transfer endpoints
router.register(r'transfers', transfers.StockTransferViewSet, basename='transfers')

# Adjustment endpoints
router.register(r'adjustments', adjustments.StockAdjustmentViewSet, basename='adjustments')
router.register(r'cycle-counts', adjustments.CycleCountViewSet, basename='cycle-counts')

# Reservation endpoints
router.register(r'reservations', reservations.StockReservationViewSet, basename='reservations')

# Alert endpoints
router.register(r'alerts', alerts.InventoryAlertViewSet, basename='alerts')
router.register(r'alert-rules', alerts.AlertRuleViewSet, basename='alert-rules')

# Report endpoints
router.register(r'reports', reports.InventoryReportViewSet, basename='reports')
router.register(r'report-templates', reports.ReportTemplateViewSet, basename='report-templates')

urlpatterns = [
    # API root and router URLs
    path('', include(router.urls)),
    
    # Custom endpoints that don't fit the ViewSet pattern
    path('dashboard/', include([
        path('summary/', core.DashboardSummaryView.as_view(), name='dashboard-summary'),
        path('kpis/', core.InventoryKPIsView.as_view(), name='inventory-kpis'),
        path('charts/', core.DashboardChartsView.as_view(), name='dashboard-charts'),
    ])),
    
    path('analytics/', include([
        path('abc-analysis/', stock.ABCAnalysisView.as_view(), name='abc-analysis'),
        path('stock-aging/', stock.StockAgingView.as_view(), name='stock-aging'),
        path('movement-velocity/', stock.MovementVelocityView.as_view(), name='movement-velocity'),
        path('supplier-performance/', purchasing.SupplierPerformanceView.as_view(), name='supplier-performance'),
    ])),
    
    path('operations/', include([
        path('reorder-suggestions/', purchasing.ReorderSuggestionsView.as_view(), name='reorder-suggestions'),
        path('stock-availability/', stock.StockAvailabilityView.as_view(), name='stock-availability'),
        path('bulk-operations/', core.BulkOperationsView.as_view(), name='bulk-operations'),
    ])),
    
    path('integrations/', include([
        path('ecommerce/sync/', core.EcommerceSyncView.as_view(), name='ecommerce-sync'),
        path('finance/sync/', core.FinanceSyncView.as_view(), name='finance-sync'),
        path('webhooks/', core.WebhookEndpointsView.as_view(), name='webhooks'),
    ])),
    
    # API documentation
    path('docs/', include_docs_urls(
        title='Inventory Management API',
        description='Comprehensive inventory management system API'
    )),
]




# Confuse urls 


# apps/inventory/api/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.documentation import include_docs_urls
from rest_framework.schemas import get_schema_view
from rest_framework import permissions

# Import all viewsets (already imported in main urls.py)

# Custom API endpoints that don't fit into ViewSets
from apps.inventory.api.v1.views import (
    custom_views, dashboard_views, integration_views
)

app_name = 'inventory_api_v1'

# Additional custom endpoints
custom_urlpatterns = [
    # Dashboard endpoints
    path('dashboard/overview/', dashboard_views.DashboardOverviewView.as_view(), 
         name='dashboard-overview'),
    path('dashboard/kpis/', dashboard_views.KPIView.as_view(), 
         name='dashboard-kpis'),
    path('dashboard/charts/', dashboard_views.ChartDataView.as_view(), 
         name='dashboard-charts'),
    
    # Integration endpoints
    path('integrations/finance/sync/', integration_views.FinanceSyncView.as_view(), 
         name='finance-sync'),
    path('integrations/ecommerce/sync/', integration_views.EcommerceSyncView.as_view(), 
         name='ecommerce-sync'),
    path('integrations/crm/sync/', integration_views.CRMSyncView.as_view(), 
         name='crm-sync'),
    
    # Bulk operations
    path('bulk/import/', custom_views.BulkImportView.as_view(), 
         name='bulk-import'),
    path('bulk/export/', custom_views.BulkExportView.as_view(), 
         name='bulk-export'),
    path('bulk/operations/', custom_views.BulkOperationsView.as_view(), 
         name='bulk-operations'),
    
    # Analytics endpoints
    path('analytics/trends/', custom_views.TrendsAnalysisView.as_view(), 
         name='analytics-trends'),
    path('analytics/forecasting/', custom_views.ForecastingView.as_view(), 
         name='analytics-forecasting'),
    path('analytics/optimization/', custom_views.OptimizationView.as_view(), 
         name='analytics-optimization'),
    
    # System endpoints
    path('system/backup/', custom_views.BackupView.as_view(), 
         name='system-backup'),
    path('system/maintenance/', custom_views.MaintenanceView.as_view(), 
         name='system-maintenance'),
    path('system/audit/', custom_views.AuditView.as_view(), 
         name='system-audit'),
]

# Schema and documentation
schema_view = get_schema_view(
    title="Inventory Management API",
    description="Comprehensive API for multi-tenant inventory management",
    version="v1",
    permission_classes=[permissions.IsAuthenticated],
)

urlpatterns = [
    # Main router URLs (from main urls.py)
    path('', include('apps.inventory.urls')),
    
    # Custom endpoints
    path('', include(custom_urlpatterns)),
    
    # API Documentation
    path('schema/', schema_view, name='api-schema'),
    path('docs/', include_docs_urls(title='Inventory API Documentation')),
    
    # OpenAPI/Swagger endpoints
    path('swagger/', custom_views.SwaggerView.as_view(), name='swagger-ui'),
    path('redoc/', custom_views.ReDocView.as_view(), name='redoc-ui'),
]