# backend/apps/finance/management/commands/cleanup_old_reconciliations.py

"""
Cleanup Old Reconciliations
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.finance.models import BankReconciliation, BankStatement
from datetime import timedelta


class Command(BaseCommand):
    """Cleanup old reconciliation data"""
    
    help = 'Cleanup old reconciliation data to save space'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete reconciliations older than this many days'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=options['days'])
        
        # Find old reconciliations
        old_reconciliations = BankReconciliation.objects.filter(
            reconciliation_date__lt=cutoff_date.date(),
            status='COMPLETED'
        )
        
        # Find old bank statements
        old_statements = BankStatement.objects.filter(
            statement_date__lt=cutoff_date.date(),
            is_reconciled=True
        )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {old_reconciliations.count()} "
                    f"reconciliations and {old_statements.count()} bank statements"
                )
            )
        else:
            # Delete old data
            reconciliations_deleted = old_reconciliations.count()
            statements_deleted = old_statements.count()
            
            old_reconciliations.delete()
            old_statements.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {reconciliations_deleted} old reconciliations "
                    f"and {statements_deleted} old bank statements"
                )
            )