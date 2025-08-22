"""
Stock movement tracking with comprehensive audit trail
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from decimal import Decimal
import uuid

from apps.core.models import TenantBaseModel
from ...managers.base import InventoryManager

User = get_user_model()


class StockMovement(TenantBaseModel):
    """
    Comprehensive stock movement tracking with full audit trail and business context
    """
    
    MOVEMENT_TYPES = [
        # Inbound movements
        ('RECEIVE', 'Stock Receipt'),
        ('PURCHASE', 'Purchase Order Receipt'),
        ('TRANSFER_IN', 'Transfer In'),
        ('RETURN_IN', 'Customer Return'),
        ('ADJUST_IN', 'Adjustment Increase'),
        ('MANUFACTURING_IN', 'Manufacturing Output'),
        ('FOUND', 'Found Stock'),
        ('CYCLE_COUNT_IN', 'Cycle Count Increase'),
        
        # Outbound movements
        ('SHIP', 'Stock Shipment'),
        ('SALE', 'Sale/Issue'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('RETURN_OUT', 'Return to Supplier'),
        ('ADJUST_OUT', 'Adjustment Decrease'),
        ('MANUFACTURING_OUT', 'Manufacturing Consumption'),
        ('DAMAGE', 'Damaged Stock'),
        ('LOSS', 'Stock Loss'),
        ('EXPIRED', 'Expired Stock'),
        ('SAMPLE', 'Sample Usage'),
        ('SCRAP', 'Scrap/Waste'),
        ('CYCLE_COUNT_OUT', 'Cycle Count Decrease'),
        
        # Internal movements
        ('RESERVE', 'Stock Reservation'),
        ('RELEASE', 'Release Reservation'),
        ('ALLOCATE', 'Stock Allocation'),
        ('PICK', 'Stock Picking'),
        ('RELOCATE', 'Location Change'),
        ('QUARANTINE', 'Quarantine Stock'),
        ('RELEASE_QUARANTINE', 'Release from Quarantine'),
        ('QUALITY_HOLD', 'Quality Hold'),
        ('QUALITY_RELEASE', 'Quality Release'),
        
        # Special movements
        ('REVALUE', 'Cost Revaluation'),
        ('CONSOLIDATE', 'Stock Consolidation'),
        ('SPLIT', 'Stock Split'),
    ]
    
    MOVEMENT_REASONS = [
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('SALES_ORDER', 'Sales Order'),
        ('TRANSFER_ORDER', 'Transfer Order'),
        ('WORK_ORDER', 'Work Order'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('CYCLE_COUNT', 'Cycle Count'),
        ('PHYSICAL_COUNT', 'Physical Inventory'),
        ('CUSTOMER_RETURN', 'Customer Return'),
        ('SUPPLIER_RETURN', 'Return to Supplier'),
        ('MANUFACTURING', 'Manufacturing Order'),
        ('QUALITY_CONTROL', 'Quality Control'),
        ('DAMAGE', 'Damaged Goods'),
        ('EXPIRY', 'Product Expiry'),
        ('THEFT', 'Theft/Loss'),
        ('SAMPLE', 'Sample/Demo'),
        ('CORRECTION', 'Data Correction'),
        ('SYSTEM_ADJUSTMENT', 'System Adjustment'),
        ('REVALUATION', 'Cost Revaluation'),
        ('OBSOLESCENCE', 'Obsolete Stock'),
        ('OTHER', 'Other'),
    ]
    
    MOVEMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('REVERSED', 'Reversed'),
    ]
    
    # Unique Movement Identifier
    movement_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    movement_number = models.CharField(max_length=50, blank=True)
    
    # Stock Item Reference
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='movements'
    )
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movements'
    )
    serial_number = models.ForeignKey(
        'stock.SerialNumber',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movements'
    )
    
    # Movement Details
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    movement_reason = models.CharField(max_length=20, choices=MOVEMENT_REASONS)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Stock Levels (before and after movement)
    stock_before = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stock_after = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Location Information
    from_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        related_name='movements_from',
        null=True, blank=True
    )
    to_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        related_name='movements_to',
        null=True, blank=True
    )
    
    # Generic Foreign Key for flexible document references
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_document = GenericForeignKey('content_type', 'object_id')
    
    # Document References (alternative to generic FK)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    document_url = models.URLField(blank=True)
    
    # Timing Information
    movement_date = models.DateTimeField(default=timezone.now)
    planned_date = models.DateTimeField(null=True, blank=True)
    actual_date = models.DateTimeField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    
    # User Information
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_movements'
    )
    authorized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='authorized_movements'
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requested_movements'
    )
    
    # Status & Workflow
    status = models.CharField(max_length=20, choices=MOVEMENT_STATUS, default='CONFIRMED')
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_movements'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Reversal Information
    is_reversal = models.BooleanField(default=False)
    reversed_movement = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reversals'
    )
    reversal_reason = models.TextField(blank=True)
    
    # Quality Information
    quality_status = models.CharField(
        max_length=20,
        choices=[
            ('PASSED', 'Quality Passed'),
            ('FAILED', 'Quality Failed'),
            ('PENDING', 'Quality Pending'),
            ('EXEMPT', 'Quality Exempt'),
        ],
        blank=True
    )
    quality_notes = models.TextField(blank=True)
    
    # Additional Information
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # System Information (for API tracking)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    api_source = models.CharField(max_length=50, blank=True)
    api_version = models.CharField(max_length=10, blank=True)
    
    # Integration & External System Tracking
    external_system_id = models.CharField(max_length=100, blank=True)
    external_system_name = models.CharField(max_length=50, blank=True)
    integration_status = models.CharField(max_length=20, default='SYNCED')
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_movements'
        ordering = ['-movement_date', '-id']
        indexes = [
            models.Index(fields=['tenant_id', 'stock_item', '-movement_date']),
            models.Index(fields=['tenant_id', 'movement_type', '-movement_date']),
            models.Index(fields=['tenant_id', 'movement_reason', '-movement_date']),
            models.Index(fields=['tenant_id', 'reference_type', 'reference_id']),
            models.Index(fields=['tenant_id', 'performed_by', '-movement_date']),
            models.Index(fields=['tenant_id', '-movement_date']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['movement_id']),  # For API lookups
        ]
    
    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.stock_item.product.sku} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Auto-generate movement number if not provided
        if not self.movement_number:
            self.movement_number = self.generate_movement_number()
        
        # Calculate total cost
        self.total_cost = self.quantity * self.unit_cost
        
        # Set actual date if not provided
        if not self.actual_date:
            self.actual_date = self.movement_date
        
        # Update status timestamps
        if self.status == 'CONFIRMED' and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_inbound(self):
        """Check if movement increases stock"""
        inbound_types = [
            'RECEIVE', 'PURCHASE', 'TRANSFER_IN', 'RETURN_IN', 'ADJUST_IN',
            'MANUFACTURING_IN', 'FOUND', 'CYCLE_COUNT_IN'
        ]
        return self.movement_type in inbound_types
    
    @property
    def is_outbound(self):
        """Check if movement decreases stock"""
        outbound_types = [
            'SHIP', 'SALE', 'TRANSFER_OUT', 'RETURN_OUT', 'ADJUST_OUT',
            'MANUFACTURING_OUT', 'DAMAGE', 'LOSS', 'EXPIRED', 'SAMPLE',
            'SCRAP', 'CYCLE_COUNT_OUT'
        ]
        return self.movement_type in outbound_types
    
    @property
    def is_internal(self):
        """Check if movement is internal (no quantity change)"""
        internal_types = [
            'RESERVE', 'RELEASE', 'ALLOCATE', 'PICK', 'RELOCATE',
            'QUARANTINE', 'RELEASE_QUARANTINE', 'QUALITY_HOLD', 'QUALITY_RELEASE'
        ]
        return self.movement_type in internal_types
    
    @property
    def cost_impact(self):
        """Calculate cost impact (positive for inbound, negative for outbound)"""
        if self.is_inbound:
            return self.total_cost
        elif self.is_outbound:
            return -self.total_cost
        return Decimal('0')
    
    @property
    def quantity_impact(self):
        """Calculate quantity impact on stock levels"""
        if self.is_inbound:
            return self.quantity
        elif self.is_outbound:
            return -self.quantity
        return Decimal('0')
    
    def generate_movement_number(self):
        """Generate unique movement number"""
        from datetime import datetime
        
        # Format: MOV-YYYYMMDD-NNNNNN
        today = datetime.now().strftime('%Y%m%d')
        
        # Get last movement number for today
        last_movement = StockMovement.objects.filter(
            tenant_id=self.tenant_id,
            movement_number__startswith=f'MOV-{today}'
        ).order_by('-movement_number').first()
        
        if last_movement:
            try:
                last_seq = int(last_movement.movement_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"MOV-{today}-{next_seq:06d}"
    
    def can_be_reversed(self):
        """Check if movement can be reversed"""
        # Business rules for reversal eligibility
        if self.status != 'CONFIRMED':
            return False, "Only confirmed movements can be reversed"
        
        if self.is_reversal:
            return False, "Cannot reverse a reversal movement"
        
        if hasattr(self, 'reversals') and self.reversals.exists():
            return False, "Movement has already been reversed"
        
        # Check if enough time has passed (business rule)
        hours_since_movement = (timezone.now() - self.movement_date).total_seconds() / 3600
        if hours_since_movement > 24:  # Example: 24-hour reversal window
            return False, "Reversal window has expired"
        
        return True, "Movement can be reversed"
    
    def reverse(self, reason, user=None):
        """Create reversal movement"""
        can_reverse, message = self.can_be_reversed()
        if not can_reverse:
            return False, message
        
        # Determine reverse movement type
        reverse_type_map = {
            'RECEIVE': 'ADJUST_OUT',
            'SHIP': 'ADJUST_IN',
            'TRANSFER_IN': 'TRANSFER_OUT',
            'TRANSFER_OUT': 'TRANSFER_IN',
            'ADJUST_IN': 'ADJUST_OUT',
            'ADJUST_OUT': 'ADJUST_IN',
        }
        
        reverse_type = reverse_type_map.get(self.movement_type)
        if not reverse_type:
            return False, f"Movement type {self.movement_type} cannot be reversed"
        
        # Create reversal movement
        reversal = StockMovement.objects.create(
            tenant_id=self.tenant_id,
            stock_item=self.stock_item,
            batch=self.batch,
            serial_number=self.serial_number,
            movement_type=reverse_type,
            movement_reason='CORRECTION',
            quantity=self.quantity,
            unit_cost=self.unit_cost,
            from_location=self.to_location,
            to_location=self.from_location,
            performed_by=user,
            is_reversal=True,
            reversed_movement=self,
            reversal_reason=reason,
            reference_type=self.reference_type,
            reference_id=self.reference_id,
            reason=f"Reversal of {self.movement_number}: {reason}"
        )
        
        # Update original movement status
        self.status = 'REVERSED'
        self.save(update_fields=['status'])
        
        return True, f"Movement reversed: {reversal.movement_number}"
    
    def get_related_movements(self):
        """Get related movements (same reference)"""
        if self.reference_type and self.reference_id:
            return StockMovement.objects.filter(
                tenant_id=self.tenant_id,
                reference_type=self.reference_type,
                reference_id=self.reference_id
            ).exclude(id=self.id)
        return StockMovement.objects.none()
    
    def get_movement_chain(self):
        """Get movement chain (reserve -> allocate -> pick -> ship)"""
        # This would return related movements in the fulfillment chain
        # Implementation depends on how reference_id is used to link movements
        pass
    
    class MovementSummary:
        """Helper class for movement analysis"""
        
        @staticmethod
        def get_period_summary(tenant_id, start_date, end_date, product=None):
            """Get movement summary for a period"""
            queryset = StockMovement.objects.filter(
                tenant_id=tenant_id,
                movement_date__range=[start_date, end_date],
                status='CONFIRMED'
            )
            
            if product:
                queryset = queryset.filter(stock_item__product=product)
            
            # Aggregate by movement type
            summary = queryset.values('movement_type').annotate(
                total_quantity=models.Sum('quantity'),
                total_value=models.Sum('total_cost'),
                count=models.Count('id')
            )
            
            return summary
        
        @staticmethod
        def get_velocity_analysis(tenant_id, days=90):
            """Analyze product velocity based on movements"""
            from django.db.models import Avg, Sum
            
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Analysis by product
            velocity_data = StockMovement.objects.filter(
                tenant_id=tenant_id,
                movement_date__range=[start_date, end_date],
                movement_type__in=['SHIP', 'SALE'],
                status='CONFIRMED'
            ).values('stock_item__product').annotate(
                total_shipped=Sum('quantity'),
                avg_shipment=Avg('quantity'),
                shipment_count=Count('id'),
                velocity_score=Sum('quantity') / days
            )
            
            return velocity_data