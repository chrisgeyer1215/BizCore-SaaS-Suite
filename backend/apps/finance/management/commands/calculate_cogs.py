# backend/apps/finance/management/commands/calculate_cogs.py

"""
Calculate Cost of Goods Sold
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import Tenant
from apps.finance.services.cogs import COGSService
from datetime import date, datetime


class Command(BaseCommand):
    """Calculate COGS for a period"""
    
    help = 'Calculate Cost of Goods Sold for invoices'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            required=True,
            help='Tenant schema name'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate existing COGS entries'
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name=options['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant '{options['tenant']}' does not exist")
        
        # Parse dates
        start_date = None
        end_date = None
        
        if options['start_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
        
        if options['end_date']:
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        
        service = COGSService(tenant)
        
        try:
            result = service.calculate_period_cogs(
                start_date=start_date,
                end_date=end_date,
                recalculate=options['recalculate']
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"COGS calculation completed:\n"
                    f"- Invoices processed: {result['invoices_processed']}\n"
                    f"- COGS entries created: {result['cogs_entries_created']}\n"
                    f"- Total COGS amount: ${result['total_cogs_amount']:,.2f}"
                )
            )
            
        except Exception as e:
            raise CommandError(f"Error calculating COGS: {str(e)}")