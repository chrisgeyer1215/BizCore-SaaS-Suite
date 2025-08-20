# apps/inventory/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.urlpatterns import format_suffix_patterns

# Import all viewsets
from apps.inventory.api.v1.views.core import (
    InventorySettingsViewSet, UnitOfMeasureViewSet, BrandViewSet
)
from apps.inventory.api.v1.views.catalog import (
    CategoryViewSet, ProductViewSet, ProductVariationViewSet
)
from apps.inventory.api.v1.views.warehouse import (
    WarehouseViewSet, StockLocationViewSet
)
from apps.inventory.api.v1.views.stock import (
    StockItemViewSet, StockMovementViewSet, BatchViewSet
)
from apps.inventory.api.v1.views.purchasing import (
    PurchaseOrderViewSet, StockReceiptViewSet
)
from apps.inventory.api.v1.views.transfers import (
    StockTransferViewSet
)
from apps.inventory.api.v1.views.adjustments import (
    StockAdjustmentViewSet, CycleCountViewSet
)
from apps.inventory.api.v1.views.reservations import (
    StockReservationViewSet
)
from apps.inventory.api.v1.views.alerts import (
    InventoryAlertViewSet
)
from apps.inventory.api.v1.views.reports import (
    InventoryReportViewSet
)

app_name = 'inventory'

# API v1 Router
v1_router = DefaultRouter()

# Core Management
v1_router.register(r'settings', InventorySettingsViewSet, basename='settings')
v1_router.register(r'units', UnitOfMeasureViewSet, basename='units')
v1_router.register(r'brands', BrandViewSet, basename='brands')

# Catalog Management
v1_router.register(r'categories', CategoryViewSet, basename='categories')
v1_router.register(r'products', ProductViewSet, basename='products')
v1_router.register(r'variations', ProductVariationViewSet, basename='variations')

# Warehouse Management
v1_router.register(r'warehouses', WarehouseViewSet, basename='warehouses')
v1_router.register(r'locations', StockLocationViewSet, basename='locations')

# Stock Management
v1_router.register(r'stock-items', StockItemViewSet, basename='stock-items')
v1_router.register(r'movements', StockMovementViewSet, basename='movements')
v1_router.register(r'batches', BatchViewSet, basename='batches')

# Purchasing
v1_router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-orders')
v1_router.register(r'receipts', StockReceiptViewSet, basename='receipts')

# Transfers
v1_router.register(r'transfers', StockTransferViewSet, basename='transfers')

# Adjustments
v1_router.register(r'adjustments', StockAdjustmentViewSet, basename='adjustments')
v1_router.register(r'cycle-counts', CycleCountViewSet, basename='cycle-counts')

# Reservations
v1_router.register(r'reservations', StockReservationViewSet, basename='reservations')

# Alerts
v1_router.register(r'alerts', InventoryAlertViewSet, basename='alerts')

# Reports
v1_router.register(r'reports', InventoryReportViewSet, basename='reports')

# URL Patterns
urlpatterns = [
    # API v1
    path('api/v1/', include(v1_router.urls)),
    
    # Health Check
    path('health/', include('apps.inventory.api.v1.health_urls')),
    
    # Documentation
    path('docs/', include('apps.inventory.api.v1.docs_urls')),
    
    # Webhooks
    path('webhooks/', include('apps.inventory.api.v1.webhook_urls')),
]

# Add format suffix patterns for content negotiation
urlpatterns = format_suffix_patterns(urlpatterns)