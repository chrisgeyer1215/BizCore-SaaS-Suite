# apps/inventory/tests/factories/core.py
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from decimal import Decimal
from django.contrib.auth.models import User

from apps.core.models import Tenant
from ...models.core import *

fake = Faker()

class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant
    
    name = factory.Sequence(lambda n: f"Test Tenant {n}")
    subdomain = factory.Sequence(lambda n: f"tenant{n}")
    is_active = True

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False
    
    tenant = factory.SubFactory(TenantFactory)

class UnitOfMeasureFactory(DjangoModelFactory):
    class Meta:
        model = UnitOfMeasure
    
    tenant = factory.SubFactory(TenantFactory)
    name = factory.Iterator(['Each', 'Kilogram', 'Liter', 'Meter', 'Pack'])
    abbreviation = factory.Iterator(['EA', 'KG', 'L', 'M', 'PACK'])
    category = factory.Iterator(['COUNT', 'WEIGHT', 'VOLUME', 'LENGTH', 'COUNT'])
    conversion_factor = Decimal('1.0000')
    is_active = True

class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    
    tenant = factory.SubFactory(TenantFactory)
    name = factory.Faker('word')
    description = factory.Faker('sentence')
    sort_order = factory.Sequence(lambda n: n)
    is_active = True

class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand
    
    tenant = factory.SubFactory(TenantFactory)
    name = factory.Faker('company')
    description = factory.Faker('sentence')
    website = factory.Faker('url')
    is_active = True

class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = Supplier
    
    tenant = factory.SubFactory(TenantFactory)
    name = factory.Faker('company')
    supplier_code = factory.Sequence(lambda n: f"SUP{n:03d}")
    contact_person = factory.Faker('name')
    email = factory.Faker('email')
    phone = factory.Faker('phone_number')
    address = factory.Faker('address')
    city = factory.Faker('city')
    country = 'US'
    payment_terms = 'NET30'
    lead_time_days = factory.Faker('random_int', min=1, max=30)
    is_active = True