# apps/inventory/tests/factories/catalog.py
import factory
from factory.django import DjangoModelFactory
from decimal import Decimal

from ...models.catalog import Product, ProductVariation
from .core import TenantFactory, CategoryFactory, BrandFactory, SupplierFactory, UnitOfMeasureFactory

class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product
    
    tenant = factory.SubFactory(TenantFactory)
    name = factory.Faker('catch_phrase')
    sku = factory.Sequence(lambda n: f"PROD{n:06d}")
    barcode = factory.Sequence(lambda n: f"{1234567890000 + n}")
    description = factory.Faker('text', max_nb_chars=500)
    category = factory.SubFactory(CategoryFactory)
    brand = factory.SubFactory(BrandFactory)
    supplier = factory.SubFactory(SupplierFactory)
    uom = factory.SubFactory(UnitOfMeasureFactory)
    
    cost_price = factory.LazyFunction(lambda: Decimal(f"{fake.pyfloat(min_value=10, max_value=1000, right_digits=2):.2f}"))
    selling_price = factory.LazyAttribute(lambda obj: obj.cost_price * Decimal('1.5'))
    
    weight = factory.Faker('pyfloat', min_value=0.1, max_value=50.0, right_digits=3)
    reorder_level = Decimal('10.0000')
    max_stock_level = Decimal('100.0000')
    lead_time_days = factory.Faker('random_int', min=1, max=21)
    
    abc_classification = factory.Iterator(['A', 'B', 'C'])
    is_active = True
    is_serialized = False
    track_batches = False

class ProductVariationFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariation
    
    tenant = factory.SubFactory(TenantFactory)
    product = factory.SubFactory(ProductFactory)
    name = factory.Sequence(lambda n: f"Variation {n}")
    sku = factory.LazyAttribute(lambda obj: f"{obj.product.sku}-V{fake.random_int(1, 999):03d}")
    additional_cost = Decimal('0.00')
    weight = factory.Faker('pyfloat', min_value=0.1, max_value=5.0, right_digits=3)
    sort_order = factory.Sequence(lambda n: n)
    is_active = True