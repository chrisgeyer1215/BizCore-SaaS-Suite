"""
Management command to cleanup old inventory data
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.tenants.models import Tenant
from apps.inventory.models import (
    StockMovement, InventoryAlert, InventoryReport, StockValuationLayer
)


class Command(BaseCommand):
    help = 'Cleanup old inventory data based on retention policies'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Tenant ID to cleanup data for'
        )
        parser.add_argument(
            '--all-tenants',
            action='store_true',
            help='Cleanup data for all tenants'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--movements-days',
            type=int,
            default=365,
            help='Keep stock movements for this many days (default: 365)'
        )
        parser.add_argument(
            '--alerts-days',
            type=int,
            default=30,
            help='Keep resolved alerts for this many days (default: 30)'
        )
        parser.add_argument(
            '--reports-days',
            type=int,
            default=90,
            help='Keep old reports for this many days (default: 90)'
        )
    
    def handle(self, *args, **options):
        if options['all_tenants']:
            tenants = Tenant.objects.filter(is_active=True)
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
        
        is_dry_run = options['dry_run']
        
        if is_dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        total_deleted = 0
        
        for tenant in tenants:
            self.stdout.write(f'Processing tenant: {tenant.name}')
            
            # Cleanup old stock movements
            movements_cutoff = timezone.now() - timedelta(days=options['movements_days'])
            movements_query = StockMovement.objects.filter(
                tenant=tenant,
                created_at__lt=movements_cutoff
            )
            movements_count = movements_query.count()
            
            if movements_count > 0:
                if not is_dry_run:
                    movements_query.delete()
                self.stdout.write(f'  Stock movements: {movements_count} records')
                total_deleted += movements_count
            
            # Cleanup old resolved alerts
            alerts_cutoff = timezone.now() - timedelta(days=options['alerts_days'])
            alerts_query = InventoryAlert.objects.filter(
                tenant=tenant,
                status='RESOLVED',
                resolved_at__lt=alerts_cutoff
            )
            alerts_count = alerts_query.count()
            
            if alerts_count > 0:
                if not is_dry_run:
                    alerts_query.delete()
                self.stdout.write(f'  Resolved alerts: {alerts_count} records')
                total_deleted += alerts_count
            
            # Cleanup old reports
            reports_cutoff = timezone.now() - timedelta(days=options['reports_days'])
            reports_query = InventoryReport.objects.filter(
                tenant=tenant,
                created_at__lt=reports_cutoff
            )
            reports_count = reports_query.count()
            
            if reports_count > 0:
                if not is_dry_run:
                    reports_query.delete()
                self.stdout.write(f'  Old reports: {reports_count} records')
                total_deleted += reports_count
            
            # Cleanup consumed valuation layers
            consumed_layers_query = StockValuationLayer.objects.filter(
                tenant=tenant,
                is_fully_consumed=True,
                receipt_date__lt=movements_cutoff
            )
            consumed_count = consumed_layers_query.count()
            
            if consumed_count > 0:
                if not is_dry_run:
                    consumed_layers_query.delete()
                self.stdout.write(f'  Consumed valuation layers: {consumed_count} records')
                total_deleted += consumed_count
        
        action = 'Would delete' if is_dry_run else 'Deleted'
        self.stdout.write(
            self.style.SUCCESS(f'Cleanup completed! {action} {total_deleted} total records')
        )
