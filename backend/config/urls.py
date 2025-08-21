# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response


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


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Root
    path('api/', api_root, name='api_root'),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Authentication
    path('api/auth/', include('apps.auth.urls')),
    
    # Core (Tenant management, etc.)
    path('api/tenants/', include('apps.core.urls')),
    
    # Tenant-specific apps (these require tenant context)
    path('api/crm/', include('apps.crm.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/ecommerce/', include('apps.ecommerce.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/ai/', include('apps.ai.urls')),
]

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



# following will added for api documentation
# config/urls.py - Add documentation URLs

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView, 
    SpectacularRedocView, 
    SpectacularSwaggerView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.inventory.api.v1.urls')),
    
    # API Documentation URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Custom documentation pages
    path('docs/', include('apps.inventory.api.documentation.urls')),
]