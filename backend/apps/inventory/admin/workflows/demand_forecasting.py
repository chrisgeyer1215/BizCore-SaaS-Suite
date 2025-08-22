# apps/inventory/admin/workflows/demand_forecasting.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg, Max, Min
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
import numpy as np

from ..base import BaseInventoryAdmin, InlineAdminMixin

class DemandForecast(models.Model):
    """Model for demand forecasting runs."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    forecast_name = models.CharField(max_length=200)
    
    # Forecast parameters
    forecast_method = models.CharField(
        max_length=30,
        choices=[
            ('MOVING_AVERAGE', 'Moving Average'),
            ('EXPONENTIAL_SMOOTHING', 'Exponential Smoothing'),
            ('LINEAR_REGRESSION', 'Linear Regression'),
            ('SEASONAL_ARIMA', 'Seasonal ARIMA'),
            ('MACHINE_LEARNING', 'Machine Learning'),
            ('ENSEMBLE', 'Ensemble Method')
        ]
    )
    
    # Time periods
    historical_period_months = models.IntegerField(default=24)  # 24 months history
    forecast_horizon_months = models.IntegerField(default=12)   # 12 months forecast
    
    # Data granularity
    granularity = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly')
        ],
        default='MONTHLY'
    )
    
    # Filters
    warehouse_filter = models.ManyToManyField('inventory.Warehouse', blank=True)
    category_filter = models.ManyToManyField('inventory.Category', blank=True)
    abc_class_filter = models.CharField(max_length=10, blank=True)
    
    # External factors
    include_seasonality = models.BooleanField(default=True)
    include_trends = models.BooleanField(default=True)
    include_promotions = models.BooleanField(default=True)
    external_factors = models.JSONField(default=dict)  # Economic indicators, etc.
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('PUBLISHED', 'Published'),
            ('ARCHIVED', 'Archived')
        ],
        default='DRAFT'
    )
    
    # Accuracy metrics
    mean_absolute_error = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    mean_squared_error = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    forecast_accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # %
    
    # Processing info
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

class DemandForecastResult(models.Model):
    """Individual product demand forecast results."""
    forecast = models.ForeignKey(DemandForecast, on_delete=models.CASCADE, related_name='results')
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE)
    
    # Historical data summary
    historical_avg_demand = models.DecimalField(max_digits=15, decimal_places=4)
    historical_demand_variance = models.DecimalField(max_digits=15, decimal_places=4)
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ('INCREASING', 'Increasing'),
            ('DECREASING', 'Decreasing'),
            ('STABLE', 'Stable'),
            ('VOLATILE', 'Volatile')
        ]
    )
    seasonality_factor = models.DecimalField(max_digits=5, decimal_places=4, default=1.0000)
    
    # Forecast results (stored as JSON for flexibility)
    forecast_data = models.JSONField(default=dict)  # Time series data
    confidence_intervals = models.JSONField(default=dict)  # Upper/lower bounds
    
    # Key forecast metrics
    next_month_forecast = models.DecimalField(max_digits=15, decimal_places=4)
    next_quarter_forecast = models.DecimalField(max_digits=15, decimal_places=4)
    next_year_forecast = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Forecast quality
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    forecast_error = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # Risk assessment
    demand_volatility = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('EXTREME', 'Extreme')
        ]
    )
    
    stockout_probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overstock_probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Recommendations
    recommended_safety_stock = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_reorder_point = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_order_quantity = models.DecimalField(max_digits=15, decimal_places=4)

class DemandForecastResultInline(admin.TabularInline):
    """Inline for forecast results."""
    model = DemandForecastResult
    fields = [
        'product', 'warehouse', 'next_month_forecast', 'confidence_score',
        'demand_volatility', 'stockout_probability'
    ]
    readonly_fields = ['confidence_score', 'stockout_probability']
    extra = 0
    max_num = 15
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'warehouse').order_by('-next_month_forecast')

@admin.register(DemandForecast)
class DemandForecastingWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for demand forecasting workflow."""
    
    list_display = [
        'forecast_name', 'forecast_method', 'status_display',
        'forecast_scope', 'accuracy_metrics', 'forecast_insights',
        'business_impact', 'publication_status'
    ]
    
    list_filter = [
        'forecast_method', 'status', 'granularity',
        ('started_at', admin.DateFieldListFilter),
        ('published_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'forecast_name', 'created_by__username'
    ]
    
    inlines = [DemandForecastResultInline]
    
    fieldsets = (
        ('Forecast Configuration', {
            'fields': (
                'forecast_name', 'forecast_method', 'granularity',
                'historical_period_months', 'forecast_horizon_months'
            )
        }),
        ('Data Filters', {
            'fields': (
                'warehouse_filter', 'category_filter', 'abc_class_filter'
            )
        }),
        ('Model Parameters', {
            'fields': (
                'include_seasonality', 'include_trends', 'include_promotions',
                'external_factors'
            )
        }),
        ('Accuracy Metrics', {
            'fields': (
                'mean_absolute_error', 'mean_squared_error', 'forecast_accuracy'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status',)
        })
    )
    
    readonly_fields = [
        'mean_absolute_error', 'mean_squared_error', 'forecast_accuracy',
        'started_at', 'completed_at', 'published_at'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'run_forecasting', 'publish_forecasts', 'update_inventory_params',
        'validate_forecasts', 'export_forecast_data'
    ]
    
    def get_urls(self):
        """Add forecasting URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'forecasting-dashboard/',
                self.admin_site.admin_view(self.forecasting_dashboard),
                name='forecasting-dashboard'
            ),
            path(
                '<int:forecast_id>/run/',
                self.admin_site.admin_view(self.run_forecast),
                name='run-forecast'
            ),
            path(
                '<int:forecast_id>/visualization/',
                self.admin_site.admin_view(self.forecast_visualization),
                name='forecast-visualization'
            ),
            path(
                'accuracy-analysis/',
                self.admin_site.admin_view(self.accuracy_analysis),
                name='forecast-accuracy-analysis'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with processing time."""
        status_colors = {
            'DRAFT': 'gray',
            'RUNNING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'PUBLISHED': 'purple',
            'ARCHIVED': 'darkgray'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Add processing time if available
        status_text = obj.get_status_display()
        if obj.status == 'RUNNING' and obj.started_at:
            elapsed = timezone.now() - obj.started_at
            status_text += f" ({elapsed.total_seconds()/60:.0f}m)"
        elif obj.status == 'COMPLETED' and obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            status_text += f" ({duration.total_seconds()/60:.0f}m)"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, status_text
        )
    status_display.short_description = 'Status'
    
    def forecast_scope(self, obj):
        """Show forecast scope and parameters."""
        results_count = obj.results.count() if obj.status in ['COMPLETED', 'PUBLISHED'] else 0
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Products: <strong>{}</strong><br/>'
            'History: {} months<br/>'
            'Horizon: {} months<br/>'
            'Granularity: {}'
            '</div>',
            results_count, obj.historical_period_months, 
            obj.forecast_horizon_months, obj.get_granularity_display()
        )
    forecast_scope.short_description = 'Scope'
    
    def accuracy_metrics(self, obj):
        """Show forecast accuracy metrics."""
        if obj.forecast_accuracy is None:
            return 'Not calculated'
        
        accuracy = obj.forecast_accuracy
        
        if accuracy >= 90:
            color = 'green'
            rating = 'Excellent'
        elif accuracy >= 80:
            color = 'blue'
            rating = 'Good'
        elif accuracy >= 70:
            color = 'orange'
            rating = 'Fair'
        else:
            color = 'red'
            rating = 'Poor'
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="color: {}; font-size: 1.3em; font-weight: bold;">{:.1f}%</span><br/>'
            '<small style="color: {};">{}</small><br/>'
            '<small>MAE: {:.2f}</small>'
            '</div>',
            color, accuracy, color, rating, obj.mean_absolute_error or 0
        )
    accuracy_metrics.short_description = 'Accuracy'
    
    def forecast_insights(self, obj):
        """Show key forecast insights."""
        if obj.status not in ['COMPLETED', 'PUBLISHED']:
            return 'Not available'
        
        results = obj.results.all()
        if not results:
            return 'No results'
        
        # Calculate insights
        high_growth = results.filter(trend_direction='INCREASING').count()
        declining = results.filter(trend_direction='DECREASING').count()
        volatile = results.filter(demand_volatility='HIGH').count()
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Growing: <span style="color: green;">{}</span><br/>'
            'Declining: <span style="color: red;">{}</span><br/>'
            'Volatile: <span style="color: orange;">{}</span><br/>'
            'Stable: <span style="color: blue;">{}</span>'
            '</div>',
            high_growth, declining, volatile, 
            results.count() - high_growth - declining - volatile
        )
    forecast_insights.short_description = 'Insights'
    
    def business_impact(self, obj):
        """Show business impact indicators."""
        if obj.status not in ['COMPLETED', 'PUBLISHED']:
            return 'Not available'
        
        results = obj.results.all()
        if not results:
            return 'No data'
        
        # Calculate impact metrics
        high_stockout_risk = results.filter(stockout_probability__gte=20).count()
        high_overstock_risk = results.filter(overstock_probability__gte=30).count()
        
        avg_confidence = results.aggregate(
            avg=Avg('confidence_score')
        )['avg'] or 0
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Stockout Risk: <span style="color: {};">{}</span><br/>'
            'Overstock Risk: <span style="color: {};">{}</span><br/>'
            'Avg Confidence: <span style="color: {};">{:.0f}%</span>'
            '</div>',
            'red' if high_stockout_risk > 10 else 'orange' if high_stockout_risk > 5 else 'green',
            high_stockout_risk,
            'red' if high_overstock_risk > 10 else 'orange' if high_overstock_risk > 5 else 'green',
            high_overstock_risk,
            'green' if avg_confidence >= 80 else 'orange' if avg_confidence >= 60 else 'red',
            avg_confidence
        )
    business_impact.short_description = 'Business Impact'
    
    def publication_status(self, obj):
        """Show publication status."""
        if obj.status == 'PUBLISHED':
            days_since_published = (timezone.now() - obj.published_at).days if obj.published_at else 0
            
            if days_since_published <= 7:
                freshness = "Fresh"
                color = "green"
            elif days_since_published <= 30:
                freshness = "Current"
                color = "blue"
            else:
                freshness = "Stale"
                color = "orange"
            
            return format_html(
                '<div style="text-align: center;">'
                '📊 Published<br/>'
                '<small style="color: {};">{}</small><br/>'
                '<small>({} days ago)</small>'
                '</div>',
                color, freshness, days_since_published
            )
        elif obj.status == 'COMPLETED':
            return format_html(
                '<div style="text-align: center;">'
                '⏳ Ready to Publish<br/>'
                '<small>Awaiting approval</small>'
                '</div>'
            )
        else:
            return format_html(
                '<div style="text-align: center;">'
                '📝 Not Published<br/>'
                '<small>In progress</small>'
                '</div>'
            )
    publication_status.short_description = 'Publication'
    
    def run_forecasting(self, request, queryset):
        """Run demand forecasting for selected configurations."""
        from ...services.analytics.demand_forecaster import DemandForecaster
        
        completed = 0
        for forecast in queryset.filter(status='DRAFT'):
            forecast.status = 'RUNNING'
            forecast.started_at = timezone.now()
            forecast.save()
            
            try:
                forecaster = DemandForecaster()
                results = forecaster.generate_forecast(forecast)
                
                forecast.status = 'COMPLETED'
                forecast.completed_at = timezone.now()
                forecast.save()
                completed += 1
                
            except Exception as e:
                forecast.status = 'FAILED'
                forecast.save()
        
        self.message_user(
            request,
            f'{completed} demand forecasts completed.',
            messages.SUCCESS
        )
    run_forecasting.short_description = "Run forecasting"
    
    def publish_forecasts(self, request, queryset):
        """Publish completed forecasts."""
        published = 0
        for forecast in queryset.filter(status='COMPLETED'):
            forecast.status = 'PUBLISHED'
            forecast.published_at = timezone.now()
            forecast.save()
            
            # Update inventory parameters based on forecast
            self._update_inventory_parameters(forecast)
            published += 1
        
        self.message_user(
            request,
            f'{published} forecasts published and inventory parameters updated.',
            messages.SUCCESS
        )
    publish_forecasts.short_description = "Publish forecasts"
    
    def _update_inventory_parameters(self, forecast):
        """Update inventory parameters based on forecast results."""
        for result in forecast.results.all():
            product = result.product
            
            # Update safety stock if recommendation is significantly different
            if abs(product.safety_stock - result.recommended_safety_stock) > product.safety_stock * 0.1:
                product.safety_stock = result.recommended_safety_stock
                product.save(update_fields=['safety_stock'])
            
            # Update reorder point
            if abs(product.reorder_level - result.recommended_reorder_point) > product.reorder_level * 0.1:
                product.reorder_level = result.recommended_reorder_point
                product.save(update_fields=['reorder_level'])