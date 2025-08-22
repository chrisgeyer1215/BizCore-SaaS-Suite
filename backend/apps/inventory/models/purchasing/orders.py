"""
Purchase order management models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from ..abstract.auditable import AuditableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class PurchaseOrder(TenantBaseModel, AuditableMixin):
    """
    Comprehensive purchase order management with workflow and approval
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SENT_TO_SUPPLIER', 'Sent to Supplier'),
        ('ACKNOWLEDGED', 'Acknowledged by Supplier'),
        ('CONFIRMED', 'Confirmed'),
        ('PARTIAL_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('INVOICED', 'Invoiced'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
        ('RETURNED', 'Returned'),
        ('DISPUTED', 'Disputed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    PO_TYPES = [
        ('STANDARD', 'Standard Purchase'),
        ('DROP_SHIP', 'Drop Ship'),
        ('CONSIGNMENT', 'Consignment'),
        ('BLANKET', 'Blanket Order'),
        ('CONTRACT', 'Contract Order'),
        ('SERVICE', 'Service Order'),
        ('CAPITAL', 'Capital Purchase'),
        ('MAINTENANCE', 'Maintenance Order'),
    ]
    
    # Basic Information
    po_number = models.CharField(max_length=100, blank=True)
    po_type = models.CharField(max_length=20, choices=PO_TYPES, default='STANDARD')
    revision_number = models.IntegerField(default=1)
    
    # Supplier & Delivery Information
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    delivery_warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    bill_to_address = models.JSONField(default=dict, blank=True)
    ship_to_address = models.JSONField(default=dict, blank=True)
    
    # Date Management
    order_date = models.DateField(default=date.today)
    required_date = models.DateField()
    promised_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    cancelled_date = models.DateField(null=True, blank=True)
    
    # Status & Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Financial Information
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    # Amount Calculations
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Payment Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    early_payment_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    late_payment_penalty = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Personnel & Approval
    buyer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_purchase_orders'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_purchase_orders'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Supplier Communication
    sent_to_supplier_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_purchase_orders'
    )
    supplier_acknowledgment_date = models.DateTimeField(null=True, blank=True)
    supplier_confirmation_number = models.CharField(max_length=100, blank=True)
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True)
    shipping_terms = models.CharField(max_length=100, blank=True)
    incoterms = models.CharField(max_length=10, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    freight_forwarder = models.CharField(max_length=100, blank=True)
    
    # Supplier References
    supplier_po_number = models.CharField(max_length=100, blank=True)
    supplier_quote_number = models.CharField(max_length=100, blank=True)
    supplier_contact = models.CharField(max_length=100, blank=True)
    supplier_email = models.EmailField(blank=True)
    supplier_phone = models.CharField(max_length=20, blank=True)
    
    # Drop Shipping (if applicable)
    is_dropship_order = models.BooleanField(default=False)
    dropship_customer_name = models.CharField(max_length=200, blank=True)
    dropship_address = models.JSONField(default=dict, blank=True)
    dropship_instructions = models.TextField(blank=True)
    
    # Quality & Inspection
    requires_inspection = models.BooleanField(default=False)
    inspection_required_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    quality_standards = models.TextField(blank=True)
    inspection_instructions = models.TextField(blank=True)
    
    # Contract & Legal
    contract_number = models.CharField(max_length=100, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    terms_and_conditions = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    
    # Internal Management
    internal_notes = models.TextField(blank=True)
    reason_for_purchase = models.TextField(blank=True)
    project_code = models.CharField(max_length=50, blank=True)
    department_code = models.CharField(max_length=50, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)
    
    # Document Management
    documents = models.JSONField(default=list, blank=True)
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='revisions'
    )
    
    # Performance Tracking
    lead_time_actual = models.IntegerField(null=True, blank=True)
    delivery_performance_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    quality_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Integration & External Systems
    external_po_id = models.CharField(max_length=100, blank=True)
    erp_system_id = models.CharField(max_length=100, blank=True)
    supplier_portal_url = models.URLField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_purchase_orders'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'po_number'], 
                name='unique_tenant_po_number'
            ),
        ]
        ordering = ['-order_date', '-id']
        indexes = [
            models.Index(fields=['tenant_id', 'supplier', 'status']),
            models.Index(fields=['tenant_id', 'status', 'order_date']),
            models.Index(fields=['tenant_id', 'buyer', 'status']),
            models.Index(fields=['tenant_id', 'required_date']),
            models.Index(fields=['tenant_id', 'po_type']),
        ]
    
    def __str__(self):
        return f"PO-{self.po_number} - {self.supplier.name}"
    
    def clean(self):
        if not self.po_number:
            # Auto-generate PO number
            last_po = PurchaseOrder.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_po and last_po.po_number:
                try:
                    last_num = int(last_po.po_number.replace('PO', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.po_number = f"PO{last_num + 1:06d}"
    
    @property
    def total_items(self):
        """Total number of line items"""
        return self.items.count()
    
    @property
    def total_quantity_ordered(self):
        """Total quantity across all items"""
        return self.items.aggregate(
            total=models.Sum('quantity_ordered')
        )['total'] or Decimal('0')
    
    @property
    def total_quantity_received(self):
        """Total quantity received across all items"""
        return self.items.aggregate(
            total=models.Sum('quantity_received')
        )['total'] or Decimal('0')
    
    @property
    def received_percentage(self):
        """Percentage of total order received"""
        total_ordered = self.total_quantity_ordered
        if total_ordered > 0:
            total_received = self.total_quantity_received
            return (total_received / total_ordered * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_fully_received(self):
        """Check if order is fully received"""
        return self.received_percentage >= 100
    
    @property
    def is_overdue(self):
        """Check if order is overdue"""
        if self.required_date and self.status not in ['RECEIVED', 'COMPLETED', 'CANCELLED']:
            return self.required_date < timezone.now().date()
        return False
    
    @property
    def days_until_required(self):
        """Days until required date"""
        if self.required_date:
            delta = self.required_date - timezone.now().date()
            return delta.days
        return None
    
    def calculate_totals(self):
        """Recalculate all financial totals"""
        # Calculate subtotal from line items
        self.subtotal = self.items.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0')
        
        # Calculate discount
        if self.discount_percentage > 0:
            self.discount_amount = (self.subtotal * self.discount_percentage / 100).quantize(Decimal('0.01'))
        
        # Calculate tax
        if self.tax_rate > 0:
            taxable_amount = self.subtotal - self.discount_amount
            self.tax_amount = (taxable_amount * self.tax_rate / 100).quantize(Decimal('0.01'))
        
        # Calculate total
        self.total_amount = (
            self.subtotal - self.discount_amount + self.tax_amount + 
            self.shipping_cost + self.handling_cost + self.other_charges
        )
        
        self.save(update_fields=[
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount'
        ])
    
    def approve(self, user, notes=''):
        """Approve the purchase order"""
        if self.status != 'PENDING_APPROVAL':
            return False, f"Cannot approve PO with status {self.status}"
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.approval_notes = notes
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes'])
        return True, "Purchase order approved successfully"
    
    def send_to_supplier(self, user):
        """Mark as sent to supplier"""
        if self.status != 'APPROVED':
            return False, f"Cannot send PO with status {self.status}"
        
        self.status = 'SENT_TO_SUPPLIER'
        self.sent_to_supplier_at = timezone.now()
        self.sent_by = user
        
        self.save(update_fields=['status', 'sent_to_supplier_at', 'sent_by'])
        
        # Here you would integrate with email/EDI system
        return True, "Purchase order sent to supplier"
    
    def acknowledge_by_supplier(self, supplier_confirmation_number=''):
        """Mark as acknowledged by supplier"""
        if self.status != 'SENT_TO_SUPPLIER':
            return False, f"Cannot acknowledge PO with status {self.status}"
        
        self.status = 'ACKNOWLEDGED'
        self.supplier_acknowledgment_date = timezone.now()
        self.supplier_confirmation_number = supplier_confirmation_number
        
        self.save(update_fields=[
            'status', 'supplier_acknowledgment_date', 'supplier_confirmation_number'
        ])
        return True, "Purchase order acknowledged by supplier"
    
    def cancel(self, reason, user):
        """Cancel the purchase order"""
        if self.status in ['RECEIVED', 'COMPLETED', 'CANCELLED']:
            return False, f"Cannot cancel PO with status {self.status}"
        
        old_status = self.status
        self.status = 'CANCELLED'
        self.cancelled_date = timezone.now().date()
        self.internal_notes = f"Cancelled by {user.get_full_name()}: {reason}\n{self.internal_notes}"
        
        self.save(update_fields=['status', 'cancelled_date', 'internal_notes'])
        
        # Release any reserved stock allocations
        for item in self.items.all():
            item.cancel_item(reason, user)
        
        return True, f"Purchase order cancelled (was {old_status})"
    
    def create_revision(self, user, reason=''):
        """Create a new revision of this PO"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False, "Cannot revise completed or cancelled PO"
        
        # Create new revision
        new_po = PurchaseOrder.objects.create(
            tenant_id=self.tenant_id,
            supplier=self.supplier,
            delivery_warehouse=self.delivery_warehouse,
            po_type=self.po_type,
            revision_number=self.revision_number + 1,
            previous_version=self,
            # Copy other relevant fields
            required_date=self.required_date,
            currency=self.currency,
            payment_terms=self.payment_terms,
            shipping_method=self.shipping_method,
            terms_and_conditions=self.terms_and_conditions,
            special_instructions=self.special_instructions,
            buyer=user,
            internal_notes=f"Revision created: {reason}"
        )
        
        # Copy line items
        for item in self.items.all():
            PurchaseOrderItem.objects.create(
                tenant_id=self.tenant_id,
                purchase_order=new_po,
                product=item.product,
                variation=item.variation,
                quantity_ordered=item.quantity_ordered,
                unit_cost=item.unit_cost,
                # Copy other item fields
                supplier_sku=item.supplier_sku,
                supplier_product_name=item.supplier_product_name,
                unit=item.unit,
                required_date=item.required_date,
                notes=item.notes
            )
        
        # Update original PO status
        self.status = 'CANCELLED'
        self.internal_notes = f"Superseded by revision {new_po.po_number}\n{self.internal_notes}"
        self.save(update_fields=['status', 'internal_notes'])
        
        # Recalculate totals for new PO
        new_po.calculate_totals()
        
        return True, f"Created revision {new_po.po_number}"
    
    def update_delivery_performance(self):
        """Update delivery performance metrics"""
        if self.delivery_date and self.required_date:
            days_difference = (self.delivery_date - self.required_date).days
            
            if days_difference <= 0:
                self.delivery_performance_score = Decimal('100')
            elif days_difference <= 7:
                self.delivery_performance_score = Decimal('80')
            elif days_difference <= 14:
                self.delivery_performance_score = Decimal('60')
            else:
                self.delivery_performance_score = Decimal('40')
            
            self.save(update_fields=['delivery_performance_score'])


class PurchaseOrderItem(TenantBaseModel):
    """
    Purchase order line items with comprehensive tracking and receiving
    """
    
    ITEM_STATUS = [
        ('ORDERED', 'Ordered'),
        ('CONFIRMED', 'Confirmed'),
        ('PARTIAL_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CANCELLED', 'Cancelled'),
        ('RETURNED', 'Returned'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    line_number = models.PositiveIntegerField()
    
    # Product Information
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='purchase_order_items'
    )
    variation = models.ForeignKey(
        'catalog.ProductVariation',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='purchase_order_items'
    )
    
    # Supplier Product Information
    supplier_sku = models.CharField(max_length=50, blank=True)
    supplier_product_name = models.CharField(max_length=200, blank=True)
    manufacturer_part_number = models.CharField(max_length=100, blank=True)
    supplier_catalog_page = models.CharField(max_length=50, blank=True)
    
    # Quantities
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_invoiced = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_returned = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Unit Information
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    unit_conversion_factor = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    required_date = models.DateField(null=True, blank=True)
    promised_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    first_receipt_date = models.DateTimeField(null=True, blank=True)
    last_receipt_date = models.DateTimeField(null=True, blank=True)
    
    # Quality & Inspection
    requires_inspection = models.BooleanField(default=False)
    inspection_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    quality_specifications = models.TextField(blank=True)
    inspection_instructions = models.TextField(blank=True)
    
    # Delivery & Location
    delivery_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchase_order_items'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=ITEM_STATUS, default='ORDERED')
    
    # Additional Costs (for landed cost calculation)
    freight_allocation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    duty_allocation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    handling_allocation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_cost_allocation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Asset Information (for capital purchases)
    is_asset = models.BooleanField(default=False)
    asset_category = models.CharField(max_length=50, blank=True)
    depreciation_schedule = models.CharField(max_length=50, blank=True)
    
    # Project & Cost Center
    project_code = models.CharField(max_length=50, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)
    gl_account = models.CharField(max_length=50, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_purchase_order_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'purchase_order', 'line_number'],
                name='unique_po_line_number'
            ),
        ]
        ordering = ['purchase_order', 'line_number']
        indexes = [
            models.Index(fields=['tenant_id', 'purchase_order']),
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'status']),
        ]
    
    def __str__(self):
        product_name = self.product.name
        if self.variation:
            product_name += f" - {self.variation.name}"
        return f"{self.purchase_order.po_number} Line {self.line_number}: {product_name}"
    
    @property
    def pending_quantity(self):
        """Quantity still pending receipt"""
        return self.quantity_ordered - self.quantity_received
    
    @property
    def received_percentage(self):
        """Percentage of line item received"""
        if self.quantity_ordered > 0:
            return (self.quantity_received / self.quantity_ordered * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def is_fully_received(self):
        """Check if line item is fully received"""
        return self.quantity_received >= self.quantity_ordered
    
    @property
    def is_overdue(self):
        """Check if line item is overdue"""
        if self.required_date and not self.is_fully_received:
            return self.required_date < timezone.now().date()
        return False
    
    @property
    def total_landed_cost_per_unit(self):
        """Calculate total landed cost per unit"""
        additional_costs = (
            self.freight_allocation + self.duty_allocation + 
            self.handling_allocation + self.other_cost_allocation
        )
        if self.quantity_ordered > 0:
            return self.unit_cost + (additional_costs / self.quantity_ordered)
        return self.unit_cost
    
    def save(self, *args, **kwargs):
        # Calculate discount amount
        if self.discount_percentage > 0:
            gross_amount = self.quantity_ordered * self.unit_cost
            self.discount_amount = (gross_amount * self.discount_percentage / 100).quantize(Decimal('0.01'))
        
        # Calculate tax amount
        taxable_amount = (self.quantity_ordered * self.unit_cost) - self.discount_amount
        if self.tax_rate > 0:
            self.tax_amount = (taxable_amount * self.tax_rate / 100).quantize(Decimal('0.01'))
        
        # Calculate total amount
        self.total_amount = taxable_amount + self.tax_amount
        
        # Auto-assign line number if not provided
        if not self.line_number:
            last_line = PurchaseOrderItem.objects.filter(
                purchase_order=self.purchase_order,
                tenant_id=self.tenant_id
            ).order_by('-line_number').first()
            
            self.line_number = (last_line.line_number + 1) if last_line else 1
        
        super().save(*args, **kwargs)
    
    def receive_quantity(self, quantity, batch_number=None, expiry_date=None, 
                        location=None, user=None, quality_status='PASSED'):
        """Receive quantity for this line item"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_received + quantity > self.quantity_ordered:
            return False, "Cannot receive more than ordered quantity"
        
        # Update received quantity
        old_received = self.quantity_received
        self.quantity_received += quantity
        
        # Update dates
        if old_received == 0:
            self.first_receipt_date = timezone.now()
        self.last_receipt_date = timezone.now()
        
        # Update status
        if self.quantity_received >= self.quantity_ordered:
            self.status = 'RECEIVED'
        else:
            self.status = 'PARTIAL_RECEIVED'
        
        self.save(update_fields=[
            'quantity_received', 'status', 
            'first_receipt_date', 'last_receipt_date'
        ])
        
        # Create or update stock item
        from ..stock.items import StockItem
        
        stock_item, created = StockItem.objects.get_or_create(
            tenant_id=self.tenant_id,
            product=self.product,
            variation=self.variation,
            warehouse=self.purchase_order.delivery_warehouse,
            location=location or self.delivery_location,
            defaults={
                'unit_cost': self.total_landed_cost_per_unit,
                'average_cost': self.total_landed_cost_per_unit,
                'last_cost': self.total_landed_cost_per_unit,
            }
        )
        
        # Receive stock
        success, message = stock_item.receive_stock(
            quantity=quantity,
            unit_cost=self.total_landed_cost_per_unit,
            reason=f"PO Receipt: {self.purchase_order.po_number}",
            reference_id=str(self.purchase_order.id),
            user=user
        )
        
        if not success:
            # Rollback the item quantity update
            self.quantity_received = old_received
            if old_received == 0:
                self.first_receipt_date = None
            # Recalculate status
            if self.quantity_received >= self.quantity_ordered:
                self.status = 'RECEIVED'
            elif self.quantity_received > 0:
                self.status = 'PARTIAL_RECEIVED'
            else:
                self.status = 'ORDERED'
            
            self.save(update_fields=[
                'quantity_received', 'status', 'first_receipt_date'
            ])
            return False, f"Stock receipt failed: {message}"
        
        # Create batch if batch tracking is enabled and batch_number provided
        if self.product.is_batch_tracked and batch_number:
            from ..stock.batches import Batch
            
            batch, batch_created = Batch.objects.get_or_create(
                tenant_id=self.tenant_id,
                product=self.product,
                batch_number=batch_number,
                defaults={
                    'initial_quantity': quantity,
                    'current_quantity': quantity,
                    'unit_cost': self.unit_cost,
                    'total_cost': quantity * self.unit_cost,
                    'supplier': self.purchase_order.supplier,
                    'purchase_order_number': self.purchase_order.po_number,
                    'expiry_date': expiry_date,
                    'quality_grade': 'A' if quality_status == 'PASSED' else 'D',
                }
            )
            
            if not batch_created:
                batch.current_quantity += quantity
                batch.total_cost += (quantity * self.unit_cost)
                batch.save(update_fields=['current_quantity', 'total_cost'])
        
        # Update PO status if all items are fully received
        self.purchase_order.update_status_from_items()
        
        return True, f"Received {quantity} units successfully"
    
    def cancel_item(self, reason, user):
        """Cancel this line item"""
        if self.status in ['RECEIVED', 'CANCELLED']:
            return False, f"Cannot cancel item with status {self.status}"
        
        self.status = 'CANCELLED'
        self.notes = f"Cancelled by {user.get_full_name()}: {reason}\n{self.notes}"
        self.save(update_fields=['status', 'notes'])
        
        # Update PO totals
        self.purchase_order.calculate_totals()
        
        return True, "Line item cancelled successfully"
    
    def return_quantity(self, quantity, reason, user):
        """Return received quantity back to supplier"""
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if self.quantity_received < quantity:
            return False, f"Cannot return more than received. Received: {self.quantity_received}"
        
        self.quantity_returned += quantity
        self.quantity_received -= quantity
        
        # Update status
        if self.quantity_received < self.quantity_ordered:
            if self.quantity_received > 0:
                self.status = 'PARTIAL_RECEIVED'
            else:
                self.status = 'ORDERED'
        
        self.notes = f"Returned {quantity} units: {reason}\n{self.notes}"
        self.save(update_fields=['quantity_returned', 'quantity_received', 'status', 'notes'])
        
        return True, f"Returned {quantity} units successfully"