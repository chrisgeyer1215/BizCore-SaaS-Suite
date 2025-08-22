"""
Base serializer classes for e-commerce functionality
"""

from rest_framework import serializers
from rest_framework.fields import SerializerMethodField
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from apps.core.mixins import TenantMixin


class EcommerceBaseSerializer(serializers.Serializer):
    """Base serializer for e-commerce models"""
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def validate_tenant(self, value):
        """Validate tenant field"""
        if not value:
            raise serializers.ValidationError("Tenant is required")
        return value
    
    def get_tenant_from_context(self):
        """Get tenant from serializer context"""
        return self.context.get('tenant') if self.context else None


class EcommerceModelSerializer(serializers.ModelSerializer):
    """Base model serializer for e-commerce models"""
    
    class Meta:
        abstract = True
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def validate_tenant(self, value):
        """Validate tenant field"""
        if not value:
            raise serializers.ValidationError("Tenant is required")
        return value
    
    def get_tenant_from_context(self):
        """Get tenant from serializer context"""
        return self.context.get('tenant') if self.context else None
    
    def create(self, validated_data):
        """Create instance with tenant validation"""
        tenant = self.get_tenant_from_context()
        if tenant:
            validated_data['tenant'] = tenant
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update instance with tenant validation"""
        tenant = self.get_tenant_from_context()
        if tenant and hasattr(instance, 'tenant'):
            if instance.tenant != tenant:
                raise serializers.ValidationError("Cannot update object from different tenant")
        return super().update(instance, validated_data)


class TenantAwareSerializer(EcommerceModelSerializer):
    """Serializer that automatically handles tenant assignment"""
    
    def create(self, validated_data):
        """Automatically assign tenant from context"""
        tenant = self.get_tenant_from_context()
        if tenant:
            validated_data['tenant'] = tenant
        return super().create(validated_data)


class AuditSerializer(EcommerceModelSerializer):
    """Serializer with audit fields"""
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(read_only=True)
    updated_by = serializers.CharField(read_only=True)
    
    def create(self, validated_data):
        """Set audit fields on creation"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user.username
            validated_data['updated_by'] = request.user.username
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Set audit fields on update"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['updated_by'] = request.user.username
        return super().update(instance, validated_data)


class StatusSerializer(EcommerceModelSerializer):
    """Serializer with status fields"""
    
    status = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_published = serializers.BooleanField(read_only=True)
    
    def validate_status(self, value):
        """Validate status field"""
        valid_statuses = getattr(self.Meta.model, 'STATUS_CHOICES', [])
        if valid_statuses and value not in [choice[0] for choice in valid_statuses]:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join([choice[0] for choice in valid_statuses])}")
        return value


class SEOSerializer(EcommerceModelSerializer):
    """Serializer with SEO fields"""
    
    seo_title = serializers.CharField(max_length=60, required=False)
    seo_description = serializers.CharField(max_length=160, required=False)
    seo_keywords = serializers.CharField(max_length=255, required=False)
    canonical_url = serializers.URLField(required=False)
    
    def validate_seo_title(self, value):
        """Validate SEO title length"""
        if value and len(value) > 60:
            raise serializers.ValidationError("SEO title must be 60 characters or less")
        return value
    
    def validate_seo_description(self, value):
        """Validate SEO description length"""
        if value and len(value) > 160:
            raise serializers.ValidationError("SEO description must be 160 characters or less")
        return value


class PricingSerializer(EcommerceModelSerializer):
    """Serializer with pricing fields"""
    
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    compare_at_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    cost_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    currency = serializers.CharField(max_length=3, default='USD')
    
    def validate(self, attrs):
        """Validate pricing logic"""
        price = attrs.get('price', 0)
        compare_at_price = attrs.get('compare_at_price')
        cost_price = attrs.get('cost_price')
        
        if compare_at_price and compare_at_price <= price:
            raise serializers.ValidationError("Compare at price must be higher than regular price")
        
        if cost_price and cost_price > price:
            raise serializers.ValidationError("Cost price cannot be higher than selling price")
        
        return attrs


class InventorySerializer(EcommerceModelSerializer):
    """Serializer with inventory fields"""
    
    stock_quantity = serializers.IntegerField(min_value=0, required=False)
    low_stock_threshold = serializers.IntegerField(min_value=0, required=False)
    out_of_stock_threshold = serializers.IntegerField(min_value=0, required=False)
    track_quantity = serializers.BooleanField(default=True)
    inventory_policy = serializers.CharField(max_length=20, required=False)
    
    def validate(self, attrs):
        """Validate inventory logic"""
        stock_quantity = attrs.get('stock_quantity', 0)
        low_threshold = attrs.get('low_stock_threshold')
        out_threshold = attrs.get('out_of_stock_threshold')
        
        if low_threshold and out_threshold and low_threshold <= out_threshold:
            raise serializers.ValidationError("Low stock threshold must be higher than out of stock threshold")
        
        if low_threshold and stock_quantity < low_threshold:
            attrs['is_low_stock'] = True
        
        if out_threshold and stock_quantity <= out_threshold:
            attrs['is_out_of_stock'] = True
        
        return attrs


class ImageSerializer(EcommerceModelSerializer):
    """Serializer with image fields"""
    
    image = serializers.ImageField(required=False)
    alt_text = serializers.CharField(max_length=255, required=False)
    caption = serializers.CharField(max_length=500, required=False)
    is_featured = serializers.BooleanField(default=False)
    position = serializers.IntegerField(min_value=0, required=False)
    
    def validate_image(self, value):
        """Validate image file"""
        if value:
            # Check file size (5MB limit)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Image file size must be 5MB or less")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError("Only JPEG, PNG, GIF, and WebP images are allowed")
        
        return value


class CustomFieldSerializer(EcommerceModelSerializer):
    """Serializer with custom fields support"""
    
    custom_fields = serializers.JSONField(required=False)
    
    def validate_custom_fields(self, value):
        """Validate custom fields JSON"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Custom fields must be a valid JSON object")
        return value


class BulkOperationSerializer(serializers.Serializer):
    """Serializer for bulk operations"""
    
    action = serializers.ChoiceField(choices=[
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('delete', 'Delete'),
        ('update', 'Update'),
        ('export', 'Export'),
        ('import', 'Import'),
    ])
    ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        help_text="List of object IDs to perform action on"
    )
    filters = serializers.DictField(required=False, help_text="Additional filters to apply")
    update_data = serializers.DictField(required=False, help_text="Data to update objects with")
    
    def validate_ids(self, value):
        """Validate ID list"""
        if not value:
            raise serializers.ValidationError("At least one ID must be provided")
        return value
    
    def validate(self, attrs):
        """Validate bulk operation data"""
        action = attrs.get('action')
        update_data = attrs.get('update_data')
        
        if action == 'update' and not update_data:
            raise serializers.ValidationError("Update data is required for update action")
        
        return attrs


class PaginationSerializer(serializers.Serializer):
    """Serializer for pagination parameters"""
    
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    ordering = serializers.CharField(required=False, help_text="Field to order by (prefix with - for descending)")
    search = serializers.CharField(required=False, help_text="Search query")
    
    def validate_page_size(self, value):
        """Validate page size"""
        if value > 100:
            raise serializers.ValidationError("Page size cannot exceed 100")
        return value


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    error = serializers.CharField(help_text="Error message")
    code = serializers.CharField(required=False, help_text="Error code")
    details = serializers.DictField(required=False, help_text="Additional error details")
    timestamp = serializers.DateTimeField(default=timezone.now, help_text="Error timestamp")


class SuccessResponseSerializer(serializers.Serializer):
    """Serializer for success responses"""
    
    message = serializers.CharField(help_text="Success message")
    data = serializers.DictField(required=False, help_text="Response data")
    timestamp = serializers.DateTimeField(default=timezone.now, help_text="Response timestamp")
