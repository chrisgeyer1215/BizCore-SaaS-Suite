# backend/apps/finance/api/webhook_urls.py

"""
Webhook URLs
External system integration endpoints
"""

from django.urls import path
from .views.webhooks import (
    StripeWebhookView, PayPalWebhookView, BankFeedWebhookView
)

urlpatterns = [
    path('stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paypal/', PayPalWebhookView.as_view(), name='paypal-webhook'),
    path('bank-feed/', BankFeedWebhookView.as_view(), name='bank-feed-webhook'),
]