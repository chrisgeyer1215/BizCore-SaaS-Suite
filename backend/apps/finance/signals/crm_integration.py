# backend/apps/finance/signals/crm_integration.py

"""
CRM integration signals
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import Invoice, Payment, CustomerFinancialProfile
from apps.crm.models import Customer, Lead


@receiver(post_save, sender=Customer)
def customer_created(sender, instance, created, **kwargs):
    """Create financial profile when customer is created"""
    if created:
        CustomerFinancialProfile.objects.create(
            tenant=instance.tenant,
            customer=instance,
            credit_limit=5000.00,  # Default credit limit
            payment_terms_days=30,
            credit_rating='UNRATED'
        )


@receiver(post_save, sender=Payment)
def customer_payment_received(sender, instance, created, **kwargs):
    """Update customer metrics when payment is received"""
    if created and instance.payment_type == 'RECEIVED' and instance.customer:
        profile = instance.customer.financial_profile
        
        # Update payment history
        profile.total_payments += instance.base_currency_amount
        profile.last_payment_date = instance.payment_date
        profile.update_payment_history()
        
        # Update CRM opportunity if linked
        for application in instance.applications.filter(invoice__isnull=False):
            invoice = application.invoice
            if hasattr(invoice, 'source_opportunity'):
                opportunity = invoice.source_opportunity
                opportunity.actual_revenue += application.amount_applied
                opportunity.save()