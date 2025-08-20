# backend/apps/finance/signals/__init__.py

"""
Finance Module Signals
Event-driven automation and integration
"""

from .accounting import *
from .inventory import *
from .crm_integration import *

__all__ = [
    'journal_entry_posted',
    'invoice_created',
    'payment_recorded',
    'inventory_cost_updated',
    'customer_payment_received',
]