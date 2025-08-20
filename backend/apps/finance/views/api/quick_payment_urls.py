# backend/apps/finance/api/quick_payment_urls.py

"""
Quick Payment Processing URLs
Simplified payment recording endpoints
"""

from django.urls import path
from .views.quick_payment import QuickPaymentView

urlpatterns = [
    path('record/', QuickPaymentView.as_view(), name='quick-payment-record'),
]