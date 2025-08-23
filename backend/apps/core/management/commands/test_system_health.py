# backend/tests/integration/test_system_health.py
from django.test import TestCase
from django.core.cache import cache
from django.db import connection
from .base import BaseAPIIntegrationTest

class SystemHealthIntegrationTest(BaseAPIIntegrationTest):
    """Test system health and monitoring endpoints."""

    def test_health_check_endpoints(self):
        """Test all health check endpoints."""
        
        # Basic health check
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        
        health_data = response.json()
        self.assertIn('status', health_data)
        self.assertEqual(health_data['status'], 'healthy')
        
        # Database health check
        db_response = self.client.get('/health/database/')
        self.assertEqual(db_response.status_code, 200)
        
        db_health = db_response.json()
        self.assertEqual(db_health['database'], 'connected')
        
        # Cache health check
        cache_response = self.client.get('/health/cache/')
        self.assertEqual(cache_response.status_code, 200)
        
        # Tenant health check
        tenant_response = self.client.get('/health/tenant/', 
                                        HTTP_HOST='test-tenant.localhost')
        self.assertEqual(tenant_response.status_code, 200)

    def test_api_performance_benchmarks(self):
        """Test API performance benchmarks."""
        import time
        
        # Create test data
        for i in range(10):
            self.create_test_account(name=f'Perf Test Account {i}')
        
        # Test list endpoint performance
        start_time = time.time()
        response = self.api_get('crm/accounts/')
        end_time = time.time()
        
        self.assertResponseSuccess(response)
        
        # Should respond within 1 second for small dataset
        response_time = end_time - start_time
        self.assertLess(response_time, 1.0, 
                       f"Account list took {response_time:.2f}s (too slow)")
        
        # Test pagination performance
        paginated_response = self.api_get('crm/accounts/?page=1&page_size=5')
        self.assertResponseSuccess(paginated_response)
        
        data = paginated_response.json()
        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertEqual(len(data['results']), 5)

    def test_concurrent_requests(self):
        """Test system behavior under concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            try:
                response = self.api_get('crm/accounts/')
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        # Create 10 concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Check results
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual(result, 200)
        
        # Should handle 10 concurrent requests within 5 seconds
        total_time = end_time - start_time
        self.assertLess(total_time, 5.0)

class DatabaseIntegrityTest(BaseAPIIntegrationTest):
    """Test database integrity and constraints."""

    def test_foreign_key_constraints(self):
        """Test foreign key constraints are enforced."""
        
        # Try to create opportunity with non-existent account
        invalid_opp_data = {
            'name': 'Invalid Opportunity',
            'account': 99999,  # Non-existent account ID
            'amount': 50000
        }
        
        response = self.api_post('crm/opportunities/', invalid_opp_data)
        self.assertResponseError(response, 400)
        
        error_data = response.json()
        self.assertIn('account', error_data)

    def test_unique_constraints(self):
        """Test unique constraints are enforced."""
        
        # Create account
        account_data = {
            'name': 'Unique Test Corp',
            'email': 'unique@test.com'
        }
        
        first_response = self.api_post('crm/accounts/', account_data)
        self.assertResponseSuccess(first_response, 201)
        
        # Try to create duplicate
        duplicate_response = self.api_post('crm/accounts/', account_data)
        self.assertResponseError(duplicate_response, 400)
        
        error_data = duplicate_response.json()
        # Should indicate duplicate email error
        self.assertIn('email', error_data)

    def test_cascade_deletes(self):
        """Test cascade delete behavior."""
        
        account = self.create_test_account()
        opportunity = self.create_test_opportunity(account=account)
        
        # Create activity related to opportunity
        activity_data = {
            'type': 'call',
            'subject': 'Follow-up call',
            'related_to': opportunity.id,
            'related_type': 'opportunity'
        }
        
        activity_response = self.api_post('crm/activities/', activity_data)
        activity_id = activity_response.json()['id']
        
        # Delete account (soft delete)
        self.api_delete(f'crm/accounts/{account.id}/')
        
        # Verify related records handling
        opp_response = self.api_get(f'crm/opportunities/{opportunity.id}/')
        self.assertResponseError(opp_response, 404)  # Should be soft deleted
        
        # Activities should remain for audit purposes
        activity_response = self.api_get(f'crm/activities/{activity_id}/')
        # Depending on business rules, might be accessible or not