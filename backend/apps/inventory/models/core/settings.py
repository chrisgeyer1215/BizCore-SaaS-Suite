"""
Inventory settings and configuration models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from ..abstract.base import TenantBaseModel
from ...managers.base import InventoryManager


class InventorySettings(TenantBaseModel):
    """
    Tenant-specific inventory configuration and settings
    """
    
    VALUATION_METHODS = [
        ('FIFO', 'First In First Out'),
        ('LIFO', 'Last In First Out'),
        ('AVERAGE', 'Weighted Average'),
        ('SPECIFIC', 'Specific Identification'),
        ('STANDARD', 'Standard Cost'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('JPY', 'Japanese Yen'),
        ('INR', 'Indian Rupee'),
        ('CAD', 'Canadian Dollar'),
        ('AUD', 'Australian Dollar'),
    ]
    
    COST_CALCULATION_METHODS = [
        ('STANDARD', 'Standard Cost'),
        ('ACTUAL', 'Actual Cost'),
        ('AVERAGE', 'Moving Average'),
    ]
    
    # Core Settings
    valuation_method = models.CharField(
        max_length=20, 
        choices=VALUATION_METHODS, 
        default='FIFO'
    )
    default_currency = models.CharField(
        max_length=3, 
        choices=CURRENCY_CHOICES, 
        default='USD'
    )
    enable_multi_currency = models.BooleanField(default=False)
    decimal_precision = models.IntegerField(
        default=2, 
        validators=[MinValueValidator(0), MaxValueValidator(6)]
    )
    
    # Stock Management
    low_stock_alert_enabled = models.BooleanField(default=True)
    low_stock_threshold_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage threshold for low stock alerts"
    )
    auto_reorder_enabled = models.BooleanField(default=False)
    allow_negative_stock = models.BooleanField(default=False)
    enable_reserved_stock = models.BooleanField(default=True)
    enable_allocated_stock = models.BooleanField(default=True)
    
    # Advanced Tracking
    enable_batch_tracking = models.BooleanField(default=True)
    enable_serial_tracking = models.BooleanField(default=False)
    enable_lot_tracking = models.BooleanField(default=True)
    enable_expiry_tracking = models.BooleanField(default=True)
    enable_landed_cost = models.BooleanField(default=False)
    
    # Barcode & Identification
    enable_barcode = models.BooleanField(default=True)
    enable_qr_code = models.BooleanField(default=True)
    auto_generate_barcodes = models.BooleanField(default=True)
    barcode_prefix = models.CharField(max_length=10, default='PRD', blank=True)
    
    # Drop Shipping & Third Party
    enable_dropshipping = models.BooleanField(default=False)
    enable_consignment = models.BooleanField(default=False)
    enable_third_party_logistics = models.BooleanField(default=False)
    
    # Manufacturing & Assembly
    enable_manufacturing = models.BooleanField(default=False)
    enable_kitting = models.BooleanField(default=False)
    enable_bundling = models.BooleanField(default=False)
    
    # Quality Control
    enable_quality_control = models.BooleanField(default=False)
    enable_inspection = models.BooleanField(default=False)
    enable_quarantine = models.BooleanField(default=False)
    
    # Pricing & Costing
    enable_dynamic_pricing = models.BooleanField(default=False)
    enable_tier_pricing = models.BooleanField(default=False)
    enable_promotional_pricing = models.BooleanField(default=False)
    cost_calculation_method = models.CharField(
        max_length=20,
        choices=COST_CALCULATION_METHODS,
        default='AVERAGE'
    )
    
    # Reporting & Analytics
    enable_abc_analysis = models.BooleanField(default=True)
    enable_velocity_analysis = models.BooleanField(default=True)
    enable_seasonality_tracking = models.BooleanField(default=False)
    
    # Integration Settings
    erp_integration_enabled = models.BooleanField(default=False)
    accounting_integration_enabled = models.BooleanField(default=False)
    ecommerce_integration_enabled = models.BooleanField(default=False)
    
    # Audit & Compliance
    require_approval_for_adjustments = models.BooleanField(default=True)
    enable_audit_trail = models.BooleanField(default=True)
    retain_data_years = models.IntegerField(default=7)
    
    # Custom configuration (JSON for flexible settings)
    custom_settings = models.JSONField(default=dict, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_settings'
        verbose_name = 'Inventory Settings'
        verbose_name_plural = 'Inventory Settings'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id'], 
                name='unique_tenant_inventory_settings'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id']),
        ]
    
    def __str__(self):
        return f"Inventory Settings - Tenant {self.tenant_id}"
    
    @property
    def formatted_decimal_precision(self):
        """Get decimal precision as string for formatting"""
        return f"0.{'0' * self.decimal_precision}"
    
    def get_currency_symbol(self):
        """Get currency symbol for display"""
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'INR': '₹',
            'CAD': 'C$',
            'AUD': 'A$',
        }
        return currency_symbols.get(self.default_currency, self.default_currency)