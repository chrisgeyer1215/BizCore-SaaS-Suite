# apps/ecommerce/apps.py

from django.apps import AppConfig


class EcommerceConfig(AppConfig):
    """E-commerce app configuration"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ecommerce'
    verbose_name = 'E-commerce'
    
    def ready(self):
        """Initialize app signals and setup"""
        try:
            import apps.ecommerce.signals
        except ImportError:
            pass