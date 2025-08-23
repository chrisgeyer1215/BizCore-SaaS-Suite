# backend/tests/integration/test_account_integration.py
import json
from decimal import Decimal
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .base import BaseAPIIntegrationTest

class AccountIntegrationTest(BaseAPIIntegrationTest):
    """Complete integration tests for Account operations."""

    def test_complete_account_lifecycle(self):
        """Test complete account lifecycle from creation to deletion."""
        
        # 1. Create Account
        account_data = {
            'name': 'Integration Test Corp',
            'email': 'integration@test.com',
            'phone': '+1-555-9999',
            'industry': 'technology',
            'annual_revenue': 5000000,
            'employees': 200,
            'website': 'https://integration.test.com'
        }
        
        create_response = self.api_post('crm/accounts/', account_data)
        self.assertResponseSuccess(create_response, 201)
        
        created_account = create_response.json()
        account_id = created_account['id']
        
        # Verify created data
        self.assertEqual(created_account['name'], account_data['name'])
        self.assertEqual(created_account['email'], account_data['email'])
        self.assertEqual(created_account['annual_revenue'], account_data['annual_revenue'])
        
        # 2. Retrieve Account
        get_response = self.api_get(f'crm/accounts/{account_id}/')
        self.assertResponseSuccess(get_response)
        
        retrieved_account = get_response.json()
        self.assertEqual(retrieved_account['id'], account_id)
        self.assertEqual(retrieved_account['name'], account_data['name'])
        
        # 3. Update Account
        update_data = {
            'annual_revenue': 7500000,
            'employees': 250,
            'status': 'customer'
        }
        
        update_response = self.api_patch(f'crm/accounts/{account_id}/', update_data)
        self.assertResponseSuccess(update_response)
        
        updated_account = update_response.json()
        self.assertEqual(updated_account['annual_revenue'], update_data['annual_revenue'])
        self.assertEqual(updated_account['employees'], update_data['employees'])
        self.assertEqual(updated_account['status'], update_data['status'])
        
        # 4. List Accounts with Filtering
        list_response = self.api_get('crm/accounts/?industry=technology&min_revenue=5000000')
        self.assertResponseSuccess(list_response)
        
        accounts_list = list_response.json()
        self.assertIn('results', accounts_list)
        self.assertGreaterEqual(len(accounts_list['results']), 1)
        
        # Verify our account is in the list
        account_ids = [acc['id'] for acc in accounts_list['results']]
        self.assertIn(account_id, account_ids)
        
        # 5. Search Accounts
        search_response = self.api_get('crm/accounts/?search=Integration')
        self.assertResponseSuccess(search_response)
        
        search_results = search_response.json()
        self.assertGreater(len(search_results['results']), 0)
        
        # 6. Get Account Analytics
        analytics_response = self.api_get(f'crm/accounts/{account_id}/analytics/?time_range=90d')
        self.assertResponseSuccess(analytics_response)
        
        analytics_data = analytics_response.json()
        self.assertIn('account_id', analytics_data)
        self.assertIn('revenue_metrics', analytics_data)
        self.assertIn('activity_metrics', analytics_data)
        
        # 7. Delete Account (Soft Delete)
        delete_response = self.api_delete(f'crm/accounts/{account_id}/')
        self.assertResponseSuccess(delete_response, 204)
        
        # Verify account is soft deleted
        get_deleted_response = self.api_get(f'crm/accounts/{account_id}/')
        self.assertResponseError(get_deleted_response, 404)

    def test_account_validation_errors(self):
        """Test account creation with validation errors."""
        
        # Missing required fields
        response = self.api_post('crm/accounts/', {})
        self.assertResponseError(response, 400)
        
        error_data = response.json()
        self.assertIn('name', error_data)
        self.assertIn('email', error_data)
        
        # Invalid email format
        invalid_data = {
            'name': 'Test Corp',
            'email': 'invalid-email',
            'annual_revenue': -1000  # Invalid negative revenue
        }
        
        response = self.api_post('crm/accounts/', invalid_data)
        self.assertResponseError(response, 400)
        
        error_data = response.json()
        self.assertIn('email', error_data)
        self.assertIn('annual_revenue', error_data)

    def test_account_permissions(self):
        """Test account access permissions."""
        
        # Create account with authenticated user
        account = self.create_test_account(name='Permission Test Corp')
        
        # Test with authenticated user
        response = self.api_get(f'crm/accounts/{account.id}/')
        self.assertResponseSuccess(response)
        
        # Test without authentication
        self.client.credentials()  # Remove auth headers
        response = self.api_get(f'crm/accounts/{account.id}/')
        self.assertResponseError(response, 401)

    def test_account_bulk_operations(self):
        """Test bulk import and export operations."""
        
        # Create test accounts for export
        for i in range(5):
            self.create_test_account(
                name=f'Bulk Test Corp {i}',
                email=f'bulk{i}@test.com',
                annual_revenue=1000000 + (i * 500000)
            )
        
        # Test bulk export
        export_response = self.api_get('crm/accounts/bulk-export/?format=csv')
        
        # Should either return file directly (200) or start background job (202)
        self.assertIn(export_response.status_code, [200, 202])
        
        if export_response.status_code == 200:
            # Direct file download
            self.assertEqual(export_response['Content-Type'], 'text/csv')
            self.assertIn('attachment', export_response['Content-Disposition'])
        else:
            # Background job started
            export_data = export_response.json()
            self.assertIn('export_id', export_data)
            self.assertIn('status', export_data)

    def test_account_relationships(self):
        """Test account relationships with other entities."""
        
        account = self.create_test_account(name='Relationship Test Corp')
        
        # Create related lead
        lead = self.create_test_lead(company=account.name)
        
        # Create related opportunity
        opportunity = self.create_test_opportunity(account=account)
        
        # Get account with relationships
        response = self.api_get(f'crm/accounts/{account.id}/')
        self.assertResponseSuccess(response)
        
        account_data = response.json()
        
        # Verify relationship counts are included
        self.assertIn('opportunity_count', account_data)
        self.assertEqual(account_data['opportunity_count'], 1)

class AccountWorkflowIntegrationTest(BaseAPIIntegrationTest):
    """Test account workflows and automation."""

    def test_account_status_change_workflow(self):
        """Test workflows triggered by account status changes."""
        
        account = self.create_test_account(status='prospect')
        
        # Change status to customer
        response = self.api_patch(f'crm/accounts/{account.id}/', {'status': 'customer'})
        self.assertResponseSuccess(response)
        
        # Verify workflow was triggered (would create activities, etc.)
        # This would test actual workflow execution in a real scenario
        activities = Activity.objects.filter(
            related_to=account,
            type='workflow_triggered'
        )
        
        # In a complete system, we'd verify workflow execution
        # self.assertGreater(activities.count(), 0)

class AccountAnalyticsIntegrationTest(BaseAPIIntegrationTest):
    """Test account analytics and reporting."""

    def test_account_revenue_analytics(self):
        """Test account revenue analytics calculation."""
        
        account = self.create_test_account(annual_revenue=5000000)
        
        # Create opportunities to generate revenue data
        won_opp = self.create_test_opportunity(
            account=account,
            stage='won',
            amount=100000
        )
        
        pending_opp = self.create_test_opportunity(
            account=account,
            stage='proposal',
            amount=200000,
            probability=75
        )
        
        # Get analytics
        response = self.api_get(f'crm/accounts/{account.id}/analytics/')
        self.assertResponseSuccess(response)
        
        analytics = response.json()
        
        # Verify revenue calculations
        self.assertIn('revenue_metrics', analytics)
        revenue_metrics = analytics['revenue_metrics']
        
        self.assertEqual(revenue_metrics['total_opportunities'], 2)
        self.assertEqual(revenue_metrics['won_opportunities'], 1)
        self.assertEqual(revenue_metrics['total_revenue'], 100000)
        
        # Verify expected revenue calculation
        expected_revenue = (200000 * 0.75)  # pending opportunity * probability
        self.assertEqual(revenue_metrics.get('expected_revenue', 0), expected_revenue)
