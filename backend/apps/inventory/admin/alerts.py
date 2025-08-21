# apps/inventory/admin/alerts.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.urls import reverse, path
from django.contrib import messages
from django.utils import timezone

from .base import BaseInventoryAdmin
from ..models.alerts import InventoryAlert
from ..utils.choices import ALERT_TYPE_CHOICES, ALERT_SEVERITY_CHOICES

@admin.register(InventoryAlert)
class InventoryAlertAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for inventory alerts."""
    
    list_display = [
        'alert_type', 'severity_display', 'product_info', 
        'warehouse', 'alert_message_short', 'status_display',
        'created_date', 'acknowledged_status', 'auto_resolve_status'
    ]
    
    list_filter = [
        'alert_type', 'severity', 'status', 'warehouse',
        'is_acknowledged', 'is_auto_resolved',
        ('created_at', admin.DateFieldListFilter),
        ('acknowledged_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'product__name', 'product__sku', 'alert_message',
        'warehouse__name', 'acknowledged_by__username'
    ]
    
    fieldsets = (
        ('Alert Information', {
            'fields': (
                'alert_type', 'severity', 'product', 'warehouse',
                'alert_message'
            )
        }),
        ('Alert Data', {
            'fields': (
                'current_value', 'threshold_value', 'variance_percentage'
            )
        }),
        ('Status & Resolution', {
            'fields': (
                'status', 'is_acknowledged', 'acknowledged_by',
                'acknowledged_at', 'is_auto_resolved', 'resolved_at'
            )
        }),
        ('Actions Taken', {
            'fields': (
                'actions_taken', 'resolution_notes'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'acknowledged_by', 'acknowledged_at', 'resolved_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = BaseInventoryAdmin.actions + [
        'acknowledge_alerts', 'resolve_alerts', 'escalate_alerts',
        'mark_false_positive', 'create_reorder_suggestions'
    ]
    
    def get_urls(self):
        """Add custom URLs for alert operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.alert_dashboard),
                name='alert-dashboard'
            ),
            path(
                'trends/',
                self.admin_site.admin_view(self.alert_trends),
                name='alert-trends'
            ),
            path(
                'bulk-resolve/',
                self.admin_site.admin_view(self.bulk_resolve),
                name='alert-bulk-resolve'
            ),
        ]
        return custom_urls + urls
    
    def severity_display(self, obj):
        """Show severity with color coding."""
        severity_colors = {
            'LOW': 'green',
            'MEDIUM': 'orange',
            'HIGH': 'red',
            'CRITICAL': 'darkred'
        }
        
        severity_icons = {
            'LOW': '●',
            'MEDIUM': '⚠️',
            'HIGH': '🔴',
            'CRITICAL': '🚨'
        }
        
        color = severity_colors.get(obj.severity, 'black')
        icon = severity_icons.get(obj.severity, '●')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_severity_display()
        )
    severity_display.short_description = 'Severity'
    
    def product_info(self, obj):
        """Show product information with link."""
        if obj.product:
            product_url = reverse(
                'admin:inventory_product_change', 
                args=[obj.product.id]
            )
            return format_html(
                '<a href="{}" title="{}">{}</a><br/><small>{}</small>',
                product_url, obj.product.description or '',
                obj.product.name, obj.product.sku
            )
        return 'System Alert'
    product_info.short_description = 'Product'
    
    def alert_message_short(self, obj):
        """Show truncated alert message."""
        if len(obj.alert_message) > 50:
            return format_html(
                '<span title="{}">{}</span>',
                obj.alert_message,
                obj.alert_message[:50] + '...'
            )
        return obj.alert_message
    alert_message_short.short_description = 'Message'
    
    def status_display(self, obj):
        """Show alert status with indicators."""
        status_colors = {
            'ACTIVE': 'red',
            'ACKNOWLEDGED': 'orange',
            'RESOLVED': 'green',
            'FALSE_POSITIVE': 'gray'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Add age indicator
        age_days = (timezone.now() - obj.created_at).days
        age_indicator = ""
        
        if obj.status == 'ACTIVE' and age_days > 7:
            age_indicator = f" ({age_days}d old)"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}{}'.format(
                color, obj.get_status_display(), age_indicator
            )
        )
    status_display.short_description = 'Status'
    
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
            obj.created_at.strftime('%m/%d %H:%M'),
            relative
        )
    created_date.short_description = 'Created'
    
    def acknowledged_status(self, obj):
        """Show acknowledgment status."""
        if obj.is_acknowledged:
            return format_html(
                '<span style="color: green;">✓ {}</span><br/>'
                '<small>{}</small>',
                obj.acknowledged_by.get_full_name() if obj.acknowledged_by else 'System',
                obj.acknowledged_at.strftime('%m/%d %H:%M') if obj.acknowledged_at else ''
            )
        elif obj.status == 'ACTIVE':
            return format_html(
                '<span style="color: red;">❌ Pending</span>'
            )
        return format_html(
            '<span style="color: gray;">N/A</span>'
        )
    acknowledged_status.short_description = 'Acknowledged'
    
    def auto_resolve_status(self, obj):
        """Show auto-resolution status."""
        if obj.is_auto_resolved:
            return format_html(
                '<span style="color: blue;">🤖 Auto</span>'
            )
        elif obj.status == 'RESOLVED':
            return format_html(
                '<span style="color: green;">👤 Manual</span>'
            )
        return format_html(
            '<span style="color: gray;">N/A</span>'
        )
    auto_resolve_status.short_description = 'Resolution'
    
    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        acknowledged = queryset.filter(
            status='ACTIVE',
            is_acknowledged=False
        ).update(
            is_acknowledged=True,
            acknowledged_by=request.user,
            acknowledged_at=timezone.now(),
            status='ACKNOWLEDGED'
        )
        
        self.message_user(
            request,
            f'{acknowledged} alerts acknowledged.',
            messages.SUCCESS
        )
    acknowledge_alerts.short_description = "Acknowledge alerts"
    
    def resolve_alerts(self, request, queryset):
        """Resolve selected alerts."""
        resolved = queryset.filter(
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        ).update(
            status='RESOLVED',
            resolved_at=timezone.now()
        )
        
        self.message_user(
            request,
            f'{resolved} alerts resolved.',
            messages.SUCCESS
        )
    resolve_alerts.short_description = "Resolve alerts"
    
    def escalate_alerts(self, request, queryset):
        """Escalate selected alerts."""
        escalated = 0
        severity_escalation = {
            'LOW': 'MEDIUM',
            'MEDIUM': 'HIGH',
            'HIGH': 'CRITICAL'
        }
        
        for alert in queryset.filter(status='ACTIVE'):
            if alert.severity in severity_escalation:
                alert.severity = severity_escalation[alert.severity]
                alert.save()
                escalated += 1
        
        self.message_user(
            request,
            f'{escalated} alerts escalated.',
            messages.SUCCESS
        )
    escalate_alerts.short_description = "Escalate severity"
    
    def mark_false_positive(self, request, queryset):
        """Mark selected alerts as false positives."""
        marked = queryset.filter(
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        ).update(
            status='FALSE_POSITIVE',
            resolved_at=timezone.now()
        )
        
        self.message_user(
            request,
            f'{marked} alerts marked as false positives.',
            messages.SUCCESS
        )
    mark_false_positive.short_description = "Mark as false positive"
    
    def create_reorder_suggestions(self, request, queryset):
        """Create reorder suggestions for low stock alerts."""
        suggestions_created = 0
        
        for alert in queryset.filter(
            alert_type__in=['LOW_STOCK', 'OUT_OF_STOCK'],
            status='ACTIVE'
        ):
            # Logic to create reorder suggestion
            # This would integrate with purchasing module
            suggestions_created += 1
        
        self.message_user(
            request,
            f'{suggestions_created} reorder suggestions created.',
            messages.SUCCESS
        )
    create_reorder_suggestions.short_description = "Create reorder suggestions"
    
    def get_changelist_summary(self, request):
        """Get alert summary statistics."""
        queryset = self.get_queryset(request)
        
        summary = queryset.aggregate(
            total_alerts=Count('id'),
            active_alerts=Count('id', filter=Q(status='ACTIVE')),
            critical_alerts=Count('id', filter=Q(severity='CRITICAL')),
            acknowledged_alerts=Count('id', filter=Q(is_acknowledged=True)),
            auto_resolved=Count('id', filter=Q(is_auto_resolved=True))
        )
        
        # Alert type breakdown
        type_breakdown = queryset.values('alert_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            **summary,
            'alert_types': {
                item['alert_type']: item['count'] 
                for item in type_breakdown
            }
        }