"""
Management command to calculate ABC analysis for inventory
"""

from django.core.management.base import BaseCommand
from apps.tenants.models import Tenant
from apps.inventory_one.services import AnalyticsService


class Command(BaseCommand):
    help = 'Calculate ABC analysis for inventory products'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Tenant ID to calculate ABC analysis for'
        )
        parser.add_argument(
            '--all-tenants',
            action='store_true',
            help='Calculate ABC analysis for all tenants'
        )
    
    def handle(self, *args, **options):
        if options['all_tenants']:
            tenants = Tenant.objects.filter(is_active=True)
            self.stdout.write(f'Calculating ABC analysis for {tenants.count()} tenants...')
        elif options['tenant_id']:
            try:
                tenants = [Tenant.objects.get(id=options['tenant_id'])]
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Tenant with ID {options["tenant_id"]} does not exist')
                )
                return
        else:
            self.stdout.write(
                self.style.ERROR('Please provide either --tenant-id or --all-tenants')
            )
            return
        
        for tenant in tenants:
            self.stdout.write(f'Processing tenant: {tenant.name}')
            
            analytics = AnalyticsService(tenant)
            analytics.calculate_abc_analysis()
            analytics.calculate_turnover_rates()
            
            self.stdout.write(
                self.style.SUCCESS(f'ABC analysis completed for tenant: {tenant.name}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('ABC analysis calculation completed!')
        )
