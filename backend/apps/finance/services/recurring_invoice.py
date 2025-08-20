backend/apps/finance/services/payment.py

"""
Payment Service - Processing and Management
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional

from ..models import Payment, PaymentApplication, Invoice, Bill, Account, Customer, Vendor
from .accounting import AccountingService


class PaymentService(AccountingService):
    """Payment processing and management service"""

    def create_received_payment(self, customer: Customer, amount: Decimal, 
                              payment_method: str, payment_date: date,
                              bank_account_id: int, reference_number: str = None,
                              description: str = None) -> Payment:
        """Create a received payment from customer"""
        
        bank_account = Account.objects.get(
            id=bank_account_id, 
            tenant=self.tenant,
            is_bank_account=True
        )
        
        base_currency = self.get_base_currency()
        
        payment = Payment.objects.create(
            tenant=self.tenant,
            payment_type='RECEIVED',
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            customer=customer,
            bank_account=bank_account,
            currency=base_currency,
            reference_number=reference_number,
            description=description or f'Payment from {customer.name}',
            status='CLEARED'
        )
        
        return payment

    def create_made_payment(self, vendor: Vendor, amount: Decimal,
                          payment_method: str, payment_date: date,
                          bank_account_id: int, reference_number: str = None,
                          description: str = None) -> Payment:
        """Create a payment made to vendor"""
        
        bank_account = Account.objects.get(
            id=bank_account_id,
            tenant=self.tenant, 
            is_bank_account=True
        )
        
        base_currency = self.get_base_currency()
        
        payment = Payment.objects.create(
            tenant=self.tenant,
            payment_type='MADE',
            payment_method=payment_method,
            payment_date=payment_date,
            amount=amount,
            vendor=vendor,
            bank_account=bank_account,
            currency=base_currency,
            reference_number=reference_number,
            description=description or f'Payment to {vendor.company_name}',
            status='CLEARED'
        )
        
        return payment

    def apply_payment_to_invoices(self, payment: Payment, 
                                applications: List[Dict]) -> List[PaymentApplication]:
        """Apply payment to multiple invoices"""
        if payment.payment_type != 'RECEIVED':
            raise ValidationError('Only received payments can be applied to invoices')
        
        total_applied = sum(Decimal(str(app['amount'])) for app in applications)
        if total_applied > payment.amount:
            raise ValidationError('Cannot apply more than payment amount')
        
        payment_applications = []
        
        with transaction.atomic():
            for app_data in applications:
                invoice = Invoice.objects.get(
                    id=app_data['invoice_id'],
                    tenant=self.tenant
                )
                
                application = PaymentApplication.objects.create(
                    tenant=self.tenant,
                    payment=payment,
                    invoice=invoice,
                    amount_applied=Decimal(str(app_data['amount'])),
                    discount_amount=Decimal(str(app_data.get('discount_amount', '0.00'))),
                    notes=app_data.get('notes', '')
                )
                
                payment_applications.append(application)
            
            # Create journal entry for payment
            from .journal_entry import JournalEntryService
            journal_service = JournalEntryService(self.tenant)
            journal_service.create_payment_journal_entry(payment)
        
        return payment_applications

    def apply_payment_to_bills(self, payment: Payment,
                             applications: List[Dict]) -> List[PaymentApplication]:
        """Apply payment to multiple bills"""
        if payment.payment_type != 'MADE':
            raise ValidationError('Only made payments can be applied to bills')
        
        total_applied = sum(Decimal(str(app['amount'])) for app in applications)
        if total_applied > payment.amount:
            raise ValidationError('Cannot apply more than payment amount')
        
        payment_applications = []
        
        with transaction.atomic():
            for app_data in applications:
                bill = Bill.objects.get(
                    id=app_data['bill_id'],
                    tenant=self.tenant
                )
                
                application = PaymentApplication.objects.create(
                    tenant=self.tenant,
                    payment=payment,
                    bill=bill,
                    amount_applied=Decimal(str(app_data['amount'])),
                    discount_amount=Decimal(str(app_data.get('discount_amount', '0.00'))),
                    notes=app_data.get('notes', '')
                )
                
                payment_applications.append(application)
            
            # Create journal entry for payment
            from .journal_entry import JournalEntryService
            journal_service = JournalEntryService(self.tenant)
            journal_service.create_payment_journal_entry(payment)
        
        return payment_applications

    def process_refund(self, original_payment: Payment, refund_amount: Decimal) -> Payment:
        """Process a refund for a received payment"""
        if original_payment.payment_type != 'RECEIVED':
            raise ValidationError('Can only refund received payments')
        
        if refund_amount > original_payment.amount:
            raise ValidationError('Refund amount cannot exceed original payment')
        
        with transaction.atomic():
            # Create refund payment
            refund_payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='MADE',  # Refund is money going out
                payment_method=original_payment.payment_method,
                payment_date=date.today(),
                amount=refund_amount,
                customer=original_payment.customer,
                bank_account=original_payment.bank_account,
                currency=original_payment.currency,
                reference_number=f'REFUND-{original_payment.payment_number}',
                description=f'Refund of payment {original_payment.payment_number}',
                status='CLEARED'
            )
            
            # Create journal entry for refund
            from .journal_entry import JournalEntryService
            journal_service = JournalEntryService(self.tenant)
            
            # Custom refund journal entry
            from ..models import JournalEntry, JournalEntryLine
            
            entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=refund_payment.payment_date,
                entry_type='REFUND',
                description=f'Refund to {original_payment.customer.name}',
                source_document_type='PAYMENT',
                source_document_id=refund_payment.id,
                currency=refund_payment.currency,
                created_by=None
            )
            
            # Debit AR (money back to customer)
            ar_account = Account.objects.filter(
                tenant=self.tenant,
                account_type='CURRENT_ASSET',
                name__icontains='receivable'
            ).first()
            
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=1,
                account=ar_account,
                description=f'Refund to {original_payment.customer.name}',
                debit_amount=refund_amount,
                base_currency_debit_amount=refund_amount,
                customer=original_payment.customer
            )
            
            # Credit bank account
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=2,
                account=refund_payment.bank_account,
                description=f'Refund payment',
                credit_amount=refund_amount,
                base_currency_credit_amount=refund_amount
            )
            
            entry.calculate_totals()
            entry.post_entry(None)
            
            refund_payment.journal_entry = entry
            refund_payment.save()
        
        return refund_payment

    def record_invoice_payment(self, invoice: Invoice, amount: Decimal,
                             payment_method: str, payment_date: date,
                             bank_account_id: int, reference_number: str = None) -> Payment:
        """Record payment for a specific invoice"""
        
        # Create payment
        payment = self.create_received_payment(
            customer=invoice.customer,
            amount=amount,
            payment_method=payment_method,
            payment_date=payment_date,
            bank_account_id=bank_account_id,
            reference_number=reference_number,
            description=f'Payment for Invoice {invoice.invoice_number}'
        )
        
        # Apply to invoice
        self.apply_payment_to_invoices(payment, [{
            'invoice_id': invoice.id,
            'amount': amount
        }])
        
        return payment

    def get_payment_summary(self, start_date: date = None, 
                          end_date: date = None) -> Dict:
        """Get payment summary for period"""
        filters = {'tenant': self.tenant}
        
        if start_date:
            filters['payment_date__gte'] = start_date
        if end_date:
            filters['payment_date__lte'] = end_date
        
        payments = Payment.objects.filter(**filters)
        
        received_payments = payments.filter(payment_type='RECEIVED')
        made_payments = payments.filter(payment_type='MADE')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'received': {
                'count': received_payments.count(),
                'total_amount': sum(p.base_currency_amount for p in received_payments)
            },
            'made': {
                'count': made_payments.count(),
                'total_amount': sum(p.base_currency_amount for p in made_payments)
            },
            'net_cash_flow': sum(p.base_currency_amount for p in received_payments) - 
                           sum(p.base_currency_amount for p in made_payments)
        }

    def get_base_currency(self):
        """Get tenant's base currency"""
        from ..models import Currency
        return Currency.objects.get(tenant=self.tenant, is_base_currency=True)