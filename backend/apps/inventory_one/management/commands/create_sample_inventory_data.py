"""
Management command to create sample inventory data for testing
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random
from faker import Faker

from apps.tenants.models import Tenant
from apps.inventory_one.models import (
    InventorySettings, UnitOfMeasure, Department, Category, SubCategory,
    Brand, Supplier, Warehouse, StockLocation, Product, StockItem
)

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = 'Create sample inventory data for testing'
    
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
            help='Number of products to create'
        )
        parser.add_argument(
            '--suppliers',
            type=int,
            default=10,
            help='Number of suppliers to create'
        )
        parser.add_argument(
            '--warehouses',
            type=int,
            default=3,
            help='Number of warehouses to create'
        )
    
    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(id=options['tenant_id'])
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tenant with ID {options["tenant_id"]} does not exist')
            )
            return
        
        self.stdout.write(f'Creating sample data for tenant: {tenant.name}')
        
        # Create inventory settings
        settings, created = InventorySettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                'valuation_method': 'FIFO',
                'enable_batch_tracking': True,
                'enable_barcode': True,
                'enable_abc_analysis': True
            }
        )
        
        # Create units of measure
        units = self.create_units(tenant)
        self.stdout.write(f'Created {len(units)} units of measure')
        
        # Create departments and categories
        departments = self.create_departments(tenant)
        categories = self.create_categories(tenant, departments)
        self.stdout.write(f'Created {len(departments)} departments and {len(categories)} categories')
        
        # Create brands
        brands = self.create_brands(tenant)
        self.stdout.write(f'Created {len(brands)} brands')
        
        # Create suppliers
        suppliers = self.create_suppliers(tenant, options['suppliers'])
        self.stdout.write(f'Created {len(suppliers)} suppliers')
        
        # Create warehouses
        warehouses = self.create_warehouses(tenant, options['warehouses'])
        self.stdout.write(f'Created {len(warehouses)} warehouses')
        
        # Create products
        products = self.create_products(tenant, options['products'], departments, categories, brands, units, suppliers)
        self.stdout.write(f'Created {len(products)} products')
        
        # Create stock items
        stock_items = self.create_stock_items(tenant, products, warehouses)
        self.stdout.write(f'Created {len(stock_items)} stock items')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created sample inventory data for tenant: {tenant.name}')
        )
    
    def create_units(self, tenant):
        """Create common units of measure"""
        units_data = [
            # Count
            ('Each', 'EA', '', 'COUNT', True),
            ('Piece', 'PC', '', 'COUNT', False),
            ('Dozen', 'DOZ', '', 'COUNT', False),
            
            # Weight
            ('Kilogram', 'KG', 'kg', 'WEIGHT', True),
            ('Gram', 'G', 'g', 'WEIGHT', False),
            ('Pound', 'LB', 'lb', 'WEIGHT', False),
            
            # Volume
            ('Liter', 'L', 'L', 'VOLUME', True),
            ('Milliliter', 'ML', 'mL', 'VOLUME', False),
            ('Gallon', 'GAL', 'gal', 'VOLUME', False),
            
            # Length
            ('Meter', 'M', 'm', 'LENGTH', True),
            ('Centimeter', 'CM', 'cm', 'LENGTH', False),
            ('Inch', 'IN', '"', 'LENGTH', False),
        ]
        
        units = []
        for name, abbrev, symbol, unit, created = UnitOfMeasure.objects.get_or_create(
                tenant=tenant,
                name=name,
                defaults={
                    'abbreviation': abbrev,
                    'symbol': symbol,
                    'unit_type': unit_type,
                    'is_base_unit': is_base,
                    'is_active': True
                }
            )
            units.append(unit)
        
        return units
    
    def create_departments(self, tenant):
        """Create sample departments"""
        dept_names = [
            'Electronics', 'Clothing', 'Home & Garden', 'Sports & Outdoors',
            'Automotive', 'Health & Beauty', 'Books & Media', 'Toys & Games'
        ]
        
        departments = []
        for i, name in enumerate(dept_names):
            dept, created = Department.objects.get_or_create(
                tenant=tenant,
                code=f'DEPT{i+1:03d}',
                defaults={
                    'name': name,
                    'description': f'{name} department',
                    'sort_order': i * 10,
                    'is_active': True
                }
            )
            departments.append(dept)
        
        return departments
    
    def create_categories(self, tenant, departments):
        """Create sample categories"""
        categories = []
        
        category_mapping = {
            'Electronics': ['Computers', 'Mobile Phones', 'Audio', 'TV & Video'],
            'Clothing': ['Men\'s Clothing', 'Women\'s Clothing', 'Shoes', 'Accessories'],
            'Home & Garden': ['Furniture', 'Kitchen', 'Garden Tools', 'Lighting'],
            'Sports & Outdoors': ['Exercise & Fitness', 'Outdoor Recreation', 'Sports Equipment'],
            'Automotive': ['Car Parts', 'Tools', 'Car Care', 'Motorcycle'],
            'Health & Beauty': ['Skincare', 'Makeup', 'Health Supplements', 'Personal Care'],
            'Books & Media': ['Books', 'Movies', 'Music', 'Games'],
            'Toys & Games': ['Action Figures', 'Board Games', 'Educational Toys', 'Outdoor Toys']
        }
        
        for dept in departments:
            if dept.name in category_mapping:
                for i, cat_name in enumerate(category_mapping[dept.name]):
                    cat, created = Category.objects.get_or_create(
                        tenant=tenant,
                        department=dept,
                        code=f'{dept.code}C{i+1:02d}',
                        defaults={
                            'name': cat_name,
                            'description': f'{cat_name} in {dept.name}',
                            'sort_order': i * 10,
                            'is_active': True
                        }
                    )
                    categories.append(cat)
        
        return categories
    
    def create_brands(self, tenant):
        """Create sample brands"""
        brand_names = [
            'TechPro', 'StyleMax', 'HomeComfort', 'SportActive', 'AutoExpert',
            'BeautyLux', 'BookWorld', 'PlayFun', 'QualityFirst', 'ValueBest'
        ]
        
        brands = []
        for i, name in enumerate(brand_names):
            brand, created = Brand.objects.get_or_create(
                tenant=tenant,
                code=f'BRD{i+1:03d}',
                defaults={
                    'name': name,
                    'description': f'{name} brand products',
                    'country_of_origin': fake.country(),
                    'quality_rating': Decimal(str(random.uniform(3.5, 5.0))),
                    'is_active': True
                }
            )
            brands.append(brand)
        
        return brands
    
    def create_suppliers(self, tenant, count):
        """Create sample suppliers"""
        suppliers = []
        
        for i in range(count):
            supplier, created = Supplier.objects.get_or_create(
                tenant=tenant,
                code=f'SUP{i+1:03d}',
                defaults={
                    'name': fake.company(),
                    'company_name': fake.company(),
                    'supplier_type': random.choice(['MANUFACTURER', 'WHOLESALER', 'DISTRIBUTOR']),
                    'email': fake.company_email(),
                    'phone': fake.phone_number()[:20],
                    'address_line1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'country': fake.country()[:100],
                    'postal_code': fake.postcode(),
                    'payment_terms': random.choice(['NET_30', 'NET_15', 'NET_45']),
                    'lead_time_days': random.randint(3, 21),
                    'quality_rating': Decimal(str(random.uniform(3.0, 5.0))),
                    'delivery_rating': Decimal(str(random.uniform(3.0, 5.0))),
                    'service_rating': Decimal(str(random.uniform(3.0, 5.0))),
                    'is_active': True
                }
            )
            suppliers.append(supplier)
        
        return suppliers
    
    def create_warehouses(self, tenant, count):
        """Create sample warehouses"""
        warehouses = []
        
        for i in range(count):
            is_default = i == 0  # First warehouse is default
            
            warehouse, created = Warehouse.objects.get_or_create(
                tenant=tenant,
                code=f'WH{i+1:03d}',
                defaults={
                    'name': f'Warehouse {i+1}',
                    'warehouse_type': 'PHYSICAL',
                    'address_line1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'country': fake.country()[:100],
                    'postal_code': fake.postcode(),
                    'phone': fake.phone_number()[:20],
                    'is_active': True,
                    'is_default': is_default,
                    'is_sellable': True
                }
            )
            
            # Create some locations for each warehouse
            for j in range(5):
                StockLocation.objects.get_or_create(
                    tenant=tenant,
                    warehouse=warehouse,
                    code=f'LOC{j+1:03d}',
                    defaults={
                        'name': f'Location {j+1}',
                        'location_type': 'STORAGE',
                        'zone': f'Z{j+1}',
                        'aisle': f'A{j+1}',
                        'rack': f'R{j+1}',
                        'is_active': True
                    }
                )
            
            warehouses.append(warehouse)
        
        return warehouses
    
    def create_products(self, tenant, count, departments, categories, brands, units, suppliers):
        """Create sample products"""
        products = []
        
        for i in range(count):
            department = random.choice(departments)
            category = random.choice([c for c in categories if c.department == department])
            brand = random.choice(brands)
            unit = random.choice([u for u in units if u.unit_type == 'COUNT'])
            supplier = random.choice(suppliers)
            
            product, created = Product.objects.get_or_create(
                tenant=tenant,
                sku=f'PRD{i+1:06d}',
                defaults={
                    'name': fake.catch_phrase(),
                    'description': fake.text(max_nb_chars=200),
                    'department': department,
                    'category': category,
                    'brand': brand,
                    'unit': unit,
                    'preferred_supplier': supplier,
                    'cost_price': Decimal(str(random.uniform(10, 200))),
                    'selling_price': Decimal(str(random.uniform(20, 400))),
                    'min_stock_level': Decimal(str(random.randint(10, 50))),
                    'reorder_point': Decimal(str(random.randint(5, 25))),
                    'reorder_quantity': Decimal(str(random.randint(50, 200))),
                    'status': 'ACTIVE',
                    'is_saleable': True,
                    'is_purchasable': True,
                    'track_inventory': True
                }
            )
            products.append(product)
        
        return products
    
    def create_stock_items(self, tenant, products, warehouses):
        """Create sample stock items"""
        stock_items = []
        
        for product in products:
            # Create stock in random warehouses (not all warehouses for each product)
            selected_warehouses = random.sample(warehouses, random.randint(1, len(warehouses)))
            
            for warehouse in selected_warehouses:
                quantity = Decimal(str(random.randint(0, 500)))
                
                stock_item, created = StockItem.objects.get_or_create(
                    tenant=tenant,
                    product=product,
                    warehouse=warehouse,
                    defaults={
                        'quantity_on_hand': quantity,
                        'quantity_available': quantity,
                        'unit_cost': product.cost_price,
                        'average_cost': product.cost_price,
                        'last_cost': product.cost_price,
                        'total_value': quantity * product.cost_price,
                        'abc_classification': random.choice(['A', 'B', 'C']),
                        'is_active': True
                    }
                )
                stock_items.append(stock_item)
        
        return stock_items
