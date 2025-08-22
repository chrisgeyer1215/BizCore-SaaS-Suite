"""
Cycle counting and physical inventory management
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from apps.core.models import TenantBaseModel
from ..abstract.auditable import AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class CycleCount(TenantBaseModel, AuditableMixin):
    """
    Cycle counting management with comprehensive planning and execution
    """
    
    COUNT_STATUS = [
        ('PLANNED', 'Planned'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
    ]
    
    COUNT_TYPES = [
        ('CYCLE', 'Cycle Count'),
        ('PHYSICAL', 'Physical Inventory'),
        ('SPOT', 'Spot Count'),
        ('ABC', 'ABC Count'),
        ('LOCATION', 'Location Count'),
        ('PRODUCT', 'Product Count'),
        ('EXCEPTION', 'Exception Count'),
        ('BLIND', 'Blind Count'),
    ]
    
    COUNT_METHODS = [
        ('MANUAL', 'Manual Count'),
        ('BARCODE', 'Barcode Scanning'),
        ('RFID', 'RFID Scanning'),
        ('VOICE', 'Voice-Directed'),
        ('MOBILE', 'Mobile Device'),
    ]
    
    # Basic Information
    count_number = models.CharField(max_length=100, blank=True)
    count_type = models.CharField(max_length=20, choices=COUNT_TYPES, default='CYCLE')
    count_method = models.CharField(max_length=20, choices=COUNT_METHODS, default='MANUAL')
    
    # Scope Definition
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='cycle_counts'
    )
    locations = models.ManyToManyField(
        'warehouse.StockLocation',
        blank=True,
        related_name='cycle_counts'
    )
    products = models.ManyToManyField(
        'catalog.Product',
        blank=True,
        related_name='cycle_counts'
    )
    categories = models.ManyToManyField(
        'core.Category',
        blank=True,
        related_name='cycle_counts'
    )
    
    # ABC/Classification Filters
    abc_class = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        blank=True
    )
    xyz_class = models.CharField(
        max_length=1,
        choices=[('X', 'Class X'), ('Y', 'Class Y'), ('Z', 'Class Z')],
        blank=True
    )
    
    # Date Management
    planned_date = models.DateField(null=True, blank=True)
    scheduled_date = models.DateField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    cutoff_date = models.DateTimeField(null=True, blank=True)
    freeze_start = models.DateTimeField(null=True, blank=True)
    freeze_end = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=COUNT_STATUS, default='PLANNED')
    count_supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supervised_cycle_counts'
    )
    assigned_counters = models.ManyToManyField(
        User,
        blank=True,
        related_name='assigned_cycle_counts'
    )
    
    # Count Parameters
    allow_multiple_counts = models.BooleanField(default=True)
    require_recount = models.BooleanField(default=False)
    blind_count = models.BooleanField(default=False)
    freeze_transactions = models.BooleanField(default=True)
    
    # Tolerance Settings
    variance_tolerance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=5,
        help_text="Acceptable variance percentage"
    )
    variance_tolerance_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=100,
        help_text="Acceptable variance amount"
    )
    require_supervisor_approval = models.BooleanField(default=True)
    auto_adjust_within_tolerance = models.BooleanField(default=False)
    
    # Results Summary
    total_items_to_count = models.PositiveIntegerField(default=0)
    items_counted = models.PositiveIntegerField(default=0)
    items_with_variance = models.PositiveIntegerField(default=0)
    items_requiring_recount = models.PositiveIntegerField(default=0)
    total_variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    positive_variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    negative_variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Performance Metrics
    count_accuracy_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    average_count_time_per_item = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Average time in minutes per item"
    )
    total_count_duration_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    
    # Business Impact
    business_disruption_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Hours of business disruption caused"
    )
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Instructions & Documentation
    counting_instructions = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    safety_requirements = models.TextField(blank=True)
    
    # Quality Control
    verification_required = models.BooleanField(default=True)
    verification_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        help_text="Percentage of items to verify"
    )
    verification_completed = models.BooleanField(default=False)
    
    # Reporting
    preliminary_report_generated = models.BooleanField(default=False)
    final_report_generated = models.BooleanField(default=False)
    management_report_sent = models.BooleanField(default=False)
    
    # Additional Information
    notes = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    improvement_recommendations = models.TextField(blank=True)
    
    # Document Management
    count_sheets = models.JSONField(default=list, blank=True)
    photos = models.JSONField(default=list, blank=True)
    reports = models.JSONField(default=list, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_cycle_counts'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'count_number'], 
                name='unique_tenant_count_number'
            ),
        ]
        ordering = ['-scheduled_date', '-id']
        indexes = [
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
            models.Index(fields=['tenant_id', 'status', 'scheduled_date']),
            models.Index(fields=['tenant_id', 'count_type', 'status']),
            models.Index(fields=['tenant_id', 'count_supervisor']),
        ]
    
    def __str__(self):
        return f"Count {self.count_number} - {self.warehouse.name}"
    
    def clean(self):
        if not self.count_number:
            # Auto-generate count number
            last_count = CycleCount.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_count and last_count.count_number:
                try:
                    last_num = int(last_count.count_number.replace('CNT', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.count_number = f"CNT{last_num + 1:06d}"
    
    def generate_count_items(self):
        """Generate count items based on scope criteria"""
        if self.status not in ['PLANNED', 'SCHEDULED']:
            return False, f"Cannot generate items for count with status {self.status}"
        
        from ..stock.items import StockItem
        
        # Build query based on scope
        queryset = StockItem.objects.filter(
            tenant_id=self.tenant_id,
            warehouse=self.warehouse,
            is_active=True,
            quantity_on_hand__gt=0  # Only count items with stock
        )
        
        # Apply location filters
        if self.locations.exists():
            queryset = queryset.filter(location__in=self.locations.all())
        
        # Apply product filters
        if self.products.exists():
            queryset = queryset.filter(product__in=self.products.all())
        
        # Apply category filters
        if self.categories.exists():
            queryset = queryset.filter(product__category__in=self.categories.all())
        
        # Apply ABC classification filter
        if self.abc_class:
            queryset = queryset.filter(abc_classification=self.abc_class)
        
        # Apply XYZ classification filter
        if self.xyz_class:
            queryset = queryset.filter(xyz_classification=self.xyz_class)
        
        # Create count items
        count_items_created = 0
        for stock_item in queryset:
            count_item, created = CycleCountItem.objects.get_or_create(
                tenant_id=self.tenant_id,
                cycle_count=self,
                stock_item=stock_item,
                defaults={
                    'location': stock_item.location,
                    'batch': stock_item.batch,
                    'system_quantity': stock_item.quantity_on_hand,
                    'unit_cost': stock_item.average_cost,
                }
            )
            if created:
                count_items_created += 1
        
        self.total_items_to_count = count_items_created
        self.save(update_fields=['total_items_to_count'])
        
        return True, f"Generated {count_items_created} count items"
    
    def start_count(self, user):
        """Start the cycle count process"""
        if self.status != 'SCHEDULED':
            return False, f"Cannot start count with status {self.status}"
        
        if self.total_items_to_count == 0:
            success, message = self.generate_count_items()
            if not success:
                return False, f"Failed to generate count items: {message}"
        
        self.status = 'IN_PROGRESS'
        self.start_date = timezone.now().date()
        self.count_supervisor = user
        
        # Set cutoff time for inventory freeze
        if self.freeze_transactions:
            self.cutoff_date = timezone.now()
            self.freeze_start = timezone.now()
        
        self.save(update_fields=[
            'status', 'start_date', 'count_supervisor', 
            'cutoff_date', 'freeze_start'
        ])
        
        return True, "Cycle count started successfully"
    
    def complete_count(self, user):
        """Complete the cycle count process"""
        if self.status != 'IN_PROGRESS':
            return False, f"Cannot complete count with status {self.status}"
        
        # Check if all items are counted
        uncounted_items = self.items.filter(counted_quantity__isnull=True).count()
        if uncounted_items > 0:
            return False, f"{uncounted_items} items still need to be counted"
        
        # Check if recounts are required and completed
        recount_required = self.items.filter(
            recount_required=True,
            recount_completed=False
        ).count()
        if recount_required > 0:
            return False, f"{recount_required} items require recounting"
        
        self.status = 'COMPLETED'
        self.end_date = timezone.now().date()
        
        # End freeze period
        if self.freeze_transactions:
            self.freeze_end = timezone.now()
        
        # Calculate summary statistics
        self.calculate_summary_stats()
        
        self.save(update_fields=[
            'status', 'end_date', 'freeze_end',
            'items_counted', 'items_with_variance', 'total_variance_value',
            'count_accuracy_percentage'
        ])
        
        # Generate preliminary report
        self.generate_preliminary_report()
        
        return True, "Cycle count completed successfully"
    
    def calculate_summary_stats(self):
        """Calculate summary statistics from count items"""
        items = self.items.all()
        
        self.items_counted = items.filter(counted_quantity__isnull=False).count()
        self.items_with_variance = items.filter(variance_quantity__ne=0).count()
        self.items_requiring_recount = items.filter(recount_required=True).count()
        
        # Calculate variance values
        positive_variance = items.filter(variance_value__gt=0).aggregate(
            total=models.Sum('variance_value')
        )['total'] or Decimal('0')
        
        negative_variance = items.filter(variance_value__lt=0).aggregate(
            total=models.Sum('variance_value')
        )['total'] or Decimal('0')
        
        self.positive_variance_value = positive_variance
        self.negative_variance_value = abs(negative_variance)
        self.total_variance_value = positive_variance + abs(negative_variance)
        
        # Calculate accuracy
        if self.items_counted > 0:
            accurate_items = self.items_counted - self.items_with_variance
            self.count_accuracy_percentage = (
                accurate_items / self.items_counted * 100
            ).quantize(Decimal('0.01'))
    
    def generate_preliminary_report(self):
        """Generate preliminary count report"""
        if self.preliminary_report_generated:
            return True, "Preliminary report already generated"
        
        # Report generation logic would go here
        # This could include PDF generation, data export, etc.
        
        self.preliminary_report_generated = True
        self.save(update_fields=['preliminary_report_generated'])
        
        return True, "Preliminary report generated"
    
    def approve_results(self, user, notes=''):
        """Approve cycle count results"""
        if self.status != 'COMPLETED':
            return False, f"Cannot approve count with status {self.status}"
        
        self.status = 'APPROVED'
        self.notes = f"Approved by {user.get_full_name()}: {notes}\n{self.notes}"
        
        self.save(update_fields=['status', 'notes'])
        
        # Auto-generate adjustments if configured
        if self.auto_adjust_within_tolerance:
            self.generate_adjustments(user)
        
        return True, "Cycle count results approved"
    
    def generate_adjustments(self, user):
        """Generate stock adjustments for variances"""
        from .adjustments import StockAdjustment, StockAdjustmentItem
        
        # Get items with variances that need adjustment
        variance_items = self.items.filter(
            variance_quantity__ne=0,
            adjustment_approved=True
        )
        
        if not variance_items.exists():
            return False, "No variance items found for adjustment"
        
        # Create adjustment
        adjustment = StockAdjustment.objects.create(
            tenant_id=self.tenant_id,
            adjustment_type='CORRECTION',
            warehouse=self.warehouse,
            cycle_count=self,
            business_reason=f"Cycle count adjustment from {self.count_number}",
            created_by=user
        )
        
        # Create adjustment items
        for count_item in variance_items:
            StockAdjustmentItem.objects.create(
                tenant_id=self.tenant_id,
                adjustment=adjustment,
                stock_item=count_item.stock_item,
                location=count_item.location,
                batch=count_item.batch,
                quantity_before=count_item.system_quantity,
                quantity_adjustment=count_item.variance_quantity,
                unit_cost_before=count_item.unit_cost,
                unit_cost_after=count_item.unit_cost,
                reason=f"Cycle count variance - {count_item.variance_reason or 'No reason specified'}"
            )
        
        # Auto-approve and post if within tolerance
        if self._all_variances_within_tolerance(variance_items):
            adjustment.approve(user, 'Auto-approved - all variances within tolerance')
            
        return True, f"Generated adjustment {adjustment.adjustment_number}"
    
    def _all_variances_within_tolerance(self, variance_items):
        """Check if all variances are within tolerance"""
        for item in variance_items:
            if not item.is_within_tolerance(self.variance_tolerance_percentage, self.variance_tolerance_amount):
                return False
        return True
    
    @property
    def completion_percentage(self):
        """Percentage of items counted"""
        if self.total_items_to_count > 0:
            return (self.items_counted / self.total_items_to_count * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def variance_percentage(self):
        """Percentage of items with variances"""
        if self.items_counted > 0:
            return (self.items_with_variance / self.items_counted * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_overdue(self):
        """Check if count is overdue"""
        if self.scheduled_date and self.status in ['SCHEDULED', 'IN_PROGRESS']:
            return self.scheduled_date < timezone.now().date()
        return False


class CycleCountItem(TenantBaseModel):
    """
    Individual items within a cycle count with variance tracking
    """
    
    VARIANCE_STATUS = [
        ('NO_VARIANCE', 'No Variance'),
        ('MINOR_VARIANCE', 'Minor Variance'),
        ('MAJOR_VARIANCE', 'Major Variance'),
        ('CRITICAL_VARIANCE', 'Critical Variance'),
        ('PENDING_RECOUNT', 'Pending Recount'),
        ('APPROVED', 'Approved'),
        ('ADJUSTED', 'Adjusted'),
    ]
    
    cycle_count = models.ForeignKey(
        CycleCount,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Product & Location References
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='cycle_count_items'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.CASCADE,
        related_name='cycle_count_items'
    )
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cycle_count_items'
    )
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Count Information
    system_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    variance_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    variance_percentage = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    
    # Cost Impact
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Count Details
    counted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='counted_items'
    )
    counted_at = models.DateTimeField(null=True, blank=True)
    count_method = models.CharField(max_length=20, blank=True)
    
    # Recount Information
    recount_required = models.BooleanField(default=False)
    recount_completed = models.BooleanField(default=False)
    recount_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recounted_items'
    )
    recount_at = models.DateTimeField(null=True, blank=True)
    original_count = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Status & Approval
    variance_status = models.CharField(max_length=20, choices=VARIANCE_STATUS, default='NO_VARIANCE')
    adjustment_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_count_items'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Quality Information
    condition_notes = models.TextField(blank=True)
    quality_issues = models.TextField(blank=True)
    damage_noted = models.BooleanField(default=False)
    
    # Variance Analysis
    variance_reason = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    
    # Count Verification
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_count_items'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_cycle_count_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'cycle_count', 'stock_item', 'location'],
                name='unique_count_stock_item'
            ),
        ]
        ordering = ['cycle_count', 'location', 'stock_item']
        indexes = [
            models.Index(fields=['tenant_id', 'cycle_count']),
            models.Index(fields=['tenant_id', 'variance_status']),
            models.Index(fields=['tenant_id', 'counted_by']),
            models.Index(fields=['tenant_id', 'recount_required']),
        ]
    
    def __str__(self):
        return f"{self.cycle_count.count_number}: {self.stock_item}"
    
    def record_count(self, counted_quantity, user, count_method='MANUAL', notes=''):
        """Record the physical count"""
        if self.counted_quantity is not None and not self.cycle_count.allow_multiple_counts:
            return False, "Item already counted and multiple counts not allowed"
        
        self.counted_quantity = Decimal(str(counted_quantity))
        self.counted_by = user
        self.counted_at = timezone.now()
        self.count_method = count_method
        
        if notes:
            self.notes = f"{notes}\n{self.notes}" if self.notes else notes
        
        # Calculate variance
        self.calculate_variance()
        
        self.save(update_fields=[
            'counted_quantity', 'counted_by', 'counted_at', 'count_method',
            'variance_quantity', 'variance_percentage', 'variance_value',
            'variance_status', 'recount_required', 'notes'
        ])
        
        return True, f"Count recorded: {counted_quantity}"
    
    def calculate_variance(self):
        """Calculate variance when counted quantity is entered"""
        if self.counted_quantity is None:
            return
        
        self.variance_quantity = self.counted_quantity - self.system_quantity
        
        # Calculate percentage variance
        if self.system_quantity != 0:
            self.variance_percentage = (
                self.variance_quantity / self.system_quantity * 100
            ).quantize(Decimal('0.001'))
        else:
            self.variance_percentage = Decimal('100') if self.counted_quantity > 0 else Decimal('0')
        
        # Calculate value variance
        self.variance_value = self.variance_quantity * self.unit_cost
        
        # Determine variance status
        tolerance_pct = self.cycle_count.variance_tolerance_percentage
        tolerance_amt = self.cycle_count.variance_tolerance_amount
        abs_variance_pct = abs(self.variance_percentage)
        abs_variance_val = abs(self.variance_value)
        
        if self.variance_quantity == 0:
            self.variance_status = 'NO_VARIANCE'
        elif (abs_variance_pct <= tolerance_pct and abs_variance_val <= tolerance_amt):
            self.variance_status = 'MINOR_VARIANCE'
        elif (abs_variance_pct <= tolerance_pct * 2 and abs_variance_val <= tolerance_amt * 2):
            self.variance_status = 'MAJOR_VARIANCE'
        else:
            self.variance_status = 'CRITICAL_VARIANCE'
        
        # Determine if recount is required
        if self.variance_status in ['MAJOR_VARIANCE', 'CRITICAL_VARIANCE']:
            self.recount_required = True
        elif self.cycle_count.require_recount and self.variance_status != 'NO_VARIANCE':
            self.recount_required = True
    
    def record_recount(self, recounted_quantity, user, notes=''):
        """Record a recount for this item"""
        if not self.recount_required:
            return False, "Recount not required for this item"
        
        if self.recount_completed:
            return False, "Recount already completed"
        
        # Store original count
        self.original_count = self.counted_quantity
        
        # Update with recount
        self.counted_quantity = Decimal(str(recounted_quantity))
        self.recount_by = user
        self.recount_at = timezone.now()
        self.recount_completed = True
        
        if notes:
            self.notes = f"Recount: {notes}\n{self.notes}" if self.notes else f"Recount: {notes}"
        
        # Recalculate variance
        self.calculate_variance()
        
        self.save(update_fields=[
            'counted_quantity', 'original_count', 'recount_by', 'recount_at',
            'recount_completed', 'variance_quantity', 'variance_percentage',
            'variance_value', 'variance_status', 'notes'
        ])
        
        return True, f"Recount recorded: {recounted_quantity}"
    
    def approve_variance(self, user, reason='', corrective_action=''):
        """Approve the variance for adjustment"""
        if self.variance_status == 'NO_VARIANCE':
            return False, "No variance to approve"
        
        self.adjustment_approved = True
        self.approved_by = user
        self.approved_at = timezone.now()
        self.variance_reason = reason
        self.corrective_action = corrective_action
        
        self.save(update_fields=[
            'adjustment_approved', 'approved_by', 'approved_at',
            'variance_reason', 'corrective_action'
        ])
        
        return True, "Variance approved for adjustment"
    
    def verify_count(self, user, verified=True, notes=''):
        """Verify the count accuracy"""
        self.verified = verified
        self.verified_by = user
        self.verified_at = timezone.now()
        
        if notes:
            self.notes = f"Verification: {notes}\n{self.notes}" if self.notes else f"Verification: {notes}"
        
        self.save(update_fields=['verified', 'verified_by', 'verified_at', 'notes'])
        
        return True, f"Count {'verified' if verified else 'not verified'}"
    
    def is_within_tolerance(self, tolerance_percentage, tolerance_amount):
        """Check if variance is within specified tolerance"""
        abs_variance_pct = abs(self.variance_percentage)
        abs_variance_val = abs(self.variance_value)
        
        return (abs_variance_pct <= tolerance_percentage and 
                abs_variance_val <= tolerance_amount)
    
    @property
    def requires_supervisor_approval(self):
        """Check if item requires supervisor approval"""
        return (
            self.variance_status in ['MAJOR_VARIANCE', 'CRITICAL_VARIANCE'] or
            abs(self.variance_value) > 1000  # High value threshold
        )
    
    @property
    def count_accuracy(self):
        """Count accuracy percentage"""
        if self.system_quantity > 0:
            accuracy = (1 - abs(self.variance_quantity) / self.system_quantity) * 100
            return max(Decimal('0'), accuracy).quantize(Decimal('0.01'))
        return Decimal('100') if self.variance_quantity == 0 else Decimal('0')


class PhysicalInventory(TenantBaseModel, AuditableMixin):
    """
    Complete physical inventory management (wall-to-wall counts)
    """
    
    INVENTORY_STATUS = [
        ('PLANNED', 'Planned'),
        ('SCHEDULED', 'Scheduled'),
        ('FROZEN', 'Inventory Frozen'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('APPROVED', 'Approved'),
    ]
    
    # Basic Information
    inventory_number = models.CharField(max_length=100, blank=True)
    inventory_name = models.CharField(max_length=200)
    
    # Scope
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='physical_inventories'
    )
    include_all_locations = models.BooleanField(default=True)
    locations = models.ManyToManyField(
        'warehouse.StockLocation',
        blank=True,
        related_name='physical_inventories'
    )
    
    # Dates
    planned_date = models.DateField()
    freeze_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    cutoff_date = models.DateTimeField(null=True, blank=True)
    
    # Status & Personnel
    status = models.CharField(max_length=20, choices=INVENTORY_STATUS, default='PLANNED')
    inventory_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_physical_inventories'
    )
    
    # Configuration
    freeze_all_transactions = models.BooleanField(default=True)
    allow_blind_counts = models.BooleanField(default=True)
    require_dual_counts = models.BooleanField(default=False)
    variance_tolerance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    
    # Results
    total_items = models.PositiveIntegerField(default=0)
    items_counted = models.PositiveIntegerField(default=0)
    total_system_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_counted_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_variance_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Additional Information
    instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_physical_inventories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'inventory_number'], 
                name='unique_tenant_inventory_number'
            ),
        ]
        ordering = ['-planned_date']
        indexes = [
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
            models.Index(fields=['tenant_id', 'status', 'planned_date']),
        ]
    
    def __str__(self):
        return f"Physical Inventory {self.inventory_number} - {self.warehouse.name}"
    
    def clean(self):
        if not self.inventory_number:
            # Auto-generate inventory number
            year = timezone.now().year
            last_inventory = PhysicalInventory.objects.filter(
                tenant_id=self.tenant_id,
                inventory_number__startswith=f'PI{year}'
            ).order_by('-inventory_number').first()
            
            if last_inventory:
                try:
                    last_num = int(last_inventory.inventory_number.replace(f'PI{year}', ''))
                    next_num = last_num + 1
                except (ValueError, AttributeError):
                    next_num = 1
            else:
                next_num = 1
            
            self.inventory_number = f"PI{year}{next_num:03d}"


class CycleCountVariance(TenantBaseModel):
    """
    Track and analyze variances discovered during cycle counting
    """
    
    VARIANCE_STATUS = [
        ('IDENTIFIED', 'Identified'),
        ('INVESTIGATING', 'Under Investigation'),
        ('EXPLAINED', 'Explained'),
        ('APPROVED', 'Approved for Adjustment'),
        ('ADJUSTED', 'Adjusted'),
        ('REJECTED', 'Rejected'),
        ('ESCALATED', 'Escalated'),
    ]
    
    VARIANCE_TYPES = [
        ('QUANTITY', 'Quantity Variance'),
        ('LOCATION', 'Location Variance'),
        ('CONDITION', 'Condition Variance'),
        ('BATCH', 'Batch/Serial Variance'),
        ('COST', 'Cost Variance'),
        ('MIXED', 'Mixed Variance'),
    ]
    
    INVESTIGATION_PRIORITY = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRITICAL', 'Critical Priority'),
    ]
    
    # Cycle Count Reference
    cycle_count = models.ForeignKey(
        CycleCount,
        on_delete=models.CASCADE,
        related_name='variances'
    )
    cycle_count_item = models.ForeignKey(
        'CycleCountItem',
        on_delete=models.CASCADE,
        related_name='variances'
    )
    
    # Basic Information
    variance_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=VARIANCE_STATUS, default='IDENTIFIED')
    variance_type = models.CharField(max_length=20, choices=VARIANCE_TYPES)
    priority = models.CharField(max_length=10, choices=INVESTIGATION_PRIORITY, default='MEDIUM')
    
    # Stock Information
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='cycle_count_variances'
    )
    
    # Quantity Variance Details
    system_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    variance_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Value Impact
    system_value = models.DecimalField(max_digits=15, decimal_places=2)
    counted_value = models.DecimalField(max_digits=15, decimal_places=2)
    variance_value = models.DecimalField(max_digits=15, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Location Information
    expected_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expected_variances'
    )
    actual_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='actual_variances'
    )
    
    # Batch/Serial Information
    expected_batch = models.CharField(max_length=100, blank=True)
    actual_batch = models.CharField(max_length=100, blank=True)
    expected_serial_numbers = models.JSONField(default=list, blank=True)
    actual_serial_numbers = models.JSONField(default=list, blank=True)
    
    # Investigation Details
    discovered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discovered_variances'
    )
    discovered_date = models.DateTimeField(default=timezone.now)
    
    # Investigation Process
    investigation_started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='investigation_variances'
    )
    investigation_started_at = models.DateTimeField(null=True, blank=True)
    investigation_due_date = models.DateTimeField(null=True, blank=True)
    
    # Root Cause Analysis
    root_cause = models.TextField(blank=True)
    contributing_factors = models.JSONField(default=list, blank=True)
    investigation_notes = models.TextField(blank=True)
    
    # Resolution Information
    resolution_action = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_variances'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Approval Information
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_variances'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Adjustment Tracking
    adjustment_created = models.BooleanField(default=False)
    adjustment_reference = models.CharField(max_length=100, blank=True)
    
    # Financial Impact
    write_off_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    insurance_claim_eligible = models.BooleanField(default=False)
    
    # Prevention & Learning
    preventable = models.BooleanField(default=True)
    prevention_measures = models.TextField(blank=True)
    process_improvement_suggestions = models.TextField(blank=True)
    training_required = models.BooleanField(default=False)
    
    # Documentation
    photos = models.JSONField(default=list, blank=True)
    supporting_documents = models.JSONField(default=list, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_cycle_count_variances'
        ordering = ['-discovered_date', '-variance_value']
        indexes = [
            models.Index(fields=['tenant_id', 'cycle_count', 'status']),
            models.Index(fields=['tenant_id', 'status', 'priority']),
            models.Index(fields=['tenant_id', 'stock_item', 'discovered_date']),
            models.Index(fields=['tenant_id', 'investigation_due_date']),
            models.Index(fields=['tenant_id', 'variance_type', 'status']),
        ]
    
    def __str__(self):
        return f"Variance {self.variance_number}: {self.stock_item.product.name} ({self.variance_quantity} units)"
    
    def clean(self):
        if not self.variance_number:
            self.variance_number = self.generate_variance_number()
        
        # Calculate variance amounts
        self.variance_quantity = self.counted_quantity - self.system_quantity
        self.variance_value = self.counted_value - self.system_value
    
    def generate_variance_number(self):
        """Generate unique variance number"""
        today = timezone.now().strftime('%Y%m%d')
        last_variance = CycleCountVariance.objects.filter(
            tenant_id=self.tenant_id,
            variance_number__startswith=f'VAR-{today}'
        ).order_by('-variance_number').first()
        
        if last_variance:
            try:
                last_seq = int(last_variance.variance_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"VAR-{today}-{next_seq:04d}"
    
    @property
    def variance_percentage(self):
        """Calculate variance as percentage"""
        if self.system_quantity != 0:
            return (self.variance_quantity / self.system_quantity * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_significant_variance(self):
        """Check if this is a significant variance"""
        return (
            abs(self.variance_value) > 100 or  # Significant value threshold
            abs(self.variance_percentage) > 5  # Significant percentage threshold
        )
    
    @property
    def is_overdue_investigation(self):
        """Check if investigation is overdue"""
        if self.investigation_due_date and self.status == 'INVESTIGATING':
            return timezone.now() > self.investigation_due_date
        return False
    
    @property
    def investigation_age_days(self):
        """Days since investigation started"""
        if self.investigation_started_at:
            return (timezone.now() - self.investigation_started_at).days
        return 0
    
    def start_investigation(self, user, due_date=None):
        """Start variance investigation"""
        if self.status != 'IDENTIFIED':
            return False, f"Cannot start investigation - status is {self.status}"
        
        self.status = 'INVESTIGATING'
        self.investigation_started_by = user
        self.investigation_started_at = timezone.now()
        
        if due_date:
            self.investigation_due_date = due_date
        else:
            # Default to 3 days for investigation
            self.investigation_due_date = timezone.now() + timedelta(days=3)
        
        self.save(update_fields=[
            'status', 'investigation_started_by', 'investigation_started_at', 'investigation_due_date'
        ])
        
        return True, "Investigation started"
    
    def explain_variance(self, user, root_cause, resolution_action=''):
        """Mark variance as explained with root cause"""
        if self.status != 'INVESTIGATING':
            return False, f"Cannot explain - status is {self.status}"
        
        self.status = 'EXPLAINED'
        self.root_cause = root_cause
        self.resolution_action = resolution_action
        self.resolved_by = user
        self.resolved_at = timezone.now()
        
        self.save(update_fields=[
            'status', 'root_cause', 'resolution_action', 'resolved_by', 'resolved_at'
        ])
        
        return True, "Variance explained"
    
    def approve_for_adjustment(self, user, notes=''):
        """Approve variance for stock adjustment"""
        if self.status != 'EXPLAINED':
            return False, f"Cannot approve - status is {self.status}"
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.approval_notes = notes
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes'])
        
        return True, "Variance approved for adjustment"
    
    def create_adjustment(self, user):
        """Create stock adjustment from approved variance"""
        if self.status != 'APPROVED':
            return False, f"Cannot create adjustment - status is {self.status}"
        
        # Import here to avoid circular imports
        from .adjustments import StockAdjustment, StockAdjustmentItem
        
        # Determine adjustment type
        adjustment_type = 'INCREASE' if self.variance_quantity > 0 else 'DECREASE'
        
        # Create stock adjustment
        adjustment = StockAdjustment.objects.create(
            tenant_id=self.tenant_id,
            adjustment_type=adjustment_type,
            reason='Cycle Count Variance',
            reference_number=self.variance_number,
            created_by=user,
            status='PENDING_APPROVAL' if self.is_significant_variance else 'APPROVED'
        )
        
        # Create adjustment item
        StockAdjustmentItem.objects.create(
            tenant_id=self.tenant_id,
            stock_adjustment=adjustment,
            stock_item=self.stock_item,
            quantity_before=self.system_quantity,
            quantity_adjustment=self.variance_quantity,
            quantity_after=self.counted_quantity,
            unit_cost_before=self.unit_cost,
            unit_cost_after=self.unit_cost,
            value_impact=self.variance_value,
            reason=f"Cycle count variance: {self.root_cause}",
            reference_number=self.cycle_count.count_number
        )
        
        # Update variance status
        self.status = 'ADJUSTED'
        self.adjustment_created = True
        self.adjustment_reference = adjustment.adjustment_number
        
        self.save(update_fields=['status', 'adjustment_created', 'adjustment_reference'])
        
        return True, f"Stock adjustment {adjustment.adjustment_number} created"
    
    def escalate(self, user, reason):
        """Escalate variance for management attention"""
        self.status = 'ESCALATED'
        self.investigation_notes += f"\nEscalated by {user.get_full_name()}: {reason}"
        
        self.save(update_fields=['status', 'investigation_notes'])
        
        return True, "Variance escalated"
    
    @classmethod
    def get_variance_summary(cls, tenant_id, cycle_count=None, date_range=None):
        """Get variance analysis summary"""
        from django.db.models import Count, Sum, Avg
        
        queryset = cls.objects.filter(tenant_id=tenant_id)
        
        if cycle_count:
            queryset = queryset.filter(cycle_count=cycle_count)
        
        if date_range:
            start_date, end_date = date_range
            queryset = queryset.filter(discovered_date__range=[start_date, end_date])
        
        summary = queryset.aggregate(
            total_variances=Count('id'),
            total_variance_value=Sum('variance_value'),
            avg_variance_value=Avg('variance_value'),
            significant_variances=Count('id', filter=models.Q(
                models.Q(variance_value__gt=100) | models.Q(variance_value__lt=-100)
            ))
        )
        
        # Group by variance type
        by_type = queryset.values('variance_type').annotate(
            count=Count('id'),
            total_value=Sum('variance_value'),
            avg_value=Avg('variance_value')
        ).order_by('-total_value')
        
        # Group by status
        by_status = queryset.values('status').annotate(
            count=Count('id'),
            total_value=Sum('variance_value')
        )
        
        return {
            'summary': summary,
            'by_type': list(by_type),
            'by_status': list(by_status)
        }