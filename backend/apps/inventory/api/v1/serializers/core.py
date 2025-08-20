from rest_framework import serializers
from django.db import transaction
from decimal import Decimal

from ....models import (
    InventorySettings, UnitOfMeasure, UnitConversion,
    Department, Category, SubCategory, Brand,
    ProductAttribute, AttributeValue
)
from .base import (
    TenantModelSerializer, AuditableSerializer, DynamicFieldsSerializerMixin,
    NestedWritableSerializerMixin
)

class InventorySettingsSerializer(AuditableSerializer):
    """Serializer for inventory settings"""
    
    class Meta:
        model = InventorySettings
        fields = [
            'id', 'tenant', 'default_costing_method', 'allow_negative_stock',
            'auto_generate_sku', 'sku_prefix', 'default_unit_of_measure',
            'enable_batch_tracking', 'enable_serial_tracking', 'enable_expiry_tracking',
            'enable_location_tracking', 'enable_multi_currency', 'default_currency',
            'inventory_turnover_periods', 'abc_analysis_method', 'reorder_point_method',
            'lead_time_calculation_method', 'enable_quality_control', 'enable_consignment',
            'enable_landed_costs', 'enable_kitting', 'notification_settings',
            'integration_settings', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_notification_settings(self, value):
        """Validate notification settings structure"""
        required_keys = ['email_alerts', 'sms_alerts', 'push_notifications']
        if not all(key in value for key in required_keys):
            raise serializers.ValidationError("Missing required notification settings")
        return value

class UnitOfMeasureSerializer(AuditableSerializer, DynamicFieldsSerializerMixin):
    """Serializer for units of measure"""
    
    conversion_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UnitOfMeasure
        fields = [
            'id', 'tenant', 'name', 'abbreviation', 'category', 'symbol',
            'is_base_unit', 'base_unit_conversion_factor', 'precision_digits',
            'is_active', 'conversion_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'conversion_count', 'created_at', 'updated_at']
    
    def get_conversion_count(self, obj):
        """Get number of conversion rules for this UOM"""
        return obj.from_conversions.count() + obj.to_conversions.count()

class UnitConversionSerializer(TenantModelSerializer):
    """Serializer for unit conversions"""
    
    from_unit_name = serializers.CharField(source='from_unit.name', read_only=True)
    to_unit_name = serializers.CharField(source='to_unit.name', read_only=True)
    
    class Meta:
        model = UnitConversion
        fields = [
            'id', 'tenant', 'from_unit', 'to_unit', 'conversion_factor',
            'formula', 'is_active', 'from_unit_name', 'to_unit_name'
        ]
        read_only_fields = ['id', 'tenant', 'from_unit_name', 'to_unit_name']
    
    def validate(self, attrs):
        """Validate conversion"""
        attrs = super().validate(attrs)
        
        from_unit = attrs.get('from_unit')
        to_unit = attrs.get('to_unit')
        
        if from_unit == to_unit:
            raise serializers.ValidationError("Cannot convert unit to itself")
        
        if from_unit and to_unit:
            if from_unit.category != to_unit.category:
                raise serializers.ValidationError("Cannot convert between different unit categories")
        
        return attrs

class DepartmentSerializer(AuditableSerializer, DynamicFieldsSerializerMixin):
    """Serializer for departments"""
    
    category_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = [
            'id', 'tenant', 'name', 'code', 'description', 'manager',
            'is_active', 'category_count', 'product_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'tenant', 'category_count', 'product_count',
                           'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_category_count(self, obj):
        """Get number of categories in this department"""
        return obj.category_set.filter(is_active=True).count()
    
    def get_product_count(self, obj):
        """Get number of products in this department"""
        return obj.product_set.filter(is_active=True).count()

class CategorySerializer(AuditableSerializer, DynamicFieldsSerializerMixin):
    """Serializer for categories"""
    
    department_name = serializers.CharField(source='department.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subcategory_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'tenant', 'department', 'parent', 'name', 'code', 'description',
            'image', 'sort_order', 'is_active', 'department_name', 'parent_name',
            'subcategory_count', 'product_count', 'full_path',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'tenant', 'department_name', 'parent_name',
                           'subcategory_count', 'product_count', 'full_path',
                           'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_subcategory_count(self, obj):
        """Get number of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    
    def get_product_count(self, obj):
        """Get number of products in this category"""
        return obj.product_set.filter(is_active=True).count()
    
    def get_full_path(self, obj):
        """Get full category path"""
        path_parts = []
        current = obj
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        return ' > '.join(path_parts)
    
    def validate(self, attrs):
        """Validate category"""
        attrs = super().validate(attrs)
        
        parent = attrs.get('parent')
        if parent and self.instance:
            # Prevent circular references
            if parent == self.instance or parent.is_descendant_of(self.instance):
                raise serializers.ValidationError("Cannot create circular category reference")
        
        return attrs

class SubCategorySerializer(AuditableSerializer):
    """Serializer for subcategories"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubCategory
        fields = [
            'id', 'tenant', 'category', 'name', 'code', 'description',
            'sort_order', 'is_active', 'category_name', 'product_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'tenant', 'category_name', 'product_count',
                           'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_product_count(self, obj):
        """Get number of products in this subcategory"""
        return obj.product_set.filter(is_active=True).count()

class BrandSerializer(AuditableSerializer, DynamicFieldsSerializerMixin):
    """Serializer for brands"""
    
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Brand
        fields = [
            'id', 'tenant', 'name', 'code', 'description', 'logo',
            'website', 'contact_email', 'contact_phone', 'is_active',
            'product_count', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'tenant', 'product_count',
                           'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_product_count(self, obj):
        """Get number of products for this brand"""
        return obj.product_set.filter(is_active=True).count()

class AttributeValueSerializer(TenantModelSerializer):
    """Serializer for attribute values"""
    
    class Meta:
        model = AttributeValue
        fields = ['id', 'tenant', 'attribute', 'value', 'sort_order']
        read_only_fields = ['id', 'tenant']

class ProductAttributeSerializer(AuditableSerializer, NestedWritableSerializerMixin):
    """Serializer for product attributes"""
    
    values = AttributeValueSerializer(many=True, read_only=True)
    value_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductAttribute
        fields = [
            'id', 'tenant', 'name', 'attribute_type', 'data_type',
            'is_required', 'is_filterable', 'is_searchable', 'sort_order',
            'validation_rules', 'default_value', 'help_text', 'is_active',
            'values', 'value_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'values', 'value_count',
                           'created_at', 'updated_at']
        nested_fields = ['values']
    
    def get_value_count(self, obj):
        """Get number of attribute values"""
        return obj.values.count()
    
    def _create_values(self, instance, values_data):
        """Create attribute values"""
            AttributeValue.objects.create(
                tenant=instance.tenant,
                attribute=instance,
                **value_data
            )
    
    def _update_values(self, instance, values_data):
        """Update attribute values"""
        # For simplicity, we'll delete existing and create new ones
        instance.values.all().delete()
        self._create_values(instance, values_data)

# Dashboard and KPI Serializers
class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary data"""
    
    total_products = serializers.IntegerField()
    total_stock_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_items = serializers.IntegerField()
    out_of_stock_items = serializers.IntegerField()
    pending_pos = serializers.IntegerField()
    pending_transfers = serializers.IntegerField()
    open_alerts = serializers.IntegerField()
    recent_movements = serializers.ListField()
    
class KPISerializer(serializers.Serializer):
    """Serializer for KPI data"""
    
    inventory_turnover = serializers.DecimalField(max_digits=10, decimal_places=2)
    days_in_inventory = serializers.DecimalField(max_digits=10, decimal_places=1)
    stock_accuracy = serializers.DecimalField(max_digits=5, decimal_places=2)
    fill_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    carrying_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    
class ChartDataSerializer(serializers.Serializer):
    """Serializer for chart data"""
    
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=serializers.DictField())
    
class BulkOperationResultSerializer(serializers.Serializer):
    """Serializer for bulk operation results"""
    
    success_count = serializers.IntegerField()
    error_count = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())
    created_ids = serializers.ListField(child=serializers.IntegerField())
    updated_ids = serializers.ListField(child=serializers.IntegerField())