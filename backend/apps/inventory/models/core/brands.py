"""
Brand and manufacturer models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from ..abstract.base import TenantBaseModel, SoftDeleteMixin, ActivatableMixin
from ...managers.base import InventoryManager


class Brand(TenantBaseModel, SoftDeleteMixin, ActivatableMixin):
    """
    Enhanced brand management with performance tracking
    """
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Contact Information
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Business Details
    manufacturer = models.BooleanField(default=False)
    country_of_origin = models.CharField(max_length=100, blank=True)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Quality & Certifications
    certifications = models.JSONField(default=list, blank=True)
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Status & Preferences
    is_preferred = models.BooleanField(default=False)
    
    # Media
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    logo_url = models.URLField(blank=True)
    brand_colors = models.JSONField(default=dict, blank=True)
    
    # Performance Metrics
    total_products = models.PositiveIntegerField(default=0)
    total_sales_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_product_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_brands'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'code'], 
                name='unique_tenant_brand_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'code']),
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['tenant_id', 'is_preferred']),
            models.Index(fields=['tenant_id', 'manufacturer']),
        ]
    
    def __str__(self):
        return self.name
    
    def update_metrics(self):
        """Update brand performance metrics"""
        from ..catalog.products import Product
        
        products = Product.objects.filter(brand=self, tenant_id=self.tenant_id)
        self.total_products = products.count()
        
        # Update other metrics as needed
        self.save(update_fields=['total_products'])