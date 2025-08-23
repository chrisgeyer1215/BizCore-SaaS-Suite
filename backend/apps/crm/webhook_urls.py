# backend/apps/crm/webhook_urls.py - Webhook Handler URLs
from django.urls import path
from .views import WebhookView

app_name = 'crm_webhooks'

urlpatterns = [
    # Generic webhook handler
    path('crm/', WebhookView.as_view(), name='crm-webhook'),
    
    # Specific webhook handlers
    path('crm/lead-created/', WebhookView.as_view(), {'event_type': 'lead_created'}, name='lead-created-webhook'),
    path('crm/opportunity-won/', WebhookView.as_view(), {'event_type': 'opportunity_won'}, name='opportunity-won-webhook'),
    path('crm/account-updated/', WebhookView.as_view(), {'event_type': 'account_updated'}, name='account-updated-webhook'),
    path('crm/ticket-created/', WebhookView.as_view(), {'event_type': 'ticket_created'}, name='ticket-created-webhook'),
    
    # Integration webhooks
    path('integrations/<str:integration_name>/', WebhookView.as_view(), name='integration-webhook'),
    
    # Third-party webhooks
    path('mailchimp/', WebhookView.as_view(), {'integration': 'mailchimp'}, name='mailchimp-webhook'),
    path('zapier/', WebhookView.as_view(), {'integration': 'zapier'}, name='zapier-webhook'),
    path('slack/', WebhookView.as_view(), {'integration': 'slack'}, name='slack-webhook'),
]