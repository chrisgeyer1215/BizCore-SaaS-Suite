# apps/inventory/tests/factories/stock.py
import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from django.utils import timezone

from ...models.stock import StockItem, StockMovement, Batch
from .catalog import ProductFactory
from .warehouse import WarehouseFactory, StockLocationFactory
from .core import UserFactory

class StockItemFactory(DjangoModelFactory):
    class Meta:
        model = StockItem
    
    tenant = factory.SubFactory(TenantFactory)
    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    location = factory.SubFactory(StockLocationFactory)
    
    quantity_on_hand = factory.LazyFunction(
        lambda: Decimal(f"{fake.pyfloat(min_value=0, max_value=1000, right_digits=4):.4f}")
    )
    quantity_reserved = Decimal('0.0000')
    unit_cost = factory.LazyFunction(
        lambda: Decimal(f"{fake.pyfloat(min_value=10, max_value=500, right_digits=2):.2f}")
    )
    average_cost = factory.LazyAttribute(lambda obj: obj.unit_cost)
    valuation_method = 'FIFO'
    last_movement_date = factory.LazyFunction(lambda: timezone.now().date())
    is_active = True

class StockMovementFactory(DjangoModelFactory):
    class Meta:
        model = StockMovement
    
    tenant = factory.SubFactory(TenantFactory)
    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    location = factory.SubFactory(StockLocationFactory)
    
    movement_type = factory.Iterator([
        'RECEIPT', 'SALE', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT',
        'TRANSFER_IN', 'TRANSFER_OUT', 'CYCLE_COUNT'
    ])
    quantity = factory.LazyFunction(
        lambda: Decimal(f"{fake.pyfloat(min_value=1, max_value=100, right_digits=4):.4f}")
    )
    unit_cost = factory.LazyFunction(
        lambda: Decimal(f"{fake.pyfloat(min_value=10, max_value=500, right_digits=2):.2f}")
    )
    reference = factory.Sequence(lambda n: f"REF{n:06d}")
    notes = factory.Faker('sentence')
    user = factory.SubFactory(UserFactory)

class BatchFactory(DjangoModelFactory):
    class Meta:
        model = Batch
    
    tenant = factory.SubFactory(TenantFactory)
    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    
    batch_number = factory.Sequence(lambda n: f"BATCH{n:06d}")
    quantity = factory.LazyFunction(
        lambda: Decimal(f"{fake.pyfloat(min_value=10, max_value=1000, right_digits=4):.4f}")
    )
    manufacturing_date = factory.Faker('date_this_year')
    expiry_date = factory.LazyAttribute(
        lambda obj: obj.manufacturing_date + timedelta(days=365)
    )
    status = 'AVAILABLE'
    is_active = True