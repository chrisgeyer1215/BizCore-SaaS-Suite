# ============================================================================
# backend/apps/crm/serializers/analytics.py - Analytics & Reporting Serializers
# ============================================================================

from rest_framework import serializers
from django.utils import timezone
from django.db.models import Avg, Sum, Count
from datetime import timedelta
from ..models import (
    ReportCategory, Report, ReportShare, Dashboard, DashboardShare, 
    DashboardWidget, Forecast, PerformanceMetric, MetricHistory, 
    ReportView, AnalyticsConfiguration, AlertRule
)
from .user import UserBasicSerializer


class ReportCategorySerializer(serializers.ModelSerializer):
    """Report category serializer with hierarchy"""
    
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subcategories_count = serializers.SerializerMethodField()
    reports_count = serializers.SerializerMethodField()
    hierarchy_path = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportCategory
        fields = [
            'id', 'name', 'code', 'description', 'parent', 'parent_name',
            'level', 'icon', 'color', 'sort_order', 'is_public',
            'restricted_roles', 'subcategories_count', 'reports_count',
            'hierarchy_path', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_name', 'level', 'subcategories_count',
            'reports_count', 'hierarchy_path', 'created_at', 'updated_at'
        ]
    
    def get_subcategories_count(self, obj):
        """Get count of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    
    def get_reports_count(self, obj):
        """Get count of reports in category"""
        return obj.reports.filter(is_active=True).count()
    
    def get_hierarchy_path(self, obj):
        """Get full hierarchy path"""
        path = []
        current = obj
        while current:
            path.insert(0, current.name)
            current = current.parent
        return " > ".join(path)


class ReportShareSerializer(serializers.ModelSerializer):
    """Report sharing serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    shared_by_details = UserBasicSerializer(source='shared_by', read_only=True)
    expires_in_days = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportShare
        fields = [
            'id', 'user', 'user_details', 'permission_level', 'shared_by',
            'shared_by_details', 'shared_at', 'expires_at', 'expires_in_days'
        ]
        read_only_fields = [
            'id', 'user_details', 'shared_by_details', 'shared_at', 'expires_in_days'
        ]
    
    def get_expires_in_days(self, obj):
        """Get days until expiration"""
        if obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            return max(0, remaining.days)
        return None


class ReportSerializer(serializers.ModelSerializer):
    """Comprehensive report serializer"""
    
    category_details = ReportCategorySerializer(source='category', read_only=True)
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    shares = ReportShareSerializer(source='share_settings', many=True, read_only=True)
    
    # Performance metrics
    performance_stats = serializers.SerializerMethodField()
    usage_trend = serializers.SerializerMethodField()
    generation_performance = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'description', 'report_type', 'category', 'category_details',
            'data_source', 'visualization_type',
            # Query configuration
            'base_query', 'columns', 'grouping', 'sorting', 'filters', 'aggregations',
            # Visualization
            'chart_config', 'color_scheme', 'display_options',
            # Access control
            'is_public', 'created_by', 'created_by_details', 'shares',
            # Performance
            'cache_duration_minutes', 'last_generated', 'generation_time_ms',
            'performance_stats', 'usage_trend', 'generation_performance',
            # Usage
            'view_count', 'last_viewed',
            # Scheduling
            'is_scheduled', 'schedule_frequency', 'schedule_time',
            'schedule_day_of_week', 'schedule_day_of_month', 'next_run',
            'email_recipients',
            # Export
            'export_formats', 'auto_export', 'export_path',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'category_details', 'created_by_details', 'shares',
            'last_generated', 'generation_time_ms', 'performance_stats',
            'usage_trend', 'generation_performance', 'view_count', 'last_viewed',
            'next_run', 'created_at', 'updated_at'
        ]
    
    def get_performance_stats(self, obj):
        """Get report performance statistics"""
        return {
            'total_views': obj.view_count,
            'average_generation_time': obj.generation_time_ms,
            'last_30_days_views': obj.view_logs.filter(
                viewed_at__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'cache_hit_rate': self._calculate_cache_hit_rate(obj)
        }
    
    def get_usage_trend(self, obj):
        """Get usage trend over time"""
        # Get daily view counts for last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        daily_views = {}
        for view in obj.view_logs.filter(viewed_at__date__range=[start_date, end_date]):
            date_key = view.viewed_at.date().isoformat()
            daily_views[date_key] = daily_views.get(date_key, 0) + 1
        
        return daily_views
    
    def get_generation_performance(self, obj):
        """Get generation performance analysis"""
        return {
            'average_time_ms': obj.generation_time_ms,
            'performance_rating': 'Fast' if obj.generation_time_ms < 1000 else 'Medium' if obj.generation_time_ms < 5000 else 'Slow',
            'optimization_suggestions': self._get_optimization_suggestions(obj)
        }
    
    def _calculate_cache_hit_rate(self, obj):
        """Calculate cache hit rate"""
        # This would require cache hit/miss tracking
        return 85.0  # Placeholder
    
    def _get_optimization_suggestions(self, obj):
        """Get optimization suggestions"""
        suggestions = []
        
        if obj.generation_time_ms > 5000:
            suggestions.append("Consider adding database indexes for filtered fields")
        
        if obj.cache_duration_minutes < 60:
            suggestions.append("Increase cache duration for better performance")
        
        if len(obj.columns) > 20:
            suggestions.append("Reduce number of columns for faster generation")
        
        return suggestions


class DashboardShareSerializer(serializers.ModelSerializer):
    """Dashboard sharing serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    shared_by_details = UserBasicSerializer(source='shared_by', read_only=True)
    
    class Meta:
        model = DashboardShare
        fields = [
            'id', 'user', 'user_details', 'permission_level', 'shared_by',
            'shared_by_details', 'shared_at'
        ]
        read_only_fields = ['id', 'user_details', 'shared_by_details', 'shared_at']


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """Dashboard widget serializer"""
    
    report_details = serializers.SerializerMethodField()
    widget_data = serializers.SerializerMethodField()
    
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'title', 'widget_type', 'description', 'report', 'report_details',
            # Layout
            'position_x', 'position_y', 'width', 'height', 'z_index',
            # Display
            'background_color', 'border_color', 'text_color', 'font_size',
            # Configuration
            'data_config', 'filters', 'refresh_interval',
            # Settings
            'show_title', 'show_border', 'is_resizable', 'is_draggable',
            # Data
            'widget_data', 'cache_enabled', 'last_updated',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'report_details', 'widget_data', 'last_updated',
            'created_at', 'updated_at'
        ]
    
    def get_report_details(self, obj):
        """Get basic report details"""
        if obj.report:
            return {
                'id': obj.report.id,
                'name': obj.report.name,
                'data_source': obj.report.data_source,
                'visualization_type': obj.report.visualization_type
            }
        return None
    
    def get_widget_data(self, obj):
        """Get widget data based on type"""
        if obj.widget_type == 'METRIC':
            return self._get_metric_data(obj)
        elif obj.widget_type == 'CHART':
            return self._get_chart_data(obj)
        elif obj.widget_type == 'TABLE':
            return self._get_table_data(obj)
        elif obj.widget_type == 'PROGRESS':
            return self._get_progress_data(obj)
        
        return {}
    
    def _get_metric_data(self, obj):
        """Get data for metric widgets"""
        return {
            'current_value': 12543,
            'previous_value': 11234,
            'change_percentage': 11.65,
            'trend': 'up',
            'unit': '$',
            'format': 'currency'
        }
    
    def _get_chart_data(self, obj):
        """Get data for chart widgets"""
        return {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            'datasets': [{
                'label': 'Revenue',
                'data': [12000, 19000, 13000, 15000, 22000],
                'backgroundColor': '#007bff'
            }]
        }
    
    def _get_table_data(self, obj):
        """Get data for table widgets"""
        return {
            'headers': ['Name', 'Value', 'Change'],
            'rows': [
                ['Leads', '1,234', '+5.2%'],
                ['Opportunities', '856', '+12.1%'],
                ['Revenue', '$125,430', '+8.9%']
            ]
        }
    
    def _get_progress_data(self, obj):
        """Get data for progress widgets"""
        return {
            'current': 75,
            'target': 100,
            'percentage': 75,
            'status': 'on_track'
        }


class DashboardSerializer(serializers.ModelSerializer):
    """Comprehensive dashboard serializer"""
    
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    widgets = DashboardWidgetSerializer(many=True, read_only=True)
    shares = DashboardShareSerializer(source='share_settings', many=True, read_only=True)
    
    # Performance metrics
    widgets_count = serializers.SerializerMethodField()
    load_time_estimate = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'description', 'dashboard_type', 'layout', 'theme',
            'background_color', 'is_public', 'is_default', 'created_by',
            'created_by_details', 'auto_refresh_interval', 'full_screen_mode',
            'widgets', 'widgets_count', 'shares', 'view_count', 'last_viewed',
            'load_time_estimate', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by_details', 'widgets', 'widgets_count', 'shares',
            'view_count', 'last_viewed', 'load_time_estimate', 'created_at', 'updated_at'
        ]
    
    def get_widgets_count(self, obj):
        """Get count of widgets"""
        return obj.widgets.filter(is_active=True).count()
    
    def get_load_time_estimate(self, obj):
        """Estimate dashboard load time"""
        base_time = 500  # Base load time in ms
        widget_count = self.get_widgets_count(obj)
        estimated_time = base_time + (widget_count * 200)  # 200ms per widget
        
        return {
            'estimated_ms': estimated_time,
            'performance_level': 'Fast' if estimated_time < 2000 else 'Medium' if estimated_time < 5000 else 'Slow'
        }


class ForecastSerializer(serializers.ModelSerializer):
    """Sales forecasting serializer"""
    
    target_user_details = UserBasicSerializer(source='target_user', read_only=True)
    approved_by_details = UserBasicSerializer(source='approved_by', read_only=True)
    
    # Forecast analysis
    accuracy_score = serializers.ReadOnlyField()
    forecast_summary = serializers.SerializerMethodField()
    trend_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = Forecast
        fields = [
            'id', 'name', 'description', 'forecast_type', 'method', 'period_type',
            'forecast_horizon_periods', 'start_date', 'end_date',
            # Target configuration
            'target_user', 'target_user_details', 'target_team', 'target_territory',
            'target_product',
            # Model parameters
            'historical_periods', 'confidence_level', 'seasonality_enabled',
            'trend_analysis', 
            # Results
            'forecast_data', 'accuracy_metrics', 'confidence_intervals',
            'accuracy_score', 'forecast_summary', 'trend_analysis',
            # Status
            'is_active', 'last_calculated', 'calculation_time_ms',
            # Approval
            'requires_approval', 'approved_by', 'approved_by_details', 'approved_at',
            # Automation
            'auto_recalculate', 'recalculate_frequency_days', 'next_calculation',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'target_user_details', 'approved_by_details', 'forecast_data',
            'accuracy_metrics', 'confidence_intervals', 'accuracy_score',
            'forecast_summary', 'trend_analysis', 'last_calculated',
            'calculation_time_ms', 'next_calculation', 'created_at', 'updated_at'
        ]
    
    def get_forecast_summary(self, obj):
        """Get forecast summary"""
        ifreturn {
                'total_periods': len(obj.forecast_data.get('periods', [])),
                'forecasted_revenue': sum(obj.forecast_data.get('values', [])),
                'confidence_level': float(obj.confidence_level),
                'method_used': obj.method,
                'last_updated': obj.last_calculated
            }
        return {}
    
    def get_trend_analysis(self, obj):
        """Get trend analysis"""
        if obj.forecast_data and 'tren
            trend_data = obj.forecast_data['trend']
            return {
                'direction': trend_data.get('direction', 'stable'),
                'strength': trend_data.get('strength', 'medium'),
                'seasonality_detected': obj.seasonality_enabled,
                'growth_rate': trend_data.get('growth_rate', 0)
            }
        return {}


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Performance metric serializer with historical data"""
    
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    
    # Performance analysis
    performance_status = serializers.ReadOnlyField()
    target_achievement = serializers.ReadOnlyField()
    trend_analysis = serializers.SerializerMethodField()
    historical_data = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'name', 'display_name', 'description', 'metric_type',
            # Calculation
            'calculation_method', 'formula', 'data_source', 'source_fields', 'filters',
            # Display
            'unit', 'decimal_places', 'format_style',
            # Targets and thresholds
            'target_value', 'benchmark_value', 'threshold_red', 'threshold_yellow',
            'threshold_green', 'performance_status', 'target_achievement',
            # Calculation settings
            'calculation_frequency', 'last_calculated', 'next_calculation',
            # Current values
            'current_value', 'previous_value', 'trend_direction',
            'trend_analysis', 'historical_data',
            # Settings
            'is_kpi', 'is_visible', 'track_history', 'owner', 'owner_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'owner_details', 'performance_status', 'target_achievement',
            'last_calculated', 'next_calculation', 'current_value', 'previous_value',
            'trend_direction', 'trend_analysis', 'historical_data', 'created_at', 'updated_at'
        ]
    
    def get_trend_analysis(self, obj):
        """Get trend analysis"""
        if obj.current_value and obj.previous_value:
            change = obj.current_value - obj.previous_value
            change_percent = (change / obj.previous_value) * 100 if obj.previous_value != 0 else 0
            
            return {
                'direction': obj.trend_direction,
                'change_absolute': float(change),
                'change_percentage': float(change_percent),
                'interpretation': 'Improving' if change > 0 else 'Declining' if change < 0 else 'Stable'
            }
        return {}
    
    def get_historical_data(self, obj):
        """Get recent historical data points"""
        if obj.track_history:
            recent_history = obj.history.order_by('-calculated_at')[:30]
            return [
                {
                    'date': history.calculated_at.date().isoformat(),
                    'value': float(history.value)
                }
                for history in recent_history
            ]
        return []


class MetricHistorySerializer(serializers.ModelSerializer):
    """Metric history serializer"""
    
    metric_name = serializers.CharField(source='metric.name', read_only=True)
    
    class Meta:
        model = MetricHistory
        fields = [
            'id', 'metric', 'metric_name', 'value', 'calculated_at',
            'period_start', 'period_end', 'calculation_method', 'data_points'
        ]
        read_only_fields = ['id', 'metric_name']


class AnalyticsConfigurationSerializer(serializers.ModelSerializer):
    """Analytics configuration serializer"""
    
    performance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalyticsConfiguration
        fields = [
            'id', 'data_retention_days', 'archive_old_data', 'enable_caching',
            'cache_duration_minutes', 'max_query_time_seconds', 'auto_generate_reports',
            'auto_calculate_metrics', 'send_alerts', 'default_export_format',
            'max_export_rows', 'require_approval_for_sensitive_reports',
            'sensitive_fields', 'external_analytics_enabled', 'external_analytics_config',
            'performance_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'performance_summary', 'created_at', 'updated_at']
    
    def get_performance_summary(self, obj):
        """Get analytics performance summary"""
        return {
            'cache_enabled': obj.enable_caching,
            'cache_duration': f"{obj.cache_duration_minutes} minutes",
            'max_query_time': f"{obj.max_query_time_seconds} seconds",
            'data_retention': f"{obj.data_retention_days} days",
            'automation_level': 'High' if obj.auto_generate_reports and obj.auto_calculate_metrics else 'Medium'
        }


class AlertRuleSerializer(serializers.ModelSerializer):
    """Alert rule serializer"""
    
    metric_details = PerformanceMetricSerializer(source='metric', read_only=True)
    report_details = ReportSerializer(source='report', read_only=True)
    
    # Alert status
    alert_status = serializers.SerializerMethodField()
    next_check = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'description', 'alert_type', 'severity',
            'metric', 'metric_details', 'report', 'report_details',
            'conditions', 'threshold_value', 'notification_channels',
            'recipients', 'message_template', 'check_frequency_minutes',
            'last_checked', 'last_triggered', 'alert_status', 'next_check',
            'is_enabled', 'suppress_duplicates', 'suppression_period_minutes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'metric_details', 'report_details', 'last_checked',
            'last_triggered', 'alert_status', 'next_check', 'created_at', 'updated_at'
        ]
    
    def get_alert_status(self, obj):
        """Get current alert status"""
        if not obj.is_enabled:
            return 'Disabled'
        
        if obj.last_triggered:
            time_since_trigger = timezone.now() - obj.last_triggered
            if time_since_trigger.total_seconds() < obj.suppression_period_minutes * 60:
                return 'Suppressed'
        
        return 'Active'
    
    def get_next_check(self, obj):
        """Get next check time"""
        if obj.last_checked:
            next_check = obj.last_checked + timedelta(minutes=obj.check_frequency_minutes)
            return next_check
        return timezone.now()