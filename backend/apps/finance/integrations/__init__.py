# backend/apps/finance/integrations/__init__.py

"""
Finance Module Integrations
Services for integrating finance with other modules
"""

from .inventory_integration import InventoryIntegrationService
from .crm_integration import CRMIntegrationService
from .ecommerce_integration import EcommerceIntegrationService

__all__ = [
    'InventoryIntegrationService',
    'CRMIntegrationService', 
    'EcommerceIntegrationService',
]