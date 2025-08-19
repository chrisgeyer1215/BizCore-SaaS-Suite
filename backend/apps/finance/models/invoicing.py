"""
Customer Invoicing Models
Enhanced customer invoices with multi-currency and CRM integration
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code
from .currency import Currency

User = get_user_model()


class Invoice(TenantBaseModel, SoftDeleteMixin):
    """Enhanced customer invoices with multi-currency and CRM integration"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SENT', 'Sent'),
        ('VIEWED', 'Viewed by Customer'),
        ('OPEN', 'Open'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
        ('DISPUTED', 'Disputed'),
        ('VOIDED', 'Voided'),
    ]
    
    INVOICE_TYPE_CHOICES = [
        ('STANDARD', 'Standard Invoice'),
        ('RECURRING', 'Recurring Invoice'),
        ('CREDIT_NOTE', 'Credit Note'),
        ('DEBIT_NOTE', 'Debit Note'),
        ('ESTIMATE', 'Estimate'),
        ('QUOTE', 'Quote'),
        ('PROFORMA', 'Proforma Invoice'),
        ('RETAINER', 'Retainer Invoice'),
        ('FINAL', 'Final Invoice'),
    ]
    
    # Invoice Identification
    invoice_number = models.CharField(max_length=50)
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES, default='STANDARD')
    reference_number = models.CharField(max_length=100, blank=True)
    purchase_order_number = models.CharField(max_length=100, blank=True)
    
    # Customer Information
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    customer_email = models.EmailField()
    customer_contact = models.ForeignKey(
        'crm.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Dates
    invoice_date = models.DateField()
    due_date = models.DateField()
    sent_date = models.DateTimeField(null=True, blank=True)
    viewed_date = models.DateTimeField(null=True, blank=True)
    service_period_start = models.DateField(null=True, blank=True)
    service_period_end = models.DateField(null=True, blank=True)
    
    # Status & Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_invoices'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Multi-Currency Support
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Base Currency Amounts
    base_currency_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    base_currency_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    base_currency_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    base_currency_amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Addresses
    billing_address = models.JSONField(default=dict)
    shipping_address = models.JSONField(default=dict)
    
    # Payment Information
    payment_terms = models.CharField(max_length=100, blank=True)
    payment_instructions = models.TextField(blank=True)
    bank_details = models.JSONField(default=dict, blank=True)
    
    # Source Documents
    source_order = models.ForeignKey(
        'ecommerce.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    source_quote = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'invoice_type': 'QUOTE'},
        related_name='converted_invoices'
    )
    source_estimate = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'invoice_type': 'ESTIMATE'},
        related_name='estimate_invoices'
    )
    
    # Recurring Invoice Settings
    is_recurring = models.BooleanField(default=False)
    recurring_interval_days = models.PositiveIntegerField(null=True, blank=True)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=[
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
        ],
        blank=True
    )
    next_invoice_date = models.DateField(null=True, blank=True)
    parent_invoice = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_invoices'
    )
    auto_send = models.BooleanField(default=False)
    recurring_end_date = models.DateField(null=True, blank=True)
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    footer_text = models.TextField(blank=True)
    customer_message = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Journal Entry
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    
    # Online Payments
    online_payment_enabled = models.BooleanField(default=True)
    payment_gateway_settings = models.JSONField(default=dict, blank=True)
    payment_link = models.URLField(blank=True)
    
    # Template & Design
    invoice_template = models.CharField(max_length=50, default='standard')
    custom_css = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Analytics & Tracking
    view_count = models.PositiveIntegerField(default=0)
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)
    email_delivery_status = models.CharField(max_length=50, blank=True)
    
    # Collections
    collection_status = models.CharField(
        max_length=20,
        choices=[
            ('CURRENT', 'Current'),
            ('FOLLOW_UP', 'Follow Up'),
            ('COLLECTIONS', 'In Collections'),
            ('WRITE_OFF', 'Write Off'),
        ],
        default='CURRENT'
    )
    collection_notes = models.TextField(blank=True)
    
    # Workflow
    workflow_state = models.CharField(max_length=50, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices'
    )
    
    class Meta:
        ordering = ['-invoice_date', '-invoice_number']
        db_table = 'finance_invoices'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'invoice_number'],
                name='unique_tenant_invoice_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'customer']),
            models.Index(fields=['tenant', 'due_date', 'status']),
            models.Index(fields=['tenant', 'invoice_date']),
            models.Index(fields=['tenant', 'is_recurring']),
            models.Index(fields=['tenant', 'collection_status']),
        ]
        
    def __str__(self):
        return f'{self.invoice_number} - {self.customer.name}'
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        if not self.customer_email and self.customer:
            self.customer_email = self.customer.email
        
        # Calculate totals
        self.calculate_totals()
        
        # Calculate base currency amounts
        self.calculate_base_currency_amounts()
        
        # Update status based on dates and amounts
        self.update_status()
        
        super().save(*args, **kwargs)
    
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        from .core import FinanceSettings
        
        try:
            settings = FinanceSettings.objects.get(tenant=self.tenant)
            return generate_code(settings.invoice_prefix, self.tenant_id, settings.invoice_starting_number)
        except FinanceSettings.DoesNotExist:
            return generate_code('INV', self.tenant_id, 1000)
    
    def calculate_totals(self):
        """Calculate invoice totals from line items"""
        line_totals = self.invoice_items.aggregate(
            subtotal=models.Sum(
                models.F('quantity') * models.F('unit_price') * (1 - models.F('discount_rate') / 100),
                output_field=models.DecimalField()
            ),
            tax_total=models.Sum('tax_amount', output_field=models.DecimalField())
        )
        
        gross_subtotal = line_totals['subtotal'] or Decimal('0.00')
        
        # Apply invoice-level discount
        if self.discount_percentage:
            self.discount_amount = gross_subtotal * (self.discount_percentage / 100)
        
        self.subtotal = gross_subtotal - self.discount_amount
        self.tax_amount = line_totals['tax_total'] or Decimal('0.00')
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_amount
        self.amount_due = self.total_amount - self.amount_paid
    
    def calculate_base_currency_amounts(self):
        """Calculate amounts in base currency"""
        self.base_currency_subtotal = self.subtotal * self.exchange_rate
        self.base_currency_total = self.total_amount * self.exchange_rate
        self.base_currency_amount_paid = self.amount_paid * self.exchange_rate
        self.base_currency_amount_due = self.amount_due * self.exchange_rate
    
    def update_status(self):
        """Update invoice status based on payments and dates"""
        if self.status not in ['DRAFT', 'PENDING_APPROVAL', 'CANCELLED', 'VOIDED']:
            if self.amount_due <= Decimal('0.00'):
                self.status = 'PAID'
            elif self.amount_paid > Decimal('0.00'):
                self.status = 'PARTIAL'
            elif self.is_overdue:
                self.status = 'OVERDUE'
            elif self.status not in ['SENT', 'VIEWED']:
                self.status = 'OPEN'
    
    def clean(self):
        """Validate invoice"""
        if self.invoice_date > date.today():
            raise ValidationError('Invoice date cannot be in the future')
        
        if self.due_date < self.invoice_date:
            raise ValidationError('Due date cannot be before invoice date')
        
        if self.service_period_start and self.service_period_end:
            if self.service_period_start >= self.service_period_end:
                raise ValidationError('Service period start must be before end date')
        
        if self.is_recurring and not self.recurring_frequency:
            raise ValidationError('Recurring frequency is required for recurring invoices')
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        return date.today() > self.due_date and self.status in ['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
    
    @property
    def days_until_due(self):
        """Days until due date"""
        return (self.due_date - date.today()).days
    
    @property
    def days_overdue(self):
        """Days overdue (negative if not overdue)"""
        return (date.today() - self.due_date).days
    
    @property
    def can_be_sent(self):
        """Check if invoice can be sent"""
        return self.status in ['APPROVED', 'OPEN'] and self.customer_email
    
    @property
    def payment_percentage(self):
        """Percentage of invoice that has been paid"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return Decimal('0.00')
    
    def send_invoice(self, send_copy_to=None, email_template=None):
        """Send invoice to customer"""
        from ..services.invoice import InvoiceService
        
        service = InvoiceService(self.tenant)
        result = service.send_invoice(self, send_copy_to, email_template)
        
        if result['success']:
            self.status = 'SENT'
            self.sent_date = timezone.now()
            self.save()
        
        return result


class InvoiceItem(TenantBaseModel):
    """Enhanced invoice line items with inventory integration"""
    
    ITEM_TYPES = [
        ('PRODUCT', 'Product'),
        ('SERVICE', 'Service'),
        ('DISCOUNT', 'Discount'),
        ('SHIPPING', 'Shipping'),
        ('FEE', 'Fee'),
        ('OTHER', 'Other'),
    ]
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_items')
    line_number = models.IntegerField()
    
    # Item Information
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='PRODUCT')
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    description = models.TextField()
    sku = models.CharField(max_length=100, blank=True)
    
    # Quantity & Pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('1.0000'))
    unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    line_total = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Account Classification
    revenue_account = models.ForeignKey('finance.Account', on_delete=models.PROTECT)
    
    # Tax Information
    tax_code = models.ForeignKey(
        'finance.TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    is_tax_inclusive = models.BooleanField(default=False)
    
    # Additional Tracking
    project = models.ForeignKey(
        'finance.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    department = models.ForeignKey(
        'finance.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    location = models.ForeignKey(
        'finance.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    job_number = models.CharField(max_length=50, blank=True)
    
    # Inventory Integration
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    lot_numbers = models.JSONField(default=list, blank=True)
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Cost Information (for COGS calculation)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Delivery Information
    delivery_date = models.DateField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    quantity_delivered = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    
    class Meta:
        ordering = ['invoice', 'line_number']
        db_table = 'finance_invoice_items'
        
    def __str__(self):
        return f'{self.invoice.invoice_number} - Line {self.line_number}: {self.description}'
    
    def save(self, *args, **kwargs):
        # Calculate line total
        line_subtotal = self.quantity * self.unit_price
        discount_amount = line_subtotal * (self.discount_rate / 100)
        self.line_total = line_subtotal - discount_amount
        
        # Calculate tax
        if self.tax_code:
            if self.is_tax_inclusive:
                # Tax is included in the price
                tax_divisor = Decimal('1') + (self.tax_code.rate / 100)
                self.tax_amount = self.line_total - (self.line_total / tax_divisor)
            else:
                # Tax is added to the price
                self.tax_amount = self.tax_code.calculate_tax(self.line_total)
        
        # Get cost information for COGS
        if self.product and self.item_type == 'PRODUCT':
            cost_info = self.get_product_cost()
            self.unit_cost = cost_info['unit_cost']
            self.total_cost = cost_info['total_cost']
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate invoice item"""
        if self.quantity <= 0:
            raise ValidationError('Quantity must be positive')
        
        if self.unit_price < 0:
            raise ValidationError('Unit price cannot be negative')
        
        if self.quantity_delivered > self.quantity:
            raise ValidationError('Delivered quantity cannot exceed invoiced quantity')
    
    def get_product_cost(self):
        """Get product cost for COGS calculation"""
        if not self.product:
            return {'unit_cost': Decimal('0.00'), 'total_cost': Decimal('0.00')}
        
        from ..services.inventory_costing import InventoryCostingService
        
        service = InventoryCostingService(self.tenant)
        return service.get_product_cost(self.product, self.quantity, self.warehouse)
    
    def reserve_inventory(self):
        """Reserve inventory for this line item"""
        if not self.product or self.item_type != 'PRODUCT':
            return
        
        from ..services.inventory import InventoryService
        
        service = InventoryService(self.tenant)
        service.reserve_inventory(self.product, self.quantity, self.warehouse, self.invoice)
    
    def release_inventory_reservation(self):
        """Release inventory reservation"""
        if not self.product or self.item_type != 'PRODUCT':
            return
        
        from ..services.inventory import InventoryService
        
        service = InventoryService(self.tenant)
        service.release_reservation(self.product, self.quantity, self.warehouse, self.invoice)
    
    @property
    def extended_price(self):
        """Get extended price (quantity * unit price)"""
        return self.quantity * self.unit_price
    
    @property
    def net_amount(self):
        """Get net amount after discount"""
        return self.line_total
    
    @property
    def total_with_tax(self):
        """Get total including tax"""
        return self.line_total + self.tax_amount
    
    @property
    def gross_margin(self):
        """Calculate gross margin"""
        if self.total_cost and self.line_total > 0:
            return ((self.line_total - self.total_cost) / self.line_total) * 100
        return Decimal('0.00')
    
    @property
    def is_fully_delivered(self):
        """Check if item is fully delivered"""
        return self.quantity_delivered >= self.quantity
    
    @property
    def pending_delivery(self):
        """Get quantity still pending delivery"""
        return self.quantity - self.quantity_delivered
    
    def record_view(self, ip_address=None, user_agent=None):
        """Record invoice view"""
        self.view_count += 1
        if self.status == 'SENT':
            self.status = 'VIEWED'
            self.viewed_date = timezone.now()
        self.save()
        
        # Log the view
        from ..models.journal import ReconciliationLog
        ReconciliationLog.log_action(
            tenant=self.tenant,
            bank_account=None,
            action_type='INVOICE_VIEWED',
            description=f'Invoice {self.invoice_number} viewed',
            details={'ip_address': ip_address, 'user_agent': user_agent}
        )
    
    def approve_invoice(self, user):
        """Approve the invoice"""
        if self.status != 'PENDING_APPROVAL':
            raise ValidationError('Invoice is not in pending approval status')
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()
        
        # Create journal entry
        self.create_journal_entry()
        
        # Create COGS entries for inventory items
        self.create_cogs_entries()
        
        # Update customer balance
        if hasattr(self.customer, 'financial_profile'):
            self.customer.financial_profile.current_balance += self.base_currency_amount_due
            self.customer.financial_profile.save()
    
    def create_journal_entry(self):
        """Create journal entry for the invoice"""
        from ..services.journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        return service.create_invoice_journal_entry(self)
    
    def create_cogs_entries(self):
        """Create COGS entries for inventory items"""
        from ..services.cogs import COGSService
        
        service = COGSService(self.tenant)
        service.create_invoice_cogs_entries(self)
    
    def create_recurring_invoice(self):
        """Create next recurring invoice"""
        if not self.is_recurring or not self.next_invoice_date:
            return None
        
        from ..services.recurring_invoice import RecurringInvoiceService
        
        service = RecurringInvoiceService(self.tenant)
        return service.create_next_invoice(self)
    
    def void_invoice(self, user, reason):
        """Void the invoice"""
        if self.status in ['PAID', 'PARTIAL']:
            raise ValidationError('Cannot void invoices with payments')
        
        self.status = 'VOIDED'
        self.notes = f"{self.notes}\n\nVoided by {user.get_full_name()}: {reason}"
        self.save()
        
        # Reverse journal entry if exists
        if self.journal_entry:
            self.journal_entry.reverse_entry(user, f"Voiding invoice {self.invoice_number}")
    
    def send_reminder(self, reminder_type='OVERDUE'):
        """Send payment reminder"""
        from ..services.invoice import InvoiceService
        
        service = InvoiceService(self.tenant)
        result = service.send_reminder(self, reminder_type)
        
        if result['success']:
            self.last_reminder_sent = timezone.now()
            self.reminder_count += 1
            self.save()
        
        return result