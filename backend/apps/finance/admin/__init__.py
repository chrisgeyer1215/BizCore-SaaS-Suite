# backend/apps/finance/admin/__init__.py

"""
Finance Module Admin Registration
Django admin interface configuration for all finance models
"""

from django.contrib import admin
from .core import *
from .accounts import *
from .transactions import *
from .reconciliation import *
from .reports import *

# Register all admin classes
__all__ = [
    'FinanceSettingsAdmin',
    'FiscalYearAdmin',
    'CurrencyAdmin',
    'ExchangeRateAdmin',
    'AccountCategoryAdmin',
    'AccountAdmin',
    'TaxCodeAdmin',
    'JournalEntryAdmin',
    'BankAccountAdmin',
    'BankReconciliationAdmin',
    'VendorAdmin',
    'InvoiceAdmin',
    'BillAdmin',
    'PaymentAdmin',
]