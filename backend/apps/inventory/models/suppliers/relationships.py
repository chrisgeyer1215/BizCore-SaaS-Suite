"""
Supplier relationship models and VMI
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import date

from ..abstract.base import TenantBaseModel, ActivatableMixin
from ...managers.base import InventoryManager


class ProductSupplier(TenantBaseModel, ActivatableMixin):
    """
    Many-to-many relationship between products and suppliers with detailed terms
    """
    
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='supplier_items'
    )
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        related_name='product_items'
    )
    
    # Supplier-specific product info
    supplier_sku = models.CharField(max_length=50, blank=True)
    supplier_product_name = models.CharField(max_length=200, blank=True)
    manufacturer_part_number = models.CharField(max_length=100, blank=True)
    
    # Pricing & Terms
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    price_valid_from = models.DateField(default=date.today)
    price_valid_to = models.DateField(null=True, blank=True)
    
    # Order Terms
    minimum_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    maximum_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    order_multiple = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    lead_time_days = models.IntegerField(default=0)
    
    # Quality & Performance
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Status & Preferences
    is_preferred = models.BooleanField(default=False)
    
    # Purchase History
    last_purchase_date = models.DateTimeField(null=True, blank=True)
    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_purchases_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_orders_count = models.IntegerField(default=0)
    
    # Additional Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    warranty_terms = models.TextField(blank=True)
    return_policy = models.TextField(blank=True)
    special_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_product_suppliers'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'supplier'], 
                name='unique_tenant_product_supplier'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'product', 'is_active']),
            models.Index(fields=['tenant_id', 'supplier', 'is_active']),
            models.Index(fields=['tenant_id', 'is_preferred']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - {self.supplier.name}"
    
    @property
    def effective_lead_time(self):
        """Get effective lead time considering supplier's default"""
        return self.lead_time_days or self.supplier.lead_time_days


class VendorManagedInventory(TenantBaseModel, ActivatableMixin):
    """
    Vendor Managed Inventory agreements and tracking
    """
    
    VMI_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDED', 'Suspended'),
        ('TERMINATED', 'Terminated'),
    ]
    
    # Agreement Information
    vmi_number = models.CharField(max_length=100, blank=True)
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        related_name='vmi_agreements'
    )
    warehouse = models.ForeignKey(
        'warehouse.Warehouse',
        on_delete=models.CASCADE,
        related_name='vmi_agreements'
    )
    
    # Agreement Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=VMI_STATUS, default='ACTIVE')
    
    # Terms & Conditions
    min_stock_days = models.IntegerField(default=7)
    max_stock_days = models.IntegerField(default=30)
    reorder_frequency_days = models.IntegerField(default=7)
    service_level_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=95)
    
    # Financial Terms
    consignment_stock = models.BooleanField(default=False)
    payment_terms_days = models.IntegerField(default=30)
    price_protection_days = models.IntegerField(default=30)
    
    # Performance Tracking
    current_service_level = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stockout_incidents = models.IntegerField(default=0)
    excess_stock_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Contact Information
    supplier_contact = models.CharField(max_length=200, blank=True)
    internal_contact = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_vmi_agreements'
    )
    
    # Additional Information
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_vendor_managed_inventory'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'vmi_number'], 
                name='unique_tenant_vmi_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'supplier', 'status']),
            models.Index(fields=['tenant_id', 'warehouse', 'status']),
        ]
    
    def __str__(self):
        return f"VMI-{self.vmi_number}: {self.supplier.name} → {self.warehouse.name}"
    
    def clean(self):
        if not self.vmi_number:
            # Auto-generate VMI number
            last_vmi = VendorManagedInventory.objects.filter(tenant_id=self.tenant_id).order_by('-id').first()
            if last_vmi and last_vmi.vmi_number:
                try:
                    last_num = int(last_vmi.vmi_number.replace('VMI', ''))
                except (ValueError, AttributeError):
                    last_num = 0
            else:
                last_num = 0
            self.vmi_number = f"VMI{last_num + 1:06d}"


class VMIProduct(TenantBaseModel, ActivatableMixin):
    """
    Products under VMI agreement with specific terms
    """
    
    vmi_agreement = models.ForeignKey(
        VendorManagedInventory,
        on_delete=models.CASCADE,
        related_name='products'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='vmi_products'
    )
    
    # Stock Levels
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    max_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    target_stock_level = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Demand Information
    average_daily_consumption = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    lead_time_days = models.IntegerField(default=7)
    safety_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Pricing
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2)
    price_valid_until = models.DateField(null=True, blank=True)
    
    # Status & Tracking
    last_replenishment_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    
    # Performance Metrics
    stockout_count = models.IntegerField(default=0)
    excess_stock_days = models.IntegerField(default=0)
    service_level_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_vmi_products'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'vmi_agreement', 'product'], 
                name='unique_vmi_product'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'vmi_agreement', 'is_active']),
            models.Index(fields=['tenant_id', 'product', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.vmi_agreement.vmi_number}: {self.product.name}"