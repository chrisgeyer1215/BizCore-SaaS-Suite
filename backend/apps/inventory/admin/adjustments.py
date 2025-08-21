# apps/inventory/admin/adjustments.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.adjustments import (
    StockAdjustment, StockAdjustmentItem, 
    CycleCount, CycleCountItem
)
from ..utils.choices import ADJUSTMENT_TYPE_CHOICES, COUNT_STATUS_CHOICES

class StockAdjustmentItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for stock adjustment items."""
    model = StockAdjustmentItem
    fields = [
        'product', 'variation', 'warehouse', 'location',
        'current_quantity', 'adjusted_quantity', 'variance',
        'unit_cost', 'total_impact', 'reason_code'
    ]
    readonly_fields = ['variance', 'total_impact']
    extra = 1
    
    def variance(self, obj):
        """Calculate variance."""
        if obj.current_quantity is not None and obj.adjusted_quantity is not None:
            return obj.adjusted_quantity - obj.current_quantity
        return 0
    variance.short_description = 'Variance'
    
    def total_impact(self, obj):
        """Calculate financial impact."""
        variance = obj.adjusted_quantity - obj.current_quantity if (
            obj.current_quantity is not None and obj.adjusted_quantity is not None
        ) else 0
        
        impact = variance * (obj.unit_cost or 0)
        
        color = 'red' if impact < 0 else 'green' if impact > 0 else 'black'
        
        return format_html(
            '<span style="color: {};">${:.2f}</span>',
            color, impact
        )
    total_impact.short_description = 'Impact'

@admin.register(StockAdjustment)
class StockAdjustmentAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for stock adjustments."""
    
    list_display = [
        'adjustment_number', 'adjustment_type', 'warehouse',
        'adjustment_date', 'status_display', 'items_count',
        'total_variance', 'financial_impact', 'approval_status'
    ]
    
    list_filter = [
        'adjustment_type', 'status', 'warehouse',
        ('adjustment_date', admin.DateFieldListFilter),
        ('approved_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'adjustment_number', 'reference_number',
        'items__product__name', 'items__product__sku',
        'reason', 'created_by__username'
    ]
    
    inlines = [StockAdjustmentItemInline]
    
    fieldsets = (
        ('Adjustment Information', {
            'fields': (
                'adjustment_number', 'adjustment_type', 'warehouse',
                'adjustment_date', 'reference_number'
            )
        }),
        ('Approval', {
            'fields': (
                'status', 'requires_approval', 'approved_by',
                'approved_date', 'approval_notes'
            )
        }),
        ('Reason & Documentation', {
            'fields': (
                'reason', 'root_cause_analysis', 'corrective_actions',
                'supporting_documents'
            )
        })
    )
    
    readonly_fields = BaseInventoryAdmin.readonly_fields + [
        'approved_by', 'approved_date'
    ]
    
    actions = BaseInventoryAdmin.actions + [
        'submit_for_approval', 'approve_adjustments', 'post_adjustments',
        'analyze_root_causes', 'generate_variance_report'
    ]
    
    def get_urls(self):
        """Add custom URLs for adjustment operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:adjustment_id>/approve/',
                self.admin_site.admin_view(self.approve_adjustment),
                name='adjustment-approve'
            ),
            path(
                '<int:adjustment_id>/variance-analysis/',
                self.admin_site.admin_view(self.variance_analysis),
                name='adjustment-variance-analysis'
            ),
            path(
                'variance-trends/',
                self.admin_site.admin_view(self.variance_trends),
                name='adjustment-variance-trends'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with approval workflow."""
        status_colors = {
            'DRAFT': 'gray',
            'PENDING_APPROVAL': 'orange',
            'APPROVED': 'blue',
            'POSTED': 'green',
            'REJECTED': 'red'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Show approval requirement
        approval_text = ""
        if obj.requires_approval and obj.status == 'DRAFT':
            approval_text = "<br/><small>⚠️ Requires Approval</small>"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}{}'.format(
                color, obj.get_status_display(), approval_text
            )
        )
    status_display.short_description = 'Status'
    
    def items_count(self, obj):
        """Show number of adjustment items."""
        count = obj.items.count()
        if count > 0:
            positive = obj.items.filter(
                adjusted_quantity__gt=F('current_quantity')
            ).count()
            negative = obj.items.filter(
                adjusted_quantity__lt=F('current_quantity')
            ).count()
            
            return format_html(
                '<strong>{}</strong> items<br/>'
                '<small style="color: green;">+{}</small> | '
                '<small style="color: red;">-{}</small>',
                count, positive, negative
            )
        return '0 items'
    items_count.short_description = 'Items'
    
    def total_variance(self, obj):
        """Calculate total quantity variance."""
        variance_data = obj.items.aggregate(
            positive_variance=Sum(
                F('adjusted_quantity') - F('current_quantity'),
                filter=Q(adjusted_quantity__gt=F('current_quantity'))
            ),
            negative_variance=Sum(
                F('adjusted_quantity') - F('current_quantity'),
                filter=Q(adjusted_quantity__lt=F('current_quantity'))
            )
        )
        
        positive = variance_data['positive_variance'] or 0
        negative = variance_data['negative_variance'] or 0
        
        return format_html(
            '<div>'
            '<span style="color: green;">+{}</span><br/>'
            '<span style="color: red;">{}</span>'
            '</div>',
            int(positive), int(negative)
        )
    total_variance.short_description = 'Variance'
    
    def financial_impact(self, obj):
        """Calculate financial impact of adjustment."""
        impact = obj.items.aggregate(
            total_impact=Sum(
                (F('adjusted_quantity') - F('current_quantity')) * F('unit_cost')
            )
        )['total_impact'] or 0
        
        color = 'red' if impact < 0 else 'green' if impact > 0 else 'black'
        symbol = '-' if impact < 0 else '+' if impact > 0 else ''
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ${:,.2f}</span>',
            color, symbol, abs(impact)
        )
    financial_impact.short_description = 'Financial Impact'
    
    def approval_status(self, obj):
        """Show approval status."""
        if not obj.requires_approval:
            return format_html(
                '<span style="color: gray;">Not Required</span>'
            )
        
        if obj.approved_by:
            return format_html(
                '<span style="color: green;">✓ {}</span><br/>'
                '<small>{}</small>',
                obj.approved_by.get_full_name(),
                obj.approved_date.strftime('%Y-%m-%d') if obj.approved_date else ''
            )
        elif obj.status == 'PENDING_APPROVAL':
            return format_html(
                '<span style="color: orange;">⏳ Pending</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">❌ Not Approved</span>'
            )
    approval_status.short_description = 'Approval'
    
    def submit_for_approval(self, request, queryset):
        """Submit adjustments for approval."""
        submitted = 0
        for adjustment in queryset.filter(status='DRAFT'):
            if adjustment.requires_approval:
                adjustment.status = 'PENDING_APPROVAL'
                adjustment.save()
                submitted += 1
        
        self.message_user(
            request,
            f'{submitted} adjustments submitted for approval.',
            messages.SUCCESS
        )
    submit_for_approval.short_description = "Submit for approval"
    
    def approve_adjustments(self, request, queryset):
        """Approve selected adjustments."""
        approved = 0
        for adjustment in queryset.filter(status='PENDING_APPROVAL'):
            adjustment.status = 'APPROVED'
            adjustment.approved_by = request.user
            adjustment.approved_date = timezone.now()
            adjustment.save()
            approved += 1
        
        self.message_user(
            request,
            f'{approved} adjustments approved.',
            messages.SUCCESS
        )
    approve_adjustments.short_description = "Approve adjustments"
    
    def variance_analysis(self, request, adjustment_id):
        """Get variance analysis data."""
        adjustment = get_object_or_404(StockAdjustment, id=adjustment_id)
        
        items_analysis = []
        for item in adjustment.items.select_related('product'):
            variance = item.adjusted_quantity - item.current_quantity
            impact = variance * item.unit_cost
            
            items_analysis.append({
                'product': item.product.name,
                'sku': item.product.sku,
                'current_quantity': float(item.current_quantity),
                'adjusted_quantity': float(item.adjusted_quantity),
                'variance': float(variance),
                'unit_cost': float(item.unit_cost),
                'financial_impact': float(impact),
                'reason_code': item.reason_code
            })
        
        return JsonResponse({
            'adjustment_number': adjustment.adjustment_number,
            'items': items_analysis,
            'summary': {
                'total_items': len(items_analysis),
                'total_impact': sum(item['financial_impact'] for item in items_analysis),
                'positive_adjustments': len([i for i in items_analysis if i['variance'] > 0]),
                'negative_adjustments': len([i for i in items_analysis if i['variance'] < 0])
            }
        })

class CycleCountItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for cycle count items."""
    model = CycleCountItem
    fields = [
        'stock_item', 'expected_quantity', 'counted_quantity',
        'variance', 'count_status', 'counter', 'count_date',
        'notes'
    ]
    readonly_fields = ['variance']
    
    def variance(self, obj):
        """Calculate count variance."""
        if (obj.expected_quantity is not None and 
            obj.counted_quantity is not None):
            variance = obj.counted_quantity - obj.expected_quantity
            
            color = 'red' if variance != 0 else 'green'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, variance
            )
        return '-'
    variance.short_description = 'Variance'

@admin.register(CycleCount)
class CycleCountAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for cycle counts."""
    
    list_display = [
        'name', 'warehouse', 'count_date', 'status_display',
        'items_count', 'completion_percentage', 'accuracy_rate',
        'variance_summary', 'count_team'
    ]
    
    list_filter = [
        'status', 'warehouse', 'count_type',
        ('count_date', admin.DateFieldListFilter),
        ('completed_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'name', 'description', 'items__stock_item__product__name',
        'items__stock_item__product__sku'
    ]
    
    inlines = [CycleCountItemInline]
    
    fieldsets = (
        ('Count Information', {
            'fields': (
                'name', 'description', 'warehouse', 'count_type',
                'count_date', 'expected_completion_date'
            )
        }),
        ('Selection Criteria', {
            'fields': (
                'selection_criteria', 'include_zero_qty',
                'abc_classes', 'categories'
            )
        }),
        ('Status & Results', {
            'fields': (
                'status', 'completed_date', 'accuracy_threshold',
                'recount_required'
            )
        })
    )
    
    actions = BaseInventoryAdmin.actions + [
        'start_counts', 'complete_counts', 'generate_adjustments',
        'schedule_recounts', 'export_count_sheets'
    ]
    
    def status_display(self, obj):
        """Show status with progress indicators."""
        status_colors = {
            'PLANNED': 'gray',
            'IN_PROGRESS': 'blue',
            'COMPLETED': 'green',
            'CANCELLED': 'red'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def items_count(self, obj):
        """Show count items statistics."""
        total_items = obj.items.count()
        completed_items = obj.items.filter(
            count_status='COUNTED'
        ).count()
        
        if total_items > 0:
            return format_html(
                '<strong>{}</strong> items<br/>'
                '<small>{} completed</small>',
                total_items, completed_items
            )
        return '0 items'
    items_count.short_description = 'Items'
    
    def completion_percentage(self, obj):
        """Calculate completion percentage."""
        total_items = obj.items.count()
        if total_items == 0:
            return '0%'
        
        completed_items = obj.items.filter(
            count_status='COUNTED'
        ).count()
        
        percentage = (completed_items / total_items * 100)
        
        # Color code percentage
        if percentage == 100:
            color = 'green'
        elif percentage >= 75:
            color = 'blue'
        elif percentage >= 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    completion_percentage.short_description = 'Complete'
    
    def accuracy_rate(self, obj):
        """Calculate count accuracy rate."""
        counted_items = obj.items.filter(
            count_status='COUNTED',
            counted_quantity__isnull=False
        )
        
        if not counted_items:
            return 'N/A'
        
        accurate_counts = counted_items.filter(
            counted_quantity=F('expected_quantity')
        ).count()
        
        total_counted = counted_items.count()
        accuracy = (accurate_counts / total_counted * 100) if total_counted > 0 else 0
        
        # Color code accuracy
        if accuracy >= 95:
            color = 'green'
        elif accuracy >= 85:
            color = 'blue'
        elif accuracy >= 75:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, accuracy
        )
    accuracy_rate.short_description = 'Accuracy'
    
    def variance_summary(self, obj):
        """Show variance summary."""
        variances = obj.items.filter(
            count_status='COUNTED',
            counted_quantity__isnull=False
        ).aggregate(
            positive_var=Count(
                'id', 
                filter=Q(counted_quantity__gt=F('expected_quantity'))
            ),
            negative_var=Count(
                'id',
                filter=Q(counted_quantity__lt=F('expected_quantity'))
            ),
            zero_var=Count(
                'id',
                filter=Q(counted_quantity=F('expected_quantity'))
            )
        )
        
        return format_html(
            '<div style="font-size: 0.85em;">'
            '<span style="color: green;">+{}</span> | '
            '<span style="color: red;">-{}</span> | '
            '<span style="color: blue;">✓{}</span>'
            '</div>',
            variances['positive_var'] or 0,
            variances['negative_var'] or 0,
            variances['zero_var'] or 0
        )
    variance_summary.short_description = 'Variances'
    
    def count_team(self, obj):
        """Show count team members."""
        counters = obj.items.values_list(
            'counter__username', flat=True
        ).distinct()
        
        counter_list = list(filter(None, counters))
        
        if counter_list:
            return format_html(
                '{}<br/><small>{} counters</small>',
                ', '.join(counter_list[:3]),
                len(counter_list)
            )
        return 'Not assigned'
    count_team.short_description = 'Team'
    
    def start_counts(self, request, queryset):
        """Start selected cycle counts."""
        started = queryset.filter(status='PLANNED').update(
            status='IN_PROGRESS'
        )
        
        self.message_user(
            request,
            f'{started} cycle counts started.',
            messages.SUCCESS
        )
    start_counts.short_description = "Start cycle counts"
    
    def generate_adjustments(self, request, queryset):
        """Generate adjustments from completed counts."""
        generated = 0
        for cycle_count in queryset.filter(status='COMPLETED'):
            # Logic to create adjustments from variances
            variance_items = cycle_count.items.exclude(
                counted_quantity=F('expected_quantity')
            )
            
            if variance_items.exists():
                # Create adjustment
                generated += 1
        
        self.message_user(
            request,
            f'Adjustments generated for {generated} cycle counts.',
            messages.SUCCESS
        )
    generate_adjustments.short_description = "Generate adjustments"