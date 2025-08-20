"""
Stock adjustment and write-off management
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date

from ..abstract.base import TenantBaseModel, AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class StockAdjustment(TenantBaseModel, AuditableMixin):
    """
    Stock adjustments and write-offs with comprehensive approval workflow
    """
    
    ADJUSTMENT_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
        ('REVERSED', 'Reversed'),
    ]
    
    ADJUSTMENT_TYPES = [
        ('INCREASE', 'Stock Increase'),
        ('DECREASE', 'Stock Decrease'),
        ('WRITE_OFF', 'Write Off'),
        ('WRITE_ON', 'Write On'),
        ('REVALUATION', 'Cost Revaluation'),
        ('CORRECTION', 'Correction'),
        ('DAMAGE', 'Damage'),
        ('THEFT', 'Theft/Loss'),
        ('EXPIRY', 'Expiry'),
        ('OBSOLETE', 'Obsolete Stock'),
        ('FOUND', 'Found Stock'),
        ('SAMPLE', 'Sample/Demo'),
        ('SHRINKAGE', 'Shrinkage'),
        ('SPOILAGE', 'Spoilage'),
        ('RETURN_TO_VENDOR', 'Return to Vendor'),
        ('QUALITY_REJECTION', 'Quality Rejection'),
        ('OTHER', 'Other'),
    ]
    
    APPROVAL_LEVELS = [
        ('NONE', 'No Approval Required'),
        ('SUPERVISOR', 'Supervisor Approval'),
        ('MANAGER', 'Manager Approval'),
        ('DIRECTOR', 'Director Approval'),
        ('CFO', 'CFO Approval'),
    ]
    
    # Basic Information
    adjustment_number = models.CharField(max_length=100, blank=True)
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    
    # Scope & Location
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='stock_adjustments'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_adjustments'
    )
    
    # Source References
    cycle_count = models.ForeignKey(
        'adjustments.CycleCount',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustments'
    )
    physical_inventory = models.ForeignKey(
        'adjustments.PhysicalInventory',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustments'
    )
    
    # Date Management
    adjustment_date = models.DateField(default=date.today)
    effective_date = models.DateField(default=date.today)
    posting_date = models.DateField(null=True, blank=True)
    reversal_date = models.DateField(null=True, blank=True)
    
    # Status & Approval Workflow
    status = models.CharField(max_length=20, choices=ADJUSTMENT_STATUS, default='DRAFT')
    approval_level_required = models.CharField(max_length=20, choices=APPROVAL_LEVELS, default='SUPERVISOR')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_adjustments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='posted_adjustments'
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    
    # Financial Impact
    total_quantity_impact = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_value_impact = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Cost Center & Accounting
    cost_center = models.CharField(max_length=50, blank=True)
    gl_account = models.CharField(max_length=50, blank=True)
    expense_account = models.CharField(max_length=50, blank=True)
    department_code = models.CharField(max_length=50, blank=True)
    
    # Business Context
    business_reason = models.TextField()
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    prevention_measures = models.TextField(blank=True)
    
    # Supporting Documentation
    supporting_documents = models.JSONField(default=list, blank=True)
    photos = models.JSONField(default=list, blank=True)
    approval_justification = models.TextField(blank=True)
    
    # Risk Assessment
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk'),
        ],
        default='MEDIUM'
    )
    compliance_impact = models.TextField(blank=True)
    
    # Reversal Information
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reversed_adjustments'
    )
    reversal_reason = models.TextField(blank=True)
    original_adjustment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reversals'
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Integration
    external_reference = models.CharField(max_length=100, blank=True)
    erp_adjustment_id = models.CharField(max_length=100, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_adjustments'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'adjustment_number'], 
                name='unique_tenant_adjustment_number'
            ),
        ]
        ordering = ['-adjustment_date', '-id']
        indexes = [
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
            models.Index(fields=['tenant_id', 'adjustment_type', 'status']),
            models.Index(fields=['tenant_id', 'status', 'adjustment_date']),
            models.Index(fields=['tenant_id', 'approval_level_required', 'status']),
            models.Index(fields=['tenant_id', 'risk_level']),
        ]
    
    def __str__(self):
        return f"Adjustment {self.adjustment_number} - {self.get_adjustment_type_display()}"
    
    def clean(self):
        if not self.adjustment_number:
            # Auto-generate adjustment number
            last_adjustment = StockAdjustment.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_adjustment and last_adjustment.adjustment_number:
                try:
                    last_num = int(last_adjustment.adjustment_number.replace('ADJ', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.adjustment_number = f"ADJ{last_num + 1:06d}"
    
    def submit_for_approval(self, user):
        """Submit adjustment for approval"""
        if self.status != 'DRAFT':
            return False, f"Cannot submit adjustment with status {self.status}"
        
        if self.approval_level_required == 'NONE':
            # Auto-approve if no approval required
            return self.approve(user, 'Auto-approved (no approval required)')
        
        self.status = 'PENDING_APPROVAL'
        self.save(update_fields=['status'])
        
        # Here you would send notifications to approvers
        
        return True, f"Adjustment submitted for {self.get_approval_level_required_display()}"
    
    def approve(self, user, notes=''):
        """Approve the adjustment"""
        if self.status not in ['PENDING_APPROVAL', 'DRAFT']:
            return False, f"Cannot approve adjustment with status {self.status}"
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.approval_notes = notes
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes'])
        
        # Auto-post if configured
        if self._should_auto_post():
            return self.post_adjustment(user)
        
        return True, "Adjustment approved successfully"
    
    def reject(self, user, reason):
        """Reject the adjustment"""
        if self.status != 'PENDING_APPROVAL':
            return False, f"Cannot reject adjustment with status {self.status}"
        
        self.status = 'REJECTED'
        self.approval_notes = f"Rejected by {user.get_full_name()}: {reason}"
        
        self.save(update_fields=['status', 'approval_notes'])
        
        return True, "Adjustment rejected"
    
    def post_adjustment(self, user):
        """Post the adjustment to inventory"""
        if self.status != 'APPROVED':
            return False, f"Cannot post adjustment with status {self.status}"
        
        posting_errors = []
        
        for item in self.items.all():
            success, message = item.apply_adjustment(user)
            if not success:
                posting_errors.append(f"Line {item.line_number}: {message}")
        
        if posting_errors:
            return False, f"Posting failed: {'; '.join(posting_errors)}"
        
        self.status = 'POSTED'
        self.posted_by = user
        self.posted_at = timezone.now()
        self.posting_date = timezone.now().date()
        
        self.save(update_fields=['status', 'posted_by', 'posted_at', 'posting_date'])
        
        # Update summary totals
        self.calculate_totals()
        
        return True, "Adjustment posted successfully"
    
    def reverse_adjustment(self, user, reason):
        """Reverse a posted adjustment"""
        if self.status != 'POSTED':
            return False, f"Cannot reverse adjustment with status {self.status}"
        
        if self.is_reversed:
            return False, "Adjustment already reversed"
        
        # Create reversal adjustment
        reversal = StockAdjustment.objects.create(
            tenant_id=self.tenant_id,
            adjustment_type=self._get_reverse_type(),
            warehouse=self.warehouse,
            location=self.location,
            business_reason=f"Reversal of {self.adjustment_number}: {reason}",
            approval_level_required='NONE',  # Auto-approve reversals
            original_adjustment=self,
            created_by=user,
        )
        
        # Create reverse line items
        for item in self.items.all():
            StockAdjustmentItem.objects.create(
                tenant_id=self.tenant_id,
                adjustment=reversal,
                stock_item=item.stock_item,
                location=item.location,
                batch=item.batch,
                quantity_before=item.quantity_after,
                quantity_adjustment=-item.quantity_adjustment,  # Reverse the adjustment
                unit_cost_before=item.unit_cost_after,
                unit_cost_after=item.unit_cost_before,
                reason=f"Reversal of adjustment {self.adjustment_number}"
            )
        
        # Post the reversal
        success, message = reversal.post_adjustment(user)
        if not success:
            reversal.delete()  # Clean up failed reversal
            return False, f"Reversal posting failed: {message}"
        
        # Mark original as reversed
        self.is_reversed = True
        self.reversed_by = user
        self.reversal_date = timezone.now().date()
        self.reversal_reason = reason
        self.status = 'REVERSED'
        
        self.save(update_fields=[
            'is_reversed', 'reversed_by', 'reversal_date', 'reversal_reason', 'status'
        ])
        
        return True, f"Adjustment reversed with number {reversal.adjustment_number}"
    
    def calculate_totals(self):
        """Calculate summary totals from line items"""
        totals = self.items.aggregate(
            total_quantity=models.Sum('quantity_adjustment'),
            total_value=models.Sum('value_impact')
        )
        
        self.total_quantity_impact = totals['total_quantity'] or Decimal('0')
        self.total_value_impact = totals['total_value'] or Decimal('0')
        
        self.save(update_fields=['total_quantity_impact', 'total_value_impact'])
    
    def _should_auto_post(self):
        """Determine if adjustment should be auto-posted"""
        # Business rules for auto-posting
        return self.risk_level == 'LOW' and abs(self.total_value_impact) < 1000
    
    def _get_reverse_type(self):
        """Get the reverse adjustment type"""
        reverse_map = {
            'INCREASE': 'DECREASE',
            'DECREASE': 'INCREASE',
            'WRITE_OFF': 'WRITE_ON',
            'WRITE_ON': 'WRITE_OFF',
        }
        return reverse_map.get(self.adjustment_type, 'CORRECTION')
    
    @property
    def requires_high_level_approval(self):
        """Check if adjustment requires high-level approval"""
        return (
            abs(self.total_value_impact) > 10000 or  # High value threshold
            self.risk_level in ['HIGH', 'CRITICAL'] or
            self.adjustment_type in ['THEFT', 'WRITE_OFF']
        )
    
    @property
    def days_since_adjustment(self):
        """Days since adjustment was made"""
        return (timezone.now().date() - self.adjustment_date).days


class StockAdjustmentItem(TenantBaseModel):
    """
    Stock adjustment line items with detailed impact tracking
    """
    
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product & Location
    stock_item = models.ForeignKey(
        'stock.StockItem',
        on_delete=models.CASCADE,
        related_name='adjustment_items'
    )
    location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustment_items'
    )
    batch = models.ForeignKey(
        'stock.Batch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='adjustment_items'
    )
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Quantity Impact
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_adjustment = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Cost Impact
    unit_cost_before = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost_after = models.DecimalField(max_digits=12, decimal_places=2)
    value_impact = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Unit Information
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='adjustment_items'
    )
    
    # Adjustment Context
    reason = models.TextField()
    root_cause = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Quality Information
    quality_impact = models.BooleanField(default=False)
    quality_notes = models.TextField(blank=True)
    
    # Physical Evidence
    photos = models.JSONField(default=list, blank=True)
    inspection_notes = models.TextField(blank=True)
    
    # Approval Tracking
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_adjustment_items'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Processing Status
    is_applied = models.BooleanField(default=False)
    applied_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='applied_adjustment_items'
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_stock_adjustment_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'adjustment', 'line_number'],
                name='unique_adjustment_line_number'
            ),
        ]
        ordering = ['adjustment', 'line_number']
        indexes = [
            models.Index(fields=['tenant_id', 'adjustment']),
            models.Index(fields=['tenant_id', 'stock_item']),
            models.Index(fields=['tenant_id', 'is_applied']),
        ]
    
    def __str__(self):
        return f"{self.adjustment.adjustment_number} Line {self.line_number}: {self.stock_item}"
    
    def save(self, *args, **kwargs):
        # Calculate quantity after
        self.quantity_after = self.quantity_before + self.quantity_adjustment
        
        # Calculate value impact
        if self.unit_cost_after != self.unit_cost_before:
            # Cost revaluation impact
            self.value_impact = (
                (self.quantity_after * self.unit_cost_after) - 
                (self.quantity_before * self.unit_cost_before)
            )
        else:
            # Quantity adjustment impact
            self.value_impact = self.quantity_adjustment * self.unit_cost_after
        
        # Auto-assign line number
        if not self.line_number:
            last_line = StockAdjustmentItem.objects.filter(
                adjustment=self.adjustment,
                tenant_id=self.tenant_id
            ).order_by('-line_number').first()
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    def apply_adjustment(self, user):
        """Apply the adjustment to the stock item"""
        if self.is_applied:
            return True, "Adjustment already applied"
        
        # Apply quantity adjustment
        if self.quantity_adjustment != 0:
            success, message = self.stock_item.adjust_stock(
                self.quantity_after,
                self.reason,
                str(self.adjustment.id),
                user
            )
            
            if not success:
                return False, f"Quantity adjustment failed: {message}"
        
        # Apply cost adjustment
        if self.unit_cost_after != self.unit_cost_before:
            if self.adjustment.adjustment_type == 'REVALUATION':
                self.stock_item.average_cost = self.unit_cost_after
                self.stock_item.update_total_value()
        
        self.is_applied = True
        self.applied_by = user
        self.applied_at = timezone.now()
        
        self.save(update_fields=['is_applied', 'applied_by', 'applied_at'])
        
        return True, "Adjustment applied successfully"
    
    @property
    def adjustment_percentage(self):
        """Percentage change in quantity"""
        if self.quantity_before != 0:
            return (self.quantity_adjustment / self.quantity_before * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_significant_adjustment(self):
        """Check if this is a significant adjustment"""
        return (
            abs(self.value_impact) > 500 or  # Significant value threshold
            abs(self.adjustment_percentage) > 10  # Significant percentage threshold
        )