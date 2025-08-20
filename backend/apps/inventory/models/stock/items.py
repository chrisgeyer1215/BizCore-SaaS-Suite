"""
Stock item management with comprehensive tracking
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from ..abstract.base import SoftDeleteMixin, TenantBaseModel, ActivatableMixin
from ...managers.base import InventoryManager
from ...managers.stock import StockItemManager

User = get_user_model()


class StockItem(TenantBaseModel, ActivatableMixin, SoftDeleteMixin):
    """
    Enhanced stock item management with comprehensive tracking and analytics
    """
    
    ABC_CLASSIFICATIONS = [
        ('A', 'Class A - High Value'),
        ('B', 'Class B - Medium Value'),
        ('C', 'Class C - Low Value'),
    ]
    
    XYZ_CLASSIFICATIONS = [
        ('X', 'Class X - Stable Demand'),
        ('Y', 'Class Y - Variable Demand'),
        ('Z', 'Class Z - Irregular Demand'),
    ]
    
    # Product & Location References
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    variation = models.ForeignKey(
        'catalog.ProductVariation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='stock_items'
    )
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_items'
    )
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_items'
    )
    
    # Quantity Tracking - Core quantities
    quantity_on_hand = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Physical quantity in location"
    )
    quantity_available = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Available for allocation (on_hand - reserved - allocated)"
    )
    quantity_reserved = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Reserved for orders but not yet allocated"
    )
    quantity_allocated = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Allocated to specific orders/shipments"
    )
    
    # Quantity Tracking - Pipeline quantities
    quantity_incoming = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Expected incoming quantity from POs"
    )
    quantity_on_order = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Total quantity on purchase orders"
    )
    quantity_picked = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Picked but not yet shipped"
    )
    quantity_shipped = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Shipped in current period"
    )
    quantity_in_transit = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="In transit between locations"
    )
    
    # Valuation & Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    standard_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fifo_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # ABC/XYZ Classification
    abc_classification = models.CharField(
        max_length=1, choices=ABC_CLASSIFICATIONS, blank=True
    )
    xyz_classification = models.CharField(
        max_length=1, choices=XYZ_CLASSIFICATIONS, blank=True
    )
    
    # Cycle Counting
    last_counted_date = models.DateTimeField(null=True, blank=True)
    last_counted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='counted_stock_items'
    )
    cycle_count_frequency_days = models.IntegerField(default=90)
    next_count_due = models.DateField(null=True, blank=True)
    variance_tolerance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=5
    )
    count_variance_history = models.JSONField(default=list, blank=True)
    
    # Movement Tracking
    last_movement_date = models.DateTimeField(null=True, blank=True)
    last_movement_type = models.CharField(max_length=20, blank=True)
    total_movements_count = models.IntegerField(default=0)
    last_receipt_date = models.DateTimeField(null=True, blank=True)
    last_shipment_date = models.DateTimeField(null=True, blank=True)
    
    # Performance Metrics
    turnover_rate = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    days_on_hand = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    velocity_score = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    stockout_count = models.IntegerField(default=0)
    last_stockout_date = models.DateTimeField(null=True, blank=True)
    stockout_duration_hours = models.IntegerField(default=0)
    
    # Demand Analytics
    demand_variance = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    forecast_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    seasonality_factor = models.DecimalField(max_digits=5, decimal_places=3, default=1.000)
    
    # Status & Flags
    is_quarantined = models.BooleanField(default=False)
    is_consignment = models.BooleanField(default=False)
    is_dropship = models.BooleanField(default=False)
    is_obsolete = models.BooleanField(default=False)
    is_dead_stock = models.BooleanField(default=False)
    
    # Special Handling
    requires_special_handling = models.BooleanField(default=False)
    handling_instructions = models.TextField(blank=True)
    storage_temperature_min = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    storage_temperature_max = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    storage_humidity_max = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Quality Control
    quality_hold = models.BooleanField(default=False)
    quality_hold_reason = models.TextField(blank=True)
    quality_hold_date = models.DateTimeField(null=True, blank=True)
    inspection_required = models.BooleanField(default=False)
    last_inspection_date = models.DateTimeField(null=True, blank=True)
    
    # Integration & External Systems
    external_system_id = models.CharField(max_length=100, blank=True)
    external_system_name = models.CharField(max_length=50, blank=True)
    last_sync_date = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, default='SYNCED')
    
    # Historical Data (for performance)
    monthly_consumption = models.JSONField(default=dict, blank=True)
    quarterly_metrics = models.JSONField(default=dict, blank=True)
    
    # Notes & Custom Data
    notes = models.TextField(blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    objects = InventoryManager()
    objects = StockItemManager()
    class Meta:
        db_table = 'inventory_stock_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'variation', 'warehouse', 'location', 'batch'],
                name='unique_stock_item_location'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'product', 'warehouse']),
            models.Index(fields=['tenant_id', 'warehouse', 'quantity_available']),
            models.Index(fields=['tenant_id', 'abc_classification']),
            models.Index(fields=['tenant_id', 'next_count_due']),
            models.Index(fields=['tenant_id', 'is_quarantined']),
            models.Index(fields=['tenant_id', 'is_active', 'quantity_on_hand']),
            models.Index(fields=['tenant_id', 'last_movement_date']),
        ]
    
    def __str__(self):
        product_name = f"{self.product.sku}"
        if self.variation:
            product_name += f"-{self.variation.variation_code}"
        return f"{product_name} @ {self.warehouse.code}: {self.quantity_available}"
    
    # ========================================================================
    # STOCK RESERVATION METHODS
    # ========================================================================
    
    def reserve_stock(self, quantity, reason='', reference_id=None):
        """Reserve stock for orders with validation"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_available < quantity:
            return False, f"Insufficient stock. Available: {self.quantity_available}"
        
        # Perform reservation
        self.quantity_reserved += quantity
        self.quantity_available -= quantity
        
        self.save(update_fields=['quantity_reserved', 'quantity_available'])
        
        # Log the reservation
        self._create_movement('RESERVE', quantity, reason, reference_id=reference_id)
        return True, "Stock reserved successfully"
    
    def release_reservation(self, quantity, reason='', reference_id=None):
        """Release reserved stock"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_reserved < quantity:
            return False, f"Cannot release more than reserved. Reserved: {self.quantity_reserved}"
        
        # Release reservation
        self.quantity_reserved -= quantity
        self.quantity_available += quantity
        
        self.save(update_fields=['quantity_reserved', 'quantity_available'])
        
        # Log the release
        self._create_movement('RELEASE', quantity, reason, reference_id=reference_id)
        return True, "Reservation released successfully"
    
    def allocate_stock(self, quantity, reason='', reference_id=None):
        """Allocate reserved stock for picking/shipping"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_reserved < quantity:
            return False, f"Insufficient reserved stock. Reserved: {self.quantity_reserved}"
        
        # Allocate stock
        self.quantity_reserved -= quantity
        self.quantity_allocated += quantity
        
        self.save(update_fields=['quantity_reserved', 'quantity_allocated'])
        
        # Log the allocation
        self._create_movement('ALLOCATE', quantity, reason, reference_id=reference_id)
        return True, "Stock allocated successfully"
    
    # ========================================================================
    # STOCK MOVEMENT METHODS
    # ========================================================================
    
    def pick_stock(self, quantity, reason='', reference_id=None, user=None):
        """Pick allocated stock for shipping"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_allocated < quantity:
            return False, f"Insufficient allocated stock. Allocated: {self.quantity_allocated}"
        
        # Pick stock
        self.quantity_allocated -= quantity
        self.quantity_picked += quantity
        
        self.save(update_fields=['quantity_allocated', 'quantity_picked'])
        
        # Log the pick
        self._create_movement('PICK', quantity, reason, reference_id=reference_id, user=user)
        return True, "Stock picked successfully"
    
    def ship_stock(self, quantity, reason='', reference_id=None, user=None):
        """Ship picked stock (final step)"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_picked < quantity:
            return False, f"Insufficient picked stock. Picked: {self.quantity_picked}"
        
        # Ship stock
        self.quantity_picked -= quantity
        self.quantity_shipped += quantity
        self.quantity_on_hand -= quantity
        
        # Update last shipment
        self.last_shipment_date = timezone.now()
        self.last_movement_date = timezone.now()
        self.last_movement_type = 'SHIP'
        
        self.save(update_fields=[
            'quantity_picked', 'quantity_shipped', 'quantity_on_hand',
            'last_shipment_date', 'last_movement_date', 'last_movement_type'
        ])
        
        # Log the shipment
        self._create_movement('SHIP', quantity, reason, reference_id=reference_id, user=user)
        
        # Update total value
        self.update_total_value()
        
        return True, "Stock shipped successfully"
    
    def receive_stock(self, quantity, unit_cost=None, reason='', reference_id=None, user=None):
        """Receive new stock into inventory"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        # Update quantities
        old_quantity = self.quantity_on_hand
        self.quantity_on_hand += quantity
        self.quantity_available += quantity
        
        # Update costs if provided
        if unit_cost:
            unit_cost = Decimal(str(unit_cost))
            self.update_average_cost(quantity, unit_cost)
            self.last_cost = unit_cost
        
        # Update timestamps
        self.last_receipt_date = timezone.now()
        self.last_movement_date = timezone.now()
        self.last_movement_type = 'RECEIVE'
        
        self.save(update_fields=[
            'quantity_on_hand', 'quantity_available', 'average_cost', 'last_cost',
            'total_value', 'last_receipt_date', 'last_movement_date', 'last_movement_type'
        ])
        
        # Log the receipt
        self._create_movement('RECEIVE', quantity, reason, unit_cost, reference_id, user)
        
        return True, "Stock received successfully"
    
    def adjust_stock(self, new_quantity, reason='', reference_id=None, user=None):
        """Adjust stock to specific quantity (for cycle counts, corrections)"""
        new_quantity = Decimal(str(new_quantity))
        old_quantity = self.quantity_on_hand
        adjustment = new_quantity - old_quantity
        
        if adjustment == 0:
            return True, "No adjustment needed"
        
        # Update quantities
        self.quantity_on_hand = new_quantity
        
        # Recalculate available (ensure it's not negative)
        reserved_allocated = self.quantity_reserved + self.quantity_allocated
        self.quantity_available = max(Decimal('0'), new_quantity - reserved_allocated)
        
        # Update tracking
        self.last_movement_date = timezone.now()
        self.last_movement_type = 'ADJUST_IN' if adjustment > 0 else 'ADJUST_OUT'
        
        self.save(update_fields=[
            'quantity_on_hand', 'quantity_available', 'total_value',
            'last_movement_date', 'last_movement_type'
        ])
        
        # Log the adjustment
        movement_type = 'ADJUST_IN' if adjustment > 0 else 'ADJUST_OUT'
        self._create_movement(movement_type, abs(adjustment), reason, reference_id=reference_id, user=user)
        
        # Update total value
        self.update_total_value()
        
        return True, f"Stock adjusted by {adjustment}"
    
    # ========================================================================
    # COST CALCULATION METHODS
    # ========================================================================
    
    def update_average_cost(self, new_quantity, new_cost):
        """Update average cost using weighted average method"""
        old_value = self.quantity_on_hand * self.average_cost
        new_value = new_quantity * new_cost
        total_value = old_value + new_value
        total_quantity = self.quantity_on_hand + new_quantity
        
        if total_quantity > 0:
            self.average_cost = (total_value / total_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        self.update_total_value()
    
    def update_total_value(self):
        """Update total inventory value"""
        self.total_value = self.quantity_on_hand * self.average_cost
        self.save(update_fields=['total_value'])
    
    def calculate_fifo_cost(self):
        """Calculate FIFO cost based on valuation layers"""
        # This would integrate with StockValuationLayer model
        # Implementation depends on valuation layer tracking
        return self.fifo_cost
    
    # ========================================================================
    # ANALYTICS & PERFORMANCE METHODS
    # ========================================================================
    
    def calculate_turnover_rate(self, days=365):
        """Calculate inventory turnover rate"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get total outbound movements in the period
        from .movements import StockMovement
        
        outbound_quantity = StockMovement.objects.filter(
            stock_item=self,
            tenant_id=self.tenant_id,
            movement_date__gte=start_date,
            movement_date__lte=end_date,
            movement_type__in=['SHIP', 'SALE', 'TRANSFER_OUT']
        ).aggregate(models.Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        # Calculate average inventory
        average_inventory = (self.quantity_on_hand + outbound_quantity) / 2
        
        if average_inventory > 0:
            self.turnover_rate = outbound_quantity / average_inventory * (365 / days)
            self.days_on_hand = 365 / self.turnover_rate if self.turnover_rate > 0 else 0
        else:
            self.turnover_rate = 0
            self.days_on_hand = 0
        
        self.save(update_fields=['turnover_rate', 'days_on_hand'])
    
    def calculate_velocity_score(self):
        """Calculate velocity score based on movement frequency and volume"""
        # Implementation depends on business requirements
        # Could factor in: frequency, volume, value, seasonality
        pass
    
    def update_abc_classification(self):
        """Update ABC classification based on value and movement"""
        # This would typically be done at a batch level for all products
        # Based on annual usage value (quantity * cost)
        pass
    
    def update_xyz_classification(self):
        """Update XYZ classification based on demand variability"""
        # Based on coefficient of variation of demand
        pass
    
    # ========================================================================
    # PROPERTY METHODS
    # ========================================================================
    
    @property
    def is_low_stock(self):
        """Check if item is below reorder point"""
        reorder_point = self.product.reorder_point
        if self.variation and self.variation.reorder_point:
            reorder_point = self.variation.reorder_point
        return self.quantity_available <= reorder_point
    
    @property
    def is_out_of_stock(self):
        """Check if item is out of stock"""
        return self.quantity_available <= 0
    
    @property
    def stock_coverage_days(self):
        """Calculate days of stock coverage based on consumption"""
        if self.turnover_rate > 0 and self.quantity_available > 0:
            daily_consumption = self.turnover_rate / 365
            return (self.quantity_available / daily_consumption).quantize(Decimal('0.1'))
        return Decimal('0')
    
    @property
    def total_committed(self):
        """Total committed stock (reserved + allocated + picked)"""
        return self.quantity_reserved + self.quantity_allocated + self.quantity_picked
    
    @property
    def stock_efficiency_ratio(self):
        """Efficiency ratio (available / on_hand)"""
        if self.quantity_on_hand > 0:
            return (self.quantity_available / self.quantity_on_hand * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _create_movement(self, movement_type, quantity, reason='', unit_cost=None, 
                        reference_id=None, user=None):
        """Create a stock movement record"""
        from .movements import StockMovement
        
        return StockMovement.objects.create(
            tenant_id=self.tenant_id,
            stock_item=self,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost or self.average_cost,
            total_cost=(quantity * (unit_cost or self.average_cost)),
            reason=reason,
            performed_by=user,
            stock_before=self.quantity_on_hand,
            stock_after=self.quantity_on_hand,  # Will be updated by calling method
            reference_id=reference_id,
            notes=reason
        )
    
    def recalculate_all_quantities(self):
        """Recalculate all quantities based on movements (for data integrity)"""
        # This would recalculate quantities from movement history
        # Useful for data integrity checks and corrections
        pass
    
    def get_movement_history(self, days=30):
        """Get recent movement history"""
        from .movements import StockMovement
        
        start_date = timezone.now() - timedelta(days=days)
        return StockMovement.objects.filter(
            stock_item=self,
            tenant_id=self.tenant_id,
            movement_date__gte=start_date
        ).order_by('-movement_date')
    
    def schedule_cycle_count(self):
        """Schedule next cycle count based on ABC classification and frequency"""
        frequency_map = {
            'A': 30,   # Class A items counted monthly
            'B': 90,   # Class B items counted quarterly
            'C': 365,  # Class C items counted annually
        }
        
        frequency = frequency_map.get(self.abc_classification, self.cycle_count_frequency_days)
        self.next_count_due = timezone.now().date() + timedelta(days=frequency)
        self.save(update_fields=['next_count_due'])
