from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, Domain

User = get_user_model()

class Command(BaseCommand):
    help = 'Create development tenant with sample data'
    
    def handle(self, *args, **options):
        # Create tenant
        tenant, created = Tenant.objects.get_or_create(
            schema_name="dev",
            defaults={
                'name': "Development Company",
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created tenant: {tenant.name}')
            )
        
        # Create domain
        domain, created = Domain.objects.get_or_create(
            domain="dev.localhost",
            defaults={
                'tenant': tenant,
                'is_primary': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created domain: {domain.domain}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Setup complete!')
        )
        self.stdout.write('Add to your hosts file:')
        self.stdout.write('127.0.0.1 dev.localhost')
        self.stdout.write('Then access: http://dev.localhost:8000/admin/')
