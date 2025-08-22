"""
Finance Recurring Invoices Tasks
Celery tasks for recurring invoice automation
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_recurring_invoices(self, tenant_id: int = None):
    """Process recurring invoices for all tenants or specific tenant"""
    try:
        from ..models import RecurringInvoice, Invoice, InvoiceItem
        from apps.core.models import Tenant
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()
        
        total_processed = 0
        total_errors = 0
        
        for tenant in tenants:
            try:
                # Set tenant context
                tenant.activate()
                
                # Process recurring invoices for this tenant
                processed, errors = _process_tenant_recurring_invoices(tenant)
                total_processed += processed
                total_errors += errors
                
                logger.info(f"Processed {processed} recurring invoices for tenant {tenant.schema_name}")
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}")
                total_errors += 1
                continue
        
        logger.info(f"Recurring invoice processing completed. Processed: {total_processed}, Errors: {total_errors}")
        return {
            'success': True,
            'total_processed': total_processed,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"Error in process_recurring_invoices task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _process_tenant_recurring_invoices(tenant) -> tuple:
    """Process recurring invoices for a specific tenant"""
    from ..models import RecurringInvoice, Invoice, InvoiceItem, Customer
    
    processed = 0
    errors = 0
    
    # Get active recurring invoices
    recurring_invoices = RecurringInvoice.objects.filter(
        tenant=tenant,
        is_active=True,
        next_invoice_date__lte=date.today()
    )
    
    for recurring in recurring_invoices:
        try:
            with transaction.atomic():
                # Create the invoice
                invoice = _create_recurring_invoice(recurring)
                
                # Update next invoice date
                _update_next_invoice_date(recurring)
                
                # Log the creation
                logger.info(f"Created invoice {invoice.invoice_number} from recurring {recurring.id}")
                processed += 1
                
        except Exception as e:
            logger.error(f"Error creating invoice from recurring {recurring.id}: {str(e)}")
            errors += 1
            continue
    
    return processed, errors


def _create_recurring_invoice(recurring) -> Invoice:
    """Create a new invoice from recurring invoice template"""
    from ..models import Invoice, InvoiceItem
    
    # Create invoice
    invoice = Invoice.objects.create(
        tenant=recurring.tenant,
        customer=recurring.customer,
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=recurring.payment_terms_days),
        invoice_type=recurring.invoice_type,
        status='DRAFT',
        notes=recurring.notes,
        created_by=recurring.created_by
    )
    
    # Copy invoice items
    for item in recurring.items.all():
        InvoiceItem.objects.create(
            invoice=invoice,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            account=item.account
        )
    
    # Calculate totals
    invoice.calculate_totals()
    invoice.save()
    
    return invoice


def _update_next_invoice_date(recurring):
    """Update next invoice date based on frequency"""
    current_date = recurring.next_invoice_date
    
    if recurring.frequency == 'DAILY':
        next_date = current_date + timedelta(days=1)
    elif recurring.frequency == 'WEEKLY':
        next_date = current_date + timedelta(weeks=1)
    elif recurring.frequency == 'MONTHLY':
        # Simple monthly calculation
        if current_date.month == 12:
            next_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            next_date = current_date.replace(month=current_date.month + 1)
    elif recurring.frequency == 'QUARTERLY':
        # Simple quarterly calculation
        quarter = (current_date.month - 1) // 3
        next_quarter_month = quarter * 3 + 4
        if next_quarter_month > 12:
            next_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            next_date = current_date.replace(month=next_quarter_month)
    elif recurring.frequency == 'YEARLY':
        next_date = current_date.replace(year=current_date.year + 1)
    else:
        next_date = current_date + timedelta(days=1)
    
    # Check if we've exceeded the end date
    if recurring.end_date and next_date > recurring.end_date:
        recurring.is_active = False
        recurring.notes = f"Deactivated - exceeded end date {recurring.end_date}"
    
    recurring.next_invoice_date = next_date
    recurring.last_processed = timezone.now()
    recurring.save()


@shared_task
def send_recurring_invoice_reminders():
    """Send reminders for upcoming recurring invoices"""
    try:
        from ..models import RecurringInvoice
        from apps.core.models import Tenant
        
        total_reminders = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Get recurring invoices due in next 7 days
                upcoming_recurring = RecurringInvoice.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    next_invoice_date__lte=date.today() + timedelta(days=7),
                    next_invoice_date__gt=date.today()
                )
                
                for recurring in upcoming_recurring:
                    # Send reminder (implementation depends on notification system)
                    _send_recurring_reminder(recurring)
                    total_reminders += 1
                
            except Exception as e:
                logger.error(f"Error sending reminders for tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Sent {total_reminders} recurring invoice reminders")
        return {'success': True, 'reminders_sent': total_reminders}
        
    except Exception as e:
        logger.error(f"Error in send_recurring_invoice_reminders task: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_recurring_reminder(recurring):
    """Send reminder for upcoming recurring invoice"""
    # This would integrate with your notification system
    # For now, just log the reminder
    logger.info(f"Reminder: Recurring invoice {recurring.id} due on {recurring.next_invoice_date}")


@shared_task
def cleanup_expired_recurring_invoices():
    """Deactivate expired recurring invoices"""
    try:
        from ..models import RecurringInvoice
        from apps.core.models import Tenant
        
        total_cleaned = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Find expired recurring invoices
                expired_recurring = RecurringInvoice.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    end_date__lt=date.today()
                )
                
                for recurring in expired_recurring:
                    recurring.is_active = False
                    recurring.notes = f"Deactivated - expired on {recurring.end_date}"
                    recurring.save()
                    total_cleaned += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {total_cleaned} expired recurring invoices")
        return {'success': True, 'cleaned_up': total_cleaned}
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_recurring_invoices task: {str(e)}")
        return {'success': False, 'error': str(e)}
