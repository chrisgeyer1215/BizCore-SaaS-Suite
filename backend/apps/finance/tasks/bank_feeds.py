"""
Finance Bank Feeds Tasks
Celery tasks for bank feed synchronization
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Count

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def sync_bank_feeds(self, tenant_id: int = None):
    """Sync bank feeds for all tenants or specific tenant"""
    try:
        from ..models import BankAccount
        from apps.core.models import Tenant
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()
        
        total_synced = 0
        total_errors = 0
        
        for tenant in tenants:
            try:
                tenant.activate()
                
                # Get bank accounts with active feeds
                bank_accounts = BankAccount.objects.filter(
                    tenant=tenant,
                    has_bank_feed=True,
                    is_active=True
                )
                
                for account in bank_accounts:
                    try:
                        synced, errors = _sync_bank_account_feed(account)
                        total_synced += synced
                        total_errors += errors
                        
                    except Exception as e:
                        logger.error(f"Error syncing account {account.id}: {str(e)}")
                        total_errors += 1
                        continue
                
            except Exception as e:
                logger.error(f"Error syncing tenant {tenant.schema_name}: {str(e)}")
                total_errors += 1
                continue
        
        logger.info(f"Bank feed sync completed. Synced: {total_synced}, Errors: {total_errors}")
        return {
            'success': True,
            'total_synced': total_synced,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"Error in sync_bank_feeds task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _sync_bank_account_feed(bank_account) -> tuple:
    """Sync bank feed for a specific account"""
    from ..models import BankTransaction, BankStatement
    
    synced = 0
    errors = 0
    
    try:
        # Get feed data (implementation depends on bank integration)
        feed_data = _get_bank_feed_data(bank_account)
        
        if not feed_data:
            return 0, 0
        
        # Process transactions
        for transaction_data in feed_data.get('transactions', []):
            try:
                with transaction.atomic():
                    # Check if transaction already exists
                    existing = BankTransaction.objects.filter(
                        tenant=bank_account.tenant,
                        bank_account=bank_account,
                        external_id=transaction_data.get('external_id')
                    ).first()
                    
                    if not existing:
                        # Create new transaction
                        _create_bank_transaction(bank_account, transaction_data)
                        synced += 1
                    else:
                        # Update existing transaction if needed
                        if _should_update_transaction(existing, transaction_data):
                            _update_bank_transaction(existing, transaction_data)
                            synced += 1
                
            except Exception as e:
                logger.error(f"Error processing transaction: {str(e)}")
                errors += 1
                continue
        
        # Update last sync time
        bank_account.last_feed_sync = timezone.now()
        bank_account.save()
        
    except Exception as e:
        logger.error(f"Error syncing bank account {bank_account.id}: {str(e)}")
        errors += 1
    
    return synced, errors


def _get_bank_feed_data(bank_account):
    """Get bank feed data from external source"""
    # This would integrate with your bank's API
    # For now, return mock data
    return {
        'transactions': [
            {
                'external_id': f"TXN_{bank_account.id}_{timezone.now().timestamp()}",
                'transaction_date': date.today(),
                'description': 'Sample transaction',
                'amount': Decimal('100.00'),
                'type': 'DEBIT'
            }
        ]
    }


def _create_bank_transaction(bank_account, transaction_data):
    """Create new bank transaction from feed data"""
    from ..models import BankTransaction
    
    BankTransaction.objects.create(
        tenant=bank_account.tenant,
        bank_account=bank_account,
        external_id=transaction_data.get('external_id'),
        transaction_date=transaction_data.get('transaction_date'),
        description=transaction_data.get('description'),
        amount=transaction_data.get('amount'),
        transaction_type=transaction_data.get('type'),
        status='PENDING'
    )


def _should_update_transaction(existing_transaction, transaction_data):
    """Check if existing transaction should be updated"""
    # Update if amount or description changed
    return (existing_transaction.amount != transaction_data.get('amount') or
            existing_transaction.description != transaction_data.get('description'))


def _update_bank_transaction(existing_transaction, transaction_data):
    """Update existing bank transaction"""
    existing_transaction.amount = transaction_data.get('amount')
    existing_transaction.description = transaction_data.get('description')
    existing_transaction.save()


@shared_task
def cleanup_old_bank_transactions():
    """Clean up old bank transactions based on retention policy"""
    try:
        from ..models import BankTransaction
        from apps.core.models import Tenant
        
        # Default retention: 7 years
        cutoff_date = date.today() - timedelta(days=7*365)
        total_cleaned = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Find old transactions
                old_transactions = BankTransaction.objects.filter(
                    tenant=tenant,
                    transaction_date__lt=cutoff_date,
                    status='RECONCILED'
                )
                
                # Archive instead of deleting
                for transaction in old_transactions:
                    transaction.notes = f"ARCHIVED - {transaction.notes or ''}"
                    transaction.is_archived = True
                    transaction.save()
                    total_cleaned += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {total_cleaned} old bank transactions")
        return {'success': True, 'cleaned_up': total_cleaned}
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_bank_transactions task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def validate_bank_feed_integrity():
    """Validate integrity of bank feed data"""
    try:
        from ..models import BankTransaction, BankAccount
        from apps.core.models import Tenant
        
        total_issues = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Check for duplicate external IDs
                duplicates = BankTransaction.objects.filter(
                    tenant=tenant
                ).values('external_id').annotate(
                    count=Count('id')
                ).filter(count__gt=1)
                
                if duplicates.exists():
                    logger.warning(f"Found {duplicates.count()} duplicate external IDs in tenant {tenant.schema_name}")
                    total_issues += duplicates.count()
                
                # Check for transactions without external IDs
                missing_external_id = BankTransaction.objects.filter(
                    tenant=tenant,
                    external_id__isnull=True
                ).count()
                
                if missing_external_id > 0:
                    logger.warning(f"Found {missing_external_id} transactions without external IDs in tenant {tenant.schema_name}")
                    total_issues += missing_external_id
                
            except Exception as e:
                logger.error(f"Error validating tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Bank feed integrity check completed. Issues found: {total_issues}")
        return {'success': True, 'issues_found': total_issues}
        
    except Exception as e:
        logger.error(f"Error in validate_bank_feed_integrity task: {str(e)}")
        return {'success': False, 'error': str(e)}
