"""
Inventory Cost Layer and COGS Models
Advanced inventory costing with FIFO, LIFO, and Weighted Average support
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel
from .currency import Currency


class InventoryCostLayer(TenantBaseModel):
    """Enhanced inventory cost layers for accurate COGS calculation"""
    
    COST_LAYER_TYPES = [
        ('PURCHASE', 'Purchase'),
        ('PRODUCTION', 'Production'),
        ('ADJUSTMENT', 'Adjustment'),
        ('OPENING_BALANCE', 'Opening Balance'),
        ('TRANSFER_IN', 'Transfer In'),
        ('LANDED_COST', 'Landed Cost'),
        ('RETURN', 'Return'),
    ]
    
    # Product & Location
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        related_name='cost_layers'
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        related_name='cost_layers'
    )
    
    # Cost Information
    layer_type = models.CharField(max_length=20, choices=COST_LAYER_TYPES)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Multi-Currency Support
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    base_currency_unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    base_currency_total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Source Information
    source_document_type = models.CharField(max_length=50)
    source_document_id = models.IntegerField()
    source_document_number = models.CharField(max_length=100, blank=True)
    
    # Dates
    acquisition_date = models.DateField()
    created_date = models.DateTimeField(auto_now_add=True)
    
    # Status
    quantity_remaining = models.DecimalField(max_digits=15, decimal_places=4)
    is_fully_consumed = models.BooleanField(default=False)
    
    # Landed Costs
    landed_cost_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    allocated_landed_costs = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Journal Entry Reference
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Batch/Lot Information
    batch_number = models.CharField(max_length=100, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Quality Information
    quality_grade = models.CharField(max_length=50, blank=True)
    condition = models.CharField(
        max_length=20,
        choices=[
            ('NEW', 'New'),
            ('USED', 'Used'),
            ('REFURBISHED', 'Refurbished'),
            ('DAMAGED', 'Damaged'),
        ],
        default='NEW'
    )
    
    class Meta:
        ordering = ['acquisition_date', 'created_date']  # FIFO by default
        db_table = 'finance_inventory_cost_layers'
        indexes = [
            models.Index(fields=['tenant', 'product', 'warehouse', 'is_fully_consumed']),
            models.Index(fields=['tenant', 'acquisition_date']),
            models.Index(fields=['tenant', 'source_document_type', 'source_document_id']),
            models.Index(fields=['tenant', 'batch_number']),
            models.Index(fields=['tenant', 'lot_number']),
        ]
        
    def __str__(self):
        return f"{self.product.name} - {self.quantity} @ {self.unit_cost} ({self.warehouse.name})"
    
    def save(self, *args, **kwargs):
        # Calculate totals
        self.total_cost = self.quantity * self.unit_cost
        self.base_currency_total_cost = self.base_currency_unit_cost * self.quantity
        
        # Initialize quantity remaining
        if not self.pk:  # New record
            self.quantity_remaining = self.quantity
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate cost layer"""
        if self.quantity <= 0:
            raise ValidationError('Quantity must be positive')
        
        if self.unit_cost < 0:
            raise ValidationError('Unit cost cannot be negative')
        
        if self.quantity_remaining > self.quantity:
            raise ValidationError('Remaining quantity cannot exceed original quantity')
        
        if self.expiry_date and self.expiry_date <= date.today():
            # Warning, but not error for expired items
            pass
    
    def consume_quantity(self, quantity_consumed, cogs_journal_entry=None, consumption_date=None):
        """Consume quantity from this cost layer"""
        if quantity_consumed > self.quantity_remaining:
            raise ValidationError(f'Cannot consume {quantity_consumed}. Only {self.quantity_remaining} remaining.')
        
        if quantity_consumed <= 0:
            raise ValidationError('Consumption quantity must be positive')
        
        # Calculate cost for consumed quantity
        consumed_cost = (quantity_consumed / self.quantity) * self.base_currency_total_cost
        
        # Update remaining quantity
        self.quantity_remaining -= quantity_consumed
        if self.quantity_remaining <= Decimal('0.0001'):  # Essentially zero
            self.is_fully_consumed = True
        
        self.save()
        
        # Create cost consumption record
        consumption = InventoryCostConsumption.objects.create(
            tenant=self.tenant,
            cost_layer=self,
            quantity_consumed=quantity_consumed,
            unit_cost=self.base_currency_unit_cost,
            total_cost=consumed_cost,
            consumption_date=consumption_date or date.today(),
            cogs_journal_entry=cogs_journal_entry
        )
        
        return consumed_cost, consumption
    
    @property
    def effective_unit_cost(self):
        """Unit cost including allocated landed costs"""
        if self.quantity > 0:
            return (self.base_currency_total_cost + self.allocated_landed_costs) / self.quantity
        return self.base_currency_unit_cost
    
    @property
    def percentage_consumed(self):
        """Percentage of layer that has been consumed"""
        if self.quantity > 0:
            consumed = self.quantity - self.quantity_remaining
            return (consumed / self.quantity) * 100
        return Decimal('0.00')
    
    @property
    def days_in_inventory(self):
        """Days this inventory has been in stock"""
        return (date.today() - self.acquisition_date).days
    
    def allocate_landed_cost(self, amount):
        """Allocate landed cost to this layer"""
        self.allocated_landed_costs += amount
        self.save(update_fields=['allocated_landed_costs'])


class InventoryCostConsumption(TenantBaseModel):
    """Track consumption of inventory cost layers"""
    
    cost_layer = models.ForeignKey(
        InventoryCostLayer,
        on_delete=models.CASCADE,
        related_name='consumptions'
    )
    quantity_consumed = models.DecimalField(max_digits=15, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    consumption_date = models.DateField()
    
    # Source of consumption
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.IntegerField(null=True, blank=True)
    
    # COGS Journal Entry
    cogs_journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Additional tracking
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    invoice = models.ForeignKey(
        'finance.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-consumption_date']
        db_table = 'finance_inventory_cost_consumptions'
        
    def __str__(self):
        return f"Consumption: {self.quantity_consumed} @ {self.unit_cost}"


class LandedCost(TenantBaseModel):
    """Landed costs allocation for inventory"""
    
    ALLOCATION_METHODS = [
        ('QUANTITY', 'By Quantity'),
        ('WEIGHT', 'By Weight'),
        ('VALUE', 'By Value'),
        ('VOLUME', 'By Volume'),
        ('MANUAL', 'Manual Allocation'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_ALLOCATION', 'Pending Allocation'),
        ('ALLOCATED', 'Allocated'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Basic Information
    reference_number = models.CharField(max_length=50)
    description = models.TextField()
    total_landed_cost = models.DecimalField(max_digits=15, decimal_places=2)
    allocation_method = models.CharField(max_length=20, choices=ALLOCATION_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Source Document
    source_document_type = models.CharField(max_length=50)
    source_document_id = models.IntegerField()
    source_purchase_order = models.ForeignKey(
        'inventory.PurchaseOrder',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Cost Categories
    freight_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    insurance_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    duty_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    handling_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    other_costs = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Currency
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    
    # Status
    is_allocated = models.BooleanField(default=False)
    allocated_date = models.DateTimeField(null=True, blank=True)
    allocated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Vendor Information
    vendor = models.ForeignKey(
        'finance.Vendor',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'finance_landed_costs'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'reference_number'],
                name='unique_tenant_landed_cost_ref'
            ),
        ]
        
    def __str__(self):
        return f"{self.reference_number} - {self.total_landed_cost}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            from apps.core.utils import generate_code
            self.reference_number = generate_code('LC', self.tenant_id)
        
        # Calculate total from components
        self.total_landed_cost = (
            self.freight_cost + self.insurance_cost + self.duty_cost +
            self.handling_cost + self.other_costs
        )
        
        super().save(*args, **kwargs)
    
    def allocate_to_products(self):
        """Allocate landed costs to products"""
        from ..services.landed_cost import LandedCostService
        
        service = LandedCostService(self.tenant)
        return service.allocate_landed_costs(self)
    
    def get_allocation_base_value(self, cost_layer):
        """Get the base value for allocation calculation"""
        if self.allocation_method == 'QUANTITY':
            return cost_layer.quantity
        elif self.allocation_method == 'WEIGHT':
            return cost_layer.product.weight * cost_layer.quantity if cost_layer.product.weight else Decimal('0.00')
        elif self.allocation_method == 'VALUE':
            return cost_layer.base_currency_total_cost
        elif self.allocation_method == 'VOLUME':
            volume = (cost_layer.product.length or 0) * (cost_layer.product.width or 0) * (cost_layer.product.height or 0)
            return Decimal(str(volume)) * cost_layer.quantity if volume else Decimal('0.00')
        else:
            return Decimal('1.00')  # Manual allocation


class LandedCostAllocation(TenantBaseModel):
    """Individual allocations of landed costs to products"""
    
    landed_cost = models.ForeignKey(
        LandedCost,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    cost_layer = models.ForeignKey(
        InventoryCostLayer,
        on_delete=models.CASCADE,
        related_name='landed_cost_allocations'
    )
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    allocation_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Cost category breakdown
    freight_allocation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    insurance_allocation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    duty_allocation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    handling_allocation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    other_allocation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Base values used for allocation
    allocation_base_value = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0.0000'))
    
    class Meta:
        ordering = ['landed_cost', 'cost_layer']
        db_table = 'finance_landed_cost_allocations'
        constraints = [
            models.UniqueConstraint(
                fields=['landed_cost', 'cost_layer'],
                name='unique_landed_cost_layer'
            ),
        ]
        
    def __str__(self):
        return f"{self.landed_cost.reference_number} -> {self.cost_layer.product.name}: {self.allocated_amount}"
    
    def save(self, *args, **kwargs):
        # Calculate total allocation from components
        self.allocated_amount = (
            self.freight_allocation + self.insurance_allocation + 
            self.duty_allocation + self.handling_allocation + self.other_allocation
        )
        
        super().save(*args, **kwargs)
        
        # Update cost layer with allocated amount
        self.cost_layer.allocate_landed_cost(self.allocated_amount)


class InventoryValuation(TenantBaseModel):
    """Periodic inventory valuation snapshots"""
    
    VALUATION_METHODS = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('WEIGHTED_AVERAGE', 'Weighted Average'),
        ('STANDARD_COST', 'Standard Cost'),
        ('SPECIFIC_ID', 'Specific Identification'),
    ]
    
    valuation_date = models.DateField()
    valuation_method = models.CharField(max_length=20, choices=VALUATION_METHODS)
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Totals
    total_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0.0000'))
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    average_cost = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0.0000'))
    
    # Status
    is_finalized = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-valuation_date']
        db_table = 'finance_inventory_valuations'
        
    def __str__(self):
        warehouse_name = self.warehouse.name if self.warehouse else 'All Warehouses'
        return f"Valuation {self.valuation_date} - {warehouse_name}"
    
    def calculate_valuation(self):
        """Calculate inventory valuation"""
        from ..services.inventory_costing import InventoryValuationService
        
        service = InventoryValuationService(self.tenant)
        return service.calculate_valuation(self)


class InventoryValuationItem(TenantBaseModel):
    """Individual product valuations within a valuation"""
    
    valuation = models.ForeignKey(
        InventoryValuation,
        on_delete=models.CASCADE,
        related_name='valuation_items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Quantities
    quantity_on_hand = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_available = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_committed = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0.0000'))
    
    # Costs
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Market values for LCM calculation
    market_value_per_unit = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    net_realizable_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Lower of Cost or Market adjustment
    lcm_adjustment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    adjusted_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    class Meta:
        ordering = ['valuation', 'product__name']
        db_table = 'finance_inventory_valuation_items'
        constraints = [
            models.UniqueConstraint(
                fields=['valuation', 'product', 'warehouse'],
                name='unique_valuation_product_warehouse'
            ),
        ]
        
    def __str__(self):
        return f"{self.valuation} - {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_on_hand * self.unit_cost
        
        # Calculate LCM adjustment
        if self.market_value_per_unit:
            market_total = self.quantity_on_hand * self.market_value_per_unit
            if market_total < self.total_cost:
                self.lcm_adjustment = self.total_cost - market_total
            else:
                self.lcm_adjustment = Decimal('0.00')
        
        # Calculate adjusted value
        self.adjusted_value = self.total_cost - self.lcm_adjustment
        
        super().save(*args, **kwargs)