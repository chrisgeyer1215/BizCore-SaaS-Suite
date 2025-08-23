# backend/tests/integration/test_cross_module_integration.py
from .base import BaseAPIIntegrationTest
from apps.crm.models import Account, Lead, Opportunity, Activity, Campaign

class CrossModuleIntegrationTest(BaseAPIIntegrationTest):
    """Test integration across multiple CRM modules."""

    def test_complete_sales_cycle(self):
        """Test complete sales cycle from lead to closed deal."""
        
        # 1. Marketing generates lead through campaign
        campaign = self.create_campaign()
        lead_data = {
            'first_name': 'Michael',
            'last_name': 'Chen',
            'email': 'michael.chen@techstart.com',
            'company': 'TechStart Inc',
            'source': f'campaign_{campaign.id}',
            'status': 'new'
        }
        
        lead_response = self.api_post('crm/leads/', lead_data)
        lead_id = lead_response.json()['id']
        
        # 2. Sales team qualifies lead through activities
        # Initial contact activity
        call_activity = {
            'type': 'call',
            'subject': 'Initial Qualification Call',
            'description': 'Discussed company needs and budget',
            'related_to': lead_id,
            'related_type': 'lead',
            'outcome': 'positive',
            'status': 'completed'
        }
        
        self.api_post('crm/activities/', call_activity)
        
        # Update lead status to qualified
        self.api_patch(f'crm/leads/{lead_id}/', {'status': 'qualified', 'score': 75})
        
        # 3. Convert qualified lead to opportunity
        conversion_data = {
            'create_account': True,
            'opportunity_name': 'TechStart Software Implementation',
            'opportunity_amount': 250000,
            'opportunity_stage': 'qualification',
            'expected_close_date': '2024-08-15'
        }
        
        convert_response = self.api_post(f'crm/leads/{lead_id}/convert/', conversion_data)
        conversion_result = convert_response.json()
        
        account_id = conversion_result['account_id']
        opportunity_id = conversion_result['opportunity_id']
        
        # 4. Sales process - move through pipeline stages
        stages = [
            {'stage': 'needs_analysis', 'probability': 35},
            {'stage': 'proposal', 'probability': 65},
            {'stage': 'negotiation', 'probability': 80}
        ]
        
        for stage_data in stages:
            # Update opportunity stage
            self.api_patch(f'crm/opportunities/{opportunity_id}/', stage_data)
            
            # Add activity for stage progression
            activity_data = {
                'type': 'meeting',
                'subject': f'Stage: {stage_data["stage"]}',
                'related_to': opportunity_id,
                'related_type': 'opportunity',
                'status': 'completed'
            }
            self.api_post('crm/activities/', activity_data)
        
        # 5. Close the deal
        close_data = {
            'stage': 'won',
            'probability': 100,
            'actual_close_date': '2024-08-10',
            'close_reason': 'Customer chose our solution'
        }
        
        close_response = self.api_post(f'crm/opportunities/{opportunity_id}/close/', close_data)
        self.assertResponseSuccess(close_response)
        
        # 6. Verify complete sales cycle data
        # Check final opportunity status
        opp_response = self.api_get(f'crm/opportunities/{opportunity_id}/')
        final_opportunity = opp_response.json()
        
        self.assertEqual(final_opportunity['stage'], 'won')
        self.assertEqual(final_opportunity['probability'], 100)
        
        # Check account is now customer
        account_response = self.api_get(f'crm/accounts/{account_id}/')
        account = account_response.json()
        self.assertEqual(account['status'], 'customer')
        
        # Check activity history
        activities_response = self.api_get(f'crm/activities/?related_to={account_id}')
        activities = activities_response.json()['results']
        self.assertGreater(len(activities), 3)  # Should have multiple activities
        
        # 7. Generate sales analytics
        analytics_response = self.api_get('crm/analytics/sales-pipeline/?time_range=90d')
        analytics = analytics_response.json()
        
        self.assertIn('won_deals', analytics)
        self.assertIn('total_revenue', analytics)
        self.assertGreaterEqual(analytics['total_revenue'], 250000)

    def test_customer_support_integration(self):
        """Test integration between sales and customer support."""
        
        # 1. Create customer account with closed deal
        account = self.create_test_account(status='customer')
        opportunity = self.create_test_opportunity(
            account=account,
            stage='won',
            amount=100000
        )
        
        # 2. Customer creates support ticket
        ticket_data = {
            'subject': 'Integration Issue with Platform',
            'description': 'Having trouble with API integration setup',
            'priority': 'high',
            'category': 'technical',
            'account': account.id,
            'status': 'open'
        }
        
        ticket_response = self.api_post('crm/tickets/', ticket_data)
        self.assertResponseSuccess(ticket_response, 201)
        ticket_id = ticket_response.json()['id']
        
        # 3. Support team works on ticket
        # Add support activity
        support_activity = {
            'type': 'support_call',
            'subject': 'Technical Support Call',
            'description': 'Helped customer with API configuration',
            'related_to': ticket_id,
            'related_type': 'ticket',
            'duration_minutes': 45,
            'status': 'completed'
        }
        
        self.api_post('crm/activities/', support_activity)
        
        # Update ticket status
        self.api_patch(f'crm/tickets/{ticket_id}/', {'status': 'resolved'})
        
        # 4. Check customer health score impact
        account_response = self.api_get(f'crm/accounts/{account.id}/analytics/')
        account_analytics = account_response.json()
        
        # Support interactions should affect customer health
        self.assertIn('support_metrics', account_analytics)
        support_metrics = account_analytics['support_metrics']
        self.assertEqual(support_metrics['total_tickets'], 1)
        self.assertEqual(support_metrics['resolved_tickets'], 1)
        
        # 5. Opportunity for upsell based on support interaction
        # Create follow-up opportunity
        upsell_data = {
            'name': 'Professional Services - API Integration',
            'account': account.id,
            'stage': 'qualification',
            'amount': 25000,
            'source': f'support_ticket_{ticket_id}',
            'expected_close_date': '2024-09-30'
        }
        
        upsell_response = self.api_post('crm/opportunities/', upsell_data)
        self.assertResponseSuccess(upsell_response, 201)

    def create_campaign(self):
        """Helper to create test campaign."""
        from apps.crm.models import Campaign
        return Campaign.objects.create(
            name='Test Campaign',
            type='email',
            status='active'
        )