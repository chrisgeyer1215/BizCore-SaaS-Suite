"""
Advanced stock reservation system for inventory allocation
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from apps.core.models import TenantBaseModel
from ..abstract.auditable import AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class StockReservation(TenantBaseModel, AuditableMixin):
    """
    Advanced stock reservation management with priority and fulfillment tracking
    """
    
    RESERVATION_STATUS = [
        ('ACTIVE', 'Active'),
        ('PARTIAL_FULFILLED', 'Partially Fulfilled'),
        ('FULFILLED', 'Fulfilled'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
        ('PENDING', 'Pending Allocation'),
    ]
    
    RESERVATION_TYPES = [
        ('SALES_ORDER', 'Sales Order'),
        ('WORK_ORDER', 'Work Order'),
        ('TRANSFER_ORDER', 'Transfer Order'),
        ('SERVICE_ORDER', 'Service Order'),
        ('SAMPLE_REQUEST', 'Sample Request'),
        ('QUALITY_HOLD', 'Quality Hold'),
        ('CUSTOMER_HOLD', 'Customer Hold'),
        ('MANUAL', 'Manual Reservation'),
        ('BLANKET_ORDER', 'Blanket Order'),
        ('CONSIGNMENT', 'Consignment'),
        ('OTHER', 'Other'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    FULFILLMENT_STRATEGIES = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('FEFO', 'First Expired First Out'),
        ('NEAREST', 'Nearest Location'),
        ('CHEAPEST', 'Lowest Cost'),
        ('HIGHEST_QUALITY', 'Highest Quality'),
        ('MANUAL', 'Manual Selection'),
    ]
    
    # Basic Information
    reservation_number = models.CharField(max_length=100, blank=True)
    reservation_type = models.CharField(max_length=20, choices=RESERVATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
    fulfillment_strategy = models.CharField(
        max_length=20, 
        choices=FULFILLMENT_STRATEGIES, 
        default='FIFO'
    )
    
    # Source Document Reference (Generic Foreign Key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_document = GenericForeignKey('content_type', 'object_id')
    
    # Alternative Reference Fields
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Customer/Entity Information
    customer_id = models.CharField(max_length=50, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_contact = models.JSONField(default=dict, blank=True)
    
    # Reservation Scope
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reservations'
    )
    
    # Date Management
    reservation_date = models.DateTimeField(default=timezone.now)
    required_date = models.DateTimeField()
    promised_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField()
    fulfilled_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Workflow
    status = models.CharField(max_length=20, choices=RESERVATION_STATUS, default='PENDING')
    fulfilled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fulfilled_reservations'
    )
    
    # Auto-management Settings
    auto_release_on_expiry = models.BooleanField(default=True)
    auto_allocate = models.BooleanField(default=False)
    partial_fulfillment_allowed = models.BooleanField(default=True)
    
    # Notification Settings
    send_expiry_notifications = models.BooleanField(default=True)
    notification_lead_time_hours = models.IntegerField(default=24)
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    
    # Financial Information
    estimated_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reserved_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fulfilled_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Service Level & Performance
    service_level_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=95,
        help_text="Target service level percentage"
    )
    actual_service_level = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    lead_time_promised_hours = models.IntegerField(null=True, blank=True)
    lead_time_actual_hours = models.IntegerField(null=True, blank=True)
    
    # Special Requirements
    special_handling_required = models.BooleanField(default=False)
    special_handling_instructions = models.TextField(blank=True)
    temperature_controlled = models.BooleanField(default=False)
    hazmat_requirements = models.BooleanField(default=False)
    
    # Quality Requirements
    quality_grade_required = models.CharField(max_length=10, blank=True)
    batch_requirements = models.JSONField(default=dict, blank=True)
    expiry_requirements = models.JSONField(default=dict, blank=True)
    
    # Reason & Context
    business_reason = models.TextField()
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    
    # Escalation Management
    escalation_required = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='escalated_reservations'
    )
    escalation_reason = models.TextField(blank=True)
    
    # Integration & External References
    external_reservation_id = models.CharField(max_length=100, blank=True)
    crm_opportunity_id = models.CharField(max_length=100, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_reservations'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'reservation_number'], 
                name='unique_tenant_reservation_number'
            ),
        ]
        ordering = ['-reservation_date', '-priority']
        indexes = [
            models.Index(fields=['tenant_id', 'status', 'expiry_date']),
            models.Index(fields=['tenant_id', 'reservation_type', 'status']),
            models.Index(fields=['tenant_id', 'reference_type', 'reference_id']),
            models.Index(fields=['tenant_id', 'priority', 'required_date']),
            models.Index(fields=['tenant_id', 'customer_id']),
        ]
    
    def __str__(self):
        return f"Reservation {self.reservation_number} - {self.customer_name}"
    
    def clean(self):
        if not self.reservation_number:
            # Auto-generate reservation number
            last_reservation = StockReservation.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_reservation and last_reservation.reservation_number:
                try:
                    last_num = int(last_reservation.reservation_number.replace('RSV', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.reservation_number = f"RSV{last_num + 1:06d}"
    
    def allocate_stock(self, user=None):
        """Allocate stock for all reservation items"""
        if self.status not in ['PENDING', 'ACTIVE']:
            return False, f"Cannot allocate stock for reservation with status {self.status}"
        
        allocation_results = []
        
        for item in self.items.all():
            success, message = item.allocate_stock(user)
            if success:
                allocation_results.append(f"Line {item.line_number}: {message}")
            else:
                allocation_results.append(f"Line {item.line_number}: FAILED - {message}")
        
        # Update reservation status
        self.update_status_from_items()
        
        return True, f"Allocation completed. Results: {'; '.join(allocation_results)}"
    
    def fulfill_reservation(self, user):
        """Fulfill the complete reservation"""
        if self.status not in ['ACTIVE', 'PARTIAL_FULFILLED']:
            return False, f"Cannot fulfill reservation with status {self.status}"
        
        unfulfilled_items = self.items.exclude(status='FULFILLED').count()
        if unfulfilled_items > 0:
            if not self.partial_fulfillment_allowed:
                return False, f"{unfulfilled_items} items not yet fulfilled"
        
        self.fulfilled_by = user
        self.fulfilled_date = timezone.now()
        
        # Calculate performance metrics
        if self.lead_time_promised_hours:
            actual_hours = (self.fulfilled_date - self.reservation_date).total_seconds() / 3600
            self.lead_time_actual_hours = int(actual_hours)
            
            if actual_hours <= self.lead_time_promised_hours:
                self.actual_service_level = Decimal('100')
            else:
                delay_penalty = ((actual_hours - self.lead_time_promised_hours) / 
                               self.lead_time_promised_hours * 20)  # 20% penalty per promised time unit
                self.actual_service_level = max(Decimal('0'), Decimal('100') - Decimal(str(delay_penalty)))
        
        self.update_status_from_items()
        
        self.save(update_fields=[
            'fulfilled_by', 'fulfilled_date', 'lead_time_actual_hours', 
            'actual_service_level', 'status'
        ])
        
        return True, f"Reservation fulfilled - Service Level: {self.actual_service_level}%"
    
    def cancel_reservation(self, reason, user):
        """Cancel the reservation and release all stock"""
        if self.status in ['FULFILLED', 'CANCELLED']:
            return False, f"Cannot cancel reservation with status {self.status}"
        
        cancellation_results = []
        
        for item in self.items.all():
            success, message = item.release_allocation(reason, user)
            if success:
                cancellation_results.append(f"Line {item.line_number}: {message}")
            else:
                cancellation_results.append(f"Line {item.line_number}: FAILED - {message}")
        
        self.status = 'CANCELLED'
        self.internal_notes = f"Cancelled by {user.get_full_name()}: {reason}\n{self.internal_notes}"
        
        self.save(update_fields=['status', 'internal_notes'])
        
        return True, f"Reservation cancelled. Results: {'; '.join(cancellation_results)}"
    
    def extend_expiry(self, new_expiry_date, reason, user):
        """Extend the reservation expiry date"""
        if self.status not in ['ACTIVE', 'PARTIAL_FULFILLED']:
            return False, f"Cannot extend expired reservation with status {self.status}"
        
        if new_expiry_date <= self.expiry_date:
            return False, "New expiry date must be later than current expiry"
        
        old_expiry = self.expiry_date
        self.expiry_date = new_expiry_date
        self.internal_notes = (
            f"Expiry extended by {user.get_full_name()} from {old_expiry} to {new_expiry_date}: {reason}\n"
            f"{self.internal_notes}"
        )
        
        self.save(update_fields=['expiry_date', 'internal_notes'])
        
        return True, f"Expiry extended to {new_expiry_date}"
    
    def escalate(self, reason, escalate_to_user, user):
        """Escalate the reservation for management attention"""
        self.escalation_required = True
        self.escalated_at = timezone.now()
        self.escalated_to = escalate_to_user
        self.escalation_reason = reason
        self.internal_notes = f"Escalated by {user.get_full_name()} to {escalate_to_user.get_full_name()}: {reason}\n{self.internal_notes}"
        
        self.save(update_fields=[
            'escalation_required', 'escalated_at', 'escalated_to', 
            'escalation_reason', 'internal_notes'
        ])
        
        # Here you would send escalation notifications
        
        return True, f"Reservation escalated to {escalate_to_user.get_full_name()}"
    
    def update_status_from_items(self):
        """Update reservation status based on item statuses"""
        items = self.items.all()
        if not items.exists():
            return
        
        total_items = items.count()
        fulfilled_items = items.filter(status='FULFILLED').count()
        
        if fulfilled_items == 0:
            if items.filter(status__in=['ALLOCATED', 'RESERVED']).exists():
                self.status = 'ACTIVE'
            else:
                self.status = 'PENDING'
        elif fulfilled_items == total_items:
            self.status = 'FULFILLED'
        else:
            self.status = 'PARTIAL_FULFILLED'
        
        # Calculate financial values
        self.reserved_value = sum(item.reserved_value for item in items)
        self.fulfilled_value = sum(item.fulfilled_value for item in items)
        
        self.save(update_fields=['status', 'reserved_value', 'fulfilled_value'])
    
    def check_expiry(self):
        """Check if reservation has expired and handle accordingly"""
        if self.status in ['FULFILLED', 'CANCELLED', 'EXPIRED']:
            return False, "Reservation already finalized"
        
        if timezone.now() > self.expiry_date:
            if self.auto_release_on_expiry:
                # Auto-cancel expired reservation
                self.cancel_reservation("Auto-cancelled due to expiry", None)
            else:
                self.status = 'EXPIRED'
                self.save(update_fields=['status'])
            
            return True, "Reservation expired"
        
        return False, "Reservation not expired"
    
    def send_expiry_notification(self):
        """Send expiry notification if due"""
        if not self.send_expiry_notifications:
            return False, "Expiry notifications disabled"
        
        notification_time = self.expiry_date - timedelta(hours=self.notification_lead_time_hours)
        
        if timezone.now() >= notification_time:
            if not self.last_notification_sent or \
               self.last_notification_sent < notification_time:
                
                # Send notification logic would go here
                self.last_notification_sent = timezone.now()
                self.save(update_fields=['last_notification_sent'])
                
                return True, "Expiry notification sent"
        
        return False, "Notification not due yet"
    
    @property
    def is_expired(self):
        """Check if reservation is expired"""
        return timezone.now() > self.expiry_date
    
    @property
    def hours_until_expiry(self):
        """Hours until expiry"""
        if self.is_expired:
            return 0
        
        delta = self.expiry_date - timezone.now()
        return int(delta.total_seconds() / 3600)
    
    @property
    def fulfillment_percentage(self):
        """Percentage of reservation fulfilled"""
        if self.estimated_value > 0:
            return (self.fulfilled_value / self.estimated_value * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def priority_score(self):
        """Numerical priority score for sorting"""
        priority_scores = {
            'EMERGENCY': 1000,
            'CRITICAL': 900,
            'URGENT': 800,
            'HIGH': 600,
            'NORMAL': 400,
            'LOW': 200,
        }
        return priority_scores.get(self.priority, 0)


class StockReservationItem(TenantBaseModel):
    """
    Individual line items within stock reservations
    """
    
    ITEM_STATUS = [
        ('REQUESTED', 'Requested'),
        ('RESERVED', 'Stock Reserved'),
        ('ALLOCATED', 'Allocated'),
        ('PARTIAL_FULFILLED', 'Partially Fulfilled'),
        ('FULFILLED', 'Fulfilled'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
        ('BACKORDERED', 'Backordered'),
    ]
    
    reservation = models.ForeignKey(
        StockReservation,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='reservation_items'
    )
    variation = models.ForeignKey(
        'catalog.ProductVariation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reservation_items'
    )
    
    # Stock Source Preferences
    preferred_warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_reservation_items'
    )
    preferred_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_reservation_items'
    )
    preferred_batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_reservation_items'
    )
    
    # Allocated Stock Sources (actual allocations)
    allocated_stock_items = models.ManyToManyField(
        'stock.StockItem',
        through='ReservationAllocation',
        related_name='reservation_items'
    )
    
    # Quantities
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_fulfilled = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_backordered = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit Information
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='reservation_items'
    )
    
    # Cost Information
    estimated_unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reserved_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fulfilled_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Quality Requirements
    quality_grade_required = models.CharField(max_length=10, blank=True)
    min_expiry_days = models.IntegerField(null=True, blank=True)
    batch_selection_criteria = models.JSONField(default=dict, blank=True)
    
    # Status & Tracking
    status = models.CharField(max_length=20, choices=ITEM_STATUS, default='REQUESTED')
    allocated_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    # Special Requirements
    substitution_allowed = models.BooleanField(default=False)
    substitute_products = models.ManyToManyField(
        'catalog.Product',
        blank=True,
        related_name='substitute_for_reservations'
    )
    
    # Customer-Specific Requirements
    customer_part_number = models.CharField(max_length=100, blank=True)
    customer_specifications = models.JSONField(default=dict, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    fulfillment_notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_reservation_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'reservation', 'line_number'],
                name='unique_reservation_line_number'
            ),
        ]
        ordering = ['reservation', 'line_number']
        indexes = [
            models.Index(fields=['tenant_id', 'reservation']),
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'status']),
        ]
    
    def __str__(self):
        return f"{self.reservation.reservation_number} Line {self.line_number}: {self.product.name}"
    
    def allocate_stock(self, user=None):
        """Allocate stock for this reservation item"""
        if self.status not in ['REQUESTED', 'BACKORDERED']:
            return False, f"Cannot allocate stock for item with status {self.status}"
        
        from ..stock.items import StockItem
        
        # Find available stock based on preferences and strategy
        available_stock = self._find_available_stock()
        
        if not available_stock:
            self.status = 'BACKORDERED'
            self.quantity_backordered = self.quantity_requested - self.quantity_allocated
            self.save(update_fields=['status', 'quantity_backordered'])
            return False, "No available stock found"
        
        allocated_quantity = Decimal('0')
        remaining_quantity = self.quantity_requested - self.quantity_allocated
        
        for stock_item, available_qty in available_stock:
            if remaining_quantity <= 0:
                break
            
            qty_to_allocate = min(remaining_quantity, available_qty)
            
            # Reserve stock in the stock item
            success, message = stock_item.reserve_stock(
                qty_to_allocate,
                f"Reservation: {self.reservation.reservation_number}",
                str(self.reservation.id)
            )
            
            if success:
                # Create allocation record
                ReservationAllocation.objects.create(
                    tenant_id=self.tenant_id,
                    reservation_item=self,
                    stock_item=stock_item,
                    quantity_allocated=qty_to_allocate,
                    unit_cost=stock_item.average_cost,
                    allocated_by=user
                )
                
                allocated_quantity += qty_to_allocate
                remaining_quantity -= qty_to_allocate
        
        # Update quantities and status
        self.quantity_allocated += allocated_quantity
        self.reserved_value = self.quantity_allocated * self.estimated_unit_cost
        
        if self.quantity_allocated >= self.quantity_requested:
            self.status = 'ALLOCATED'
            self.allocated_at = timezone.now()
        elif self.quantity_allocated > 0:
            self.status = 'RESERVED'
            self.quantity_backordered = self.quantity_requested - self.quantity_allocated
        else:
            self.status = 'BACKORDERED'
            self.quantity_backordered = self.quantity_requested
        
        self.save(update_fields=[
            'quantity_allocated', 'reserved_value', 'status', 
            'allocated_at', 'quantity_backordered'
        ])
        
        return True, f"Allocated {allocated_quantity} units"
    
    def fulfill_item(self, quantity, user, notes=''):
        """Fulfill a portion or all of this reservation item"""
        quantity = Decimal(str(quantity))
        
        if self.status not in ['RESERVED', 'ALLOCATED', 'PARTIAL_FULFILLED']:
            return False, f"Cannot fulfill item with status {self.status}"
        
        if quantity > self.quantity_allocated:
            return False, f"Cannot fulfill more than allocated. Allocated: {self.quantity_allocated}"
        
        # Process fulfillment through allocations
        remaining_to_fulfill = quantity
        fulfilled_cost = Decimal('0')
        
        for allocation in self.allocations.filter(quantity_remaining__gt=0):
            if remaining_to_fulfill <= 0:
                break
            
            qty_to_fulfill = min(remaining_to_fulfill, allocation.quantity_remaining)
            success, cost = allocation.fulfill_allocation(qty_to_fulfill, user)
            
            if success:
                fulfilled_cost += cost
                remaining_to_fulfill -= qty_to_fulfill
        
        # Update item quantities and status
        self.quantity_fulfilled += (quantity - remaining_to_fulfill)
        self.fulfilled_value += fulfilled_cost
        
        if self.quantity_fulfilled >= self.quantity_requested:
            self.status = 'FULFILLED'
            self.fulfilled_at = timezone.now()
        elif self.quantity_fulfilled > 0:
            self.status = 'PARTIAL_FULFILLED'
        
        if notes:
            self.fulfillment_notes = f"{notes}\n{self.fulfillment_notes}" if self.fulfillment_notes else notes
        
        self.save(update_fields=[
            'quantity_fulfilled', 'fulfilled_value', 'status', 
            'fulfilled_at', 'fulfillment_notes'
        ])
        
        return True, f"Fulfilled {quantity - remaining_to_fulfill} units"
    
    def release_allocation(self, reason, user):
        """Release all allocated stock for this item"""
        if self.status not in ['RESERVED', 'ALLOCATED', 'PARTIAL_FULFILLED']:
            return False, f"Cannot release allocation for item with status {self.status}"
        
        release_results = []
        
        for allocation in self.allocations.all():
            success, message = allocation.release_allocation(reason, user)
            release_results.append(message)
        
        # Reset quantities and status
        self.quantity_allocated = Decimal('0')
        self.quantity_reserved = Decimal('0')
        self.reserved_value = Decimal('0')
        self.status = 'CANCELLED'
        
        self.notes = f"Released by {user.get_full_name() if user else 'System'}: {reason}\n{self.notes}"
        
        self.save(update_fields=[
            'quantity_allocated', 'quantity_reserved', 'reserved_value', 
            'status', 'notes'
        ])
        
        return True, f"Allocation released: {'; '.join(release_results)}"
    
    def _find_available_stock(self):
        """Find available stock based on fulfillment strategy"""
        from ..stock.items import StockItem
        
        # Base query for available stock
        queryset = StockItem.objects.filter(
            tenant_id=self.tenant_id,
            product=self.product,
            variation=self.variation,
            is_active=True,
            quantity_available__gt=0
        )
        
        # Apply warehouse preference
        if self.preferred_warehouse:
            queryset = queryset.filter(warehouse=self.preferred_warehouse)
        elif self.reservation.warehouse:
            queryset = queryset.filter(warehouse=self.reservation.warehouse)
        
        # Apply location preference
        if self.preferred_location:
            queryset = queryset.filter(location=self.preferred_location)
        
        # Apply batch preference
        if self.preferred_batch:
            queryset = queryset.filter(batch=self.preferred_batch)
        
        # Apply quality requirements
        if self.quality_grade_required:
            queryset = queryset.filter(batch__quality_grade=self.quality_grade_required)
        
        # Apply expiry requirements
        if self.min_expiry_days:
            min_expiry_date = timezone.now().date() + timedelta(days=self.min_expiry_days)
            queryset = queryset.filter(
                models.Q(batch__expiry_date__isnull=True) |
                models.Q(batch__expiry_date__gte=min_expiry_date)
            )
        
        # Apply fulfillment strategy ordering
        if self.reservation.fulfillment_strategy == 'FIFO':
            queryset = queryset.order_by('created_at')
        elif self.reservation.fulfillment_strategy == 'LIFO':
            queryset = queryset.order_by('-created_at')
        elif self.reservation.fulfillment_strategy == 'FEFO':
            queryset = queryset.order_by('batch__expiry_date')
        elif self.reservation.fulfillment_strategy == 'CHEAPEST':
            queryset = queryset.order_by('average_cost')
        elif self.reservation.fulfillment_strategy == 'HIGHEST_QUALITY':
            queryset = queryset.order_by('-batch__quality_grade')
        elif self.reservation.fulfillment_strategy == 'NEAREST':
            # Would need location-based sorting logic
            pass
        
        # Return list of (stock_item, available_quantity) tuples
        return [(item, item.quantity_available) for item in queryset]
    
    def save(self, *args, **kwargs):
        # Auto-assign line number
        if not self.line_number:
            last_line = StockReservationItem.objects.filter(
                reservation=self.reservation,
                tenant_id=self.tenant_id
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    @property
    def pending_quantity(self):
        """Quantity pending fulfillment"""
        return self.quantity_allocated - self.quantity_fulfilled
    
    @property
    def fulfillment_percentage(self):
        """Percentage of requested quantity fulfilled"""
        if self.quantity_requested > 0:
            return (self.quantity_fulfilled / self.quantity_requested * 100).quantize(Decimal('0.01'))
        return Decimal('0')


class ReservationAllocation(TenantBaseModel):
    """
    Junction table tracking specific stock allocations to reservations
    """
    
    reservation_item = models.ForeignKey(
        StockReservationItem,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='reservation_allocations'
    )
    
    # Allocation Details
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_fulfilled = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_remaining = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Cost Information
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Tracking Information
    allocated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_allocations'
    )
    allocated_at = models.DateTimeField(default=timezone.now)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_reservation_allocations'
        indexes = [
            models.Index(fields=['tenant_id', 'reservation_item']),
            models.Index(fields=['tenant_id', 'stock_item']),
            models.Index(fields=['tenant_id', 'is_active']),
        ]
    
    def __str__(self):
        return f"Allocation: {self.stock_item} → {self.reservation_item}"
    
    def save(self, *args, **kwargs):
        # Calculate derived fields
        self.quantity_remaining = self.quantity_allocated - self.quantity_fulfilled
        self.total_cost = self.quantity_allocated * self.unit_cost
        
        super().save(*args, **kwargs)
    
    def fulfill_allocation(self, quantity, user):
        """Fulfill a portion of this allocation"""
        quantity = Decimal(str(quantity))
        
        if quantity > self.quantity_remaining:
            return False, Decimal('0')
        
        # Ship the stock from the source stock item
        success, message = self.stock_item.ship_stock(
            quantity,
            f"Reservation fulfillment: {self.reservation_item.reservation.reservation_number}",
            str(self.reservation_item.reservation.id),
            user
        )
        
        if success:
            self.quantity_fulfilled += quantity
            self.quantity_remaining -= quantity
            
            if self.quantity_remaining == 0:
                self.fulfilled_at = timezone.now()
            
            cost = quantity * self.unit_cost
            
            self.save(update_fields=[
                'quantity_fulfilled', 'quantity_remaining', 'fulfilled_at'
            ])
            
            return True, cost
        
        return False, Decimal('0')
    
    def release_allocation(self, reason, user):
        """Release this allocation back to available stock"""
        if self.quantity_remaining == 0:
            return True, "Allocation already fulfilled"
        
        # Release the reservation from stock item
        success, message = self.stock_item.release_reservation(
            self.quantity_remaining,
            f"Reservation release: {reason}",
            str(self.reservation_item.reservation.id)
        )
        
        if success:
            self.is_active = False
            self.save(update_fields=['is_active'])
        
        return success, message


class ReservationFulfillment(TenantBaseModel):
    """
    Track fulfillment of stock reservations with detailed picking and shipping integration
    """
    
    FULFILLMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('PICKED', 'Picked'),
        ('PACKED', 'Packed'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('RETURNED', 'Returned'),
    ]
    
    FULFILLMENT_TYPES = [
        ('FULL', 'Full Fulfillment'),
        ('PARTIAL', 'Partial Fulfillment'),
        ('SPLIT', 'Split Fulfillment'),
        ('SUBSTITUTE', 'Substitute Product'),
        ('BACKORDER', 'Backorder'),
    ]
    
    # Reservation Reference
    reservation_item = models.ForeignKey(
        StockReservationItem,
        on_delete=models.CASCADE,
        related_name='fulfillments'
    )
    
    # Basic Information
    fulfillment_number = models.CharField(max_length=50, blank=True)
    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_TYPES, default='FULL')
    status = models.CharField(max_length=20, choices=FULFILLMENT_STATUS, default='PENDING')
    
    # Quantities
    quantity_to_fulfill = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_picked = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_packed = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_shipped = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_returned = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Stock Item & Location
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='fulfillments'
    )
    pick_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pick_fulfillments'
    )
    staging_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='staging_fulfillments'
    )
    
    # Batch/Serial Tracking
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fulfillments'
    )
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Timing Information
    planned_pick_date = models.DateTimeField(null=True, blank=True)
    actual_pick_date = models.DateTimeField(null=True, blank=True)
    planned_ship_date = models.DateTimeField(null=True, blank=True)
    actual_ship_date = models.DateTimeField(null=True, blank=True)
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Personnel
    assigned_picker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_fulfillments'
    )
    picked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='picked_fulfillments'
    )
    packed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='packed_fulfillments'
    )
    shipped_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shipped_fulfillments'
    )
    
    # Shipping Information
    carrier = models.CharField(max_length=100, blank=True)
    service_level = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    package_weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    package_dimensions = models.JSONField(default=dict, blank=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Quality & Condition
    quality_check_required = models.BooleanField(default=False)
    quality_check_passed = models.BooleanField(default=True)
    quality_notes = models.TextField(blank=True)
    condition_at_pick = models.CharField(max_length=50, blank=True)
    condition_at_delivery = models.CharField(max_length=50, blank=True)
    
    # Customer Information
    delivery_address = models.JSONField(default=dict, blank=True)
    delivery_instructions = models.TextField(blank=True)
    customer_contact = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Performance Metrics
    pick_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    pack_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    transit_time_hours = models.PositiveIntegerField(null=True, blank=True)
    
    # Cost Information
    pick_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pack_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fulfillment_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Substitute Product Information (for substitution fulfillments)
    is_substitution = models.BooleanField(default=False)
    original_product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='original_fulfillments'
    )
    substitute_reason = models.TextField(blank=True)
    customer_approved_substitution = models.BooleanField(default=False)
    
    # Exception Handling
    has_exceptions = models.BooleanField(default=False)
    exception_notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Integration & External Systems
    wms_fulfillment_id = models.CharField(max_length=100, blank=True)
    tms_shipment_id = models.CharField(max_length=100, blank=True)
    erp_fulfillment_id = models.CharField(max_length=100, blank=True)
    
    # Additional Information
    priority_level = models.CharField(max_length=10, default='NORMAL')
    rush_order = models.BooleanField(default=False)
    special_handling = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_reservation_fulfillments'
        ordering = ['-created_at', '-planned_ship_date']
        indexes = [
            models.Index(fields=['tenant_id', 'reservation_item', 'status']),
            models.Index(fields=['tenant_id', 'status', 'planned_pick_date']),
            models.Index(fields=['tenant_id', 'assigned_picker', 'status']),
            models.Index(fields=['tenant_id', 'stock_item', 'status']),
            models.Index(fields=['tenant_id', 'tracking_number']),
            models.Index(fields=['tenant_id', 'carrier', 'actual_ship_date']),
        ]
    
    def __str__(self):
        return f"Fulfillment {self.fulfillment_number}: {self.stock_item.product.name} - {self.quantity_to_fulfill} units"
    
    def clean(self):
        if not self.fulfillment_number:
            self.fulfillment_number = self.generate_fulfillment_number()
    
    def generate_fulfillment_number(self):
        """Generate unique fulfillment number"""
        today = timezone.now().strftime('%Y%m%d')
        last_fulfillment = ReservationFulfillment.objects.filter(
            tenant_id=self.tenant_id,
            fulfillment_number__startswith=f'FF-{today}'
        ).order_by('-fulfillment_number').first()
        
        if last_fulfillment:
            try:
                last_seq = int(last_fulfillment.fulfillment_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"FF-{today}-{next_seq:06d}"
    
    @property
    def quantity_remaining(self):
        """Quantity still to be fulfilled"""
        return self.quantity_to_fulfill - self.quantity_shipped
    
    @property
    def fulfillment_percentage(self):
        """Percentage of fulfillment completed"""
        if self.quantity_to_fulfill > 0:
            return (self.quantity_shipped / self.quantity_to_fulfill * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_overdue(self):
        """Check if fulfillment is overdue"""
        if self.planned_ship_date and self.status in ['PENDING', 'PICKED', 'PACKED']:
            return timezone.now() > self.planned_ship_date
        return False
    
    @property
    def days_overdue(self):
        """Number of days overdue"""
        if self.is_overdue:
            return (timezone.now() - self.planned_ship_date).days
        return 0
    
    @property
    def is_express_shipment(self):
        """Check if this is an express/rush shipment"""
        return self.rush_order or 'EXPRESS' in self.service_level.upper()
    
    def assign_picker(self, picker, planned_pick_date=None):
        """Assign picker to this fulfillment"""
        if self.status != 'PENDING':
            return False, f"Cannot assign picker - status is {self.status}"
        
        self.assigned_picker = picker
        if planned_pick_date:
            self.planned_pick_date = planned_pick_date
        
        self.save(update_fields=['assigned_picker', 'planned_pick_date'])
        
        return True, f"Assigned to {picker.get_full_name()}"
    
    def start_picking(self, picker):
        """Start the picking process"""
        if self.status != 'PENDING':
            return False, f"Cannot start picking - status is {self.status}"
        
        if self.assigned_picker and self.assigned_picker != picker:
            return False, f"Assigned to different picker: {self.assigned_picker.get_full_name()}"
        
        # Check stock availability
        if self.stock_item.available_quantity < self.quantity_to_fulfill:
            return False, f"Insufficient stock. Available: {self.stock_item.available_quantity}"
        
        # Update pick start time for performance tracking
        self.actual_pick_date = timezone.now()
        self.picked_by = picker
        
        self.save(update_fields=['actual_pick_date', 'picked_by'])
        
        return True, "Picking started"
    
    def complete_picking(self, quantity_picked, picker, batch=None, serial_numbers=None):
        """Complete the picking process"""
        if self.status != 'PENDING':
            return False, f"Cannot complete picking - status is {self.status}"
        
        if quantity_picked > self.quantity_to_fulfill:
            return False, f"Cannot pick more than required. Required: {self.quantity_to_fulfill}"
        
        self.quantity_picked = quantity_picked
        self.status = 'PICKED'
        self.picked_by = picker
        
        if batch:
            self.batch = batch
        
        if serial_numbers:
            self.serial_numbers = serial_numbers
        
        # Calculate pick time
        if self.actual_pick_date:
            pick_duration = timezone.now() - self.actual_pick_date
            self.pick_time_minutes = int(pick_duration.total_seconds() / 60)
        
        self.save(update_fields=[
            'quantity_picked', 'status', 'picked_by', 'batch', 
            'serial_numbers', 'pick_time_minutes'
        ])
        
        return True, f"Picked {quantity_picked} units"
    
    def pack_items(self, packer, package_weight=None, dimensions=None):
        """Pack the picked items"""
        if self.status != 'PICKED':
            return False, f"Cannot pack - status is {self.status}"
        
        pack_start_time = timezone.now()
        
        self.quantity_packed = self.quantity_picked
        self.status = 'PACKED'
        self.packed_by = packer
        
        if package_weight:
            self.package_weight = package_weight
        
        if dimensions:
            self.package_dimensions = dimensions
        
        # Calculate pack time
        if self.actual_pick_date:
            pack_duration = pack_start_time - self.actual_pick_date
            self.pack_time_minutes = int(pack_duration.total_seconds() / 60)
        
        self.save(update_fields=[
            'quantity_packed', 'status', 'packed_by', 'package_weight',
            'package_dimensions', 'pack_time_minutes'
        ])
        
        return True, f"Packed {self.quantity_packed} units"
    
    def ship_items(self, shipper, carrier, tracking_number, service_level=''):
        """Ship the packed items"""
        if self.status != 'PACKED':
            return False, f"Cannot ship - status is {self.status}"
        
        self.quantity_shipped = self.quantity_packed
        self.status = 'SHIPPED'
        self.shipped_by = shipper
        self.carrier = carrier
        self.tracking_number = tracking_number
        self.service_level = service_level
        self.actual_ship_date = timezone.now()
        
        # Set estimated delivery date based on service level
        if 'OVERNIGHT' in service_level.upper() or 'EXPRESS' in service_level.upper():
            self.estimated_delivery_date = self.actual_ship_date + timedelta(days=1)
        elif 'GROUND' in service_level.upper():
            self.estimated_delivery_date = self.actual_ship_date + timedelta(days=3)
        else:
            self.estimated_delivery_date = self.actual_ship_date + timedelta(days=5)
        
        self.save(update_fields=[
            'quantity_shipped', 'status', 'shipped_by', 'carrier',
            'tracking_number', 'service_level', 'actual_ship_date',
            'estimated_delivery_date'
        ])
        
        # Update reservation item fulfillment
        self.reservation_item.update_fulfillment_status()
        
        return True, f"Shipped {self.quantity_shipped} units with tracking {tracking_number}"
    
    def confirm_delivery(self, delivery_date=None):
        """Confirm delivery of shipment"""
        if self.status != 'SHIPPED':
            return False, f"Cannot confirm delivery - status is {self.status}"
        
        self.status = 'DELIVERED'
        self.quantity_delivered = self.quantity_shipped
        self.actual_delivery_date = delivery_date or timezone.now()
        
        # Calculate transit time
        if self.actual_ship_date and self.actual_delivery_date:
            transit_duration = self.actual_delivery_date - self.actual_ship_date
            self.transit_time_hours = int(transit_duration.total_seconds() / 3600)
        
        self.save(update_fields=[
            'status', 'quantity_delivered', 'actual_delivery_date', 'transit_time_hours'
        ])
        
        # Update reservation item fulfillment
        self.reservation_item.update_fulfillment_status()
        
        return True, f"Delivery confirmed for {self.quantity_delivered} units"
    
    def process_return(self, return_quantity, reason, user):
        """Process returned items"""
        if return_quantity > self.quantity_delivered:
            return False, f"Cannot return more than delivered. Delivered: {self.quantity_delivered}"
        
        self.quantity_returned = return_quantity
        if return_quantity == self.quantity_delivered:
            self.status = 'RETURNED'
        
        self.notes += f"\nReturn processed by {user.get_full_name()}: {return_quantity} units - {reason}"
        
        self.save(update_fields=['quantity_returned', 'status', 'notes'])
        
        # Return stock to inventory
        success, message = self.stock_item.receive_stock(
            return_quantity,
            self.stock_item.unit_cost,
            f"Customer return: {reason}",
            reference_id=str(self.id),
            user=user
        )
        
        return success, f"Return processed: {message}"
    
    def cancel_fulfillment(self, reason, user):
        """Cancel this fulfillment"""
        if self.status in ['SHIPPED', 'DELIVERED']:
            return False, f"Cannot cancel - status is {self.status}"
        
        self.status = 'CANCELLED'
        self.notes += f"\nCancelled by {user.get_full_name()}: {reason}"
        
        self.save(update_fields=['status', 'notes'])
        
        # Release any allocated stock
        if self.status in ['PICKED', 'PACKED']:
            # Return picked quantity to available stock
            success, message = self.stock_item.release_allocation(
                self.quantity_picked,
                f"Fulfillment cancelled: {reason}",
                str(self.reservation_item.id)
            )
            
            if not success:
                return False, f"Failed to release stock: {message}"
        
        return True, "Fulfillment cancelled"
    
    def get_performance_metrics(self):
        """Get fulfillment performance metrics"""
        metrics = {
            'fulfillment_rate': self.fulfillment_percentage,
            'pick_time_minutes': self.pick_time_minutes,
            'pack_time_minutes': self.pack_time_minutes,
            'transit_time_hours': self.transit_time_hours,
            'total_fulfillment_cost': self.total_fulfillment_cost,
        }
        
        # Calculate on-time performance
        if self.actual_ship_date and self.planned_ship_date:
            on_time = self.actual_ship_date <= self.planned_ship_date
            metrics['shipped_on_time'] = on_time
            
        if self.actual_delivery_date and self.estimated_delivery_date:
            delivered_on_time = self.actual_delivery_date <= self.estimated_delivery_date
            metrics['delivered_on_time'] = delivered_on_time
        
        return metrics
    
    @classmethod
    def get_fulfillment_analytics(cls, tenant_id, date_range=None, picker=None):
        """Get fulfillment performance analytics"""
        from django.db.models import Avg, Sum, Count, F, Q
        
        queryset = cls.objects.filter(tenant_id=tenant_id)
        
        if date_range:
            start_date, end_date = date_range
            queryset = queryset.filter(actual_ship_date__range=[start_date, end_date])
        
        if picker:
            queryset = queryset.filter(picked_by=picker)
        
        analytics = queryset.aggregate(
            total_fulfillments=Count('id'),
            avg_pick_time=Avg('pick_time_minutes'),
            avg_pack_time=Avg('pack_time_minutes'),
            avg_transit_time=Avg('transit_time_hours'),
            total_quantity_shipped=Sum('quantity_shipped'),
            total_fulfillment_cost=Sum('total_fulfillment_cost'),
            on_time_shipments=Count('id', filter=Q(
                actual_ship_date__lte=F('planned_ship_date')
            )),
        )
        
        # Calculate on-time percentage
        if analytics['total_fulfillments'] > 0:
            analytics['on_time_percentage'] = (
                analytics['on_time_shipments'] / analytics['total_fulfillments'] * 100
            )
        else:
            analytics['on_time_percentage'] = 0
        
        return analytics