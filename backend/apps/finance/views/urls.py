# backend/apps/finance/urls.py

"""
Finance Module URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FinanceDashboardViewSet,
    AccountCategoryViewSet,
    AccountViewSet,
    JournalEntryViewSet,
    BankAccountViewSet,
    BankReconciliationViewSet,
    InvoiceViewSet,
    BillViewSet,
    PaymentViewSet,
    VendorViewSet,
    CustomerFinancialViewSet,
    FinancialReportsViewSet,
    FinanceSettingsViewSet
)

app_name = 'finance'

# Create router and register viewsets
router = DefaultRouter()

# Dashboard
router.register(r'dashboard', FinanceDashboardViewSet, basename='dashboard')

# Settings
router.register(r'settings', FinanceSettingsViewSet, basename='settings')

# Chart of Accounts
router.register(r'account-categories', AccountCategoryViewSet, basename='account-categories')
router.register(r'accounts', AccountViewSet, basename='accounts')

# Journal Entries
router.register(r'journal-entries', JournalEntryViewSet, basename='journal-entries')

# Banking
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-accounts')
router.register(r'bank-reconciliations', BankReconciliationViewSet, basename='bank-reconciliations')

# Sales & Receivables
router.register(r'invoices', InvoiceViewSet, basename='invoices')

# Purchases & Payables
router.register(r'vendors', VendorViewSet, basename='vendors')
router.register(r'bills', BillViewSet, basename='bills')

# Payments
router.register(r'payments', PaymentViewSet, basename='payments')

# Customer Financial Data
router.register(r'customer-financials', CustomerFinancialViewSet, basename='customer-financials')

# Reports
router.register(r'reports', FinancialReportsViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional custom endpoints
    path('api/v1/', include([
        # Quick access endpoints
        path('quick-invoice/', include('apps.finance.api.quick_invoice_urls')),
        path('quick-payment/', include('apps.finance.api.quick_payment_urls')),
        
        # Bulk operations
        path('bulk/', include('apps.finance.api.bulk_urls')),
        
        # Import/Export
        path('import/', include('apps.finance.api.import_urls')),
        path('export/', include('apps.finance.api.export_urls')),
        
        # Webhooks
        path('webhooks/', include('apps.finance.api.webhook_urls')),
    ])),
]