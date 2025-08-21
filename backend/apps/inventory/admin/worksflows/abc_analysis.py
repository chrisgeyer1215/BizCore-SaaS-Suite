# apps/inventory/admin/workflows/abc_analysis.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg, DecimalField
from django.db.models.functions import Coalesce
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
import csv

from ..base import BaseInventoryAdmin, InlineAdminMixin

class ABCAnalysisRun(models.Model):
    """Model for ABC analysis runs."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    analysis_name = models.CharField(max_length=200)
    
    # Analysis parameters
    analysis_period_start = models.DateField()
    analysis_period_end = models.DateField()
    analysis_method = models.CharField(
        max_length=30,
        choices=[
            ('SALES_VALUE', 'Sales Value'),
            ('USAGE_QUANTITY', 'Usage Quantity'),
            ('PROFIT_MARGIN', 'Profit Margin'),
            ('INVENTORY_VALUE', 'Inventory Value'),
            ('MOVEMENT_FREQUENCY', 'Movement Frequency')
        ],
        default='SALES_VALUE'
    )
    
    # Classification thresholds
    class_a_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80.00)  # 80%
    class_b_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=95.00)  # 95%
    # Class C is everything else (95-100%)
    
    # Filters
    warehouse_filter = models.ManyToManyField('inventory.Warehouse', blank=True)
    category_filter = models.ManyToManyField('inventory.Category', blank=True)
    supplier_filter = models.ManyToManyField('inventory.Supplier', blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('ARCHIVED', 'Archived')
        ],
        default='DRAFT'
    )
    
    # Results summary
    total_products_analyzed = models.IntegerField(default=0)
    class_a_count = models.IntegerField(default=0)
    class_b_count = models.IntegerField(default=0)
    class_c_count = models.IntegerField(default=0)
    
    class_a_value_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    class_b_value_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    class_c_value_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Processing info
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Auto-application
    auto_apply_results = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

class ABCAnalysisResult(models.Model):
    """Individual product results from ABC analysis."""
    analysis_run = models.ForeignKey(ABCAnalysisRun, on_delete=models.CASCADE, related_name='results')
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    
    # Analysis values
    analysis_value = models.DecimalField(max_digits=15, decimal_places=2)  # The value used for classification
    cumulative_value = models.DecimalField(max_digits=15, decimal_places=2)
    cumulative_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Classification
    previous_classification = models.CharField(max_length=1, blank=True)
    recommended_classification = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')]
    )
    
    # Supporting data
    quantity_sold = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    sales_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    inventory_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    movement_frequency = models.IntegerField(default=0)
    
    # Change indicators
    classification_changed = models.BooleanField(default=False)
    variance_from_previous = models.DecimalField(max_digits=5, decimal_places=2, default=0)

class ABCAnalysisResultInline(admin.TabularInline):
    """Inline for ABC analysis results."""
    model = ABCAnalysisResult
    fields = [
        'product', 'analysis_value', 'cumulative_percentage',
        'previous_classification', 'recommended_classification',
        'classification_changed'
    ]
    readonly_fields = [
        'analysis_value', 'cumulative_percentage', 'classification_changed'
    ]
    extra = 0
    max_num = 20  # Limit displayed results
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product').order_by('cumulative_percentage')

@admin.register(ABCAnalysisRun)
class ABCAnalysisWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for ABC analysis workflow."""
    
    list_display = [
        'analysis_name', 'analysis_method', 'analysis_period',
        'status_display', 'results_summary', 'classification_changes',
        'progress_indicator', 'performance_impact', 'actions_column'
    ]
    
    list_filter = [
        'analysis_method', 'status', 'auto_apply_results',
        ('analysis_period_start', admin.DateFieldListFilter),
        ('completed_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'analysis_name', 'created_by__username'
    ]
    
    inlines = [ABCAnalysisResultInline]
    
    fieldsets = (
        ('Analysis Configuration', {
            'fields': (
                'analysis_name', 'analysis_method',
                'analysis_period_start', 'analysis_period_end'
            )
        }),
        ('Classification Thresholds', {
            'fields': (
                'class_a_threshold', 'class_b_threshold'
            )
        }),
        ('Filters', {
            'fields': (
                'warehouse_filter', 'category_filter', 'supplier_filter'
            )
        }),
        ('Processing Options', {
            'fields': (
                'auto_apply_results', 'status'
            )
        }),
        ('Results Summary', {
            'fields': (
                'total_products_analyzed', 'class_a_count', 'class_b_count', 'class_c_count',
                'class_a_value_percentage', 'class_b_value_percentage', 'class_c_value_percentage'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'total_products_analyzed', 'class_a_count', 'class_b_count', 'class_c_count',
        'class_a_value_percentage', 'class_b_value_percentage', 'class_c_value_percentage',
        'started_at', 'completed_at', 'applied_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'run_analysis', 'apply_results', 'compare_with_previous',
        'export_results', 'create_reorder_policies', 'archive_analysis'
    ]
    
    def get_urls(self):
        """Add ABC analysis URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'abc-dashboard/',
                self.admin_site.admin_view(self.abc_dashboard),
                name='abc-dashboard'
            ),
            path(
                '<int:analysis_id>/run/',
                self.admin_site.admin_view(self.run_analysis),
                name='run-abc-analysis'
            ),
            path(
                '<int:analysis_id>/results/',
                self.admin_site.admin_view(self.analysis_results),
                name='abc-analysis-results'
            ),
            path(
                '<int:analysis_id>/visualization/',
                self.admin_site.admin_view(self.abc_visualization),
                name='abc-visualization'
            ),
            path(
                'trend-analysis/',
                self.admin_site.admin_view(self.trend_analysis),
                name='abc-trend-analysis'
            ),
        ]
        return custom_urls + urls
    
    def analysis_period(self, obj):
        """Show analysis period."""
        period_days = (obj.analysis_period_end - obj.analysis_period_start).days
        
        return format_html(
            '<div>'
            '{} to<br/>'
            '{}<br/>'
            '<small>({} days)</small>'
            '</div>',
            obj.analysis_period_start.strftime('%m/%d/%Y'),
            obj.analysis_period_end.strftime('%m/%d/%Y'),
            period_days
        )
    analysis_period.short_description = 'Analysis Period'
    
    def status_display(self, obj):
        """Show status with progress."""
        status_colors = {
            'DRAFT': 'gray',
            'RUNNING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'ARCHIVED': 'purple'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Add timing information
        if obj.status == 'RUNNING' and obj.started_at:
            elapsed = timezone.now() - obj.started_at
            elapsed_minutes = elapsed.total_seconds() / 60
            status_text = f"{obj.get_status_display()} ({elapsed_minutes:.0f}m)"
        elif obj.status == 'COMPLETED' and obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            duration_minutes = duration.total_seconds() / 60
            status_text = f"{obj.get_status_display()} ({duration_minutes:.0f}m)"
        else:
            status_text = obj.get_status_display()
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, status_text
        )
    status_display.short_description = 'Status'
    
    def results_summary(self, obj):
        """Show results summary."""
        if obj.status != 'COMPLETED':
            return 'Not completed'
        
        total = obj.total_products_analyzed
        if total == 0:
            return 'No results'
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            '<strong>Total: {}</strong><br/>'
            'A: <span style="color: red;">{} ({:.1f}%)</span><br/>'
            'B: <span style="color: orange;">{} ({:.1f}%)</span><br/>'
            'C: <span style="color: green;">{} ({:.1f}%)</span>'
            '</div>',
            total,
            obj.class_a_count, (obj.class_a_count / total * 100) if total > 0 else 0,
            obj.class_b_count, (obj.class_b_count / total * 100) if total > 0 else 0,
            obj.class_c_count, (obj.class_c_count / total * 100) if total > 0 else 0
        )
    results_summary.short_description = 'Results Summary'
    
    def classification_changes(self, obj):
        """Show classification changes."""
        if obj.status != 'COMPLETED':
            return 'N/A'
        
        changes = obj.results.filter(classification_changed=True).count()
        total = obj.total_products_analyzed
        
        if changes == 0:
            return format_html(
                '<span style="color: green;">No changes</span>'
            )
        
        change_percentage = (changes / total * 100) if total > 0 else 0
        
        # Break down changes by type
        a_to_b = obj.results.filter(
            previous_classification='A',
            recommended_classification='B'
        ).count()
        
        a_to_c = obj.results.filter(
            previous_classification='A',
            recommended_classification='C'
        ).count()
        
        b_to_a = obj.results.filter(
            previous_classification='B',
            recommended_classification='A'
        ).count()
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            '<strong style="color: orange;">{} changes ({:.1f}%)</strong><br/>'
            'A→B: {} | A→C: {}<br/>'
            'B→A: {} | Others: {}'
            '</div>',
            changes, change_percentage,
            a_to_b, a_to_c, b_to_a,
            changes - (a_to_b + a_to_c + b_to_a)
        )
    classification_changes.short_description = 'Changes'
    
    def progress_indicator(self, obj):
        """Show analysis progress."""
        if obj.status == 'DRAFT':
            return format_html(
                '<span style="color: gray;">📝 Ready to run</span>'
            )
        elif obj.status == 'RUNNING':
            return format_html(
                '<span style="color: blue;">🔄 Processing...</span>'
            )
        elif obj.status == 'COMPLETED':
            if obj.applied_at:
                return format_html(
                    '<span style="color: green;">✅ Applied</span>'
                )
            else:
                return format_html(
                    '<span style="color: orange;">⏳ Pending Application</span>'
                )
        elif obj.status == 'FAILED':
            return format_html(
                '<span style="color: red;">❌ Failed</span>'
            )
        else:
            return format_html(
                '<span style="color: purple;">📦 Archived</span>'
            )
    progress_indicator.short_description = 'Progress'
    
    def performance_impact(self, obj):
        """Show expected performance impact."""
        if obj.status != 'COMPLETED':
            return 'N/A'
        
        # Calculate Pareto efficiency
        pareto_ratio = obj.class_a_value_percentage / (obj.class_a_count / obj.total_products_analyzed * 100) if obj.total_products_analyzed > 0 else 0
        
        if pareto_ratio > 4:  # 80/20 rule
            efficiency = "Excellent"
            color = "green"
        elif pareto_ratio > 3:
            efficiency = "Good"
            color = "blue"
        elif pareto_ratio > 2:
            efficiency = "Fair"
            color = "orange"
        else:
            efficiency = "Poor"
            color = "red"
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Efficiency: <span style="color: {}; font-weight: bold;">{}</span><br/>'
            'A-Class Value: <strong>{:.1f}%</strong><br/>'
            'Pareto Ratio: {:.1f}'
            '</div>',
            color, efficiency, obj.class_a_value_percentage, pareto_ratio
        )
    performance_impact.short_description = 'Impact'
    
    def actions_column(self, obj):
        """Show action buttons."""
        buttons = []
        
        if obj.status == 'DRAFT':
            buttons.append(
                f'<a href="/admin/inventory/abcanalysisrun/{obj.id}/run/" '
                f'class="button" style="font-size: 0.8em; padding: 2px 6px;">Run Analysis</a>'
            )
        
        if obj.status == 'COMPLETED' and not obj.applied_at:
            buttons.append(
                '<button onclick="applyABCResults({})" class="button" '
                'style="font-size: 0.8em; padding: 2px 6px;">Apply Results</button>'.format(obj.id)
            )
        
        if obj.status == 'COMPLETED':
            buttons.append(
                f'<a href="/admin/inventory/abcanalysisrun/{obj.id}/visualization/" '
                f'class="button" style="font-size: 0.8em; padding: 2px 6px;">View Chart</a>'
            )
        
        return format_html('<br/>'.join(buttons)) if buttons else '-'
    actions_column.short_description = 'Actions'
    
    def run_analysis(self, request, queryset):
        """Run ABC analysis for selected runs."""
        from ...services import ABCAnalysisService
        
        started = 0
        for analysis_run in queryset.filter(status='DRAFT'):
            analysis_run.status = 'RUNNING'
            analysis_run.started_at = timezone.now()
            analysis_run.save()
            
            # Queue analysis task
            abc_service = ABCAnalysisService()
            try:
                results = abc_service.run_abc_analysis(analysis_run)
                analysis_run.status = 'COMPLETED'
                analysis_run.completed_at = timezone.now()
                analysis_run.save()
                started += 1
            except Exception as e:
                analysis_run.status = 'FAILED'
                analysis_run.error_message = str(e)
                analysis_run.save()
        
        self.message_user(
            request,
            f'{started} ABC analyses completed.',
            messages.SUCCESS
        )
    run_analysis.short_description = "Run ABC analysis"
    
    def apply_results(self, request, queryset):
        """Apply ABC analysis results to products."""
        applied = 0
        
        for analysis_run in queryset.filter(status='COMPLETED', applied_at__isnull=True):
            # Apply classifications to products
            for result in analysis_run.results.all():
                result.product.abc_classification = result.recommended_classification
                result.product.save(update_fields=['abc_classification'])
            
            analysis_run.applied_at = timezone.now()
            analysis_run.save()
            applied += 1
        
        self.message_user(
            request,
            f'ABC classifications applied for {applied} analyses.',
            messages.SUCCESS
        )
    apply_results.short_description = "Apply results to products"
    
    def abc_visualization(self, request, analysis_id):
        """Generate ABC visualization data."""
        analysis_run = get_object_or_404(ABCAnalysisRun, id=analysis_id)
        
        if analysis_run.status != 'COMPLETED':
            return JsonResponse({'error': 'Analysis not completed'})
        
        # Prepare data for charts
        results = analysis_run.results.select_related('product').order_by('cumulative_percentage')
        
        chart_data = {
            'pareto_chart': {
                'labels': [result.product.sku for result in results[:50]],  # Top 50
                'values': [float(result.analysis_value) for result in results[:50]],
                'cumulative': [float(result.cumulative_percentage) for result in results[:50]]
            },
            'classification_pie': {
                'labels': ['Class A', 'Class B', 'Class C'],
                'values': [analysis_run.class_a_count, analysis_run.class_b_count, analysis_run.class_c_count],
                'value_percentages': [
                    float(analysis_run.class_a_value_percentage),
                    float(analysis_run.class_b_value_percentage),
                    float(analysis_run.class_c_value_percentage)
                ]
            },
            'value_distribution': {
                'class_a': {
                    'count': analysis_run.class_a_count,
                    'value_percentage': float(analysis_run.class_a_value_percentage),
                    'items': [
                        {
                            'sku': result.product.sku,
                            'name': result.product.name,
                            'value': float(result.analysis_value)
                        }
                        for result in results.filter(recommended_classification='A')[:10]
                    ]
                },
                'class_b': {
                    'count': analysis_run.class_b_count,
                    'value_percentage': float(analysis_run.class_b_value_percentage)
                },
                'class_c': {
                    'count': analysis_run.class_c_count,
                    'value_percentage': float(analysis_run.class_c_value_percentage)
                }
            }
        }
        
        return JsonResponse(chart_data)