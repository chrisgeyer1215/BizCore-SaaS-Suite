# ============================================================================
# backend/apps/crm/serializers/system.py - System Management Serializers
# ============================================================================

from rest_framework import serializers
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from ..models import CustomField, AuditTrail, DataExportLog, APIUsageLog, SyncLog
from .user import UserBasicSerializer


class CustomFieldSerializer(serializers.ModelSerializer):
    """Custom field configuration serializer"""
    
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    usage_count = serializers.SerializerMethodField()
    field_configuration = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomField
        fields = [
            'id', 'name', 'label', 'field_type', 'content_type',
            'content_type_name', 'is_required', 'default_value',
            'field_options', 'validation_rules', 'help_text',
            'sort_order', 'is_active', 'usage_count',
            'field_configuration',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'content_type_name', 'usage_count', 'field_configuration',
            'created_at', 'updated_at'
        ]
    
    def get_usage_count(self, obj):
        """Get usage count for this custom field"""
        # This would require tracking field usage in actual records
        return 0  # Placeholder
    
    def get_field_configuration(self, obj):
        """Get field configuration summary"""
        config = {
            'type': obj.field_type,
            'required': obj.is_required,
            'has_default': bool(obj.default_value),
            'has_options': bool(obj.field_options),
            'has_validation': bool(obj.validation_rules)
        }
        
        # Add type-specific configuration
        if obj.field_type in ['SELECT', 'MULTI_SELECT']:
            config['options_count'] = len(obj.field_options) if obj.field_options else 0
        elif obj.field_type == 'NUMBER':
            if obj.validation_rules:
                config['min_value'] = obj.validation_rules.get('min')
                config['max_value'] = obj.validation_rules.get('max')
        
        return config
    
    def validate_field_options(self, value):
        """Validate field options"""
        if self.initial_data.get('field_type') in ['SELECT', 'MULTI_SELECT']:
            if not value or not isinstance(value, list):
                raise serializers.ValidationError("Field options are required for select fields")
            
            if len(value) < 1:
                raise serializers.ValidationError("At least one option is required")
        
        return value


class AuditTrailSerializer(serializers.ModelSerializer):
    """Audit trail serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    
    # Change analysis
    changes_summary = serializers.SerializerMethodField()
    impact_level = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditTrail
        fields = [
            'id', 'action', 'content_type', 'content_type_name',
            'object_id', 'object_repr', 'user', 'user_details',
            'timestamp', 'ip_address', 'user_agent',
            'changes', 'changes_summary', 'impact_level',
            'session_key', 'additional_data'
        ]
        read_only_fields = [
            'id', 'content_type_name', 'user_details', 'changes_summary',
            'impact_level'
        ]
    
    def get_changes_summary(self, obj):
        """Get summary of changes"""
        if not obj.changes:
            return {'fields_changed': 0, 'has_sensitive_changes': False}
        
        changes = obj.changes if isinstance(obj.changes, dict) else {}
        fields_changed = len(changes)
        
        # Check for sensitive fields
        sensitive_fields = ['password', 'email', 'phone', 'ssn', 'credit_card']
        has_sensitive_changes = any(
            field in sensitive_fields for field in changes.keys()
        )
        
        return {
            'fields_changed': fields_changed,
            'has_sensitive_changes': has_sensitive_changes,
            'field_names': list(changes.keys())
        }
    
    def get_impact_level(self, obj):
        """Determine impact level of the change"""
        if obj.action == 'DELETE':
            return 'High'
        elif obj.action == 'CREATE':
            return 'Medium'
        elif obj.action == 'UPDATE':
            changes_summary = self.get_changes_summary(obj)
            if changes_summary['has_sensitive_changes']:
                return 'High'
            elif changes_summary['fields_changed'] > 5:
                return 'Medium'
            else:
                return 'Low'
        return 'Low'


class DataExportLogSerializer(serializers.ModelSerializer):
    """Data export log serializer"""
    
    exported_by_details = UserBasicSerializer(source='exported_by', read_only=True)
    
    # Export analysis
    export_summary = serializers.SerializerMethodField()
    file_size_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = DataExportLog
        fields = [
            'id', 'export_type', 'file_format', 'filters_applied',
            'record_count', 'file_size', 'file_size_formatted',
            'file_path', 'download_url', 'exported_by',
            'exported_by_details', 'exported_at', 'expires_at',
            'download_count', 'last_downloaded', 'export_summary',
            'is_successful', 'error_message'
        ]
        read_only_fields = [
            'id', 'exported_by_details', 'file_size_formatted',
            'export_summary'
        ]
    
    def get_export_summary(self, obj):
        """Get export summary"""
        return {
            'type': obj.export_type,
            'format': obj.file_format,
            'records': obj.record_count,
            'size_mb': round(obj.file_size / (1024 * 1024), 2) if obj.file_size else 0,
            'downloads': obj.download_count,
            'status': 'Success' if obj.is_successful else 'Failed',
            'has_filters': bool(obj.filters_applied)
        }
    
    def get_file_size_formatted(self, obj):
        """Get human-readable file size"""
        if not obj.file_size:
            return "0 B"
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class APIUsageLogSerializer(serializers.ModelSerializer):
    """API usage log serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    
    # Request analysis
    performance_metrics = serializers.SerializerMethodField()
    request_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = APIUsageLog
        fields = [
            'id', 'user', 'user_details', 'endpoint', 'method',
            'status_code', 'response_time_ms', 'request_size',
            'response_size', 'ip_address', 'user_agent',
            'timestamp', 'request_data', 'response_data',
            'error_message', 'performance_metrics', 'request_summary'
        ]
        read_only_fields = [
            'id', 'user_details', 'performance_metrics', 'request_summary'
        ]
    
    def get_performance_metrics(self, obj):
        """Get performance metrics"""
        return {
            'response_time_ms': obj.response_time_ms,
            'performance_level': 'Fast' if obj.response_time_ms < 500 else 'Medium' if obj.response_time_ms < 2000 else 'Slow',
            'request_size_kb': round(obj.request_size / 1024, 2) if obj.request_size else 0,
            'response_size_kb': round(obj.response_size / 1024, 2) if obj.response_size else 0,
            'is_error': obj.status_code >= 400,
            'is_success': 200 <= obj.status_code < 300
        }
    
    def get_request_summary(self, obj):
        """Get request summary"""
        return {
            'method': obj.method,
            'endpoint': obj.endpoint,
            'status': obj.status_code,
            'success': 200 <= obj.status_code < 300,
            'has_error': bool(obj.error_message),
            'user_type': 'Authenticated' if obj.user else 'Anonymous'
        }


class SyncLogSerializer(serializers.ModelSerializer):
    """Synchronization log serializer"""
    
    sync_summary = serializers.SerializerMethodField()
    performance_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = SyncLog
        fields = [
            'id', 'sync_type', 'direction', 'external_system',
            'status', 'started_at', 'completed_at', 'records_processed',
            'records_created', 'records_updated', 'records_failed',
            'error_details', 'sync_data', 'sync_summary',
            'performance_analysis'
        ]
        read_only_fields = ['id', 'sync_summary', 'performance_analysis']
    
    def get_sync_summary(self, obj):
        """Get synchronization summary"""
        total_records = obj.records_processed or 0
        success_rate = 0
        if total_records > 0:
            failed_records = obj.records_failed or 0
            success_rate = ((total_records - failed_records) / total_records) * 100
        
        return {
            'type': obj.sync_type,
            'direction': obj.direction,
            'system': obj.external_system,
            'status': obj.status,
            'success_rate': success_rate,
            'total_records': total_records,
            'created': obj.records_created or 0,
            'updated': obj.records_updated or 0,
            'failed': obj.records_failed or 0
        }
    
    def get_performance_analysis(self, obj):
        """Get performance analysis"""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            duration_seconds = duration.total_seconds()
            
            records_per_second = 0
            if duration_seconds > 0 and obj.records_processed:
                records_per_second = obj.records_processed / duration_seconds
            
            return {
                'duration_seconds': int(duration_seconds),
                'duration_formatted': str(duration),
                'records_per_second': round(records_per_second, 2),
                'performance_level': 'Fast' if records_per_second > 10 else 'Medium' if records_per_second > 1 else 'Slow'
            }
        
        return {'duration_seconds': 0, 'records_per_second': 0}


class SystemAnalyticsSerializer(serializers.Serializer):
    """System analytics serializer"""
    
    date_range = serializers.CharField(required=False, default='30d')
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'api_usage', 'export_activity', 'audit_trail',
            'sync_performance', 'custom_fields_usage', 'system_health'
        ]),
        required=False,
        default=['api_usage', 'export_activity', 'system_health']
    )
    
    def validate_date_range(self, value):
        """Validate date range"""
        valid_ranges = ['7d', '30d', '90d', '180d', '1y']
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Date range must be one of: {', '.join(valid_ranges)}")
        return value


class SystemHealthSerializer(serializers.Serializer):
    """System health check serializer"""
    
    check_database = serializers.BooleanField(default=True)
    check_integrations = serializers.BooleanField(default=True)
    check_storage = serializers.BooleanField(default=True)
    check_performance = serializers.BooleanField(default=True)
    
    def validate(self, data):
        """Validate health check parameters"""
        if not any(data.values()):
            raise serializers.ValidationError("At least one health check must be enabled")
        return data