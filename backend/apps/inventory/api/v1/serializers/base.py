from rest_framework import serializers
from rest_framework.fields import empty
from django.utils import timezone
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TenantModelSerializer(serializers.ModelSerializer):
    """Base serializer for tenant-aware models"""
    
    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance, data, **kwargs)
        self.tenant = self.context.get('tenant') if self.context else None
        self.user = self.context.get('user') if self.context else None
    
    def validate(self, attrs):
        """Add tenant validation"""
        attrs = super().validate(attrs)
        
        # Ensure tenant is set for creation
        if not self.instance and self.tenant:
            attrs['tenant'] = self.tenant
        
        return attrs
    
    def create(self, validated_data):
        """Override create to handle tenant and user context"""
        # Set tenant and user context on instance
        if self.tenant:
            validated_data['tenant'] = self.tenant
        
        instance = super().create(validated_data)
        
        # Set current user context for signals
        if self.user:
            instance._current_user = self.user
        
        return instance
    
    def update(self, instance, validated_data):
        """Override update to handle user context"""
        # Set current user context for signals
        if self.user:
            instance._current_user = self.user
        
        return super().update(instance, validated_data)

class DynamicFieldsSerializerMixin:
    """
    Mixin to dynamically include/exclude fields based on request parameters
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.context:
            return
            
        request = self.context.get('request')
        if not request:
            return
        
        # Handle field inclusion/exclusion
        fields_param = request.query_params.get('fields')
        exclude_param = request.query_params.get('exclude')
        
        if fields_param:
            # Only include specified fields
            fields = fields_param.split(',')
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)
        
        elif exclude_param:
            # Exclude specified fields
            exclude = exclude_param.split(',')
            for field_name in exclude:
                self.fields.pop(field_name, None)

class TimestampedSerializer(TenantModelSerializer):
    """Serializer for models with timestamps"""
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        abstract = True

class AuditableSerializer(TimestampedSerializer):
    """Serializer for auditable models"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        abstract = True

class BulkOperationSerializer(serializers.Serializer):
    """Base serializer for bulk operations"""
    
    operation = serializers.ChoiceField(choices=[
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ])
    data = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=1000  # Configurable limit
    )
    
    def validate_data(self, value):
        """Validate bulk data"""
        if len(value) > 1000:
            raise serializers.ValidationError("Maximum 1000 items allowed per bulk operation")
        
        return value

class NestedWritableSerializerMixin:
    """
    Mixin for handling nested writable serializers
    """
    
    def create(self, validated_data):
        """Handle nested object creation"""
        nested_data = self._extract_nested_data(validated_data)
        instance = super().create(validated_data)
        self._create_nested_objects(instance, nested_data)
        return instance
    
    def update(self, instance, validated_data):
        """Handle nested object updates"""
        nested_data = self._extract_nested_data(validated_data)
        instance = super().update(instance, validated_data)
        self._update_nested_objects(instance, nested_data)
        return instance
    
    def _extract_nested_data(self, validated_data):
        """Extract nested data from validated data"""
        nested_data = {}
        
        # Get nested field names from serializer
        nested_fields = getattr(self.Meta, 'nested_fields', [])
        
        for field_name in nested_fields:pop(field_name)
        
        return nested_data
    
    def _create_nested_objects(self, instance, nested_data):
        """Create nested objects"""
        for field_name, data in nested_data.items():
            if hasattr(self, f'_create_{field_name}'):
                getattr(self, f'_create_{field_name}')(instance, data)
    
    def _update_nested_objects(self, instance, nested_data):
        """Update nested objects"""
        for field_name, data in nested_data.items():
            if hasattr(self, f'_update_{field_name}'):
                getattr(self, f'_update_{field_name}')(instance, data)

class ValidationErrorSerializer(serializers.Serializer):
    """Serializer for validation errors"""
    
    field = serializers.CharField()
    message = serializers.CharField()
    code = serializers.CharField(required=False)

class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    error = serializers.CharField()
    message = serializers.CharField()
    details = serializers.ListField(
        child=ValidationErrorSerializer(),
        required=False
    )
    timestamp = serializers.DateTimeField()

class SuccessResponseSerializer(serializers.Serializer):
    """Serializer for success responses"""
    
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(default=timezone.now)

class PaginatedResponseSerializer(serializers.Serializer):
    """Serializer for paginated responses"""
    
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField()

class FileUploadSerializer(serializers.Serializer):
    """Serializer for file uploads"""
    
    file = serializers.FileField()
    description = serializers.CharField(max_length=255, required=False)
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # File size validation (10MB limit)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB")
        
        # File type validation
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'text/csv', 
                        'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        
        if hasattr(value, 'content_type') and value.content_type not in allowed_types:
            raise serializers.ValidationError("File type not supported")
        
        return value

class ExportSerializer(serializers.Serializer):
    """Serializer for export operations"""
    
    format = serializers.ChoiceField(choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON')
    ])
    filters = serializers.DictField(required=False)
    fields = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
class ImportSerializer(serializers.Serializer):
    """Serializer for import operations"""
    
    file = serializers.FileField()
    format = serializers.ChoiceField(choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON')
    ])
    mapping = serializers.DictField(required=False)
    skip_header = serializers.BooleanField(default=True)
    dry_run = serializers.BooleanField(default=False)

class SearchSerializer(serializers.Serializer):
    """Serializer for search operations"""
    
    query = serializers.CharField(max_length=255)
    fields = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    filters = serializers.DictField(required=False)
    sort_by = serializers.CharField(required=False)
    sort_order = serializers.ChoiceField(
        choices=[('asc', 'Ascending'), ('desc', 'Descending')],
        default='asc'
    )

class DateRangeSerializer(serializers.Serializer):
    """Serializer for date range filters"""
    
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, attrs):
        """Validate date range"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check if range is not too large (e.g., more than 1 year)
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError("Date range cannot exceed 1 year")
        
        return attrs

class FilterSerializer(serializers.Serializer):
    """Base serializer for filters"""
    
    search = serializers.CharField(max_length=255, required=False)
    ordering = serializers.CharField(max_length=100, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=1000, required=False)

def create_response_serializer(data_serializer_class, many=False):
    """
    Factory function to create response serializers
    """
    class ResponseSerializer(serializers.Serializer):
        success = serializers.BooleanField(default=True)
        message = serializers.CharField()
        data = data_serializer_class(many=many) if data_serializer_class else serializers.DictField()
        timestamp = serializers.DateTimeField(default=timezone.now)
    
    return ResponseSerializer

def create_error_response(message: str, details: Dict[str, Any] = None):
    """
    Helper function to create standardized error responses
    """
    return {
        'success': False,
        'error': message,
        'details': details or {},
        'timestamp': timezone.now()
    }

def create_success_response(message to create standardized success responses
    """
    return {
        'success': True,
        'message': message,
        'data': data,
        'timestamp': timezone.now()
    }

class MetadataSerializer(serializers.Serializer):
    """Serializer for response metadata"""
    
    total_count = serializers.IntegerField()
    page_count = serializers.IntegerField()
    current_page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()

class EnumChoiceField(serializers.ChoiceField):
    """Custom field for handling enum choices"""
    
    def __init__(self, enum_class, **kwargs):
        self.enum_class = enum_class
        choices = [(choice.value, choice.name) for choice in enum_class]
        super().__init__(choices=choices, **kwargs)
    
    def to_representation(self, value):
        """Convert internal value to representation"""
        return value
    
    def to_internal_value(self, data):
        """Convert representation to internal value"""
        try:
            return self.enum_class(data)
        except ValueError:
            self.fail('invalid_choice', input=data)

class DecimalField(serializers.DecimalField):
    """Enhanced decimal field with better validation"""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 15)
        kwargs.setdefault('decimal_places', 4)
        super().__init__(**kwargs)
    
    def validate_empty_values(self, data):
        """Handle empty values appropriately"""
        if data == '' or data is None:
            if self.required:
                self.fail('required')
            return (True, None)
        return (False, data)