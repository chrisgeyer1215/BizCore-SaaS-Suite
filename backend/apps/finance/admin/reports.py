"""
Finance Reports Admin
Admin interface for financial reports and analytics
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from decimal import Decimal

from ..models import (
    FinancialReport, ReportSchedule, ReportTemplate, ReportParameter,
    ReportExport, ReportLog, DashboardWidget, FinancialMetric
)


@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    """Admin for financial reports"""
    list_display = [
        'name', 'report_type', 'status', 'generated_date', 'generated_by',
        'file_size', 'tenant'
    ]
    list_filter = [
        'report_type', 'status', 'generated_date', 'tenant'
    ]
    search_fields = ['name', 'description', 'generated_by__username']
    readonly_fields = ['generated_date', 'file_size', 'generated_by']
    date_hierarchy = 'generated_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'report_type')
        }),
        ('Generation', {
            'fields': ('generated_date', 'generated_by', 'status', 'file_size')
        }),
        ('Parameters', {
            'fields': ('parameters', 'filters_applied'),
            'classes': ('collapse',)
        }),
        ('File Information', {
            'fields': ('report_file', 'file_format', 'file_path'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'generated_by'
        )
    
    def file_size(self, obj):
        """Display file size in human readable format"""
        if obj.report_file:
            size = obj.report_file.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size.short_description = 'File Size'


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    """Admin for report schedules"""
    list_display = [
        'name', 'report_type', 'frequency', 'next_run', 'is_active',
        'last_run_status', 'tenant'
    ]
    list_filter = [
        'frequency', 'is_active', 'last_run_status', 'tenant'
    ]
    search_fields = ['name', 'description', 'report_type']
    readonly_fields = ['next_run', 'last_run', 'last_run_status']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'report_type')
        }),
        ('Schedule Configuration', {
            'fields': ('frequency', 'cron_expression', 'timezone', 'is_active')
        }),
        ('Parameters', {
            'fields': ('default_parameters', 'recipients', 'email_template')
        }),
        ('Execution', {
            'fields': ('next_run', 'last_run', 'last_run_status', 'last_error'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')
    
    def last_run_status(self, obj):
        """Display last run status with color coding"""
        if obj.last_run_status == 'SUCCESS':
            return format_html('<span style="color: green;">✓ Success</span>')
        elif obj.last_run_status == 'FAILED':
            return format_html('<span style="color: red;">✗ Failed</span>')
        elif obj.last_run_status == 'RUNNING':
            return format_html('<span style="color: blue;">⟳ Running</span>')
        else:
            return format_html('<span style="color: gray;">- Never Run</span>')
    last_run_status.short_description = 'Last Run Status'


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """Admin for report templates"""
    list_display = [
        'name', 'report_type', 'version', 'is_default', 'created_by',
        'created_date', 'tenant'
    ]
    list_filter = [
        'report_type', 'is_default', 'created_date', 'tenant'
    ]
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_date', 'created_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'report_type')
        }),
        ('Template Details', {
            'fields': ('version', 'is_default', 'template_file', 'template_type')
        }),
        ('Configuration', {
            'fields': ('default_parameters', 'styling_options', 'layout_config')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_date', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'created_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReportParameter)
class ReportParameterAdmin(admin.ModelAdmin):
    """Admin for report parameters"""
    list_display = [
        'name', 'report_type', 'parameter_type', 'is_required',
        'default_value', 'tenant'
    ]
    list_filter = [
        'parameter_type', 'is_required', 'report_type', 'tenant'
    ]
    search_fields = ['name', 'description', 'report_type']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'report_type')
        }),
        ('Parameter Configuration', {
            'fields': ('parameter_type', 'is_required', 'default_value')
        }),
        ('Validation', {
            'fields': ('validation_rules', 'allowed_values', 'min_value', 'max_value')
        }),
        ('Display', {
            'fields': ('display_order', 'help_text', 'is_hidden')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    """Admin for report exports"""
    list_display = [
        'report', 'export_format', 'exported_date', 'exported_by',
        'file_size', 'download_count', 'tenant'
    ]
    list_filter = [
        'export_format', 'exported_date', 'tenant'
    ]
    search_fields = ['report__name', 'exported_by__username']
    readonly_fields = ['exported_date', 'exported_by', 'file_size', 'download_count']
    date_hierarchy = 'exported_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'report', 'export_format')
        }),
        ('Export Details', {
            'fields': ('exported_date', 'exported_by', 'file_size', 'download_count')
        }),
        ('File Information', {
            'fields': ('export_file', 'file_path', 'expires_at')
        }),
        ('Access Control', {
            'fields': ('is_public', 'access_token', 'download_limit'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'report', 'exported_by'
        )
    
    def file_size(self, obj):
        """Display file size in human readable format"""
        if obj.export_file:
            size = obj.export_file.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size.short_description = 'File Size'


@admin.register(ReportLog)
class ReportLogAdmin(admin.ModelAdmin):
    """Admin for report logs"""
    list_display = [
        'report', 'action', 'status', 'user', 'timestamp', 'duration',
        'tenant'
    ]
    list_filter = [
        'action', 'status', 'timestamp', 'tenant'
    ]
    search_fields = ['report__name', 'user__username', 'details']
    readonly_fields = ['timestamp', 'duration', 'user']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'report', 'action', 'status')
        }),
        ('Execution Details', {
            'fields': ('timestamp', 'duration', 'user', 'ip_address')
        }),
        ('Additional Information', {
            'fields': ('details', 'error_message', 'parameters_used')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'report', 'user'
        )
    
    def duration(self, obj):
        """Display duration in human readable format"""
        if obj.duration:
            if obj.duration < 1:
                return f"{obj.duration * 1000:.0f}ms"
            else:
                return f"{obj.duration:.2f}s"
        return "N/A"
    duration.short_description = 'Duration'


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    """Admin for dashboard widgets"""
    list_display = [
        'name', 'widget_type', 'is_active', 'refresh_interval',
        'created_by', 'tenant'
    ]
    list_filter = [
        'widget_type', 'is_active', 'refresh_interval', 'tenant'
    ]
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'widget_type')
        }),
        ('Configuration', {
            'fields': ('is_active', 'refresh_interval', 'position', 'size')
        }),
        ('Data Source', {
            'fields': ('data_source', 'parameters', 'filters')
        }),
        ('Display Options', {
            'fields': ('chart_type', 'color_scheme', 'display_options')
        }),
        ('Access Control', {
            'fields': ('is_public', 'allowed_users', 'allowed_groups'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'created_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FinancialMetric)
class FinancialMetricAdmin(admin.ModelAdmin):
    """Admin for financial metrics"""
    list_display = [
        'name', 'metric_type', 'calculation_method', 'is_active',
        'last_calculated', 'tenant'
    ]
    list_filter = [
        'metric_type', 'calculation_method', 'is_active', 'tenant'
    ]
    search_fields = ['name', 'description', 'formula']
    readonly_fields = ['last_calculated']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'metric_type')
        }),
        ('Calculation', {
            'fields': ('calculation_method', 'formula', 'parameters')
        }),
        ('Configuration', {
            'fields': ('is_active', 'calculation_frequency', 'thresholds')
        }),
        ('Display', {
            'fields': ('unit', 'decimal_places', 'format_string')
        }),
        ('Metadata', {
            'fields': ('last_calculated', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


# Custom admin actions
@admin.action(description="Activate selected report schedules")
def activate_report_schedules(modeladmin, request, queryset):
    """Activate selected report schedules"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} report schedules activated.')


@admin.action(description="Deactivate selected report schedules")
def deactivate_report_schedules(modeladmin, request, queryset):
    """Deactivate selected report schedules"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} report schedules deactivated.')


@admin.action(description="Mark selected reports as archived")
def archive_reports(modeladmin, request, queryset):
    """Mark selected reports as archived"""
    updated = queryset.update(status='ARCHIVED')
    modeladmin.message_user(request, f'{updated} reports marked as archived.')


@admin.action(description="Activate selected dashboard widgets")
def activate_dashboard_widgets(modeladmin, request, queryset):
    """Activate selected dashboard widgets"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} dashboard widgets activated.')


@admin.action(description="Deactivate selected dashboard widgets")
def deactivate_dashboard_widgets(modeladmin, request, queryset):
    """Deactivate selected dashboard widgets"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} dashboard widgets deactivated.')


# Add actions to admin classes
ReportScheduleAdmin.actions = [activate_report_schedules, deactivate_report_schedules]
FinancialReportAdmin.actions = [archive_reports]
DashboardWidgetAdmin.actions = [activate_dashboard_widgets, deactivate_dashboard_widgets]
