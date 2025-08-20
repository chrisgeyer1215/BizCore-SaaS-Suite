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


# backend/apps/finance/api/__init__.py

"""
Finance API Sub-modules
Additional API endpoints for specialized functionality
"""


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


# backend/apps/finance/api/quick_payment_urls.py

"""
Quick Payment Processing URLs
Simplified payment recording endpoints
"""

from django.urls import path
from .views.quick_payment import QuickPaymentView

urlpatterns = [
    path('record/', QuickPaymentView.as_view(), name='quick-payment-record'),
]


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


# backend/apps/finance/api/webhook_urls.py

"""
Webhook URLs
External system integration endpoints
"""

from django.urls import path
from .views.webhooks import (
    StripeWebhookView, PayPalWebhookView, BankFeedWebhookView
)

urlpatterns = [
    path('stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paypal/', PayPalWebhookView.as_view(), name='paypal-webhook'),
    path('bank-feed/', BankFeedWebhookView.as_view(), name='bank-feed-webhook'),
]


# backend/apps/finance/filters.py

"""
Finance Module Filters
DjangoFilter classes for API filtering
"""

import django_filters
from django.db.models import Q
from .models import (
    Account, JournalEntry, Invoice, Bill, Payment,
    Vendor, BankTransaction, BankReconciliation
)


class AccountFilter(django_filters.FilterSet):
    """Account filtering"""
    
    account_type = django_filters.CharFilter(field_name='account_type')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_bank_account = django_filters.BooleanFilter(field_name='is_bank_account')
    parent_account = django_filters.NumberFilter(field_name='parent_account')
    category = django_filters.NumberFilter(field_name='category')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Account
        fields = ['account_type', 'is_active', 'is_bank_account', 'parent_account', 'category']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(code__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class JournalEntryFilter(django_filters.FilterSet):
    """Journal entry filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    entry_type = django_filters.CharFilter(field_name='entry_type')
    entry_date_from = django_filters.DateFilter(field_name='entry_date', lookup_expr='gte')
    entry_date_to = django_filters.DateFilter(field_name='entry_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_debit', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_debit', lookup_expr='lte')
    created_by = django_filters.NumberFilter(field_name='created_by')
    
    class Meta:
        model = JournalEntry
        fields = ['status', 'entry_type', 'created_by']


class InvoiceFilter(django_filters.FilterSet):
    """Invoice filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    invoice_type = django_filters.CharFilter(field_name='invoice_type')
    customer = django_filters.NumberFilter(field_name='customer')
    invoice_date_from = django_filters.DateFilter(field_name='invoice_date', lookup_expr='gte')
    invoice_date_to = django_filters.DateFilter(field_name='invoice_date', lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = Invoice
        fields = ['status', 'invoice_type', 'customer']
    
    def filter_overdue(self, queryset, name, value):
        from datetime import date
        if value:
            return queryset.filter(
                due_date__lt=date.today(),
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                amount_due__gt=0
            )
        return queryset


class BillFilter(django_filters.FilterSet):
    """Bill filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    bill_type = django_filters.CharFilter(field_name='bill_type')
    vendor = django_filters.NumberFilter(field_name='vendor')
    bill_date_from = django_filters.DateFilter(field_name='bill_date', lookup_expr='gte')
    bill_date_to = django_filters.DateFilter(field_name='bill_date', lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = Bill
        fields = ['status', 'bill_type', 'vendor']
    
    def filter_overdue(self, queryset, name, value):
        from datetime import date
        if value:
            return queryset.filter(
                due_date__lt=date.today(),
                status__in=['OPEN', 'APPROVED', 'PARTIAL'],
                amount_due__gt=0
            )
        return queryset


class PaymentFilter(django_filters.FilterSet):
    """Payment filtering"""
    
    payment_type = django_filters.CharFilter(field_name='payment_type')
    payment_method = django_filters.CharFilter(field_name='payment_method')
    status = django_filters.CharFilter(field_name='status')
    customer = django_filters.NumberFilter(field_name='customer')
    vendor = django_filters.NumberFilter(field_name='vendor')
    payment_date_from = django_filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    payment_date_to = django_filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    bank_account = django_filters.NumberFilter(field_name='bank_account')
    
    class Meta:
        model = Payment
        fields = ['payment_type', 'payment_method', 'status', 'customer', 'vendor', 'bank_account']


class VendorFilter(django_filters.FilterSet):
    """Vendor filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    vendor_type = django_filters.CharFilter(field_name='vendor_type')
    is_inventory_supplier = django_filters.BooleanFilter(field_name='is_inventory_supplier')
    is_1099_vendor = django_filters.BooleanFilter(field_name='is_1099_vendor')
    payment_terms = django_filters.CharFilter(field_name='payment_terms')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Vendor
        fields = ['status', 'vendor_type', 'is_inventory_supplier', 'is_1099_vendor', 'payment_terms']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(company_name__icontains=value) |
            Q(vendor_number__icontains=value) |
            Q(email__icontains=value)
        )


class BankTransactionFilter(django_filters.FilterSet):
    """Bank transaction filtering"""
    
    bank_statement = django_filters.NumberFilter(field_name='bank_statement')
    transaction_type = django_filters.CharFilter(field_name='transaction_type')
    reconciliation_status = django_filters.CharFilter(field_name='reconciliation_status')
    transaction_date_from = django_filters.DateFilter(field_name='transaction_date', lookup_expr='gte')
    transaction_date_to = django_filters.DateFilter(field_name='transaction_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    is_duplicate = django_filters.BooleanFilter(field_name='is_duplicate')
    
    class Meta:
        model = BankTransaction
        fields = ['bank_statement', 'transaction_type', 'reconciliation_status', 'is_duplicate']


class BankReconciliationFilter(django_filters.FilterSet):
    """Bank reconciliation filtering"""
    
    bank_account = django_filters.NumberFilter(field_name='bank_account')
    status = django_filters.CharFilter(field_name='status')
    reconciliation_date_from = django_filters.DateFilter(field_name='reconciliation_date', lookup_expr='gte')
    reconciliation_date_to = django_filters.DateFilter(field_name='reconciliation_date', lookup_expr='lte')
    is_balanced = django_filters.BooleanFilter(field_name='is_balanced')
    started_by = django_filters.NumberFilter(field_name='started_by')
    completed_by = django_filters.NumberFilter(field_name='completed_by')
    
    class Meta:
        model = BankReconciliation
        fields = ['bank_account', 'status', 'is_balanced', 'started_by', 'completed_by']