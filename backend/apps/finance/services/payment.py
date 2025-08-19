"""
Finance Services - Payment Processing Service
Advanced payment management with multi-currency and payment gateway integration
"""

from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Q, Case, When, DecimalField, Max, Min
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any

from apps.core.utils import generate_code
from ..models import (
    Payment, PaymentApplication, Invoice, Bill, Customer, Vendor, Account,
    JournalEntry, JournalEntryLine, Currency, ExchangeRate, FinanceSettings,
    CustomerFinancialProfile
)


logger = logging.getLogger(__name__)


class PaymentService:
    """Advanced payment processing service with multi-currency and gateway integration"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
        self.base_currency = self._get_base_currency()
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
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
                code=self.settings.base_currency,
                is_active=True
            )
        except Currency.DoesNotExist:
            return Currency.objects.create(
                tenant=self.tenant,
                code=self.settings.base_currency,
                name='US Dollar',
                symbol='$',
                is_base_currency=True
            )
    
    # ============================================================================
    # PAYMENT CREATION & PROCESSING
    # ============================================================================
    
    @transaction.atomic
    def create_customer_payment(self, payment_data: Dict, user) -> Payment:
        """
        Create and process a payment received from customer
        
        Args:
            payment_data: Payment details dictionary
                - customer_id: Customer ID
                - amount: Payment amount
                - currency_code: Payment currency
                - payment_method: Payment method
                - payment_date: Payment date
                - bank_account_id: Receiving bank account
                - reference_number: Payment reference
                - description: Payment description
                - invoice_applications: List of invoice applications (optional)
                - processing_fee: Processing fee amount (optional)
        
        Returns:
            Created Payment instance
        """
        try:
            # Validate required fields
            required_fields = ['customer_id', 'amount', 'payment_method', 'bank_account_id']
            for field in required_fields:
                if field not in payment_data or payment_data[field] is None:
                    raise ValidationError(f"Missing required field: {field}")
            
            # Get related objects
            customer = Customer.objects.get(id=payment_data['customer_id'], tenant=self.tenant)
            bank_account = Account.objects.get(
                id=payment_data['bank_account_id'], 
                tenant=self.tenant,
                is_bank_account=True
            )
            
            # Get currency and exchange rate
            currency_code = payment_data.get('currency_code', self.base_currency.code)
            currency = Currency.objects.get(tenant=self.tenant, code=currency_code)
            exchange_rate = self._get_exchange_rate(
                currency, 
                self.base_currency, 
                payment_data.get('payment_date', date.today())
            )
            
            # Create payment record
            payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='RECEIVED',
                payment_method=payment_data['payment_method'],
                payment_date=payment_data.get('payment_date', date.today()),
                customer=customer,
                amount=Decimal(str(payment_data['amount'])),
                currency=currency,
                exchange_rate=exchange_rate,
                base_currency_amount=Decimal(str(payment_data['amount'])) * exchange_rate,
                bank_account=bank_account,
                reference_number=payment_data.get('reference_number', ''),
                description=payment_data.get('description', f'Payment from {customer.name}'),
                processing_fee=Decimal(str(payment_data.get('processing_fee', '0.00'))),
                status='PENDING',
                external_transaction_id=payment_data.get('external_transaction_id', ''),
                card_last_four=payment_data.get('card_last_four', ''),
                card_type=payment_data.get('card_type', ''),
                processor_name=payment_data.get('processor_name', ''),
                processor_transaction_id=payment_data.get('processor_transaction_id', ''),
                created_by=user
            )
            
            # Apply to invoices if specified
            if 'invoice_applications' in payment_data and payment_data['invoice_applications']:
                self.apply_payment_to_invoices(
                    payment, 
                    payment_data['invoice_applications'], 
                    user
                )
            
            # Create journal entry
            journal_entry = self._create_payment_journal_entry(payment, user)
            payment.journal_entry = journal_entry
            
            # Mark as cleared for certain payment methods
            if payment_data['payment_method'] in ['CASH', 'BANK_TRANSFER', 'ACH']:
                payment.status = 'CLEARED'
            
            payment.save()
            
            # Update customer financial profile
            self._update_customer_payment_history(customer, payment)
            
            logger.info(f"Customer payment {payment.payment_number} created for {customer.name}")
            return payment
            
        except Customer.DoesNotExist:
            raise ValidationError(f"Customer {payment_data['customer_id']} not found")
        except Account.DoesNotExist:
            raise ValidationError(f"Bank account {payment_data['bank_account_id']} not found")
        except Currency.DoesNotExist:
            raise ValidationError(f"Currency {payment_data.get('currency_code')} not found")
        except Exception as e:
            logger.error(f"Error creating customer payment: {str(e)}")
            raise ValidationError(f"Failed to create payment: {str(e)}")
    
    @transaction.atomic
    def create_vendor_payment(self, payment_data: Dict, user) -> Payment:
        """
        Create and process a payment made to vendor
        
        Args:
            payment_data: Payment details dictionary
            user: User creating the payment
        
        Returns:
            Created Payment instance
        """
        try:
            # Validate required fields
            required_fields = ['vendor_id', 'amount', 'payment_method', 'bank_account_id']
            for field in required_fields:
                if field not in payment_data or payment_data[field] is None:
                    raise ValidationError(f"Missing required field: {field}")
            
            # Get related objects
            vendor = Vendor.objects.get(id=payment_data['vendor_id'], tenant=self.tenant)
            bank_account = Account.objects.get(
                id=payment_data['bank_account_id'], 
                tenant=self.tenant,
                is_bank_account=True
            )
            
            # Get currency and exchange rate
            currency_code = payment_data.get('currency_code', self.base_currency.code)
            currency = Currency.objects.get(tenant=self.tenant, code=currency_code)
            exchange_rate = self._get_exchange_rate(
                currency, 
                self.base_currency, 
                payment_data.get('payment_date', date.today())
            )
            
            # Create payment record
            payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='MADE',
                payment_method=payment_data['payment_method'],
                payment_date=payment_data.get('payment_date', date.today()),
                vendor=vendor,
                amount=Decimal(str(payment_data['amount'])),
                currency=currency,
                exchange_rate=exchange_rate,
                base_currency_amount=Decimal(str(payment_data['amount'])) * exchange_rate,
                bank_account=bank_account,
                reference_number=payment_data.get('reference_number', ''),
                description=payment_data.get('description', f'Payment to {vendor.company_name}'),
                processing_fee=Decimal(str(payment_data.get('processing_fee', '0.00'))),
                status='PENDING',
                check_number=payment_data.get('check_number', ''),
                check_date=payment_data.get('check_date'),
                external_transaction_id=payment_data.get('external_transaction_id', ''),
                processor_name=payment_data.get('processor_name', ''),
                processor_transaction_id=payment_data.get('processor_transaction_id', ''),
                created_by=user
            )
            
            # Apply to bills if specified
            if 'bill_applications' in payment_data and payment_data['bill_applications']:
                self.apply_payment_to_bills(
                    payment, 
                    payment_data['bill_applications'], 
                    user
                )
            
            # Create journal entry
            journal_entry = self._create_payment_journal_entry(payment, user)
            payment.journal_entry = journal_entry
            
            # Mark as cleared for certain payment methods
            if payment_data['payment_method'] in ['CASH', 'BANK_TRANSFER', 'ACH']:
                payment.status = 'CLEARED'
            
            payment.save()
            
            # Update vendor payment history
            self._update_vendor_payment_history(vendor, payment)
            
            logger.info(f"Vendor payment {payment.payment_number} created for {vendor.company_name}")
            return payment
            
        except Vendor.DoesNotExist:
            raise ValidationError(f"Vendor {payment_data['vendor_id']} not found")
        except Account.DoesNotExist:
            raise ValidationError(f"Bank account {payment_data['bank_account_id']} not found")
        except Currency.DoesNotExist:
            raise ValidationError(f"Currency {payment_data.get('currency_code')} not found")
        except Exception as e:
            logger.error(f"Error creating vendor payment: {str(e)}")
            raise ValidationError(f"Failed to create payment: {str(e)}")
    
    # ============================================================================
    # PAYMENT APPLICATION
    # ============================================================================
    
    @transaction.atomic
    def apply_payment_to_invoices(self, payment: Payment, invoice_applications: List[Dict], user) -> List[PaymentApplication]:
        """
        Apply payment to specific invoices
        
        Args:
            payment: Payment instance
            invoice_applications: List of invoice application details
                - invoice_id: Invoice ID
                - amount: Amount to apply
                - discount_amount: Early payment discount (optional)
            user: User applying the payment
        
        Returns:
            List of created PaymentApplication instances
        """
        if payment.payment_type != 'RECEIVED':
            raise ValidationError('Only received payments can be applied to invoices')
        
        try:
            applications = []
            total_applied = Decimal('0.00')
            
            for app_data in invoice_applications:
                invoice = Invoice.objects.get(
                    id=app_data['invoice_id'], 
                    tenant=self.tenant,
                    customer=payment.customer
                )
                
                amount_applied = Decimal(str(app_data['amount']))
                discount_amount = Decimal(str(app_data.get('discount_amount', '0.00')))
                
                # Validate application amount
                if amount_applied > invoice.amount_due:
                    raise ValidationError(
                        f"Cannot apply {amount_applied} to invoice {invoice.invoice_number}. "
                        f"Amount due: {invoice.amount_due}"
                    )
                
                # Create payment application
                application = PaymentApplication.objects.create(
                    tenant=self.tenant,
                    payment=payment,
                    invoice=invoice,
                    amount_applied=amount_applied,
                    discount_amount=discount_amount,
                    exchange_rate=payment.exchange_rate,
                    base_currency_amount_applied=amount_applied * payment.exchange_rate,
                    notes=app_data.get('notes', '')
                )
                
                applications.append(application)
                total_applied += amount_applied + discount_amount
            
            # Validate total doesn't exceed payment amount
            if total_applied > payment.amount:
                raise ValidationError(
                    f"Total applied amount {total_applied} exceeds payment amount {payment.amount}"
                )
            
            logger.info(f"Payment {payment.payment_number} applied to {len(applications)} invoices")
            return applications
            
        except Invoice.DoesNotExist:
            raise ValidationError(f"Invoice not found or doesn't belong to customer")
        except Exception as e:
            logger.error(f"Error applying payment to invoices: {str(e)}")
            raise ValidationError(f"Failed to apply payment: {str(e)}")
    
    @transaction.atomic
    def apply_payment_to_bills(self, payment: Payment, bill_applications: List[Dict], user) -> List[PaymentApplication]:
        """
        Apply payment to specific bills
        
        Args:
            payment: Payment instance
            bill_applications: List of bill application details
            user: User applying the payment
        
        Returns:
            List of created PaymentApplication instances
        """
        if payment.payment_type != 'MADE':
            raise ValidationError('Only made payments can be applied to bills')
        
        try:
            applications = []
            total_applied = Decimal('0.00')
            
            for app_data in bill_applications:
                bill = Bill.objects.get(
                    id=app_data['bill_id'], 
                    tenant=self.tenant,
                    vendor=payment.vendor
                )
                
                amount_applied = Decimal(str(app_data['amount']))
                discount_amount = Decimal(str(app_data.get('discount_amount', '0.00')))
                
                # Validate application amount
                if amount_applied > bill.amount_due:
                    raise ValidationError(
                        f"Cannot apply {amount_applied} to bill {bill.bill_number}. "
                        f"Amount due: {bill.amount_due}"
                    )
                
                # Create payment application
                application = PaymentApplication.objects.create(
                    tenant=self.tenant,
                    payment=payment,
                    bill=bill,
                    amount_applied=amount_applied,
                    discount_amount=discount_amount,
                    exchange_rate=payment.exchange_rate,
                    base_currency_amount_applied=amount_applied * payment.exchange_rate,
                    notes=app_data.get('notes', '')
                )
                
                applications.append(application)
                total_applied += amount_applied + discount_amount
            
            # Validate total doesn't exceed payment amount
            if total_applied > payment.amount:
                raise ValidationError(
                    f"Total applied amount {total_applied} exceeds payment amount {payment.amount}"
                )
            
            logger.info(f"Payment {payment.payment_number} applied to {len(applications)} bills")
            return applications
            
        except Bill.DoesNotExist:
            raise ValidationError(f"Bill not found or doesn't belong to vendor")
        except Exception as e:
            logger.error(f"Error applying payment to bills: {str(e)}")
            raise ValidationError(f"Failed to apply payment: {str(e)}")
    
    @transaction.atomic
    def unapply_payment(self, application_id: int, user) -> Dict:
        """
        Remove a payment application
        
        Args:
            application_id: PaymentApplication ID to remove
            user: User removing the application
        
        Returns:
            Unapplication result
        """
        try:
            application = PaymentApplication.objects.get(
                id=application_id,
                tenant=self.tenant
            )
            
            payment = application.payment
            amount_unapplied = application.amount_applied
            
            # Store reference info before deletion
            if application.invoice:
                document_type = 'Invoice'
                document_number = application.invoice.invoice_number
            else:
                document_type = 'Bill' 
                document_number = application.bill.bill_number
            
            # Delete the application (this will trigger model save to update amounts)
            application.delete()
            
            logger.info(f"Payment application removed: {payment.payment_number} from {document_number}")
            
            return {
                'success': True,
                'payment_number': payment.payment_number,
                'document_type': document_type,
                'document_number': document_number,
                'amount_unapplied': amount_unapplied,
                'unapplied_by': user.get_full_name(),
                'unapplied_at': timezone.now()
            }
            
        except PaymentApplication.DoesNotExist:
            raise ValidationError(f"Payment application {application_id} not found")
        except Exception as e:
            logger.error(f"Error unapplying payment: {str(e)}")
            raise ValidationError(f"Failed to unapply payment: {str(e)}")
    
    # ============================================================================
    # PAYMENT PROCESSING & STATUS MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def process_payment_clearance(self, payment_id: int, clearance_data: Dict, user) -> Payment:
        """
        Process payment clearance (e.g., check clearing, card settlement)
        
        Args:
            payment_id: Payment ID
            clearance_data: Clearance details
            user: User processing clearance
        
        Returns:
            Updated Payment instance
        """
        try:
            payment = Payment.objects.get(id=payment_id, tenant=self.tenant)
            
            if payment.status == 'CLEARED':
                raise ValidationError('Payment is already cleared')
            
            # Update payment status
            payment.status = 'CLEARED'
            payment.reconciled_date = clearance_data.get('clearance_date', date.today())
            payment.reconciled_by = user
            
            # Update processing details if provided
            if 'actual_fee' in clearance_data:
                actual_fee = Decimal(str(clearance_data['actual_fee']))
                if actual_fee != payment.processing_fee:
                    # Create adjustment for fee difference
                    fee_difference = actual_fee - payment.processing_fee
                    self._create_fee_adjustment_entry(payment, fee_difference, user)
                    payment.processing_fee = actual_fee
            
            if 'processor_reference' in clearance_data:
                payment.processor_transaction_id = clearance_data['processor_reference']
            
            payment.save()
            
            logger.info(f"Payment {payment.payment_number} marked as cleared")
            return payment
            
        except Payment.DoesNotExist:
            raise ValidationError(f"Payment {payment_id} not found")
        except Exception as e:
            logger.error(f"Error processing payment clearance: {str(e)}")
            raise ValidationError(f"Failed to process clearance: {str(e)}")
    
    @transaction.atomic
    def process_payment_bounce(self, payment_id: int, bounce_data: Dict, user) -> Payment:
        """
        Process bounced payment (NSF, declined card, etc.)
        
        Args:
            payment_id: Payment ID
            bounce_data: Bounce details
            user: User processing bounce
        
        Returns:
            Updated Payment instance
        """
        try:
            payment = Payment.objects.get(id=payment_id, tenant=self.tenant)
            
            if payment.status == 'BOUNCED':
                raise ValidationError('Payment is already marked as bounced')
            
            # Update payment status
            payment.status = 'BOUNCED'
            payment.notes = bounce_data.get('bounce_reason', 'Payment bounced')
            payment.save()
            
            # Reverse any applications
            applications = payment.applications.all()
            for application in applications:
                if application.invoice:
                    # Add bounce fee to invoice if configured
                    if 'bounce_fee' in bounce_data:
                        self._add_bounce_fee_to_invoice(
                            application.invoice, 
                            Decimal(str(bounce_data['bounce_fee'])),
                            user
                        )
                
                # The application deletion will automatically update amounts
                application.delete()
            
            # Create reversal journal entry
            if payment.journal_entry:
                self._create_payment_reversal_entry(payment, bounce_data.get('bounce_reason', ''), user)
            
            logger.info(f"Payment {payment.payment_number} processed as bounced")
            return payment
            
        except Payment.DoesNotExist:
            raise ValidationError(f"Payment {payment_id} not found")
        except Exception as e:
            logger.error(f"Error processing payment bounce: {str(e)}")
            raise ValidationError(f"Failed to process bounce: {str(e)}")
    
    @transaction.atomic
    def process_refund(self, payment: Payment, refund_amount: Decimal, 
                      refund_reason: str = '', user=None) -> Payment:
        """
        Process a refund for a customer payment
        
        Args:
            payment: Original payment to refund
            refund_amount: Amount to refund
            refund_reason: Reason for refund
            user: User processing refund
        
        Returns:
            Created refund Payment instance
        """
        if payment.payment_type != 'RECEIVED':
            raise ValidationError('Only received payments can be refunded')
        
        if refund_amount > payment.amount:
            raise ValidationError('Refund amount cannot exceed original payment amount')
        
        try:
            # Check if payment has sufficient unapplied amount
            total_applied = payment.applications.aggregate(
                total=Sum('amount_applied')
            )['total'] or Decimal('0.00')
            
            available_to_refund = payment.amount - total_applied
            
            if refund_amount > available_to_refund:
                raise ValidationError(
                    f"Cannot refund {refund_amount}. Only {available_to_refund} is available "
                    f"(payment has {total_applied} applied to invoices)"
                )
            
            # Create refund payment
            refund_payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='REFUND',
                payment_method=payment.payment_method,
                payment_date=date.today(),
                customer=payment.customer,
                amount=refund_amount,
                currency=payment.currency,
                exchange_rate=payment.exchange_rate,
                base_currency_amount=refund_amount * payment.exchange_rate,
                bank_account=payment.bank_account,
                reference_number=f"REFUND-{payment.payment_number}",
                description=f"Refund of {payment.payment_number}: {refund_reason}",
                status='PROCESSED',
                created_by=user or payment.created_by
            )
            
            # Create refund journal entry
            journal_entry = self._create_refund_journal_entry(refund_payment, payment, user)
            refund_payment.journal_entry = journal_entry
            refund_payment.save()
            
            logger.info(f"Refund {refund_payment.payment_number} processed for {refund_amount}")
            return refund_payment
            
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            raise ValidationError(f"Failed to process refund: {str(e)}")
    
    # ============================================================================
    # JOURNAL ENTRY CREATION
    # ============================================================================
    
    def _create_payment_journal_entry(self, payment: Payment, user) -> JournalEntry:
        """Create journal entry for payment"""
        
        from .journal_entry import JournalEntryService
        
        journal_service = JournalEntryService(self.tenant)
        return journal_service.create_payment_journal_entry(payment)
    
    def _create_fee_adjustment_entry(self, payment: Payment, fee_difference: Decimal, user):
        """Create journal entry for processing fee adjustment"""
        
        if abs(fee_difference) <= Decimal('0.01'):
            return  # No adjustment needed for minimal amounts
        
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=date.today(),
            description=f"Processing fee adjustment - {payment.payment_number}",
            entry_type='ADJUSTMENT',
            status='DRAFT',
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            created_by=user
        )
        
        fee_account = self._get_processing_fee_account()
        bank_account = payment.bank_account
        
        if fee_difference > 0:
            # Additional fee charged
            # Debit: Processing Fee Expense, Credit: Bank Account
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=1,
                account=fee_account,
                description="Additional processing fee",
                debit_amount=fee_difference,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=fee_difference * payment.exchange_rate,
                base_currency_credit_amount=Decimal('0.00')
            )
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=2,
                account=bank_account,
                description="Additional processing fee charged",
                debit_amount=Decimal('0.00'),
                credit_amount=fee_difference,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=fee_difference * payment.exchange_rate
            )
        else:
            # Fee refund/credit
            # Debit: Bank Account, Credit: Processing Fee Expense
            fee_credit = abs(fee_difference)
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=1,
                account=bank_account,
                description="Processing fee credit",
                debit_amount=fee_credit,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=fee_credit * payment.exchange_rate,
                base_currency_credit_amount=Decimal('0.00')
            )
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=2,
                account=fee_account,
                description="Processing fee adjustment",
                debit_amount=Decimal('0.00'),
                credit_amount=fee_credit,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=fee_credit * payment.exchange_rate
            )
        
        journal_entry.calculate_totals()
        journal_entry.post_entry(user)
    
    def _create_payment_reversal_entry(self, payment: Payment, reason: str, user):
        """Create journal entry to reverse a bounced payment"""
        
        if not payment.journal_entry:
            return
        
        # Create reversal entry
        reversal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=date.today(),
            description=f"Payment reversal - {payment.payment_number}",
            entry_type='REVERSAL',
            status='DRAFT',
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            notes=f"Reversal due to: {reason}",
            created_by=user
        )
        
        # Create reversal lines (swap debits and credits from original)
        line_number = 1
        for original_line in payment.journal_entry.journal_lines.all():
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=reversal_entry,
                line_number=line_number,
                account=original_line.account,
                description=f"Reversal: {original_line.description}",
                debit_amount=original_line.credit_amount,
                credit_amount=original_line.debit_amount,
                base_currency_debit_amount=original_line.base_currency_credit_amount,
                base_currency_credit_amount=original_line.base_currency_debit_amount,
                customer=original_line.customer,
                vendor=original_line.vendor
            )
            line_number += 1
        
        reversal_entry.calculate_totals()
        reversal_entry.post_entry(user)
    
    def _create_refund_journal_entry(self, refund_payment: Payment, 
                                   original_payment: Payment, user) -> JournalEntry:
        """Create journal entry for refund"""
        
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=refund_payment.payment_date,
            description=f"Customer refund - {original_payment.payment_number}",
            entry_type='PAYMENT',
            status='DRAFT',
            currency=refund_payment.currency,
            exchange_rate=refund_payment.exchange_rate,
            source_document_type='PAYMENT',
            source_document_id=refund_payment.id,
            source_document_number=refund_payment.payment_number,
            created_by=user
        )
        
        # Get accounts
        ar_account = self._get_accounts_receivable_account()
        
        # Credit: Bank Account (refund paid out)
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=1,
            account=refund_payment.bank_account,
            description=f"Refund to {refund_payment.customer.name}",
            debit_amount=Decimal('0.00'),
            credit_amount=refund_payment.amount,
            base_currency_debit_amount=Decimal('0.00'),
            base_currency_credit_amount=refund_payment.base_currency_amount,
            customer=refund_payment.customer
        )
        
        # Debit: Accounts Receivable (if no specific reason account)
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=2,
            account=ar_account,
            description=f"Refund - {refund_payment.customer.name}",
            debit_amount=refund_payment.amount,
            credit_amount=Decimal('0.00'),
            base_currency_debit_amount=refund_payment.base_currency_amount,
            base_currency_credit_amount=Decimal('0.00'),
            customer=refund_payment.customer
        )
        
        journal_entry.calculate_totals()
        journal_entry.post_entry(user)
        
        return journal_entry
    
    def _add_bounce_fee_to_invoice(self, invoice: Invoice, bounce_fee: Decimal, user):
        """Add bounce fee to invoice"""
        
        from ..models import InvoiceItem
        
        # Create bounce fee line item
        last_line = invoice.invoice_items.aggregate(
            max_line=models.Max('line_number')
        )['max_line'] or 0
        
        bounce_fee_account = self._get_bounce_fee_account()
        
        InvoiceItem.objects.create(
            tenant=self.tenant,
            invoice=invoice,
            line_number=last_line + 1,
            item_type='OTHER',
            description='NSF/Bounce Fee',
            quantity=Decimal('1.0000'),
            unit_price=bounce_fee,
            line_total=bounce_fee,
            revenue_account=bounce_fee_account
        )
        
        # Recalculate invoice totals
        invoice.calculate_totals()
        invoice.save()
        
        logger.info(f"Bounce fee {bounce_fee} added to invoice {invoice.invoice_number}")
    
    # ============================================================================
    # PAYMENT MATCHING & RECONCILIATION
    # ============================================================================
    
    def suggest_payment_matches(self, payment_id: int, search_criteria: Dict = None) -> List[Dict]:
        """
        Suggest invoices/bills that could match with an unapplied payment
        
        Args:
            payment_id: Payment ID to find matches for
            search_criteria: Additional search criteria
        
        Returns:
            List of potential matches
        """
        try:
            payment = Payment.objects.get(id=payment_id, tenant=self.tenant)
            
            matches = []
            tolerance = Decimal('0.01')  # Amount tolerance for matching
            
            if payment.payment_type == 'RECEIVED':
                # Find matching invoices
                invoices = Invoice.objects.filter(
                    tenant=self.tenant,
                    customer=payment.customer,
                    status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                    amount_due__gt=Decimal('0.00')
                ).order_by('due_date')
                
                for invoice in invoices:
                    match_score = self._calculate_match_score(payment, invoice)
                    
                    if match_score > 0:
                        matches.append({
                            'type': 'invoice',
                            'document_id': invoice.id,
                            'document_number': invoice.invoice_number,
                            'document_date': invoice.invoice_date,
                            'due_date': invoice.due_date,
                            'total_amount': invoice.total_amount,
                            'amount_due': invoice.amount_due,
                            'currency': invoice.currency.code,
                            'match_score': match_score,
                            'match_reasons': self._get_match_reasons(payment, invoice),
                            'recommended_amount': min(payment.amount, invoice.amount_due)
                        })
            
            elif payment.payment_type == 'MADE':
                # Find matching bills
                bills = Bill.objects.filter(
                    tenant=self.tenant,
                    vendor=payment.vendor,
                    status__in=['OPEN', 'APPROVED', 'PARTIAL'],
                    amount_due__gt=Decimal('0.00')
                ).order_by('due_date')
                
                for bill in bills:
                    match_score = self._calculate_match_score(payment, bill)
                    
                    if match_score > 0:
                        matches.append({
                            'type': 'bill',
                            'document_id': bill.id,
                            'document_number': bill.bill_number,
                            'vendor_invoice_number': bill.vendor_invoice_number,
                            'document_date': bill.bill_date,
                            'due_date': bill.due_date,
                            'total_amount': bill.total_amount,
                            'amount_due': bill.amount_due,
                            'currency': bill.currency.code,
                            'match_score': match_score,
                            'match_reasons': self._get_match_reasons(payment, bill),
                            'recommended_amount': min(payment.amount, bill.amount_due)
                        })
            
            # Sort by match score (highest first)
            matches.sort(key=lambda x: x['match_score'], reverse=True)
            
            return matches[:10]  # Return top 10 matches
            
        except Payment.DoesNotExist:
            raise ValidationError(f"Payment {payment_id} not found")
    
    def _calculate_match_score(self, payment: Payment, document) -> Decimal:
        """Calculate match score between payment and document"""
        
        score = Decimal('0.00')
        
        # Exact amount match (highest score)
        if abs(payment.amount - document.amount_due) <= Decimal('0.01'):
            score += Decimal('100.00')
        elif abs(payment.amount - document.total_amount) <= Decimal('0.01'):
            score += Decimal('90.00')
        
        # Partial amount match
        elif payment.amount < document.amount_due:
            # Payment is less than due amount (partial payment)
            ratio = payment.amount / document.amount_due
            score += ratio * Decimal('80.00')
        
        # Reference number match
        if payment.reference_number and hasattr(document, 'vendor_invoice_number'):
            if payment.reference_number.upper() in document.vendor_invoice_number.upper():
                score += Decimal('50.00')
        
        if payment.reference_number and document.reference_number:
            if payment.reference_number.upper() in document.reference_number.upper():
                score += Decimal('50.00')
        
        # Date proximity (within 30 days)
        date_diff = abs((payment.payment_date - document.due_date).days)
        if date_diff <= 7:
            score += Decimal('30.00')
        elif date_diff <= 30:
            score += Decimal('10.00')
        
        # Currency match
        if payment.currency == document.currency:
            score += Decimal('20.00')
        
        return score
    
    def _get_match_reasons(self, payment: Payment, document) -> List[str]:
        """Get reasons why payment matches document"""
        
        reasons = []
        
        # Amount matching
        if abs(payment.amount - document.amount_due) <= Decimal('0.01'):
            reasons.append('Exact amount match')
        elif abs(payment.amount - document.total_amount) <= Decimal('0.01'):
            reasons.append('Total amount match')
        elif payment.amount < document.amount_due:
            reasons.append('Partial payment amount')
        
        # Reference matching
        if payment.reference_number and hasattr(document, 'vendor_invoice_number'):
            if payment.reference_number.upper() in document.vendor_invoice_number.upper():
                reasons.append('Reference number match')
        
        # Date proximity
        date_diff = abs((payment.payment_date - document.due_date).days)
        if date_diff <= 7:
            reasons.append('Payment date near due date')
        
        # Currency
        if payment.currency == document.currency:
            reasons.append('Same currency')
        
        return reasons
    
    def auto_apply_payments(self, payment_ids: List[int] = None, 
                          confidence_threshold: Decimal = Decimal('80.00')) -> Dict:
        """
        Automatically apply payments based on matching confidence
        
        Args:
            payment_ids: Specific payment IDs to process (optional)
            confidence_threshold: Minimum confidence score for auto-application
        
        Returns:
            Auto-application results
        """
        try:
            # Get unapplied payments
            payments_query = Payment.objects.filter(
                tenant=self.tenant,
                status__in=['PENDING', 'CLEARED']
            )
            
            if payment_ids:
                payments_query = payments_query.filter(id__in=payment_ids)
            else:
                # Only process payments without applications
                payments_query = payments_query.filter(
                    applications__isnull=True
                )
            
            auto_applied = []
            manual_review = []
            
            for payment in payments_query:
                matches = self.suggest_payment_matches(payment.id)
                
                if matches and matches[0]['match_score'] >= confidence_threshold:
                    best_match = matches[0]
                    
                    try:
                        # Auto-apply the payment
                        if best_match['type'] == 'invoice':
                            applications = self.apply_payment_to_invoices(
                                payment,
                                [{
                                    'invoice_id': best_match['document_id'],
                                    'amount': best_match['recommended_amount']
                                }],
                                payment.created_by
                            )
                        else:  # bill
                            applications = self.apply_payment_to_bills(
                                payment,
                                [{
                                    'bill_id': best_match['document_id'],
                                    'amount': best_match['recommended_amount']
                                }],
                                payment.created_by
                            )
                        
                        auto_applied.append({
                            'payment_id': payment.id,
                            'payment_number': payment.payment_number,
                            'document_type': best_match['type'],
                            'document_number': best_match['document_number'],
                            'amount_applied': best_match['recommended_amount'],
                            'confidence_score': best_match['match_score']
                        })
                        
                    except Exception as e:
                        logger.warning(f"Failed to auto-apply payment {payment.payment_number}: {str(e)}")
                        manual_review.append({
                            'payment_id': payment.id,
                            'payment_number': payment.payment_number,
                            'reason': 'Auto-application failed',
                            'error': str(e)
                        })
                
                elif matches:
                    # Has matches but below confidence threshold
                    manual_review.append({
                        'payment_id': payment.id,
                        'payment_number': payment.payment_number,
                        'reason': 'Low confidence matches',
                        'best_match_score': matches[0]['match_score'],
                        'potential_matches': len(matches)
                    })
                
                else:
                    # No matches found
                    manual_review.append({
                        'payment_id': payment.id,
                        'payment_number': payment.payment_number,
                        'reason': 'No matches found',
                        'best_match_score': Decimal('0.00'),
                        'potential_matches': 0
                    })
            
            return {
                'auto_applied': auto_applied,
                'manual_review': manual_review,
                'summary': {
                    'total_processed': len(auto_applied) + len(manual_review),
                    'auto_applied_count': len(auto_applied),
                    'manual_review_count': len(manual_review),
                    'success_rate': (len(auto_applied) / max(1, len(auto_applied) + len(manual_review))) * 100
                },
                'processed_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error in auto-apply payments: {str(e)}")
            raise ValidationError(f"Auto-application failed: {str(e)}")
    
    # ============================================================================
    # PAYMENT ANALYTICS & REPORTING
    # ============================================================================
    
    def get_payment_summary(self, start_date: date, end_date: date, 
                          payment_type: str = None) -> Dict:
        """
        Get payment summary for a period
        
        Args:
            start_date: Period start date
            end_date: Period end date
            payment_type: Filter by payment type (optional)
        
        Returns:
            Payment summary data
        """
        payments_query = Payment.objects.filter(
            tenant=self.tenant,
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        if payment_type:
            payments_query = payments_query.filter(payment_type=payment_type)
        
        # Calculate summary by payment type
        summary_data = payments_query.values('payment_type').annotate(
            total_count=models.Count('id'),
            total_amount=Sum('base_currency_amount'),
            avg_amount=models.Avg('base_currency_amount'),
            total_fees=Sum('processing_fee')
        )
        
        # Calculate summary by payment method
        method_summary = payments_query.values('payment_method').annotate(
            count=models.Count('id'),
            amount=Sum('base_currency_amount')
        ).order_by('-amount')
        
        # Calculate summary by status
        status_summary = payments_query.values('status').annotate(
            count=models.Count('id'),
            amount=Sum('base_currency_amount')
        )
        
        # Daily breakdown
        daily_summary = payments_query.extra(
            select={'payment_day': 'DATE(payment_date)'}
        ).values('payment_day').annotate(
            count=models.Count('id'),
            amount=Sum('base_currency_amount')
        ).order_by('payment_day')
        
        # Overall totals
        overall_totals = payments_query.aggregate(
            total_payments=models.Count('id'),
            total_amount=Sum('base_currency_amount'),
            total_fees=Sum('processing_fee'),
            avg_payment_size=models.Avg('base_currency_amount')
        )
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'overall_totals': {
                'total_payments': overall_totals['total_payments'] or 0,
                'total_amount': overall_totals['total_amount'] or Decimal('0.00'),
                'total_fees': overall_totals['total_fees'] or Decimal('0.00'),
                'average_payment_size': overall_totals['avg_payment_size'] or Decimal('0.00'),
                'net_amount': (overall_totals['total_amount'] or Decimal('0.00')) - (overall_totals['total_fees'] or Decimal('0.00'))
            },
            'by_payment_type': list(summary_data),
            'by_payment_method': list(method_summary),
            'by_status': list(status_summary),
            'daily_breakdown': list(daily_summary),
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def get_collection_metrics(self, customer_id: int = None, 
                             period_months: int = 12) -> Dict:
        """
        Get collection performance metrics
        
        Args:
            customer_id: Specific customer (optional)
            period_months: Number of months to analyze
        
        Returns:
            Collection metrics data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_months * 30)
        
        # Base query for invoices
        invoices_query = Invoice.objects.filter(
            tenant=self.tenant,
            invoice_date__gte=start_date,
            invoice_date__lte=end_date,
            status__in=['PAID', 'PARTIAL', 'OPEN', 'OVERDUE']
        )
        
        if customer_id:
            invoices_query = invoices_query.filter(customer_id=customer_id)
        
        # Base query for payments
        payments_query = Payment.objects.filter(
            tenant=self.tenant,
            payment_type='RECEIVED',
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        if customer_id:
            payments_query = payments_query.filter(customer_id=customer_id)
        
        # Calculate metrics
        invoice_totals = invoices_query.aggregate(
            total_invoiced=Sum('base_currency_total'),
            total_collected=Sum('base_currency_amount_paid'),
            total_outstanding=Sum('base_currency_amount_due'),
            invoice_count=models.Count('id')
        )
        
        payment_totals = payments_query.aggregate(
            total_payments=Sum('base_currency_amount'),
            payment_count=models.Count('id'),
            avg_payment_size=models.Avg('base_currency_amount')
        )
        
        # Collection efficiency
        total_invoiced = invoice_totals['total_invoiced'] or Decimal('0.00')
        total_collected = invoice_totals['total_collected'] or Decimal('0.00')
        collection_rate = (total_collected / total_invoiced * 100) if total_invoiced > 0 else Decimal('0.00')
        
        # Days Sales Outstanding (DSO)
        current_ar = invoice_totals['total_outstanding'] or Decimal('0.00')
        daily_sales = total_invoiced / (period_months * 30) if total_invoiced > 0 else Decimal('0.00')
        dso = current_ar / daily_sales if daily_sales > 0 else Decimal('0.00')
        
        # Average days to pay
        paid_invoices = invoices_query.filter(status='PAID')
        total_days_to_pay = Decimal('0.00')
        paid_count = 0
        
        for invoice in paid_invoices:
            # Find the last payment for this invoice
            last_payment = PaymentApplication.objects.filter(
                invoice=invoice
            ).order_by('-application_date').first()
            
            if last_payment:
                days_to_pay = (last_payment.application_date - invoice.invoice_date).days
                total_days_to_pay += days_to_pay
                paid_count += 1
        
        avg_days_to_pay = total_days_to_pay / paid_count if paid_count > 0 else Decimal('0.00')
        
        # Aging breakdown
        overdue_30 = invoices_query.filter(
            due_date__lt=end_date - timedelta(days=30),
            status__in=['OPEN', 'OVERDUE']
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        overdue_60 = invoices_query.filter(
            due_date__lt=end_date - timedelta(days=60),
            status__in=['OPEN', 'OVERDUE']
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        overdue_90 = invoices_query.filter(
            due_date__lt=end_date - timedelta(days=90),
            status__in=['OPEN', 'OVERDUE']
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'months': period_months
            },
            'invoice_metrics': {
                'total_invoiced': total_invoiced,
                'total_collected': total_collected,
                'total_outstanding': invoice_totals['total_outstanding'] or Decimal('0.00'),
                'invoice_count': invoice_totals['invoice_count'] or 0,
                'average_invoice_size': total_invoiced / max(1, invoice_totals['invoice_count'] or 1)
            },
            'payment_metrics': {
                'total_payments': payment_totals['total_payments'] or Decimal('0.00'),
                'payment_count': payment_totals['payment_count'] or 0,
                'average_payment_size': payment_totals['avg_payment_size'] or Decimal('0.00')
            },
            'collection_performance': {
                'collection_rate_percent': collection_rate,
                'days_sales_outstanding': dso,
                'average_days_to_pay': avg_days_to_pay,
                'collection_efficiency_rating': self._get_collection_rating(collection_rate, dso)
            },
            'aging_analysis': {
                'current': invoice_totals['total_outstanding'] or Decimal('0.00') - overdue_30,
                'overdue_1_30_days': overdue_30 - overdue_60,
                'overdue_31_60_days': overdue_60 - overdue_90,
                'overdue_61_90_days': overdue_90,
                'overdue_over_90_days': overdue_90
            },
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def _get_collection_rating(self, collection_rate: Decimal, dso: Decimal) -> str:
        """Get collection efficiency rating"""
        
        if collection_rate >= 95 and dso <= 30:
            return 'EXCELLENT'
        elif collection_rate >= 90 and dso <= 45:
            return 'GOOD'
        elif collection_rate >= 80 and dso <= 60:
            return 'FAIR'
        else:
            return 'POOR'
    
    # ============================================================================
    # CUSTOMER & VENDOR FINANCIAL UPDATES
    # ============================================================================
    
    def _update_customer_payment_history(self, customer: Customer, payment: Payment):
        """Update customer financial profile with payment information"""
        
        try:
            profile, created = CustomerFinancialProfile.objects.get_or_create(
                tenant=self.tenant,
                customer=customer,
                defaults={
                    'credit_limit': Decimal('0.00'),
                    'payment_terms_days': 30
                }
            )
            
            # Update payment history
            profile.last_payment_date = payment.payment_date
            
            # Calculate running totals
            profile.total_payments += payment.base_currency_amount
            
            # Update current balance (will be updated by invoice applications)
            profile.save()
            
        except Exception as e:
            logger.warning(f"Failed to update customer payment history: {str(e)}")
    
    def _update_vendor_payment_history(self, vendor: Vendor, payment: Payment):
        """Update vendor with payment information"""
        
        try:
            # Update vendor's average payment days and other metrics
            # This would typically be handled by a separate vendor analytics service
            pass
            
        except Exception as e:
            logger.warning(f"Failed to update vendor payment history: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
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
    
    def _get_accounts_receivable_account(self) -> Account:
        """Get the Accounts Receivable account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='Accounts Receivable',
                is_active=True
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='1200',
                name='Accounts Receivable',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='Accounts Receivable',
                is_active=True
            ).first()
    
    def _get_processing_fee_account(self) -> Account:
        """Get the processing fee expense account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Processing Fee',
                is_active=True
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='6150',
                name='Payment Processing Fees',
                account_type='EXPENSE',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                name__icontains='Processing Fee',
                is_active=True
            ).first()
    
    def _get_bounce_fee_account(self) -> Account:
        """Get the bounce fee revenue account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Bounce Fee',
                is_active=True
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='4200',
                name='Bounce Fee Income',
                account_type='REVENUE',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                name__icontains='Bounce Fee',
                is_active=True
            ).first()
    
    # ============================================================================
    # VALIDATION & UTILITIES
    # ============================================================================
    
    def validate_payment_data(self, payment_data: Dict) -> Dict:
        """
        Validate payment data before processing
        
        Args:
            payment_data: Payment data to validate
        
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        # Required fields validation
        required_fields = ['amount', 'payment_method', 'bank_account_id']
        for field in required_fields:
            if field not in payment_data or payment_data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Amount validation
        if 'amount' in payment_data:
            try:
                amount = Decimal(str(payment_data['amount']))
                if amount <= 0:
                    errors.append("Payment amount must be greater than zero")
            except (ValueError, TypeError):
                errors.append("Invalid payment amount format")
        
        # Bank account validation
        if 'bank_account_id' in payment_data:
            try:
                Account.objects.get(
                    id=payment_data['bank_account_id'],
                    tenant=self.tenant,
                    is_bank_account=True,
                    is_active=True
                )
            except Account.DoesNotExist:
                errors.append("Invalid or inactive bank account")
        
        # Customer/Vendor validation
        if 'customer_id' in payment_data:
            try:
                Customer.objects.get(id=payment_data['customer_id'], tenant=self.tenant)
            except Customer.DoesNotExist:
                errors.append("Customer not found")
        
        if 'vendor_id' in payment_data:
            try:
                Vendor.objects.get(id=payment_data['vendor_id'], tenant=self.tenant)
            except Vendor.DoesNotExist:
                errors.append("Vendor not found")
        
        # Currency validation
        if 'currency_code' in payment_data:
            try:
                Currency.objects.get(
                    tenant=self.tenant,
                    code=payment_data['currency_code'],
                    is_active=True
                )
            except Currency.DoesNotExist:
                errors.append("Invalid currency code")
        
        # Date validation
        if 'payment_date' in payment_data:
            payment_date = payment_data['payment_date']
            if isinstance(payment_date, str):
                try:
                    payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
                except ValueError:
                    errors.append("Invalid payment date format")
            
            if payment_date > date.today():
                warnings.append("Payment date is in the future")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_payment_status_summary(self, start_date: date = None, 
                                 end_date: date = None) -> Dict:
        """Get summary of payment statuses"""
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        payments = Payment.objects.filter(
            tenant=self.tenant,
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        status_summary = payments.values('status').annotate(
            count=models.Count('id'),
            total_amount=Sum('base_currency_amount')
        ).order_by('status')
        
        return {
            'period': {'start_date': start_date, 'end_date': end_date},
            'status_breakdown': list(status_summary),
            'total_payments': payments.count(),
            'total_amount': payments.aggregate(
                total=Sum('base_currency_amount')
            )['total'] or Decimal('0.00'),
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }