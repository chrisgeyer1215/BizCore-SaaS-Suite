# tenants/create_tenant.py

import os
import sys
import django
from django.core.management import execute_from_command_line
from django.db import transaction
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.core.models import Tenant, Domain, TenantSettings
from apps.auth.models import User, Membership


def create_tenant(
    name,
    slug=None,
    domain=None,
    admin_email=None,
    admin_password=None,
    plan='free',
    company_name=None
):
    """
    Create a new tenant with admin user
    """
    try:
        with transaction.atomic():
            # Create tenant
            tenant_data = {
                'name': name,
                'plan': plan,
                'status': 'trial',
                'trial_end_date': datetime.now() + timedelta(days=30),
            }
            
            if slug:
                tenant_data['slug'] = slug
            if company_name:
                tenant_data['company_name'] = company_name
            
            tenant = Tenant.objects.create(**tenant_data)
            
            print(f"✓ Created tenant: {tenant.name} (ID: {tenant.id})")
            
            # Create domain
            domain_name = domain or f"{tenant.slug}.localhost"
            domain_obj = Domain.objects.create(
                domain=domain_name,
                tenant=tenant,
                is_primary=True
            )
            
            print(f"✓ Created domain: {domain_name}")
            
            # Create tenant settings
            settings = TenantSettings.objects.create(tenant=tenant)
            print(f"✓ Created tenant settings")
            
            # Create admin user if email provided
            if admin_email:
                # Check if user exists
                try:
                    admin_user = User.objects.get(email=admin_email)
                    print(f"✓ Found existing user: {admin_email}")
                except User.DoesNotExist:
                    # Create new user
                    admin_user = User.objects.create_user(
                        email=admin_email,
                        username=admin_email,
                        password=admin_password or 'changeMe123!',
                        first_name='Admin',
                        last_name='User',
                        user_type='tenant_admin',
                        email_verified=True
                    )
                    print(f"✓ Created admin user: {admin_email}")
                
                # Create membership
                membership = Membership.objects.create(
                    user=admin_user,
                    tenant_id=tenant.id,
                    role='owner',
                    status='active'
                )
                print(f"✓ Created admin membership")
            
            # Create tenant schema
            tenant.create_schema(check_if_exists=True)
            print(f"✓ Created tenant schema: {tenant.schema_name}")
            
            # Run migrations for tenant
            execute_from_command_line([
                'manage.py', 'migrate_schemas', '--schema', tenant.schema_name
            ])
            print(f"✓ Applied migrations to tenant schema")
            
            return tenant
            
    except Exception as e:
        print(f"✗ Error creating tenant: {e}")
        raise


def delete_tenant(tenant_id_or_slug):
    """
    Delete a tenant and its schema
    """
    try:
        # Get tenant
        if str(tenant_id_or_slug).isdigit():
            tenant = Tenant.objects.get(id=tenant_id_or_slug)
        else:
            tenant = Tenant.objects.get(slug=tenant_id_or_slug)
        
        schema_name = tenant.schema_name
        
        with transaction.atomic():
            # Delete tenant (cascades to domains and settings)
            tenant.delete()
            print(f"✓ Deleted tenant: {tenant.name}")
            
            # Drop schema
            tenant.drop_schema()
            print(f"✓ Dropped schema: {schema_name}")
        
    except Tenant.DoesNotExist:
        print(f"✗ Tenant not found: {tenant_id_or_slug}")
    except Exception as e:
        print(f"✗ Error deleting tenant: {e}")
        raise


def list_tenants():
    """
    List all tenants
    """
    tenants = Tenant.objects.all().order_by('created_at')
    
    print(f"\n{'ID':<5} {'Name':<20} {'Slug':<15} {'Plan':<12} {'Status':<10} {'Created':<12}")
    print("-" * 80)
    
    for tenant in tenants:
        print(f"{tenant.id:<5} {tenant.name[:19]:<20} {tenant.slug:<15} {tenant.plan:<12} {tenant.status:<10} {tenant.created_at.strftime('%Y-%m-%d'):<12}")
    
    print(f"\nTotal tenants: {tenants.count()}")


def main():
    """Main script function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_tenant.py create <name> [options]")
        print("  python create_tenant.py delete <tenant_id_or_slug>")
        print("  python create_tenant.py list")
        print("\nCreate options:")
        print("  --slug <slug>")
        print("  --domain <domain>")
        print("  --admin-email <email>")
        print("  --admin-password <password>")
        print("  --plan <plan>")
        print("  --company <company_name>")
        return
    
    command = sys.argv[1]
    
    if command == 'create':
        if len(sys.argv) < 3:
            print("Error: Tenant name is required")
            return
        
        name = sys.argv[2]
        
        # Parse options
        options = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith('--'):
                option = sys.argv[i][2:].replace('-', '_')
                if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('--'):
                    options[option] = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        create_tenant(name, **options)
        
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("Error: Tenant ID or slug is required")
            return
        
        tenant_id_or_slug = sys.argv[2]
        
        # Confirm deletion
        confirm = input(f"Are you sure you want to delete tenant '{tenant_id_or_slug}'? [y/N]: ")
        if confirm.lower() == 'y':
            delete_tenant(tenant_id_or_slug)
        else:
            print("Cancelled")
    
    elif command == 'list':
        list_tenants()
    
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()