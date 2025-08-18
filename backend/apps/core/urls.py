# apps/core/urls.py

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Tenant Management (Public schema)
    path('', views.TenantListView.as_view(), name='tenant_list'),
    path('create/', views.TenantCreateView.as_view(), name='tenant_create'),
    path('<int:pk>/', views.TenantDetailView.as_view(), name='tenant_detail'),
    path('<int:pk>/update/', views.TenantUpdateView.as_view(), name='tenant_update'),
    path('<slug:slug>/', views.TenantBySlugView.as_view(), name='tenant_by_slug'),
    
    # Tenant Settings
    path('<int:pk>/settings/', views.TenantSettingsView.as_view(), name='tenant_settings'),
    path('<int:pk>/usage/', views.TenantUsageView.as_view(), name='tenant_usage'),
    
    # Domain Management
    path('<int:pk>/domains/', views.TenantDomainsView.as_view(), name='tenant_domains'),
    path('domains/<int:pk>/', views.DomainDetailView.as_view(), name='domain_detail'),
    path('domains/<int:pk>/verify/', views.verify_domain, name='verify_domain'),
    
    # Health Check
    path('health/', views.health_check, name='health_check'),
    
    # Tenant Status
    path('<int:pk>/activate/', views.activate_tenant, name='activate_tenant'),
    path('<int:pk>/suspend/', views.suspend_tenant, name='suspend_tenant'),
]