from django.core.management.base import BaseCommand
from tenants.models import Tenant, Domain  # Notice: tenants.models, not apps.tenants.models

class Command(BaseCommand):
    help = 'Create development tenant'
    
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
                self.style.SUCCESS(f'✅ Created tenant: {tenant.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Tenant already exists: {tenant.name}')
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
                self.style.SUCCESS(f'✅ Created domain: {domain.domain}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Domain already exists: {domain.domain}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('🎯 Setup complete!')
        )
        self.stdout.write('Now you can access: http://dev.localhost:8000/admin/')
