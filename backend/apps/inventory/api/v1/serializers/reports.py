# apps/inventory/api/v1/serializers/reports.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.core.files.base import ContentFile
import json
from apps.inventory.models.reports.reports import InventoryReport
from .base import AuditableSerializer, DynamicFieldsSerializer

class ReportFilterSerializer(serializers.Serializer):
    """Serializer for report filter parameters."""
    
    # Date filters
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    date_range = serializers.ChoiceField(
        choices=[
            ('TODAY', 'Today'),
            ('YESTERDAY', 'Yesterday'),
            ('THIS_WEEK', 'This Week'),
            ('LAST_WEEK', 'Last Week'),
            ('THIS_MONTH', 'This Month'),
            ('LAST_MONTH', 'Last Month'),
            ('THIS_QUARTER', 'This Quarter'),
            ('LAST_QUARTER', 'Last Quarter'),
            ('THIS_YEAR', 'This Year'),
            ('LAST_YEAR', 'Last Year'),
            ('CUSTOM', 'Custom Range')
        ],
        required=False
    )
    
    # Location filters
    warehouse_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of warehouse IDs to include"
    )
    location_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of location IDs to include"
    )
    
    # Product filters
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of product IDs to include"
    )
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of category IDs to include"
    )
    brand_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of brand IDs to include"
    )
    supplier_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of supplier IDs to include"
    )
    
    # Product characteristics
    abc_classifications = serializers.ListField(
        child=serializers.ChoiceField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')]),
        required=False
    )
    velocity_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('FAST', 'Fast Moving'),
            ('MEDIUM', 'Medium Moving'),
            ('SLOW', 'Slow Moving'),
            ('DEAD', 'Dead Stock')
        ]),
        required=False
    )
    
    # Value filters
    min_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    max_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    min_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    # Stock status filters
    include_zero_stock = serializers.BooleanField(default=True)
    include_negative_stock = serializers.BooleanField(default=True)
    stock_status = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('NORMAL', 'Normal'),
            ('LOW_STOCK', 'Low Stock'),
            ('OUT_OF_STOCK', 'Out of Stock'),
            ('OVERSTOCK', 'Overstock')
        ]),
        required=False
    )
    
    # Movement type filters (for movement reports)
    movement_types = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    # Aging filters
    aging_periods = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=[30, 60, 90, 180]
    )
    
    # Grouping and sorting
    group_by = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('WAREHOUSE', 'Warehouse'),
            ('CATEGORY', 'Category'),
            ('BRAND', 'Brand'),
            ('SUPPLIER', 'Supplier'),
            ('ABC_CLASS', 'ABC Classification'),
            ('VELOCITY', 'Velocity Category'),
            ('DATE', 'Date'),
            ('MONTH', 'Month'),
            ('QUARTER', 'Quarter'),
            ('YEAR', 'Year')
        ]),
        required=False
    )
    sort_by = serializers.CharField(required=False)
    sort_order = serializers.ChoiceField(
        choices=[('ASC', 'Ascending'), ('DESC', 'Descending')],
        default='ASC'
    )
    
    def validate(self, data):
        """Cross-field validation for report filters."""
        # Validate date range
        if data.get('date_range') == 'CUSTOM':
            if not data.get('start_date') or not data.get('end_date'):
                raise serializers.ValidationError(
                    "start_date and end_date are required for custom date range"
                )
        
        # Validate date logic
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("start_date cannot be after end_date")
        
        # Validate value ranges
        min_value = data.get('min_value')
        max_value = data.get('max_value')
        if min_value and max_value and min_value > max_value:
            raise serializers.ValidationError("min_value cannot be greater than max_value")
        
        return data

class ReportConfigSerializer(serializers.Serializer):
    """Serializer for report configuration."""
    
    report_name = serializers.CharField(max_length=200)
    report_type = serializers.ChoiceField(choices=[
        ('STOCK_SUMMARY', 'Stock Summary'),
        ('VALUATION', 'Inventory Valuation'),
        ('MOVEMENT', 'Stock Movement'),
        ('ABC_ANALYSIS', 'ABC Analysis'),
        ('AGING', 'Inventory Aging'),
        ('REORDER', 'Reorder Recommendations'),
        ('SUPPLIER_PERFORMANCE', 'Supplier Performance'),
        ('CYCLE_COUNT', 'Cycle Count'),
        ('VARIANCE', 'Variance Analysis'),
        ('CUSTOM', 'Custom Report')
    ])
    description = serializers.CharField(required=False, allow_blank=True)
    
    # Report content configuration
    filters = ReportFilterSerializer()
    columns = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of columns to include in report"
    )
    calculations = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        help_text="List of calculated fields"
    )
    
    # Output configuration
    format = serializers.ChoiceField(
        choices=[
            ('JSON', 'JSON'),
            ('CSV', 'CSV'),
            ('EXCEL', 'Excel'),
            ('PDF', 'PDF'),
            ('HTML', 'HTML')
        ],
        default='JSON'
    )
    
    # Chart configuration
    include_charts = serializers.BooleanField(default=False)
    chart_config = serializers.JSONField(required=False)
    
    # Summary configuration
    include_summary = serializers.BooleanField(default=True)
    summary_calculations = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('SUM', 'Sum'),
            ('AVERAGE', 'Average'),
            ('COUNT', 'Count'),
            ('MIN', 'Minimum'),
            ('MAX', 'Maximum')
        ]),
        required=False
    )
    
    def validate_columns(self, value):
        """Validate report columns."""
        if not value:
            raise serializers.ValidationError("At least one column must be specified")
        
        # Define available columns by report type
        available_columns = {
            'STOCK_SUMMARY': [
                'product_name', 'product_sku', 'category', 'warehouse',
                'quantity_on_hand', 'quantity_reserved', 'quantity_available',
                'unit_cost', 'total_value', 'reorder_level'
            ],
            'VALUATION': [
                'product_name', 'product_sku', 'category', 'quantity',
                'unit_cost', 'total_value', 'valuation_method'
            ],
            'MOVEMENT': [
                'product_name', 'product_sku', 'movement_type', 'quantity',
                'warehouse', 'movement_date', 'reference', 'user'
            ],
            'ABC_ANALYSIS': [
                'product_name', 'product_sku', 'annual_usage_value',
                'abc_classification', 'percentage_of_total', 'cumulative_percentage'
            ]
        }
        
        report_type = self.initial_data.get('report_type')
        if report_type in available_columns:
            valid_columns = available_columns[report_type]
            invalid_columns = [col for col in value if col not in valid_columns]
            
            if invalid_columns:
                raise serializers.ValidationError(
                    f"Invalid columns for {report_type}: {invalid_columns}"
                )
        
        return value

class InventoryReportSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main inventory report serializer."""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    # Report metadata
    row_count = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    generation_time_seconds = serializers.SerializerMethodField()
    
    # Report content (for JSON reports)
    report_data = serializers.JSONField(read_only=True)
    summary_data = serializers.JSONField(read_only=True)
    
    class Meta:
        model = InventoryReport
        fields = [
            'id', 'report_name', 'report_type', 'description',
            'format', 'status', 'parameters', 'filters',
            'file_path', 'file_hash', 'expires_at',
            'row_count', 'file_size', 'generation_time_seconds',
            'report_data', 'summary_data', 'error_message',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'row_count', 'file_size', 'generation_time_seconds',
            'report_data', 'summary_data', 'file_hash'
        ]
    
    def get_row_count(self, obj):
        """Get number of data rows in report."""
        if obj.report_data and isinstance(obj.report_data, dict):
            return len(obj.report_data.get('data', []))
        return None
    
    def get_file_size(self, obj):
        """Get report file size in bytes."""
        if obj.file_path:
            try:
                import os
                return os.path.getsize(obj.file_path)
            except (OSError, AttributeError):
                return None
        return None
    
    def get_generation_time_seconds(self, obj):
        """Calculate report generation time."""
        if obj.created_at and obj.updated_at:
            delta = obj.updated_at - obj.created_at
            return delta.total_seconds()
        return None

class ReportScheduleSerializer(serializers.Serializer):
    """Serializer for scheduled report configuration."""
    
    schedule_name = serializers.CharField(max_length=200)
    report_config = ReportConfigSerializer()
    
    # Schedule settings
    frequency = serializers.ChoiceField(choices=[
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually')
    ])
    
    # Weekly settings
    day_of_week = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=6,
        help_text="0=Monday, 6=Sunday"
    )
    
    # Monthly settings
    day_of_month = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=31
    )
    
    # Time settings
    run_time = serializers.TimeField(default='09:00')
    timezone = serializers.CharField(default='UTC')
    
    # Recipients
    email_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False
    )
    user_recipients = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    role_recipients = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    # Advanced settings
    is_active = serializers.BooleanField(default=True)
    next_run_date = serializers.DateTimeField(required=False)
    retry_on_failure = serializers.BooleanField(default=True)
    max_retries = serializers.IntegerField(default=3, min_value=0, max_value=10)
    
    def validate(self, data):
        """Validate schedule configuration."""
        frequency = data.get('frequency')
        
        # Validate frequency-specific fields
        if frequency == 'WEEKLY' and not data.get('day_of_week'):
            raise serializers.ValidationError("day_of_week is required for weekly frequency")
        
        if frequency == 'MONTHLY' and not data.get('day_of_month'):
            raise serializers.ValidationError("day_of_month is required for monthly frequency")
        
        # Validate recipients
        email_recipients = data.get('email_recipients', [])
        user_recipients = data.get('user_recipients', [])
        role_recipients = data.get('role_recipients', [])
        
        if not any([email_recipients, user_recipients, role_recipients]):
            raise serializers.ValidationError("At least one recipient must be specified")
        
        return data

class CustomReportSerializer(serializers.Serializer):
    """Serializer for custom report builder."""
    
    # Data sources
    data_sources = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('PRODUCTS', 'Products'),
            ('STOCK_ITEMS', 'Stock Items'),
            ('MOVEMENTS', 'Stock Movements'),
            ('PURCHASE_ORDERS', 'Purchase Orders'),
            ('RECEIPTS', 'Stock Receipts'),
            ('TRANSFERS', 'Stock Transfers'),
            ('ADJUSTMENTS', 'Stock Adjustments'),
            ('CYCLE_COUNTS', 'Cycle Counts'),
            ('RESERVATIONS', 'Stock Reservations'),
            ('ALERTS', 'Inventory Alerts')
        ])
    )
    
    # Field selection
    selected_fields = serializers.ListField(
        child=serializers.JSONField(),
        help_text="List of field configurations"
    )
    
    # Join configuration
    joins = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        help_text="Join configurations between data sources"
    )
    
    # Filters and conditions
    conditions = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        help_text="Filter conditions"
    )
    
    # Grouping and aggregation
    group_by_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    aggregations = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        help_text="Aggregation configurations"
    )
    
    # Sorting
    sort_fields = serializers.ListField(
        child=serializers.JSONField(),
        required=False
    )
    
    # Formatting
    formatting_rules = serializers.JSONField(required=False)
    
    # Chart configuration
    chart_settings = serializers.JSONField(required=False)
    
    def validate_selected_fields(self, value):
        """Validate selected fields configuration."""
        if not value:
            raise serializers.ValidationError("At least one field must be selected")
        
        for field_config in value:
            required_keys = ['source', 'field_name', 'display_name']
            for key in required_keys:
                if key not in field_config:
                    raise serializers.ValidationError(f"Missing required key '{key}' in field config")
        
        return value
    
    def validate_conditions(self, value):
        """Validate filter conditions."""
        if not value:
            return value
        
        for condition in value:
            required_keys = ['field', 'operator', 'value']
            for key in required_keys:
                if key not in condition:
                    raise serializers.ValidationError(f"Missing required key '{key}' in condition")
            
            # Validate operator
            valid_operators = ['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN', 'NOT IN', 'IS NULL', 'IS NOT NULL']
            if condition['operator'] not in valid_operators:
                raise serializers.ValidationError(f"Invalid operator: {condition['operator']}")
        
        return value

class ReportTemplateSerializer(serializers.Serializer):
    """Serializer for report templates."""
    
    template_name = serializers.CharField(max_length=200)
    template_type = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True)
    
    # Template configuration
    template_config = serializers.JSONField()
    default_parameters = serializers.JSONField(required=False)
    
    # Template metadata
    is_public = serializers.BooleanField(default=False)
    category = serializers.CharField(required=False)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    # Usage tracking
    usage_count = serializers.IntegerField(read_only=True, default=0)
    last_used_at = serializers.DateTimeField(read_only=True, required=False)
    
    def validate_template_config(self, value):
        """Validate template configuration structure."""
        required_sections = ['filters', 'columns', 'format']
        
        for section in required_sections:
            if section not in value:
                raise serializers.ValidationError(f"Missing required section: {section}")
        
        return value

class ReportExportSerializer(serializers.Serializer):
    """Serializer for report export requests."""
    
    export_format = serializers.ChoiceField(choices=[
        ('CSV', 'CSV'),
        ('EXCEL', 'Excel'),
        ('PDF', 'PDF'),
        ('JSON', 'JSON')
    ])
    
    # Export options
    include_summary = serializers.BooleanField(default=True)
    include_charts = serializers.BooleanField(default=False)
    compress_file = serializers.BooleanField(default=False)
    
    # Delivery options
    delivery_method = serializers.ChoiceField(
        choices=[
            ('DOWNLOAD', 'Direct Download'),
            ('EMAIL', 'Email Delivery'),
            ('STORE', 'Store on Server')
        ],
        default='DOWNLOAD'
    )
    
    email_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False
    )
    
    # File options
    filename = serializers.CharField(required=False, max_length=200)
    password_protect = serializers.BooleanField(default=False)
    password = serializers.CharField(required=False, write_only=True)
    
    def validate(self, data):
        """Validate export configuration."""
        delivery_method = data.get('delivery_method')
        
        if delivery_method == 'EMAIL' and not data.get('email_recipients'):
            raise serializers.ValidationError("email_recipients required for email delivery")
        
        if data.get('password_protect') and not data.get('password'):
            raise serializers.ValidationError("password required when password_protect is True")
        
        return data