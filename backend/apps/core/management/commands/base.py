# backend/tests/integration/base.py
import json
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import get_tenant_model, schema_context

from apps.auth.models import Tenant, Domain
from apps.crm.models import Account, Lead, Opportunity, Activity

User = get_user_model()
TenantModel = get_tenant_model()

class BaseIntegrationTest(TenantTestCase):
    """Base class for all integration tests with tenant support."""
    
    @classmethod
    def setUpClass(cls):
        """Set up tenant for the test class."""
        super().setUpClass()
        
        # Create test tenant
        cls.tenant = TenantModel.objects.create(
            name='Test Tenant',
            schema_name='test_tenant',
            status='active',
            plan='enterprise'
        )
        
        # Create domain for tenant
        cls.domain = Domain.objects.create(
            domain='test-tenant.localhost',
            tenant=cls.tenant,
            is_primary=True
        )
        
        # Set tenant context
        cls.tenant_client = TenantClient(cls.tenant)

    def setUp(self):
        """Set up test data for each test method."""
        super().setUp()
        
        with schema_context(self.tenant.schema_name):
            # Create test user
            self.user = User.objects.create_user(
                email='test@test.com',
                password='testpass123',
                first_name='Test',
                last_name='User',
                is_active=True
            )
            
            # Create API client with authentication
            self.client = APIClient()
            self.client.force_authenticate(user=self.user)
            
            # Create JWT token
            refresh = RefreshToken.for_user(self.user)
            self.access_token = str(refresh.access_token)
            self.refresh_token = str(refresh)
            
            # Set authentication header
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {self.access_token}',
                HTTP_HOST='test-tenant.localhost'
            )

    def create_test_account(self, **kwargs):
        """Create a test account with default values."""
        defaults = {
            'name': 'Test Account',
            'email': 'account@test.com',
            'phone': '+1-555-0123',
            'industry': 'technology',
            'annual_revenue': 1000000,
            'employees': 50,
            'status': 'active'
        }
        defaults.update(kwargs)
        return Account.objects.create(**defaults)

    def create_test_lead(self, **kwargs):
        """Create a test lead with default values."""
        defaults = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@test.com',
            'company': 'Test Company',
            'title': 'Manager',
            'phone': '+1-555-0124',
            'status': 'new',
            'source': 'website'
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)

    def create_test_opportunity(self, account=None, **kwargs):
        """Create a test opportunity with default values."""
        if account is None:
            account = self.create_test_account()
            
        defaults = {
            'name': 'Test Opportunity',
            'account': account,
            'stage': 'qualification',
            'amount': 50000,
            'probability': 25,
            'expected_close_date': '2024-12-31'
        }
        defaults.update(kwargs)
        return Opportunity.objects.create(**defaults)

    def assertResponseSuccess(self, response, status_code=200):
        """Assert response is successful."""
        self.assertEqual(
            response.status_code, 
            status_code,
            f"Expected {status_code}, got {response.status_code}. Response: {response.content}"
        )

    def assertResponseError(self, response, status_code=400):
        """Assert response contains error."""
        self.assertEqual(response.status_code, status_code)
        self.assertIn('error', response.json() if response.content else {})

class BaseAPIIntegrationTest(BaseIntegrationTest):
    """Extended base class for API integration tests."""
    
    def setUp(self):
        super().setUp()
        self.api_base_url = '/api/v1'
        
    def get_url(self, endpoint):
        """Get full API URL."""
        return f"{self.api_base_url}/{endpoint.lstrip('/')}"
        
    def api_get(self, endpoint, **kwargs):
        """Make authenticated GET request."""
        return self.client.get(self.get_url(endpoint), **kwargs)
        
    def api_post(self, endpoint, data=None, **kwargs):
        """Make authenticated POST request."""
        return self.client.post(
            self.get_url(endpoint), 
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )
        
    def api_put(self, endpoint, data=None, **kwargs):
        """Make authenticated PUT request."""
        return self.client.put(
            self.get_url(endpoint),
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )
        
    def api_patch(self, endpoint, data=None, **kwargs):
        """Make authenticated PATCH request."""
        return self.client.patch(
            self.get_url(endpoint),
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )
        
    def api_delete(self, endpoint, **kwargs):
        """Make authenticated DELETE request."""
        return self.client.delete(self.get_url(endpoint), **kwargs)