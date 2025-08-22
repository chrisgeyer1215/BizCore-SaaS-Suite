"""
Stock receipt management for incoming inventory
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from apps.core.models import TenantBaseModel
from ..abstract.auditable import AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class StockReceipt(TenantBaseModel, AuditableMixin):
    """
    Stock receipt management for incoming inventory with quality control
    """
    
    RECEIPT_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Receipt'),
        ('IN_PROGRESS', 'In Progress'),
        ('PARTIAL', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
        ('DISPUTED', 'Disputed'),
    ]
    
    RECEIPT_TYPES = [
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('TRANSFER', 'Transfer Receipt'),
        ('RETURN', 'Customer Return'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('MANUFACTURING', 'Manufacturing Output'),
        ('FOUND_STOCK', 'Found Stock'),
        ('CONSIGNMENT', 'Consignment Receipt'),
        ('SAMPLE', 'Sample Receipt'),
        ('OTHER', 'Other'),
    ]
    
    QUALITY_STATUS = [
        ('PENDING', 'Pending Inspection'),
        ('PASSED', 'Quality Passed'),
        ('FAILED', 'Quality Failed'),
        ('PARTIAL_PASS', 'Partial Pass'),
        ('EXEMPT', 'Inspection Exempt'),
    ]
    
    # Basic Information
    receipt_number = models.CharField(max_length=100, blank=True)
    receipt_type = models.CharField(max_length=20, choices=RECEIPT_TYPES, default='PURCHASE_ORDER')
    
    # Source References
    purchase_order = models.ForeignKey(
        'purchasing.PurchaseOrder',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='receipts'
    )
    transfer_order_id = models.CharField(max_length=50, blank=True)
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='stock_receipts'
    )
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='stock_receipts'
    )
    
    # Date & Time Information
    receipt_date = models.DateTimeField(default=timezone.now)
    expected_date = models.DateTimeField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=RECEIPT_STATUS, default='DRAFT')
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='received_stock_receipts'
    )
    inspected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inspected_stock_receipts'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_stock_receipts'
    )
    
    # Shipping & Delivery Information
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    delivery_note_number = models.CharField(max_length=100, blank=True)
    packing_slip_number = models.CharField(max_length=100, blank=True)
    bill_of_lading = models.CharField(max_length=100, blank=True)
    container_number = models.CharField(max_length=50, blank=True)
    seal_number = models.CharField(max_length=50, blank=True)
    
    # Vehicle & Driver Information
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_license = models.CharField(max_length=50, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    
    # Quality Control & Inspection
    requires_inspection = models.BooleanField(default=False)
    inspection_completed = models.BooleanField(default=False)
    inspection_completion_date = models.DateTimeField(null=True, blank=True)
    quality_status = models.CharField(max_length=20, choices=QUALITY_STATUS, default='PENDING')
    quality_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Quality score percentage (0-100)"
    )
    
    # Financial Information
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    freight_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duty_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Physical Characteristics
    total_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    total_volume = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    package_count = models.IntegerField(null=True, blank=True)
    pallet_count = models.IntegerField(null=True, blank=True)
    
    # Temperature & Storage Conditions
    temperature_recorded = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    humidity_recorded = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_conditions_met = models.BooleanField(default=True)
    
    # Damage & Discrepancy Reporting
    has_damage = models.BooleanField(default=False)
    damage_report = models.TextField(blank=True)
    has_discrepancy = models.BooleanField(default=False)
    discrepancy_report = models.TextField(blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Document Management
    receipt_documents = models.JSONField(default=list, blank=True)
    photos = models.JSONField(default=list, blank=True)
    quality_certificates = models.JSONField(default=list, blank=True)
    
    # Performance Metrics
    receipt_duration_minutes = models.IntegerField(null=True, blank=True)
    items_per_minute = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    accuracy_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Integration & External References
    external_receipt_id = models.CharField(max_length=100, blank=True)
    wms_receipt_id = models.CharField(max_length=100, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_receipts'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'receipt_number'], 
                name='unique_tenant_receipt_number'
            ),
        ]
        ordering = ['-receipt_date']
        indexes = [
            models.Index(fields=['tenant_id', 'status', '-receipt_date']),
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
            models.Index(fields=['tenant_id', 'supplier', 'status']),
            models.Index(fields=['tenant_id', 'receipt_type']),
            models.Index(fields=['tenant_id', 'quality_status']),
        ]
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.warehouse.name}"
    
    def clean(self):
        if not self.receipt_number:
            # Auto-generate receipt number
            last_receipt = StockReceipt.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_receipt and last_receipt.receipt_number:
                try:
                    last_num = int(last_receipt.receipt_number.replace('REC', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.receipt_number = f"REC{last_num + 1:06d}"
    
    def start_receiving(self, user):
        """Start the receiving process"""
        if self.status != 'PENDING':
            return False, f"Cannot start receipt with status {self.status}"
        
        self.status = 'IN_PROGRESS'
        self.started_at = timezone.now()
        self.received_by = user
        
        self.save(update_fields=['status', 'started_at', 'received_by'])
        return True, "Receipt process started"
    
    def complete_receiving(self, user):
        """Complete the receiving process"""
        if self.status != 'IN_PROGRESS':
            return False, f"Cannot complete receipt with status {self.status}"
        
        # Check if all items are processed
        pending_items = self.items.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
        if pending_items > 0:
            return False, f"{pending_items} items still pending processing"
        
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        
        # Calculate performance metrics
        if self.started_at:
            duration = self.completed_at - self.started_at
            self.receipt_duration_minutes = int(duration.total_seconds() / 60)
            
            total_items = self.items.count()
            if total_items > 0 and self.receipt_duration_minutes > 0:
                self.items_per_minute = Decimal(str(total_items)) / Decimal(str(self.receipt_duration_minutes))
        
        # Calculate accuracy
        total_expected = sum(item.quantity_expected for item in self.items.all())
        total_received = sum(item.quantity_received for item in self.items.all())
        if total_expected > 0:
            self.accuracy_percentage = (total_received / total_expected * 100).quantize(Decimal('0.01'))
        
        self.save(update_fields=[
            'status', 'completed_at', 'receipt_duration_minutes', 
            'items_per_minute', 'accuracy_percentage'
        ])
        
        return True, "Receipt completed successfully"
    
    def put_on_hold(self, reason, user):
        """Put receipt on hold"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False, f"Cannot put receipt on hold with status {self.status}"
        
        self.status = 'ON_HOLD'
        self.internal_notes = f"Put on hold by {user.get_full_name()}: {reason}\n{self.internal_notes}"
        
        self.save(update_fields=['status', 'internal_notes'])
        return True, "Receipt put on hold"
    
    def remove_from_hold(self, user):
        """Remove receipt from hold"""
        if self.status != 'ON_HOLD':
            return False, "Receipt is not on hold"
        
        # Determine appropriate status based on progress
        if self.started_at and not self.completed_at:
            self.status = 'IN_PROGRESS'
        elif self.items.filter(status='COMPLETED').exists():
            self.status = 'PARTIAL'
        else:
            self.status = 'PENDING'
        
        self.internal_notes = f"Removed from hold by {user.get_full_name()}\n{self.internal_notes}"
        self.save(update_fields=['status', 'internal_notes'])
        
        return True, f"Receipt status changed to {self.status}"
    
    def calculate_totals(self):
        """Calculate total costs from line items"""
        item_totals = self.items.aggregate(
            total_cost=models.Sum('total_cost'),
            total_quantity=models.Sum('quantity_received')
        )
        
        self.total_cost = (item_totals['total_cost'] or Decimal('0')) + \
                         self.freight_cost + self.duty_cost + \
                         self.handling_cost + self.other_charges
        
        self.save(update_fields=['total_cost'])
    
    @property
    def total_items(self):
        """Total number of line items"""
        return self.items.count()
    
    @property
    def total_quantity_expected(self):
        """Total quantity expected"""
        return self.items.aggregate(
            total=models.Sum('quantity_expected')
        )['total'] or Decimal('0')
    
    @property
    def total_quantity_received(self):
        """Total quantity actually received"""
        return self.items.aggregate(
            total=models.Sum('quantity_received')
        )['total'] or Decimal('0')
    
    @property
    def receipt_variance(self):
        """Variance between expected and received quantities"""
        return self.total_quantity_received - self.total_quantity_expected
    
    @property
    def receipt_variance_percentage(self):
        """Variance percentage"""
        expected = self.total_quantity_expected
        if expected > 0:
            return (self.receipt_variance / expected * 100).quantize(Decimal('0.01'))
        return Decimal('0')


class StockReceiptItem(TenantBaseModel):
    """
    Stock receipt line items with detailed tracking
    """
    
    ITEM_STATUS = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('QUARANTINED', 'Quarantined'),
        ('REJECTED', 'Rejected'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    QUALITY_STATUS = [
        ('PENDING', 'Pending Inspection'),
        ('PASSED', 'Quality Passed'),
        ('FAILED', 'Quality Failed'),
        ('QUARANTINED', 'Quarantined'),
        ('CONDITIONAL_PASS', 'Conditional Pass'),
    ]
    
    receipt = models.ForeignKey(
        StockReceipt,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='receipt_items'
    )
    variation = models.ForeignKey(
        'catalog.ProductVariation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Purchase Order Reference
    purchase_order_item = models.ForeignKey(
        'purchasing.PurchaseOrderItem',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Quantities
    quantity_expected = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_accepted = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_on_hold = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit & Location
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='receipt_items'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='receipt_items'
    )
    
    # Batch & Serial Information
    batch_number = models.CharField(max_length=50, blank=True)
    lot_number = models.CharField(max_length=50, blank=True)
    serial_numbers = models.JSONField(default=list, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    landed_cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Quality Information
    quality_status = models.CharField(max_length=20, choices=QUALITY_STATUS, default='PENDING')
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    quality_notes = models.TextField(blank=True)
    quality_test_results = models.JSONField(default=dict, blank=True)
    
    # Physical Characteristics
    actual_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    actual_dimensions = models.JSONField(default=dict, blank=True)
    package_condition = models.CharField(max_length=100, blank=True)
    
    # Status & Processing
    status = models.CharField(max_length=20, choices=ITEM_STATUS, default='PENDING')
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='processed_receipt_items'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    damage_description = models.TextField(blank=True)
    special_handling_notes = models.TextField(blank=True)
    
    # Document References
    inspection_certificate_url = models.URLField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_receipt_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'receipt', 'line_number'],
                name='unique_receipt_line_number'
            ),
        ]
        ordering = ['receipt', 'line_number']
        indexes = [
            models.Index(fields=['tenant_id', 'receipt']),
            models.Index(fields=['tenant_id', 'product', 'quality_status']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'batch_number']),
        ]
    
    def __str__(self):
        return f"{self.receipt.receipt_number} Line {self.line_number}: {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_received * (self.unit_cost + self.landed_cost_per_unit)
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockReceiptItem.objects.filter(
                receipt=self.receipt,
                tenant_id=self.tenant_id
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    def process_item(self, quantity_received, user, quality_status='PENDING', 
                    batch_number=None, expiry_date=None, location=None, notes=''):
        """Process the receipt item"""
        if self.status not in ['PENDING', 'IN_PROGRESS']:
            return False, f"Cannot process item with status {self.status}"
        
        quantity_received = Decimal(str(quantity_received))
        
        self.quantity_received = quantity_received
        self.quality_status = quality_status
        self.batch_number = batch_number or self.batch_number
        self.expiry_date = expiry_date or self.expiry_date
        self.location = location or self.location
        self.processed_by = user
        self.processed_at = timezone.now()
        
        if notes:
            self.notes = f"{notes}\n{self.notes}" if self.notes else notes
        
        # Determine quantities based on quality status
        if quality_status == 'PASSED':
            self.quantity_accepted = quantity_received
            self.quantity_rejected = Decimal('0')
            self.status = 'COMPLETED'
        elif quality_status == 'FAILED':
            self.quantity_accepted = Decimal('0')
            self.quantity_rejected = quantity_received
            self.status = 'REJECTED'
        elif quality_status == 'QUARANTINED':
            self.quantity_accepted = Decimal('0')
            self.quantity_on_hold = quantity_received
            self.status = 'QUARANTINED'
        else:  # PENDING or CONDITIONAL_PASS
            self.quantity_accepted = quantity_received
            self.status = 'COMPLETED'
        
        self.save(update_fields=[
            'quantity_received', 'quantity_accepted', 'quantity_rejected', 'quantity_on_hold',
            'quality_status', 'batch_number', 'expiry_date', 'location',
            'processed_by', 'processed_at', 'status', 'notes', 'total_cost'
        ])
        
        # Create stock movement if accepted
        if self.quantity_accepted > 0:
            success, message = self._create_stock_entry()
            if not success:
                return False, f"Stock entry failed: {message}"
        
        # Update purchase order item if linked
        if self.purchase_order_item:
            self.purchase_order_item.receive_quantity(
                self.quantity_accepted,
                batch_number=self.batch_number,
                expiry_date=self.expiry_date,
                location=self.location,
                user=user,
                quality_status=quality_status
            )
        
        return True, f"Item processed: {self.quantity_accepted} accepted, {self.quantity_rejected} rejected"
    
    def _create_stock_entry(self):
        """Create stock entry for accepted quantity"""
        from ..stock.items import StockItem
        
        # Get or create stock item
        stock_item, created = StockItem.objects.get_or_create(
            tenant_id=self.tenant_id,
            product=self.product,
            variation=self.variation,
            warehouse=self.receipt.warehouse,
            location=self.location,
            defaults={
                'unit_cost': self.unit_cost + self.landed_cost_per_unit,
                'average_cost': self.unit_cost + self.landed_cost_per_unit,
                'last_cost': self.unit_cost + self.landed_cost_per_unit,
            }
        )
        
        # Receive stock
        return stock_item.receive_stock(
            quantity=self.quantity_accepted,
            unit_cost=self.unit_cost + self.landed_cost_per_unit,
            reason=f"Receipt: {self.receipt.receipt_number}",
            reference_id=str(self.receipt.id),
            user=self.processed_by
        )
    
    def reject_item(self, reason, user):
        """Reject the entire item"""
        if self.status not in ['PENDING', 'IN_PROGRESS']:
            return False, f"Cannot reject item with status {self.status}"
        
        self.quantity_rejected = self.quantity_received
        self.quantity_accepted = Decimal('0')
        self.quality_status = 'FAILED'
        self.rejection_reason = reason
        self.status = 'REJECTED'
        self.processed_by = user
        self.processed_at = timezone.now()
        
        self.save(update_fields=[
            'quantity_rejected', 'quantity_accepted', 'quality_status',
            'rejection_reason', 'status', 'processed_by', 'processed_at'
        ])
        
        return True, "Item rejected successfully"
    
    def quarantine_item(self, reason, user):
        """Quarantine the item for further inspection"""
        if self.status not in ['PENDING', 'IN_PROGRESS', 'COMPLETED']:
            return False, f"Cannot quarantine item with status {self.status}"
        
        self.quantity_on_hold = self.quantity_received
        self.quantity_accepted = Decimal('0')
        self.quality_status = 'QUARANTINED'
        self.quality_notes = f"Quarantined: {reason}"
        self.status = 'QUARANTINED'
        
        self.save(update_fields=[
            'quantity_on_hold', 'quantity_accepted', 'quality_status',
            'quality_notes', 'status'
        ])
        
        return True, "Item quarantined successfully"
    
    @property
    def variance_quantity(self):
        """Quantity variance (received vs expected)"""
        return self.quantity_received - self.quantity_expected
    
    @property
    def variance_percentage(self):
        """Variance percentage"""
        if self.quantity_expected > 0:
            return (self.variance_quantity / self.quantity_expected * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_over_received(self):
        """Check if more was received than expected"""
        return self.quantity_received > self.quantity_expected
    
    @property
    def is_under_received(self):
        """Check if less was received than expected"""
        return self.quantity_received < self.quantity_expected