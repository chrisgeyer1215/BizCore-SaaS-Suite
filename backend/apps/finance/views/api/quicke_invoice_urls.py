# backend/apps/finance/api/quick_invoice_urls.py

"""
Quick Invoice Creation URLs
Simplified invoice creation endpoints
"""

from django.urls import path
from .views.quick_invoice import QuickInvoiceView

urlpatterns = [
    path('create/', QuickInvoiceView.as_view(), name='quick-invoice-create'),
]