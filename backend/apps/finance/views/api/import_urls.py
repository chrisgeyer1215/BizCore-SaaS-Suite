# backend/apps/finance/api/import_urls.py

"""
Data Import URLs
Import financial data from various sources
"""

from django.urls import path
from .views.imports import (
    ImportChartOfAccountsView, ImportBankStatementView,
    ImportInvoicesView, ImportVendorsView
)

urlpatterns = [
    path('chart-of-accounts/', ImportChartOfAccountsView.as_view(), name='import-chart-accounts'),
    path('bank-statement/', ImportBankStatementView.as_view(), name='import-bank-statement'),
    path('invoices/', ImportInvoicesView.as_view(), name='import-invoices'),
    path('vendors/', ImportVendorsView.as_view(), name='import-vendors'),
]