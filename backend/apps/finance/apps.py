# backend/apps/finance/apps.py

"""
Finance Application Configuration
"""

from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Finance app configuration"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = 'Finance & Accounting'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.finance.signals