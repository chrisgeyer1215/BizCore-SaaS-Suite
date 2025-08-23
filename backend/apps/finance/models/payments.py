"""
Payment Processing Models
Enhanced payment records with multi-currency and integration support
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code
from .currency import Currency
from .base import (
    AIFinanceBaseMixin, 
    SmartCategorizationMixin, 
    PredictiveAnalyticsMixin, 
    IntelligentMatchingMixin
)

User = get_user_model()


class Payment(TenantBaseModel, SoftDeleteMixin, AIFinanceBaseMixin, 
              SmartCategorizationMixin, PredictiveAnalyticsMixin, IntelligentMatchingMixin):
    """AI-Enhanced payment records with fraud detection and intelligent matching"""
    
    PAYMENT_TYPE_CHOICES = [
        ('RECEIVED', 'Payment Received'),
        ('MADE', 'Payment Made'),
        ('TRANSFER', 'Transfer'),
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('REFUND', 'Refund'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CHECK', 'Check'),
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('ACH', 'ACH'),
        ('WIRE_TRANSFER', 'Wire Transfer'),
        ('PAYPAL', 'PayPal'),
        ('STRIPE', 'Stripe'),
        ('SQUARE', 'Square'),
        ('CRYPTOCURRENCY', 'Cryptocurrency'),
        ('MONEY_ORDER', 'Money Order'),
        ('GIFT_CARD', 'Gift Card'),
        ('STORE_CREDIT', 'Store Credit'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('CLEARED', 'Cleared'),
        ('BOUNCED', 'Bounced'),
        ('CANCELLED', 'Cancelled'),
        ('RECONCILED', 'Reconciled'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('DISPUTED', 'Disputed'),
    ]
    
    # Payment Identification
    payment_number = models.CharField(max_length=50)
    reference_number = models.CharField(max_length=100, blank=True)
    external_transaction_id = models.CharField(max_length=200, blank=True)
    confirmation_number = models.CharField(max_length=100, blank=True)
    
    # Payment Details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Parties
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    vendor = models.ForeignKey(
        'finance.Vendor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Multi-Currency Support
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    base_currency_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Bank Account
    bank_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        related_name='payments',
        limit_choices_to={'is_bank_account': True}
    )
    
    # Payment Method Specific Information
    # Check Information
    check_number = models.CharField(max_length=50, blank=True)
    check_date = models.DateField(null=True, blank=True)
    check_memo = models.CharField(max_length=200, blank=True)
    
    # Credit Card Information (PCI compliant - no sensitive data)
    card_last_four = models.CharField(max_length=4, blank=True)
    card_type = models.CharField(max_length=20, blank=True)
    card_expiry_month = models.CharField(max_length=2, blank=True)
    card_expiry_year = models.CharField(max_length=4, blank=True)
    card_holder_name = models.CharField(max_length=200, blank=True)
    
    # Processing Information
    processor_name = models.CharField(max_length=100, blank=True)
    processor_transaction_id = models.CharField(max_length=200, blank=True)
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    processing_fee_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processing_fees'
    )
    
    # Gateway Information
    gateway_response = models.JSONField(default=dict, blank=True)
    gateway_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    memo = models.CharField(max_length=200, blank=True)
    
    # Journal Entry
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Reconciliation
    bank_transaction = models.ForeignKey(
        'finance.BankTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_payments'
    )
    reconciled_date = models.DateField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciled_payments'
    )
    
    # Refund Information
    original_payment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds'
    )
    refund_reason = models.TextField(blank=True)
    is_partial_refund = models.BooleanField(default=False)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payments'
    )
    
    class Meta:
        ordering = ['-payment_date', '-payment_number']
        db_table = 'finance_payments'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'payment_number'],
                name='unique_tenant_payment_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'payment_type', 'status']),
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['tenant', 'vendor', 'status']),
            models.Index(fields=['tenant', 'payment_date']),
            models.Index(fields=['tenant', 'external_transaction_id']),
        ]
        
    def __str__(self):
        party = self.customer or self.vendor or 'Unknown'
        return f'{self.payment_number} - {party} ({self.amount} {self.currency.code})'
    
    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        
        # Calculate base currency amount
        self.base_currency_amount = self.amount * self.exchange_rate
        
        super().save(*args, **kwargs)
    
    def generate_payment_number(self):
        """Generate unique payment number"""
        from .core import FinanceSettings
        
        try:
            settings = FinanceSettings.objects.get(tenant=self.tenant)
            prefix = settings.payment_prefix
        except FinanceSettings.DoesNotExist:
            prefix = 'PAY'
        
        if self.payment_type == 'RECEIVED':
            prefix = 'REC'
        elif self.payment_type == 'MADE':
            prefix = 'PAY'
        elif self.payment_type == 'REFUND':
            prefix = 'REF'
        
        return generate_code(prefix, self.tenant_id)
    
    def clean(self):
        """Validate payment"""
        if self.amount <= 0:
            raise ValidationError('Payment amount must be positive')
        
        if self.payment_type == 'RECEIVED' and not self.customer:
            raise ValidationError('Customer is required for received payments')
        
        if self.payment_type == 'MADE' and not self.vendor:
            raise ValidationError('Vendor is required for made payments')
        
        if self.processing_fee > self.amount:
            raise ValidationError('Processing fee cannot exceed payment amount')
        
        if self.check_date and self.check_date > self.payment_date:
            raise ValidationError('Check date cannot be after payment date')
    
    @transaction.atomic
    def apply_to_invoices(self, invoice_applications):
        """Apply payment to invoices"""
        if self.payment_type != 'RECEIVED':
            raise ValidationError('Only received payments can be applied to invoices')
        
        total_applied = Decimal('0.00')
        
        for application in invoice_applications:
            invoice_id = application['invoice_id']
            amount_applied = Decimal(str(application['amount']))
            discount_amount = Decimal(str(application.get('discount_amount', '0.00')))
            
            # Validate invoice exists and belongs to correct customer
            from .invoicing import Invoice
            try:
                invoice = Invoice.objects.get(
                    id=invoice_id,
                    tenant=self.tenant,
                    customer=self.customer
                )
            except Invoice.DoesNotExist:
                raise ValidationError(f'Invoice {invoice_id} not found')
            
            # Create payment application
            PaymentApplication.objects.create(
                tenant=self.tenant,
                payment=self,
                invoice=invoice,
                amount_applied=amount_applied,
                discount_amount=discount_amount
            )
            
            total_applied += amount_applied
        
        if total_applied > self.amount:
            raise ValidationError('Cannot apply more than payment amount')
        
        return True
    
    @transaction.atomic
    def apply_to_bills(self, bill_applications):
        """Apply payment to bills"""
        if self.payment_type != 'MADE':
            raise ValidationError('Only made payments can be applied to bills')
        
        total_applied = Decimal('0.00')
        
        for application in bill_applications:
            bill_id = application['bill_id']
            amount_applied = Decimal(str(application['amount']))
            discount_amount = Decimal(str(application.get('discount_amount', '0.00')))
            
            # Validate bill exists and belongs to correct vendor
            from .vendors import Bill
            try:
                bill = Bill.objects.get(
                    id=bill_id,
                    tenant=self.tenant,
                    vendor=self.vendor
                )
            except Bill.DoesNotExist:
                raise ValidationError(f'Bill {bill_id} not found')
            
            # Create payment application
            PaymentApplication.objects.create(
                tenant=self.tenant,
                payment=self,
                bill=bill,
                amount_applied=amount_applied,
                discount_amount=discount_amount
            )
            
            total_applied += amount_applied
        
        if total_applied > self.amount:
            raise ValidationError('Cannot apply more than payment amount')
        
        return True
    
    def create_journal_entry(self):
        """Create journal entry for payment"""
        from ..services.journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        return service.create_payment_journal_entry(self)
    
    def process_refund(self, refund_amount=None, reason=''):
        """Process a refund for this payment"""
        if self.payment_type != 'RECEIVED':
            raise ValidationError('Only received payments can be refunded')
        
        if self.status != 'CLEARED':
            raise ValidationError('Only cleared payments can be refunded')
        
        refund_amount = refund_amount or self.amount
        
        if refund_amount > self.amount:
            raise ValidationError('Refund amount cannot exceed original payment amount')
        
        # Check if partial refunds already exist
        existing_refunds = self.refunds.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        if existing_refunds + refund_amount > self.amount:
            raise ValidationError('Total refund amount cannot exceed original payment')
        
        from ..services.payment import PaymentService
        
        service = PaymentService(self.tenant)
        return service.process_refund(self, refund_amount, reason)
    
    def void_payment(self, user, reason):
        """Void the payment"""
        if self.status in ['CLEARED', 'RECONCILED']:
            raise ValidationError('Cannot void cleared or reconciled payments')
        
        # Check if payment has been applied
        if self.applications.exists():
            raise ValidationError('Cannot void payments that have been applied to invoices/bills')
        
        self.status = 'CANCELLED'
        self.notes = f"{self.notes}\n\nVoided by {user.get_full_name()}: {reason}"
        self.save()
        
        # Reverse journal entry if exists
        if self.journal_entry:
            self.journal_entry.reverse_entry(user, f"Voiding payment {self.payment_number}")
    
    @property
    def net_amount(self):
        """Get net payment amount after fees"""
        return self.amount - self.processing_fee - self.gateway_fee
    
    @property
    def is_refunded(self):
        """Check if payment has been refunded"""
        return self.refunds.exists()
    
    @property
    def total_refunded(self):
        """Get total amount refunded"""
        return self.refunds.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    @property
    def available_for_refund(self):
        """Get amount available for refund"""
        return self.amount - self.total_refunded
    
    @property
    def is_applied(self):
        """Check if payment has been applied to invoices/bills"""
        return self.applications.exists()
    
    @property
    def total_applied(self):
        """Get total amount applied to invoices/bills"""
        return self.applications.aggregate(
            total=models.Sum('amount_applied')
        )['total'] or Decimal('0.00')
    
    @property
    def unapplied_amount(self):
        """Get amount not yet applied"""
        return self.amount - self.total_applied


class PaymentApplication(TenantBaseModel):
    """Enhanced payment applications with discount support"""
    
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='applications')
    
    # Document References
    invoice = models.ForeignKey(
        'finance.Invoice',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='applications'
    )
    bill = models.ForeignKey(
        'finance.Bill',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='applications'
    )
    
    # Application Details
    amount_applied = models.DecimalField(max_digits=15, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    application_date = models.DateField(auto_now_add=True)
    
    # Multi-Currency
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    base_currency_amount_applied = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Additional Information
    notes = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Tracking
    applied_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-application_date']
        db_table = 'finance_payment_applications'
        
    def __str__(self):
        document = self.invoice or self.bill
        return f'{self.payment.payment_number} -> {document} ({self.amount_applied})'
    
    def save(self, *args, **kwargs):
        # Calculate base currency amount
        self.base_currency_amount_applied = self.amount_applied * self.exchange_rate
        
        super().save(*args, **kwargs)
        
        # Update document amounts
        if self.invoice:
            self.update_invoice_amounts()
        elif self.bill:
            self.update_bill_amounts()
    
    def clean(self):
        """Validate payment application"""
        if not self.invoice and not self.bill:
            raise ValidationError('Either invoice or bill must be specified')
        
        if self.invoice and self.bill:
            raise ValidationError('Cannot apply to both invoice and bill')
        
        if self.amount_applied <= 0:
            raise ValidationError('Applied amount must be positive')
        
        if self.discount_amount < 0:
            raise ValidationError('Discount amount cannot be negative')
    
    def update_invoice_amounts(self):
        """Update invoice payment amounts"""
        if not self.invoice:
            return
        
        total_applied = self.invoice.applications.aggregate(
            total=models.Sum('amount_applied')
        )['total'] or Decimal('0.00')
        
        total_discount = self.invoice.applications.aggregate(
            total=models.Sum('discount_amount')
        )['total'] or Decimal('0.00')
        
        self.invoice.amount_paid = total_applied
        self.invoice.amount_due = self.invoice.total_amount - total_applied - total_discount
        
        # Update status
        if self.invoice.amount_due <= Decimal('0.00'):
            self.invoice.status = 'PAID'
        elif self.invoice.amount_paid > Decimal('0.00'):
            self.invoice.status = 'PARTIAL'
        else:
            self.invoice.status = 'OPEN'
        
        self.invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])
    
    def update_bill_amounts(self):
        """Update bill payment amounts"""
        if not self.bill:
            return
        
        total_applied = self.bill.applications.aggregate(
            total=models.Sum('amount_applied')
        )['total'] or Decimal('0.00')
        
        total_discount = self.bill.applications.aggregate(
            total=models.Sum('discount_amount')
        )['total'] or Decimal('0.00')
        
        self.bill.amount_paid = total_applied
        self.bill.amount_due = self.bill.total_amount - total_applied - total_discount
        
        # Update status
        if self.bill.amount_due <= Decimal('0.00'):
            self.bill.status = 'PAID'
        elif self.bill.amount_paid > Decimal('0.00'):
            self.bill.status = 'PARTIAL'
        else:
            self.bill.status = 'OPEN'
        
        self.bill.save(update_fields=['amount_paid', 'amount_due', 'status'])
    
    @property
    def total_credit_taken(self):
        """Get total credit taken (applied amount + discount)"""
        return self.amount_applied + self.discount_amount
    
    @property
    def document(self):
        """Get the related document (invoice or bill)"""
        return self.invoice or self.bill