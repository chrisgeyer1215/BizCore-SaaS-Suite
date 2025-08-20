"""
Inventory module URL configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InventorySettingsViewSet, UnitOfMeasureViewSet, DepartmentViewSet,
    CategoryViewSet, SubCategoryViewSet, BrandViewSet, SupplierViewSet,
    SupplierContactViewSet, WarehouseViewSet, StockLocationViewSet,
    ProductAttributeViewSet, AttributeValueViewSet, ProductViewSet,
    ProductVariationViewSet, BatchViewSet, StockItemViewSet, StockMovementViewSet,
    PurchaseOrderViewSet, PurchaseOrderItemViewSet, InventoryDashboardViewSet,
    InventoryAlertViewSet
)

# Create router and register viewsets
router = DefaultRouter()

# Core settings
router.register(r'settings', InventorySettingsViewSet, basename='inventory-settings')
router.register(r'units', UnitOfMeasureViewSet, basename='units')

# Categorization
router.register(r'departments', DepartmentViewSet, basename='departments')
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'subcategories', SubCategoryViewSet, basename='subcategories')

# Brands & Suppliers
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'suppliers', SupplierViewSet, basename='suppliers')
router.register(r'supplier-contacts', SupplierContactViewSet, basename='supplier-contacts')

# Warehouses & Locations
router.register(r'warehouses', WarehouseViewSet, basename='warehouses')
router.register(r'locations', StockLocationViewSet, basename='locations')

# Product Attributes
router.register(r'attributes', ProductAttributeViewSet, basename='attributes')
router.register(r'attribute-values', AttributeValueViewSet, basename='attribute-values')

# Products
router.register(r'products', ProductViewSet, basename='products')
router.register(r'product-variations', ProductVariationViewSet, basename='product-variations')
router.register(r'batches', BatchViewSet, basename='batches')

# Stock Management
router.register(r'stock-items', StockItemViewSet, basename='stock-items')
router.register(r'stock-movements', StockMovementViewSet, basename='stock-movements')

# Purchase Orders
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-orders')
router.register(r'purchase-order-items', PurchaseOrderItemViewSet, basename='purchase-order-items')

# Analytics & Alerts
router.register(r'dashboard', InventoryDashboardViewSet, basename='dashboard')
router.register(r'alerts', InventoryAlertViewSet, basename='alerts')

app_name = 'inventory'
urlpatterns = [
    path('api/v1/inventory/', include(router.urls)),
]








# # apps/inventory/urls.py - Complete Inventory URL Configuration

# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from . import views

# # Create router for ViewSets
# router = DefaultRouter()

# # Settings and Configuration
# router.register(r'settings', views.InventorySettingsViewSet, basename='inventory-settings')

# # Category Management
# router.register(r'departments', views.DepartmentViewSet, basename='departments')
# router.register(r'categories', views.CategoryViewSet, basename='categories')
# router.register(r'subcategories', views.SubCategoryViewSet, basename='subcategories')
# router.register(r'brands', views.BrandViewSet, basename='brands')

# # Supplier and Warehouse Management
# router.register(r'suppliers', views.SupplierViewSet, basename='suppliers')
# router.register(r'warehouses', views.WarehouseViewSet, basename='warehouses')

# # Product Attributes
# router.register(r'product-attributes', views.ProductAttributeViewSet, basename='product-attributes')
# router.register(r'attribute-values', views.AttributeValueViewSet, basename='attribute-values')

# # Product Management
# router.register(r'products', views.ProductViewSet, basename='products')
# router.register(r'product-variations', views.ProductVariationViewSet, basename='product-variations')

# # Stock Management
# router.register(r'stock-items', views.StockItemViewSet, basename='stock-items')
# router.register(r'stock-movements', views.StockMovementViewSet, basename='stock-movements')

# # Purchase Orders
# router.register(r'purchase-orders', views.PurchaseOrderViewSet, basename='purchase-orders')

# # Transfers and Adjustments
# router.register(r'stock-transfers', views.StockTransferViewSet, basename='stock-transfers')
# router.register(r'stock-adjustments', views.StockAdjustmentViewSet, basename='stock-adjustments')

# app_name = 'inventory'

# urlpatterns = [
#     # ViewSet routes
#     path('', include(router.urls)),
    
#     # Dashboard and Summary Views
#     path('dashboard/', views.InventoryDashboardView.as_view(), name='dashboard'),
#     path('alerts/', views.StockAlertsView.as_view(), name='stock-alerts'),
    
#     # Bulk Operations
#     path('bulk/stock-update/', views.BulkStockUpdateView.as_view(), name='bulk-stock-update'),
#     path('bulk/price-update/', views.BulkPriceUpdateView.as_view(), name='bulk-price-update'),
#     path('bulk/transfer/', views.BulkTransferView.as_view(), name='bulk-transfer'),
    
#     # Reports
#     path('reports/', views.InventoryReportsView.as_view(), name='reports'),
    
#     # Additional API endpoints that might be needed
#     path('search/products/', views.ProductSearchView.as_view(), name='product-search'),
#     path('search/stock-items/', views.StockItemSearchView.as_view(), name='stock-item-search'),
    
#     # Import/Export endpoints
#     path('import/products/', views.ProductImportView.as_view(), name='product-import'),
#     path('export/products/', views.ProductExportView.as_view(), name='product-export'),
#     path('import/stock/', views.StockImportView.as_view(), name='stock-import'),
#     path('export/stock/', views.StockExportView.as_view(), name='stock-export'),
    
#     # Barcode operations
#     path('barcode/generate/', views.BarcodeGenerateView.as_view(), name='barcode-generate'),
#     path('barcode/scan/', views.BarcodeScanView.as_view(), name='barcode-scan'),
    
#     # Quick operations
#     path('quick/stock-in/', views.QuickStockInView.as_view(), name='quick-stock-in'),
#     path('quick/stock-out/', views.QuickStockOutView.as_view(), name='quick-stock-out'),
#     path('quick/transfer/', views.QuickTransferView.as_view(), name='quick-transfer'),
    
#     # Analytics endpoints
#     path('analytics/stock-trend/', views.StockTrendAnalyticsView.as_view(), name='stock-trend'),
#     path('analytics/movement-pattern/', views.MovementPatternAnalyticsView.as_view(), name='movement-pattern'),
#     path('analytics/supplier-performance/', views.SupplierPerformanceView.as_view(), name='supplier-performance'),
#     path('analytics/warehouse-utilization/', views.WarehouseUtilizationView.as_view(), name='warehouse-utilization'),
# ]