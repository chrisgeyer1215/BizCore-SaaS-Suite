"""
Stock valuation layers for FIFO/LIFO cost tracking
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal

from ..abstract.base import TenantBaseModel, ActivatableMixin
from ...managers.base import InventoryManager


class StockValuationLayer(TenantBaseModel, ActivatableMixin):
    """
    Stock valuation layers for FIFO/LIFO cost tracking and landed cost allocation
    """
    
    VALUATION_METHODS = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('SPECIFIC', 'Specific Identification'),
    ]
    
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='valuation_layers'
    )
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='valuation_layers'
    )
    
    # Layer Information
    layer_sequence = models.PositiveIntegerField()
    layer_id = models.CharField(max_length=100, blank=True)
    receipt_date = models.DateTimeField(default=timezone.now)
    valuation_method = models.CharField(max_length=10, choices=VALUATION_METHODS, default='FIFO')
    
    # Quantities
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_consumed = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_remaining = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    landed_cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_landed_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Source Information
    source_movement = models.ForeignKey(
        'stock.StockMovement',
        on_delete=models.CASCADE,
        related_name='valuation_layers'
    )
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.CharField(max_length=50, blank=True)
    purchase_order_number = models.CharField(max_length=50, blank=True)
    
    # Status
    is_fully_consumed = models.BooleanField(default=False)
    consumption_date = models.DateTimeField(null=True, blank=True)
    
    # Additional Costs (for landed cost calculation)
    freight_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    duty_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_valuation_layers'
        ordering = ['stock_item', 'receipt_date', 'layer_sequence']  # FIFO order
        indexes = [
            models.Index(fields=['tenant_id', 'stock_item', 'is_active']),
            models.Index(fields=['tenant_id', 'stock_item', 'receipt_date']),
            models.Index(fields=['tenant_id', 'is_fully_consumed']),
            models.Index(fields=['tenant_id', 'valuation_method']),
        ]
    
    def __str__(self):
        return f"Layer {self.layer_sequence}: {self.stock_item} - {self.quantity_remaining} @ {self.unit_cost}"
    
    def consume_quantity(self, quantity, consumption_method='FIFO'):
        """Consume quantity from this layer (FIFO/LIFO)"""
        quantity = Decimal(str(quantity))
        available = self.quantity_remaining
        
        if available >= quantity:
            # Can consume full quantity from this layer
            self.quantity_consumed += quantity
            self.quantity_remaining -= quantity
            
            if self.quantity_remaining == 0:
                self.is_fully_consumed = True
                self.consumption_date = timezone.now()
            
            consumed_cost = quantity * (self.unit_cost + self.landed_cost_per_unit)
            
            self.save(update_fields=[
                'quantity_consumed', 'quantity_remaining', 
                'is_fully_consumed', 'consumption_date'
            ])
            
            return quantity, consumed_cost
        else:
            # Can only consume what's available
            self.quantity_consumed += available
            self.quantity_remaining = Decimal('0')
            self.is_fully_consumed = True
            self.consumption_date = timezone.now()
            
            consumed_cost = available * (self.unit_cost + self.landed_cost_per_unit)
            
            self.save(update_fields=[
                'quantity_consumed', 'quantity_remaining', 
                'is_fully_consumed', 'consumption_date'
            ])
            
            return available, consumed_cost
    
    def calculate_total_unit_cost(self):
        """Calculate total unit cost including landed costs"""
        return self.unit_cost + self.landed_cost_per_unit
    
    def allocate_landed_costs(self, freight=0, duty=0, handling=0, other=0):
        """Allocate additional landed costs to this layer"""
        additional_costs = Decimal(str(freight)) + Decimal(str(duty)) + \
                         Decimal(str(handling)) + Decimal(str(other))
        
        if self.quantity_received > 0:
            additional_per_unit = additional_costs / self.quantity_received
            self.landed_cost_per_unit += additional_per_unit
            self.total_landed_cost += additional_costs
            
            # Update individual cost components
            self.freight_cost += Decimal(str(freight))
            self.duty_cost += Decimal(str(duty))
            self.handling_cost += Decimal(str(handling))
            self.other_costs += Decimal(str(other))
            
            self.save(update_fields=[
                'landed_cost_per_unit', 'total_landed_cost',
                'freight_cost', 'duty_cost', 'handling_cost', 'other_costs'
            ])
    
    def save(self, *args, **kwargs):
        # Calculate total costs
        self.total_cost = self.quantity_received * self.unit_cost
        self.total_landed_cost = self.quantity_received * self.landed_cost_per_unit
        
        # Auto-generate sequence if not provided
        if not self.layer_sequence:
            last_layer = StockValuationLayer.objects.filter(
                stock_item=self.stock_item,
                tenant_id=self.tenant_id
            ).order_by('-layer_sequence').first()
            
            self.layer_sequence = (last_layer.layer_sequence + 1) if last_layer else 1
        
        # Generate layer ID
        if not self.layer_id:
            self.layer_id = f"{self.stock_item.id}-{self.layer_sequence}-{self.receipt_date.strftime('%Y%m%d')}"
        
        super().save(*args, **kwargs)


class CostAllocation(TenantBaseModel):
    """
    Cost allocation tracking for landed costs and overhead distribution
    """
    
    ALLOCATION_TYPES = [
        ('FREIGHT', 'Freight Cost'),
        ('DUTY', 'Import Duty'),
        ('HANDLING', 'Handling Cost'),
        ('INSURANCE', 'Insurance Cost'),
        ('OVERHEAD', 'Overhead Allocation'),
        ('CURRENCY_ADJUSTMENT', 'Currency Adjustment'),
        ('OTHER', 'Other Costs'),
    ]
    
    ALLOCATION_METHODS = [
        ('QUANTITY', 'By Quantity'),
        ('VALUE', 'By Value'),
        ('WEIGHT', 'By Weight'),
        ('VOLUME', 'By Volume'),
        ('EQUAL', 'Equal Distribution'),
        ('MANUAL', 'Manual Allocation'),
    ]
    
    # Reference to source document (PO, Receipt, etc.)
    source_document_type = models.CharField(max_length=50)
    source_document_id = models.CharField(max_length=50)
    source_document_number = models.CharField(max_length=100, blank=True)
    
    # Allocation Details
    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_TYPES)
    allocation_method = models.CharField(max_length=10, choices=ALLOCATION_METHODS)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Allocation Date
    allocation_date = models.DateTimeField(default=timezone.now)
    
    # Supplier Information
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cost_allocations'
    )
    
    # Notes
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_cost_allocations'
        indexes = [
            models.Index(fields=['tenant_id', 'source_document_type', 'source_document_id']),
            models.Index(fields=['tenant_id', 'allocation_type']),
            models.Index(fields=['tenant_id', 'allocation_date']),
        ]
    
    def __str__(self):
        return f"{self.get_allocation_type_display()}: {self.total_amount} for {self.source_document_number}"
    
    def allocate_to_layers(self):
        """Allocate costs to relevant valuation layers"""
        # Get all valuation layers for the source document
        layers = StockValuationLayer.objects.filter(
            tenant_id=self.tenant_id,
            source_document_type=self.source_document_type,
            source_document_id=self.source_document_id,
            is_active=True
        )
        
        if not layers.exists():
            return False, "No valuation layers found for allocation"
        
        # Calculate allocation base
        if self.allocation_method == 'QUANTITY':
            total_base = sum(layer.quantity_received for layer in layers)
        elif self.allocation_method == 'VALUE':
            total_base = sum(layer.total_cost for layer in layers)
        elif self.allocation_method == 'EQUAL':
            total_base = layers.count()
        else:
            return False, f"Allocation method {self.allocation_method} not implemented"
        
        if total_base <= 0:
            return False, "Invalid allocation base"
        
        # Allocate to each layer
        allocated_amount = Decimal('0')
        for layer in layers:
            if self.allocation_method == 'QUANTITY':
                allocation_ratio = layer.quantity_received / total_base
            elif self.allocation_method == 'VALUE':
                allocation_ratio = layer.total_cost / total_base
            elif self.allocation_method == 'EQUAL':
                allocation_ratio = Decimal('1') / total_base
            
            layer_allocation = (self.total_amount * allocation_ratio).quantize(Decimal('0.01'))
            allocated_amount += layer_allocation
            
            # Update layer based on allocation type
            if self.allocation_type == 'FREIGHT':
                layer.allocate_landed_costs(freight=layer_allocation)
            elif self.allocation_type == 'DUTY':
                layer.allocate_landed_costs(duty=layer_allocation)
            elif self.allocation_type == 'HANDLING':
                layer.allocate_landed_costs(handling=layer_allocation)
            else:
                layer.allocate_landed_costs(other=layer_allocation)
        
        return True, f"Allocated {allocated_amount} to {layers.count()} layers"


class CostAdjustment(TenantBaseModel):
    """
    Cost adjustments and revaluations
    """
    
    ADJUSTMENT_TYPES = [
        ('REVALUATION', 'Cost Revaluation'),
        ('CORRECTION', 'Cost Correction'),
        ('WRITE_DOWN', 'Inventory Write-down'),
        ('WRITE_UP', 'Inventory Write-up'),
        ('CURRENCY_ADJUSTMENT', 'Currency Adjustment'),
        ('STANDARD_COST_UPDATE', 'Standard Cost Update'),
    ]
    
    # Reference Information
    adjustment_number = models.CharField(max_length=50, blank=True)
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    adjustment_date = models.DateTimeField(default=timezone.now)
    
    # Product/Stock Item
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='cost_adjustments'
    )
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='cost_adjustments'
    )
    
    # Cost Changes
    old_unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    new_unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    cost_difference = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Quantity Affected
    quantity_affected = models.DecimalField(max_digits=12, decimal_places=3)
    total_adjustment_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Approval Information
    requires_approval = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_cost_adjustments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Accounting Impact
    gl_impact = models.JSONField(default=dict, blank=True)
    
    # Reason and Documentation
    reason = models.TextField()
    supporting_documentation = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_cost_adjustments'
        indexes = [
            models.Index(fields=['tenant_id', 'adjustment_type']),
            models.Index(fields=['tenant_id', 'product']),
            models.Index(fields=['tenant_id', 'adjustment_date']),
            models.Index(fields=['tenant_id', 'requires_approval']),
        ]
    
    def __str__(self):
        return f"{self.adjustment_number}: {self.get_adjustment_type_display()}"
    
    def save(self, *args, **kwargs):
        # Calculate derived fields
        self.cost_difference = self.new_unit_cost - self.old_unit_cost
        self.total_adjustment_value = self.cost_difference * self.quantity_affected
        
        # Auto-generate adjustment number
        if not self.adjustment_number:
            from datetime import datetime
            today = datetime.now().strftime('%Y%m%d')
            
            last_adjustment = CostAdjustment.objects.filter(
                tenant_id=self.tenant_id,
                adjustment_number__startswith=f'CA-{today}'
            ).order_by('-adjustment_number').first()
            
            if last_adjustment:
                try:
                    last_seq = int(last_adjustment.adjustment_number.split('-')[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = 1
            else:
                next_seq = 1
            
            self.adjustment_number = f"CA-{today}-{next_seq:04d}"
        
        super().save(*args, **kwargs)
    
    def approve(self, user):
        """Approve the cost adjustment"""
        if not self.requires_approval:
            return True, "Adjustment does not require approval"
        
        if self.approved_by:
            return False, "Adjustment already approved"
        
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=['approved_by', 'approved_at'])
        
        # Apply the adjustment
        return self.apply_adjustment()
    
    def apply_adjustment(self):
        """Apply the cost adjustment to inventory"""
        if self.requires_approval and not self.approved_by:
            return False, "Adjustment requires approval before application"
        
        if self.stock_item:
            # Apply to specific stock item
            if self.adjustment_type == 'REVALUATION':
                self.stock_item.standard_cost = self.new_unit_cost
                self.stock_item.save(update_fields=['standard_cost'])
            elif self.adjustment_type == 'CORRECTION':
                self.stock_item.average_cost = self.new_unit_cost
                self.stock_item.update_total_value()
        elif self.product:
            # Apply to product (affects all stock items)
            if self.adjustment_type == 'STANDARD_COST_UPDATE':
                self.product.standard_cost = self.new_unit_cost
                self.product.save(update_fields=['standard_cost'])
                
                # Update all stock items for this product
                stock_items = self.product.stock_items.filter(
                    tenant_id=self.tenant_id,
                    is_active=True
                )
                for stock_item in stock_items:
                    stock_item.standard_cost = self.new_unit_cost
                    stock_item.save(update_fields=['standard_cost'])
        
        return True, "Cost adjustment applied successfully"