"""
Bank Account and Reconciliation Models - Part 1
Enhanced bank management and reconciliation with automation
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import json
import re

from apps.core.models import TenantBaseModel

User = get_user_model()


class BankAccount(TenantBaseModel):
    """Enhanced bank account model combining features from both approaches"""
    
    ACCOUNT_TYPES = [
        ('CHECKING', 'Checking'),
        ('SAVINGS', 'Savings'),
        ('MONEY_MARKET', 'Money Market'),
        ('CREDIT_CARD', 'Credit Card'),
        ('LINE_OF_CREDIT', 'Line of Credit'),
        ('PETTY_CASH', 'Petty Cash'),
    ]
    
    # Core Account Relationship
    account = models.OneToOneField(
        'finance.Account', 
        on_delete=models.CASCADE, 
        related_name='bank_details',
        limit_choices_to={'is_bank_account': True}
    )
    
    # Bank Information
    bank_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    
    # Routing Information
    routing_number = models.CharField(max_length=20, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    branch_code = models.CharField(max_length=20, blank=True)
    
    # Contact Information
    bank_contact_name = models.CharField(max_length=200, blank=True)
    bank_contact_phone = models.CharField(max_length=20, blank=True)
    bank_contact_email = models.EmailField(blank=True)
    
    # Bank Feed Integration
    enable_bank_feeds = models.BooleanField(default=False)
    bank_feed_id = models.CharField(max_length=100, blank=True)
    bank_feed_provider = models.CharField(max_length=50, blank=True)
    last_feed_sync = models.DateTimeField(null=True, blank=True)
    feed_sync_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MANUAL', 'Manual Only'),
        ],
        default='DAILY'
    )
    
    # Statement Import Settings
    statement_import_format = models.CharField(
        max_length=20,
        choices=[
            ('CSV', 'CSV File'),
            ('QFX', 'Quicken QFX'),
            ('OFX', 'Open Financial Exchange'),
            ('MT940', 'SWIFT MT940'),
            ('BAI', 'BAI Format'),
            ('BANK_FEED', 'Bank Feed'),
            ('EXCEL', 'Excel File'),
        ],
        default='CSV'
    )
    
    # CSV Import Configuration
    csv_delimiter = models.CharField(max_length=5, default=',')
    csv_encoding = models.CharField(max_length=20, default='utf-8')
    csv_skip_rows = models.IntegerField(default=1)
    csv_column_mapping = models.JSONField(default=dict, blank=True)
    
    # Reconciliation Settings
    auto_reconcile = models.BooleanField(default=False)
    reconciliation_tolerance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.01')
    )
    auto_match_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00'),
        help_text="Minimum confidence percentage for auto-matching"
    )
    
    # Balance Tracking
    current_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    available_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    last_reconciled_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    last_reconciliation_date = models.DateField(null=True, blank=True)
    
    # Credit Card Specific
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    minimum_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    payment_due_date = models.DateField(null=True, blank=True)
    
    # Notifications
    low_balance_alert = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    send_balance_alerts = models.BooleanField(default=False)
    alert_email = models.EmailField(blank=True)
    
    # Security
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    require_approval_over = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'finance_bank_accounts'
        verbose_name = 'Bank Account'
        verbose_name_plural = 'Bank Accounts'
        ordering = ['bank_name', 'account_number']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'account_number', 'bank_name'],
                name='unique_tenant_bank_account'
            ),
        ]
        
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
    
    def clean(self):
        """Validate bank account"""
        if self.account_type == 'CREDIT_CARD' and not self.credit_limit:
            raise ValidationError('Credit limit is required for credit card accounts')
        
        if self.low_balance_alert and self.low_balance_alert < 0:
            raise ValidationError('Low balance alert cannot be negative')
        
        if self.reconciliation_tolerance < 0:
            raise ValidationError('Reconciliation tolerance cannot be negative')
    
    @property
    def masked_account_number(self):
        """Get masked account number for security"""
        if len(self.account_number) > 4:
            return f"****{self.account_number[-4:]}"
        return self.account_number
    
    @property
    def available_credit(self):
        """Get available credit for credit card accounts"""
        if self.account_type == 'CREDIT_CARD' and self.credit_limit:
            return self.credit_limit + self.current_balance  # Balance is negative for credit cards
        return None
    
    @property
    def is_overdrawn(self):
        """Check if account is overdrawn"""
        if self.account_type == 'CREDIT_CARD':
            return self.available_credit < 0
        return self.current_balance < 0
    
    @property
    def days_since_last_reconciliation(self):
        """Days since last reconciliation"""
        if self.last_reconciliation_date:
            return (date.today() - self.last_reconciliation_date).days
        return None
    
    def update_balance(self, amount, transaction_type='DEBIT'):
        """Update account balance"""
        if transaction_type == 'DEBIT':
            self.current_balance -= amount
        else:  # CREDIT
            self.current_balance += amount
        
        # Update available balance (same for non-credit accounts)
        if self.account_type != 'CREDIT_CARD':
            self.available_balance = self.current_balance
        
        self.save(update_fields=['current_balance', 'available_balance'])
    
    def check_low_balance(self):
        """Check if balance is below alert threshold"""
        if self.low_balance_alert and self.send_balance_alerts:
            return self.current_balance <= self.low_balance_alert
        return False


class BankStatement(TenantBaseModel):
    """Enhanced bank statement model"""
    
    PROCESSING_STATUS_CHOICES = [
        ('IMPORTED', 'Imported'),
        ('PROCESSING', 'Processing'),
        ('PROCESSED', 'Processed'),
        ('RECONCILED', 'Reconciled'),
        ('ERROR', 'Error'),
    ]
    
    bank_account = models.ForeignKey(
        BankAccount, 
        on_delete=models.CASCADE, 
        related_name='statements'
    )
    
    # Statement Period
    statement_date = models.DateField()
    statement_period_start = models.DateField()
    statement_period_end = models.DateField()
    
    # Statement Balances
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Import Information
    import_date = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    import_file_name = models.CharField(max_length=255, blank=True)
    import_format = models.CharField(max_length=20)
    imported_from = models.CharField(max_length=100, blank=True)  # Bank feed, manual, etc.
    
    # Processing Status
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='IMPORTED'
    )
    processing_errors = models.JSONField(default=list, blank=True)
    
    # Transaction Counts
    total_transactions = models.IntegerField(default=0)
    matched_transactions = models.IntegerField(default=0)
    unmatched_transactions = models.IntegerField(default=0)
    auto_matched_transactions = models.IntegerField(default=0)
    manual_matched_transactions = models.IntegerField(default=0)
    
    # Reconciliation Status
    is_reconciled = models.BooleanField(default=False)
    reconciled_date = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciled_statements'
    )
    
    # Statement Metadata
    statement_id = models.CharField(max_length=100, blank=True)
    statement_checksum = models.CharField(max_length=64, blank=True)
    
    class Meta:
        db_table = 'finance_bank_statements'
        ordering = ['-statement_date']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'bank_account', 'statement_date'],
                name='unique_bank_statement_per_date'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'bank_account', 'processing_status']),
            models.Index(fields=['tenant', 'statement_period_start', 'statement_period_end']),
        ]
        
    def __str__(self):
        return f"{self.bank_account.bank_name} - {self.statement_date}"
    
    def clean(self):
        """Validate bank statement"""
        if self.statement_period_start >= self.statement_period_end:
            raise ValidationError('Statement start date must be before end date')
        
        if self.statement_date < self.statement_period_start or self.statement_date > self.statement_period_end:
            raise ValidationError('Statement date must be within the statement period')
    
    @property
    def net_change(self):
        """Net change in balance during statement period"""
        return self.closing_balance - self.opening_balance
    
    @property
    def matching_percentage(self):
        """Percentage of transactions that are matched"""
        if self.total_transactions > 0:
            return (self.matched_transactions / self.total_transactions) * 100
        return Decimal('0.00')
    
    def update_transaction_counts(self):
        """Update transaction count statistics"""
        transactions = self.bank_transactions.all()
        self.total_transactions = transactions.count()
        self.matched_transactions = transactions.filter(
            reconciliation_status__in=['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH']
        ).count()
        self.unmatched_transactions = self.total_transactions - self.matched_transactions
        self.auto_matched_transactions = transactions.filter(
            reconciliation_status='AUTO_MATCH'
        ).count()
        self.manual_matched_transactions = transactions.filter(
            reconciliation_status='MANUAL_MATCH'
        ).count()
        
        self.save(update_fields=[
            'total_transactions', 'matched_transactions', 'unmatched_transactions',
            'auto_matched_transactions', 'manual_matched_transactions'
        ])
    
    def process_auto_matching(self):
        """Process automatic transaction matching"""
        from ..services.bank_reconciliation import BankReconciliationService
        
        service = BankReconciliationService(self.tenant)
        return service.auto_match_statement_transactions(self)
class BankTransaction(TenantBaseModel):
    """Enhanced bank transaction model with comprehensive features"""
    
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('TRANSFER', 'Transfer'),
        ('FEE', 'Bank Fee'),
        ('INTEREST', 'Interest'),
        ('CHECK', 'Check'),
        ('ATM', 'ATM Transaction'),
        ('DEBIT_CARD', 'Debit Card'),
        ('CREDIT_CARD', 'Credit Card'),
        ('ACH', 'ACH Transaction'),
        ('WIRE', 'Wire Transfer'),
        ('CARD', 'Card Transaction'),
        ('ONLINE', 'Online Transaction'),
        ('MOBILE', 'Mobile Transaction'),
        ('OTHER', 'Other'),
    ]
    
    RECONCILIATION_STATUS_CHOICES = [
        ('UNMATCHED', 'Unmatched'),
        ('MATCHED', 'Matched'),
        ('MANUAL_MATCH', 'Manually Matched'),
        ('AUTO_MATCH', 'Auto Matched'),
        ('EXCLUDED', 'Excluded'),
        ('PENDING', 'Pending Review'),
        ('RECONCILED', 'Reconciled'),
        ('DUPLICATE', 'Duplicate'),
    ]
    
    bank_statement = models.ForeignKey(
        'finance.BankStatement', 
        on_delete=models.CASCADE, 
        related_name='bank_transactions'
    )
    
    # Transaction Details
    transaction_date = models.DateField()
    post_date = models.DateField(null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Description Information
    description = models.TextField()
    memo = models.CharField(max_length=255, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    check_number = models.CharField(max_length=50, blank=True)
    
    # Payee/Bank Information
    payee = models.CharField(max_length=200, blank=True)
    bank_transaction_id = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    
    # Running Balance
    running_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Reconciliation Status
    reconciliation_status = models.CharField(
        max_length=20, 
        choices=RECONCILIATION_STATUS_CHOICES, 
        default='UNMATCHED'
    )
    
    # Matching Information
    matched_payment = models.ForeignKey(
        'finance.Payment', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='bank_matches'
    )
    matched_journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bank_matches'
    )
    matched_invoice = models.ForeignKey(
        'finance.Invoice',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bank_matches'
    )
    matched_bill = models.ForeignKey(
        'finance.Bill',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bank_matches'
    )
    
    # Reconciliation Details
    reconciliation_difference = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Manual Review
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='reviewed_bank_transactions'
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Duplicate Detection
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='duplicates'
    )
    
    # Auto-matching metadata
    match_confidence = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, blank=True,
        help_text="Confidence score for auto-matching (0-100)"
    )
    matching_rule_applied = models.CharField(max_length=100, blank=True)
    matching_criteria = models.JSONField(default=dict, blank=True)
    
    # Additional Classification
    is_transfer = models.BooleanField(default=False)
    transfer_account = models.ForeignKey(
        'finance.BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_transactions'
    )
    
    # Import metadata
    import_id = models.CharField(max_length=100, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'finance_bank_transactions'
        ordering = ['-transaction_date', '-id']
        indexes = [
            models.Index(fields=['tenant', 'bank_statement', 'reconciliation_status']),
            models.Index(fields=['tenant', 'transaction_date', 'amount']),
            models.Index(fields=['tenant', 'reference_number']),
            models.Index(fields=['tenant', 'description']),
            models.Index(fields=['tenant', 'bank_transaction_id']),
            models.Index(fields=['tenant', 'payee']),
        ]
        
    def __str__(self):
        return f"{self.transaction_date} - {self.description}: {self.amount}"
    
    def clean(self):
        """Validate bank transaction"""
        if self.post_date and self.transaction_date > self.post_date:
            raise ValidationError('Transaction date cannot be after post date')
        
        if self.amount == 0:
            raise ValidationError('Transaction amount cannot be zero')
    
    def auto_match(self):
        """Attempt to auto-match with existing transactions"""
        from ..services.bank_reconciliation import BankReconciliationService
        
        service = BankReconciliationService(self.tenant)
        return service.auto_match_transaction(self)
    
    def mark_as_matched(self, matched_record, user=None, confidence=None, criteria=None):
        """Mark transaction as matched with a specific record"""
        # Clear existing matches
        self.matched_payment = None
        self.matched_journal_entry = None
        self.matched_invoice = None
        self.matched_bill = None
        
        # Set appropriate match
        if hasattr(matched_record, '_meta'):
            model_name = matched_record._meta.model_name
            if model_name == 'payment':
                self.matched_payment = matched_record
            elif model_name == 'journalentry':
                self.matched_journal_entry = matched_record
            elif model_name == 'invoice':
                self.matched_invoice = matched_record
            elif model_name == 'bill':
                self.matched_bill = matched_record
        
        self.reconciliation_status = 'AUTO_MATCH' if confidence else 'MANUAL_MATCH'
        self.match_confidence = confidence
        self.matching_criteria = criteria or {}
        
        if user:
            self.reviewed_by = user
            self.reviewed_date = timezone.now()
        
        self.save()
    
    def unmatch(self, user=None):
        """Remove matching from transaction"""
        self.matched_payment = None
        self.matched_journal_entry = None
        self.matched_invoice = None
        self.matched_bill = None
        self.reconciliation_status = 'UNMATCHED'
        self.match_confidence = None
        self.matching_rule_applied = ''
        self.matching_criteria = {}
        
        if user:
            self.reviewed_by = user
            self.reviewed_date = timezone.now()
        
        self.save()
    
    def get_matched_record(self):
        """Get the matched record"""
        return (
            self.matched_payment or
            self.matched_journal_entry or
            self.matched_invoice or
            self.matched_bill
        )
    
    @property
    def is_credit(self):
        """Check if transaction is a credit (positive amount)"""
        return self.amount > 0
    
    @property
    def is_debit(self):
        """Check if transaction is a debit (negative amount)"""
        return self.amount < 0
    
    @property
    def formatted_amount(self):
        """Get formatted amount"""
        return f"{self.amount:,.2f}"
    
    def detect_duplicates(self):
        """Detect potential duplicate transactions"""
        # Look for transactions with same amount, date, and similar description
        potential_duplicates = BankTransaction.objects.filter(
            tenant=self.tenant,
            bank_statement__bank_account=self.bank_statement.bank_account,
            amount=self.amount,
            transaction_date=self.transaction_date,
            is_duplicate=False
        ).exclude(id=self.id)
        
        # Check for similar descriptions
        for transaction in potential_duplicates:
            similarity = self.calculate_description_similarity(transaction.description)
            if similarity > 0.8:  # 80% similarity threshold
                return transaction
        
        return None
    
    def calculate_description_similarity(self, other_description):
        """Calculate similarity between descriptions"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, self.description.lower(), other_description.lower()).ratio()


class BankReconciliation(TenantBaseModel):
    """Enhanced bank reconciliation model"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('REVIEWED', 'Reviewed'),
        ('APPROVED', 'Approved'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    bank_account = models.ForeignKey(
        'finance.BankAccount',
        on_delete=models.CASCADE,
        related_name='reconciliations'
    )
    bank_statement = models.ForeignKey(
        'finance.BankStatement',
        on_delete=models.CASCADE,
        related_name='reconciliations'
    )
    
    # Reconciliation Period
    reconciliation_date = models.DateField()
    previous_reconciliation_date = models.DateField(null=True, blank=True)
    cutoff_date = models.DateField()
    
    # Starting Balances
    statement_beginning_balance = models.DecimalField(max_digits=15, decimal_places=2)
    statement_ending_balance = models.DecimalField(max_digits=15, decimal_places=2)
    book_beginning_balance = models.DecimalField(max_digits=15, decimal_places=2)
    book_ending_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Reconciling Items
    total_deposits_in_transit = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    total_outstanding_checks = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    total_bank_adjustments = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    total_book_adjustments = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    
    # Results
    adjusted_bank_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    adjusted_book_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    difference = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    is_balanced = models.BooleanField(default=False)
    
    # Status and Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Session Information
    started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='started_reconciliations'
    )
    started_date = models.DateTimeField(auto_now_add=True)
    
    # Completion
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_reconciliations'
    )
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Review and Approval
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_reconciliations'
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_reconciliations'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Notes and Comments
    notes = models.TextField(blank=True)
    completion_notes = models.TextField(blank=True)
    
    # Auto-matching statistics
    auto_matched_count = models.IntegerField(default=0)
    manual_matched_count = models.IntegerField(default=0)
    unmatched_count = models.IntegerField(default=0)
    excluded_count = models.IntegerField(default=0)
    
    # Performance metrics
    total_time_spent = models.DurationField(null=True, blank=True)
    efficiency_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'finance_bank_reconciliations'
        ordering = ['-reconciliation_date']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'bank_account', 'reconciliation_date'],
                name='unique_bank_reconciliation'
            ),
        ]
        
    def __str__(self):
        return f"{self.bank_account} - {self.reconciliation_date}"
    
    def clean(self):
        """Validate reconciliation"""
        if self.cutoff_date > self.reconciliation_date:
            raise ValidationError('Cutoff date cannot be after reconciliation date')
        
        if self.previous_reconciliation_date and self.previous_reconciliation_date >= self.reconciliation_date:
            raise ValidationError('Previous reconciliation date must be before current date')
    
    def calculate_balances(self):
        """Calculate adjusted balances and difference"""
        self.adjusted_bank_balance = (
            self.statement_ending_balance +
            self.total_deposits_in_transit -
            self.total_outstanding_checks +
            self.total_bank_adjustments
        )
        
        self.adjusted_book_balance = (
            self.book_ending_balance + 
            self.total_book_adjustments
        )
        
        self.difference = self.adjusted_bank_balance - self.adjusted_book_balance
        self.is_balanced = abs(self.difference) <= self.bank_account.reconciliation_tolerance
        
        self.save()
    
    def complete_reconciliation(self, user):
        """Complete the reconciliation process"""
        if not self.is_balanced:
            raise ValidationError('Reconciliation must be balanced before completion')
        
        self.status = 'COMPLETED'
        self.completed_by = user
        self.completed_date = timezone.now()
        
        # Calculate time spent if start time is available
        if self.started_date:
            self.total_time_spent = self.completed_date - self.started_date
        
        self.save()
        
        # Update bank account
        self.bank_account.last_reconciled_balance = self.statement_ending_balance
        self.bank_account.last_reconciliation_date = self.reconciliation_date
        self.bank_account.save()
        
        # Mark statement as reconciled
        self.bank_statement.is_reconciled = True
        self.bank_statement.reconciled_date = timezone.now()
        self.bank_statement.reconciled_by = user
        self.bank_statement.save()
        
        # Update transaction statuses
        self.update_transaction_statuses()
        
        return True
    
    def update_transaction_statuses(self):
        """Update transaction reconciliation statuses"""
        # Mark matched transactions as reconciled
        matched_transactions = self.bank_statement.bank_transactions.filter(
            reconciliation_status__in=['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH']
        )
        matched_transactions.update(reconciliation_status='RECONCILED')
    
    def calculate_statistics(self):
        """Calculate reconciliation statistics"""
        transactions = self.bank_statement.bank_transactions.all()
        
        self.auto_matched_count = transactions.filter(
            reconciliation_status='AUTO_MATCH'
        ).count()
        self.manual_matched_count = transactions.filter(
            reconciliation_status='MANUAL_MATCH'
        ).count()
        self.unmatched_count = transactions.filter(
            reconciliation_status='UNMATCHED'
        ).count()
        self.excluded_count = transactions.filter(
            reconciliation_status='EXCLUDED'
        ).count()
        
        # Calculate efficiency score
        total_transactions = transactions.count()
        if total_transactions > 0:
            auto_match_percentage = (self.auto_matched_count / total_transactions) * 100
            self.efficiency_score = auto_match_percentage
        
        self.save()
    
    def get_reconciliation_summary(self):
        """Get reconciliation summary data"""
        return {
            'statement_balance': self.statement_ending_balance,
            'book_balance': self.book_ending_balance,
            'deposits_in_transit': self.total_deposits_in_transit,
            'outstanding_checks': self.total_outstanding_checks,
            'bank_adjustments': self.total_bank_adjustments,
            'book_adjustments': self.total_book_adjustments,
            'adjusted_bank_balance': self.adjusted_bank_balance,
            'adjusted_book_balance': self.adjusted_book_balance,
            'difference': self.difference,
            'is_balanced': self.is_balanced,
            'auto_matched': self.auto_matched_count,
            'manual_matched': self.manual_matched_count,
            'unmatched': self.unmatched_count,
            'excluded': self.excluded_count,
            'efficiency_score': self.efficiency_score,
        }
class ReconciliationAdjustment(TenantBaseModel):
    """Reconciliation adjustments and differences"""
    
    ADJUSTMENT_TYPES = [
        ('BANK_FEE', 'Bank Fee'),
        ('INTEREST_INCOME', 'Interest Income'),
        ('NSF_FEE', 'NSF Fee'),
        ('BANK_ERROR', 'Bank Error'),
        ('BOOK_ERROR', 'Book Error'),
        ('TIMING_DIFFERENCE', 'Timing Difference'),
        ('OUTSTANDING_CHECK', 'Outstanding Check'),
        ('DEPOSIT_IN_TRANSIT', 'Deposit in Transit'),
        ('SERVICE_CHARGE', 'Service Charge'),
        ('OVERDRAFT_FEE', 'Overdraft Fee'),
        ('ATM_FEE', 'ATM Fee'),
        ('WIRE_FEE', 'Wire Transfer Fee'),
        ('OTHER', 'Other Adjustment'),
    ]
    
    reconciliation = models.ForeignKey(
        'finance.BankReconciliation', 
        on_delete=models.CASCADE, 
        related_name='adjustments'
    )
    
    # Adjustment Details
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    adjustment_date = models.DateField()
    
    # Related Records
    bank_transaction = models.ForeignKey(
        'finance.BankTransaction', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='adjustments'
    )
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconciliation_adjustments'
    )
    
    # Account assignments
    debit_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        related_name='debit_adjustments'
    )
    credit_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        related_name='credit_adjustments'
    )
    
    # Processing
    is_processed = models.BooleanField(default=False)
    processed_date = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    
    # Approval
    requires_approval = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_adjustments'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'finance_reconciliation_adjustments'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.adjustment_type} - {self.amount}"
    
    def process_adjustment(self, user):
        """Process the adjustment by creating journal entry"""
        if self.is_processed:
            raise ValidationError('Adjustment has already been processed')
        
        if self.requires_approval and not self.is_approved:
            raise ValidationError('Adjustment requires approval before processing')
        
        from ..services.journal_entry import JournalEntryService
        
        service = JournalEntryService(self.tenant)
        journal_entry = service.create_reconciliation_adjustment_entry(self)
        
        self.journal_entry = journal_entry
        self.is_processed = True
        self.processed_by = user
        self.processed_date = timezone.now()
        self.save()
        
        return journal_entry


class ReconciliationRule(TenantBaseModel):
    """Enhanced automated matching rules for bank reconciliation"""
    
    RULE_TYPES = [
        ('AMOUNT_EXACT', 'Exact Amount Match'),
        ('AMOUNT_RANGE', 'Amount Range Match'),
        ('DESCRIPTION_CONTAINS', 'Description Contains'),
        ('DESCRIPTION_REGEX', 'Description Regex'),
        ('REFERENCE_MATCH', 'Reference Number Match'),
        ('PAYEE_MATCH', 'Payee Name Match'),
        ('DATE_RANGE', 'Date Range Match'),
        ('COMPOSITE', 'Composite Rule'),
        ('BANK_SPECIFIC', 'Bank Specific Pattern'),
    ]
    
    CONDITION_OPERATORS = [
        ('EQUALS', 'Equals'),
        ('CONTAINS', 'Contains'),
        ('STARTS_WITH', 'Starts With'),
        ('ENDS_WITH', 'Ends With'),
        ('REGEX', 'Regular Expression'),
        ('GREATER_THAN', 'Greater Than'),
        ('LESS_THAN', 'Less Than'),
        ('BETWEEN', 'Between'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    
    # Rule Configuration (JSON field for flexible rule definition)
    rule_config = models.JSONField(
        default=dict, 
        help_text="Rule configuration parameters"
    )
    
    # Matching Criteria
    amount_tolerance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.01')
    )
    date_tolerance_days = models.IntegerField(default=2)
    
    # Rule Conditions
    conditions = models.JSONField(
        default=list,
        help_text="List of conditions for composite rules"
    )
    
    # Rule Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=10, help_text="Lower numbers = higher priority")
    
    # Bank Account Restriction
    bank_accounts = models.ManyToManyField(
        'finance.BankAccount',
        blank=True,
        help_text="Restrict rule to specific bank accounts"
    )
    
    # Statistics
    matches_found = models.IntegerField(default=0)
    successful_matches = models.IntegerField(default=0)
    false_positives = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    average_confidence = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, blank=True
    )
    
    class Meta:
        db_table = 'finance_reconciliation_rules'
        ordering = ['priority', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.rule_type})"
    
    def apply_rule(self, bank_transaction):
        """Apply this rule to a bank transaction"""
        from ..services.reconciliation_rules import ReconciliationRuleEngine
        
        engine = ReconciliationRuleEngine(self.tenant)
        return engine.apply_rule(self, bank_transaction)
    
    def test_conditions(self, bank_transaction):
        """Test if bank transaction matches rule conditions"""
        if self.rule_type == 'AMOUNT_EXACT':
            return self.test_amount_exact(bank_transaction)
        elif self.rule_type == 'AMOUNT_RANGE':
            return self.test_amount_range(bank_transaction)
        elif self.rule_type == 'DESCRIPTION_CONTAINS':
            return self.test_description_contains(bank_transaction)
        elif self.rule_type == 'DESCRIPTION_REGEX':
            return self.test_description_regex(bank_transaction)
        elif self.rule_type == 'REFERENCE_MATCH':
            return self.test_reference_match(bank_transaction)
        elif self.rule_type == 'PAYEE_MATCH':
            return self.test_payee_match(bank_transaction)
        elif self.rule_type == 'DATE_RANGE':
            return self.test_date_range(bank_transaction)
        elif self.rule_type == 'COMPOSITE':
            return self.test_composite_conditions(bank_transaction)
        
        return False, 0
    
    def test_amount_exact(self, bank_transaction):
        """Test exact amount match"""
        target_amount = Decimal(str(self.rule_config.get('amount', 0)))
        difference = abs(bank_transaction.amount - target_amount)
        
        if difference <= self.amount_tolerance:
            confidence = max(0, 100 - (float(difference) / float(self.amount_tolerance)) * 10)
            return True, confidence
        
        return False, 0
    
    def test_amount_range(self, bank_transaction):
        """Test amount range match"""
        min_amount = Decimal(str(self.rule_config.get('min_amount', 0)))
        max_amount = Decimal(str(self.rule_config.get('max_amount', 0)))
        
        if min_amount <= bank_transaction.amount <= max_amount:
            # Higher confidence for amounts closer to middle of range
            range_size = max_amount - min_amount
            if range_size > 0:
                distance_from_center = abs(bank_transaction.amount - (min_amount + max_amount) / 2)
                confidence = max(50, 100 - (float(distance_from_center) / float(range_size)) * 50)
            else:
                confidence = 100
            return True, confidence
        
        return False, 0
    
    def test_description_contains(self, bank_transaction):
        """Test description contains text"""
        search_text = self.rule_config.get('search_text', '').lower()
        description = bank_transaction.description.lower()
        
        if search_text in description:
            # Higher confidence for exact matches or longer matches
            confidence = min(100, (len(search_text) / len(description)) * 100 + 50)
            return True, confidence
        
        return False, 0
    
    def test_description_regex(self, bank_transaction):
        """Test description regex match"""
        pattern = self.rule_config.get('regex_pattern', '')
        
        try:
            match = re.search(pattern, bank_transaction.description, re.IGNORECASE)
            if match:
                # Confidence based on match length
                confidence = min(100, (len(match.group()) / len(bank_transaction.description)) * 100 + 60)
                return True, confidence
        except re.error:
            pass
        
        return False, 0
    
    def test_reference_match(self, bank_transaction):
        """Test reference number match"""
        target_reference = self.rule_config.get('reference_number', '')
        
        if target_reference and bank_transaction.reference_number:
            if target_reference.lower() == bank_transaction.reference_number.lower():
                return True, 95
            elif target_reference.lower() in bank_transaction.reference_number.lower():
                return True, 75
        
        return False, 0
    
    def test_payee_match(self, bank_transaction):
        """Test payee name match"""
        target_payee = self.rule_config.get('payee_name', '').lower()
        
        if target_payee and bank_transaction.payee:
            payee = bank_transaction.payee.lower()
            if target_payee == payee:
                return True, 90
            elif target_payee in payee or payee in target_payee:
                return True, 70
        
        return False, 0
    
    def test_date_range(self, bank_transaction):
        """Test date range match"""
        start_date = self.rule_config.get('start_date')
        end_date = self.rule_config.get('end_date')
        
        if start_date and end_date:
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start <= bank_transaction.transaction_date <= end:
                return True, 80
        
        return False, 0
    
    def test_composite_conditions(self, bank_transaction):
        """Test multiple conditions"""
        if not self.conditions:
            return False, 0
        
        total_confidence = 0
        conditions_met = 0
        
        for condition in self.conditions:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            weight = condition.get('weight', 1)
            
            if self.test_single_condition(bank_transaction, field, operator, value):
                conditions_met += 1
                total_confidence += 80 * weight
        
        if conditions_met >= self.rule_config.get('min_conditions', 1):
            average_confidence = total_confidence / len(self.conditions)
            return True, min(100, average_confidence)
        
        return False, 0
    
    def test_single_condition(self, bank_transaction, field, operator, value):
        """Test a single condition"""
        # Get field value from bank transaction
        field_value = getattr(bank_transaction, field, None)
        
        if field_value is None:
            return False
        
        # Convert to string for text operations
        if isinstance(field_value, (str, int, float, Decimal)):
            field_str = str(field_value).lower()
            value_str = str(value).lower()
        else:
            field_str = str(field_value)
            value_str = str(value)
        
        # Apply operator
        if operator == 'EQUALS':
            return field_str == value_str
        elif operator == 'CONTAINS':
            return value_str in field_str
        elif operator == 'STARTS_WITH':
            return field_str.startswith(value_str)
        elif operator == 'ENDS_WITH':
            return field_str.endswith(value_str)
        elif operator == 'REGEX':
            try:
                return bool(re.search(value_str, field_str, re.IGNORECASE))
            except re.error:
                return False
        elif operator == 'GREATER_THAN':
            try:
                return float(field_value) > float(value)
            except (ValueError, TypeError):
                return False
        elif operator == 'LESS_THAN':
            try:
                return float(field_value) < float(value)
            except (ValueError, TypeError):
                return False
        elif operator == 'BETWEEN':
            try:
                min_val, max_val = value.split(',')
                return float(min_val) <= float(field_value) <= float(max_val)
            except (ValueError, TypeError, AttributeError):
                return False
        
        return False
    
    def update_statistics(self, found_match, was_successful, confidence=None):
        """Update rule performance statistics"""
        if found_match:
            self.matches_found += 1
            if was_successful:
                self.successful_matches += 1
            else:
                self.false_positives += 1
                
        if confidence:
            if self.average_confidence:
                # Running average
                total_matches = self.matches_found
                self.average_confidence = (
                    (self.average_confidence * (total_matches - 1) + confidence) / total_matches
                )
            else:
                self.average_confidence = confidence
                
        self.last_used = timezone.now()
        self.save()
    
    @property
    def success_rate(self):
        """Calculate rule success rate"""
        if self.matches_found > 0:
            return (self.successful_matches / self.matches_found) * 100
        return Decimal('0.00')


class ReconciliationLog(TenantBaseModel):
    """Audit log for reconciliation activities"""
    
    ACTION_TYPES = [
        ('RECONCILIATION_STARTED', 'Reconciliation Started'),
        ('TRANSACTION_MATCHED', 'Transaction Matched'),
        ('TRANSACTION_UNMATCHED', 'Transaction Unmatched'),
        ('ADJUSTMENT_ADDED', 'Adjustment Added'),
        ('RULE_APPLIED', 'Rule Applied'),
        ('RECONCILIATION_COMPLETED', 'Reconciliation Completed'),
        ('RECONCILIATION_REVIEWED', 'Reconciliation Reviewed'),
        ('RECONCILIATION_APPROVED', 'Reconciliation Approved'),
        ('STATEMENT_IMPORTED', 'Statement Imported'),
        ('AUTO_MATCH_RUN', 'Auto Match Process Run'),
        ('DUPLICATE_DETECTED', 'Duplicate Transaction Detected'),
        ('BALANCE_CALCULATED', 'Balance Calculated'),
    ]
    
    reconciliation = models.ForeignKey(
        'finance.BankReconciliation',
        on_delete=models.CASCADE,
        related_name='activity_logs',
        null=True,
        blank=True
    )
    
    bank_account = models.ForeignKey(
        'finance.BankAccount',
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    action_date = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    
    # Details
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    # Related objects
    bank_transaction = models.ForeignKey(
        'finance.BankTransaction',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    adjustment = models.ForeignKey(
        ReconciliationAdjustment,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    rule_applied = models.ForeignKey(
        ReconciliationRule,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    
    # Performance metrics
    processing_time = models.DurationField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'finance_reconciliation_logs'
        ordering = ['-action_date']
        indexes = [
            models.Index(fields=['tenant', 'bank_account', 'action_date']),
            models.Index(fields=['tenant', 'reconciliation', 'action_type']),
        ]
        
    def __str__(self):
        return f"{self.action_type} - {self.action_date}"
    
    @classmethod
    def log_action(cls, tenant, bank_account, action_type, description, **kwargs):
        """Helper method to create log entries"""
        return cls.objects.create(
            tenant=tenant,
            bank_account=bank_account,
            action_type=action_type,
            description=description,
            **kwargs
        )


class BankFeedConnection(TenantBaseModel):
    """Bank feed connection configurations"""
    
    PROVIDER_CHOICES = [
        ('PLAID', 'Plaid'),
        ('YODLEE', 'Yodlee'),
        ('OPEN_BANKING', 'Open Banking'),
        ('SALTEDGE', 'Salt Edge'),
        ('FINICITY', 'Finicity'),
        ('CUSTOM', 'Custom API'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ERROR', 'Error'),
        ('PENDING_SETUP', 'Pending Setup'),
        ('RECONNECT_REQUIRED', 'Reconnect Required'),
    ]
    
    bank_account = models.OneToOneField(
        'finance.BankAccount',
        on_delete=models.CASCADE,
        related_name='feed_connection'
    )
    
    # Provider Information
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_account_id = models.CharField(max_length=200)
    provider_item_id = models.CharField(max_length=200, blank=True)
    
    # Connection Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_SETUP')
    last_sync_date = models.DateTimeField(null=True, blank=True)
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    next_sync_date = models.DateTimeField(null=True, blank=True)
    
    # Sync Configuration
    sync_frequency_hours = models.IntegerField(default=24)
    auto_sync_enabled = models.BooleanField(default=True)
    include_pending_transactions = models.BooleanField(default=False)
    
    # Error Handling
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Authentication
    access_token = models.TextField(blank=True)  # Encrypted
    refresh_token = models.TextField(blank=True)  # Encrypted
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Sync Statistics
    total_syncs = models.IntegerField(default=0)
    successful_syncs = models.IntegerField(default=0)
    failed_syncs = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'finance_bank_feed_connections'
        
    def __str__(self):
        return f"{self.bank_account} - {self.provider}"
    
    def sync_transactions(self):
        """Sync transactions from bank feed"""
        from ..services.bank_feeds import BankFeedService
        
        service = BankFeedService(self.tenant)
        return service.sync_account_transactions(self)
    
    def test_connection(self):
        """Test bank feed connection"""
        from ..services.bank_feeds import BankFeedService
        
        service = BankFeedService(self.tenant)
        return service.test_connection(self)
    
    @property
    def sync_success_rate(self):
        """Calculate sync success rate"""
        if self.total_syncs > 0:
            return (self.successful_syncs / self.total_syncs) * 100
        return Decimal('0.00')
    
    @property
    def needs_reconnection(self):
        """Check if connection needs to be reestablished"""
        return self.status == 'RECONNECT_REQUIRED' or self.error_count >= self.max_retries