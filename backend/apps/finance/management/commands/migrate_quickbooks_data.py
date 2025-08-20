# backend/apps/finance/management/commands/migrate_quickbooks_data.py

"""
Migrate QuickBooks Data
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import Tenant
from apps.finance.services.imports import QuickBooksImportService
import json


class Command(BaseCommand):
    """Migrate data from QuickBooks"""
    
    help = 'Import data from QuickBooks export file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            required=True,
            help='Tenant schema name'
        )
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to QuickBooks export file'
        )
        parser.add_argument(
            '--data-type',
            type=str,
            required=True,
            choices=['chart_of_accounts', 'customers', 'vendors', 'items', 'transactions'],
            help='Type of data to import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate import without saving data'
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name=options['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant '{options['tenant']}' does not exist")
        
        import_file = options['file']
        data_type = options['data_type']
        dry_run = options['dry_run']
        
        service = QuickBooksImportService(tenant)
        
        try:
            with open(import_file, 'r') as f:
                if import_file.endswith('.json'):
                    data = json.load(f)
                elif import_file.endswith('.csv'):
                    import csv
                    data = list(csv.DictReader(f))
                else:
                    raise CommandError("Unsupported file format. Use JSON or CSV.")
            
            if dry_run:
                result = service.validate_import(data_type, data)
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN: Validation result:\n"
                        f"Valid records: {result['valid_count']}\n"
                        f"Invalid records: {result['invalid_count']}\n"
                        f"Errors: {result.get('errors', [])}"
                    )
                )
            else:
                with transaction.atomic():
                    result = service.import_data(data_type, data)
                    
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Import completed:\n"
                        f"Records imported: {result['imported_count']}\n"
                        f"Records skipped: {result['skipped_count']}\n"
                        f"Errors: {result['error_count']}"
                    )
                )
                
        except Exception as e:
            raise CommandError(f"Error importing data: {str(e)}")