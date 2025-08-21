# apps/inventory/tests/factories/__init__.py
from .core import *
from .catalog import *
from .warehouse import *
from .stock import *
from .purchasing import *
from .ml import *

__all__ = [
    # Core factories
    'TenantFactory', 'UserFactory', 'UnitOfMeasureFactory',
    'CategoryFactory', 'BrandFactory', 'SupplierFactory',
    
    # Catalog factories
    'ProductFactory', 'ProductVariationFactory',
    
    # Warehouse factories  
    'WarehouseFactory', 'StockLocationFactory',
    
    # Stock factories
    'StockItemFactory', 'StockMovementFactory', 'BatchFactory',
    
    # Purchasing factories
    'PurchaseOrderFactory', 'PurchaseOrderItemFactory',
    
    # ML factories
    'MLModelFactory', 'DemandDataFactory'
]