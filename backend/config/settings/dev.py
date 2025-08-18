# config/settings/dev.py

import sys
from .base import *

# Debug mode
DEBUG = True

# Allowed hosts for development
ALLOWED_HOSTS = ['*']

# Database for development
DATABASES['default'].update({
    'HOST': config('DB_HOST', default='localhost'),
    'PORT': config('DB_PORT', default='5432'),
})

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

CORS_ALLOW_ALL_ORIGINS = True  # Only for development
CORS_ALLOW_CREDENTIALS = True

# CSRF settings for development
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Add development tools
INSTALLED_APPS += [
    'django_extensions',
    'debug_toolbar',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
] + MIDDLEWARE

# Debug toolbar configuration
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# Development-specific logging
LOGGING['loggers'].update({
    'django_tenants': {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    },
    'apps': {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    },
})

# Celery settings for development
CELERY_TASK_ALWAYS_EAGER = config('CELERY_ALWAYS_EAGER', default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True

# Cache configuration for development
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Development file uploads
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Static files for development
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# JWT settings for development (shorter expiry for testing)
SIMPLE_JWT.update({
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
})

# Development feature flags
DEVELOPMENT_FEATURES = {
    'ENABLE_SWAGGER': True,
    'ENABLE_DEBUG_TOOLBAR': True,
    'ENABLE_DJANGO_EXTENSIONS': True,
    'SKIP_EMAIL_VERIFICATION': True,
    'AUTO_VERIFY_DOMAINS': True,
}

# Spectacular settings for development
SPECTACULAR_SETTINGS.update({
    'SERVE_INCLUDE_SCHEMA': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'displayOperationId': True,
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
        'displayRequestDuration': True,
        'docExpansion': 'none',
        'filter': True,
        'showExtensions': True,
        'showCommonExtensions': True,
    }
})

# Development console commands
if 'shell_plus' in sys.argv:
    SHELL_PLUS_IMPORTS = [
        'from apps.auth.models import User, Membership, Invitation',
        'from apps.core.models import Tenant, Domain, TenantSettings',
        'from django.db import connection',
        'from django_tenants.utils import get_tenant_model, get_tenant_domain_model',
    ]

# Development middleware order (debug toolbar first)
if DEBUG and 'debug_toolbar' in INSTALLED_APPS:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# Tenant creation settings for development
TENANT_CREATION_FAKES_MIGRATIONS = True

# Auto-create demo data
AUTO_CREATE_DEMO_TENANT = config('AUTO_CREATE_DEMO_TENANT', default=False, cast=bool)