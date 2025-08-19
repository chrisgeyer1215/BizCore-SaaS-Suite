"""
Journal Entry Service
Automated journal entry creation and management
"""

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional

from ..models import (
    JournalEntry, JournalEntryLine, Account, Currency, ExchangeRate,
    Invoice, Bill, Payment, FiscalYear, FinanceSettings
)


class JournalEntryService:
    """Service for creating and managing journal entries"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
            return None
    
    @transaction.atomic
    def create_invoice_journal_entry(self, invoice) -> JournalEntry:
        """
        Create journal entry for invoice approval
        DR: Accounts Receivable
        CR: Revenue
        CR: Tax Payable (if applicable)
        """
        if invoice.journal_entry:
            return invoice.journal_entry
        
        # Get accounts
        ar_account = self._get_accounts_receivable_account()
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=invoice.invoice_date,
            entry_type='INVOICE',
            description=f'Invoice {invoice.invoice_number} - {invoice.customer.name}',
            currency=invoice.currency,
            exchange_rate=invoice.exchange_rate,
            source_document_type='Invoice',
            source_document_id=invoice.id,
            source_document_number=invoice.invoice_number,
            created_by_id=invoice.created_by_id if invoice.created_by_id else 1
        )
        
        line_number = 1
        
        # Debit Accounts Receivable
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=ar_account,
            description=f'Invoice {invoice.invoice_number}',
            debit_amount=invoice.total_amount,
            base_currency_debit_amount=invoice.base_currency_total,
            customer=invoice.customer
        )
        line_number += 1
        
        # Credit Revenue and Tax accounts
        for item in invoice.invoice_items.all():
            # Credit Revenue
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=item.revenue_account,
                description=f'{item.description}',
                credit_amount=item.line_total,
                base_currency_credit_amount=item.line_total * invoice.exchange_rate,
                customer=invoice.customer,
                product=item.product,
                project=item.project,
                department=item.department,
                location=item.location
            )
            line_number += 1
            
            # Credit Tax if applicable
            if item.tax_amount > 0 and item.tax_code:
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=item.tax_code.tax_collected_account,
                    description=f'Tax on {item.description}',
                    credit_amount=item.tax_amount,
                    base_currency_credit_amount=item.tax_amount * invoice.exchange_rate,
                    customer=invoice.customer,
                    tax_code=item.tax_code
                )
                line_number += 1
        
        # Credit Shipping if applicable
        if invoice.shipping_amount > 0:
            shipping_account = self._get_shipping_revenue_account()
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=shipping_account,
                description='Shipping',
                credit_amount=invoice.shipping_amount,
                base_currency_credit_amount=invoice.shipping_amount * invoice.exchange_rate,
                customer=invoice.customer
            )
        
        # Calculate and save totals
        journal_entry.calculate_totals()
        
        # Auto-post if enabled
        if self.settings and self.settings.auto_create_journal_entries:
            journal_entry.post_entry(invoice.approved_by or invoice.created_by)
        
        # Link to invoice
        invoice.journal_entry = journal_entry
        invoice.save(update_fields=['journal_entry'])
        
        return journal_entry
    
    @transaction.atomic
    def create_bill_journal_entry(self, bill) -> JournalEntry:
        """
        Create journal entry for bill approval
        DR: Expense/Asset
        DR: Tax (if recoverable)
        CR: Accounts Payable
        """
        if bill.journal_entry:
            return bill.journal_entry
        
        # Get accounts
        ap_account = self._get_accounts_payable_account()
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=bill.bill_date,
            entry_type='BILL',
            description=f'Bill {bill.bill_number} - {bill.vendor.company_name}',
            currency=bill.currency,
            exchange_rate=bill.exchange_rate,
            source_document_type='Bill',
            source_document_id=bill.id,
            source_document_number=bill.bill_number,
            created_by_id=bill.created_by_id if bill.created_by_id else 1
        )
        
        line_number = 1
        
        # Debit Expense/Asset accounts
        for item in bill.bill_items.all():
            # Debit Expense/Asset
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=item.expense_account,
                description=f'{item.description}',
                debit_amount=item.line_total,
                base_currency_debit_amount=item.line_total * bill.exchange_rate,
                vendor=bill.vendor,
                product=item.product,
                project=item.project,
                department=item.department,
                location=item.location
            )
            line_number += 1
            
            # Debit Tax if recoverable
            if item.tax_amount > 0 and item.tax_code and item.tax_code.is_recoverable:
                tax_account = item.tax_code.tax_paid_account or self._get_input_tax_account()
                JournalEntryLine.objects.create(
                    tenant=self.tenant,
                    journal_entry=journal_entry,
                    line_number=line_number,
                    account=tax_account,
                    description=f'Tax on {item.description}',
                    debit_amount=item.tax_amount,
                    base_currency_debit_amount=item.tax_amount * bill.exchange_rate,
                    vendor=bill.vendor,
                    tax_code=item.tax_code
                )
                line_number += 1
        
        # Debit Shipping if applicable
        if bill.shipping_amount > 0:
            shipping_account = self._get_shipping_expense_account()
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=shipping_account,
                description='Shipping',
                debit_amount=bill.shipping_amount,
                base_currency_debit_amount=bill.shipping_amount * bill.exchange_rate,
                vendor=bill.vendor
            )
            line_number += 1
        
        # Credit Accounts Payable
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=line_number,
            account=ap_account,
            description=f'Bill {bill.bill_number}',
            credit_amount=bill.total_amount,
            base_currency_credit_amount=bill.base_currency_total,
            vendor=bill.vendor
        )
        
        # Calculate and save totals
        journal_entry.calculate_totals()
        
        # Auto-post if enabled
        if self.settings and self.settings.auto_create_journal_entries:
            journal_entry.post_entry(bill.approved_by or bill.created_by)
        
        # Link to bill
        bill.journal_entry = journal_entry
        bill.save(update_fields=['journal_entry'])
        
        return journal_entry
    
    @transaction.atomic
    def create_payment_journal_entry(self, payment) -> JournalEntry:
        """
        Create journal entry for payment
        For received payments: DR: Bank, CR: AR
        For made payments: DR: AP, CR: Bank
        """
        if payment.journal_entry:
            return payment.journal_entry
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=payment.payment_date,
            entry_type='PAYMENT',
            description=f'Payment {payment.payment_number}',
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            source_document_type='Payment',
            source_document_id=payment.id,
            source_