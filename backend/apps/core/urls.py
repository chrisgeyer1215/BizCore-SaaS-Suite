# apps/core/urls.py

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Health Check (available on public tenant)
    path('health/', views.health_check, name='health_check'),
    
    # Basic tenant endpoints
    path('', views.TenantListView.as_view(), name='tenant_list'),
    path('create/', views.TenantCreateView.as_view(), name='tenant_create'),
    path('<int:pk>/', views.TenantDetailView.as_view(), name='tenant_detail'),
    
    # Use only slug-based lookup to avoid conflicts
    path('by-slug/<slug:slug>/', views.TenantBySlugView.as_view(), name='tenant_by_slug'),
]