# backend/apps/finance/api/bulk_urls.py

"""
Bulk Operations URLs
Mass operations for finance data
"""

from django.urls import path
from .views.bulk import (
    BulkInvoiceView, BulkPaymentView, BulkJournalEntryView
)

urlpatterns = [
    path('invoices/', BulkInvoiceView.as_view(), name='bulk-invoices'),
    path('payments/', BulkPaymentView.as_view(), name='bulk-payments'),
    path('journal-entries/', BulkJournalEntryView.as_view(), name='bulk-journal-entries'),
]