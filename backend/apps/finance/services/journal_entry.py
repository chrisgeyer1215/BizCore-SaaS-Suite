"""
Finance Services - Journal Entry Service
Advanced journal entry management with multi-currency and automation support
"""

from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any

from apps.core.utils import generate_code
from ..models import (
    JournalEntry, JournalEntryLine, Account, Currency, ExchangeRate,
    Invoice, InvoiceItem, Bill, BillItem, Payment, PaymentApplication,
    TaxCode, FinanceSettings, InventoryCostLayer, Project, Department, Location
)


logger = logging.getLogger(__name__)


class JournalEntryService:
    """Enhanced journal entry service for automated and manual accounting entries"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
        self.base_currency = self._get_base_currency()
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
            # Create default settings
            return FinanceSettings.objects.create(
                tenant=self.tenant,
                company_name=f"{self.tenant.name} Inc.",
                base_currency='USD'
            )
    
    def _get_base_currency(self):
        """Get base currency for tenant"""
        try:
            return Currency.objects.get(
                tenant=self.tenant,
                code=self.settings.base_currency
            )
        except Currency.DoesNotExist:
            # Create default base currency
            return Currency.objects.create(
                tenant=self.tenant,
                code=self.settings.base_currency,
                name='US Dollar',
                symbol='$',
                is_base_currency=True
            )
    
    def _get_exchange_rate(self, from_currency: Currency, to_currency: Currency, 
                          rate_date: date = None) -> Decimal:
        """Get exchange rate between currencies"""
        if from_currency.id == to_currency.id:
            return Decimal('1.000000')
        
        if not rate_date:
            rate_date = date.today()
        
        return ExchangeRate.get_rate(
            self.tenant, from_currency, to_currency, rate_date
        )
    
    # ============================================================================
    # MANUAL JOURNAL ENTRIES
    # ============================================================================
    
    @transaction.atomic
    def create_manual_journal_entry(self, entry_data: Dict, user) -> JournalEntry:
        """
        Create a manual journal entry
        
        Args:
            entry_data: Dictionary containing entry details and line items
            user: User creating the entry
        
        Returns:
            Created JournalEntry instance
        """
        try:
            # Validate entry data
            self._validate_journal_entry_data(entry_data)
            
            # Get currency and exchange rate
            currency = Currency.objects.get(
                tenant=self.tenant,
                code=entry_data.get('currency_code', self.base_currency.code)
            )
            exchange_rate = self._get_exchange_rate(
                currency, self.base_currency, 
                entry_data.get('entry_date', date.today())
            )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=entry_data['entry_date'],
                description=entry_data['description'],
                notes=entry_data.get('notes', ''),
                reference_number=entry_data.get('reference_number', ''),
                entry_type='MANUAL',
                status='DRAFT',
                currency=currency,
                exchange_rate=exchange_rate,
                created_by=user
            )
            
            # Create journal entry lines
            self._create_journal_entry_lines(journal_entry, entry_data['lines'])
            
            # Calculate totals
            journal_entry.calculate_totals()
            
            # Auto-post if enabled in settings
            if self.settings.auto_create_journal_entries and entry_data.get('auto_post', False):
                journal_entry.post_entry(user)
            
            logger.info(f"Manual journal entry {journal_entry.entry_number} created by {user}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating manual journal entry: {str(e)}")
            raise ValidationError(f"Failed to create journal entry: {str(e)}")
    
    def _validate_journal_entry_data(self, entry_data: Dict):
        """Validate journal entry data"""
        required_fields = ['entry_date', 'description', 'lines']
        for field in required_fields:
            if field not in entry_data:
                raise ValidationError(f"Missing required field: {field}")
        
        if not entry_data['lines']:
            raise ValidationError("Journal entry must have at least one line")
        
        # Validate that debits equal credits
        total_debits = sum(
            Decimal(str(line.get('debit_amount', '0.00'))) 
            for line in entry_data['lines']
        )
        total_credits = sum(
            Decimal(str(line.get('credit_amount', '0.00'))) 
            for line in entry_data['lines']
        )
        
        if abs(total_debits - total_credits) > Decimal('0.01'):
            raise ValidationError(
                f"Journal entry is not balanced. Debits: {total_debits}, Credits: {total_credits}"
            )
    
    def _create_journal_entry_lines(self, journal_entry: JournalEntry, lines_data: List[Dict]):
        """Create journal entry lines"""
        for idx, line_data in enumerate(lines_data, 1):
            account = Account.objects.get(
                tenant=self.tenant,
                id=line_data['account_id']
            )
            
            debit_amount = Decimal(str(line_data.get('debit_amount', '0.00')))
            credit_amount = Decimal(str(line_data.get('credit_amount', '0.00')))
            
            # Calculate base currency amounts
            base_debit = debit_amount * journal_entry.exchange_rate
            base_credit = credit_amount * journal_entry.exchange_rate
            
            # Get related entities
            customer_id = line_data.get('customer_id')
            vendor_id = line_data.get('vendor_id')
            product_id = line_data.get('product_id')
            project_id = line_data.get('project_id')
            department_id = line_data.get('department_id')
            location_id = line_data.get('location_id')
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=idx,
                account=account,
                description=line_data.get('description', journal_entry.description),
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                base_currency_debit_amount=base_debit,
                base_currency_credit_amount=base_credit,
                customer_id=customer_id,
                vendor_id=vendor_id,
                product_id=product_id,
                project_id=project_id,
                department_id=department_id,
                location_id=location_id,
                quantity=line_data.get('quantity'),
                unit_cost=line_data.get('unit_cost')
            )
    
    # ============================================================================
    # AUTOMATED JOURNAL ENTRIES - INVOICES
    # ============================================================================
    
    @transaction.atomic
    def create_invoice_journal_entry(self, invoice) -> JournalEntry:
        """
        Create journal entry for an approved invoice
        
        Args:
            invoice: Invoice instance
        
        Returns:
            Created JournalEntry instance
        """
        try:
            if invoice.journal_entry:
                logger.warning(f"Invoice {invoice.invoice_number} already has a journal entry")
                return invoice.journal_entry
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=invoice.invoice_date,
                description=f"Sales Invoice {invoice.invoice_number} - {invoice.customer.name}",
                entry_type='INVOICE',
                status='DRAFT',
                currency=invoice.currency,
                exchange_rate=invoice.exchange_rate,
                source_document_type='INVOICE',
                source_document_id=invoice.id,
                source_document_number=invoice.invoice_number,
                created_by=invoice.approved_by or invoice.created_by
            )
            
            # Create journal entry lines
            self._create_invoice_journal_lines(journal_entry, invoice)
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(invoice.approved_by or invoice.created_by)
            
            # Update invoice with journal entry reference
            invoice.journal_entry = journal_entry
            invoice.save(update_fields=['journal_entry'])
            
            logger.info(f"Invoice journal entry {journal_entry.entry_number} created for {invoice.invoice_number}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating invoice journal entry: {str(e)}")
            raise ValidationError(f"Failed to create invoice journal entry: {str(e)}")
    
    def _create_invoice_journal_lines(self, journal_entry: JournalEntry, invoice):
        """Create journal entry lines for invoice"""
        line_number = 1
        
        # Get accounts receivable account
        ar_account = self._get_accounts_receivable_account()
        
        # Debit: Accounts Receivable (total amount)
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=ar_account,
            description=f"A/R - {invoice.customer.name}",
            debit_amount=invoice.total_amount,
            credit_amount=Decimal('0.00'),
            base_currency_debit_amount=invoice.base_currency_total,
            base_currency_credit_amount=Decimal('0.00'),
            customer=invoice.customer
        )
        line_number += 1
        
        # Credit: Revenue accounts (by line item)
        for item in invoice.invoice_items.all():
            if item.line_total > Decimal('0.00'):
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=item.revenue_account,
                    description=f"Sales - {item.description[:50]}",
                    debit_amount=Decimal('0.00'),
                    credit_amount=item.line_total,
                    base_currency_debit_amount=Decimal('0.00'),
                    base_currency_credit_amount=item.line_total * invoice.exchange_rate,
                    customer=invoice.customer,
                    product=item.product,
                    project=item.project,
                    department=item.department,
                    location=item.location,
                    quantity=item.quantity,
                    unit_cost=item.unit_price
                )
                line_number += 1
        
        # Credit: Tax accounts (if applicable)
        if invoice.tax_amount > Decimal('0.00'):
            tax_account = self._get_sales_tax_account()
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=tax_account,
                description="Sales Tax Collected",
                debit_amount=Decimal('0.00'),
                credit_amount=invoice.tax_amount,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=invoice.tax_amount * invoice.exchange_rate,
                customer=invoice.customer
            )
    
    # ============================================================================
    # AUTOMATED JOURNAL ENTRIES - BILLS
    # ============================================================================
    
    @transaction.atomic
    def create_bill_journal_entry(self, bill) -> JournalEntry:
        """
        Create journal entry for an approved bill
        
        Args:
            bill: Bill instance
        
        Returns:
            Created JournalEntry instance
        """
        try:
            if bill.journal_entry:
                logger.warning(f"Bill {bill.bill_number} already has a journal entry")
                return bill.journal_entry
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=bill.bill_date,
                description=f"Purchase Bill {bill.bill_number} - {bill.vendor.company_name}",
                entry_type='BILL',
                status='DRAFT',
                currency=bill.currency,
                exchange_rate=bill.exchange_rate,
                source_document_type='BILL',
                source_document_id=bill.id,
                source_document_number=bill.bill_number,
                created_by=bill.approved_by or bill.created_by
            )
            
            # Create journal entry lines
            self._create_bill_journal_lines(journal_entry, bill)
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(bill.approved_by or bill.created_by)
            
            # Update bill with journal entry reference
            bill.journal_entry = journal_entry
            bill.save(update_fields=['journal_entry'])
            
            logger.info(f"Bill journal entry {journal_entry.entry_number} created for {bill.bill_number}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating bill journal entry: {str(e)}")
            raise ValidationError(f"Failed to create bill journal entry: {str(e)}")
    
    def _create_bill_journal_lines(self, journal_entry: JournalEntry, bill):
        """Create journal entry lines for bill"""
        line_number = 1
        
        # Get accounts payable account
        ap_account = self._get_accounts_payable_account()
        
        # Debit: Expense/Asset accounts (by line item)
        for item in bill.bill_items.all():
            if item.line_total > Decimal('0.00'):
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=item.expense_account,
                    description=f"Purchase - {item.description[:50]}",
                    debit_amount=item.line_total,
                    credit_amount=Decimal('0.00'),
                    base_currency_debit_amount=item.line_total * bill.exchange_rate,
                    base_currency_credit_amount=Decimal('0.00'),
                    vendor=bill.vendor,
                    product=item.product,
                    project=item.project,
                    department=item.department,
                    location=item.location,
                    quantity=item.quantity,
                    unit_cost=item.unit_cost
                )
                line_number += 1
        
        # Debit: Tax accounts (if applicable)
        if bill.tax_amount > Decimal('0.00'):
            tax_account = self._get_purchase_tax_account()
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=tax_account,
                description="Purchase Tax Paid",
                debit_amount=bill.tax_amount,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=bill.tax_amount * bill.exchange_rate,
                base_currency_credit_amount=Decimal('0.00'),
                vendor=bill.vendor
            )
            line_number += 1
        
        # Credit: Accounts Payable (total amount)
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=ap_account,
            description=f"A/P - {bill.vendor.company_name}",
            debit_amount=Decimal('0.00'),
            credit_amount=bill.total_amount,
            base_currency_debit_amount=Decimal('0.00'),
            base_currency_credit_amount=bill.base_currency_total,
            vendor=bill.vendor
        )
    
    # ============================================================================
    # AUTOMATED JOURNAL ENTRIES - PAYMENTS
    # ============================================================================
    
    @transaction.atomic
    def create_payment_journal_entry(self, payment) -> JournalEntry:
        """
        Create journal entry for a payment
        
        Args:
            payment: Payment instance
        
        Returns:
            Created JournalEntry instance
        """
        try:
            if payment.journal_entry:
                logger.warning(f"Payment {payment.payment_number} already has a journal entry")
                return payment.journal_entry
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=payment.payment_date,
                description=self._get_payment_description(payment),
                entry_type='PAYMENT',
                status='DRAFT',
                currency=payment.currency,
                exchange_rate=payment.exchange_rate,
                source_document_type='PAYMENT',
                source_document_id=payment.id,
                source_document_number=payment.payment_number,
                created_by=payment.created_by
            )
            
            # Create journal entry lines based on payment type
            if payment.payment_type == 'RECEIVED':
                self._create_payment_received_lines(journal_entry, payment)
            elif payment.payment_type == 'MADE':
                self._create_payment_made_lines(journal_entry, payment)
            elif payment.payment_type == 'TRANSFER':
                self._create_payment_transfer_lines(journal_entry, payment)
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(payment.created_by)
            
            # Update payment with journal entry reference
            payment.journal_entry = journal_entry
            payment.save(update_fields=['journal_entry'])
            
            logger.info(f"Payment journal entry {journal_entry.entry_number} created for {payment.payment_number}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating payment journal entry: {str(e)}")
            raise ValidationError(f"Failed to create payment journal entry: {str(e)}")
    
    def _get_payment_description(self, payment) -> str:
        """Generate payment description"""
        if payment.payment_type == 'RECEIVED':
            party = payment.customer.name if payment.customer else 'Customer'
            return f"Payment Received from {party}"
        elif payment.payment_type == 'MADE':
            party = payment.vendor.company_name if payment.vendor else 'Vendor'
            return f"Payment Made to {party}"
        elif payment.payment_type == 'TRANSFER':
            return f"Bank Transfer - {payment.description}"
        else:
            return f"Payment - {payment.description}"
    
    def _create_payment_received_lines(self, journal_entry: JournalEntry, payment):
        """Create journal lines for payment received"""
        line_number = 1
        
        # Debit: Bank Account
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=payment.bank_account,
            description=f"Payment received - {payment.payment_method}",
            debit_amount=payment.amount,
            credit_amount=Decimal('0.00'),
            base_currency_debit_amount=payment.base_currency_amount,
            base_currency_credit_amount=Decimal('0.00'),
            customer=payment.customer
        )
        line_number += 1
        
        # Handle processing fees
        if payment.processing_fee > Decimal('0.00') and payment.processing_fee_account:
            # Debit: Processing Fee Expense
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=payment.processing_fee_account,
                description="Payment processing fee",
                debit_amount=payment.processing_fee,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=payment.processing_fee * payment.exchange_rate,
                base_currency_credit_amount=Decimal('0.00'),
                customer=payment.customer
            )
            line_number += 1
        
        # Credit: Accounts Receivable or Undeposited Funds
        if payment.applications.exists():
            # Applied to specific invoices - credit A/R
            ar_account = self._get_accounts_receivable_account()
            total_applied = payment.applications.aggregate(
                total=models.Sum('amount_applied')
            )['total'] or Decimal('0.00')
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=ar_account,
                description=f"A/R payment - {payment.customer.name}",
                debit_amount=Decimal('0.00'),
                credit_amount=total_applied + payment.processing_fee,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=(total_applied + payment.processing_fee) * payment.exchange_rate,
                customer=payment.customer
            )
        else:
            # Unapplied payment - credit Undeposited Funds
            undeposited_account = self._get_undeposited_funds_account()
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=undeposited_account,
                description=f"Unapplied payment - {payment.customer.name}",
                debit_amount=Decimal('0.00'),
                credit_amount=payment.amount + payment.processing_fee,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=(payment.amount + payment.processing_fee) * payment.exchange_rate,
                customer=payment.customer
            )
    
    def _create_payment_made_lines(self, journal_entry: JournalEntry, payment):
        """Create journal lines for payment made"""
        line_number = 1
        
        # Credit: Bank Account
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=payment.bank_account,
            description=f"Payment made - {payment.payment_method}",
            debit_amount=Decimal('0.00'),
            credit_amount=payment.amount,
            base_currency_debit_amount=Decimal('0.00'),
            base_currency_credit_amount=payment.base_currency_amount,
            vendor=payment.vendor
        )
        line_number += 1
        
        # Handle processing fees
        if payment.processing_fee > Decimal('0.00') and payment.processing_fee_account:
            # Debit: Processing Fee Expense
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=payment.processing_fee_account,
                description="Payment processing fee",
                debit_amount=payment.processing_fee,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=payment.processing_fee * payment.exchange_rate,
                base_currency_credit_amount=Decimal('0.00'),
                vendor=payment.vendor
            )
            line_number += 1
        
        # Debit: Accounts Payable
        if payment.applications.exists():
            ap_account = self._get_accounts_payable_account()
            total_applied = payment.applications.aggregate(
                total=models.Sum('amount_applied')
            )['total'] or Decimal('0.00')
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=ap_account,
                description=f"A/P payment - {payment.vendor.company_name}",
                debit_amount=total_applied,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=total_applied * payment.exchange_rate,
                base_currency_credit_amount=Decimal('0.00'),
                vendor=payment.vendor
            )
    
    def _create_payment_transfer_lines(self, journal_entry: JournalEntry, payment):
        """Create journal lines for bank transfer"""
        # This would require additional fields to specify from/to accounts
        # For now, we'll create a simple entry
        pass
    
    # ============================================================================
    # PERIOD-END ENTRIES
    # ============================================================================
    
    @transaction.atomic
    def create_year_end_closing_entries(self, fiscal_year, user) -> List[JournalEntry]:
        """
        Create year-end closing entries
        
        Args:
            fiscal_year: FiscalYear instance
            user: User creating entries
        
        Returns:
            List of created JournalEntry instances
        """
        try:
            closing_entries = []
            
            # Get income summary account
            income_summary = self._get_income_summary_account()
            retained_earnings = self._get_retained_earnings_account()
            
            # Close revenue accounts to Income Summary
            revenue_entry = self._close_revenue_accounts(fiscal_year, income_summary, user)
            if revenue_entry:
                closing_entries.append(revenue_entry)
            
            # Close expense accounts to Income Summary
            expense_entry = self._close_expense_accounts(fiscal_year, income_summary, user)
            if expense_entry:
                closing_entries.append(expense_entry)
            
            # Close Income Summary to Retained Earnings
            summary_entry = self._close_income_summary(fiscal_year, income_summary, retained_earnings, user)
            if summary_entry:
                closing_entries.append(summary_entry)
            
            logger.info(f"Created {len(closing_entries)} year-end closing entries for FY {fiscal_year.year}")
            return closing_entries
            
        except Exception as e:
            logger.error(f"Error creating year-end closing entries: {str(e)}")
            raise ValidationError(f"Failed to create closing entries: {str(e)}")
    
    def _close_revenue_accounts(self, fiscal_year, income_summary, user):
        """Close revenue accounts to Income Summary"""
        # Implementation for closing revenue accounts
        pass
    
    def _close_expense_accounts(self, fiscal_year, income_summary, user):
        """Close expense accounts to Income Summary"""
        # Implementation for closing expense accounts
        pass
    
    def _close_income_summary(self, fiscal_year, income_summary, retained_earnings, user):
        """Close Income Summary to Retained Earnings"""
        # Implementation for closing income summary
        pass
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_accounts_receivable_account(self) -> Account:
        """Get the Accounts Receivable account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='Accounts Receivable'
            )
        except Account.DoesNotExist:
            # Create default A/R account
            return Account.objects.create(
                tenant=self.tenant,
                code='1200',
                name='Accounts Receivable',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
    
    def _get_accounts_payable_account(self) -> Account:
        """Get the Accounts Payable account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_LIABILITY',
                name__icontains='Accounts Payable'
            )
        except Account.DoesNotExist:
            # Create default A/P account
            return Account.objects.create(
                tenant=self.tenant,
                code='2000',
                name='Accounts Payable',
                account_type='CURRENT_LIABILITY',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
    
    def _get_sales_tax_account(self) -> Account:
        """Get the Sales Tax Payable account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_LIABILITY',
                name__icontains='Sales Tax'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='2100',
                name='Sales Tax Payable',
                account_type='CURRENT_LIABILITY',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
    
    def _get_purchase_tax_account(self) -> Account:
        """Get the Purchase Tax account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='Purchase Tax'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='1250',
                name='Purchase Tax Recoverable',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
    
    def _get_undeposited_funds_account(self) -> Account:
        """Get the Undeposited Funds account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Undeposited Funds'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='1050',
                name='Undeposited Funds',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
    
    def _get_income_summary_account(self) -> Account:
        """Get the Income Summary account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Income Summary'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='3900',
                name='Income Summary',
                account_type='EQUITY',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
    
    def _get_retained_earnings_account(self) -> Account:
        """Get the Retained Earnings account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='RETAINED_EARNINGS'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='3800',
                name='Retained Earnings',
                account_type='RETAINED_EARNINGS',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
    
    # ============================================================================
    # JOURNAL ENTRY MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def reverse_journal_entry(self, journal_entry_id: int, user, reason: str) -> JournalEntry:
        """
        Reverse a posted journal entry
        
        Args:
            journal_entry_id: ID of journal entry to reverse
            user: User performing the reversal
            reason: Reason for reversal
        
        Returns:
            Reversal JournalEntry instance
        """
        try:
            journal_entry = JournalEntry.objects.get(
                id=journal_entry_id,
                tenant=self.tenant
            )
            
            return journal_entry.reverse_entry(user, reason)
            
        except JournalEntry.DoesNotExist:
            raise ValidationError(f"Journal entry {journal_entry_id} not found")
        except Exception as e:
            logger.error(f"Error reversing journal entry: {str(e)}")
            raise ValidationError(f"Failed to reverse journal entry: {str(e)}")
    
    def get_journal_entry_summary(self, journal_entry_id: int) -> Dict:
        """
        Get journal entry summary with line details
        
        Args:
            journal_entry_id: Journal entry ID
        
        Returns:
            Dictionary with entry summary
        """
        try:
            journal_entry = JournalEntry.objects.select_related(
                'currency', 'created_by', 'posted_by'
            ).prefetch_related(
                'journal_lines__account', 'journal_lines__customer', 
                'journal_lines__vendor', 'journal_lines__product'
            ).get(id=journal_entry_id, tenant=self.tenant)
            
            lines = []
            for line in journal_entry.journal_lines.all():
                lines.append({
                    'line_number': line.line_number,
                    'account_code': line.account.code,
                    'account_name': line.account.name,
                    'description': line.description,
                    'debit_amount': line.debit_amount,
                    'credit_amount': line.credit_amount,
                    'base_debit_amount': line.base_currency_debit_amount,
                    'base_credit_amount': line.base_currency_credit_amount,
                    'customer_name': line.customer.name if line.customer else None,
                    'vendor_name': line.vendor.company_name if line.vendor else None,
                    'product_name': line.product.name if line.product else None,
                    'project_name': line.project.name if line.project else None,
                    'department_name': line.department.name if line.department else None,
                    'location_name': line.location.name if line.location else None
                })
            
            return {
                'entry_number': journal_entry.entry_number,
                'entry_date': journal_entry.entry_date,
                'description': journal_entry.description,
                'entry_type': journal_entry.entry_type,
                'status': journal_entry.status,
                'currency_code': journal_entry.currency.code,
                'exchange_rate': journal_entry.exchange_rate,
                'total_debit': journal_entry.total_debit,
                'total_credit': journal_entry.total_credit,
                'base_total_debit': journal_entry.base_currency_total_debit,
                'base_total_credit': journal_entry.base_currency_total_credit,
                'created_by': journal_entry.created_by.get_full_name(),
                'created_at': journal_entry.created_at,
                'posted_by': journal_entry.posted_by.get_full_name() if journal_entry.posted_by else None,
                'posted_date': journal_entry.posted_date,
                'source_document': {
                    'type': journal_entry.source_document_type,
                    'number': journal_entry.source_document_number
                } if journal_entry.source_document_type else None,
                'lines': lines,
                'is_balanced': abs(journal_entry.total_debit - journal_entry.total_credit) <= Decimal('0.01'),
                'can_be_reversed': journal_entry.status == 'POSTED' and not journal_entry.reversed_entry
            }
            
        except JournalEntry.DoesNotExist:
            raise ValidationError(f"Journal entry {journal_entry_id} not found")
    
    def validate_journal_entry_balance(self, lines_data: List[Dict]) -> Dict:
        """
        Validate that journal entry lines are balanced
        
        Args:
            lines_data: List of line data dictionaries
        
        Returns:
            Validation result dictionary
        """
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for line in lines_data:
            debit = Decimal(str(line.get('debit_amount', '0.00')))
            credit = Decimal(str(line.get('credit_amount', '0.00')))
            
            total_debits += debit
            total_credits += credit
            
            # Validate individual line
            if debit > 0 and credit > 0:
                return {
                    'is_valid': False,
                    'error': f"Line {line.get('line_number', '?')} cannot have both debit and credit amounts"
                }
            
            if debit == 0 and credit == 0:
                return {
                    'is_valid': False,
                    'error': f"Line {line.get('line_number', '?')} must have either debit or credit amount"
                }
        
        difference = abs(total_debits - total_credits)
        is_balanced = difference <= Decimal('0.01')
        
        return {
            'is_valid': is_balanced,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'difference': difference,
            'error': f"Entry is not balanced. Difference: {difference}" if not is_balanced else None
        }
    
    # ============================================================================
    # RECURRING JOURNAL ENTRIES
    # ============================================================================
    
    @transaction.atomic
    def create_recurring_journal_entry(self, template_data: Dict, user) -> JournalEntry:
        """
        Create journal entry from recurring template
        
        Args:
            template_data: Template data with entry details
            user: User creating the entry
        
        Returns:
            Created JournalEntry instance
        """
        try:
            # Adjust dates for current period
            current_date = date.today()
            entry_data = template_data.copy()
            entry_data['entry_date'] = current_date
            entry_data['description'] = f"{template_data['description']} - {current_date.strftime('%B %Y')}"
            
            # Create the journal entry
            return self.create_manual_journal_entry(entry_data, user)
            
        except Exception as e:
            logger.error(f"Error creating recurring journal entry: {str(e)}")
            raise ValidationError(f"Failed to create recurring entry: {str(e)}")
    
    # ============================================================================
    # ADJUSTING ENTRIES
    # ============================================================================
    
    @transaction.atomic
    def create_adjusting_entry(self, adjustment_data: Dict, user) -> JournalEntry:
        """
        Create adjusting journal entry
        
        Args:
            adjustment_data: Adjustment data
            user: User creating the entry
        
        Returns:
            Created JournalEntry instance
        """
        try:
            # Set entry type as adjustment
            adjustment_data['entry_type'] = 'ADJUSTMENT'
            
            # Create the journal entry
            journal_entry = self.create_manual_journal_entry(adjustment_data, user)
            
            logger.info(f"Adjusting entry {journal_entry.entry_number} created")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating adjusting entry: {str(e)}")
            raise ValidationError(f"Failed to create adjusting entry: {str(e)}")
    
    # ============================================================================
    # INVENTORY INTEGRATION
    # ============================================================================
    
    @transaction.atomic
    def create_inventory_adjustment_entry(self, adjustment_data: Dict, user) -> JournalEntry:
        """
        Create journal entry for inventory adjustments
        
        Args:
            adjustment_data: Inventory adjustment data
            user: User creating the entry
        
        Returns:
            Created JournalEntry instance
        """
        try:
            # Get inventory account
            inventory_account = self._get_inventory_account()
            inventory_adjustment_account = self._get_inventory_adjustment_account()
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=adjustment_data['adjustment_date'],
                description=f"Inventory Adjustment - {adjustment_data.get('reason', 'Manual Adjustment')}",
                entry_type='INVENTORY',
                status='DRAFT',
                currency=self.base_currency,
                exchange_rate=Decimal('1.000000'),
                created_by=user
            )
            
            line_number = 1
            total_adjustment = Decimal('0.00')
            
            # Create lines for each product adjustment
            for item in adjustment_data['items']:
                adjustment_amount = Decimal(str(item['adjustment_value']))
                total_adjustment += adjustment_amount
                
                if adjustment_amount > 0:
                    # Increase inventory
                    debit_amount = adjustment_amount
                    credit_amount = Decimal('0.00')
                else:
                    # Decrease inventory
                    debit_amount = Decimal('0.00')
                    credit_amount = abs(adjustment_amount)
                
                # Inventory account line
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=inventory_account,
                    description=f"Inventory adjustment - {item['product_name']}",
                    debit_amount=debit_amount,
                    credit_amount=credit_amount,
                    base_currency_debit_amount=debit_amount,
                    base_currency_credit_amount=credit_amount,
                    product_id=item['product_id'],
                    quantity=item.get('quantity_adjustment'),
                    unit_cost=item.get('unit_cost')
                )
                line_number += 1
            
            # Offsetting entry to inventory adjustment account
            if total_adjustment > 0:
                debit_amount = Decimal('0.00')
                credit_amount = total_adjustment
            else:
                debit_amount = abs(total_adjustment)
                credit_amount = Decimal('0.00')
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=inventory_adjustment_account,
                description="Inventory adjustment offset",
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                base_currency_debit_amount=debit_amount,
                base_currency_credit_amount=credit_amount
            )
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(user)
            
            logger.info(f"Inventory adjustment entry {journal_entry.entry_number} created")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating inventory adjustment entry: {str(e)}")
            raise ValidationError(f"Failed to create inventory adjustment entry: {str(e)}")
    
    def _get_inventory_account(self) -> Account:
        """Get the Inventory account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='Inventory'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='1300',
                name='Inventory',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency,
                track_inventory=True
            )
    
    def _get_inventory_adjustment_account(self) -> Account:
        """Get the Inventory Adjustment account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Inventory Adjustment'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='5200',
                name='Inventory Adjustments',
                account_type='EXPENSE',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
    
    # ============================================================================
    # DEPRECIATION ENTRIES
    # ============================================================================
    
    @transaction.atomic
    def create_depreciation_entry(self, depreciation_data: Dict, user) -> JournalEntry:
        """
        Create depreciation journal entry
        
        Args:
            depreciation_data: Depreciation calculation data
            user: User creating the entry
        
        Returns:
            Created JournalEntry instance
        """
        try:
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=depreciation_data['depreciation_date'],
                description=f"Depreciation - {depreciation_data['period']}",
                entry_type='DEPRECIATION',
                status='DRAFT',
                currency=self.base_currency,
                exchange_rate=Decimal('1.000000'),
                created_by=user
            )
            
            line_number = 1
            total_depreciation = Decimal('0.00')
            
            # Get depreciation expense account
            depreciation_expense_account = self._get_depreciation_expense_account()
            
            # Create lines for each asset
            for asset in depreciation_data['assets']:
                depreciation_amount = Decimal(str(asset['depreciation_amount']))
                total_depreciation += depreciation_amount
                
                # Get or create accumulated depreciation account for this asset
                accumulated_depreciation_account = self._get_accumulated_depreciation_account(
                    asset['asset_account_id']
                )
                
                # Debit: Depreciation Expense
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=depreciation_expense_account,
                    description=f"Depreciation - {asset['asset_name']}",
                    debit_amount=depreciation_amount,
                    credit_amount=Decimal('0.00'),
                    base_currency_debit_amount=depreciation_amount,
                    base_currency_credit_amount=Decimal('0.00')
                )
                line_number += 1
                
                # Credit: Accumulated Depreciation
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=accumulated_depreciation_account,
                    description=f"Accumulated Depreciation - {asset['asset_name']}",
                    debit_amount=Decimal('0.00'),
                    credit_amount=depreciation_amount,
                    base_currency_debit_amount=Decimal('0.00'),
                    base_currency_credit_amount=depreciation_amount
                )
                line_number += 1
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(user)
            
            logger.info(f"Depreciation entry {journal_entry.entry_number} created for {total_depreciation}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating depreciation entry: {str(e)}")
            raise ValidationError(f"Failed to create depreciation entry: {str(e)}")
    
    def _get_depreciation_expense_account(self) -> Account:
        """Get the Depreciation Expense account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='EXPENSE',
                name__icontains='Depreciation'
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='6200',
                name='Depreciation Expense',
                account_type='EXPENSE',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
    
    def _get_accumulated_depreciation_account(self, asset_account_id: int) -> Account:
        """Get or create Accumulated Depreciation account for specific asset"""
        try:
            asset_account = Account.objects.get(id=asset_account_id, tenant=self.tenant)
            account_name = f"Accumulated Depreciation - {asset_account.name}"
            
            return Account.objects.get(
                tenant=self.tenant,
                name=account_name
            )
        except Account.DoesNotExist:
            asset_account = Account.objects.get(id=asset_account_id, tenant=self.tenant)
            return Account.objects.create(
                tenant=self.tenant,
                code=f"{asset_account.code}-AD",
                name=f"Accumulated Depreciation - {asset_account.name}",
                account_type='FIXED_ASSET',
                normal_balance='CREDIT',
                currency=self.base_currency,
                parent_account=asset_account
            )
    
    # ============================================================================
    # REPORTING HELPERS
    # ============================================================================
    
    def get_journal_entries_for_period(self, start_date: date, end_date: date, 
                                     entry_type: str = None, status: str = 'POSTED') -> models.QuerySet:
        """
        Get journal entries for a specific period
        
        Args:
            start_date: Period start date
            end_date: Period end date
            entry_type: Optional entry type filter
            status: Entry status filter (default: POSTED)
        
        Returns:
            QuerySet of JournalEntry instances
        """
        queryset = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_date__gte=start_date,
            entry_date__lte=end_date,
            status=status
        ).select_related('currency', 'created_by', 'posted_by').prefetch_related(
            'journal_lines__account'
        )
        
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        return queryset.order_by('entry_date', 'entry_number')
    
    def get_account_activity(self, account_id: int, start_date: date, 
                           end_date: date) -> Dict:
        """
        Get account activity for a period
        
        Args:
            account_id: Account ID
            start_date: Period start date
            end_date: Period end date
        
        Returns:
            Dictionary with account activity details
        """
        try:
            account = Account.objects.get(id=account_id, tenant=self.tenant)
            
            # Get opening balance
            opening_balance = self.get_account_balance(account_id, start_date - timedelta(days=1))
            
            # Get journal lines for period
            journal_lines = JournalEntryLine.objects.filter(
                tenant=self.tenant,
                account=account,
                journal_entry__status='POSTED',
                journal_entry__entry_date__gte=start_date,
                journal_entry__entry_date__lte=end_date
            ).select_related('journal_entry').order_by('journal_entry__entry_date', 'journal_entry__entry_number')
            
            # Calculate period activity
            period_debits = journal_lines.aggregate(
                total=models.Sum('base_currency_debit_amount')
            )['total'] or Decimal('0.00')
            
            period_credits = journal_lines.aggregate(
                total=models.Sum('base_currency_credit_amount')
            )['total'] or Decimal('0.00')
            
            # Calculate closing balance
            closing_balance = self.get_account_balance(account_id, end_date)
            
            # Format line details
            lines = []
            for line in journal_lines:
                lines.append({
                    'date': line.journal_entry.entry_date,
                    'entry_number': line.journal_entry.entry_number,
                    'description': line.description,
                    'debit_amount': line.base_currency_debit_amount,
                    'credit_amount': line.base_currency_credit_amount,
                    'source_document': line.journal_entry.source_document_number
                })
            
            return {
                'account': {
                    'code': account.code,
                    'name': account.name,
                    'type': account.account_type,
                    'normal_balance': account.normal_balance
                },
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'balances': {
                    'opening_balance': opening_balance,
                    'period_debits': period_debits,
                    'period_credits': period_credits,
                    'closing_balance': closing_balance,
                    'net_change': period_debits - period_credits if account.normal_balance == 'DEBIT' else period_credits - period_debits
                },
                'lines': lines
            }
            
        except Account.DoesNotExist:
            raise ValidationError(f"Account {account_id} not found")
    
    # ============================================================================
    # VALIDATION AND UTILITIES
    # ============================================================================
    
    def validate_account_access(self, account_id: int) -> bool:
        """Validate that account exists and belongs to tenant"""
        return Account.objects.filter(
            id=account_id, 
            tenant=self.tenant, 
            is_active=True
        ).exists()
    
    def get_next_entry_number(self) -> str:
        """Get the next journal entry number"""
        return generate_code('JE', self.tenant.id)
    
    def validate_period_lock(self, entry_date: date) -> bool:
        """Check if period is locked for new entries"""
        # Implementation would check if fiscal period is locked
        # For now, return True (not locked)
        return True