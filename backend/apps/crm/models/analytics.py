# ============================================================================
# backend/apps/crm/models/analytics.py - Analytics & Reporting Models
# ============================================================================

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid
import json

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class ReportCategory(TenantBaseModel, SoftDeleteMixin):
    """Report categorization for better organization"""
    
    # Category Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Display Settings
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=7, blank=True)  # Hex color
    sort_order = models.IntegerField(default=0)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    restricted_roles = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['level', 'sort_order', 'name']
        verbose_name = 'Report Category'
        verbose_name_plural = 'Report Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_report_category_code'
            ),
        ]
        
    def __str__(self):
        return self.name


class Report(TenantBaseModel, SoftDeleteMixin):
    """Comprehensive reporting system for CRM analytics"""
    
    REPORT_TYPES = [
        ('STANDARD', 'Standard Report'),
        ('DASHBOARD', 'Dashboard Report'),
        ('TABULAR', 'Tabular Report'),
        ('CHART', 'Chart Report'),
        ('PIVOT', 'Pivot Table'),
        ('TREND', 'Trend Analysis'),
        ('COMPARISON', 'Comparison Report'),
        ('SUMMARY', 'Summary Report'),
        ('DETAILED', 'Detailed Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    DATA_SOURCES = [
        ('LEADS', 'Leads'),
        ('ACCOUNTS', 'Accounts'),
        ('CONTACTS', 'Contacts'),
        ('OPPORTUNITIES', 'Opportunities'),
        ('ACTIVITIES', 'Activities'),
        ('CAMPAIGNS', 'Campaigns'),
        ('TICKETS', 'Support Tickets'),
        ('PRODUCTS', 'Products'),
        ('REVENUE', 'Revenue'),
        ('FORECASTS', 'Sales Forecasts'),
        ('PERFORMANCE', 'Performance Metrics'),
        ('MIXED', 'Multiple Sources'),
    ]
    
    VISUALIZATION_TYPES = [
        ('TABLE', 'Data Table'),
        ('BAR_CHART', 'Bar Chart'),
        ('LINE_CHART', 'Line Chart'),
        ('PIE_CHART', 'Pie Chart'),
        ('DONUT_CHART', 'Donut Chart'),
        ('AREA_CHART', 'Area Chart'),
        ('SCATTER_PLOT', 'Scatter Plot'),
        ('HISTOGRAM', 'Histogram'),
        ('HEATMAP', 'Heat Map'),
        ('GAUGE', 'Gauge Chart'),
        ('FUNNEL', 'Funnel Chart'),
        ('WATERFALL', 'Waterfall Chart'),
        ('TREEMAP', 'Tree Map'),
        ('BUBBLE_CHART', 'Bubble Chart'),
        ('MIXED', 'Mixed Charts'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='STANDARD')
    category = models.ForeignKey(
        ReportCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    
    # Data Configuration
    data_source = models.CharField(max_length=20, choices=DATA_SOURCES)
    visualization_type = models.CharField(max_length=20, choices=VISUALIZATION_TYPES, default='TABLE')
    
    # Query Configuration
    base_query = models.JSONField(default=dict)  # Base filters and conditions
    columns = models.JSONField(default=list)  # Selected columns/fields
    grouping = models.JSONField(default=list, blank=True)  # Group by fields
    sorting = models.JSONField(default=list, blank=True)  # Sort order
    filters = models.JSONField(default=list, blank=True)  # Dynamic filters
    aggregations = models.JSONField(default=list, blank=True)  # Sum, Count, Avg, etc.
    
    # Visualization Settings
    chart_config = models.JSONField(default=dict, blank=True)
    color_scheme = models.CharField(max_length=50, blank=True)
    display_options = models.JSONField(default=dict, blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_reports'
    )
    shared_with = models.ManyToManyField(
        User,
        through='ReportShare',
        related_name='shared_reports',
        blank=True
    )
    
    # Performance
    cache_duration_minutes = models.IntegerField(default=60)
    last_generated = models.DateTimeField(null=True, blank=True)
    generation_time_ms = models.IntegerField(default=0)
    
    # Usage Tracking
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('HOURLY', 'Hourly'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
        ],
        blank=True
    )
    schedule_time = models.TimeField(null=True, blank=True)
    schedule_day_of_week = models.IntegerField(null=True, blank=True)  # 0=Monday
    schedule_day_of_month = models.IntegerField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    email_recipients = models.JSONField(default=list, blank=True)
    
    # Export Settings
    export_formats = models.JSONField(default=list, blank=True)  # PDF, Excel, CSV
    auto_export = models.BooleanField(default=False)
    export_path = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'data_source', 'is_active']),
            models.Index(fields=['tenant', 'created_by']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'is_scheduled']),
        ]
        
    def __str__(self):
        return self.name
    
    def generate_data(self, user_filters=None, date_range=None):
        """Generate report data based on configuration"""
        from ..services.analytics_service import ReportGeneratorService
        
        service = ReportGeneratorService(self.tenant)
        return service.generate_report_data(self, user_filters, date_range)
    
    def can_view(self, user):
        """Check if user can view this report"""
        if self.is_public or self.created_by == user:
            return True
        
        return self.shared_with.filter(id=user.id).exists()
    
    def increment_view_count(self, user=None):
        """Increment view count and update last viewed"""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=['view_count', 'last_viewed'])
        
        # Log the view
        if user:
            ReportView.objects.create(
                tenant=self.tenant,
                report=self,
                viewed_by=user,
                viewed_at=timezone.now()
            )


class ReportShare(TenantBaseModel):
    """Report sharing permissions and settings"""
    
    PERMISSION_LEVELS = [
        ('VIEW', 'View Only'),
        ('EDIT', 'View and Edit'),
        ('ADMIN', 'Full Access'),
    ]
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='share_settings'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='report_shares'
    )
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='VIEW')
    shared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shared_reports_by_user'
    )
    shared_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['report', 'user'],
                name='unique_report_user_share'
            ),
        ]
        
    def __str__(self):
        return f'{self.report.name} shared with {self.user.get_full_name()}'


class Dashboard(TenantBaseModel, SoftDeleteMixin):
    """Interactive dashboards with multiple widgets"""
    
    DASHBOARD_TYPES = [
        ('EXECUTIVE', 'Executive Dashboard'),
        ('SALES', 'Sales Dashboard'),
        ('MARKETING', 'Marketing Dashboard'),
        ('SERVICE', 'Customer Service Dashboard'),
        ('PERFORMANCE', 'Performance Dashboard'),
        ('OPERATIONAL', 'Operational Dashboard'),
        ('PERSONAL', 'Personal Dashboard'),
        ('TEAM', 'Team Dashboard'),
        ('CUSTOM', 'Custom Dashboard'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES, default='CUSTOM')
    
    # Layout Configuration
    layout = models.JSONField(default=dict)  # Grid layout configuration
    theme = models.CharField(max_length=50, default='default')
    background_color = models.CharField(max_length=7, blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_dashboards'
    )
    shared_with = models.ManyToManyField(
        User,
        through='DashboardShare',
        related_name='shared_dashboards',
        blank=True
    )
    
    # Settings
    auto_refresh_interval = models.IntegerField(default=300)  # seconds
    full_screen_mode = models.BooleanField(default=False)
    
    # Usage Tracking
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'dashboard_type', 'is_active']),
            models.Index(fields=['tenant', 'created_by']),
            models.Index(fields=['tenant', 'is_public']),
        ]
        
    def __str__(self):
        return self.name
    
    def can_view(self, user):
        """Check if user can view this dashboard"""
        if self.is_public or self.created_by == user:
            return True
        
        return self.shared_with.filter(id=user.id).exists()


class DashboardShare(TenantBaseModel):
    """Dashboard sharing permissions"""
    
    PERMISSION_LEVELS = [
        ('VIEW', 'View Only'),
        ('EDIT', 'View and Edit'),
        ('ADMIN', 'Full Access'),
    ]
    
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='share_settings'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_shares'
    )
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='VIEW')
    shared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shared_dashboards_by_user'
    )
    shared_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dashboard', 'user'],
                name='unique_dashboard_user_share'
            ),
        ]
        
    def __str__(self):
        return f'{self.dashboard.name} shared with {self.user.get_full_name()}'


class DashboardWidget(TenantBaseModel, SoftDeleteMixin):
    """Individual widgets within dashboards"""
    
    WIDGET_TYPES = [
        ('METRIC', 'Key Metric'),
        ('CHART', 'Chart Widget'),
        ('TABLE', 'Data Table'),
        ('LIST', 'List Widget'),
        ('PROGRESS', 'Progress Bar'),
        ('GAUGE', 'Gauge Chart'),
        ('MAP', 'Geographic Map'),
        ('TIMELINE', 'Timeline'),
        ('CALENDAR', 'Calendar'),
        ('FEED', 'Activity Feed'),
        ('IFRAME', 'External Content'),
        ('TEXT', 'Text/HTML'),
        ('IMAGE', 'Image Widget'),
        ('CUSTOM', 'Custom Widget'),
    ]
    
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widgets'
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dashboard_widgets'
    )
    
    # Widget Configuration
    title = models.CharField(max_length=255)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    description = models.TextField(blank=True)
    
    # Layout and Position
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    width = models.IntegerField(default=4)
    height = models.IntegerField(default=3)
    z_index = models.IntegerField(default=1)
    
    # Display Settings
    background_color = models.CharField(max_length=7, blank=True)
    border_color = models.CharField(max_length=7, blank=True)
    text_color = models.CharField(max_length=7, blank=True)
    font_size = models.IntegerField(default=14)
    
    # Data Configuration
    data_config = models.JSONField(default=dict)
    filters = models.JSONField(default=dict, blank=True)
    refresh_interval = models.IntegerField(default=300)  # seconds
    
    # Widget Settings
    show_title = models.BooleanField(default=True)
    show_border = models.BooleanField(default=True)
    is_resizable = models.BooleanField(default=True)
    is_draggable = models.BooleanField(default=True)
    
    # Caching
    cache_enabled = models.BooleanField(default=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['dashboard', 'position_y', 'position_x']
        indexes = [
            models.Index(fields=['tenant', 'dashboard']),
            models.Index(fields=['tenant', 'widget_type']),
        ]
        
    def __str__(self):
        return f'{self.dashboard.name} - {self.title}'


class Forecast(TenantBaseModel, SoftDeleteMixin):
    """Sales forecasting and predictive analytics"""
    
    FORECAST_TYPES = [
        ('REVENUE', 'Revenue Forecast'),
        ('SALES_VOLUME', 'Sales Volume Forecast'),
        ('PIPELINE', 'Pipeline Forecast'),
        ('QUOTA', 'Quota Achievement'),
        ('TERRITORY', 'Territory Forecast'),
        ('PRODUCT', 'Product Forecast'),
        ('TEAM', 'Team Performance'),
        ('INDIVIDUAL', 'Individual Performance'),
        ('QUARTERLY', 'Quarterly Forecast'),
        ('ANNUAL', 'Annual Forecast'),
    ]
    
    FORECAST_METHODS = [
        ('HISTORICAL', 'Historical Trend'),
        ('PIPELINE', 'Pipeline Analysis'),
        ('REGRESSION', 'Linear Regression'),
        ('MOVING_AVERAGE', 'Moving Average'),
        ('EXPONENTIAL', 'Exponential Smoothing'),
        ('MACHINE_LEARNING', 'ML Algorithm'),
        ('MANUAL', 'Manual Input'),
        ('HYBRID', 'Hybrid Method'),
    ]
    
    PERIOD_TYPES = [
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPES)
    
    # Forecast Configuration
    method = models.CharField(max_length=20, choices=FORECAST_METHODS, default='PIPELINE')
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPES, default='MONTHLY')
    forecast_horizon_periods = models.IntegerField(default=12)
    
    # Time Range
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Target Configuration
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='individual_forecasts'
    )
    target_team = models.CharField(max_length=255, blank=True)
    target_territory = models.CharField(max_length=255, blank=True)
    target_product = models.CharField(max_length=255, blank=True)
    
    # Model Parameters
    historical_periods = models.IntegerField(default=12)
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00'),
        validators=[MinValueValidator(50), MaxValueValidator(99.99)]
    )
    seasonality_enabled = models.BooleanField(default=True)
    trend_analysis = models.BooleanField(default=True)
    
    # Results
    forecast_data = models.JSONField(default=dict)
    accuracy_metrics = models.JSONField(default=dict, blank=True)
    confidence_intervals = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_calculated = models.DateTimeField(null=True, blank=True)
    calculation_time_ms = models.IntegerField(default=0)
    
    # Approval
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_forecasts'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-update
    auto_recalculate = models.BooleanField(default=True)
    recalculate_frequency_days = models.IntegerField(default=7)
    next_calculation = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'forecast_type', 'is_active']),
            models.Index(fields=['tenant', 'target_user']),
            models.Index(fields=['tenant', 'method']),
            models.Index(fields=['tenant', 'last_calculated']),
        ]
        
    def __str__(self):
        return self.name
    
    def calculate_forecast(self):
        """Calculate forecast using specified method"""
        from ..services.forecast_service import ForecastService
        
        service = ForecastService(self.tenant)
        result = service.calculate_forecast(self)
        
        self.forecast_data = result.get('forecast_data', {})
        self.accuracy_metrics = result.get('accuracy_metrics', {})
        self.confidence_intervals = result.get('confidence_intervals', {})
        self.last_calculated = timezone.now()
        self.calculation_time_ms = result.get('calculation_time_ms', 0)
        
        if self.auto_recalculate:
            self.next_calculation = timezone.now() + timezone.timedelta(days=self.recalculate_frequency_days)
        
        self.save()
        return result
    
    @property
    def accuracy_score(self):
        """Get overall accuracy score"""
        return self.accuracy_metrics.get('overall_accuracy', 0)


class PerformanceMetric(TenantBaseModel, SoftDeleteMixin):
    """KPI and performance metric definitions"""
    
    METRIC_TYPES = [
        ('REVENUE', 'Revenue Metric'),
        ('SALES', 'Sales Metric'),
        ('MARKETING', 'Marketing Metric'),
        ('SERVICE', 'Service Metric'),
        ('EFFICIENCY', 'Efficiency Metric'),
        ('QUALITY', 'Quality Metric'),
        ('GROWTH', 'Growth Metric'),
        ('RETENTION', 'Retention Metric'),
        ('CONVERSION', 'Conversion Metric'),
        ('ENGAGEMENT', 'Engagement Metric'),
        ('COST', 'Cost Metric'),
        ('PRODUCTIVITY', 'Productivity Metric'),
    ]
    
    CALCULATION_METHODS = [
        ('SUM', 'Sum'),
        ('COUNT', 'Count'),
        ('AVERAGE', 'Average'),
        ('PERCENTAGE', 'Percentage'),
        ('RATIO', 'Ratio'),
        ('MEDIAN', 'Median'),
        ('MIN', 'Minimum'),
        ('MAX', 'Maximum'),
        ('GROWTH_RATE', 'Growth Rate'),
        ('VARIANCE', 'Variance'),
        ('CUSTOM', 'Custom Formula'),
    ]
    
    FREQUENCY_OPTIONS = [
        ('REAL_TIME', 'Real-time'),
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    
    # Calculation Configuration
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHODS)
    formula = models.TextField(blank=True)  # Custom formula if needed
    data_source = models.CharField(max_length=100)
    source_fields = models.JSONField(default=list)
    filters = models.JSONField(default=dict, blank=True)
    
    # Display Settings
    unit = models.CharField(max_length=50, blank=True)  # $, %, units, etc.
    decimal_places = models.IntegerField(default=2)
    format_style = models.CharField(
        max_length=20,
        choices=[
            ('NUMBER', 'Number'),
            ('CURRENCY', 'Currency'),
            ('PERCENTAGE', 'Percentage'),
            ('DURATION', 'Duration'),
            ('CUSTOM', 'Custom'),
        ],
        default='NUMBER'
    )
    
    # Target and Benchmarks
    target_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    benchmark_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    threshold_red = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    threshold_yellow = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    threshold_green = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Calculation Settings
    calculation_frequency = models.CharField(max_length=15, choices=FREQUENCY_OPTIONS, default='DAILY')
    last_calculated = models.DateTimeField(null=True, blank=True)
    next_calculation = models.DateTimeField(null=True, blank=True)
    
    # Current Values
    current_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    previous_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    trend_direction = models.CharField(
        max_length=10,
        choices=[('UP', 'Up'), ('DOWN', 'Down'), ('FLAT', 'Flat')],
        blank=True
    )
    
    # Settings
    is_kpi = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    track_history = models.BooleanField(default=True)
    
    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_metrics'
    )
    
    class Meta:
        ordering = ['metric_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_performance_metric'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'metric_type', 'is_active']),
            models.Index(fields=['tenant', 'is_kpi']),
            models.Index(fields=['tenant', 'calculation_frequency']),
        ]
        
    def __str__(self):
        return self.display_name
    
    def calculate_value(self, date_range=None):
        """Calculate metric value"""
        from ..services.metrics_service import MetricsCalculationService
        
        service = MetricsCalculationService(self.tenant)
        result = service.calculate_metric(self, date_range)
        
        self.previous_value = self.current_value
        self.current_value = result.get('value')
        self.trend_direction = result.get('trend_direction', 'FLAT')
        self.last_calculated = timezone.now()
        
        # Schedule next calculation
        if self.calculation_frequency != 'REAL_TIME':
            from datetime import timedelta
            frequency_map = {
                'HOURLY': timedelta(hours=1),
                'DAILY': timedelta(days=1),
                'WEEKLY': timedelta(weeks=1),
                'MONTHLY': timedelta(days=30),
                'QUARTERLY': timedelta(days=90),
                'ANNUALLY': timedelta(days=365),
            }
            if self.calculation_frequency in frequency_map:
                self.next_calculation = timezone.now() + frequency_map[self.calculation_frequency]
        
        self.save()
        
        # Store historical value if tracking enabled
        if self.track_history:
            MetricHistory.objects.create(
                tenant=self.tenant,
                metric=self,
                value=self.current_value,
                calculated_at=self.last_calculated,
                period_start=date_range.get('start') if date_range else None,
                period_end=date_range.get('end') if date_range else None
            )
        
        return result
    
    @property
    def performance_status(self):
        """Get performance status based on thresholds"""
        if not self.current_value:
            return 'UNKNOWN'
        
        if self.threshold_green and self.current_value >= self.threshold_green:
            return 'GOOD'
        elif self.threshold_yellow and self.current_value >= self.threshold_yellow:
            return 'WARNING'
        elif self.threshold_red:
            return 'CRITICAL'
        
        return 'UNKNOWN'
    
    @property
    def target_achievement(self):
        """Calculate target achievement percentage"""
        if self.target_value and self.current_value and self.target_value > 0:
            return (self.current_value / self.target_value) * 100
        return None


class MetricHistory(TenantBaseModel):
    """Historical values for performance metrics"""
    
    metric = models.ForeignKey(
        PerformanceMetric,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    # Value Information
    value = models.DecimalField(max_digits=15, decimal_places=2)
    calculated_at = models.DateTimeField()
    
    # Period Information
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    
    # Context
    calculation_method = models.CharField(max_length=100, blank=True)
    data_points = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['tenant', 'metric', 'calculated_at']),
            models.Index(fields=['tenant', 'period_start', 'period_end']),
        ]
        
    def __str__(self):
        return f'{self.metric.name} - {self.value} at {self.calculated_at}'


class ReportView(TenantBaseModel):
    """Track report views for analytics"""
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='view_logs'
    )
    viewed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='report_views'
    )
    viewed_at = models.DateTimeField()
    
    # Context Information
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # View Details
    filters_applied = models.JSONField(default=dict, blank=True)
    date_range = models.JSONField(default=dict, blank=True)
    export_format = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['tenant', 'report', 'viewed_at']),
            models.Index(fields=['tenant', 'viewed_by']),
        ]
        
    def __str__(self):
        return f'{self.report.name} viewed by {self.viewed_by.get_full_name()}'


class AnalyticsConfiguration(TenantBaseModel):
    """Analytics system configuration per tenant"""
    
    # Data Retention
    data_retention_days = models.IntegerField(default=365)
    archive_old_data = models.BooleanField(default=True)
    
    # Performance Settings
    enable_caching = models.BooleanField(default=True)
    cache_duration_minutes = models.IntegerField(default=60)
    max_query_time_seconds = models.IntegerField(default=30)
    
    # Automation
    auto_generate_reports = models.BooleanField(default=True)
    auto_calculate_metrics = models.BooleanField(default=True)
    send_alerts = models.BooleanField(default=True)
    
    # Export Settings
    default_export_format = models.CharField(
        max_length=10,
        choices=[
            ('PDF', 'PDF'),
            ('EXCEL', 'Excel'),
            ('CSV', 'CSV'),
        ],
        default='PDF'
    )
    max_export_rows = models.IntegerField(default=10000)
    
    # Security
    require_approval_for_sensitive_reports = models.BooleanField(default=True)
    sensitive_fields = models.JSONField(default=list, blank=True)
    
    # Integration
    external_analytics_enabled = models.BooleanField(default=False)
    external_analytics_config = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Analytics Configuration'
        verbose_name_plural = 'Analytics Configurations'
        
    def __str__(self):
        return f'Analytics Config - {self.tenant.name}'


class AlertRule(TenantBaseModel, SoftDeleteMixin):
    """Automated alerts based on metrics and thresholds"""
    
    ALERT_TYPES = [
        ('METRIC_THRESHOLD', 'Metric Threshold'),
        ('TREND_CHANGE', 'Trend Change'),
        ('ANOMALY', 'Data Anomaly'),
        ('TARGET_MISS', 'Target Miss'),
        ('FORECAST_DEVIATION', 'Forecast Deviation'),
        ('CUSTOM', 'Custom Rule'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Rule Configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='MEDIUM')
    
    # Target
    metric = models.ForeignKey(
        PerformanceMetric,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alert_rules'
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alert_rules'
    )
    
    # Conditions
    conditions = models.JSONField(default=dict)
    threshold_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Notification Settings
    notification_channels = models.JSONField(default=list)  # email, sms, slack, etc.
    recipients = models.JSONField(default=list)
    message_template = models.TextField(blank=True)
    
    # Timing
    check_frequency_minutes = models.IntegerField(default=60)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    
    # Settings
    is_enabled = models.BooleanField(default=True)
    suppress_duplicates = models.BooleanField(default=True)
    suppression_period_minutes = models.IntegerField(default=60)
    
    class Meta:
        ordering = ['severity', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_enabled', 'is_active']),
            models.Index(fields=['tenant', 'metric']),
            models.Index(fields=['tenant', 'last_checked']),
        ]
        
    def __str__(self):
        return self.name
    
    def check_conditions(self):
        """Check if alert conditions are met"""
        from ..services.alert_service import AlertService
        
        service = AlertService(self.tenant)
        return service.check_alert_rule(self)
    
    def trigger_alert(self, context=None):
        """Trigger alert notification"""
        from ..services.alert_service import AlertService
        
        service = AlertService(self.tenant)
        service.trigger_alert(self, context)
        
        self.last_triggered = timezone.now()
        self.save(update_fields=['last_triggered'])