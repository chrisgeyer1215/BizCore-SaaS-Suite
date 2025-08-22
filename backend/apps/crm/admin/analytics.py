# ============================================================================
# backend/apps/crm/admin/analytics.py - Advanced Analytics Admin Views
# ============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
import json

from .base import TenantAwareAdmin, BaseModelAdmin
from ..models import Report, Dashboard, AuditLog, TaskExecution


class ReportAdmin(TenantAwareAdmin):
    """Advanced report management with scheduling and sharing"""
    
    list_display = [
        'name', 'report_type', 'is_template', 'is_scheduled',
        'last_generated', 'generation_time', 'status_indicator'
    ]
    
    list_filter = ['report_type', 'is_template', 'is_scheduled', 'created_at']
    search_fields = ['name', 'description']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('name', 'description', 'report_type', 'is_template')
        }),
        ('Configuration', {
            'fields': ('configuration', 'parameters')
        }),
        ('Scheduling', {
            'fields': ('is_scheduled', 'schedule_frequency', 'schedule_recipients'),
            'classes': ('collapse',)
        }),
        ('Sharing', {
            'fields': ('is_public', 'shared_with_users', 'shared_with_roles'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['last_generated', 'generation_time']
    
    def get_form(self, request, obj=None, **kwargs):
        """Enhanced form with JSON editor"""
        form = super().get_form(request, obj, **kwargs)
        
        # Add JavaScript for JSON editing
        class Media:
            js = ('admin/js/json-editor.js',)
            css = {'all': ('admin/css/json-editor.css',)}
        
        form.Media = Media
        return form


class DashboardAdmin(TenantAwareAdmin):
    """Advanced dashboard management"""
    
    list_display = [
        'name', 'dashboard_type', 'is_default', 'widget_count',
        'last_accessed', 'access_count', 'status_indicator'
    ]
    
    list_filter = ['dashboard_type', 'is_default', 'is_public']
    search_fields = ['name', 'description']
    
    def get_queryset(self, request):
        """Add widget count annotation"""
        return super().get_queryset(request).annotate(
            widget_count=Count('widgets')
        )
    
    def widget_count(self, obj):
        """Display widget count"""
        return obj.widget_count
    
    widget_count.short_description = 'Widgets'
    widget_count.admin_order_field = 'widget_count'


class AuditLogAdmin(BaseModelAdmin):
    """Comprehensive audit log viewer with advanced filtering"""
    
    list_display = [
        'timestamp', 'event_type', 'event_subtype', 'user', 'object_type',
        'object_id', 'ip_address', 'result_indicator'
    ]
    
    list_filter = [
        'event_type', 'event_subtype', 'result',
        ('timestamp', admin.DateFieldListFilter),
        'user', 'tenant'
    ]
    
    search_fields = ['user__username', 'object_type', 'ip_address', 'additional_data']
    date_hierarchy = 'timestamp'
    
    readonly_fields = [
        'timestamp', 'event_type', 'event_subtype', 'user', 'tenant',
        'object_type', 'object_id', 'ip_address', 'user_agent',
        'additional_data_formatted'
    ]
    
    def has_add_permission(self, request):
        """Audit logs cannot be manually created"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs cannot be modified"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete audit logs"""
        return request.user.is_superuser
    
    def result_indicator(self, obj):
        """Visual indicator for audit result"""
        if obj.additional:
                data = json.loads(obj.additional_data)
                result = data.get('result', True)
                
                if result:
                    return format_html('<span style="color: green;">✓</span>')
                else:
                    return format_html('<span style="color: red;">✗</span>')
            except:
                pass
        
        return '-'
    
    result_indicator.short_description = 'Result'
    
    def additional_data_formatted(self, obj):
        """Format additional data as readable JSON"""
        if obj.additional_data = json.loads(obj.additional_data)
                formatted = json.dumps(data, indent=2)
                return format_html('<pre>{}</pre>', formatted)
            except:
                return obj.additional_data
        return 'No additional data'
    
    additional_data_formatted.short_description = 'Additional Data'


class TaskExecutionAdmin(BaseModelAdmin):
    """Task execution monitoring and management"""
    
    list_display = [
        'task_name', 'status', 'started_at', 'execution_time_display',
        'worker_name', 'user', 'tenant', 'status_indicator'
    ]
    
    list_filter = [
        'status', 'task_name', 'worker_name',
        ('started_at', admin.DateFieldListFilter)
    ]
    
    search_fields = ['task_id', 'task_name', 'worker_name', 'user__username']
    date_hierarchy = 'started_at'
    
    readonly_fields = [
        'task_id', 'task_name', 'status', 'started_at', 'completed_at',
        'execution_time_seconds', 'worker_name', 'queue_name',
        'arguments', 'result_formatted', 'memory_usage_mb', 'cpu_time_seconds'
    ]
    
    def has_add_permission(self, request):
        """Task executions cannot be manually created"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Task executions cannot be modified"""
        return False
    
    def execution_time_display(self, obj):
        """Format execution time for display"""
        if obj.execution_time_seconds:
            if obj.execution_time_seconds < 60:
                return f'{obj.execution_time_seconds:.1f}s'
            else:
                minutes = obj.execution_time_seconds // 60
                seconds = obj.execution_time_seconds % 60
                return f'{int(minutes)}m {seconds:.1f}s'
        return '-'
    
    execution_time_display.short_description = 'Duration'
    execution_time_display.admin_order_field = 'execution_time_seconds'
    
    def result_formatted(self, obj):
        """Format task result for display"""
        if obj.result:
            try:
                if isinstance(obj.result, str):
                    result_data = json.loads(obj.result)
                else:
                    result_data = obj.result
                
                formatted = json.dumps(result_data, indent=2)
                return format_html('<pre style="max-height: 300px; overflow-y: auto;">{}</pre>', formatted)
            except:
                return obj.result
        return 'No result data'
    
    result_formatted.short_description = 'Result Data'
    
    actions = ['retry_failed_tasks', 'export_task_logs']
    
    def retry_failed_tasks(self, request, queryset):
        """Retry selected failed tasks"""
        failed_tasks = queryset.filter(status='FAILED')
        
        retry_count = 0
        for task_execution in failed_tasks:
            try:
                # Get the task function and retry
                from ..tasks import get_task_by_name
                task_func = get_task_by_name(task_execution.task_name)
                
                if task_func:
                    # Parse arguments
                    args_data = json.loads(task_execution.arguments)
                    args = args_data.get('args', [])
                    kwargs = args_data.get('kwargs', {})
                    
                    # Retry the task
                    task_func.delay(*args, **kwargs)
                    retry_count += 1
            except Exception as e:
                self.message_user(request, f'Failed to retry task {task_execution.task_name}: {e}', level='ERROR')
        
        if retry_count > 0:
            self.message_user(request, f'Retried {retry_count} failed tasks.')
    
    retry_failed_tasks.short_description = "Retry selected failed tasks"