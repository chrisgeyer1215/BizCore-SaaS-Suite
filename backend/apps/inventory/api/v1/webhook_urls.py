# apps/inventory/api/v1/webhook_urls.py

from django.urls import path
from apps.inventory.api.v1.views.webhooks import (
    InventoryWebhookView, StockUpdateWebhookView, 
    AlertWebhookView, ReportWebhookView
)

urlpatterns = [
    path('inventory/', InventoryWebhookView.as_view(), name='inventory-webhook'),
    path('stock-updates/', StockUpdateWebhookView.as_view(), name='stock-webhook'),
    path('alerts/', AlertWebhookView.as_view(), name='alert-webhook'),
    path('reports/', ReportWebhookView.as_view(), name='report-webhook'),
]