from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import random
from faker import Faker
from apps.ecommerce.models import (
    EcommerceSettings, Collection, EcommerceProduct, 
    ProductVariant, Cart, CartItem, Order, OrderItem,
    Coupon, ReviewRating, ShippingZone, ShippingMethod
)
from apps.inventory.models import Product, Category, Warehouse
from apps.crm.models import Customer
from apps.core.models import Tenant

fake = Faker()

class Command(BaseCommand):
    help = 'Generate sample e-commerce data for testing'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-id', type=int, required=True)
        parser.add_argument('--products', type=int, default=50)
        parser.add_argument('--customers', type=int, default=20)
        parser.add_argument('--orders', type=int, default=30)
        parser.add_argument('--reviews', type=int, default=100)

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tenant with ID {tenant_id} does not exist')
            )
            return

        self.tenant = tenant
        
        with transaction.atomic():
            self.create_settings()
            self.create_collections()
            self.create_shipping_zones()
            self.create_products(options['products'])
            self.create_customers(options['customers'])
            self.create_orders(options['orders'])
            self.create_reviews(options['reviews'])
            self.create_coupons()

        self.stdout.write(
            self.style.SUCCESS('Sample data created successfully!')
        )

    def create_settings(self):
        """Create e-commerce settings"""
        EcommerceSettings.objects.get_or_create(
            tenant=self.tenant,
            defaults={
                'store_name': fake.company(),
                'store_tagline': fake.catch_phrase(),
                'store_description': fake.text(200),
                'store_email': fake.email(),
                'contact_phone': fake.phone_number(),
                'business_address_line1': fake.street_address(),
                'business_city': fake.city(),
                'business_state': fake.state(),
                'business_country': fake.country(),
                'business_postal_code': fake.postcode(),
                'default_currency': 'USD',
                'is_live': True,
            }
        )

    def create_collections(self):
        """Create sample collections"""
        self.collections = []
        collection_names = [
            'Featured Products', 'New Arrivals', 'Best Sellers', 
            'Electronics', 'Clothing', 'Home & Garden'
        ]
        
        for name in collection_names:
            collection = Collection.objects.create(
                tenant=self.tenant,
                title=name,
                slug=name.lower().replace(' ', '-').replace('&', 'and'),
                description=fake.text(100),
                is_featured=random.choice([True, False]),
                is_visible=True
            )
            self.collections.append(collection)

    def create_shipping_zones(self):
        """Create shipping zones"""
        # Domestic zone
        domestic_zone = ShippingZone.objects.create(
            tenant=self.tenant,
            name='Domestic',
            countries=['US'],
            is_active=True
        )
        
        ShippingMethod.objects.create(
            tenant=self.tenant,
            name='Standard Shipping',
            shipping_zone=domestic_zone,
            rate_type='FLAT_RATE',
            base_rate=Decimal('9.99'),
            estimated_delivery_days_min=3,
            estimated_delivery_days_max=7
        )
        
        # International zone
        international_zone = ShippingZone.objects.create(
            tenant=self.tenant,
            name='International',
            countries=['CA', 'MX', 'GB', 'FR', 'DE'],
            is_active=True
        )
        
        ShippingMethod.objects.create(
            tenant=self.tenant,
            name='International Shipping',
            shipping_zone=international_zone,
            rate_type='FLAT_RATE',
            base_rate=Decimal('24.99'),
            estimated_delivery_days_min=7,
            estimated_delivery_days_max=14
        )

    def create_products(self, count):
        """Create sample products"""
        self.products = []
        
        # Ensure we have inventory products
        warehouse, _ = Warehouse.objects.get_or_create(
            tenant=self.tenant,
            name='Main Warehouse',
            defaults={
                'is_sellable': True,
                'address': fake.address()
            }
        )
        
        for i in range(count):
            # Create inventory product first
            inventory_product = Product.objects.create(
                tenant=self.tenant,
                name=fake.catch_phrase(),
                description=fake.text(200),
                sku=f'PROD-{i+1:04d}',
                product_code=f'PROD-{i+1:04d}',
                unit_price=Decimal(random.uniform(10, 500)),
            )
            
            # Create e-commerce product
            product = EcommerceProduct.objects.create(
                tenant=self.tenant,
                inventory_product=inventory_product,
                title=inventory_product.name,
                slug=f'product-{i+1}',
                url_handle=f'product-{i+1}',
                regular_price=Decimal(random.uniform(10, 500)),
                compare_at_price=Decimal(random.uniform(15, 600)) if random.choice([True, False]) else None,
                short_description=fake.sentence(),
                description=fake.text(400),
                status='ACTIVE',
                is_published=True,
                published_at=timezone.now(),
                stock_quantity=random.randint(0, 100),
                weight=Decimal(random.uniform(0.1, 5.0)),
                is_featured=random.choice([True, False]),
                vendor=fake.company(),
                tags=[fake.word() for _ in range(random.randint(2, 5))]
            )
            
            # Add to random collections
            collections_to_add = random.sample(
                self.collections, 
                random.randint(1, 3)
            )
            for collection in collections_to_add:
                collection.products.add(product)
            
            self.products.append(product)

    def create_customers(self, count):
        """Create sample customers"""
        self.customers = []
        
        for _ in range(count):
            customer = Customer.objects.create(
                tenant=self.tenant,
                name=fake.name(),
                email=fake.email(),
                phone=fake.phone_number(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80)
            )
            self.customers.append(customer)

    def create_orders(self, count):
        """Create sample orders"""
        for i in range(count):
            customer = random.choice(self.customers)
            
            order = Order.objects.create(
                tenant=self.tenant,
                customer=customer,
                customer_email=customer.email,
                status=random.choice(['PENDING', 'CONFIRMED', 'SHIPPED', 'DELIVERED']),
                payment_status=random.choice(['PENDING', 'PAID']),
                subtotal=Decimal('0'),
                total_amount=Decimal('0'),
                billing_address={
                    'first_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'address1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'postal_code': fake.postcode(),
                    'country': fake.country()
                },
                shipping_address={
                    'first_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'address1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'postal_code': fake.postcode(),
                    'country': fake.country()
                },
                payment_method='CREDIT_CARD'
            )
            
            # Add random order items
            subtotal = Decimal('0')
            for _ in range(random.randint(1, 5)):
                product = random.choice(self.products)
                quantity = random.randint(1, 3)
                price = product.current_price
                
                OrderItem.objects.create(
                    tenant=self.tenant,
                    order=order,
                    product=product,
                    title=product.title,
                    sku=product.sku,
                    quantity=quantity,
                    price=price,
                    line_total=price * quantity
                )
                
                subtotal += price * quantity
            
            order.subtotal = subtotal
            order.total_amount = subtotal
            order.save()

    def create_reviews(self, count):
        """Create sample reviews"""
        for _ in range(count):
            product = random.choice(self.products)
            customer = random.choice(self.customers)
            
            ReviewRating.objects.create(
                tenant=self.tenant,
                product=product,
                customer=customer,
                rating=random.randint(1, 5),
                title=fake.sentence(nb_words=6),
                review_text=fake.text(200),
                is_approved=random.choice([True, True, True, False]),  # 75% approved
                is_verified_purchase=random.choice([True, False])
            )

    def create_coupons(self):
        """Create sample coupons"""
        coupons_data = [
            {
                'code': 'WELCOME10',
                'name': 'Welcome Discount',
                'coupon_type': 'PERCENTAGE',
                'discount_value': Decimal('10'),
                'minimum_order_amount': Decimal('50')
            },
            {
                'code': 'SAVE25',
                'name': 'Save $25',
                'coupon_type': 'FIXED_AMOUNT',
                'discount_value': Decimal('25'),
                'minimum_order_amount': Decimal('100')
            },
            {
                'code': 'FREESHIP',
                'name': 'Free Shipping',
                'coupon_type': 'FREE_SHIPPING',
                'discount_value': Decimal('0'),
                'minimum_order_amount': Decimal('75')
            }
        ]
        
        for coupon_data
        Coupon.objects.create(
                tenant=self.tenant,
                valid_from=timezone.now(),
                valid_until=timezone.now() + timezone.timedelta(days=90),
                **coupon_data
            )
