# backend/apps/finance/urls.py

"""
Finance Module URL Configuration
Complete API routing for all finance functionality
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    # Core
    FinanceSettingsViewSet, FiscalYearViewSet, FinancialPeriodViewSet,
    
    # Accounts & Chart
    AccountCategoryViewSet, AccountViewSet,
    
    # Currency & Tax
    CurrencyViewSet, ExchangeRateViewSet, TaxCodeViewSet, TaxGroupViewSet,
    
    # Journal Entries
    JournalEntryViewSet,
    
    # Invoices & Sales
    InvoiceViewSet,
    
    # Payments
    PaymentViewSet,
    
    # Vendors & Purchases
    VendorViewSet, BillViewSet,
    
    # Bank & Reconciliation
    BankAccountViewSet, BankStatementViewSet, BankReconciliationViewSet,
    
    # Reports & Dashboard
    FinancialReportsViewSet, FinanceDashboardViewSet,
)

app_name = 'finance'

# Create router and register viewsets
router = DefaultRouter()

# Core Configuration
router.register(r'settings', FinanceSettingsViewSet, basename='settings')
router.register(r'fiscal-years', FiscalYearViewSet, basename='fiscal-years')
router.register(r'financial-periods', FinancialPeriodViewSet, basename='financial-periods')

# Chart of Accounts
router.register(r'account-categories', AccountCategoryViewSet, basename='account-categories')
router.register(r'accounts', AccountViewSet, basename='accounts')

# Currency & Tax
router.register(r'currencies', CurrencyViewSet, basename='currencies')
router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchange-rates')
router.register(r'tax-codes', TaxCodeViewSet, basename='tax-codes')
router.register(r'tax-groups', TaxGroupViewSet, basename='tax-groups')

# Journal Entries
router.register(r'journal-entries', JournalEntryViewSet, basename='journal-entries')

# Invoices & Sales
router.register(r'invoices', InvoiceViewSet, basename='invoices')

# Payments
router.register(r'payments', PaymentViewSet, basename='payments')

# Vendors & Purchases
router.register(r'vendors', VendorViewSet, basename='vendors')
router.register(r'bills', BillViewSet, basename='bills')

# Bank & Reconciliation
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-accounts')
router.register(r'bank-statements', BankStatementViewSet, basename='bank-statements')
router.register(r'bank-reconciliations', BankReconciliationViewSet, basename='bank-reconciliations')

# Reports & Dashboard
router.register(r'reports', FinancialReportsViewSet, basename='reports')
router.register(r'dashboard', FinanceDashboardViewSet, basename='dashboard')

urlpatterns = [
    # API routes
    path('api/', include(router.urls)),
    
    # Additional custom endpoints
    path('api/quick-actions/', include([
        # Quick invoice creation
        path('create-invoice/', InvoiceViewSet.as_view({'post': 'create_invoice'}), name='quick-create-invoice'),
        
        # Quick payment entry
        path('create-payment/', PaymentViewSet.as_view({'post': 'create_payment'}), name='quick-create-payment'),
        
        # Quick journal entry
        path('create-journal-entry/', JournalEntryViewSet.as_view({'post': 'create_entry'}), name='quick-create-journal-entry'),
        
        # Financial summary
        path('summary/', FinanceDashboardViewSet.as_view({'get': 'overview'}), name='financial-summary'),
    ])),
    
    # Bulk operations
    path('api/bulk/', include([
        # Bulk invoice operations
        path('invoices/send/', InvoiceViewSet.as_view({'post': 'send_invoices'}), name='bulk-send-invoices'),
        path('invoices/approve/', InvoiceViewSet.as_view({'post': 'approve_invoices'}), name='bulk-approve-invoices'),
        
        # Bulk journal entry operations
        path('journal-entries/post/', JournalEntryViewSet.as_view({'post': 'post_entries'}), name='bulk-post-journal-entries'),
        
        # Bulk account creation
        path('accounts/create/', AccountViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-accounts'),
    ])),
    
    # Integration endpoints
    path('api/integrations/', include([
        # Bank feed sync
        path('bank-feeds/sync/', BankStatementViewSet.as_view({'post': 'sync_bank_feeds'}), name='sync-bank-feeds'),
        
        # Auto-matching
        path('auto-match/bank-transactions/', BankStatementViewSet.as_view({'post': 'auto_match_transactions'}), name='auto-match-bank-transactions'),
        
        # Inventory integration
        path('inventory/sync-costs/', include('apps.finance.integrations.inventory_urls')),
        
        # CRM integration
        path('crm/sync-customers/', include('apps.finance.integrations.crm_urls')),
        
        # E-commerce integration
        path('ecommerce/sync-orders/', include('apps.finance.integrations.ecommerce_urls')),
    ])),
    
    # Export endpoints
    path('api/exports/', include([
        # Financial statements exports
        path('balance-sheet/pdf/', FinancialReportsViewSet.as_view({'get': 'balance_sheet'}), {'format': 'pdf'}, name='export-balance-sheet-pdf'),
        path('income-statement/pdf/', FinancialReportsViewSet.as_view({'get': 'income_statement'}), {'format': 'pdf'}, name='export-income-statement-pdf'),
        path('cash-flow/pdf/', FinancialReportsViewSet.as_view({'get': 'cash_flow'}), {'format': 'pdf'}, name='export-cash-flow-pdf'),
        
        # Aging reports exports
        path('ar-aging/pdf/', FinancialReportsViewSet.as_view({'get': 'ar_aging'}), {'format': 'pdf'}, name='export-ar-aging-pdf'),
        path('ap-aging/pdf/', FinancialReportsViewSet.as_view({'get': 'ap_aging'}), {'format': 'pdf'}, name='export-ap-aging-pdf'),
        
        # Trial balance export
        path('trial-balance/pdf/', FinancialReportsViewSet.as_view({'get': 'trial_balance'}), {'format': 'pdf'}, name='export-trial-balance-pdf'),
        
        # Data exports
        path('chart-of-accounts/csv/', AccountViewSet.as_view({'get': 'export_csv'}), name='export-accounts-csv'),
        path('journal-entries/csv/', JournalEntryViewSet.as_view({'get': 'export_csv'}), name='export-journal-entries-csv'),
        path('invoices/csv/', InvoiceViewSet.as_view({'get': 'export_csv'}), name='export-invoices-csv'),
        path('payments/csv/', PaymentViewSet.as_view({'get': 'export_csv'}), name='export-payments-csv'),
    ])),
    
    # Workflow endpoints
    path('api/workflows/', include([
        # Invoice workflow
        path('invoices/<int:pk>/approve/', InvoiceViewSet.as_view({'post': 'approve'}), name='approve-invoice'),
        path('invoices/<int:pk>/send/', InvoiceViewSet.as_view({'post': 'send'}), name='send-invoice'),
        path('invoices/<int:pk>/void/', InvoiceViewSet.as_view({'post': 'void'}), name='void-invoice'),
        path('invoices/<int:pk>/send-reminder/', InvoiceViewSet.as_view({'post': 'send_reminder'}), name='send-invoice-reminder'),
        
        # Bill workflow
        path('bills/<int:pk>/approve/', BillViewSet.as_view({'post': 'approve'}), name='approve-bill'),
        
        # Journal entry workflow
        path('journal-entries/<int:pk>/post/', JournalEntryViewSet.as_view({'post': 'post_entry'}), name='post-journal-entry'),
        path('journal-entries/<int:pk>/reverse/', JournalEntryViewSet.as_view({'post': 'reverse_entry'}), name='reverse-journal-entry'),
        
        # Payment workflow
        path('payments/<int:pk>/apply-to-invoices/', PaymentViewSet.as_view({'post': 'apply_to_invoices'}), name='apply-payment-to-invoices'),
        path('payments/<int:pk>/apply-to-bills/', PaymentViewSet.as_view({'post': 'apply_to_bills'}), name='apply-payment-to-bills'),
        path('payments/<int:pk>/refund/', PaymentViewSet.as_view({'post': 'process_refund'}), name='process-payment-refund'),
        
        # Bank reconciliation workflow
        path('reconciliations/start/', BankReconciliationViewSet.as_view({'post': 'start_reconciliation'}), name='start-bank-reconciliation'),
        path('reconciliations/<int:pk>/complete/', BankReconciliationViewSet.as_view({'post': 'complete'}), name='complete-bank-reconciliation'),
        
        # Fiscal year workflow
        path('fiscal-years/<int:pk>/close/', FiscalYearViewSet.as_view({'post': 'close_year'}), name='close-fiscal-year'),
        path('financial-periods/<int:pk>/close/', FinancialPeriodViewSet.as_view({'post': 'close_period'}), name='close-financial-period'),
    ])),
    
    # Analytics endpoints
    path('api/analytics/', include([
        # Dashboard analytics
        path('kpis/', FinanceDashboardViewSet.as_view({'get': 'kpis'}), name='financial-kpis'),
        path('cash-flow-forecast/', FinanceDashboardViewSet.as_view({'get': 'cash_flow'}), name='cash-flow-forecast'),
        path('aging-summary/', FinanceDashboardViewSet.as_view({'get': 'aging_summary'}), name='aging-summary'),
        path('revenue-trend/', FinanceDashboardViewSet.as_view({'get': 'revenue_trend'}), name='revenue-trend'),
        path('expense-breakdown/', FinanceDashboardViewSet.as_view({'get': 'expense_breakdown'}), name='expense-breakdown'),
        path('alerts/', FinanceDashboardViewSet.as_view({'get': 'alerts'}), name='financial-alerts'),
        
        # Summary statistics
        path('invoices/summary/', InvoiceViewSet.as_view({'get': 'summary'}), name='invoices-summary'),
        path('payments/summary/', PaymentViewSet.as_view({'get': 'summary'}), name='payments-summary'),
        path('journal-entries/summary/', JournalEntryViewSet.as_view({'get': 'summary'}), name='journal-entries-summary'),
        
        # Performance metrics
        path('vendors/top-by-purchases/', VendorViewSet.as_view({'get': 'top_by_purchases'}), name='top-vendors-by-purchases'),
        path('customers/top-by-revenue/', InvoiceViewSet.as_view({'get': 'top_customers_by_revenue'}), name='top-customers-by-revenue'),
    ])),
    
    # Utility endpoints
    path('api/utilities/', include([
        # Account hierarchy
        path('accounts/hierarchy/', AccountViewSet.as_view({'get': 'hierarchy'}), name='accounts-hierarchy'),
        path('accounts/balance-sheet/', AccountViewSet.as_view({'get': 'balance_sheet_accounts'}), name='balance-sheet-accounts'),
        path('accounts/income-statement/', AccountViewSet.as_view({'get': 'income_statement_accounts'}), name='income-statement-accounts'),
        
        # Balance queries
        path('accounts/<int:pk>/balance/', AccountViewSet.as_view({'get': 'balance'}), name='account-balance'),
        
        # Quick access lists
        path('invoices/overdue/', InvoiceViewSet.as_view({'get': 'overdue'}), name='overdue-invoices'),
        path('bills/overdue/', BillViewSet.as_view({'get': 'overdue'}), name='overdue-bills'),
        path('bills/pending-approval/', BillViewSet.as_view({'get': 'pending_approval'}), name='bills-pending-approval'),
        path('payments/unallocated/', PaymentViewSet.as_view({'get': 'unallocated'}), name='unallocated-payments'),
        
        # Current data
        path('fiscal-years/current/', FiscalYearViewSet.as_view({'get': 'current'}), name='current-fiscal-year'),
        
        # Settings
        path('settings/reset/', FinanceSettingsViewSet.as_view({'post': 'reset_to_defaults'}), name='reset-finance-settings'),
    ])),
]


# backend/apps/finance/integrations/inventory_urls.py

"""
Finance-Inventory Integration URLs
"""

from django.urls import path
from .views import InventoryIntegrationViewSet

urlpatterns = [
    path('sync-product-costs/', InventoryIntegrationViewSet.as_view({'post': 'sync_product_costs'}), name='sync-product-costs'),
    path('update-inventory-valuation/', InventoryIntegrationViewSet.as_view({'post': 'update_inventory_valuation'}), name='update-inventory-valuation'),
    path('create-cogs-entries/', InventoryIntegrationViewSet.as_view({'post': 'create_cogs_entries'}), name='create-cogs-entries'),
    path('calculate-landed-costs/', InventoryIntegrationViewSet.as_view({'post': 'calculate_landed_costs'}), name='calculate-landed-costs'),
]


# backend/apps/finance/integrations/crm_urls.py

"""
Finance-CRM Integration URLs
"""

from django.urls import path
from .views import CRMIntegrationViewSet

urlpatterns = [
    path('sync-customer-profiles/', CRMIntegrationViewSet.as_view({'post': 'sync_customer_profiles'}), name='sync-customer-profiles'),
    path('update-credit-limits/', CRMIntegrationViewSet.as_view({'post': 'update_credit_limits'}), name='update-credit-limits'),
    path('generate-customer-statements/', CRMIntegrationViewSet.as_view({'post': 'generate_customer_statements'}), name='generate-customer-statements'),
    path('calculate-customer-lifetime-value/', CRMIntegrationViewSet.as_view({'post': 'calculate_customer_lifetime_value'}), name='calculate-customer-lifetime-value'),
]


# backend/apps/finance/integrations/ecommerce_urls.py

"""
Finance-E-commerce Integration URLs
"""

from django.urls import path
from .views import EcommerceIntegrationViewSet

urlpatterns = [
    path('sync-orders/', EcommerceIntegrationViewSet.as_view({'post': 'sync_orders'}), name='sync-ecommerce-orders'),
    path('create-invoices-from-orders/', EcommerceIntegrationViewSet.as_view({'post': 'create_invoices_from_orders'}), name='create-invoices-from-orders'),
    path('process-payments/', EcommerceIntegrationViewSet.as_view({'post': 'process_payments'}), name='process-ecommerce-payments'),
    path('calculate-sales-tax/', EcommerceIntegrationViewSet.as_view({'post': 'calculate_sales_tax'}), name='calculate-sales-tax'),
]


# backend/apps/finance/api_urls.py

"""
Finance API URL Configuration
Separate file for clean API routing
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import *

# API v1 Router
v1_router = DefaultRouter()

# Register all viewsets
v1_router.register(r'settings', FinanceSettingsViewSet, basename='settings')
v1_router.register(r'fiscal-years', FiscalYearViewSet, basename='fiscal-years')
v1_router.register(r'financial-periods', FinancialPeriodViewSet, basename='financial-periods')
v1_router.register(r'account-categories', AccountCategoryViewSet, basename='account-categories')
v1_router.register(r'accounts', AccountViewSet, basename='accounts')
v1_router.register(r'currencies', CurrencyViewSet, basename='currencies')
v1_router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchange-rates')
v1_router.register(r'tax-codes', TaxCodeViewSet, basename='tax-codes')
v1_router.register(r'tax-groups', TaxGroupViewSet, basename='tax-groups')
v1_router.register(r'journal-entries', JournalEntryViewSet, basename='journal-entries')
v1_router.register(r'invoices', InvoiceViewSet, basename='invoices')
v1_router.register(r'payments', PaymentViewSet, basename='payments')
v1_router.register(r'vendors', VendorViewSet, basename='vendors')
v1_router.register(r'bills', BillViewSet, basename='bills')
v1_router.register(r'bank-accounts', BankAccountViewSet, basename='bank-accounts')
v1_router.register(r'bank-statements', BankStatementViewSet, basename='bank-statements')
v1_router.register(r'bank-reconciliations', BankReconciliationViewSet, basename='bank-reconciliations')
v1_router.register(r'reports', FinancialReportsViewSet, basename='reports')
v1_router.register(r'dashboard', FinanceDashboardViewSet, basename='dashboard')

# URL patterns for API v1
api_v1_patterns = [
    path('', include(v1_router.urls)),
    
    # Custom API endpoints that don't fit into standard REST patterns
    path('quick-actions/', include([
        path('create-invoice/', InvoiceViewSet.as_view({'post': 'create_invoice'})),
        path('create-payment/', PaymentViewSet.as_view({'post': 'create_payment'})),
        path('create-journal-entry/', JournalEntryViewSet.as_view({'post': 'create_entry'})),
    ])),
    
    path('bulk-operations/', include([
        path('send-invoices/', InvoiceViewSet.as_view({'post': 'send_invoices'})),
        path('post-journal-entries/', JournalEntryViewSet.as_view({'post': 'post_entries'})),
        path('create-accounts/', AccountViewSet.as_view({'post': 'bulk_create'})),
    ])),
    
    path('workflows/', include([
        path('invoices/<int:pk>/approve/', InvoiceViewSet.as_view({'post': 'approve'})),
        path('invoices/<int:pk>/send/', InvoiceViewSet.as_view({'post': 'send'})),
        path('invoices/<int:pk>/void/', InvoiceViewSet.as_view({'post': 'void'})),
        path('bills/<int:pk>/approve/', BillViewSet.as_view({'post': 'approve'})),
        path('journal-entries/<int:pk>/post/', JournalEntryViewSet.as_view({'post': 'post_entry'})),
        path('journal-entries/<int:pk>/reverse/', JournalEntryViewSet.as_view({'post': 'reverse_entry'})),
        path('payments/<int:pk>/apply-to-invoices/', PaymentViewSet.as_view({'post': 'apply_to_invoices'})),
        path('payments/<int:pk>/apply-to-bills/', PaymentViewSet.as_view({'post': 'apply_to_bills'})),
        path('reconciliations/start/', BankReconciliationViewSet.as_view({'post': 'start_reconciliation'})),
        path('reconciliations/<int:pk>/complete/', BankReconciliationViewSet.as_view({'post': 'complete'})),
    ])),
    
    path('analytics/', include([
        path('kpis/', FinanceDashboardViewSet.as_view({'get': 'kpis'})),
        path('cash-flow/', FinanceDashboardViewSet.as_view({'get': 'cash_flow'})),
        path('aging-summary/', FinanceDashboardViewSet.as_view({'get': 'aging_summary'})),
        path('revenue-trend/', FinanceDashboardViewSet.as_view({'get': 'revenue_trend'})),
        path('expense-breakdown/', FinanceDashboardViewSet.as_view({'get': 'expense_breakdown'})),
    ])),
    
    path('exports/', include([
        path('balance-sheet/pdf/', FinancialReportsViewSet.as_view({
            'get': 'balance_sheet'
        }), {'format': 'pdf'}),
        path('income-statement/pdf/', FinancialReportsViewSet.as_view({
            'get': 'income_statement'
        }), {'format': 'pdf'}),
        path('cash-flow/pdf/', FinancialReportsViewSet.as_view({
            'get': 'cash_flow'
        }), {'format': 'pdf'}),
    ])),
]

# Main API URL patterns
urlpatterns = [
    path('v1/', include(api_v1_patterns)),
    # Future API versions can be added here
    # path('v2/', include(api_v2_patterns)),
]


# backend/apps/finance/admin_urls.py

"""
Finance Admin URL Configuration
For Django admin customizations
"""

from django.urls import path
from .admin_views import (
    FinanceAdminDashboardView, BulkJournalEntryCreateView,
    ChartOfAccountsImportView, FinancialReportsAdminView
)

urlpatterns = [
    path('dashboard/', FinanceAdminDashboardView.as_view(), name='finance-admin-dashboard'),
    path('bulk-journal-entries/', BulkJournalEntryCreateView.as_view(), name='bulk-journal-entries'),
    path('import-chart-of-accounts/', ChartOfAccountsImportView.as_view(), name='import-chart-of-accounts'),
    path('financial-reports/', FinancialReportsAdminView.as_view(), name='financial-reports-admin'),
]