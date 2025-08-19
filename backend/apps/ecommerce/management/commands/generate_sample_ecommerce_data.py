"""
Management command to generate sample e-commerce data for testing
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random
from faker import Faker

from apps.tenants.models import Tenant
from apps.ecommerce.models import (
    EcommerceSettings, EcommerceCategory, EcommerceProduct, Order, OrderItem,
    Coupon, ProductReview, Cart, CartItem
)
from apps.inventory.models import Product as InventoryProduct

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = 'Generate sample e-commerce data for testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Tenant ID to create data for',
            required=True
        )
        parser.add_argument(
            '--products',
            type=int,
            default=50,
            help='Number of e-commerce products to create'
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=100,
            help='Number of orders to create'
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=20,
            help='Number of customers to create'
        )
        parser.add_argument(
            '--reviews',
            type=int,
            default=200,
            help='Number of reviews to create'
        )
    
    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(id=options['tenant_id'])
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tenant with ID {options["tenant_id"]} does not exist')
            )
            return
        
        self.stdout.write(f'Creating sample e-commerce data for tenant: {tenant.name}')
        
        # Create e-commerce settings
        settings, created = EcommerceSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                'store_name': f'{tenant.name} Store',
                'store_email': f'store@{tenant.schema_name}.com',
                'enable_reviews': True,
                'enable_coupons': True,
                'enable_wishlists': True
            }
        )
        if created:
            self.stdout.write('Created e-commerce settings')
        
        # Create categories
        categories = self.create_categories(tenant)
        self.stdout.write(f'Created {len(categories)} categories')
        
        # Create e-commerce products from existing inventory products
        ecommerce_products = self.create_ecommerce_products(tenant, categories, options['products'])
        self.stdout.write(f'Created {len(ecommerce_products)} e-commerce products')
        
        # Create customers
        customers = self.create_customers(options['customers'])
        self.stdout.write(f'Created {len(customers)} customers')
        
        # Create orders
        orders = self.create_orders(tenant, customers, ecommerce_products, options['orders'])
        self.stdout.write(f'Created {len(orders)} orders')
        
        # Create reviews
        reviews = self.create_reviews(tenant, customers, ecommerce_products, orders, options['reviews'])
        self.stdout.write(f'Created {len(reviews)} reviews')
        
        # Create coupons
        coupons = self.create_coupons(tenant, categories, ecommerce_products)
        self.stdout.write(f'Created {len(coupons)} coupons')
        
        # Create some active carts
        carts = self.create_active_carts(tenant, customers, ecommerce_products)
        self.stdout.write(f'Created {len(carts)} active carts')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created sample e-commerce data for tenant: {tenant.name}')
        )
    
    def create_categories(self, tenant):
        """Create sample e-commerce categories"""
        categories = []
        
        category_data = [
            ('Electronics', ['Smartphones', 'Laptops', 'Accessories']),
            ('Clothing', ['Men\'s Clothing', 'Women\'s Clothing', 'Shoes']),
            ('Home & Garden', ['Furniture', 'Decor', 'Kitchen']),
            ('Books', ['Fiction', 'Non-Fiction', 'Technical']),
            ('Sports', ['Fitness', 'Outdoor', 'Equipment']),
        ]
        
        for parent Create parent category
            parent, created = EcommerceCategory.objects.get_or_create(
                tenant=tenant,
                name=parent_name,
                defaults={
                    'slug': parent_name.lower().replace(' ', '-').replace('&', 'and'),
                    'description': f'{parent_name} products and accessories',
                    'is_active': True,
                    'is_featured': random.choice([True, False]),
                    'sort_order': len(categories) * 10
                }
            )
            categories.append(parent)
            
            # Create child categories
            for child_name in children:
                child, created = EcommerceCategory.objects.get_or_create(
                    tenant=tenant,
                    name=child_name,
                    defaults={
                        'slug': child_name.lower().replace(' ', '-').replace('\'', ''),
                        'description': f'{child_name} in {parent_name}',
                        'parent': parent,
                        'is_active': True,
                        'sort_order': len(categories) * 10
                    }
                )
                categories.append(child)
        
        return categories
    
    def create_ecommerce_products(self, tenant, categories, count):
        """Create e-commerce products from inventory products"""
        # Get existing inventory products
        inventory_products = InventoryProduct.objects.filter(
            tenant=tenant,
            status='ACTIVE'
        )[:count]
        
        if not inventory_products.exists():
            self.stdout.write(
                self.style.WARNING('No inventory products found. Create inventory products first.')
            )
            return []
        
        ecommerce_products = []
        
        for inventory_product in inventory_products:
            # Skip if e-commerce product already exists
            if EcommerceProduct.objects.filter(
                tenant=tenant,
                inventory_product=inventory_product
            ).exists():
                continue
            
            category = random.choice(categories)
            regular_price = Decimal(str(random.uniform(10, 500)))
            
            # 30% chance of being on sale
            sale_price = None
            if random.random() < 0.3:
                sale_price = regular_price * Decimal(str(random.uniform(0.7, 0.9)))
            
            ecommerce_product = EcommerceProduct.objects.create(
                tenant=tenant,
                inventory_product=inventory_product,
                product_type='SIMPLE',
                status='ACTIVE',
                primary_category=category,
                regular_price=regular_price,
                sale_price=sale_price,
                stock_quantity=random.randint(0, 100),
                low_stock_threshold=random.randint(5, 20),
                stock_status=random.choice(['IN_STOCK', 'OUT_OF_STOCK', 'LOW_STOCK']),
                slug=inventory_product.sku.lower(),
                short_description=fake.sentence(),
                long_description=fake.text(),
                is_featured=random.choice([True, False]),
                is_best_seller=random.choice([True, False]),
                is_new_arrival=random.choice([True, False]),
                visibility='VISIBLE',
                view_count=random.randint(0, 1000),
                sales_count=random.randint(0, 100),
                average_rating=Decimal(str(random.uniform(3.0, 5.0))),
                review_count=random.randint(0, 50)
            )
            
            # Add to additional categories
            additional_categories = random.sample(
                [c for c in categories if c != category],
                random.randint(0, 2)
            )
            ecommerce_product.categories.set([category] + additional_categories)
            
            ecommerce_products.append(ecommerce_product)
        
        return ecommerce_products
    
    def create_customers(self, count):
        """Create sample customers"""
        customers = []
        
        for i in range(count):
            customer = User.objects.create_user(
                email=fake.email(),
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name()
            )
            customers.append(customer)
        
        return customers
    
    def create_orders(self, tenant, customers, products, count):
        """Create sample orders"""
        orders = []
        
        for i in range(count):
            customer = random.choice(customers)
            
            order = Order.objects.create(
                tenant=tenant,
                order_number=f'ORD-{fake.date_this_year().strftime("%Y%m%d")}-{fake.random_number(digits=6)}',
                customer=customer,
                customer_email=customer.email,
                status=random.choice(['PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'COMPLETED']),
                payment_status=random.choice(['PENDING', 'PAID', 'FAILED']),
                currency='USD',
                payment_method=random.choice(['credit_card', 'paypal', 'stripe']),
                billing_address={
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'address_line1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'country': 'USA',
                    'postal_code': fake.postcode()
                },
                shipping_address={
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'address_line1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'country': 'USA',
                    'postal_code': fake.postcode()
                },
                order_date=fake.date_time_this_year()
            )
            
            # Create order items
            num_items = random.randint(1, 5)
            selected_products = random.sample(products, min(num_items, len(products)))
            
            subtotal = Decimal('0.00')
            
            for product in selected_products:
                quantity = random.randint(1, 3)
                unit_price = product.current_price
                total_price = unit_price * quantity
                
                OrderItem.objects.create(
                    tenant=tenant,
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_sku=product.sku,
                    unit_price=unit_price,
                    quantity=quantity,
                    total_price=total_price
                )
                
                subtotal += total_price
            
            # Update order totals
            tax_amount = subtotal * Decimal('0.08')  # 8% tax
            shipping_amount = Decimal('10.00') if subtotal < 50 else Decimal('0.00')
            
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.shipping_amount = shipping_amount
            order.total_amount = subtotal + tax_amount + shipping_amount
            order.save()
            
            orders.append(order)
        
        return orders
    
    def create_reviews(self, tenant, customers, products, orders, count):
        """Create sample product reviews"""
        reviews = []
        
        for i in range(count):
            customer = random.choice(customers)
            product = random.choice(products)
            order = random.choice([o for o in orders if o.customer == customer]) if orders else None
            
            # Don't create duplicate reviews
            if ProductReview.objects.filter(
                tenant=tenant,
                product=product,
                customer=customer
            ).exists():
                continue
            
            review = ProductReview.objects.create(
                tenant=tenant,
                product=product,
                customer=customer,
                order=order,
                rating=random.randint(1, 5),
                title=fake.sentence()[:200],
                review_text=fake.text(),
                status=random.choice(['PENDING', 'APPROVED', 'REJECTED']),
                helpful_count=random.randint(0, 20),
                not_helpful_count=random.randint(0, 5),
                is_verified_purchase=bool(order),
                created_at=fake.date_time_this_year()
            )
            
            reviews.append(review)
        
        return reviews
    
    def create_coupons(self, tenant, categories, products):
        """Create sample coupons"""
        coupons = []
        
        coupon_data = [
            ('WELCOME10', 'Welcome Discount', 'PERCENTAGE', 10),
            ('SAVE20', 'Save $20', 'FIXED_AMOUNT', 20),
            ('FREESHIP', 'Free Shipping', 'FREE_SHIPPING', 0),
            ('NEWUSER15', 'New User 15% Off', 'PERCENTAGE', 15),
            ('BULK50', 'Bulk Order Discount', 'FIXED_AMOUNT', 50),
        ]
        
        for code, name, coupon_type, value.create(
                tenant=tenant,
                code=code,
                name=name,
                description=f'{name} - Limited time offer',
                coupon_type=coupon_type,
                discount_value=Decimal(str(value)),
                applicable_to=random.choice(['ALL', 'CATEGORIES', 'PRODUCTS']),
                minimum_order_amount=Decimal(str(random.choice([0, 50, 100]))),
                usage_limit_per_coupon=random.choice([None, 100, 500, 1000]),
                usage_limit_per_customer=random.choice([None, 1, 3, 5]),
                valid_from=fake.date_time_this_year(),
                valid_until=fake.date_time_between(start_date='now', end_date='+1y'),
                is_active=True
            )
            
            # Add applicable categories/products
            if coupon.applicable_to == 'CATEGORIES':
                coupon.applicable_categories.set(random.sample(categories, random.randint(1, 3)))
            elif coupon.applicable_to == 'PRODUCTS':
                coupon.applicable_products.set(random.sample(products, random.randint(1, 5)))
            
            coupons.append(coupon)
        
        return coupons
    
    def create_active_carts(self, tenant, customers, products):
        """Create sample active carts"""
        carts = []
        
        # Create active carts for some customers
        selected_customers = random.sample(customers, min(10, len(customers)))
        
        for customer in selected_customers:
            cart = Cart.objects.create(
                tenant=tenant,
                customer=customer,
                is_active=True,
                currency='USD'
            )
            
            # Add random items to cart
            num_items = random.randint(1, 4)
            selected_products = random.sample(products, min(num_items, len(products)))
            
            subtotal = Decimal('0.00')
            
            for product in selected_products:
                quantity = random.randint(1, 2)
                unit_price = product.current_price
                
                CartItem.objects.create(
                    tenant=tenant,
                    cart=cart,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price
                )
                
                subtotal += unit_price * quantity
            
            # Update cart totals
            cart.subtotal = subtotal
            cart.total_amount = subtotal
            cart.save()
            
            # Some carts are abandoned
            if random.random() < 0.3:
                cart.is_abandoned = True
                cart.abandoned_at = fake.date_time_this_month()
                cart.save()
            
            carts.append(cart)
        
        return carts
