# backend/apps/finance/management/commands/sync_bank_feeds.py

"""
Sync Bank Feeds
"""

from django.core.management.base import BaseCommand
from apps.finance.models import BankAccount
from apps.finance.services.bank_feeds import BankFeedService


class Command(BaseCommand):
    """Sync bank feeds"""
    
    help = 'Sync bank transactions from external feeds'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Process for specific tenant only'
        )
        parser.add_argument(
            '--bank-account',
            type=int,
            help='Process specific bank account only'
        )

    def handle(self, *args, **options):
        filters = {'enable_bank_feeds': True}
        
        if options['tenant']:
            filters['account__tenant__schema_name'] = options['tenant']
        
        if options['bank_account']:
            filters['id'] = options['bank_account']
        
        bank_accounts = BankAccount.objects.filter(**filters)
        
        total_synced = 0
        
        for bank_account in bank_accounts:
            service = BankFeedService(bank_account.account.tenant)
            
            try:
                result = service.sync_bank_feed(bank_account)
                transactions_synced = result.get('transactions_synced', 0)
                total_synced += transactions_synced
                
                self.stdout.write(
                    f"Synced {transactions_synced} transactions for "
                    f"{bank_account.bank_name} - {bank_account.account_number}"
                )
                
            except Exception as e:
                self.stderr.write(
                    f"Error syncing {bank_account.bank_name} - "
                    f"{bank_account.account_number}: {str(e)}"
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Total transactions synced: {total_synced}")
        )