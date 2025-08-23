# backend/tests/integration/test_lead_conversion_integration.py
from .base import BaseAPIIntegrationTest
from apps.crm.models import Lead, Account, Opportunity

class LeadConversionIntegrationTest(BaseAPIIntegrationTest):
    """Test complete lead to opportunity conversion process."""

    def test_complete_lead_conversion_workflow(self):
        """Test end-to-end lead conversion process."""
        
        # 1. Create Lead
        lead_data = {
            'first_name': 'Sarah',
            'last_name': 'Johnson', 
            'email': 'sarah.johnson@newcorp.com',
            'company': 'New Corporation',
            'title': 'VP of Operations',
            'phone': '+1-555-1234',
            'source': 'referral',
            'status': 'qualified'
        }
        
        create_response = self.api_post('crm/leads/', lead_data)
        self.assertResponseSuccess(create_response, 201)
        
        lead_id = create_response.json()['id']
        
        # 2. Update lead score through activities
        activity_data = {
            'type': 'call',
            'subject': 'Discovery Call',
            'description': 'Great conversation about needs',
            'related_to': lead_id,
            'related_type': 'lead',
            'status': 'completed'
        }
        
        activity_response = self.api_post('crm/activities/', activity_data)
        self.assertResponseSuccess(activity_response, 201)
        
        # 3. Convert Lead to Opportunity
        conversion_data = {
            'create_account': True,
            'account_name': 'New Corporation',
            'opportunity_name': 'Q1 Software Implementation',
            'opportunity_amount': 150000,
            'opportunity_stage': 'qualification',
            'expected_close_date': '2024-06-30'
        }
        
        convert_response = self.api_post(f'crm/leads/{lead_id}/convert/', conversion_data)
        self.assertResponseSuccess(convert_response, 201)
        
        conversion_result = convert_response.json()
        
        # 4. Verify Conversion Results
        self.assertIn('account_id', conversion_result)
        self.assertIn('opportunity_id', conversion_result)
        self.assertIn('success', conversion_result)
        self.assertTrue(conversion_result['success'])
        
        account_id = conversion_result['account_id']
        opportunity_id = conversion_result['opportunity_id']
        
        # 5. Verify Account Creation
        account_response = self.api_get(f'crm/accounts/{account_id}/')
        self.assertResponseSuccess(account_response)
        
        account = account_response.json()
        self.assertEqual(account['name'], conversion_data['account_name'])
        self.assertEqual(account['email'], lead_data['email'])
        
        # 6. Verify Opportunity Creation
        opp_response = self.api_get(f'crm/opportunities/{opportunity_id}/')
        self.assertResponseSuccess(opp_response)
        
        opportunity = opp_response.json()
        self.assertEqual(opportunity['name'], conversion_data['opportunity_name'])
        self.assertEqual(opportunity['amount'], conversion_data['opportunity_amount'])
        self.assertEqual(opportunity['account'], account_id)
        
        # 7. Verify Lead Status Update
        lead_response = self.api_get(f'crm/leads/{lead_id}/')
        self.assertResponseSuccess(lead_response)
        
        updated_lead = lead_response.json()
        self.assertEqual(updated_lead['status'], 'converted')
        
        # 8. Verify Activity Transfer
        activities_response = self.api_get(f'crm/activities/?related_to={account_id}&related_type=account')
        self.assertResponseSuccess(activities_response)
        
        activities = activities_response.json()['results']
        # Activities should be transferred from lead to account
        self.assertGreater(len(activities), 0)

    def test_lead_conversion_with_existing_account(self):
        """Test lead conversion using existing account."""
        
        # Create existing account
        existing_account = self.create_test_account(name='Existing Corp')
        
        # Create lead
        lead = self.create_test_lead(company='Existing Corp')
        
        # Convert with existing account
        conversion_data = {
            'create_account': False,
            'account_id': existing_account.id,
            'opportunity_name': 'Expansion Deal',
            'opportunity_amount': 75000
        }
        
        response = self.api_post(f'crm/leads/{lead.id}/convert/', conversion_data)
        self.assertResponseSuccess(response, 201)
        
        result = response.json()
        
        # Should use existing account
        self.assertEqual(result['account_id'], existing_account.id)
        
        # Verify opportunity is linked to existing account
        opp_response = self.api_get(f'crm/opportunities/{result["opportunity_id"]}/')
        opportunity = opp_response.json()
        self.assertEqual(opportunity['account'], existing_account.id)

    def test_lead_conversion_validation(self):
        """Test lead conversion validation and error handling."""
        
        lead = self.create_test_lead(status='new')  # Not qualified
        
        # Try to convert unqualified lead
        conversion_data = {
            'create_account': True,
            'opportunity_name': 'Test Deal',
            'opportunity_amount': 50000
        }
        
        response = self.api_post(f'crm/leads/{lead.id}/convert/', conversion_data)
        
        # Should validate lead qualification first
        if response.status_code != 201:
            error_data = response.json()
            self.assertIn('error', error_data)