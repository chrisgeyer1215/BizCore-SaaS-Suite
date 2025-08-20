backend/apps/finance/tasks.py

"""
Finance Module Celery Tasks
Background tasks for financial operations
"""

from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

@shared_task
def send_invoice_notification(invoice_id):
    """Send notification for new invoice"""
    try:
        from .models import Invoice
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Send email notification
        from .services.notifications import FinanceNotificationService
        service = FinanceNotificationService(invoice.tenant)
        service.send_invoice_created_notification(invoice)
        
    except Exception as e:
        # Log error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send invoice notification: {str(e)}")


@shared_task
def send_payment_notification(payment_id):
    """Send notification for payment received"""
    try:
        from .models import Payment
        payment = Payment.objects.get(id=payment_id)
        
        # Send email notification
        from .services.notifications import FinanceNotificationService
        service = FinanceNotificationService(payment.tenant)
        service.send_payment_received_notification(payment)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send payment notification: {str(e)}")


@shared_task
def auto_match_bank_transaction(transaction_id):
    """Attempt to auto-match bank transaction"""
    try:
        from .models import BankTransaction
        from .services.bank_reconciliation import BankReconciliationService
        
        transaction = BankTransaction.objects.get(id=transaction_id)
        service = BankReconciliationService(transaction.tenant)
        
        result = service.auto_match_transaction(transaction)
        if result['matched']:
            transaction.mark_as_matched(
                result['record'],
                confidence=result['confidence']
            )
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to auto-match bank transaction: {str(e)}")


@shared_task
def update_inventory_valuation(tenant_id):
    """Update inventory valuation in finance"""
    try:
        from .integrations.inventory_integration import InventoryIntegrationService
        from apps.core.models import Tenant
        
        tenant = Tenant.objects.get(id=tenant_id)
        service = InventoryIntegrationService(tenant)
        
        result = service.update_inventory_valuation()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to update inventory valuation: {str(e)}")


@shared_task
def create_invoice_from_order(order_id):
    """Create invoice from e-commerce order"""
    try:
        from apps.ecommerce.models import Order
        from .integrations.ecommerce_integration import EcommerceIntegrationService
        
        order = Order.objects.get(id=order_id)
        service = EcommerceIntegrationService(order.tenant)
        
        invoice = service.create_invoice_from_order(order)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create invoice from order: {str(e)}")


@shared_task
def create_cogs_entry(movement_id):
    """Create COGS entry for inventory movement"""
    try:
        from apps.inventory.models import StockMovement
        from .integrations.inventory_integration import InventoryIntegrationService
        
        movement = StockMovement.objects.get(id=movement_id)
        service = InventoryIntegrationService(movement.tenant)
        
        if movement.movement_type == 'OUT':
            # Create COGS entry
            cogs_entry = service.create_cogs_entries([{
                'product_id': movement.stock_item.product.id,
                'quantity': movement.quantity,
                'sale_date': movement.movement_date,
                'warehouse_id': movement.stock_item.warehouse.id,
                'source_type': 'STOCK_MOVEMENT',
                'source_id': movement.id
            }])
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create COGS entry: {str(e)}")


@shared_task
def process_recurring_invoices():
    """Process recurring invoices"""
    try:
        from .models import Invoice
        from .services.recurring_invoice import RecurringInvoiceService
        
        # Get invoices due for recurring
        today = date.today()
        recurring_invoices = Invoice.objects.filter(
            is_recurring=True,
            next_invoice_date__lte=today,
            status='PAID'
        )
        
        for invoice in recurring_invoices:
            service = RecurringInvoiceService(invoice.tenant)
            service.create_next_invoice(invoice)
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to process recurring invoices: {str(e)}")


@shared_task
def send_payment_reminders():
    """Send payment reminders for overdue invoices"""
    try:
        from .models import Invoice
        from .services.notifications import FinanceNotificationService
        
        # Get overdue invoices
        today = date.today()
        overdue_invoices = Invoice.objects.filter(
            status__in=['OPEN', 'SENT', 'VIEWED'],
            due_date__lt=today,
            amount_due__gt=0
        )
        
        for invoice in overdue_invoices:
            service = FinanceNotificationService(invoice.tenant)
            service.send_payment_reminder(invoice)
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send payment reminders: {str(e)}")


@shared_task
def update_exchange_rates():
    """Update currency exchange rates"""
    try:
        from .services.currency import CurrencyService
        from apps.core.models import Tenant
        
        tenants = Tenant.objects.filter(is_active=True)
        
        for tenant in tenants:
            service = CurrencyService(tenant)
            service.update_exchange_rates()
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to update exchange rates: {str(e)}")


@shared_task
def sync_bank_feeds():
    """Sync bank feeds for all accounts"""
    try:
        from .models import BankAccount
        from .services.bank_feeds import BankFeedService
        
        bank_accounts = BankAccount.objects.filter(
            enable_bank_feeds=True,
            bank_feed_id__isnull=False
        )
        
        for account in bank_accounts:
            service = BankFeedService(account.tenant)
            service.sync_bank_feed(account)
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync bank feeds: {str(e)}")


@shared_task
def generate_financial_reports():
    """Generate scheduled financial reports"""
    try:
        from .services.reporting import FinancialReportingService
        from apps.core.models import Tenant
        
        tenants = Tenant.objects.filter(is_active=True)
        
        for tenant in tenants:
            service = FinancialReportingService(tenant)
            
            # Generate monthly reports
            if date.today().day == 1:  # First day of month
                service.generate_monthly_reports()
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate financial reports: {str(e)}")


@shared_task
def cleanup_old_reconciliations():
    """Cleanup old bank reconciliation data"""
    try:
        from .models import BankReconciliation
        
        # Keep reconciliations for 2 years
        cutoff_date = date.today() - timedelta(days=730)
        
        old_reconciliations = BankReconciliation.objects.filter(
            reconciliation_date__lt=cutoff_date,
            status='COMPLETED'
        )
        
        count = old_reconciliations.count()
        old_reconciliations.delete()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Cleaned up {count} old bank reconciliations")
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to cleanup old reconciliations: {str(e)}")


# Periodic tasks (configured in celery beat schedule)
@shared_task
def daily_finance_tasks():
    """Run daily finance maintenance tasks"""
    update_exchange_rates.delay()
    process_recurring_invoices.delay()
    send_payment_reminders.delay()
    sync_bank_feeds.delay()


@shared_task
def weekly_finance_tasks():
    """Run weekly finance maintenance tasks"""
    cleanup_old_reconciliations.delay()


@shared_task
def monthly_finance_tasks():
    """Run monthly finance maintenance tasks"""
    generate_financial_reports.delay()