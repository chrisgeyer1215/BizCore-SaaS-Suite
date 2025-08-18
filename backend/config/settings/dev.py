# Add this to your config/settings/dev.py to disable Redis issues

import sys
from .base import *

# Debug mode
DEBUG = True

# Allowed hosts for development
ALLOWED_HOSTS = ['*']

# Database for development - keep your working Neon config
DATABASES['default'].update({
    'HOST': config('DB_HOST'),
    'PORT': config('DB_PORT', default='5432'),
})

# DISABLE REDIS FOR DEVELOPMENT - This fixes admin login
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Use database sessions instead of cache (fixes admin login)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Disable Celery Redis dependency for development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Override any Redis URLs to avoid connection attempts
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'db+sqlite:///results.sqlite'

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

# Development file uploads
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Static files for development
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
] if (BASE_DIR / 'static').exists() else []