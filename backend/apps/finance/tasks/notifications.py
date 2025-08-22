"""
Finance Notifications Tasks
Celery tasks for payment reminders and notifications
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_payment_reminders(self, tenant_id: int = None):
    """Send payment reminders for overdue invoices and bills"""
    try:
        from ..models import Invoice, Bill
        from apps.core.models import Tenant
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()
        
        total_reminders = 0
        total_errors = 0
        
        for tenant in tenants:
            try:
                tenant.activate()
                
                # Send invoice reminders
                invoice_reminders, invoice_errors = _send_invoice_reminders(tenant)
                total_reminders += invoice_reminders
                total_errors += invoice_errors
                
                # Send bill reminders
                bill_reminders, bill_errors = _send_bill_reminders(tenant)
                total_reminders += bill_reminders
                total_errors += bill_errors
                
            except Exception as e:
                logger.error(f"Error sending reminders for tenant {tenant.schema_name}: {str(e)}")
                total_errors += 1
                continue
        
        logger.info(f"Payment reminders completed. Sent: {total_reminders}, Errors: {total_errors}")
        return {
            'success': True,
            'total_reminders': total_reminders,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"Error in send_payment_reminders task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _send_invoice_reminders(tenant) -> tuple:
    """Send reminders for overdue invoices"""
    from ..models import Invoice
    
    reminders_sent = 0
    errors = 0
    
    # Get overdue invoices
    overdue_invoices = Invoice.objects.filter(
        tenant=tenant,
        status__in=['OPEN', 'SENT', 'VIEWED'],
        due_date__lt=date.today(),
        amount_due__gt=0
    )
    
    for invoice in overdue_invoices:
        try:
            # Check if reminder already sent today
            if _should_send_reminder(invoice):
                _send_invoice_reminder(invoice)
                reminders_sent += 1
                
                # Update last reminder date
                invoice.last_reminder_sent = timezone.now()
                invoice.save()
                
        except Exception as e:
            logger.error(f"Error sending reminder for invoice {invoice.id}: {str(e)}")
            errors += 1
            continue
    
    return reminders_sent, errors


def _send_bill_reminders(tenant) -> tuple:
    """Send reminders for overdue bills"""
    from ..models import Bill
    
    reminders_sent = 0
    errors = 0
    
    # Get overdue bills
    overdue_bills = Bill.objects.filter(
        tenant=tenant,
        status__in=['OPEN', 'APPROVED'],
        due_date__lt=date.today(),
        amount_due__gt=0
    )
    
    for bill in overdue_bills:
        try:
            # Check if reminder already sent today
            if _should_send_reminder(bill):
                _send_bill_reminder(bill)
                reminders_sent += 1
                
                # Update last reminder date
                bill.last_reminder_sent = timezone.now()
                bill.save()
                
        except Exception as e:
            logger.error(f"Error sending reminder for bill {bill.id}: {str(e)}")
            errors += 1
            continue
    
    return reminders_sent, errors


def _should_send_reminder(document) -> bool:
    """Check if reminder should be sent"""
    if not document.last_reminder_sent:
        return True
    
    # Don't send more than one reminder per day
    return document.last_reminder_sent.date() < date.today()


def _send_invoice_reminder(invoice):
    """Send reminder for overdue invoice"""
    # This would integrate with your notification system
    # For now, just log the reminder
    days_overdue = (date.today() - invoice.due_date).days
    
    logger.info(f"Invoice reminder: {invoice.invoice_number} is {days_overdue} days overdue. "
                f"Amount: {invoice.amount_due}, Customer: {invoice.customer.name}")


def _send_bill_reminder(bill):
    """Send reminder for overdue bill"""
    # This would integrate with your notification system
    # For now, just log the reminder
    days_overdue = (date.today() - bill.due_date).days
    
    logger.info(f"Bill reminder: {bill.bill_number} is {days_overdue} days overdue. "
                f"Amount: {bill.amount_due}, Vendor: {bill.vendor.name}")


@shared_task
def send_low_balance_alerts():
    """Send alerts for low bank account balances"""
    try:
        from ..models import BankAccount
        from apps.core.models import Tenant
        
        total_alerts = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Get bank accounts with low balances
                low_balance_accounts = BankAccount.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    current_balance__lt=Decimal('100.00')  # Threshold
                )
                
                for account in low_balance_accounts:
                    try:
                        _send_low_balance_alert(account)
                        total_alerts += 1
                        
                    except Exception as e:
                        logger.error(f"Error sending low balance alert for account {account.id}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Low balance alerts completed. Sent: {total_alerts}")
        return {'success': True, 'alerts_sent': total_alerts}
        
    except Exception as e:
        logger.error(f"Error in send_low_balance_alerts task: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_low_balance_alert(account):
    """Send low balance alert for bank account"""
    # This would integrate with your notification system
    logger.warning(f"Low balance alert: Account {account.account_number} "
                   f"({account.account_name}) has balance: {account.current_balance}")


@shared_task
def send_reconciliation_alerts():
    """Send alerts for overdue bank reconciliations"""
    try:
        from ..models import BankAccount
        from apps.core.models import Tenant
        
        total_alerts = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Get accounts that need reconciliation
                accounts_needing_reconciliation = BankAccount.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    last_reconciliation_date__lt=date.today() - timedelta(days=30)
                )
                
                for account in accounts_needing_reconciliation:
                    try:
                        _send_reconciliation_alert(account)
                        total_alerts += 1
                        
                    except Exception as e:
                        logger.error(f"Error sending reconciliation alert for account {account.id}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Reconciliation alerts completed. Sent: {total_alerts}")
        return {'success': True, 'alerts_sent': total_alerts}
        
    except Exception as e:
        logger.error(f"Error in send_reconciliation_alerts task: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_reconciliation_alert(account):
    """Send reconciliation alert for bank account"""
    days_since_reconciliation = (date.today() - account.last_reconciliation_date).days
    
    logger.warning(f"Reconciliation alert: Account {account.account_number} "
                   f"({account.account_name}) hasn't been reconciled for {days_since_reconciliation} days")


@shared_task
def send_financial_period_reminders():
    """Send reminders for financial period closing"""
    try:
        from ..models import FiscalYear, FinancialPeriod
        from apps.core.models import Tenant
        
        total_reminders = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Get current fiscal year
                current_fiscal_year = FiscalYear.objects.filter(
                    tenant=tenant,
                    status='OPEN'
                ).first()
                
                if current_fiscal_year:
                    # Get periods that need closing
                    periods_needing_closure = FinancialPeriod.objects.filter(
                        tenant=tenant,
                        fiscal_year=current_fiscal_year,
                        status='OPEN',
                        end_date__lt=date.today() - timedelta(days=7)
                    )
                    
                    for period in periods_needing_closure:
                        try:
                            _send_period_closure_reminder(period)
                            total_reminders += 1
                            
                        except Exception as e:
                            logger.error(f"Error sending period reminder for {period.id}: {str(e)}")
                            continue
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Financial period reminders completed. Sent: {total_reminders}")
        return {'success': True, 'reminders_sent': total_reminders}
        
    except Exception as e:
        logger.error(f"Error in send_financial_period_reminders task: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_period_closure_reminder(period):
    """Send reminder for financial period closure"""
    days_overdue = (date.today() - period.end_date).days
    
    logger.warning(f"Period closure reminder: {period.name} ended {days_overdue} days ago "
                   f"and needs to be closed")
