# apps/inventory/admin/workflows/inventory_optimization.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg, Max, Min, Case, When, DecimalField
from django.db.models.functions import Coalesce
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
import numpy as np

from ..base import BaseInventoryAdmin, InlineAdminMixin

class InventoryOptimizationRun(models.Model):
    """Model for inventory optimization runs."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    optimization_name = models.CharField(max_length=200)
    
    # Optimization parameters
    optimization_type = models.CharField(
        max_length=30,
        choices=[
            ('EOQ', 'Economic Order Quantity'),
            ('SAFETY_STOCK', 'Safety Stock Optimization'),
            ('REORDER_POINTS', 'Reorder Point Optimization'),
            ('MIN_MAX', 'Min-Max Optimization'),
            ('SERVICE_LEVEL', 'Service Level Optimization'),
            ('CARRYING_COST', 'Carrying Cost Minimization'),
            ('MULTI_OBJECTIVE', 'Multi-Objective Optimization')
        ]
    )
    
    # Analysis period
    analysis_period_months = models.IntegerField(default=12)
    demand_forecast_months = models.IntegerField(default=6)
    
    # Optimization constraints
    target_service_level = models.DecimalField(max_digits=5, decimal_places=2, default=95.0)  # 95%
    max_carrying_cost_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25.0)  # 25%
    budget_constraint = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Filters
    warehouse_filter = models.ManyToManyField('inventory.Warehouse', blank=True)
    category_filter = models.ManyToManyField('inventory.Category', blank=True)
    abc_class_filter = models.CharField(max_length=10, blank=True)  # e.g., "A,B"
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('APPLIED', 'Applied'),
            ('ARCHIVED', 'Archived')
        ],
        default='DRAFT'
    )
    
    # Results summary
    total_products_optimized = models.IntegerField(default=0)
    potential_cost_savings = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    inventory_reduction_potential = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    service_level_improvement = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Processing info
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

class InventoryOptimizationResult(models.Model):
    """Individual product optimization results."""
    optimization_run = models.ForeignKey(InventoryOptimizationRun, on_delete=models.CASCADE, related_name='results')
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE)
    
    # Current state
    current_reorder_level = models.DecimalField(max_digits=15, decimal_places=4)
    current_max_stock = models.DecimalField(max_digits=15, decimal_places=4)
    current_safety_stock = models.DecimalField(max_digits=15, decimal_places=4)
    current_order_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Optimized recommendations
    recommended_reorder_level = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_max_stock = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_safety_stock = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_order_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Analysis data
    avg_demand_per_day = models.DecimalField(max_digits=15, decimal_places=4)
    demand_variability = models.DecimalField(max_digits=5, decimal_places=2)  # CV%
    lead_time_days = models.IntegerField()
    lead_time_variability = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Cost analysis
    current_carrying_cost = models.DecimalField(max_digits=15, decimal_places=2)
    optimized_carrying_cost = models.DecimalField(max_digits=15, decimal_places=2)
    potential_savings = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Service level analysis
    current_service_level = models.DecimalField(max_digits=5, decimal_places=2)
    projected_service_level = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Implementation priority
    priority_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    implementation_complexity = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High')
        ],
        default='MEDIUM'
    )
    
    # Status
    approved = models.BooleanField(default=False)
    applied = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

class InventoryOptimizationResultInline(admin.TabularInline):
    """Inline for optimization results."""
    model = InventoryOptimizationResult
    fields = [
        'product', 'warehouse', 'current_reorder_level', 'recommended_reorder_level',
        'potential_savings', 'priority_score', 'approved'
    ]
    readonly_fields = ['potential_savings', 'priority_score']
    extra = 0
    max_num = 20
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'warehouse').order_by('-priority_score')

@admin.register(InventoryOptimizationRun)
class InventoryOptimizationWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for inventory optimization workflow."""
    
    list_display = [
        'optimization_name', 'optimization_type', 'status_display',
        'products_optimized', 'savings_potential', 'service_impact',
        'implementation_progress', 'roi_analysis', 'actions_column'
    ]
    
    list_filter = [
        'optimization_type', 'status',
        ('started_at', admin.DateFieldListFilter),
        ('applied_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'optimization_name', 'created_by__username'
    ]
    
    inlines = [InventoryOptimizationResultInline]
    
    fieldsets = (
        ('Optimization Configuration', {
            'fields': (
                'optimization_name', 'optimization_type',
                'analysis_period_months', 'demand_forecast_months'
            )
        }),
        ('Constraints & Targets', {
            'fields': (
                'target_service_level', 'max_carrying_cost_rate', 'budget_constraint'
            )
        }),
        ('Filters', {
            'fields': (
                'warehouse_filter', 'category_filter', 'abc_class_filter'
            )
        }),
        ('Results Summary', {
            'fields': (
                'total_products_optimized', 'potential_cost_savings',
                'inventory_reduction_potential', 'service_level_improvement'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status',)
        })
    )
    
    readonly_fields = [
        'total_products_optimized', 'potential_cost_savings',
        'inventory_reduction_potential', 'service_level_improvement',
        'started_at', 'completed_at', 'applied_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'run_optimization', 'approve_recommendations', 'apply_optimizations',
        'export_recommendations', 'create_implementation_plan'
    ]
    
    def get_urls(self):
        """Add optimization URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'optimization-dashboard/',
                self.admin_site.admin_view(self.optimization_dashboard),
                name='optimization-dashboard'
            ),
            path(
                '<int:optimization_id>/run/',
                self.admin_site.admin_view(self.run_optimization),
                name='run-optimization'
            ),
            path(
                '<int:optimization_id>/simulation/',
                self.admin_site.admin_view(self.optimization_simulation),
                name='optimization-simulation'
            ),
            path(
                'what-if-analysis/',
                self.admin_site.admin_view(self.what_if_analysis),
                name='what-if-analysis'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with progress."""
        status_colors = {
            'DRAFT': 'gray',
            'RUNNING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'APPLIED': 'purple',
            'ARCHIVED': 'darkgray'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def products_optimized(self, obj):
        """Show products optimization summary."""
        if obj.status not in ['COMPLETED', 'APPLIED']:
            return 'Not completed'
        
        results = obj.results.all()
        high_priority = results.filter(priority_score__gte=80).count()
        approved = results.filter(approved=True).count()
        
        return format_html(
            '<div>'
            'Total: <strong>{}</strong><br/>'
            'High Priority: <span style="color: red;">{}</span><br/>'
            'Approved: <span style="color: green;">{}</span>'
            '</div>',
            obj.total_products_optimized, high_priority, approved
        )
    products_optimized.short_description = 'Products'
    
    def savings_potential(self, obj):
        """Show savings potential with breakdown."""
        if obj.potential_cost_savings <= 0:
            return 'No savings identified'
        
        # Calculate annualized savings
        annual_savings = obj.potential_cost_savings
        
        # Estimate inventory reduction value
        inventory_reduction_value = obj.inventory_reduction_potential
        
        # Calculate ROI (simplified)
        implementation_cost = annual_savings * 0.1  # Assume 10% implementation cost
        roi = (annual_savings / implementation_cost * 100) if implementation_cost > 0 else 0
        
        return format_html(
            '<div>'
            'Annual Savings: <strong>${:,.0f}</strong><br/>'
            'Inventory Reduction: ${:,.0f}<br/>'
            'Estimated ROI: <span style="color: green;">{:.0f}%</span>'
            '</div>',
            annual_savings, inventory_reduction_value, roi
        )
    savings_potential.short_description = 'Savings Potential'
    
    def service_impact(self, obj):
        """Show service level impact."""
        if obj.service_level_improvement == 0:
            return 'No change'
        
        if obj.service_level_improvement > 0:
            color = 'green'
            arrow = '↗️'
            impact = 'Improvement'
        else:
            color = 'red'
            arrow = '↘️'
            impact = 'Decline'
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="font-size: 1.2em;">{}</span><br/>'
            '<span style="color: {}; font-weight: bold;">{:+.1f}%</span><br/>'
            '<small>{}</small>'
            '</div>',
            arrow, color, obj.service_level_improvement, impact
        )
    service_impact.short_description = 'Service Impact'
    
    def implementation_progress(self, obj):
        """Show implementation progress."""
        if obj.status not in ['COMPLETED', 'APPLIED']:
            return 'Not ready'
        
        results = obj.results.all()
        total_results = results.count()
        
        if total_results == 0:
            return 'No results'
        
        approved_count = results.filter(approved=True).count()
        applied_count = results.filter(applied=True).count()
        
        approval_rate = (approved_count / total_results * 100) if total_results > 0 else 0
        implementation_rate = (applied_count / total_results * 100) if total_results > 0 else 0
        
        return format_html(
            '<div>'
            'Approved: <span style="color: blue;">{:.1f}%</span><br/>'
            'Implemented: <span style="color: green;">{:.1f}%</span><br/>'
            '<small>{}/{} items</small>'
            '</div>',
            approval_rate, implementation_rate, applied_count, total_results
        )
    implementation_progress.short_description = 'Progress'
    
    def roi_analysis(self, obj):
        """Show ROI analysis."""
        if obj.potential_cost_savings <= 0:
            return 'No ROI data'
        
        # Simplified ROI calculation
        annual_savings = obj.potential_cost_savings
        investment_required = annual_savings * 0.15  # Assume 15% investment
        payback_months = (investment_required / (annual_savings / 12)) if annual_savings > 0 else 0
        
        if payback_months <= 6:
            color = 'green'
            rating = 'Excellent'
        elif payback_months <= 12:
            color = 'blue'
            rating = 'Good'
        elif payback_months <= 24:
            color = 'orange'
            rating = 'Fair'
        else:
            color = 'red'
            rating = 'Poor'
        
        return format_html(
            '<div style="text-align: center;">'
            'Payback: <span style="color: {}; font-weight: bold;">{:.1f}mo</span><br/>'
            '<small style="color: {};">{}</small>'
            '</div>',
            color, payback_months, color, rating
        )
    roi_analysis.short_description = 'ROI Analysis'
    
    def actions_column(self, obj):
        """Show action buttons."""
        buttons = []
        
        if obj.status == 'DRAFT':
            buttons.append(
                f'<a href="/admin/inventory/inventoryoptimizationrun/{obj.id}/run/" '
                f'class="button" style="font-size: 0.8em; padding: 2px 6px;">Run Optimization</a>'
            )
        
        if obj.status == 'COMPLETED':
            buttons.append(
                '<button onclick="approveOptimization({})" class="button" '
                'style="font-size: 0.8em; padding: 2px 6px;">Approve All</button>'.format(obj.id)
            )
            buttons.append(
                f'<a href="/admin/inventory/inventoryoptimizationrun/{obj.id}/simulation/" '
                f'class="button" style="font-size: 0.8em; padding: 2px 6px;">Simulate</a>'
            )
        
        return format_html('<br/>'.join(buttons)) if buttons else '-'
    actions_column.short_description = 'Actions'
    
    def run_optimization(self, request, queryset):
        """Run optimization for selected configurations."""
        from ...services.optimization.inventory_optimizer import InventoryOptimizer
        
        completed = 0
        for optimization_run in queryset.filter(status='DRAFT'):
            optimization_run.status = 'RUNNING'
            optimization_run.started_at = timezone.now()
            optimization_run.save()
            
            try:
                optimizer = InventoryOptimizer()
                results = optimizer.optimize_inventory(optimization_run)
                
                optimization_run.status = 'COMPLETED'
                optimization_run.completed_at = timezone.now()
                optimization_run.save()
                completed += 1
                
            except Exception as e:
                optimization_run.status = 'FAILED'
                optimization_run.save()
        
        self.message_user(
            request,
            f'{completed} optimization runs completed.',
            messages.SUCCESS
        )
    run_optimization.short_description = "Run optimization"

    def optimization_simulation(self, request, optimization_id):
        """Run what-if simulation for optimization results."""
        optimization_run = get_object_or_404(InventoryOptimizationRun, id=optimization_id)
        
        if optimization_run.status != 'COMPLETED':
            return JsonResponse({'error': 'Optimization not completed'})
        
        # Simulate different scenarios
        scenarios = {
            'conservative': {'service_level': 90, 'carrying_cost': 20},
            'balanced': {'service_level': 95, 'carrying_cost': 25},
            'aggressive': {'service_level': 99, 'carrying_cost': 30}
        }
        
        simulation_results = {}
        
        for scenario_name, params in scenarios.items():
            scenario_savings = 0
            scenario_inventory = 0
            scenario_service = 0
            
            for result in optimization_run.results.all():
                # Recalculate based on scenario parameters
                # This is a simplified simulation
                if params['service_level'] < optimization_run.target_service_level:
                    savings_factor = 1.2
                else:
                    savings_factor = 0.8
                
                scenario_savings += result.potential_savings * savings_factor
                scenario_inventory += result.recommended_max_stock * result.product.cost_price
                scenario_service += params['service_level']
            
            simulation_results[scenario_name] = {
                'total_savings': scenario_savings,
                'inventory_value': scenario_inventory,
                'avg_service_level': scenario_service / optimization_run.results.count() if optimization_run.results.count() > 0 else 0,
                'carrying_cost_rate': params['carrying_cost']
            }
        
        return JsonResponse(simulation_results)