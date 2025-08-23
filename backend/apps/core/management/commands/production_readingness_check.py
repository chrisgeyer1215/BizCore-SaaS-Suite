# backend/apps/core/management/commands/production_readiness_check.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from django.core.cache import cache
import os
import requests

class Command(BaseCommand):
    help = 'Run production readiness checklist for SaaS-AICE CRM'

    def handle(self, *args, **options):
        
        self.stdout.write(
            self.style.SUCCESS('🚀 SaaS-AICE CRM PRODUCTION READINESS CHECK')
        )
        self.stdout.write('='*60)
        
        checks = [
            self.check_database_connection,
            self.check_cache_connection,
            self.check_environment_variables,
            self.check_security_settings,
            self.check_api_endpoints,
            self.check_static_files,
            self.check_email_configuration,
            self.check_celery_configuration,
            self.check_tenant_configuration,
            self.check_api_documentation,
        ]
        
        passed = 0
        failed = 0
        
        for check in checks:
            try:
                result = check()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ {check.__name__}: ERROR - {str(e)}')
                )
                failed += 1
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'✅ PASSED: {passed}')
        self.stdout.write(f'❌ FAILED: {failed}')
        
        if failed == 0:
            self.stdout.write(
                self.style.SUCCESS('\n🎉 SYSTEM IS PRODUCTION READY!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'\n⚠️  {failed} checks failed. Review before production deployment.')
            )

    def check_database_connection(self):
        """Check database connectivity."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            self.stdout.write(self.style.SUCCESS('✅ Database connection: OK'))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Database connection: FAILED - {str(e)}'))
            return False

    def check_cache_connection(self):
        """Check cache connectivity."""
        try:
            cache.set('test_key', 'test_value', 30)
            result = cache.get('test_key')
            
            if result == 'test_value':
                self.stdout.write(self.style.SUCCESS('✅ Cache connection: OK'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ Cache connection: FAILED - Unable to store/retrieve'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Cache connection: FAILED - {str(e)}'))
            return False

    def check_environment_variables(self):
        """Check required environment variables."""
        required_vars = [
            'SECRET_KEY',
            'DATABASE_URL',
            'REDIS_URL',
            'EMAIL_HOST_USER',
            'JWT_SECRET_KEY'
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if not missing:
            self.stdout.write(self.style.SUCCESS('✅ Environment variables: OK'))
            return True
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Environment variables: MISSING - {", ".join(missing)}')
            )
            return False

    def check_security_settings(self):
        """Check security configuration."""
        issues = []
        
        if settings.DEBUG:
            issues.append('DEBUG=True (should be False in production)')
        
        if settings.SECRET_KEY == 'your-secret-key-here':
            issues.append('SECRET_KEY not changed from default')
        
        if not settings.SECURE_SSL_REDIRECT:
            issues.append('SECURE_SSL_REDIRECT not enabled')
        
        if not issues:
            self.stdout.write(self.style.SUCCESS('✅ Security settings: OK'))
            return True
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Security settings: ISSUES - {"; ".join(issues)}')
            )
            return False

    def check_api_endpoints(self):
        """Check API endpoints accessibility."""
        try:
            from django.test import Client
            client = Client()
            
            # Check health endpoint
            response = client.get('/health/')
            
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('✅ API endpoints: OK'))
                return True
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ API endpoints: FAILED - Health check returned {response.status_code}')
                )
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ API endpoints: FAILED - {str(e)}'))
            return False

    def check_static_files(self):
        """Check static files configuration."""
        try:
            if settings.STATIC_ROOT and os.path.exists(settings.STATIC_ROOT):
                self.stdout.write(self.style.SUCCESS('✅ Static files: OK'))
                return True
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Static files: FAILED - STATIC_ROOT not configured or missing')
                )
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Static files: FAILED - {str(e)}'))
            return False

    def check_email_configuration(self):
        """Check email configuration."""
        try:
            from django.core.mail import get_connection
            connection = get_connection()
            
            # Just check if connection can be established
            if hasattr(connection, 'host') and connection.host:
                self.stdout.write(self.style.SUCCESS('✅ Email configuration: OK'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ Email configuration: FAILED - No SMTP host configured'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Email configuration: FAILED - {str(e)}'))
            return False

    def check_celery_configuration(self):
        """Check Celery configuration."""
        try:
            if hasattr(settings, 'CELERY_BROKER_URL') and settings.CELERY_BROKER_URL:
                self.stdout.write(self.style.SUCCESS('✅ Celery configuration: OK'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ Celery configuration: FAILED - CELERY_BROKER_URL not set'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Celery configuration: FAILED - {str(e)}'))
            return False

    def check_tenant_configuration(self):
        """Check tenant configuration."""
        try:
            from django_tenants.utils import get_tenant_model
            TenantModel = get_tenant_model()
            
            if TenantModel:
                self.stdout.write(self.style.SUCCESS('✅ Tenant configuration: OK'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ Tenant configuration: FAILED'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Tenant configuration: FAILED - {str(e)}'))
            return False

    def check_api_documentation(self):
        """Check API documentation accessibility."""
        try:
            from django.test import Client
            client = Client()
            
            response = client.get('/api/docs/')
            
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('✅ API documentation: OK'))
                return True
            else:
                self.stdout.write(self.style.ERROR('❌ API documentation: FAILED - Not accessible'))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ API documentation: FAILED - {str(e)}'))
            return False