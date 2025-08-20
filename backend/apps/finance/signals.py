# backend/apps/finance/signals.py

"""
Finance Module Signals
Handle model events and integration points
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

# Import models
from .models import (
    Invoice, InvoiceItem, Bill, BillItem, Payment, PaymentApplication,
    JournalEntry, JournalEntryLine, BankTransaction, InventoryCostLayer
)


@receiver(post_save, sender=Invoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """Handle invoice creation and updates"""
    if created:
        # Send notification for new invoice
        from .tasks import send_invoice_notification
        send_invoice_notification.delay(instance.id)
    
    # Update customer financial profile
    if hasattr(instance.customer, 'financial_profile'):
        from .integrations.crm_integration import CRMIntegrationService
        service = CRMIntegrationService(instance.tenant)
        service.update_customer_financial_metrics(
            instance.customer, 
            instance.customer.financial_profile
        )


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """Handle payment creation and updates"""
    if created:
        # Create journal entry for payment
        instance.create_journal_entry()
        
        # Send payment notification
        from .tasks import send_payment_notification
        send_payment_notification.delay(instance.id)


@receiver(post_save, sender=PaymentApplication)
def payment_application_post_save(sender, instance, created, **kwargs):
    """Handle payment application updates"""
    if created:
        # Update invoice/bill payment status
        if instance.invoice:
            instance.update_invoice_amounts()
        elif instance.bill:
            instance.update_bill_amounts()


@receiver(post_save, sender=JournalEntry)
def journal_entry_post_save(sender, instance, created, **kwargs):
    """Handle journal entry updates"""
    if instance.status == 'POSTED' and hasattr(instance, '_just_posted'):
        # Update account balances when entry is posted
        for line in instance.journal_lines.all():
            line.update_account_balance()
        
        # Remove the flag
        delattr(instance, '_just_posted')


@receiver(pre_save, sender=JournalEntry)
def journal_entry_pre_save(sender, instance, **kwargs):
    """Handle journal entry pre-save"""
    if instance.pk:
        # Check if status changed to POSTED
        old_instance = JournalEntry.objects.get(pk=instance.pk)
        if old_instance.status != 'POSTED' and instance.status == 'POSTED':
            instance._just_posted = True


@receiver(post_save, sender=BankTransaction)
def bank_transaction_post_save(sender, instance, created, **kwargs):
    """Handle bank transaction auto-matching"""
    if created and instance.reconciliation_status == 'UNMATCHED':
        # Attempt auto-matching
        from .tasks import auto_match_bank_transaction
        auto_match_bank_transaction.delay(instance.id)


@receiver(post_save, sender=InventoryCostLayer)
def inventory_cost_layer_post_save(sender, instance, created, **kwargs):
    """Handle inventory cost layer updates"""
    if created:
        # Update inventory account balance
        from .tasks import update_inventory_valuation
        update_inventory_valuation.delay(instance.tenant.id)


# Integration signals

@receiver(post_save, sender='ecommerce.Order')
def ecommerce_order_post_save(sender, instance, created, **kwargs):
    """Handle e-commerce order creation"""
    if created and instance.status == 'COMPLETED':
        # Create invoice from order
        from .tasks import create_invoice_from_order
        create_invoice_from_order.delay(instance.id)


@receiver(post_save, sender='inventory.StockMovement')
def inventory_movement_post_save(sender, instance, created, **kwargs):
    """Handle inventory movements for COGS"""
    if created and instance.movement_type == 'OUT':
        # Create COGS entry for sales
        from .tasks import create_cogs_entry
        create_cogs_entry.delay(instance.id)


@receiver(post_save, sender='crm.Customer')
def crm_customer_post_save(sender, instance, created, **kwargs):
    """Handle CRM customer creation"""
    if created:
        # Create financial profile
        from .models import CustomerFinancialProfile
        CustomerFinancialProfile.objects.get_or_create(
            customer=instance,
            tenant=instance.tenant,
            defaults={
                'credit_limit': Decimal('5000.00'),
                'payment_terms_days': 30,
                'credit_rating': 'UNRATED'
            }
        )