"""
Finance Maintenance Tasks
Celery tasks for data cleanup and maintenance
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_data_integrity_check(self, tenant_id: int = None):
    """Run comprehensive data integrity checks for all tenants or specific tenant"""
    try:
        from ..models import Account, JournalEntry, Invoice, Bill, Payment
        from apps.core.models import Tenant
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()
        
        total_issues = 0
        total_tenants = 0
        
        for tenant in tenants:
            try:
                tenant.activate()
                
                # Run integrity checks for this tenant
                issues = _check_tenant_data_integrity(tenant)
                total_issues += len(issues)
                total_tenants += 1
                
                if issues:
                    logger.warning(f"Found {len(issues)} integrity issues in tenant {tenant.schema_name}")
                    for issue in issues:
                        logger.warning(f"  - {issue}")
                
            except Exception as e:
                logger.error(f"Error checking tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Data integrity check completed for {total_tenants} tenants. Total issues: {total_issues}")
        return {
            'success': True,
            'total_tenants': total_tenants,
            'total_issues': total_issues
        }
        
    except Exception as e:
        logger.error(f"Error in run_data_integrity_check task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _check_tenant_data_integrity(tenant) -> list:
    """Check data integrity for a specific tenant"""
    issues = []
    
    # Check journal entry balances
    unbalanced_entries = JournalEntry.objects.filter(
        tenant=tenant,
        status='POSTED'
    ).exclude(total_debit=F('total_credit'))
    
    if unbalanced_entries.exists():
        issues.append(f"{unbalanced_entries.count()} unbalanced journal entries found")
    
    # Check for journal entries without lines
    entries_without_lines = JournalEntry.objects.filter(
        tenant=tenant,
        lines__isnull=True
    )
    
    if entries_without_lines.exists():
        issues.append(f"{entries_without_lines.count()} journal entries without lines found")
    
    # Check account balances
    accounts_with_issues = _check_account_balances(tenant)
    if accounts_with_issues:
        issues.extend(accounts_with_issues)
    
    # Check invoice/bill payment integrity
    payment_issues = _check_payment_integrity(tenant)
    if payment_issues:
        issues.extend(payment_issues)
    
    return issues


def _check_account_balances(tenant) -> list:
    """Check account balance integrity"""
    from ..services.accounting import AccountingService
    
    issues = []
    accounting_service = AccountingService(tenant)
    
    # Check if calculated balances match stored balances
    accounts = Account.objects.filter(tenant=tenant, is_active=True)
    mismatched_count = 0
    
    for account in accounts:
        try:
            calculated_balance = accounting_service.get_account_balance(account.id)
            if abs(calculated_balance - (account.current_balance or 0)) > Decimal('0.01'):
                mismatched_count += 1
        except Exception:
            mismatched_count += 1
    
    if mismatched_count > 0:
        issues.append(f"{mismatched_count} accounts have mismatched balances")
    
    return issues


def _check_payment_integrity(tenant) -> list:
    """Check payment integrity"""
    issues = []
    
    # Check for overpaid invoices
    overpaid_invoices = Invoice.objects.filter(
        tenant=tenant,
        amount_paid__gt=F('total_amount')
    )
    
    if overpaid_invoices.exists():
        issues.append(f"{overpaid_invoices.count()} overpaid invoices found")
    
    # Check for overpaid bills
    overpaid_bills = Bill.objects.filter(
        tenant=tenant,
        amount_paid__gt=F('total_amount')
    )
    
    if overpaid_bills.exists():
        issues.append(f"{overpaid_bills.count()} overpaid bills found")
    
    return issues


@shared_task
def cleanup_old_data():
    """Clean up old data based on retention policies"""
    try:
        from ..models import JournalEntry, BankTransaction, FinancialReport
        from apps.core.models import Tenant
        
        # Default retention: 7 years
        cutoff_date = date.today() - timedelta(days=7*365)
        total_cleaned = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Clean up old journal entries
                old_entries = JournalEntry.objects.filter(
                    tenant=tenant,
                    entry_date__lt=cutoff_date,
                    status='POSTED'
                )
                
                # Mark as archived instead of deleting
                archived_count = old_entries.update(
                    notes=F('notes') + ' [ARCHIVED]',
                    is_archived=True
                )
                total_cleaned += archived_count
                
                # Clean up old bank transactions
                old_bank_transactions = BankTransaction.objects.filter(
                    tenant=tenant,
                    transaction_date__lt=cutoff_date,
                    status='RECONCILED'
                )
                
                archived_bank_count = old_bank_transactions.update(
                    notes=F('notes') + ' [ARCHIVED]',
                    is_archived=True
                )
                total_cleaned += archived_bank_count
                
                # Clean up old reports
                old_reports = FinancialReport.objects.filter(
                    tenant=tenant,
                    generated_date__date__lt=cutoff_date
                )
                
                archived_reports_count = old_reports.update(
                    status='ARCHIVED',
                    notes=F('notes') + ' [ARCHIVED]'
                )
                total_cleaned += archived_reports_count
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Data cleanup completed. Total items archived: {total_cleaned}")
        return {'success': True, 'total_cleaned': total_cleaned}
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_data task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def update_account_balances():
    """Update all account balances for all tenants"""
    try:
        from ..services.accounting import AccountingService
        from apps.core.models import Tenant
        
        total_updated = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                accounting_service = AccountingService(tenant)
                updated_balances = accounting_service.update_account_balances()
                
                total_updated += len(updated_balances)
                logger.info(f"Updated {len(updated_balances)} account balances for tenant {tenant.schema_name}")
                
            except Exception as e:
                logger.error(f"Error updating balances for tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Account balance update completed. Total accounts updated: {total_updated}")
        return {'success': True, 'total_updated': total_updated}
        
    except Exception as e:
        logger.error(f"Error in update_account_balances task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def validate_accounting_equation():
    """Validate accounting equation (Assets = Liabilities + Equity) for all tenants"""
    try:
        from ..services.accounting import AccountingService
        from apps.core.models import Tenant
        
        total_validated = 0
        total_issues = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                accounting_service = AccountingService(tenant)
                validation_result = accounting_service.validate_accounting_equation()
                
                total_validated += 1
                
                if not validation_result.get('is_balanced', False):
                    total_issues += 1
                    difference = validation_result.get('difference', 0)
                    logger.warning(f"Accounting equation not balanced for tenant {tenant.schema_name}. "
                                 f"Difference: {difference}")
                
            except Exception as e:
                logger.error(f"Error validating tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Accounting equation validation completed. Validated: {total_validated}, Issues: {total_issues}")
        return {
            'success': True,
            'total_validated': total_validated,
            'total_issues': total_issues
        }
        
    except Exception as e:
        logger.error(f"Error in validate_accounting_equation task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_orphaned_records():
    """Clean up orphaned records and fix referential integrity issues"""
    try:
        from ..models import JournalEntryLine, InvoiceItem, BillItem, PaymentApplication
        from apps.core.models import Tenant
        
        total_cleaned = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Clean up orphaned journal entry lines
                orphaned_lines = JournalEntryLine.objects.filter(
                    tenant=tenant,
                    journal_entry__isnull=True
                )
                
                if orphaned_lines.exists():
                    orphaned_lines.delete()
                    total_cleaned += orphaned_lines.count()
                
                # Clean up orphaned invoice items
                orphaned_invoice_items = InvoiceItem.objects.filter(
                    tenant=tenant,
                    invoice__isnull=True
                )
                
                if orphaned_invoice_items.exists():
                    orphaned_invoice_items.delete()
                    total_cleaned += orphaned_invoice_items.count()
                
                # Clean up orphaned bill items
                orphaned_bill_items = BillItem.objects.filter(
                    tenant=tenant,
                    bill__isnull=True
                )
                
                if orphaned_bill_items.exists():
                    orphaned_bill_items.delete()
                    total_cleaned += orphaned_bill_items.count()
                
                # Clean up orphaned payment applications
                orphaned_applications = PaymentApplication.objects.filter(
                    tenant=tenant,
                    payment__isnull=True
                )
                
                if orphaned_applications.exists():
                    orphaned_applications.delete()
                    total_cleaned += orphaned_applications.count()
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Orphaned records cleanup completed. Total cleaned: {total_cleaned}")
        return {'success': True, 'total_cleaned': total_cleaned}
        
    except Exception as e:
        logger.error(f"Error in cleanup_orphaned_records task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def optimize_database():
    """Run database optimization tasks"""
    try:
        from django.db import connection
        from apps.core.models import Tenant
        
        total_optimized = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                with connection.cursor() as cursor:
                    # Analyze tables for better query planning
                    cursor.execute("ANALYZE;")
                    total_optimized += 1
                    
            except Exception as e:
                logger.error(f"Error optimizing tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Database optimization completed for {total_optimized} tenants")
        return {'success': True, 'total_optimized': total_optimized}
        
    except Exception as e:
        logger.error(f"Error in optimize_database task: {str(e)}")
        return {'success': False, 'error': str(e)}
