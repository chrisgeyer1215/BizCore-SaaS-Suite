"""
Vendor and Bill Management Models
Enhanced vendor management with bills and purchase integration
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


class Vendor(TenantBaseModel, SoftDeleteMixin):
    """Enhanced vendor/supplier management with CRM integration"""
    
    VENDOR_TYPE_CHOICES = [
        ('SUPPLIER', 'Supplier'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('CONTRACTOR', 'Contractor'),
        ('EMPLOYEE', 'Employee'),
        ('UTILITY', 'Utility Company'),
        ('GOVERNMENT', 'Government Agency'),
        ('PROFESSIONAL_SERVICES', 'Professional Services'),
        ('OTHER', 'Other'),
    ]
    
    PAYMENT_TERMS_CHOICES = [
        ('NET_15', 'Net 15 Days'),
        ('NET_30', 'Net 30 Days'),
        ('NET_60', 'Net 60 Days'),
        ('NET_90', 'Net 90 Days'),
        ('COD', 'Cash on Delivery'),
        ('PREPAID', 'Prepaid'),
        ('2_10_NET_30', '2/10 Net 30'),
        ('1_10_NET_30', '1/10 Net 30'),
        ('CUSTOM', 'Custom Terms'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ON_HOLD', 'On Hold'),
        ('BLOCKED', 'Blocked'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Basic Information
    vendor_number = models.CharField(max_length=50)
    company_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    vendor_type = models.CharField(max_length=25, choices=VENDOR_TYPE_CHOICES, default='SUPPLIER')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Contact Information
    primary_contact = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address Information
    billing_address = models.JSONField(default=dict)
    shipping_address = models.JSONField(default=dict)
    remit_to_address = models.JSONField(default=dict)
    
    # Financial Information
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='NET_30')
    payment_terms_days = models.PositiveIntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    
    # Tax Information
    tax_id = models.CharField(max_length=50, blank=True)
    vat_number = models.CharField(max_length=50, blank=True)
    is_tax_exempt = models.BooleanField(default=False)
    tax_exempt_number = models.CharField(max_length=50, blank=True)
    is_1099_vendor = models.BooleanField(default=False)  # US Tax reporting
    
    # Default Accounts
    default_expense_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_expense'
    )
    accounts_payable_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_payable'
    )
    
    # Banking Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    routing_number = models.CharField(max_length=20, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    
    # CRM Integration
    crm_contact_id = models.IntegerField(null=True, blank=True)
    lead_source = models.CharField(max_length=100, blank=True)
    
    # Inventory Integration
    is_inventory_supplier = models.BooleanField(default=False)
    supplier_code = models.CharField(max_length=50, blank=True)
    
    # Performance Metrics
    average_payment_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    quality_rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    
    # Contract Information
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    contract_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_vendors'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['company_name']
        db_table = 'finance_vendors'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'vendor_number'],
                name='unique_tenant_vendor_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'vendor_type']),
            models.Index(fields=['tenant', 'is_inventory_supplier']),
            models.Index(fields=['tenant', 'company_name']),
        ]
        
    def __str__(self):
        return self.display_name or self.company_name
    
    def save(self, *args, **kwargs):
        if not self.vendor_number:
            self.vendor_number = self.generate_vendor_number()
        if not self.display_name:
            self.display_name = self.company_name
        super().save(*args, **kwargs)
    
    def generate_vendor_number(self):
        """Generate unique vendor number"""
        return generate_code('VEN', self.tenant_id)
    
    def clean(self):
        """Validate vendor"""
        if self.credit_limit and self.credit_limit < 0:
            raise ValidationError('Credit limit cannot be negative')
        
        if self.payment_terms_days > 365:
            raise ValidationError('Payment terms cannot exceed 365 days')
        
        if self.contract_start_date and self.contract_end_date:
            if self.contract_start_date >= self.contract_end_date:
                raise ValidationError('Contract start date must be before end date')
    
    @property
    def full_name(self):
        """Get full vendor name"""
        if self.primary_contact:
            return f'{self.company_name} ({self.primary_contact})'
        return self.company_name
    
    @property
    def is_overdue(self):
        """Check if vendor has overdue bills"""
        return self.bills.filter(
            status__in=['OPEN', 'APPROVED'],
            due_date__lt=date.today()
        ).exists()
    
    @property
    def has_active_contract(self):
        """Check if vendor has an active contract"""
        if not self.contract_start_date or not self.contract_end_date:
            return False
        
        today = date.today()
        return self.contract_start_date <= today <= self.contract_end_date
    
    def get_outstanding_balance(self):
        """Get total outstanding balance"""
        outstanding = self.bills.filter(
            status__in=['OPEN', 'APPROVED', 'PARTIAL']
        ).aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')
        
        return outstanding
    
    def get_ytd_purchases(self):
        """Get year-to-date purchases"""
        current_year = timezone.now().year
        ytd_purchases = self.bills.filter(
            bill_date__year=current_year,
            status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
        ).aggregate(total=models.Sum('total_amount'))
        
        return ytd_purchases['total'] or Decimal('0.00')
    
    def update_performance_metrics(self):
        """Update vendor performance metrics"""
        from ..services.vendor_performance import VendorPerformanceService
        
        service = VendorPerformanceService(self.tenant)
        service.calculate_vendor_metrics(self)
    
    def get_aging_summary(self):
        """Get accounts payable aging summary"""
        from datetime import timedelta
        
        today = date.today()
        aging = {
            'current': Decimal('0.00'),
            '1_30_days': Decimal('0.00'),
            '31_60_days': Decimal('0.00'),
            '61_90_days': Decimal('0.00'),
            'over_90_days': Decimal('0.00')
        }
        
        overdue_bills = self.bills.filter(
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__lt=today
        )
        
        for bill in overdue_bills:
            days_overdue = (today - bill.due_date).days
            
            if days_overdue <= 30:
                aging['1_30_days'] += bill.amount_due
            elif days_overdue <= 60:
                aging['31_60_days'] += bill.amount_due
            elif days_overdue <= 90:
                aging['61_90_days'] += bill.amount_due
            else:
                aging['over_90_days'] += bill.amount_due
        
        # Current (not yet due)
        current_bills = self.bills.filter(
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            due_date__gte=today
        )
        aging['current'] = current_bills.aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')
        
        return aging


class VendorContact(TenantBaseModel):
    """Additional contacts for vendors"""
    
    CONTACT_TYPES = [
        ('PRIMARY', 'Primary Contact'),
        ('ACCOUNTING', 'Accounting Contact'),
        ('PURCHASING', 'Purchasing Contact'),
        ('TECHNICAL', 'Technical Contact'),
        ('SALES', 'Sales Contact'),
        ('SUPPORT', 'Support Contact'),
        ('BILLING', 'Billing Contact'),
        ('OTHER', 'Other'),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    
    # Contact Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    title = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    extension = models.CharField(max_length=10, blank=True)
    
    # Settings
    is_primary = models.BooleanField(default=False)
    receive_communications = models.BooleanField(default=True)
    receive_pos = models.BooleanField(default=False)
    receive_bills = models.BooleanField(default=False)
    
    # Additional Information
    notes = models.TextField(blank=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
            ('MOBILE', 'Mobile'),
        ],
        default='EMAIL'
    )
    
    class Meta:
        ordering = ['vendor', 'last_name', 'first_name']
        db_table = 'finance_vendor_contacts'
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.vendor.company_name})"
    
    @property
    def full_name(self):
        """Get full contact name"""
        return f"{self.first_name} {self.last_name}"


class Bill(TenantBaseModel, SoftDeleteMixin):
    """Enhanced vendor bills with multi-currency and workflow support"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('OPEN', 'Open'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
        ('ON_HOLD', 'On Hold'),
        ('DISPUTED', 'Disputed'),
    ]
    
    BILL_TYPES = [
        ('STANDARD', 'Standard Bill'),
        ('RECURRING', 'Recurring Bill'),
        ('CREDIT_NOTE', 'Credit Note'),
        ('DEBIT_NOTE', 'Debit Note'),
        ('EXPENSE_REPORT', 'Expense Report'),
        ('UTILITIES', 'Utilities'),
        ('RENT', 'Rent'),
        ('PROFESSIONAL_SERVICES', 'Professional Services'),
    ]
    
    # Bill Identification
    bill_number = models.CharField(max_length=50)
    vendor_invoice_number = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    bill_type = models.CharField(max_length=25, choices=BILL_TYPES, default='STANDARD')
    
    # Vendor Information
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='bills')
    vendor_contact = models.ForeignKey(
        VendorContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Dates
    bill_date = models.DateField()
    due_date = models.DateField()
    received_date = models.DateField(null=True, blank=True)
    service_period_start = models.DateField(null=True, blank=True)
    service_period_end = models.DateField(null=True, blank=True)
    
    # Status & Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_bills'
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
    
    # Source Documents
    source_purchase_order = models.ForeignKey(
        'inventory.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills'
    )
    
    # Recurring Bill Settings
    is_recurring = models.BooleanField(default=False)
    recurring_interval_days = models.PositiveIntegerField(null=True, blank=True)
    next_bill_date = models.DateField(null=True, blank=True)
    parent_bill = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    auto_approve = models.BooleanField(default=False)
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
    
    # Journal Entry
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills'
    )
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Workflow
    workflow_state = models.CharField(max_length=50, blank=True)
    approval_workflow = models.JSONField(default=list, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_bills'
    )
    
    class Meta:
        ordering = ['-bill_date', '-bill_number']
        db_table = 'finance_bills'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'bill_number'],
                name='unique_tenant_bill_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'vendor']),
            models.Index(fields=['tenant', 'due_date', 'status']),
            models.Index(fields=['tenant', 'bill_date']),
            models.Index(fields=['tenant', 'vendor_invoice_number']),
        ]
        
    def __str__(self):
        return f'{self.bill_number} - {self.vendor.company_name}'
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        
        # Calculate totals
        self.calculate_totals()
        
        # Calculate base currency amounts
        self.calculate_base_currency_amounts()
        
        super().save(*args, **kwargs)
    
    def generate_bill_number(self):
        """Generate unique bill number"""
        from .core import FinanceSettings
        
        try:
            settings = FinanceSettings.objects.get(tenant=self.tenant)
            return generate_code(settings.bill_prefix, self.tenant_id, settings.bill_starting_number)
        except FinanceSettings.DoesNotExist:
            return generate_code('BILL', self.tenant_id, 1000)
    
    def calculate_totals(self):
        """Calculate bill totals from line items"""
        line_totals = self.bill_items.aggregate(
            subtotal=models.Sum(
                models.F('quantity') * models.F('unit_cost') * (1 - models.F('discount_rate') / 100),
                output_field=models.DecimalField()
            ),
            tax_total=models.Sum('tax_amount', output_field=models.DecimalField())
        )
        
        gross_subtotal = line_totals['subtotal'] or Decimal('0.00')
        
        # Apply bill-level discount
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
    
    def clean(self):
        """Validate bill"""
        if self.bill_date > date.today():
            raise ValidationError('Bill date cannot be in the future')
        
        if self.due_date < self.bill_date:
            raise ValidationError('Due date cannot be before bill date')
        
        if self.service_period_start and self.service_period_end:
            if self.service_period_start >= self.service_period_end:
                raise ValidationError('Service period start must be before end date')
    
    @property
    def is_overdue(self):
        """Check if bill is overdue"""
        return date.today() > self.due_date and self.status in ['OPEN', 'APPROVED']
    
    @property
    def days_until_due(self):
        """Days until due date"""
        return (self.due_date - date.today()).days
    
    @property
    def days_overdue(self):
        """Days overdue (negative if not overdue)"""
        return (date.today() - self.due_date).days
    
    @property
    def can_be_approved(self):
        """Check if bill can be approved"""
        return self.status == 'PENDING_APPROVAL' and self.bill_items.exists()
    
    def approve_bill(self, user):
        """Approve the bill"""
        if self.status != 'PENDING_APPROVAL':
            raise ValidationError('Bill is not in pending approval status')
        
        self.status = 'OPEN'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()
        
        # Create journal entry
        self.create_journal_entry()
        
        # Update vendor balance
        self.vendor.current_balance += self.base_currency_amount_due
        self.vendor.save()
    
    def create_journal_entry(self):
        """Create journal entry for the bill"""
        from ..services.journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        return service.create_bill_journal_entry(self)
    
    def create_cogs_entries(self):
        """Create COGS entries for inventory items"""
        if not self.vendor.is_inventory_supplier:
            return
        
        from ..services.cogs import COGSService
        service = COGSService(self.tenant)
        service.create_bill_cogs_entries(self)
    
    def create_next_recurring_bill(self):
        """Create next occurrence of recurring bill"""
        if not self.is_recurring or not self.next_bill_date:
            return None
        
        from ..services.recurring_bill import RecurringBillService
        
        service = RecurringBillService(self.tenant)
        return service.create_next_bill(self)


class BillItem(TenantBaseModel):
    """Enhanced bill line items with inventory integration"""
    
    ITEM_TYPES = [
        ('PRODUCT', 'Product'),
        ('SERVICE', 'Service'),
        ('EXPENSE', 'Expense'),
        ('ASSET', 'Asset'),
        ('FREIGHT', 'Freight'),
        ('OTHER', 'Other'),
    ]
    
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='bill_items')
    line_number = models.IntegerField()
    
    # Item Information
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='EXPENSE')
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
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    line_total = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Account Classification
    expense_account = models.ForeignKey('finance.Account', on_delete=models.PROTECT)
    
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
    lot_number = models.CharField(max_length=100, blank=True)
    serial_numbers = models.JSONField(default=list, blank=True)
    
    # Purchase Order Integration
    purchase_order_item = models.ForeignKey(
        'inventory.PurchaseOrderItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Received Information
    quantity_received = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=Decimal('0.0000')
    )
    received_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['bill', 'line_number']
        db_table = 'finance_bill_items'
        
    def __str__(self):
        return f'{self.bill.bill_number} - Line {self.line_number}: {self.description}'
    
    def save(self, *args, **kwargs):
        # Calculate line total
        line_subtotal = self.quantity * self.unit_cost
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
        
        super().save(*args, **kwargs)
        
        # Update inventory if this is a product purchase
        if self.product and self.item_type == 'PRODUCT' and self.bill.status == 'APPROVED':
            self.update_inventory()
    
    def clean(self):
        """Validate bill item"""
        if self.quantity <= 0:
            raise ValidationError('Quantity must be positive')
        
        if self.unit_cost < 0:
            raise ValidationError('Unit cost cannot be negative')
        
        if self.quantity_received > self.quantity:
            raise ValidationError('Received quantity cannot exceed ordered quantity')
    
    def update_inventory(self):
        """Update inventory levels and cost layers"""
        if not self.product or self.bill.status != 'APPROVED':
            return
        
        from ..services.inventory import InventoryService
        service = InventoryService(self.tenant)
        service.process_purchase_receipt(self)
    
    @property
    def extended_cost(self):
        """Get extended cost (quantity * unit cost)"""
        return self.quantity * self.unit_cost
    
    @property
    def net_amount(self):
        """Get net amount after discount"""
        return self.line_total
    
    @property
    def total_with_tax(self):
        """Get total including tax"""
        return self.line_total + self.tax_amount
    
    @property
    def is_fully_received(self):
        """Check if item is fully received"""
        return self.quantity_received >= self.quantity
    
    @property
    def pending_quantity(self):
        """Get quantity still pending receipt"""
        return self.quantity - self.quantity_received