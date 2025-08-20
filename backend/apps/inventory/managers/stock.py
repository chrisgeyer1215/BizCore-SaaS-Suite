from django.db import models
from django.db.models import Q, F, Sum, Count, Avg, Max, Min, Case, When, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
from .base import TenantAwareManager
from .tenant import TenantQuerySet

class StockQuerySet(TenantQuerySet):
    """
    Custom queryset for stock-related operations
    """
    
    def with_quantities(self):
        """Annotate with calculated quantities"""
        return self.annotate(
            total_quantity=F('quantity_on_hand') + F('quantity_reserved'),
            available_quantity=F('quantity_on_hand') - F('quantity_reserved'),
            quantity_in_transit=Coalesce(
                Sum('stockmovementitem__quantity', 
                    filter=Q(stockmovementitem__movement__status='IN_TRANSIT')), 
                0
            )
        )
    
    def low_stock(self):
        """Get items with low stock"""
        return self.filter(
            quantity_on_hand__lte=F('reorder_level')
        ).exclude(reorder_level=0)
    
    def out_of_stock(self):
        """Get out of stock items"""
        return self.filter(quantity_on_hand=0)
    
    def overstock(self):
        """Get overstocked items"""
        return self.filter(
            quantity_on_hand__gte=F('maximum_stock_level')
        ).exclude(maximum_stock_level=0)
    
    def negative_stock(self):
        """Get items with negative stock"""
        return self.filter(quantity_on_hand__lt=0)
    
    def by_abc_classification(self, classification):
        """Filter by ABC classification"""
        return self.filter(abc_classification=classification)
    
    def fast_moving(self, days=30):
        """Get fast moving items"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.annotate(
            movement_count=Count(
                'stockmovementitem',
                filter=Q(stockmovementitem__movement__created_at__gte=cutoff_date)
            )
        ).filter(movement_count__gte=10)  # Configurable threshold
    
    def slow_moving(self, days=90):
        """Get slow moving items"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.annotate(
            movement_count=Count(
                'stockmovementitem',
                filter=Q(stockmovementitem__movement__created_at__gte=cutoff_date)
            )
        ).filter(movement_count__lte=2)
    
    def dead_stock(self, days=180):
        """Get dead stock items"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(
            Q(last_movement_date__lt=cutoff_date) | Q(last_movement_date__isnull=True),
            quantity_on_hand__gt=0
        )
    
    def with_valuation(self):
        """Annotate with stock valuation"""
        return self.annotate(
            total_value=F('quantity_on_hand') * F('unit_cost'),
            available_value=(F('quantity_on_hand') - F('quantity_reserved')) * F('unit_cost')
        )
    
    def expiring_soon(self, days=30):
        """Get items expiring soon"""
        cutoff_date = timezone.now() + timezone.timedelta(days=days)
        return self.filter(
            batch__expiry_date__lte=cutoff_date,
            batch__expiry_date__isnull=False
        ).distinct()

class StockManager(TenantAwareManager):
    """
    Manager for stock-related models
    """
    
    def get_queryset(self):
        return StockQuerySet(self.model, using=self._db)
    
    def with_quantities(self):
        return self.get_queryset().with_quantities()
    
    def low_stock(self):
        return self.get_queryset().low_stock()
    
    def out_of_stock(self):
        return self.get_queryset().out_of_stock()
    
    def overstock(self):
        return self.get_queryset().overstock()
    
    def negative_stock(self):
        return self.get_queryset().negative_stock()
    
    def by_abc_classification(self, classification):
        return self.get_queryset().by_abc_classification(classification)
    
    def fast_moving(self, days=30):
        return self.get_queryset().fast_moving(days)
    
    def slow_moving(self, days=90):
        return self.get_queryset().slow_moving(days)
    
    def dead_stock(self, days=180):
        return self.get_queryset().dead_stock(days)
    
    def with_valuation(self):
        return self.get_queryset().with_valuation()
    
    def expiring_soon(self, days=30):
        return self.get_queryset().expiring_soon(days)
    
    def get_stock_summary(self, tenant, warehouse=None):
        """Get comprehensive stock summary"""
        queryset = self.for_tenant(tenant).with_quantities().with_valuation()
        
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        
        return queryset.aggregate(
            total_items=Count('id'),
            total_quantity=Sum('quantity_on_hand'),
            total_available=Sum('available_quantity'),
            total_reserved=Sum('quantity_reserved'),
            total_value=Sum('total_value'),
            low_stock_items=Count('id', filter=Q(quantity_on_hand__lte=F('reorder_level'))),
            out_of_stock_items=Count('id', filter=Q(quantity_on_hand=0)),
            negative_stock_items=Count('id', filter=Q(quantity_on_hand__lt=0))
        )

class StockItemManager(StockManager):
    """
    Specialized manager for StockItem model
    """
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'warehouse', 'location', 'tenant'
        ).prefetch_related('batches')
    
    def for_product(self, product):
        """Get stock items for a specific product"""
        return self.filter(product=product)
    
    def for_warehouse(self, warehouse):
        """Get stock items for a specific warehouse"""
        return self.filter(warehouse=warehouse)
    
    def for_location(self, location):
        """Get stock items for a specific location"""
        return self.filter(location=location)
    
    def with_movements(self, days=30):
        """Get stock items with recent movements"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.prefetch_related(
            models.Prefetch(
                'stockmovementitem_set',
                queryset=models.get_model('inventory.StockMovementItem').objects.filter(
                    movement__created_at__gte=cutoff_date
                ).select_related('movement')
            )
        )
    
    def calculate_abc_classification(self, tenant):
        """Calculate ABC classification for stock items"""
        from django.db import transaction
        
        # Get items with their total value ordered by value
        items_with_value = list(
            self.for_tenant(tenant)
            .with_valuation()
            .filter(total_value__gt=0)
            .order_by('-total_value')
            .values('id', 'total_value')
        )
        
        if not items_with_value:
            return
        
        total_value = sum(item['total_value'] for item in items_with_value)
        cumulative_value = 0
        
        with transaction.atomic():
            for item in items_with_value:
                cumulative_value += item['total_value']
                cumulative_percentage = (cumulative_value / total_value) * 100
                
                if cumulative_percentage <= 80:
                    classification = 'A'
                elif cumulative_percentage <= 95:
                    classification = 'B'
                else:
                    classification = 'C'
                
                self.filter(id=item['id']).update(abc_classification=classification)

class StockMovementManager(TenantAwareManager):
    """
    Manager for StockMovement model
    """
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'warehouse', 'created_by', 'tenant'
        ).prefetch_related('items__stock_item__product')
    
    def by_movement_type(self, movement_type):
        """Filter by movement type"""
        return self.filter(movement_type=movement_type)
    
    def by_status(self, status):
        """Filter by status"""
        return self.filter(status=status)
    
    def in_date_range(self, start_date, end_date):
        """Filter by date range"""
        return self.filter(created_at__range=[start_date, end_date])
    
    def pending_approval(self):
        """Get movements pending approval"""
        return self.filter(status='PENDING_APPROVAL')
    
    def completed(self):
        """Get completed movements"""
        return self.filter(status='COMPLETED')
    
    def with_quantities(self):
        """Annotate with total quantities"""
        return self.annotate(
            total_quantity=Sum('items__quantity'),
            total_value=Sum(F('items__quantity') * F('items__unit_cost'))
        )
    
    def get_movement_summary(self, tenant, start_date=None, end_date=None):
        """Get movement summary for a period"""
        queryset = self.for_tenant(tenant)
        
        if start_date and end_date:
            queryset = queryset.in_date_range(start_date, end_date)
        
        return queryset.values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('items__quantity'),
            total_value=Sum(F('items__quantity') * F('items__unit_cost'))
        ).order_by('movement_type')
    
    def create_movement(self, tenant, movement_type, warehouse, items_data, **kwargs):
        """Create a stock movement with items"""
        from django.db import transaction
        from ..models import StockMovement, StockMovementItem
        
        with transaction.atomic():
            # Create the movement
            movement = self.create(
                tenant=tenant,
                movement_type=movement_type,
                warehouse=warehouse,
                **kwargs
            )
            
            # Create
                movement_item = StockMovementItem(
                    movement=movement,
                    **item_data
                )
                movement_items.append(movement_item)
            
            StockMovementItem.objects.bulk_create(movement_items)
            
            # Update movement total
            movement.calculate_totals()
            
            return movement