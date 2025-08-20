from django.db import models
from django.db.models import Q, F, Sum, Count, Avg, Case, When, Value
from django.db.models.functions import Coalesce, Extract
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional

class InventoryQueryUtils:
    """
    Utility class for complex inventory queries
    """
    
    @staticmethod
    def get_stock_aging_analysis(tenant, warehouse=None, days_buckets=None):
        """
        Get stock aging analysis
        """
        if days_buckets is None:
            days_buckets = [30, 60, 90, 180, 365]
        
        from ..models import StockItem
        
        queryset = StockItem.objects.for_tenant(tenant)
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        
        # Calculate days since last movement
        queryset = queryset.annotate(
            days_since_movement=Case(
                When(
                    last_movement_date__isnull=True,
                    then=Extract('day', timezone.now() - F('created_at'))
                ),
                default=Extract('day', timezone.now() - F('last_movement_date')),
                output_field=models.IntegerField()
            )
        )
        
        # Create aging buckets
        aging_cases = []
        for i, days in enumerate(days_buckets):
            if i == 0:
                aging_cases.append(
                    When(days_since_movement__lte=days, then=Value(f'0-{days} days'))
                )
            else:
                prev_days = days_buckets[i-1]
                aging_cases.append(
                    When(days_since_movement__range=(prev_days+1, days), then=Value(f'{prev_days+1}-{days} days'))
                )
        
        # Add final bucket for very old stock
        if days_buckets:
            max_days = max(days_buckets)
            aging_cases.append(
                When(days_since_movement__gt=max_days, then=Value(f'>{max_days} days'))
            )
        
        return queryset.annotate(
            aging_bucket=Case(*aging_cases, default=Value('Unknown'), output_field=models.CharField())
        ).values('aging_bucket').annotate(
            item_count=Count('id'),
            total_quantity=Sum('quantity_on_hand'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        ).order_by('aging_bucket')
    
    @staticmethod
    def get_movement_velocity_analysis(tenant, days=90, warehouse=None):
        """
        Analyze stock movement velocity
        """
        from ..models import StockMovement, StockItem
        
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        # Get movement data
        movement_query = StockMovement.objects.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date],
            status='COMPLETED'
        )
        
        if warehouse:
            movement_query = movement_query.filter(warehouse=warehouse)
        
        # Calculate velocity metrics
        return StockItem.objects.for_tenant(tenant).annotate(
            total_movements=Count(
                'stockmovementitem__movement',
                filter=Q(
                    stockmovementitem__movement__created_at__range=[start_date, end_date],
                    stockmovementitem__movement__status='COMPLETED'
                )
            ),
            total_quantity_moved=Coalesce(
                Sum(
                    'stockmovementitem__quantity',
                    filter=Q(
                        stockmovementitem__movement__created_at__range=[start_date, end_date],
                        stockmovementitem__movement__status='COMPLETED'
                    )
                ), 0
            ),
            avg_daily_movement=F('total_quantity_moved') / days,
            velocity_ratio=Case(
                When(quantity_on_hand=0, then=Value(0)),
                default=F('avg_daily_movement') / F('quantity_on_hand'),
                output_field=models.DecimalField(max_digits=10, decimal_places=4)
            )
        ).filter(total_movements__gt=0)
    
    @staticmethod
    def get_supplier_performance_metrics(tenant, start_date, end_date):
        """
        Calculate supplier performance metrics
        """
        from ..models import PurchaseOrder, StockReceipt, Supplier
        
        return Supplier.objects.for_tenant(tenant).annotate(
            total_orders=Count(
                'purchaseorder',
                filter=Q(purchaseorder__order_date__range=[start_date, end_date])
            ),
            completed_orders=Count(
                'purchaseorder',
                filter=Q(
                    purchaseorder__order_date__range=[start_date, end_date],
                    purchaseorder__status='COMPLETED'
                )
            ),
            total_order_value=Coalesce(
                Sum(
                    'purchaseorder__total_amount',
                    filter=Q(purchaseorder__order_date__range=[start_date, end_date])
                ), 0
            ),
            avg_lead_time=Avg(
                F('purchaseorder__stockreceipt__receipt_date') - F('purchaseorder__order_date'),
                filter=Q(
                    purchaseorder__order_date__range=[start_date, end_date],
                    purchaseorder__stockreceipt__status='COMPLETED'
                )
            ),
            on_time_deliveries=Count(
                'purchaseorder',
                filter=Q(
                    purchaseorder__order_date__range=[start_date, end_date],
                    purchaseorder__stockreceipt__receipt_date__lte=F('purchaseorder__expected_delivery_date'),
                    purchaseorder__stockreceipt__status='COMPLETED'
                )
            )
        ).filter(total_orders__gt=0).annotate(
            completion_rate=Case(
                When(total_orders=0, then=Value(0)),
                default=F('completed_orders') * 100.0 / F('total_orders'),
                output_field=models.DecimalField(max_digits=5, decimal_places=2)
            ),
            on_time_rate=Case(
                When(completed_orders=0, then=Value(0)),
                default=F('on_time_deliveries') * 100.0 / F('completed_orders'),
                output_field=models.DecimalField(max_digits=5, decimal_places=2)
            )
        )

class BulkOperationsMixin:
    """
    Mixin for bulk operations on inventory models
    """
    
    def bulk_update_stock_levels(self, updates: List[Dict[str, Any]], tenant):
        """
        Bulk update stock levels
        updates: [{'product_id': 1, 'warehouse_id': 1, 'quantity': 100, 'unit_cost': 10.50}, ...]
        """
        from django.db import transaction
        from ..models import StockItem, StockMovement, StockMovementItem
        
        with transaction.atomic():
            # Group updates by stock item
            stock_items_to_update = []
            movements_to_create = []
            
            for update in updates:
                try:
                    stock_item = StockItem.objects.get(
                        tenant=tenant,
                        product_id=update['product_id'],
                        warehouse_id=update['warehouse_id']
                    )
                    
                    old_quantity = stock_item.quantity_on_hand
                    new_quantity = update['quantity']
                    quantity_diff = new_quantity - old_quantity
                    
                    # Update stock item
                    stock_item.quantity_on_hand = new_quantity
                    if 'unit_cost' in update:
                        stock_item.unit_cost = update['unit_cost']
                    stock_items_to_update.append(stock_item)
                    
                    # Create movement record
                    if quantity_diff != 0:
                        movement_type = 'ADJUSTMENT_POSITIVE' if quantity_diff > 0 else 'ADJUSTMENT_NEGATIVE'
                        movements_to_create.append({
                            'tenant': tenant,
                            'warehouse_id': update['warehouse_id'],
                            'movement_type': movement_type,
                            'reference_number': f'BULK-{timezone.now().strftime("%Y%m%d-%H%M%S")}',
                            'items': [{
                                'stock_item': stock_item,
                                'quantity': abs(quantity_diff),
                                'unit_cost': update.get('unit_cost', stock_item.unit_cost)
                            }]
                        })
                        
                except StockItem.DoesNotExist:
                    continue
            
            # Bulk update stock items
            StockItem.objects.bulk_update(
                stock_items_to_update, 
                ['quantity_on_hand', 'unit_cost', 'updated_at']
            )
            
            # Create movement records
            for movement_data in movements_to_create:
                items_data = movement_data.pop('items')
                movement = StockMovement.objects.create(**movement_data)
                
                movement_items = [
                    StockMovementItem(
                        movement=movement,
                        **item_data
                    ) for item_data in items_data
                ]
                StockMovementItem.objects.bulk_create(movement_items)
    
    def bulk_create_products_with_stock(self, products tenant):
        """
        Bulk create products with initial stock
        """
        from django.db import transaction
        from ..models import Product, StockItem
        
        with transaction.atomic():
            products = []
            stock_items = []
            
            for product_data in products_data:
                stock_data = product_data.pop('initial_stock', {})
                
                product = Product(tenant=tenant, **product_data)
                products.append(product)_item = StockItem(
                        tenant=tenant,
                        product=product,
                        **stock_data
                    )
                    stock_items.append(stock_item)
            
            # Bulk create products
            Product.objects.bulk_create(products)
            
            # Update stock items with created product instances
            for i, stock_item in enumerate(stock_items):
                stock_item.product = products[i]
            
            # Bulk create stock items
            StockItem.objects.bulk_create(stock_items)
            
            return products
    
    def bulk_process_transfers(self, transfers_ Any]], tenant):
        """
        Bulk process stock transfers
        """
        from django.db import transaction
        from ..models import StockTransfer, StockTransferItem, StockItem
        
        with transaction.atomic():
            transfers_created = []
            
            for transfer
                items_data = transfer_data.pop('items', [])
                
                # Create transfer
                transfer = StockTransfer.objects.create(
                    tenant=tenant,
                    **transfer_data
                )
                
                # Create transfer items
                transfer_items = []
                for item_data in items_item = StockTransferItem(
                        transfer=transfer,
                        **item_data
                    )
                    transfer_items.append(transfer_item)
                
                StockTransferItem.objects.bulk_create(transfer_items)
                transfers_created.append(transfer)
            
            return transfers_created