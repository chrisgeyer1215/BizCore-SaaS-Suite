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