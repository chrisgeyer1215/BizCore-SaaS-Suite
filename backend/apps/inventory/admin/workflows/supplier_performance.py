# apps/inventory/admin/workflows/supplier_performance.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg, Case, When, DecimalField
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from ..base import BaseInventoryAdmin, InlineAdminMixin

class SupplierPerformanceScore(models.Model):
    """Model for supplier performance scoring."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.CASCADE)
    
    # Evaluation period
    evaluation_period_start = models.DateField()
    evaluation_period_end = models.DateField()
    
    # Performance metrics
    delivery_performance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    cost_competitiveness_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    service_level_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    communication_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    
    # Weighted overall score
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Performance tier
    performance_tier = models.CharField(
        max_length=20,
        choices=[
            ('STRATEGIC', 'Strategic Partner'),
            ('PREFERRED', 'Preferred'),
            ('APPROVED', 'Approved'),
            ('CONDITIONAL', 'Conditional'),
            ('PROBATION', 'On Probation'),
            ('TERMINATED', 'Terminated')
        ],
        default='APPROVED'
    )
    
    # Key metrics data
    total_orders = models.IntegerField(default=0)
    total_order_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    on_time_deliveries = models.IntegerField(default=0)
    late_deliveries = models.IntegerField(default=0)
    quality_issues = models.IntegerField(default=0)
    returns_count = models.IntegerField(default=0)
    returns_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Lead time metrics
    avg_lead_time_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lead_time_variance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Cost metrics
    price_stability = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # % variance
    cost_savings_delivered = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Compliance metrics
    documentation_compliance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    certification_status = models.CharField(max_length=50, blank=True)
    audit_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Action items
    improvement_areas = models.TextField(blank=True)
    action_plan = models.TextField(blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('UNDER_REVIEW', 'Under Review'),
            ('APPROVED', 'Approved'),
            ('DISPUTED', 'Disputed'),
            ('ARCHIVED', 'Archived')
        ],
        default='DRAFT'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='approved_supplier_scores')
    approved_at = models.DateTimeField(null=True, blank=True)

class SupplierPerformanceMetric(models.Model):
    """Individual metric tracking for supplier performance."""
    performance_score = models.ForeignKey(SupplierPerformanceScore, on_delete=models.CASCADE, related_name='metrics')
    
    metric_name = models.CharField(max_length=100)
    metric_category = models.CharField(
        max_length=30,
        choices=[
            ('DELIVERY', 'Delivery'),
            ('QUALITY', 'Quality'),
            ('COST', 'Cost'),
            ('SERVICE', 'Service'),
            ('COMMUNICATION', 'Communication'),
            ('COMPLIANCE', 'Compliance')
        ]
    )
    
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    actual_value = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20)
    
    score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)  # Weighting factor
    
    trend = models.CharField(
        max_length=20,
        choices=[
            ('IMPROVING', 'Improving'),
            ('STABLE', 'Stable'),
            ('DECLINING', 'Declining')
        ],
        default='STABLE'
    )
    
    notes = models.TextField(blank=True)

class SupplierPerformanceMetricInline(InlineAdminMixin, admin.TabularInline):
    """Inline for performance metrics."""
    model = SupplierPerformanceMetric
    fields = [
        'metric_name', 'metric_category', 'target_value', 'actual_value',
        'unit_of_measure', 'score', 'weight', 'trend'
    ]
    extra = 5

@admin.register(SupplierPerformanceScore)
class SupplierPerformanceWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for supplier performance management."""
    
    list_display = [
        'supplier_info', 'evaluation_period', 'overall_score_display',
        'performance_tier_display', 'key_metrics_summary',
        'trend_indicators', 'risk_assessment', 'action_status'
    ]
    
    list_filter = [
        'performance_tier', 'status',
        ('evaluation_period_start', admin.DateFieldListFilter),
        ('approved_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'supplier__name', 'supplier__supplier_code',
        'created_by__username'
    ]
    
    inlines = [SupplierPerformanceMetricInline]
    
    fieldsets = (
        ('Evaluation Details', {
            'fields': (
                'supplier', 'evaluation_period_start', 'evaluation_period_end'
            )
        }),
        ('Performance Scores', {
            'fields': (
                'delivery_performance_score', 'quality_score', 'cost_competitiveness_score',
                'service_level_score', 'communication_score', 'overall_score'
            )
        }),
        ('Key Performance Data', {
            'fields': (
                'total_orders', 'total_order_value', 'on_time_deliveries',
                'late_deliveries', 'quality_issues', 'returns_count', 'returns_value'
            )
        }),
        ('Lead Time Analysis', {
            'fields': (
                'avg_lead_time_days', 'lead_time_variance'
            )
        }),
        ('Cost Analysis', {
            'fields': (
                'price_stability', 'cost_savings_delivered'
            )
        }),
        ('Compliance', {
            'fields': (
                'documentation_compliance', 'certification_status', 'audit_score'
            )
        }),
        ('Classification & Actions', {
            'fields': (
                'performance_tier', 'improvement_areas', 'action_plan',
                'next_review_date', 'status'
            )
        })
    )
    
    readonly_fields = [
        'approved_by', 'approved_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'generate_performance_scores', 'approve_evaluations', 'create_action_plans',
        'send_scorecards', 'tier_reassessment', 'export_performance_report'
    ]
    
    def get_urls(self):
        """Add supplier performance URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'performance-dashboard/',
                self.admin_site.admin_view(self.performance_dashboard),
                name='supplier-performance-dashboard'
            ),
            path(
                '<int:score_id>/scorecard/',
                self.admin_site.admin_view(self.supplier_scorecard),
                name='supplier-scorecard'
            ),
            path(
                'benchmark-analysis/',
                self.admin_site.admin_view(self.benchmark_analysis),
                name='supplier-benchmark'
            ),
            path(
                'tier-optimization/',
                self.admin_site.admin_view(self.tier_optimization),
                name='tier-optimization'
            ),
        ]
        return custom_urls + urls
    
    def supplier_info(self, obj):
        """Display supplier information."""
        supplier_url = reverse('admin:inventory_supplier_change', args=[obj.supplier.id])
        
        return format_html(
            '<a href="{}" title="View supplier details">{}</a><br/>'
            '<small>Code: {}</small>',
            supplier_url, obj.supplier.name, obj.supplier.supplier_code
        )
    supplier_info.short_description = 'Supplier'
    
    def evaluation_period(self, obj):
        """Show evaluation period."""
        period_days = (obj.evaluation_period_end - obj.evaluation_period_start).days
        
        return format_html(
            '<div>'
            '{} to<br/>'
            '{}<br/>'
            '<small>({} days)</small>'
            '</div>',
            obj.evaluation_period_start.strftime('%m/%d/%Y'),
            obj.evaluation_period_end.strftime('%m/%d/%Y'),
            period_days
        )
    evaluation_period.short_description = 'Period'
    
    def overall_score_display(self, obj):
        """Show overall score with color coding."""
        score = obj.overall_score
        
        if score >= 90:
            color = 'green'
            rating = 'Excellent'
        elif score >= 80:
            color = 'blue'
            rating = 'Good'
        elif score >= 70:
            color = 'orange'
            rating = 'Acceptable'
        elif score >= 60:
            color = 'red'
            rating = 'Poor'
        else:
            color = 'darkred'
            rating = 'Critical'
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="color: {}; font-size: 1.5em; font-weight: bold;">{:.1f}</span><br/>'
            '<small style="color: {};">{}</small>'
            '</div>',
            color, score, color, rating
        )
    overall_score_display.short_description = 'Overall Score'
    
    def performance_tier_display(self, obj):
        """Show performance tier with visual indicator."""
        tier_colors = {
            'STRATEGIC': 'green',
            'PREFERRED': 'blue',
            'APPROVED': 'gray',
            'CONDITIONAL': 'orange',
            'PROBATION': 'red',
            'TERMINATED': 'darkred'
        }
        
        tier_icons = {
            'STRATEGIC': '⭐',
            'PREFERRED': '💎',
            'APPROVED': '✅',
            'CONDITIONAL': '⚠️',
            'PROBATION': '🚨',
            'TERMINATED': '❌'
        }
        
        color = tier_colors.get(obj.performance_tier, 'black')
        icon = tier_icons.get(obj.performance_tier, '●')
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="font-size: 1.2em;">{}</span><br/>'
            '<span style="color: {}; font-weight: bold; font-size: 0.9em;">{}</span>'
            '</div>',
            icon, color, obj.get_performance_tier_display()
        )
    performance_tier_display.short_description = 'Tier'
    
    def key_metrics_summary(self, obj):
        """Show key performance metrics."""
        on_time_rate = (obj.on_time_deliveries / obj.total_orders * 100) if obj.total_orders > 0 else 0
        return_rate = (obj.returns_value / obj.total_order_value * 100) if obj.total_order_value > 0 else 0
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Orders: <strong>{}</strong> (${:,.0f})<br/>'
            'On-time: <span style="color: {};">{:.1f}%</span><br/>'
            'Returns: <span style="color: {};">{:.1f}%</span><br/>'
            'Avg Lead Time: {}d'
            '</div>',
            obj.total_orders, obj.total_order_value,
            'green' if on_time_rate >= 95 else ('orange' if on_time_rate >= 85 else 'red'), on_time_rate,
            'green' if return_rate <= 2 else ('orange' if return_rate <= 5 else 'red'), return_rate,
            obj.avg_lead_time_days
        )
    key_metrics_summary.short_description = 'Key Metrics'
    
    def trend_indicators(self, obj):
        """Show performance trend indicators."""
        # This would compare with previous period
        delivery_trend = "stable"  # Would be calculated from historical data
        quality_trend = "improving"
        cost_trend = "stable"
        
        trend_icons = {
            'improving': '📈',
            'stable': '➡️',
            'declining': '📉'
        }
        
        trend_colors = {
            'improving': 'green',
            'stable': 'blue',
            'declining': 'red'
        }
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Delivery: <span style="color: {};">{} {}</span><br/>'
            'Quality: <span style="color: {};">{} {}</span><br/>'
            'Cost: <span style="color: {};">{} {}</span>'
            '</div>',
            trend_colors[delivery_trend], trend_icons[delivery_trend], delivery_trend.title(),
            trend_colors[quality_trend], trend_icons[quality_trend], quality_trend.title(),
            trend_colors[cost_trend], trend_icons[cost_trend], cost_trend.title()
        )
    trend_indicators.short_description = 'Trends'
    
    def risk_assessment(self, obj):
        """Show risk assessment."""
        risk_factors = []
        
        # Calculate risk based on various factors
        if obj.overall_score < 70:
            risk_factors.append("Low Performance")
        
        if obj.late_deliveries / obj.total_orders > 0.1 if obj.total_orders > 0 else False:
            risk_factors.append("Delivery Issues")
        
        if obj.quality_issues > 0:
            risk_factors.append("Quality Concerns")
        
        if obj.returns_value / obj.total_order_value > 0.05 if obj.total_order_value > 0 else False:
            risk_factors.append("High Returns")
        
        if not risk_factors:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Low Risk</span>'
            )
        elif len(risk_factors) == 1:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠️ Medium Risk</span><br/>'
                '<small>{}</small>',
                risk_factors[0]
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">🚨 High Risk</span><br/>'
                '<small>{} issues</small>',
                len(risk_factors)
            )
    risk_assessment.short_description = 'Risk'
    
    def action_status(self, obj):
        """Show action plan status."""
        if obj.status == 'APPROVED' and obj.action_plan:
            if obj.next_review_date:
                days_to_review = (obj.next_review_date - timezone.now().date()).days
                
                if days_to_review < 0:
                    return format_html(
                        '<span style="color: red; font-weight: bold;">⏰ Review Overdue</span><br/>'
                        '<small>{} days</small>',
                        abs(days_to_review)
                    )
                elif days_to_review < 30:
                    return format_html(
                        '<span style="color: orange;">📅 Review Due Soon</span><br/>'
                        '<small>{} days</small>',
                        days_to_review
                    )
                else:
                    return format_html(
                        '<span style="color: green;">📋 Action Plan Active</span><br/>'
                        '<small>Review in {} days</small>',
                        days_to_review
                    )
            else:
                return format_html(
                    '<span style="color: blue;">📋 Action Plan Ready</span>'
                )
        elif obj.improvement_areas:
            return format_html(
                '<span style="color: orange;">⚠️ Needs Action Plan</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">No Actions Needed</span>'
            )
    action_status.short_description = 'Action Status'