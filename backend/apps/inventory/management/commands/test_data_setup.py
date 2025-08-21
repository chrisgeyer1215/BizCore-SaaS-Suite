# apps/inventory/management/commands/test_data_setup.py
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
import random
from datetime import datetime, timedelta
from django.utils import timezone

from apps.inventory.tests.factories import *

class Command(BaseCommand):
    """
    Set up comprehensive test data for development and testing.
    
    Usage:
        python manage.py test_data_setup [options]
    """
    
    help = 'Set up comprehensive test data for development and testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-name',
            default='Test Company',
            help='Name of the test tenant'
        )
        
        parser.add_argument(
            '--products',
            type=int,
            default=100,
            help='Number of products to create'
        )
        
        parser.add_argument(
            '--warehouses',
            type=int,
            default=3,
            help='Number of warehouses to create'
        )
        
        parser.add_argument(
            '--movements',
            type=int,
            default=1000,
            help='Number of stock movements to create'
        )
        
        parser.add_argument(
            '--orders',
            type=int,
            default=50,
            help='Number of purchase orders to create'
        )
        
        parser.add_argument(
            '--days-history',
            type=int,
            default=365,
            help='Days of historical data to create'
        )
        
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing test data before creating new data'
        )
    
    def handle(self, *args, **options):
        """Create comprehensive test data."""
        self.stdout.write(
            self.style.SUCCESS('🏗️  Setting up comprehensive test data...')
        )
        
        with transaction.atomic():
            # Clear existing data if requested
            if options['clear_existing']:
                self._clear_existing_data()
            
            # Create tenant and basic setup
            tenant = self._create_tenant_setup(options)
            
            # Create core data
            categories, brands, suppliers, warehouses = self._create_core_data(
                tenant, options
            )
            
            # Create products
            products = self._create_products(
                tenant, categories, brands, suppliers, options
            )
            
            # Create stock items and movements
            self._create_stock_data(
                tenant, products, warehouses, options
            )
            
            # Create purchase orders
            self._create_purchase_orders(
                tenant, products, suppliers, warehouses, options
            )
            
            # Create ML training data
            self._create_ml_training_data(
                tenant, products, warehouses, options
            )
            
            self.stdout.write(
                self.style.SUCCESS('✅ Test data setup completed successfully!')
            )
            
            self._print_summary(tenant, options)
    
    def _clear_existing_data(self):
        """Clear existing test data."""
        self.stdout.write('🧹 Clearing existing test data...')
        
        # Clear in proper order to handle foreign key constraints
        from apps.inventory.models.stock.movements import StockMovement
        from apps.inventory.models.stock.items import StockItem
        from apps.inventory.models.catalog.products import Product
        from apps.inventory.models.purchasing.orders import PurchaseOrder
        
        StockMovement.objects.all().delete()
        StockItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Product.objects.all().delete()
        
        self.stdout.write('✅ Existing data cleared')
    
    def _create_tenant_setup(self, options):
        """Create tenant and basic user setup."""
        self.stdout.write('👥 Creating tenant and users...')
        
        # Create tenant
        tenant = TenantFactory(name=options['tenant_name'])
        
        # Create admin user
        admin_user = UserFactory(
            tenant=tenant,
            username='admin',
            email='admin@testcompany.com',
            is_staff=True,
            is_superuser=True
        )
        
        # Create regular users
        UserFactory.create_batch(
            5, 
            tenant=tenant,
            is_staff=False,
            is_superuser=False
        )
        
        self.stdout.write(f'✅ Tenant "{tenant.name}" created with users')
        return tenant
    
    def _create_core_data(self, tenant, options):
        """Create core reference data."""
        self.stdout.write('🏢 Creating core reference data...')
        
        # Create UOMs
        uoms = [
            UnitOfMeasureFactory(tenant=tenant, name='Each', abbreviation='EA'),
            UnitOfMeasureFactory(tenant=tenant, name='Kilogram', abbreviation='KG'),
            UnitOfMeasureFactory(tenant=tenant, name='Liter', abbreviation='L'),
            UnitOfMeasureFactory(tenant=tenant, name='Meter', abbreviation='M'),
            UnitOfMeasureFactory(tenant=tenant, name='Box', abbreviation='BOX'),
        ]
        
        # Create departments
        departments = DepartmentFactory.create_batch(5, tenant=tenant)
        
        # Create categories
        categories = []
        category_names = [
            'Electronics', 'Clothing', 'Books', 'Home & Garden', 
            'Sports & Outdoors', 'Health & Beauty', 'Automotive',
            'Tools & Hardware', 'Food & Beverages', 'Office Supplies'
        ]
        
        for name in category_names:
            category = CategoryFactory(
                tenant=tenant,
                name=name,
                department=random.choice(departments)
            )
            categories.append(category)
        
        # Create brands
        brand_names = [
            'Apple', 'Samsung', 'Nike', 'Adidas', 'Sony',
            'Microsoft', 'Google', 'Amazon', 'Dell', 'HP',
            'Canon', 'Nikon', 'Toyota', 'Ford', 'BMW'
        ]
        
        brands = []
        for name in brand_names:
            brand = BrandFactory(tenant=tenant, name=name)
            brands.append(brand)
        
        # Create suppliers
        suppliers = SupplierFactory.create_batch(20, tenant=tenant)
        
        # Create warehouses
        warehouse_names = ['Main Warehouse', 'Distribution Center', 'Retail Store']
        warehouses = []
        
        for i in range(options['warehouses']):
            name = warehouse_names[i] if i < len(warehouse_names) else f'Warehouse {i+1}'
            warehouse = WarehouseFactory(tenant=tenant, name=name)
            
            # Create locations for each warehouse
            StockLocationFactory.create_batch(10, warehouse=warehouse)
            warehouses.append(warehouse)
        
        self.stdout.write('✅ Core reference data created')
        return categories, brands, suppliers, warehouses
    
    def _create_products(self, tenant, categories, brands, suppliers, options):
        """Create products with realistic data."""
        self.stdout.write(f'📦 Creating {options["products"]} products...')
        
        products = []
        
        # Product templates for realistic data
        product_templates = [
            {'name': 'iPhone 14 Pro', 'category': 'Electronics', 'brand': 'Apple', 'cost': 800, 'price': 1200},
            {'name': 'Samsung Galaxy S23', 'category': 'Electronics', 'brand': 'Samsung', 'cost': 700, 'price': 1100},
            {'name': 'Nike Air Max 90', 'category': 'Clothing', 'brand': 'Nike', 'cost': 60, 'price': 120},
            {'name': 'Dell XPS 13', 'category': 'Electronics', 'brand': 'Dell', 'cost': 900, 'price': 1400},
            {'name': 'Office Chair Pro', 'category': 'Office Supplies', 'brand': 'Generic', 'cost': 150, 'price': 300},
        ]
        
        for i in range(options['products']):
            # Use template or generate random
            if i < len(product_templates):
                template = product_templates[i]
                category = next((c for c in categories if c.name == template['category']), random.choice(categories))
                brand = next((b for b in brands if b.name == template['brand']), random.choice(brands))
                cost_price = Decimal(str(template['cost']))
                selling_price = Decimal(str(template['price']))
                name = template['name']
            else:
                category = random.choice(categories)
                brand = random.choice(brands)
                cost_price = Decimal(str(random.uniform(10, 500)))
                selling_price = cost_price * Decimal(str(random.uniform(1.2, 2.5)))
                name = f"{category.name} Product {i+1}"
            
            product = ProductFactory(
                tenant=tenant,
                name=name,
                sku=f"PROD{i+1:06d}",
                category=category,
                brand=brand,
                supplier=random.choice(suppliers),
                cost_price=cost_price,
                selling_price=selling_price,
                reorder_level=Decimal(str(random.randint(10, 50))),
                max_stock_level=Decimal(str(random.randint(100, 500))),
                abc_classification=random.choices(['A', 'B', 'C'], weights=[20, 30, 50])[0]
            )
            products.append(product)
        
        self.stdout.write(f'✅ {len(products)} products created')
        return products
    
    def _create_stock_data(self, tenant, products, warehouses, options):
        """Create stock items and movements."""
        self.stdout.write('📊 Creating stock data...')
        
        # Create stock items
        stock_items = []
        for product in products:
            for warehouse in warehouses:
                location = random.choice(warehouse.locations.all())
                
                stock_item = StockItemFactory(
                    tenant=tenant,
                    product=product,
                    warehouse=warehouse,
                    location=location,
                    quantity_on_hand=Decimal(str(random.randint(0, 200))),
                    unit_cost=product.cost_price
                )
                stock_items.append(stock_item)
        
        # Create historical stock movements
        movement_types = ['RECEIPT', 'SALE', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'TRANSFER_IN', 'TRANSFER_OUT']
        
        for i in range(options['movements']):
            stock_item = random.choice(stock_items)
            movement_type = random.choice(movement_types)
            
            # Generate realistic quantities based on movement type
            if movement_type in ['RECEIPT', 'ADJUSTMENT_IN']:
                quantity = Decimal(str(random.randint(10, 100)))
            else:  # Outbound movements
                quantity = Decimal(str(random.randint(1, min(50, int(stock_item.quantity_on_hand))))
                
                # Ensure we don't go negative
                if quantity > stock_item.quantity_on_hand:
                    quantity = stock_item.quantity_on_hand
            
            # Random date within history period
            days_ago = random.randint(1, options['days_history'])
            created_at = timezone.now() - timedelta(days=days_ago)
            
            movement = StockMovementFactory(
                tenant=tenant,
                product=stock_item.product,
                warehouse=stock_item.warehouse,
                location=stock_item.location,
                movement_type=movement_type,
                quantity=quantity,
                unit_cost=stock_item.unit_cost,
                reference=f"TEST-{i+1:06d}",
                created_at=created_at
            )
            
            # Update stock item quantity (simplified)
            if movement_type in ['RECEIPT', 'ADJUSTMENT_IN', 'TRANSFER_IN']:
                stock_item.quantity_on_hand += quantity
            else:
                stock_item.quantity_on_hand = max(Decimal('0'), stock_item.quantity_on_hand - quantity)
            
            stock_item.save()
        
        self.stdout.write(f'✅ {options["movements"]} stock movements created')
    
    def _create_purchase_orders(self, tenant, products, suppliers, warehouses, options):
        """Create purchase orders."""
        self.stdout.write(f'📋 Creating {options["orders"]} purchase orders...')
        
        for i in range(options['orders']):
            supplier = random.choice(suppliers)
            warehouse = random.choice(warehouses)
            
            # Random date within history
            days_ago = random.randint(1, options['days_history'])
            order_date = timezone.now().date() - timedelta(days=days_ago)
            
            # Create PO
            po = PurchaseOrderFactory(
                tenant=tenant,
                po_number=f"PO-{i+1:06d}",
                supplier=supplier,
                warehouse=warehouse,
                order_date=order_date,
                status=random.choice(['DRAFT', 'APPROVED', 'SENT', 'RECEIVED']),
                expected_delivery_date=order_date + timedelta(days=random.randint(7, 30))
            )
            
            # Create PO items
            num_items = random.randint(1, 10)
            selected_products = random.sample(products, min(num_items, len(products)))
            
            total_amount = Decimal('0')
            
            for product in selected_products:
                quantity = Decimal(str(random.randint(10, 100)))
                unit_cost = product.cost_price * Decimal(str(random.uniform(0.9, 1.1)))  # Some price variation
                
                PurchaseOrderItemFactory(
                    tenant=tenant,
                    purchase_order=po,
                    product=product,
                    quantity_ordered=quantity,
                    unit_cost=unit_cost
                )
                
                total_amount += quantity * unit_cost
            
            po.total_amount = total_amount
            po.save()
        
        self.stdout.write(f'✅ {options["orders"]} purchase orders created')
    
    def _create_ml_training_data(self, tenant, products, warehouses, options):
        """Create additional data for ML training."""
        self.stdout.write('🤖 Creating ML training data...')
        
        # Create seasonal demand patterns for top products
        top_products = products[:20]  # Use first 20 products for ML data
        
        for product in top_products:
            warehouse = warehouses[0]  # Use first warehouse
            
            # Create daily demand data for the past year
            for days_ago in range(365):
                date = timezone.now().date() - timedelta(days=days_ago)
                
                # Generate seasonal demand pattern
                base_demand = random.randint(5, 25)
                
                # Add weekly seasonality (higher on weekends)
                if date.weekday() in [5, 6]:  # Saturday, Sunday
                    base_demand *= 1.3
                
                # Add monthly seasonality
                month_factor = 1 + 0.2 * np.sin(2 * np.pi * date.month / 12)
                base_demand = int(base_demand * month_factor)
                
                # Add noise
                actual_demand = max(0, base_demand + random.randint(-5, 5))
                
                if actual_demand > 0:
                    # Create corresponding sale movement
                    StockMovementFactory(
                        tenant=tenant,
                        product=product,
                        warehouse=warehouse,
                        movement_type='SALE',
                        quantity=Decimal(str(actual_demand)),
                        unit_cost=product.cost_price,
                        reference=f"ML-TRAIN-{date}",
                        created_at=timezone.make_aware(
                            datetime.combine(date, datetime.min.time())
                        )
                    )
        
        self.stdout.write('✅ ML training data created')
    
    def _print_summary(self, tenant, options):
        """Print summary of created data."""
        self.stdout.write('\n📊 Test Data Summary:')
        self.stdout.write('=' * 50)
        
        from apps.inventory.models.catalog.products import Product
        from apps.inventory.models.stock.items import StockItem
        from apps.inventory.models.stock.movements import StockMovement
        from apps.inventory.models.purchasing.orders import PurchaseOrder
        
        product_count = Product.objects.filter(tenant=tenant).count()
        stock_item_count = StockItem.objects.filter(tenant=tenant).count()
        movement_count = StockMovement.objects.filter(tenant=tenant).count()
        po_count = PurchaseOrder.objects.filter(tenant=tenant).count()
        
        self.stdout.write(f'📦 Products: {product_count}')
        self.stdout.write(f'🏪 Stock Items: {stock_item_count}')
        self.stdout.write(f'📊 Stock Movements: {movement_count}')
        self.stdout.write(f'📋 Purchase Orders: {po_count}')
        self.stdout.write(f'🏢 Warehouses: {options["warehouses"]}')
        
        total_stock_value = StockItem.objects.filter(tenant=tenant).aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'))
        )['total'] or Decimal('0')
        
        self.stdout.write(f'💰 Total Stock Value: ${total_stock_value:,.2f}')
        self.stdout.write('\n🎉 Ready for testing and development!')