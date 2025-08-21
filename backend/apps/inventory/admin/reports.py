# apps/inventory/admin/reports.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone

from .base import BaseInventoryAdmin
from ..models.reports import InventoryReport
from ..utils.choices import REPORT_TYPE_CHOICES, REPORT_STATUS_CHOICES

@admin.register(InventoryReport)
class InventoryReportAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for inventory reports."""
    
    list_display = [
        'name', 'report_type', 'created_date', 'status_display',
        'file_info', 'generation_time', 'download_count',
        'auto_schedule_info', 'expiry_status'
    ]
    
    list_filter = [
        'report_type', 'status', 'output_format',
        'is_scheduled', 'is_public',
        ('created_at', admin.DateFieldListFilter),
        ('expires_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'name', 'description', 'created_by__username'
    ]
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'name', 'description', 'report_type', 'output_format'
            )
        }),
        ('Filters & Parameters', {
            'fields': (
                'filters', 'parameters'
            )
        }),
        ('Scheduling', {
            'fields': (
                'is_scheduled', 'schedule_frequency', 'schedule_time',
                'next_run_date'
            )
        }),
        ('Access & Sharing', {
            'fields': (
                'is_public', 'shared_with_users', 'expires_at'
            )
        }),
        ('Generated Report', {
            'fields': (
                'status', 'file_path', 'file_size', 'download_count',
                'generation_started_at', 'generation_completed_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'status', 'file_path', 'file_size', 'download_count',
        'generation_started_at', 'generation_completed_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = BaseInventoryAdmin.actions + [
        'generate_reports', 'regenerate_reports', 'schedule_reports',
        'share_reports', 'export_report_data', 'cleanup_expired'
    ]
    
    def get_urls(self):
        """Add custom URLs for report operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:report_id>/generate/',
                self.admin_site.admin_view(self.generate_report),
                name='report-generate'
            ),
            path(
                '<int:report_id>/download/',
                self.admin_site.admin_view(self.download_report),
                name='report-download'
            ),
            path(
                '<int:report_id>/preview/',
                self.admin_site.admin_view(self.preview_report),
                name='report-preview'
            ),
            path(
                'dashboard/',
                self.admin_site.admin_view(self.reports_dashboard),
                name='reports-dashboard'
            ),
        ]
        return custom_urls + urls
    
    def created_date(self, obj):
        """Show creation date with relative time."""
        age = timezone.now() - obj.created_at
        
        if age.days > 0:
            relative = f"{age.days}d ago"
        elif age.seconds > 3600:
            relative = f"{age.seconds // 3600}h ago"
        else:
            relative = f"{age.seconds // 60}m ago"
        
        return format_html(
            '{}<br/><small>{}</small>',
            obj.created_at.strftime('%m/%d/%Y %H:%M'),
            relative
        )
    created_date.short_description = 'Created'
    
    def status_display(self, obj):
        """Show status with progress indicators."""
        status_colors = {
            'PENDING': 'orange',
            'GENERATING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'EXPIRED': 'gray'
        }
        
        status_icons = {
            'PENDING': '⏳',
            'GENERATING': '⚙️',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'EXPIRED': '🗓️'
        }
        
        color = status_colors.get(obj.status, 'black')
        icon = status_icons.get(obj.status, '●')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def file_info(self, obj):
        """Show file information with download link."""
        if obj.status == 'COMPLETED' and obj.file_path:
            size_mb = (obj.file_size / 1024 / 1024) if obj.file_size else 0
            
            download_url = reverse(
                'admin:report-download',
                args=[obj.id]
            )
            
            return format_html(
                '<a href="{}" title="Download report">📁 {}</a><br/>'
                '<small>{:.1f} MB</small>',
                download_url, obj.get_output_format_display(), size_mb
            )
        elif obj.status == 'GENERATING':
            return format_html(
                '<span style="color: blue;">🔄 Generating...</span>'
            )
        elif obj.status == 'FAILED':
            return format_html(
                '<span style="color: red;">❌ Generation Failed</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">📄 Not Generated</span>'
            )
    file_info.short_description = 'File'
    
    def generation_time(self, obj):
        """Show report generation time."""
        if obj.generation_started_at and obj.generation_completed_at:
            duration = obj.generation_completed_at - obj.generation_started_at
            
            if duration.total_seconds() < 60:
                time_str = f"{duration.total_seconds():.1f}s"
            elif duration.total_seconds() < 3600:
                time_str = f"{duration.total_seconds() / 60:.1f}m"
            else:
                time_str = f"{duration.total_seconds() / 3600:.1f}h"
            
            return format_html(
                '<span style="color: green;">{}</span>',
                time_str
            )
        elif obj.generation_started_at:
            # Currently generating
            elapsed = timezone.now() - obj.generation_started_at
            return format_html(
                '<span style="color: blue;">⏱️ {:.0f}s</span>',
                elapsed.total_seconds()
            )
        
        return 'N/A'
    generation_time.short_description = 'Gen Time'
    
    def auto_schedule_info(self, obj):
        """Show scheduling information."""
        if not obj.is_scheduled:
            return format_html(
                '<span style="color: gray;">Manual</span>'
            )
        
        # Show next run time
        next_run = obj.next_run_date
        if next_run:
            if next_run < timezone.now():
                color = 'red'
                status = 'Overdue'
            else:
                color = 'green'
                status = 'Scheduled'
                
            return format_html(
                '<span style="color: {};">{}</span><br/>'
                '<small>{} | {}</small>',
                color, status,
                obj.get_schedule_frequency_display(),
                next_run.strftime('%m/%d %H:%M')
            )
        
        return format_html(
            '<span style="color: orange;">Setup Required</span>'
        )
    auto_schedule_info.short_description = 'Schedule'
    
    def expiry_status(self, obj):
        """Show expiry status."""
        if not obj.expires_at:
            return format_html(
                '<span style="color: gray;">No Expiry</span>'
            )
        
        time_to_expiry = obj.expires_at - timezone.now()
        
        if time_to_expiry.total_seconds() < 0:
            return format_html(
                '<span style="color: red;">Expired</span>'
            )
        elif time_to_expiry.days < 1:
            return format_html(
                '<span style="color: orange;">Today</span>'
            )
        elif time_to_expiry.days < 7:
            return format_html(
                '<span style="color: blue;">{} days</span>',
                time_to_expiry.days
            )
        else:
            return format_html(
                '<span style="color: green;">{} days</span>',
                time_to_expiry.days
            )
    expiry_status.short_description = 'Expires'
    
    def generate_reports(self, request, queryset):
        """Generate selected reports."""
        generated = 0
        for report in queryset.filter(status='PENDING'):
            # Trigger report generation
            report.status = 'GENERATING'
            report.generation_started_at = timezone.now()
            report.save()
            
            # Queue report generation task
            # generate_report_task.delay(report.id)
            generated += 1
        
        self.message_user(
            request,
            f'{generated} reports queued for generation.',
            messages.SUCCESS
        )
    generate_reports.short_description = "Generate reports"
    
    def regenerate_reports(self, request, queryset):
        """Regenerate completed reports."""
        regenerated = 0
        for report in queryset:
            report.status = 'GENERATING'
            report.generation_started_at = timezone.now()
            report.generation_completed_at = None
            report.file_path = None
            report.file_size = None
            report.save()
            
            # Queue report generation task
            # generate_report_task.delay(report.id)
            regenerated += 1
        
        self.message_user(
            request,
            f'{regenerated} reports queued for regeneration.',
            messages.SUCCESS
        )
    regenerate_reports.short_description = "Regenerate reports"
    
    def schedule_reports(self, request, queryset):
        """Enable scheduling for selected reports."""
        scheduled = queryset.update(is_scheduled=True)
        
        self.message_user(
            request,
            f'{scheduled} reports enabled for scheduling.',
            messages.SUCCESS
        )
    schedule_reports.short_description = "Enable scheduling"
    
    def download_report(self, request, report_id):
        """Download report file."""
        from django.shortcuts import get_object_or_404
        from django.http import FileResponse, Http404
        import os
        
        report = get_object_or_404(InventoryReport, id=report_id)
        
        if report.status != 'COMPLETED' or not report.file_path:
            raise Http404("Report not available for download")
        
        if not os.path.exists(report.file_path):
            raise Http404("Report file not found")
        
        # Increment download count
        report.download_count = (report.download_count or 0) + 1
        report.save()
        
        # Return file response
        response = FileResponse(
            open(report.file_path, 'rb'),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{report.name}.{report.output_format.lower()}"'
        
        return response
    
    def get_changelist_summary(self, request):
        """Get report summary statistics."""
        queryset = self.get_queryset(request)
        
        summary = queryset.aggregate(
            total_reports=Count('id'),
            completed_reports=Count('id', filter=Q(status='COMPLETED')),
            scheduled_reports=Count('id', filter=Q(is_scheduled=True)),
            total_downloads=Sum('download_count')
        )
        
        # Report type breakdown
        type_breakdown = queryset.values('report_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            **summary,
            'report_types': {
                item['report_type']: item['count'] 
                for item in type_breakdown
            }
        }