"""
Product variation models for configurable products
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from ..abstract.base import ActivatableMixin, OrderableMixin
from ...managers.base import InventoryManager


class ProductVariation(TenantBaseModel, SoftDeleteMixin, ActivatableMixin, OrderableMixin):
    """
    Product variations for configurable products with attribute combinations
    """
    
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='variations'
    )
    variation_code = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255)
    
    # Override product properties
    sku = models.CharField(max_length=50, blank=True)
    barcode = models.CharField(max_length=50, blank=True)
    
    # Pricing overrides
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    msrp = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Physical property overrides
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    
    # Stock level overrides
    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reorder_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    
    # Media overrides
    primary_image = models.ImageField(upload_to='variations/', blank=True, null=True)
    images = models.JSONField(default=list, blank=True)
    
    # Attribute combinations (for variant generation)
    attribute_values = models.ManyToManyField(
        'core.AttributeValue',
        blank=True,
        related_name='product_variations'
    )
    
    # Additional properties
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_product_variations'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'variation_code'], 
                name='unique_tenant_variation_code'
            ),
            models.UniqueConstraint(
                fields=['tenant_id', 'sku'],
                condition=models.Q(sku__isnull=False) & ~models.Q(sku=''),
                name='unique_tenant_variation_sku'
            ),
            models.UniqueConstraint(
                fields=['tenant_id', 'barcode'],
                condition=models.Q(barcode__isnull=False) & ~models.Q(barcode=''),
                name='unique_tenant_variation_barcode'
            ),
        ]
        ordering = ['product__name', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['tenant_id', 'product', 'is_active']),
            models.Index(fields=['tenant_id', 'sku']),
            models.Index(fields=['tenant_id', 'barcode']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"
    
    @property
    def effective_cost_price(self):
        """Get effective cost price (variation or parent product)"""
        return self.cost_price or self.product.cost_price
    
    @property
    def effective_selling_price(self):
        """Get effective selling price (variation or parent product)"""
        return self.selling_price or self.product.selling_price
    
    @property
    def effective_sku(self):
        """Get effective SKU (variation or generated)"""
        return self.sku or f"{self.product.sku}-{self.variation_code}"
    
    @property
    def attribute_display(self):
        """Get attribute combination display"""
        attrs = []
        for attr_value in self.attribute_values.all():
            attrs.append(f"{attr_value.attribute.name}: {attr_value.display_name}")
        return ", ".join(attrs)
    
    @property
    def total_stock(self):
        """Total stock across all warehouses"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            variation=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        return sum(item.quantity_on_hand for item in stock_items)
    
    @property
    def available_stock(self):
        """Available stock across all warehouses"""
        from ..stock.items import StockItem
        
        stock_items = StockItem.objects.filter(
            variation=self,
            tenant_id=self.tenant_id,
            is_active=True
        )
        return sum(item.quantity_available for item in stock_items)
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        if not self.variation_code:
            # Auto-generate variation code
            existing_count = ProductVariation.objects.filter(
                tenant_id=self.tenant_id,
                product=self.product
            ).count()
            self.variation_code = f"VAR{existing_count + 1:03d}"
        
        if not self.sku:
            self.sku = f"{self.product.sku}-{self.variation_code}"


class ProductAttributeValue(TenantBaseModel):
    """
    Junction table for product attributes with flexible value storage
    """
    
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='attribute_values'
    )
    attribute = models.ForeignKey(
        'core.ProductAttribute',
        on_delete=models.CASCADE
    )
    
    # Value storage (only one should be used based on attribute type)
    value = models.ForeignKey(
        'core.AttributeValue',
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(null=True, blank=True)
    
    # For multiple select attributes
    multiple_values = models.ManyToManyField(
        'core.AttributeValue', 
        blank=True, 
        related_name='product_multi_values'
    )
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_product_attribute_values'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'attribute'], 
                name='unique_tenant_product_attribute'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'product']),
            models.Index(fields=['tenant_id', 'attribute']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}: {self.get_display_value()}"
    
    def get_display_value(self):
        """Get the appropriate display value based on attribute type"""
        if self.attribute.attribute_type == 'SELECT' and self.value:
            return self.value.display_name
        elif self.attribute.attribute_type == 'MULTISELECT':
            values = [v.display_name for v in self.multiple_values.all()]
            return ', '.join(values)
        elif self.attribute.attribute_type in ['TEXT', 'TEXTAREA', 'URL', 'EMAIL']:
            return self.text_value
        elif self.attribute.attribute_type in ['NUMBER', 'DECIMAL']:
            return str(self.number_value) if self.number_value else ''
        elif self.attribute.attribute_type == 'DATE':
            return str(self.date_value) if self.date_value else ''
        elif self.attribute.attribute_type == 'BOOLEAN':
            return 'Yes' if self.boolean_value else 'No'
        elif self.attribute.attribute_type == 'JSON':
            return str(self.json_value) if self.json_value else ''
        return ''
    
    def set_value(self, value):
        """Set value based on attribute type"""
        if self.attribute.attribute_type == 'SELECT':
            if hasattr(value, 'pk'):  # AttributeValue instance
                self.value = value
            elif isinstance(value, str):
                from ..core.attributes import AttributeValue
                self.value = AttributeValue.objects.get(
                    attribute=self.attribute, 
                    value=value,
                    tenant_id=self.tenant_id
                )
        elif self.attribute.attribute_type in ['TEXT', 'TEXTAREA', 'URL', 'EMAIL']:
            self.text_value = str(value)
        elif self.attribute.attribute_type in ['NUMBER', 'DECIMAL']:
            self.number_value = Decimal(str(value))
        elif self.attribute.attribute_type == 'DATE':
            self.date_value = value
        elif self.attribute.attribute_type == 'BOOLEAN':
            self.boolean_value = bool(value)
        elif self.attribute.attribute_type == 'JSON':
            self.json_value = value