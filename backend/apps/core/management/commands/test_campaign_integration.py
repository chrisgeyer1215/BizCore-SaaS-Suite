# backend/tests/integration/test_campaign_integration.py
from django.core import mail
from .base import BaseAPIIntegrationTest

class CampaignIntegrationTest(BaseAPIIntegrationTest):
    """Test complete campaign management and execution."""

    def test_email_campaign_execution(self):
        """Test complete email campaign creation and execution."""
        
        # 1. Create target accounts and leads
        accounts = []
        leads = []
        
        for i in range(3):
            account = self.create_test_account(
                name=f'Campaign Target {i}',
                email=f'campaign{i}@test.com'
            )
            accounts.append(account)
            
            lead = self.create_test_lead(
                email=f'lead{i}@test.com',
                status='qualified'
            )
            leads.append(lead)
        
        # 2. Create Email Campaign
        campaign_data = {
            'name': 'Q1 Product Launch Campaign',
            'type': 'email',
            'subject': 'Introducing Our Revolutionary New Platform',
            'content': '''
            <html>
            <body>
                <h1>Dear {{first_name}},</h1>
                <p>We're excited to introduce our new platform...</p>
                <a href="{{cta_link}}">Learn More</a>
            </body>
            </html>
            ''',
            'target_audience': 'qualified_leads',
            'status': 'draft',
            'scheduled_date': '2024-02-01T10:00:00Z'
        }
        
        create_response = self.api_post('crm/campaigns/', campaign_data)
        self.assertResponseSuccess(create_response, 201)
        
        campaign_id = create_response.json()['id']
        
        # 3. Add Campaign Members
        for lead in leads:
            member_data = {
                'campaign': campaign_id,
                'contact_type': 'lead',
                'contact_id': lead.id,
                'status': 'active'
            }
            
            member_response = self.api_post('crm/campaign-members/', member_data)
            self.assertResponseSuccess(member_response, 201)
        
        # 4. Launch Campaign
        launch_response = self.api_post(f'crm/campaigns/{campaign_id}/launch/')
        self.assertResponseSuccess(launch_response, 200)
        
        # 5. Verify Campaign Status
        campaign_response = self.api_get(f'crm/campaigns/{campaign_id}/')
        updated_campaign = campaign_response.json()
        self.assertEqual(updated_campaign['status'], 'active')
        
        # 6. Check Email Queue (in test environment)
        # In real system, emails would be queued for Celery
        self.assertGreater(len(mail.outbox), 0)
        
        # Verify email content personalization
        first_email = mail.outbox[0]
        self.assertIn('Introducing Our Revolutionary', first_email.subject)
        
        # 7. Track Campaign Performance
        performance_response = self.api_get(f'crm/campaigns/{campaign_id}/performance/')
        self.assertResponseSuccess(performance_response)
        
        performance = performance_response.json()
        self.assertIn('sent_count', performance)
        self.assertIn('delivery_rate', performance)
        self.assertIn('open_rate', performance)

    def test_campaign_segmentation(self):
        """Test campaign audience segmentation."""
        
        # Create leads with different characteristics
        high_score_lead = self.create_test_lead(
            email='highscore@test.com',
            score=85,
            status='qualified'
        )
        
        low_score_lead = self.create_test_lead(
            email='lowscore@test.com',
            score=25,
            status='new'
        )
        
        # Create segmented campaign
        campaign_data = {
            'name': 'High Value Prospects Campaign',
            'type': 'email',
            'subject': 'Exclusive Offer for Qualified Prospects',
            'target_criteria': {
                'min_score': 70,
                'status': 'qualified'
            }
        }
        
        response = self.api_post('crm/campaigns/', campaign_data)
        self.assertResponseSuccess(response, 201)
        
        campaign_id = response.json()['id']
        
        # Get campaign audience
        audience_response = self.api_get(f'crm/campaigns/{campaign_id}/audience/')
        self.assertResponseSuccess(audience_response)
        
        audience = audience_response.json()
        
        # Should only include high-scoring qualified leads
        audience_emails = [contact['email'] for contact in audience['contacts']]
        self.assertIn('highscore@test.com', audience_emails)
        self.assertNotIn('lowscore@test.com', audience_emails)