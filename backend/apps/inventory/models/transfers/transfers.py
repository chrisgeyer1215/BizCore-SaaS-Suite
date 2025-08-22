"""
Stock transfer management between warehouses and locations
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel
from ..abstract.auditable import AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class StockTransfer(TenantBaseModel, AuditableMixin):
    """
    Inter-warehouse and inter-location stock transfers with comprehensive workflow
    """
    
    TRANSFER_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('RESERVED', 'Stock Reserved'),
        ('PICKED', 'Picked'),
        ('IN_TRANSIT', 'In Transit'),
        ('PARTIAL_RECEIVED', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    TRANSFER_TYPES = [
        ('STANDARD', 'Standard Transfer'),
        ('EMERGENCY', 'Emergency Transfer'),
        ('REBALANCING', 'Stock Rebalancing'),
        ('RETURN', 'Return Transfer'),
        ('REPAIR', 'Repair Transfer'),
        ('RELOCATION', 'Internal Relocation'),
        ('CONSOLIDATION', 'Stock Consolidation'),
        ('SPLIT', 'Stock Split'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    # Basic Information
    transfer_number = models.CharField(max_length=100, blank=True)
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES, default='STANDARD')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
    
    # Source and Destination
    from_warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='transfers_out'
    )
    to_warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='transfers_in'
    )
    from_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfers_from'
    )
    to_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfers_to'
    )
    
    # Date Management
    transfer_date = models.DateField(default=date.today)
    required_date = models.DateField()
    scheduled_pickup_date = models.DateTimeField(null=True, blank=True)
    actual_pickup_date = models.DateTimeField(null=True, blank=True)
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS, default='DRAFT')
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requested_transfers'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_transfers'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    picked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='picked_transfers'
    )
    shipped_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shipped_transfers'
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='received_transfers'
    )
    
    # Shipping & Transportation
    shipping_method = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_contact = models.CharField(max_length=20, blank=True)
    
    # Cost Information
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_transfer_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Transfer Value (for insurance/tracking)
    total_inventory_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Quality & Condition Tracking
    condition_on_pickup = models.CharField(max_length=20, default='GOOD')
    condition_on_delivery = models.CharField(max_length=20, blank=True)
    quality_inspection_required = models.BooleanField(default=False)
    quality_inspection_completed = models.BooleanField(default=False)
    
    # Temperature & Environment Tracking
    temperature_controlled = models.BooleanField(default=False)
    min_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperature_log = models.JSONField(default=list, blank=True)
    
    # Documentation & References
    transfer_slip_number = models.CharField(max_length=100, blank=True)
    bill_of_lading = models.CharField(max_length=100, blank=True)
    manifest_number = models.CharField(max_length=100, blank=True)
    seal_numbers = models.JSONField(default=list, blank=True)
    
    # Reason & Authorization
    reason = models.TextField()
    business_justification = models.TextField(blank=True)
    authorization_code = models.CharField(max_length=50, blank=True)
    
    # Special Handling
    special_handling_required = models.BooleanField(default=False)
    special_handling_instructions = models.TextField(blank=True)
    hazmat_transfer = models.BooleanField(default=False)
    
    # Performance Metrics
    picking_duration_minutes = models.IntegerField(null=True, blank=True)
    transit_duration_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    receiving_duration_minutes = models.IntegerField(null=True, blank=True)
    accuracy_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Document Management
    transfer_documents = models.JSONField(default=list, blank=True)
    photos = models.JSONField(default=list, blank=True)
    
    # Integration & External References
    external_transfer_id = models.CharField(max_length=100, blank=True)
    wms_transfer_id = models.CharField(max_length=100, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_transfers'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'transfer_number'], 
                name='unique_tenant_transfer_number'
            ),
        ]
        ordering = ['-transfer_date', '-id']
        indexes = [
            models.Index(fields=['tenant_id', 'status', '-transfer_date']),
            models.Index(fields=['tenant_id', 'from_warehouse', 'status']),
            models.Index(fields=['tenant_id', 'to_warehouse', 'status']),
            models.Index(fields=['tenant_id', 'transfer_type']),
            models.Index(fields=['tenant_id', 'priority', 'required_date']),
        ]
    
    def __str__(self):
        return f"Transfer {self.transfer_number}: {self.from_warehouse.code} → {self.to_warehouse.code}"
    
    def clean(self):
        if not self.transfer_number:
            # Auto-generate transfer number
            last_transfer = StockTransfer.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_transfer and last_transfer.transfer_number:
                try:
                    last_num = int(last_transfer.transfer_number.replace('TRN', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.transfer_number = f"TRN{last_num + 1:06d}"
    
    def approve(self, user, notes=''):
        """Approve the transfer request"""
        if self.status != 'PENDING_APPROVAL':
            return False, f"Cannot approve transfer with status {self.status}"
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        
        if notes:
            self.internal_notes = f"Approved: {notes}\n{self.internal_notes}"
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'internal_notes'])
        
        # Auto-reserve stock if approved
        success, message = self.reserve_stock()
        if not success:
            return False, f"Approval succeeded but stock reservation failed: {message}"
        
        return True, "Transfer approved and stock reserved"
    
    def reserve_stock(self):
        """Reserve stock for all transfer items"""
        if self.status not in ['APPROVED', 'RESERVED']:
            return False, f"Cannot reserve stock for transfer with status {self.status}"
        
        reservation_failures = []
        
        for item in self.items.all():
            success, message = item.reserve_stock()
            if not success:
                reservation_failures.append(f"Line {item.line_number}: {message}")
        
        if reservation_failures:
            return False, f"Stock reservation failed: {'; '.join(reservation_failures)}"
        
        self.status = 'RESERVED'
        self.save(update_fields=['status'])
        
        return True, "All stock successfully reserved"
    
    def start_picking(self, user):
        """Start the picking process"""
        if self.status != 'RESERVED':
            return False, f"Cannot start picking with status {self.status}"
        
        self.status = 'PICKED'
        self.picked_by = user
        self.actual_pickup_date = timezone.now()
        
        self.save(update_fields=['status', 'picked_by', 'actual_pickup_date'])
        
        return True, "Picking process started"
    
    def ship_transfer(self, user, tracking_number='', carrier=''):
        """Ship the transfer"""
        if self.status != 'PICKED':
            return False, f"Cannot ship transfer with status {self.status}"
        
        # Check if all items are picked
        unpicked_items = self.items.filter(status__in=['REQUESTED', 'APPROVED', 'RESERVED']).count()
        if unpicked_items > 0:
            return False, f"{unpicked_items} items not yet picked"
        
        self.status = 'IN_TRANSIT'
        self.shipped_by = user
        self.tracking_number = tracking_number
        self.carrier = carrier
        
        # Calculate transit time estimate
        if self.scheduled_pickup_date:
            self.estimated_delivery_date = self.scheduled_pickup_date + timezone.timedelta(days=1)
        
        self.save(update_fields=[
            'status', 'shipped_by', 'tracking_number', 'carrier', 'estimated_delivery_date'
        ])
        
        # Process outbound stock movements
        for item in self.items.all():
            item.process_outbound_movement(user)
        
        return True, f"Transfer shipped with tracking number {tracking_number}"
    
    def receive_transfer(self, user):
        """Receive the complete transfer"""
        if self.status not in ['IN_TRANSIT', 'PARTIAL_RECEIVED']:
            return False, f"Cannot receive transfer with status {self.status}"
        
        self.received_by = user
        self.actual_delivery_date = timezone.now()
        
        # Calculate performance metrics
        if self.actual_pickup_date:
            transit_time = self.actual_delivery_date - self.actual_pickup_date
            self.transit_duration_hours = Decimal(str(transit_time.total_seconds() / 3600))
        
        # Check if all items are received
        pending_items = self.items.exclude(status='RECEIVED').count()
        if pending_items == 0:
            self.status = 'COMPLETED'
        else:
            self.status = 'PARTIAL_RECEIVED'
        
        self.save(update_fields=[
            'status', 'received_by', 'actual_delivery_date', 'transit_duration_hours'
        ])
        
        return True, f"Transfer received - Status: {self.get_status_display()}"
    
    def cancel_transfer(self, reason, user):
        """Cancel the transfer"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False, f"Cannot cancel transfer with status {self.status}"
        
        old_status = self.status
        self.status = 'CANCELLED'
        self.internal_notes = f"Cancelled by {user.get_full_name()}: {reason}\n{self.internal_notes}"
        
        self.save(update_fields=['status', 'internal_notes'])
        
        # Release reserved stock
        if old_status in ['RESERVED', 'PICKED']:
            for item in self.items.all():
                item.release_reservation(user)
        
        return True, f"Transfer cancelled (was {old_status})"
    
    def calculate_totals(self):
        """Calculate total costs and values"""
        item_totals = self.items.aggregate(
            total_cost=models.Sum('total_cost'),
            total_value=models.Sum('total_value')
        )
        
        self.total_inventory_value = item_totals['total_value'] or Decimal('0')
        self.total_transfer_cost = (
            self.shipping_cost + self.handling_cost + self.insurance_cost
        )
        
        self.save(update_fields=['total_inventory_value', 'total_transfer_cost'])
    
    @property
    def total_items(self):
        """Total number of line items"""
        return self.items.count()
    
    @property
    def total_quantity_requested(self):
        """Total quantity requested"""
        return self.items.aggregate(
            total=models.Sum('quantity_requested')
        )['total'] or Decimal('0')
    
    @property
    def total_quantity_shipped(self):
        """Total quantity shipped"""
        return self.items.aggregate(
            total=models.Sum('quantity_shipped')
        )['total'] or Decimal('0')
    
    @property
    def total_quantity_received(self):
        """Total quantity received"""
        return self.items.aggregate(
            total=models.Sum('quantity_received')
        )['total'] or Decimal('0')
    
    @property
    def is_overdue(self):
        """Check if transfer is overdue"""
        if self.required_date and self.status not in ['COMPLETED', 'CANCELLED']:
            return self.required_date < timezone.now().date()
        return False
    
    @property
    def days_in_transit(self):
        """Days the transfer has been in transit"""
        if self.status == 'IN_TRANSIT' and self.actual_pickup_date:
            delta = timezone.now() - self.actual_pickup_date
            return delta.days
        return 0


class StockTransferItem(TenantBaseModel):
    """
    Stock transfer line items with detailed tracking
    """
    
    ITEM_STATUS = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('RESERVED', 'Stock Reserved'),
        ('PICKED', 'Picked'),
        ('SHIPPED', 'Shipped'),
        ('IN_TRANSIT', 'In Transit'),
        ('RECEIVED', 'Received'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    CONDITION_CODES = [
        ('GOOD', 'Good Condition'),
        ('FAIR', 'Fair Condition'),
        ('POOR', 'Poor Condition'),
        ('DAMAGED', 'Damaged'),
        ('DEFECTIVE', 'Defective'),
    ]
    
    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='transfer_items'
    )
    variation = models.ForeignKey(
        'catalog.ProductVariation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='transfer_items'
    )
    
    # Stock Item Reference (source)
    source_stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='transfer_items_out'
    )
    
    # Batch and Serial Tracking
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_items'
    )
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Quantities
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_picked = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_shipped = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_damaged = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit Information
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='transfer_items'
    )
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Condition Tracking
    condition_on_pickup = models.CharField(max_length=20, choices=CONDITION_CODES, default='GOOD')
    condition_on_delivery = models.CharField(max_length=20, choices=CONDITION_CODES, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=ITEM_STATUS, default='REQUESTED')
    picked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='picked_transfer_items'
    )
    picked_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='received_transfer_items'
    )
    received_at = models.DateTimeField(null=True, blank=True)
    
    # Quality Information
    quality_check_required = models.BooleanField(default=False)
    quality_check_completed = models.BooleanField(default=False)
    quality_status = models.CharField(max_length=20, blank=True)
    quality_notes = models.TextField(blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    damage_description = models.TextField(blank=True)
    handling_instructions = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_transfer_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'transfer', 'line_number'],
                name='unique_transfer_line_number'
            ),
        ]
        ordering = ['transfer', 'line_number']
        indexes = [
            models.Index(fields=['tenant_id', 'transfer']),
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'source_stock_item']),
        ]
    
    def __str__(self):
        return f"{self.transfer.transfer_number} Line {self.line_number}: {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Calculate costs
        self.total_cost = self.quantity_requested * self.unit_cost
        self.total_value = self.quantity_requested * self.unit_cost
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockTransferItem.objects.filter(
                transfer=self.transfer,
                tenant_id=self.tenant_id
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    def reserve_stock(self):
        """Reserve stock for this transfer item"""
        if self.status != 'APPROVED':
            return False, f"Cannot reserve stock for item with status {self.status}"
        
        if not self.source_stock_item:
            # Try to find appropriate stock item
            from ..stock.items import StockItem
            
            stock_items = StockItem.objects.filter(
                tenant_id=self.tenant_id,
                product=self.product,
                variation=self.variation,
                warehouse=self.transfer.from_warehouse,
                is_active=True,
                quantity_available__gte=self.quantity_requested
            ).order_by('-quantity_available')
            
            if not stock_items.exists():
                return False, "No available stock found"
            
            self.source_stock_item = stock_items.first()
        
        # Reserve the stock
        success, message = self.source_stock_item.reserve_stock(
            self.quantity_requested,
            f"Transfer: {self.transfer.transfer_number}",
            str(self.transfer.id)
        )
        
        if success:
            self.quantity_reserved = self.quantity_requested
            self.status = 'RESERVED'
            self.save(update_fields=['quantity_reserved', 'status', 'source_stock_item'])
        
        return success, message
    
    def pick_item(self, quantity, user, condition='GOOD', notes=''):
        """Pick the item for transfer"""
        quantity = Decimal(str(quantity))
        
        if self.status != 'RESERVED':
            return False, f"Cannot pick item with status {self.status}"
        
        if quantity > self.quantity_reserved:
            return False, f"Cannot pick more than reserved. Reserved: {self.quantity_reserved}"
        
        # Allocate the stock
        success, message = self.source_stock_item.allocate_stock(
            quantity,
            f"Transfer pick: {self.transfer.transfer_number}",
            str(self.transfer.id)
        )
        
        if not success:
            return False, f"Stock allocation failed: {message}"
        
        self.quantity_picked = quantity
        self.condition_on_pickup = condition
        self.picked_by = user
        self.picked_at = timezone.now()
        self.status = 'PICKED'
        
        if notes:
            self.notes = f"{notes}\n{self.notes}" if self.notes else notes
        
        self.save(update_fields=[
            'quantity_picked', 'condition_on_pickup', 'picked_by', 
            'picked_at', 'status', 'notes'
        ])
        
        return True, f"Item picked: {quantity} units"
    
    def process_outbound_movement(self, user):
        """Process the outbound stock movement"""
        if self.status != 'PICKED':
            return False, "Item must be picked first"
        
        # Ship the stock from source
        success, message = self.source_stock_item.ship_stock(
            self.quantity_picked,
            f"Transfer shipment: {self.transfer.transfer_number}",
            str(self.transfer.id),
            user
        )
        
        if success:
            self.quantity_shipped = self.quantity_picked
            self.status = 'SHIPPED'
            self.save(update_fields=['quantity_shipped', 'status'])
        
        return success, message
    
    def receive_item(self, quantity, user, condition='GOOD', damage_quantity=0, notes=''):
        """Receive the transferred item at destination"""
        quantity = Decimal(str(quantity))
        damage_quantity = Decimal(str(damage_quantity))
        
        if self.status not in ['SHIPPED', 'IN_TRANSIT']:
            return False, f"Cannot receive item with status {self.status}"
        
        if quantity + damage_quantity > self.quantity_shipped:
            return False, f"Cannot receive more than shipped. Shipped: {self.quantity_shipped}"
        
        # Create or update destination stock item
        from ..stock.items import StockItem
        
        dest_stock_item, created = StockItem.objects.get_or_create(
            tenant_id=self.tenant_id,
            product=self.product,
            variation=self.variation,
            warehouse=self.transfer.to_warehouse,
            location=self.transfer.to_location,
            defaults={
                'unit_cost': self.unit_cost,
                'average_cost': self.unit_cost,
                'last_cost': self.unit_cost,
            }
        )
        
        # Receive the good quantity
        if quantity > 0:
            success, message = dest_stock_item.receive_stock(
                quantity,
                self.unit_cost,
                f"Transfer receipt: {self.transfer.transfer_number}",
                str(self.transfer.id),
                user
            )
            
            if not success:
                return False, f"Stock receipt failed: {message}"
        
        # Handle damaged quantity
        if damage_quantity > 0:
            # Could create a separate stock item for damaged goods
            # or write off the damaged quantity
            pass
        
        self.quantity_received = quantity
        self.quantity_damaged = damage_quantity
        self.condition_on_delivery = condition
        self.received_by = user
        self.received_at = timezone.now()
        self.status = 'RECEIVED'
        
        if notes:
            self.notes = f"{notes}\n{self.notes}" if self.notes else notes
        
        if damage_quantity > 0:
            self.damage_description = f"Damaged quantity: {damage_quantity}"
        
        self.save(update_fields=[
            'quantity_received', 'quantity_damaged', 'condition_on_delivery',
            'received_by', 'received_at', 'status', 'notes', 'damage_description'
        ])
        
        return True, f"Item received: {quantity} good, {damage_quantity} damaged"
    
    def release_reservation(self, user):
        """Release reserved stock (for cancellation)"""
        if self.status not in ['RESERVED', 'PICKED']:
            return False, f"Cannot release reservation for item with status {self.status}"
        
        if self.quantity_reserved > 0 and self.source_stock_item:
            success, message = self.source_stock_item.release_reservation(
                self.quantity_reserved,
                f"Transfer cancelled: {self.transfer.transfer_number}",
                str(self.transfer.id)
            )
            
            if success:
                self.quantity_reserved = Decimal('0')
                self.status = 'CANCELLED'
                self.save(update_fields=['quantity_reserved', 'status'])
        
        return True, "Reservation released"
    
    @property
    def pending_quantity(self):
        """Quantity pending receipt"""
        return self.quantity_shipped - self.quantity_received - self.quantity_damaged
    
    @property
    def is_fully_received(self):
        """Check if item is fully received"""
        return self.quantity_received + self.quantity_damaged >= self.quantity_shipped
    
    @property
    def transfer_efficiency(self):
        """Efficiency percentage (received / requested)"""
        if self.quantity_requested > 0:
            return (self.quantity_received / self.quantity_requested * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def damage_rate(self):
        """Damage rate percentage"""
        total_processed = self.quantity_received + self.quantity_damaged
        if total_processed > 0:
            return (self.quantity_damaged / total_processed * 100).quantize(Decimal('0.01'))
        return Decimal('0')