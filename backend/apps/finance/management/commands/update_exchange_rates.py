# backend/apps/finance/management/commands/update_exchange_rates.py

"""
Update Exchange Rates
"""

from django.core.management.base import BaseCommand
from apps.finance.models import Currency, ExchangeRate, FinanceSettings
from apps.finance.services.currency import CurrencyService
from datetime import date


class Command(BaseCommand):
    """Update exchange rates"""
    
    help = 'Update exchange rates from external sources'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Update for specific tenant only'
        )
        parser.add_argument(
            '--source',
            type=str,
            default='fixer.io',
            choices=['fixer.io', 'exchangerate-api.com', 'manual'],
            help='Exchange rate source'
        )

    def handle(self, *args, **options):
        filters = {'auto_update_exchange_rates': True}
        
        if options['tenant']:
            filters['tenant__schema_name'] = options['tenant']
        
        settings_list = FinanceSettings.objects.filter(**filters)
        
        total_updated = 0
        
        for settings in settings_list:
            service = CurrencyService(settings.tenant)
            
            try:
                result = service.update_exchange_rates(source=options['source'])
                rates_updated = result.get('rates_updated', 0)
                total_updated += rates_updated
                
                self.stdout.write(
                    f"Updated {rates_updated} exchange rates for tenant "
                    f"'{settings.tenant.name}'"
                )
                
            except Exception as e:
                self.stderr.write(
                    f"Error updating exchange rates for tenant "
                    f"'{settings.tenant.name}': {str(e)}"
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Total exchange rates updated: {total_updated}")
        )