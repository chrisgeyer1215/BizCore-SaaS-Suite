# config/settings/test.py
from .base import *
import tempfile

# Enable testing mode
DEBUG = False
ALLOWED_HOSTS = ['*']
SECRET_KEY = 'test-secret-key-not-for-production'
TESTING = True

# Use in-memory database for speed
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'init_command': 'PRAGMA foreign_keys=ON;',
        },
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Cache configuration for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# Test media root
MEDIA_ROOT = tempfile.mkdtemp()

# Celery eager execution for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'INFO',
    },
}

# ML Testing configuration
ML_TESTING = {
    'USE_MOCK_MODELS': True,
    'MOCK_PREDICTION_LATENCY': 0.1,  # seconds
    'GENERATE_SYNTHETIC_DATA': True,
}

# Test-specific security settings
SECRET_KEY = 'test-secret-key-not-for-production'
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast for tests
]

# Disable CSRF for API tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}