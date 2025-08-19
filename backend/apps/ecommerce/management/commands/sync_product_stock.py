from django.core.management.base import BaseCommand
from django.db import transaction
from apps.ecommerce.models import EcommerceProduct, ProductVariant
from apps.inventory.models import Product, ProductVariation
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync product stock quantities from inventory to e-commerce'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to sync'
        )
        parser.add_argument(
            '--product-ids',
            type=str,
            help='Comma-separated product IDs to sync'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        product_ids = options.get('product_ids')
        dry_run = options.get('dry_run')

        # Build queryset
        queryset = EcommerceProduct.objects.select_related('inventory_product')
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if product_ids:
            ids = [int(id.strip()) for id in product_ids.split(',')]
            queryset = queryset.filter(id__in=ids)

        total_products = queryset.count()
        self.stdout.write(f'Processing {total_products} products...')

        updated_count = 0
        error_count = 0

        for product in queryset.iterator():
            try:
                old_stock = product.stock_quantity
                new_stock = self.get_inventory_stock(product)
                
                if old_stock != new_stock:
                    if not dry_run:
                        product.stock_quantity = new_stock
                        product.stock_status = self.determine_stock_status(
                            product, new_stock
                        )
                        product.save(update_fields=['stock_quantity', 'stock_status'])
                    
                    self.stdout.write(
                        f'{"[DRY RUN] " if dry_run else ""}Updated {product.title}: '
                        f'{old_stock} -> {new_stock}'
                    )
                    updated_count += 1

                # Sync variants
                if product.has_variants:
                    updated_count += self.sync_variants(product, dry_run)

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error syncing {product.title}: {str(e)}')
                )
                logger.error(f'Stock sync error for product {product.id}: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(
                f'{"DRY RUN: " if dry_run else ""}Sync completed: '
                f'{updated_count} updated, {error_count} errors'
            )
        )

    def get_inventory_stock(self, product):
        """Get available stock from inventory system"""
        if not product.inventory_product:
            return 0
        
        # Get total available stock from all sellable warehouses
        total_stock = product.inventory_product.stock_items.filter(
            warehouse__is_sellable=True
        ).aggregate(
            total=models.Sum('quantity_available')
        )['total'] or 0
        
        return max(0, total_stock)

    def determine_stock_status(self, product, stock_quantity):
        """Determine stock status based on quantity"""
        if not product.track_quantity:
            return 'IN_STOCK'
        
        if stock_quantity <= 0:
            if product.allow_backorders:
                return 'ON_BACKORDER'
            else:
                return 'OUT_OF_STOCK'
        
        return 'IN_STOCK'

    def sync_variants(self, product, dry_run):
        """Sync stock for product variants"""
        updated_count = 0
        
        for variant in product.variants.all():
            if variant.inventory_variation:
                old_stock = variant.inventory_quantity
                new_stock = variant.inventory_variation.available_stock or 0
                
                if old_stock != new_stock:
                    if not dry_run:
                        variant.inventory_quantity = new_stock
                        variant.save(update_fields=['inventory_quantity'])
                    
                    self.stdout.write(
                        f'  {"[DRY RUN] " if dry_run else ""}Variant {variant.title}: '
                        f'{old_stock} -> {new_stock}'
                    )
                    updated_count += 1
        
        return updated_count
