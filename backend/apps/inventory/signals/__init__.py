from django.apps import AppConfig

def register_signals():
    """Register all inventory signals"""
    from . import handlers
    from . import stock_signals
    from . import product_signals
    from . import alert_signals
    from . import purchasing_signals
    from . import transfer_signals
    from . import adjustment_signals
    from . import integration_signals