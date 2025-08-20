"""
Stock location management within warehouses
"""
from django.db import models
from decimal import Decimal

from ..abstract.base import TenantBaseModel, ActivatableMixin
from ...managers.base import InventoryManager


class StockLocation(TenantBaseModel, ActivatableMixin):
    """
    Detailed location tracking within warehouses
    """
    
    LOCATION_TYPES = [
        ('RECEIVING', 'Receiving Area'),
        ('STORAGE', 'Storage Area'),
        ('PICKING', 'Picking Area'),
        ('PACKING', 'Packing Area'),
        ('SHIPPING', 'Shipping Area'),
        ('QUARANTINE', 'Quarantine Area'),
        ('RETURNS', 'Returns Area'),
        ('QUALITY_CONTROL', 'Quality Control'),
        ('STAGING', 'Staging Area'),
        ('CROSS_DOCK', 'Cross Dock'),
    ]
    
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='locations'
    )
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='STORAGE')
    
    # Physical Layout - Hierarchical addressing system
    zone = models.CharField(max_length=10, blank=True)
    aisle = models.CharField(max_length=10, blank=True)
    rack = models.CharField(max_length=10, blank=True)
    shelf = models.CharField(max_length=10, blank=True)
    bin = models.CharField(max_length=10, blank=True)
    level = models.CharField(max_length=10, blank=True)
    
    # Capacity & Physical Constraints
    max_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    
    # Environment & Special Requirements
    temperature_controlled = models.BooleanField(default=False)
    humidity_controlled = models.BooleanField(default=False)
    hazmat_approved = models.BooleanField(default=False)
    
    # Operational Settings
    is_pickable = models.BooleanField(default=True)
    is_receivable = models.BooleanField(default=True)
    is_countable = models.BooleanField(default=True)
    
    # Picking sequence for optimization
    pick_sequence = models.PositiveIntegerField(default=0)
    
    # Current utilization
    current_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    current_volume = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_locations'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'warehouse', 'code'], 
                name='unique_tenant_location_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'warehouse', 'is_active']),
            models.Index(fields=['tenant_id', 'warehouse', 'location_type']),
            models.Index(fields=['tenant_id', 'is_pickable', 'pick_sequence']),
            models.Index(fields=['tenant_id', 'zone', 'aisle', 'rack']),
        ]
        ordering = ['warehouse', 'pick_sequence', 'code']
    
    def __str__(self):
        parts = filter(None, [self.zone, self.aisle, self.rack, self.shelf, self.bin])
        location = '-'.join(parts) if parts else self.code
        return f"{self.warehouse.code}/{location}"
    
    @property
    def full_location_code(self):
        """Full location code including all components"""
        parts = filter(None, [self.zone, self.aisle, self.rack, self.shelf, self.bin, self.level])
        return '-'.join(parts) if parts else self.code
    
    @property
    def weight_utilization_percentage(self):
        """Weight capacity utilization percentage"""
        if self.max_weight and self.max_weight > 0:
            return (self.current_weight / self.max_weight * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def volume_utilization_percentage(self):
        """Volume capacity utilization percentage"""
        if self.max_volume and self.max_volume > 0:
            return (self.current_volume / self.max_volume * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_over_capacity(self):
        """Check if location is over capacity"""
        weight_over = self.max_weight and self.current_weight > self.max_weight
        volume_over = self.max_volume and self.current_volume > self.max_volume
        return weight_over or volume_over
    
    def can_accommodate(self, weight=None, volume=None):
        """Check if location can accommodate additional weight/volume"""
        if weight and self.max_weight:
            if self.current_weight + Decimal(str(weight)) > self.max_weight:
                return False
        
        if volume and self.max_volume:
            if self.current_volume + Decimal(str(volume)) > self.max_volume:
                return False
        
        return True
    
    def update_utilization(self):
        """Update current utilization based on stock items"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            location=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        
        total_weight = Decimal('0')
        total_volume = Decimal('0')
        
        for item in stock_items:
            if item.product.weight:
                total_weight += item.quantity_on_hand * item.product.weight
            if item.product.volume:
                total_volume += item.quantity_on_hand * item.product.volume
        
        self.current_weight = total_weight
        self.current_volume = total_volume
        self.save(update_fields=['current_weight', 'current_volume'])