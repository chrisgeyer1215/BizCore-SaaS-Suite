# tenants/demo_tenant.py

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.db import transaction
from apps.core.models import Tenant, Domain, TenantSettings
from apps.auth.models import User, Membership, Invitation


def create_demo_tenant():
    """
    Create a demo tenant with sample data
    """
    try:
        with transaction.atomic():
            # Create demo tenant
            tenant = Tenant.objects.create(
                name="ACME Corporation",
                slug="acme-demo",
                description="Demo tenant for ACME Corporation",
                plan="professional",
                status="trial",
                trial_end_date=datetime.now() + timedelta(days=30),
                company_name="ACME Corporation",
                company_address="123 Business Street, Suite 100, Business City, BC 12345",
                contact_email="admin@acme-demo.com",
                contact_phone="+1 (555) 123-4567",
                timezone="America/New_York",
                currency="USD",
                max_users=50,
                max_storage_gb=10,
                max_api_calls_per_month=10000,
                features={
                    "crm": True,
                    "inventory": True,
                    "ecommerce": True,
                    "finance": True,
                    "ai_analytics": True,
                    "custom_reports": True,
                    "api_access": True,
                    "sso": False,
                    "white_label": False
                }
            )
            
            print(f"✓ Created demo tenant: {tenant.name}")
            
            # Create domain
            domain = Domain.objects.create(
                domain="acme-demo.localhost",
                tenant=tenant,
                is_primary=True,
                domain_type="subdomain",
                is_verified=True
            )
            
            print(f"✓ Created domain: {domain.domain}")
            
            # Create tenant settings
            settings = TenantSettings.objects.create(
                tenant=tenant,
                primary_color="#2563EB",
                secondary_color="#64748B",
                business_hours_start="09:00:00",
                business_hours_end="17:00:00",
                business_days=[1, 2, 3, 4, 5],  # Monday to Friday
                email_notifications=True,
                sms_notifications=False,
                push_notifications=True,
                api_rate_limit=1000,
                integrations={
                    "stripe": {"enabled": False},
                    "mailgun": {"enabled": False},
                    "slack": {"enabled": False},
                    "zapier": {"enabled": True}
                }
            )
            
            print(f"✓ Created tenant settings")
            
            # Create admin user
            admin_user = User.objects.create_user(
                email="admin@acme-demo.com",
                username="admin@acme-demo.com",
                password="DemoAdmin123!",
                first_name="John",
                last_name="Administrator",
                user_type="tenant_admin",
                phone="+1 (555) 123-4567",
                bio="Administrator of ACME Corporation demo tenant",
                timezone="America/New_York",
                language="en",
                theme="light",
                email_verified=True,
                phone_verified=True,
                is_active=True
            )
            
            print(f"✓ Created admin user: {admin_user.email}")
            
            # Create admin membership
            admin_membership = Membership.objects.create(
                user=admin_user,
                tenant_id=tenant.id,
                role="owner",
                status="active",
                permissions={
                    "create_user": True,
                    "edit_user": True,
                    "delete_user": True,
                    "view_reports": True,
                    "manage_settings": True,
                    "manage_billing": True,
                    "export_data": True
                }
            )
            
            print(f"✓ Created admin membership")
            
            # Create sample users
            sample_users = [
                {
                    "email": "manager@acme-demo.com",
                    "username": "manager@acme-demo.com",
                    "password": "DemoManager123!",
                    "first_name": "Sarah",
                    "last_name": "Manager",
                    "role": "manager",
                    "phone": "+1 (555) 234-5678"
                },
                {
                    "email": "sales@acme-demo.com",
                    "username": "sales@acme-demo.com",
                    "password": "DemoSales123!",
                    "first_name": "Mike",
                    "last_name": "Rodriguez",
                    "role": "employee",
                    "phone": "+1 (555) 345-6789"
                },
                {
                    "email": "support@acme-demo.com",
                    "username": "support@acme-demo.com",
                    "password": "DemoSupport123!",
                    "first_name": "Emily",
                    "last_name": "Chen",
                    "role": "employee",
                    "phone": "+1 (555) 456-7890"
                }
            ]
            
            for user_data in sample_users:
                role = user_data.pop("role")
                
                user = User.objects.create_user(
                    **user_data,
                    user_type="user",
                    timezone="America/New_York",
                    language="en",
                    theme="light",
                    email_verified=True,
                    is_active=True
                )
                
                # Create membership
                membership = Membership.objects.create(
                    user=user,
                    tenant_id=tenant.id,
                    role=role,
                    status="active",
                    permissions={
                        "view_data": True,
                        "edit_own_data": True,
                        "create_user": role == "manager",
                        "edit_user": role == "manager",
                        "view_reports": role == "manager"
                    }
                )
                
                print(f"✓ Created user: {user.email} ({role})")
            
            # Create pending invitations
            pending_invitations = [
                {
                    "email": "finance@acme-demo.com",
                    "role": "employee"
                },
                {
                    "email": "hr@acme-demo.com",
                    "role": "manager"
                }
            ]
            
            for inv_data in pending_invitations:
                invitation = Invitation.objects.create(
                    email=inv_data["email"],
                    tenant_id=tenant.id,
                    role=inv_data["role"],
                    invited_by=admin_user,
                    expires_at=datetime.now() + timedelta(days=7)
                )
                
                print(f"✓ Created pending invitation: {invitation.email}")
            
            # Create tenant schema
            tenant.create_schema(check_if_exists=True)
            print(f"✓ Created tenant schema: {tenant.schema_name}")
            
            # Run migrations for tenant
            from django.core.management import execute_from_command_line
            execute_from_command_line([
                'manage.py', 'migrate_schemas', '--schema', tenant.schema_name
            ])
            print(f"✓ Applied migrations to tenant schema")
            
            print(f"\n🎉 Demo tenant created successfully!")
            print(f"Tenant: {tenant.name} (ID: {tenant.id})")
            print(f"Domain: {domain.domain}")
            print(f"Admin Login: {admin_user.email} / DemoAdmin123!")
            print(f"Schema: {tenant.schema_name}")
            
            return tenant
            
    except Exception as e:
        print(f"✗ Error creating demo tenant: {e}")
        raise


def delete_demo_tenant():
    """
    Delete the demo tenant
    """
    try:
        tenant = Tenant.objects.get(slug="acme-demo")
        
        # Confirm deletion
        confirm = input(f"Are you sure you want to delete demo tenant '{tenant.name}'? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return
        
        schema_name = tenant.schema_name
        
        with transaction.atomic():
            # Delete associated users (only if they don't have other memberships)
            demo_emails = [
                "admin@acme-demo.com",
                "manager@acme-demo.com", 
                "sales@acme-demo.com",
                "support@acme-demo.com"
            ]
            
            for email in demo_emails:
                try:
                    user = User.objects.get(email=email)
                    # Check if user has other active memberships
                    other_memberships = user.memberships.filter(
                        is_active=True,
                        status="active"
                    ).exclude(tenant_id=tenant.id)
                    
                    if not other_memberships.exists():
                        user.delete()
                        print(f"✓ Deleted user: {email}")
                    else:
                        print(f"→ Kept user (has other memberships): {email}")
                        
                except User.DoesNotExist:
                    pass
            
            # Delete tenant (cascades to domains, settings, memberships, invitations)
            tenant.delete()
            print(f"✓ Deleted tenant: {tenant.name}")
            
            # Drop schema
            tenant.drop_schema()
            print(f"✓ Dropped schema: {schema_name}")
            
            print(f"\n🗑️ Demo tenant deleted successfully!")
        
    except Tenant.DoesNotExist:
        print("✗ Demo tenant not found")
    except Exception as e:
        print(f"✗ Error deleting demo tenant: {e}")
        raise


def reset_demo_tenant():
    """
    Reset demo tenant by deleting and recreating
    """
    print("Resetting demo tenant...")
    
    # Delete existing demo tenant if it exists
    try:
        delete_demo_tenant()
    except:
        pass
    
    # Create new demo tenant
    create_demo_tenant()


def show_demo_info():
    """
    Show demo tenant information
    """
    try:
        tenant = Tenant.objects.get(slug="acme-demo")
        
        print(f"\n📊 Demo Tenant Information")
        print(f"{'='*50}")
        print(f"Name: {tenant.name}")
        print(f"Slug: {tenant.slug}")
        print(f"Status: {tenant.status}")
        print(f"Plan: {tenant.plan}")
        print(f"Schema: {tenant.schema_name}")
        print(f"Created: {tenant.created_at}")
        
        if tenant.trial_end_date:
            print(f"Trial Ends: {tenant.trial_end_date}")
        
        # Show domains
        print(f"\n🌐 Domains:")
        for domain in tenant.domains.all():
            print(f"  • {domain.domain} ({'Primary' if domain.is_primary else 'Secondary'})")
        
        # Show users
        print(f"\n👥 Users:")
        memberships = Membership.objects.filter(tenant_id=tenant.id, is_active=True)
        for membership in memberships:
            print(f"  • {membership.user.email} ({membership.role})")
        
        # Show pending invitations
        print(f"\n📧 Pending Invitations:")
        invitations = Invitation.objects.filter(tenant_id=tenant.id, status="pending")
        for invitation in invitations:
            print(f"  • {invitation.email} ({invitation.role})")
        
        # Show features
        print(f"\n🚀 Features:")
        for feature, enabled in tenant.features.items():
            status = "✓" if enabled else "✗"
            print(f"  {status} {feature.replace('_', ' ').title()}")
        
    except Tenant.DoesNotExist:
        print("✗ Demo tenant not found")


def main():
    """Main script function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python demo_tenant.py create    - Create demo tenant")
        print("  python demo_tenant.py delete    - Delete demo tenant")
        print("  python demo_tenant.py reset     - Reset demo tenant")
        print("  python demo_tenant.py info      - Show demo tenant info")
        return
    
    command = sys.argv[1]
    
    if command == 'create':
        create_demo_tenant()
    elif command == 'delete':
        delete_demo_tenant()
    elif command == 'reset':
        reset_demo_tenant()
    elif command == 'info':
        show_demo_info()
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()