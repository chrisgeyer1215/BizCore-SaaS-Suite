# apps/inventory/api/v1/health_urls.py

from django.urls import path
from apps.inventory.api.v1.views.health import HealthCheckView

urlpatterns = [
    path('', HealthCheckView.as_view(), name='health-check'),
    path('detailed/', HealthCheckView.as_view(detailed=True), name='health-detailed'),
]