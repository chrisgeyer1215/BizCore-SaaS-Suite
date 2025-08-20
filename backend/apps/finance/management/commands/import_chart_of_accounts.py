# backend/apps/finance/management/commands/import_chart_of_accounts.py

"""
Import Chart of Accounts from Templates
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import Tenant
from apps.finance.models import Account, AccountCategory, Currency
import json
import os


class Command(BaseCommand):
    """Import chart of accounts from template"""
    
    help = 'Import chart of accounts from predefined templates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            required=True,
            help='Tenant schema name'
        )
        parser.add_argument(
            '--template',
            type=str,
            default='standard',
            choices=['standard', 'retail', 'manufacturing', 'service', 'nonprofit'],
            help='Chart of accounts template'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force import even if accounts exist'
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name=options['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant '{options['tenant']}' does not exist")
        
        template_name = options['template']
        force = options['force']
        
        # Check if accounts already exist
        if not force and Account.objects.filter(tenant=tenant).exists():
            raise CommandError("Accounts already exist. Use --force to overwrite.")
        
        # Load template
        template_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 'fixtures', 
            f'chart_of_accounts_{template_name}.json'
        )
        
        if not os.path.exists(template_path):
            raise CommandError(f"Template '{template_name}' not found")
        
        with open(template_path, 'r') as f:
            template_data = json.load(f)
        
        with transaction.atomic():
            # Clear existing accounts if force
            if force:
                Account.objects.filter(tenant=tenant).delete()
                AccountCategory.objects.filter(tenant=tenant).delete()
            
            # Create categories first
            categories_map = {}
            for category_data in template_data.get('categories', []):
                category = AccountCategory.objects.create(
                    tenant=tenant,
                    **category_data
                )
                categories_map[category_data['name']] = category
            
            # Get base currency
            base_currency = Currency.objects.filter(
                tenant=tenant, 
                is_base_currency=True
            ).first()
            
            # Create accounts
            accounts_created = 0
            for account_data in template_data.get('accounts', []):
                # Map category name to object
                if 'category' in account_data:
                    category_name = account_data.pop('category')
                    account_data['category'] = categories_map.get(category_name)
                
                # Set currency
                account_data['currency'] = base_currency
                account_data['tenant'] = tenant
                
                Account.objects.create(**account_data)
                accounts_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported {accounts_created} accounts "
                f"from '{template_name}' template for tenant '{tenant.name}'"
            )
        )