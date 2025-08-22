"""
Unit of Measure models
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify
from decimal import Decimal, ROUND_HALF_UP

from apps.core.models import TenantBaseModel
from ..abstract.base import ActivatableMixin
from ...managers.base import InventoryManager


class UnitOfMeasure(TenantBaseModel, ActivatableMixin):
    """
    Enhanced unit of measure system with conversion capabilities
    """
    
    UNIT_TYPES = [
        ('COUNT', 'Count/Each'),
        ('WEIGHT', 'Weight'),
        ('VOLUME', 'Volume'),
        ('LENGTH', 'Length'),
        ('AREA', 'Area'),
        ('TIME', 'Time'),
        ('TEMPERATURE', 'Temperature'),
        ('ENERGY', 'Energy'),
        ('CURRENCY', 'Currency'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    symbol = models.CharField(max_length=5, blank=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    
    # Conversion System
    base_unit = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='derived_units',
        help_text="Base unit for conversion calculations"
    )
    conversion_factor = models.DecimalField(
        max_digits=15, decimal_places=6, default=Decimal('1.000000'),
        help_text="Factor to convert to base unit"
    )
    conversion_offset = models.DecimalField(
        max_digits=10, decimal_places=6, default=Decimal('0'),
        help_text="Offset for temperature conversions"
    )
    
    # Properties
    is_base_unit = models.BooleanField(default=False)
    allow_fractions = models.BooleanField(default=True)
    decimal_places = models.IntegerField(default=3, validators=[MinValueValidator(0)])
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_units_of_measure'
        ordering = ['unit_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'abbreviation'], 
                name='unique_tenant_uom_abbreviation'
            ),
            models.UniqueConstraint(
                fields=['tenant_id', 'name'], 
                name='unique_tenant_uom_name'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'unit_type', 'is_active']),
            models.Index(fields=['tenant_id', 'is_base_unit']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
    
    def convert_to_base(self, value):
        """Convert value to base unit"""
        if not self.base_unit:
            return Decimal(str(value))
        
        decimal_value = Decimal(str(value))
        return (decimal_value * self.conversion_factor) + self.conversion_offset
    
    def convert_from_base(self, value):
        """Convert from base unit to this unit"""
        if not self.base_unit:
            return Decimal(str(value))
        
        decimal_value = Decimal(str(value))
        return (decimal_value - self.conversion_offset) / self.conversion_factor
    
    def convert_to_unit(self, value, target_unit):
        """Convert value from this unit to target unit"""
        if self == target_unit:
            return Decimal(str(value))
        
        # Convert to base unit first
        base_value = self.convert_to_base(value)
        
        # Then convert to target unit
        return target_unit.convert_from_base(base_value)
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Base unit cannot have conversion factor other than 1
        if self.is_base_unit and self.conversion_factor != 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Base unit must have conversion factor of 1")
        
        # Cannot be its own base unit
        if self.base_unit == self:
            from django.core.exceptions import ValidationError
            raise ValidationError("Unit cannot be its own base unit")
    
    def save(self, *args, **kwargs):
        # Auto-set as base unit if no base unit specified
        if not self.base_unit:
            self.is_base_unit = True
            self.conversion_factor = Decimal('1')
            self.conversion_offset = Decimal('0')
        
        super().save(*args, **kwargs)


class UnitConversion(TenantBaseModel):
    """
    Unit conversion rules for automatic conversions between units
    """
    
    from_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name='conversions_from'
    )
    to_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name='conversions_to'
    )
    
    # Conversion Formula: (from_value * factor) + offset = to_value
    conversion_factor = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    conversion_offset = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    
    # Rounding and precision
    round_to_decimal_places = models.IntegerField(default=3)
    
    # Validation and notes
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_unit_conversions'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'from_unit', 'to_unit'],
                name='unique_unit_conversion'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'from_unit', 'is_active']),
            models.Index(fields=['tenant_id', 'to_unit', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.from_unit.symbol} → {self.to_unit.symbol} (×{self.conversion_factor})"
    
    def convert(self, value):
        """Convert a value from from_unit to to_unit"""
        from decimal import Decimal, ROUND_HALF_UP
        
        value = Decimal(str(value))
        result = (value * self.conversion_factor) + self.conversion_offset
        
        # Round to specified decimal places
        return result.quantize(
            Decimal('0.' + '0' * self.round_to_decimal_places),
            rounding=ROUND_HALF_UP
        )
    
    def reverse_convert(self, value):
        """Convert a value from to_unit back to from_unit"""
        from decimal import Decimal, ROUND_HALF_UP
        
        value = Decimal(str(value))
        result = (value - self.conversion_offset) / self.conversion_factor
        
        # Round to specified decimal places
        return result.quantize(
            Decimal('0.' + '0' * self.round_to_decimal_places),
            rounding=ROUND_HALF_UP
        )
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Cannot convert unit to itself
        if self.from_unit == self.to_unit:
            from django.core.exceptions import ValidationError
            raise ValidationError("Cannot convert unit to itself")
        
        # Units must be of the same type
        if self.from_unit.unit_type != self.to_unit.unit_type:
            from django.core.exceptions import ValidationError
            raise ValidationError("Can only convert between units of the same type")
    
    @classmethod
    def find_conversion_path(cls, from_unit, to_unit, tenant_id):
        """
        Find a conversion path between two units (direct or through intermediary units)
        Returns list of conversions to apply in sequence
        """
        # Try direct conversion first
        direct = cls.objects.filter(
            tenant_id=tenant_id,
            from_unit=from_unit,
            to_unit=to_unit,
            is_active=True
        ).first()
        
        if direct:
            return [direct]
        
        # Try reverse conversion
        reverse = cls.objects.filter(
            tenant_id=tenant_id,
            from_unit=to_unit,
            to_unit=from_unit,
            is_active=True
        ).first()
        
        if reverse:
            return [('reverse', reverse)]
        
        # For now, return empty list if no direct/reverse conversion found
        # Could implement graph traversal for multi-step conversions here
        return []