"""
Product attribute system for flexible product specifications
"""
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator

from apps.core.models import TenantBaseModel
from ..abstract.base import ActivatableMixin, OrderableMixin
from ...managers.base import InventoryManager


class ProductAttribute(TenantBaseModel, ActivatableMixin, OrderableMixin):
    """
    Flexible product attribute system for specifications
    """
    
    ATTRIBUTE_TYPES = [
        ('TEXT', 'Text'),
        ('NUMBER', 'Number'),
        ('DECIMAL', 'Decimal'),
        ('BOOLEAN', 'Boolean'),
        ('DATE', 'Date'),
        ('COLOR', 'Color'),
        ('IMAGE', 'Image'),
        ('URL', 'URL'),
        ('EMAIL', 'Email'),
        ('SELECT', 'Single Select'),
        ('MULTISELECT', 'Multiple Select'),
        ('TEXTAREA', 'Text Area'),
        ('JSON', 'JSON Data'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='TEXT')
    
    # Validation & Constraints
    is_required = models.BooleanField(default=False)
    is_unique = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=True)
    is_filterable = models.BooleanField(default=True)
    is_variant_attribute = models.BooleanField(default=False)
    
    # Display Properties
    display_name = models.CharField(max_length=100, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    placeholder_text = models.CharField(max_length=100, blank=True)
    
    # Validation Rules (JSON)
    validation_rules = models.JSONField(default=dict, blank=True)
    default_value = models.CharField(max_length=255, blank=True)
    
    # Grouping & Organization
    attribute_group = models.CharField(max_length=50, blank=True)
    
    # Units (for numeric attributes)
    unit = models.ForeignKey(
        'core.UnitOfMeasure',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attributes'
    )
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_product_attributes'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'slug'], 
                name='unique_tenant_attribute_slug'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['tenant_id', 'attribute_type']),
            models.Index(fields=['tenant_id', 'attribute_group']),
            models.Index(fields=['tenant_id', 'is_variant_attribute']),
        ]
    
    def __str__(self):
        return self.display_name or self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.display_name:
            self.display_name = self.name
        super().save(*args, **kwargs)
    
    def get_validation_rules_display(self):
        """Get formatted validation rules for display"""
        rules = []
        for key, value in self.validation_rules.items():
            rules.append(f"{key}: {value}")
        return ", ".join(rules)


class AttributeValue(TenantBaseModel, ActivatableMixin, OrderableMixin):
    """
    Predefined values for select-type attributes
    """
    
    attribute = models.ForeignKey(
        ProductAttribute,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
    
    # Additional Properties
    color_code = models.CharField(max_length=7, blank=True)  # For color attributes
    image = models.ImageField(upload_to='attribute_values/', blank=True, null=True)
    description = models.TextField(blank=True)
    
    # Default Setting
    is_default = models.BooleanField(default=False)
    
    # Additional Data
    extra_data = models.JSONField(default=dict, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_attribute_values'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'attribute', 'value'], 
                name='unique_tenant_attribute_value'
            ),
        ]
        ordering = ['attribute__sort_order', 'sort_order', 'display_name']
        indexes = [
            models.Index(fields=['tenant_id', 'attribute', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.attribute.name}: {self.display_name or self.value}"
    
    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.value
        super().save(*args, **kwargs)