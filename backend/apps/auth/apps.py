# apps/auth/apps.py

from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auth'
    label = 'custom_auth'  # Different from built-in auth
    verbose_name = 'Authentication'