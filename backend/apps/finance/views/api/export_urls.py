# backend/apps/finance/api/export_urls.py

"""
Data Export URLs
Export financial data in various formats
"""

from django.urls import path
from .views.exports import (
    ExportTrialBalanceView, ExportInvoicesView,
    ExportPaymentsView, ExportJournalEntriesView
)

urlpatterns = [
    path('trial-balance/', ExportTrialBalanceView.as_view(), name='export-trial-balance'),
    path('invoices/', ExportInvoicesView.as_view(), name='export-invoices'),
    path('payments/', ExportPaymentsView.as_view(), name='export-payments'),
    path('journal-entries/', ExportJournalEntriesView.as_view(), name='export-journal-entries'),
]