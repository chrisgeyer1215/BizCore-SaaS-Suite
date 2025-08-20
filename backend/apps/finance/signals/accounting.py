# backend/apps/finance/signals/accounting.py

"""
Accounting-related signals
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from ..models import (
    JournalEntry, Invoice, Bill, Payment, 
    PaymentApplication, BankTransaction
)


@receiver(post_save, sender=JournalEntry)
def journal_entry_posted(sender, instance, created, **kwargs):
    """Handle journal entry posting"""
    if instance.status == 'POSTED' and created:
        # Update account balances
        for line in instance.journal_lines.all():
            line.update_account_balance()
        
        # Send notifications if required
        if instance.total_debit > 10000:  # Large transactions
            from ..tasks.notifications import send_large_transaction_alert
            send_large_transaction_alert.delay(instance.id)


@receiver(post_save, sender=Invoice)
def invoice_created(sender, instance, created, **kwargs):
    """Handle invoice creation and updates"""
    if created:
        # Update customer financial profile
        if hasattr(instance.customer, 'financial_profile'):
            profile = instance.customer.financial_profile
            profile.total_sales += instance.base_currency_total
            profile.current_balance += instance.base_currency_amount_due
            profile.save()
    
    # Handle status changes
    if instance.status == 'SENT' and not instance.sent_date:
        instance.sent_date = timezone.now()
        instance.save(update_fields=['sent_date'])


@receiver(post_save, sender=Bill)
def bill_created(sender, instance, created, **kwargs):
    """Handle bill creation and updates"""
    if created:
        # Update vendor balance
        instance.vendor.current_balance += instance.base_currency_amount_due
        instance.vendor.save(update_fields=['current_balance'])
    
    # Auto-approve small bills if configured
    if (instance.status == 'DRAFT' and 
        instance.total_amount <= 100 and 
        instance.tenant.finance_settings.auto_approve_small_bills):
        instance.status = 'APPROVED'
        instance.save(update_fields=['status'])


@receiver(post_save, sender=PaymentApplication)
def payment_applied(sender, instance, created, **kwargs):
    """Handle payment applications"""
    if created:
        # Update document balances
        if instance.invoice:
            instance.update_invoice_amounts()
        elif instance.bill:
            instance.update_bill_amounts()
        
        # Update customer payment history
        if instance.invoice and hasattr(instance.invoice.customer, 'financial_profile'):
            profile = instance.invoice.customer.financial_profile
            profile.last_payment_date = instance.payment.payment_date
            profile.update_payment_history()


@receiver(post_save, sender=BankTransaction)
def bank_transaction_created(sender, instance, created, **kwargs):
    """Handle bank transaction creation"""
    if created and instance.bank_statement.bank_account.auto_reconcile:
        # Attempt auto-matching
        from ..services.bank_reconciliation import BankReconciliationService
        service = BankReconciliationService(instance.tenant)
        service.auto_match_transaction(instance)