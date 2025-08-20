# backend/apps/finance/__init__.py

"""
Finance Module for SaaS-AICE
Enterprise-ready accounting and financial management
"""

default_app_config = 'apps.finance.apps.FinanceConfig'

# Version information
__version__ = '1.0.0'
__author__ = 'SaaS-AICE Development Team'

# Module metadata
MODULE_INFO = {
    'name': 'Finance & Accounting',
    'version': __version__,
    'description': 'Comprehensive financial management with QuickBooks-like functionality',
    'features': [
        'Multi-tenant Chart of Accounts',
        'Journal Entries & General Ledger',
        'Accounts Receivable & Invoicing',
        'Accounts Payable & Bills',
        'Bank Reconciliation',
        'Multi-currency Support',
        'Financial Reporting',
        'COGS & Inventory Integration',
        'CRM Financial Profiles',
        'E-commerce Integration',
        'Tax Management',
        'Budget & Forecasting',
        'Dashboard & Analytics'
    ],
    'integrations': [
        'CRM Module',
        'Inventory Module', 
        'E-commerce Module',
        'Core Tenant System'
    ]
}