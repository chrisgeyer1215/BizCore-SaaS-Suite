"""
Finance Module Views - Entry Point
All financial view modules organized by domain
"""

# Core Views
from .dashboard import *
from .accounts import *
from .journal_entries import *
from .invoices import *

# Transaction Views
from .bills import *
from .payments import *
from .vendors import *

# Reporting Views
from .reports import *

# Configuration Views
from .settings import *

# Reconciliation Views
from .bank_reconciliation import *

# Customer Views
from .customers import *

# All views for convenience
__all__ = [
    # Dashboard
    'dashboard',
    
    # Core Management
    'accounts',
    'journal_entries',
    'invoices',
    
    # Transaction Management
    'bills',
    'payments',
    'vendors',
    
    # Reporting
    'reports',
    
    # Configuration
    'settings',
    
    # Reconciliation
    'bank_reconciliation',
    
    # Customer Management
    'customers',
]


