from django.apps import AppConfig


class EcommerceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ecommerce'
    verbose_name = 'E-commerce'
    
    def ready(self):
        """Import signals when Django starts"""
        import apps.ecommerce.signals
