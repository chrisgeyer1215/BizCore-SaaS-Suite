"""
Warehouse and storage facility management models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from decimal import Decimal

from ..abstract.base import TenantBaseModel, SoftDeleteMixin, ActivatableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class Warehouse(TenantBaseModel, SoftDeleteMixin, ActivatableMixin):
    """
    Comprehensive warehouse management with operational details
    """
    
    WAREHOUSE_TYPES = [
        ('PHYSICAL', 'Physical Warehouse'),
        ('VIRTUAL', 'Virtual/Drop-ship'),
        ('CONSIGNMENT', 'Consignment'),
        ('TRANSIT', 'In-Transit'),
        ('QUARANTINE', 'Quarantine'),
        ('RETURNED_GOODS', 'Returned Goods'),
        ('WORK_IN_PROGRESS', 'Work in Progress'),
    ]
    
    TEMPERATURE_ZONES = [
        ('AMBIENT', 'Ambient Temperature'),
        ('REFRIGERATED', 'Refrigerated (2-8°C)'),
        ('FROZEN', 'Frozen (-18°C)'),
        ('CONTROLLED', 'Temperature Controlled'),
        ('HAZMAT', 'Hazardous Materials'),
    ]
    
    SECURITY_LEVELS = [
        ('BASIC', 'Basic'),
        ('STANDARD', 'Standard'),
        ('HIGH', 'High Security'),
        ('MAXIMUM', 'Maximum Security'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='PHYSICAL')
    
    # Address & Location
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # GPS Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Contact Information
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_warehouses'
    )
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Operational Details
    is_default = models.BooleanField(default=False)
    is_sellable = models.BooleanField(default=True)
    allow_negative_stock = models.BooleanField(default=False)
    
    # Capacity & Physical Properties
    total_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    storage_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='warehouse_areas'
    )
    max_capacity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_occupancy_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Temperature & Environment
    temperature_zone = models.CharField(max_length=20, choices=TEMPERATURE_ZONES, default='AMBIENT')
    min_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    humidity_controlled = models.BooleanField(default=False)
    
    # Security & Compliance
    security_level = models.CharField(max_length=20, choices=SECURITY_LEVELS, default='STANDARD')
    cctv_enabled = models.BooleanField(default=False)
    access_control_enabled = models.BooleanField(default=False)
    fire_suppression_system = models.BooleanField(default=False)
    
    # Operating Schedule
    operating_hours = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Cost Centers
    rent_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    utility_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labor_cost_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_costs_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Integration
    wms_system = models.CharField(max_length=50, blank=True)  # Warehouse Management System
    wms_integration_enabled = models.BooleanField(default=False)
    
    # Notes & Description
    description = models.TextField(blank=True)
    special_handling_instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_warehouses'
        ordering = ['-is_default', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'code'], 
                name='unique_tenant_warehouse_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'code']),
            models.Index(fields=['tenant_id', 'is_active', 'is_default']),
            models.Index(fields=['tenant_id', 'warehouse_type']),
            models.Index(fields=['tenant_id', 'is_sellable']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default warehouse per tenant
        if self.is_default:
            Warehouse.objects.filter(
                tenant_id=self.tenant_id,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def total_monthly_cost(self):
        """Total monthly operational cost"""
        return (
            self.rent_cost_per_month + 
            self.utility_cost_per_month + 
            self.labor_cost_per_month + 
            self.other_costs_per_month
        )
    
    @property
    def full_address(self):
        """Get formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}",
            self.country
        ]
        return ", ".join(filter(None, address_parts))
    
    def calculate_occupancy_percentage(self):
        """Calculate current occupancy percentage"""
        if not self.max_capacity:
            return Decimal('0')
        
        # This would be calculated based on current stock volume
        # Implementation depends on stock tracking requirements
        # For now, return current value
        return self.current_occupancy_percentage
    
    def get_total_stock_value(self):
        """Get total value of stock in this warehouse"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            warehouse=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        
        total_value = sum(item.total_value for item in stock_items)
        return total_value