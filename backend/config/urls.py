# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.documentation import include_docs_urls
from rest_framework.routers import DefaultRouter


@api_view(['GET'])
def api_root(request):
    """
    API Root endpoint
    """
    return Response({
        'message': 'Welcome to SaaS-AICE API',
        'version': '1.0.0',
        'status': 'operational',
        'documentation': {
            'swagger': request.build_absolute_uri('/api/docs/'),
            'redoc': request.build_absolute_uri('/api/redoc/'),
            'schema': request.build_absolute_uri('/api/schema/')
        },
        'endpoints': {
            'auth': request.build_absolute_uri('/api/auth/'),
            'tenants': request.build_absolute_uri('/api/tenants/'),
            'crm': request.build_absolute_uri('/api/crm/'),
            'inventory': request.build_absolute_uri('/api/inventory/'),
            'ecommerce': request.build_absolute_uri('/api/ecommerce/'),
            'finance': request.build_absolute_uri('/api/finance/'),
        },
        'quick_start': {
            'register': 'POST /api/auth/register/',
            'login': 'POST /api/auth/login/',
            'create_tenant': 'POST /api/auth/create-tenant/',
            'health_check': 'GET /api/tenants/health/'
        }
    })


# API Version 1 Router
api_v1_router = DefaultRouter()

urlpatterns = [

     # Admin
    path('admin/', admin.site.urls),

     # CRM Admin Interface
    path('crm-admin/', include('apps.crm.admin_urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('docs/', include_docs_urls(title='SaaS-AICE API')),
    
    # Authentication (Public Schema)
    path('api/v1/auth/', include('apps.auth.urls')),
    
    # Core APIs (Tenant Schema)
    path('api/v1/core/', include('apps.core.urls')),
    path('api/v1/crm/', include('apps.crm.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/ecommerce/', include('apps.ecommerce.urls')),
    path('api/v1/finance/', include('apps.finance.urls')),
    
    # Sector Apps
    path('api/v1/sectors/', include('apps.sectors.urls')),
    
    # AI & Analytics
    path('api/v1/ai/', include('apps.ai.urls')),
    
    # API Router (for ViewSets)
    path('api/v1/', include(api_v1_router.urls)),
    
    # Health Check
    path('health/', include('apps.core.health_urls')),
]

# Error handlers
handler400 = 'apps.core.views.bad_request'
handler403 = 'apps.core.views.permission_denied'
handler404 = 'apps.core.views.page_not_found'
handler500 = 'apps.core.views.server_error'

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add debug toolbar in development
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
