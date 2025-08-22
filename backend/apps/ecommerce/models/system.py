# ============================================================================
# backend/apps/ecommerce/models/system.py - AI-Powered E-commerce System Models
# ============================================================================

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import timedelta
import uuid
import json
import logging

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()
logger = logging.getLogger(__name__)


class AISystemConfiguration(TenantBaseModel, SoftDeleteMixin):
    """AI-powered system configuration with intelligent defaults and optimization"""
    
    CONFIG_TYPES = [
        ('AI_ENGINE', 'AI Engine Settings'),
        ('RECOMMENDATION', 'Recommendation System'),
        ('PERSONALIZATION', 'Personalization Engine'),
        ('PRICING', 'Dynamic Pricing'),
        ('SEARCH', 'Search Engine'),
        ('ANALYTICS', 'Analytics Engine'),
        ('PERFORMANCE', 'Performance Optimization'),
        ('SECURITY', 'Security & Fraud Detection'),
        ('WORKFLOW', 'Workflow Automation'),
        ('NOTIFICATION', 'Intelligent Notifications'),
    ]
    
    PRIORITY_LEVELS = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    # Configuration Identity
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES)
    key = models.CharField(max_length=100)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # AI Configuration Values
    value = models.JSONField()
    default_value = models.JSONField(null=True, blank=True)
    ai_recommended_value = models.JSONField(null=True, blank=True)
    optimization_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Intelligent Metadata
    is_ai_managed = models.BooleanField(default=False)
    auto_optimize = models.BooleanField(default=False)
    last_optimized = models.DateTimeField(null=True, blank=True)
    optimization_frequency_hours = models.IntegerField(default=24)
    
    # Performance Tracking
    usage_frequency = models.IntegerField(default=0)
    performance_impact = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    error_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Business Impact
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    business_value_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cost_impact = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Validation and Constraints
    validation_rules = models.JSONField(default=dict, blank=True)
    constraints = models.JSONField(default=dict, blank=True)
    dependencies = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['config_type', 'priority', 'key']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'config_type', 'key'],
                name='unique_tenant_ai_config'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'config_type', 'is_active']),
            models.Index(fields=['tenant', 'is_ai_managed']),
            models.Index(fields=['tenant', 'priority']),
        ]
    
    def __str__(self):
        return f'{self.config_type} - {self.display_name}'
    
    def get_effective_value(self):
        """Get the most effective configuration value"""
        if self.is_ai_managed and self.ai_recommended_value:
            return self.ai_recommended_value
        return self.value
    
    def optimize_configuration(self):
        """AI-powered configuration optimization"""
        if self.auto_optimize and self.is_ai_managed:
            # Implement AI optimization logic here
            optimization_data = {
                'performance_score': float(self.performance_impact),
                'error_rate': float(self.error_rate),
                'usage_frequency': self.usage_frequency,
                'business_value': float(self.business_value_score)
            }
            
            # AI recommendation logic would go here
            self.last_optimized = timezone.now()
            self.save()
    
    def track_usage(self):
        """Track configuration usage for optimization"""
        self.usage_frequency += 1
        self.save()


class AIPerformanceMonitor(TenantBaseModel):
    """Real-time AI system performance monitoring and optimization"""
    
    METRIC_TYPES = [
        ('RESPONSE_TIME', 'Response Time'),
        ('ACCURACY', 'Model Accuracy'),
        ('THROUGHPUT', 'System Throughput'),
        ('ERROR_RATE', 'Error Rate'),
        ('RESOURCE_USAGE', 'Resource Usage'),
        ('COST', 'Operational Cost'),
        ('USER_SATISFACTION', 'User Satisfaction'),
        ('BUSINESS_KPI', 'Business KPI'),
    ]
    
    ALERT_LEVELS = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    # Metric Identification
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    metric_name = models.CharField(max_length=100)
    component_name = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Performance Data
    value = models.DecimalField(max_digits=15, decimal_places=4)
    unit = models.CharField(max_length=20, blank=True)
    baseline_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    threshold_warning = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    threshold_critical = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Context Information
    request_id = models.UUIDField(null=True, blank=True)
    user_segment = models.CharField(max_length=50, blank=True)
    geographic_region = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(max_length=30, blank=True)
    
    # AI Analysis
    anomaly_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    is_anomaly = models.BooleanField(default=False)
    prediction_accuracy = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # Alert Management
    alert_level = models.CharField(max_length=10, choices=ALERT_LEVELS, null=True, blank=True)
    alert_triggered = models.BooleanField(default=False)
    alert_resolved = models.BooleanField(default=False)
    resolution_time = models.DateTimeField(null=True, blank=True)
    
    # Additional Metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'metric_type', 'timestamp']),
            models.Index(fields=['tenant', 'component_name', 'timestamp']),
            models.Index(fields=['tenant', 'is_anomaly']),
            models.Index(fields=['tenant', 'alert_triggered']),
        ]
    
    def __str__(self):
        return f'{self.component_name} - {self.metric_name}: {self.value}'
    
    def check_thresholds(self):
        """Check performance thresholds and trigger alerts"""
        if self.threshold_critical and self.value >= self.threshold_critical:
            self.alert_level = 'CRITICAL'
            self.alert_triggered = True
        elif self.threshold_warning and self.value >= self.threshold_warning:
            self.alert_level = 'WARNING'
            self.alert_triggered = True
        
        if self.alert_triggered:
            self.save()
            self.send_alert()
    
    def send_alert(self):
        """Send performance alert to administrators"""
        # Implementation for sending alerts would go here
        logger.warning(f"Performance alert: {self.component_name} {self.metric_name} = {self.value}")
    
    def detect_anomaly(self):
        """AI-powered anomaly detection"""
        # Implementation for anomaly detection would go here
        # This would use ML algorithms to detect unusual patterns
        pass


class AIModelRegistry(TenantBaseModel):
    """Registry for managing AI models with versioning and performance tracking"""
    
    MODEL_TYPES = [
        ('RECOMMENDATION', 'Product Recommendation'),
        ('SEARCH_RANKING', 'Search Ranking'),
        ('PERSONALIZATION', 'Personalization'),
        ('PRICING', 'Dynamic Pricing'),
        ('FRAUD_DETECTION', 'Fraud Detection'),
        ('CHURN_PREDICTION', 'Churn Prediction'),
        ('DEMAND_FORECASTING', 'Demand Forecasting'),
        ('SENTIMENT_ANALYSIS', 'Sentiment Analysis'),
        ('IMAGE_RECOGNITION', 'Image Recognition'),
        ('NLP', 'Natural Language Processing'),
    ]
    
    MODEL_STATUS = [
        ('DEVELOPMENT', 'In Development'),
        ('TESTING', 'Testing'),
        ('STAGING', 'Staging'),
        ('PRODUCTION', 'Production'),
        ('DEPRECATED', 'Deprecated'),
        ('RETIRED', 'Retired'),
    ]
    
    # Model Identity
    model_name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    version = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Model Files and Configuration
    model_file_path = models.CharField(max_length=500, blank=True)
    config_file_path = models.CharField(max_length=500, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    
    # Lifecycle Management
    status = models.CharField(max_length=15, choices=MODEL_STATUS, default='DEVELOPMENT')
    deployment_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    retirement_date = models.DateTimeField(null=True, blank=True)
    
    # Performance Metrics
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    precision_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    recall_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    auc_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    # Business Metrics
    business_impact_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    revenue_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    user_engagement_lift = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Training Information
    training_data_size = models.BigIntegerField(null=True, blank=True)
    training_duration_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    last_retrained = models.DateTimeField(null=True, blank=True)
    retrain_frequency_days = models.IntegerField(default=30)
    
    # Technical Specifications
    framework = models.CharField(max_length=50, blank=True)
    algorithm = models.CharField(max_length=100, blank=True)
    model_size_mb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    inference_time_ms = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Dependencies and Environment
    dependencies = models.JSONField(default=list, blank=True)
    environment_requirements = models.JSONField(default=dict, blank=True)
    deployment_config = models.JSONField(default=dict, blank=True)
    
    # Monitoring and Alerts
    monitoring_enabled = models.BooleanField(default=True)
    alert_thresholds = models.JSONField(default=dict, blank=True)
    health_check_endpoint = models.URLField(blank=True)
    
    class Meta:
        ordering = ['-deployment_date', 'model_name', 'version']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'model_name', 'version'],
                name='unique_tenant_model_version'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'model_type', 'status']),
            models.Index(fields=['tenant', 'status', 'deployment_date']),
        ]
    
    def __str__(self):
        return f'{self.model_name} v{self.version} ({self.status})'
    
    def is_production_ready(self):
        """Check if model is ready for production deployment"""
        return (
            self.status in ['TESTING', 'STAGING'] and
            self.accuracy_score and self.accuracy_score > 0.8 and
            self.model_file_path and
            self.parameters
        )
    
    def schedule_retraining(self):
        """Schedule model retraining based on performance degradation"""
        if (self.last_retrained and 
            timezone.now() - self.last_retrained > timedelta(days=self.retrain_frequency_days)):
            # Schedule retraining job
            return True
        return False
    
    def get_performance_summary(self):
        """Get comprehensive performance summary"""
        return {
            'accuracy': float(self.accuracy_score or 0),
            'precision': float(self.precision_score or 0),
            'recall': float(self.recall_score or 0),
            'f1': float(self.f1_score or 0),
            'auc': float(self.auc_score or 0),
            'business_impact': float(self.business_impact_score),
            'revenue_impact': float(self.revenue_impact),
            'inference_time': float(self.inference_time_ms or 0),
        }


class AIJobQueue(TenantBaseModel):
    """Intelligent job queue for AI tasks with priority management and optimization"""
    
    JOB_TYPES = [
        ('MODEL_TRAINING', 'Model Training'),
        ('MODEL_INFERENCE', 'Model Inference'),
        ('DATA_PROCESSING', 'Data Processing'),
        ('FEATURE_ENGINEERING', 'Feature Engineering'),
        ('MODEL_EVALUATION', 'Model Evaluation'),
        ('BATCH_PREDICTION', 'Batch Prediction'),
        ('DATA_SYNC', 'Data Synchronization'),
        ('ANALYTICS', 'Analytics Processing'),
        ('OPTIMIZATION', 'System Optimization'),
        ('CLEANUP', 'Data Cleanup'),
    ]
    
    JOB_STATUS = [
        ('QUEUED', 'Queued'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('RETRYING', 'Retrying'),
    ]
    
    PRIORITY_LEVELS = [
        ('URGENT', 'Urgent'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
        ('BACKGROUND', 'Background'),
    ]
    
    # Job Identification
    job_id = models.UUIDField(default=uuid.uuid4, unique=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Job Configuration
    parameters = models.JSONField(default=dict, blank=True)
    input_data = models.JSONField(default=dict, blank=True)
    expected_output = models.JSONField(default=dict, blank=True)
    
    # Scheduling and Priority
    priority = models.CharField(max_length=15, choices=PRIORITY_LEVELS, default='MEDIUM')
    scheduled_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField(null=True, blank=True)
    estimated_duration_minutes = models.IntegerField(null=True, blank=True)
    
    # Execution Status
    status = models.CharField(max_length=15, choices=JOB_STATUS, default='QUEUED')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    worker_id = models.CharField(max_length=100, blank=True)
    
    # Progress Tracking
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_step = models.CharField(max_length=255, blank=True)
    total_steps = models.IntegerField(null=True, blank=True)
    
    # Results and Output
    output_data = models.JSONField(default=dict, blank=True)
    result_summary = models.JSONField(default=dict, blank=True)
    log_messages = models.JSONField(default=list, blank=True)
    
    # Error Handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Resource Requirements
    cpu_requirements = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    memory_requirements_gb = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    gpu_required = models.BooleanField(default=False)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # Dependencies
    depends_on = models.ManyToManyField('self', blank=True, symmetrical=False)
    blocks_jobs = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='blocked_by')
    
    # Performance Metrics
    actual_duration_seconds = models.IntegerField(null=True, blank=True)
    resource_utilization = models.JSONField(default=dict, blank=True)
    efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', 'scheduled_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'priority']),
            models.Index(fields=['tenant', 'job_type', 'status']),
            models.Index(fields=['tenant', 'scheduled_at']),
            models.Index(fields=['job_id']),
        ]
    
    def __str__(self):
        return f'{self.name} ({self.status}) - {self.priority}'
    
    @property
    def is_overdue(self):
        """Check if job is overdue"""
        return self.deadline and timezone.now() > self.deadline and self.status != 'COMPLETED'
    
    @property
    def execution_time_seconds(self):
        """Calculate actual execution time"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return 0
    
    def can_start(self):
        """Check if job can start (all dependencies completed)"""
        return not self.depends_on.filter(status__in=['QUEUED', 'RUNNING', 'RETRYING']).exists()
    
    def update_progress(self, percentage, current_step=None, log_message=None):
        """Update job progress"""
        self.progress_percentage = min(100, max(0, percentage))
        if current_step:
            self.current_step = current_step
        if log_message:
            if not isinstance(self.log_messages, list):
                self.log_messages = []
            self.log_messages.append({
                'timestamp': timezone.now().isoformat(),
                'message': log_message
            })
        self.save()
    
    def mark_failed(self, error_message, error_details=None):
        """Mark job as failed with error details"""
        self.status = 'FAILED'
        self.error_message = error_message
        self.error_details = error_details or {}
        self.completed_at = timezone.now()
        self.save()
    
    def retry_job(self):
        """Retry failed job if retries available"""
        if self.retry_count < self.max_retries and self.status == 'FAILED':
            self.retry_count += 1
            self.status = 'QUEUED'
            self.started_at = None
            self.completed_at = None
            self.progress_percentage = 0
            self.error_message = ''
            self.save()
            return True
        return False


class AIAnalyticsDashboard(TenantBaseModel):
    """Intelligent analytics dashboard with AI-powered insights"""
    
    DASHBOARD_TYPES = [
        ('EXECUTIVE', 'Executive Summary'),
        ('OPERATIONAL', 'Operational Metrics'),
        ('CUSTOMER', 'Customer Analytics'),
        ('PRODUCT', 'Product Performance'),
        ('MARKETING', 'Marketing Analytics'),
        ('SALES', 'Sales Dashboard'),
        ('FINANCIAL', 'Financial Metrics'),
        ('TECHNICAL', 'Technical Metrics'),
        ('CUSTOM', 'Custom Dashboard'),
    ]
    
    INSIGHT_TYPES = [
        ('TREND', 'Trend Analysis'),
        ('ANOMALY', 'Anomaly Detection'),
        ('FORECAST', 'Forecasting'),
        ('CORRELATION', 'Correlation Analysis'),
        ('SEGMENTATION', 'Customer Segmentation'),
        ('RECOMMENDATION', 'Recommendations'),
        ('ALERT', 'Alert/Warning'),
        ('OPTIMIZATION', 'Optimization Opportunity'),
    ]
    
    # Dashboard Configuration
    dashboard_type = models.CharField(max_length=15, choices=DASHBOARD_TYPES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Layout and Configuration
    layout_config = models.JSONField(default=dict, blank=True)
    widget_config = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    refresh_interval_minutes = models.IntegerField(default=60)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    allowed_users = models.ManyToManyField(User, blank=True, related_name='accessible_dashboards')
    allowed_groups = models.JSONField(default=list, blank=True)
    
    # AI Insights Configuration
    ai_insights_enabled = models.BooleanField(default=True)
    insight_types = models.JSONField(default=list, blank=True)
    auto_generate_insights = models.BooleanField(default=True)
    insight_refresh_hours = models.IntegerField(default=6)
    
    # Performance and Usage
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    average_load_time_ms = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Data Sources
    data_sources = models.JSONField(default=list, blank=True)
    data_freshness_hours = models.IntegerField(default=1)
    last_data_update = models.DateTimeField(null=True, blank=True)
    
    # Alerts and Notifications
    alert_rules = models.JSONField(default=list, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['dashboard_type', 'name']
        indexes = [
            models.Index(fields=['tenant', 'dashboard_type']),
            models.Index(fields=['tenant', 'is_public']),
            models.Index(fields=['tenant', 'last_viewed']),
        ]
    
    def __str__(self):
        return f'{self.dashboard_type} - {self.name}'
    
    def record_view(self, user=None):
        """Record dashboard view for analytics"""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save()
    
    def generate_ai_insights(self):
        """Generate AI-powered insights for dashboard"""
        insights = []
        
        # Implementation would analyze dashboard data and generate insights
        # This would use various AI/ML techniques to identify patterns,
        # anomalies, trends, and recommendations
        
        return insights
    
    def check_alert_rules(self, current_data):
        """Check alert rules against current data"""
        triggered_alerts = []
        
        for rule in self.alert_rules:
            # Implementation would check each alert rule
            # and trigger notifications if conditions are met
            pass
        
        return triggered_alerts
    
    def get_performance_summary(self):
        """Get dashboard performance summary"""
        return {
            'view_count': self.view_count,
            'average_load_time': float(self.average_load_time_ms or 0),
            'data_freshness_hours': self.data_freshness_hours,
            'last_viewed': self.last_viewed,
            'insights_enabled': self.ai_insights_enabled,
        }


class AIAuditLog(TenantBaseModel):
    """Comprehensive AI-powered audit logging with intelligent analysis"""
    
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('VIEW', 'Viewed'),
        ('SEARCH', 'Searched'),
        ('PURCHASE', 'Purchased'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('PERMISSION_CHANGE', 'Permission Changed'),
        ('SYSTEM_CONFIG', 'System Configuration'),
        ('DATA_EXPORT', 'Data Export'),
        ('AI_PREDICTION', 'AI Prediction'),
        ('MODEL_UPDATE', 'Model Update'),
    ]
    
    RISK_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
    ]
    
    # Action Details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action_datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions'
    )
    
    # Entity Information
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=36, blank=True)
    object_name = models.CharField(max_length=255, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Change Details
    field_changes = models.JSONField(default=dict, blank=True)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    change_summary = models.TextField(blank=True)
    
    # Context Information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_path = models.URLField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    
    # AI Risk Assessment
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='LOW')
    anomaly_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    fraud_probability = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    behavioral_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    
    # Geographic and Device Context
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=30, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    platform = models.CharField(max_length=50, blank=True)
    
    # Business Context
    business_impact_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    data_sensitivity_level = models.CharField(
        max_length=20,
        choices=[
            ('PUBLIC', 'Public'),
            ('INTERNAL', 'Internal'),
            ('CONFIDENTIAL', 'Confidential'),
            ('RESTRICTED', 'Restricted'),
        ],
        default='INTERNAL'
    )
    
    # AI Analysis Results
    pattern_detected = models.JSONField(default=list, blank=True)
    similar_actions = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Alert and Follow-up
    requires_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_audits'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Additional Metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-action_datetime']
        indexes = [
            models.Index(fields=['tenant', 'action_datetime']),
            models.Index(fields=['tenant', 'action_type']),
            models.Index(fields=['tenant', 'user', 'action_datetime']),
            models.Index(fields=['tenant', 'risk_level']),
            models.Index(fields=['tenant', 'requires_review']),
            models.Index(fields=['tenant', 'ip_address']),
        ]
    
    def __str__(self):
        user_name = self.user.get_full_name() if self.user else 'System'
        return f'{user_name} {self.get_action_type_display()} - {self.risk_level}'
    
    @classmethod
    def log_action(cls, tenant, action_type, user, obj=None, field_changes=None,
                   request=None, metadata=None):
        """Enhanced audit logging with AI risk assessment"""
        
        # Extract request information
        ip_address = None
        user_agent = ''
        request_path = ''
        request_method = ''
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            request_path = request.path
            request_method = request.method
        
        # Create audit entry
        audit_entry = cls.objects.create(
            tenant=tenant,
            action_type=action_type,
            user=user,
            content_type=ContentType.objects.get_for_model(obj) if obj else None,
            object_id=str(obj.pk) if obj else '',
            object_name=str(obj) if obj else '',
            field_changes=field_changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            metadata=metadata or {}
        )
        
        # Perform AI risk assessment
        audit_entry.assess_risk()
        
        return audit_entry
    
    def assess_risk(self):
        """AI-powered risk assessment for audit entry"""
        risk_factors = []
        risk_score = 0
        
        # Time-based risk factors
        if self.action_datetime.hour < 6 or self.action_datetime.hour > 22:
            risk_factors.append('Off-hours activity')
            risk_score += 10
        
        # Action type risk factors
        high_risk_actions = ['DELETE', 'PERMISSION_CHANGE', 'SYSTEM_CONFIG', 'DATA_EXPORT']
        if self.action_type in high_risk_actions:
            risk_factors.append('High-risk action type')
            risk_score += 20
        
        # User behavior analysis
        if self.user:
            # Check for unusual patterns (implementation would go here)
            recent_actions = AIAuditLog.objects.filter(
                tenant=self.tenant,
                user=self.user,
                action_datetime__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_actions > 50:  # High activity threshold
                risk_factors.append('Unusual activity volume')
                risk_score += 15
        
        # Geographic risk factors (if IP geolocation is available)
        # Implementation would check for unusual locations
        
        # Device and browser analysis
        # Implementation would check for new/unusual devices
        
        # Determine risk level
        if risk_score >= 50:
            self.risk_level = 'CRITICAL'
        elif risk_score >= 30:
            self.risk_level = 'HIGH'
        elif risk_score >= 15:
            self.risk_level = 'MEDIUM'
        else:
            self.risk_level = 'LOW'
        
        # Set review requirement for high-risk actions
        self.requires_review = self.risk_level in ['HIGH', 'CRITICAL']
        
        # Store risk factors
        self.metadata.update({
            'risk_factors': risk_factors,
            'risk_score': risk_score,
            'assessment_timestamp': timezone.now().isoformat()
        })
        
        self.save()
    
    def detect_patterns(self):
        """Detect patterns in audit logs for security analysis"""
        patterns = []
        
        if self.user:
            # Check for similar actions by same user
            similar_actions = AIAuditLog.objects.filter(
                tenant=self.tenant,
                user=self.user,
                action_type=self.action_type,
                action_datetime__gte=timezone.now() - timedelta(days=7)
            ).exclude(id=self.id)
            
            if similar_actions.count() > 10:
                patterns.append({
                    'type': 'repeated_action',
                    'description': f'User performed {self.action_type} {similar_actions.count()} times in past week'
                })
        
        # Check for IP-based patterns
        if self.ip_address:
            ip_actions = AIAuditLog.objects.filter(
                tenant=self.tenant,
                ip_address=self.ip_address,
                action_datetime__gte=timezone.now() - timedelta(hours=24)
            ).exclude(id=self.id)
            
            unique_users = ip_actions.values_list('user', flat=True).distinct().count()
            if unique_users > 5:
                patterns.append({
                    'type': 'multi_user_ip',
                    'description': f'IP address used by {unique_users} different users in 24 hours'
                })
        
        self.pattern_detected = patterns
        self.save()
        
        return patterns


class AISystemHealthCheck(TenantBaseModel):
    """Automated system health monitoring with AI-powered diagnostics"""
    
    HEALTH_STATUS = [
        ('HEALTHY', 'Healthy'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
        ('DOWN', 'Down'),
        ('MAINTENANCE', 'Maintenance'),
    ]
    
    CHECK_TYPES = [
        ('DATABASE', 'Database Connectivity'),
        ('CACHE', 'Cache Performance'),
        ('API', 'API Endpoints'),
        ('ML_MODELS', 'ML Model Status'),
        ('QUEUE', 'Job Queue Health'),
        ('STORAGE', 'Storage Systems'),
        ('NETWORK', 'Network Connectivity'),
        ('SECURITY', 'Security Systems'),
    ]
    
    # Check Configuration
    check_type = models.CharField(max_length=15, choices=CHECK_TYPES)
    check_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Status and Results
    status = models.CharField(max_length=15, choices=HEALTH_STATUS)
    last_check = models.DateTimeField(auto_now=True)
    response_time_ms = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Health Metrics
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    availability_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    error_count_24h = models.IntegerField(default=0)
    
    # Diagnostic Information
    diagnostic_data = models.JSONField(default=dict, blank=True)
    error_messages = models.JSONField(default=list, blank=True)
    performance_metrics = models.JSONField(default=dict, blank=True)
    
    # AI Analysis
    trend_analysis = models.JSONField(default=dict, blank=True)
    predicted_issues = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Alert Configuration
    alert_enabled = models.BooleanField(default=True)
    alert_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=95)
    escalation_rules = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['status', 'check_type', 'check_name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'check_type', 'check_name'],
                name='unique_tenant_health_check'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'check_type']),
            models.Index(fields=['tenant', 'last_check']),
        ]
    
    def __str__(self):
        return f'{self.check_name} ({self.status})'
    
    def perform_check(self):
        """Perform the actual health check"""
        check_result = {
            'timestamp': timezone.now().isoformat(),
            'success': True,
            'response_time': 0,
            'details': {}
        }
        
        try:
            start_time = timezone.now()
            
            if self.check_type == 'DATABASE':
                self._check_database()
            elif self.check_type == 'CACHE':
                self._check_cache()
            elif self.check_type == 'API':
                self._check_api_endpoints()
            elif self.check_type == 'ML_MODELS':
                self._check_ml_models()
            elif self.check_type == 'QUEUE':
                self._check_job_queue()
            # Add more check implementations
            
            end_time = timezone.now()
            check_result['response_time'] = (end_time - start_time).total_seconds() * 1000
            
            self.status = 'HEALTHY'
            self.response_time_ms = check_result['response_time']
            
        except Exception as e:
            check_result['success'] = False
            check_result['error'] = str(e)
            self.status = 'CRITICAL'
            self.error_messages.append(check_result)
        
        self.diagnostic_data = check_result
        self.save()
        
        return check_result
    
    def _check_database(self):
        """Check database connectivity and performance"""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result[0] != 1:
                raise Exception("Database query failed")
    
    def _check_cache(self):
        """Check cache system performance"""
        test_key = f"health_check_{self.tenant.id}"
        test_value = "health_check_value"
        
        cache.set(test_key, test_value, 60)
        retrieved_value = cache.get(test_key)
        
        if retrieved_value != test_value:
            raise Exception("Cache system not working properly")
        
        cache.delete(test_key)
    
    def _check_api_endpoints(self):
        """Check critical API endpoints"""
        # Implementation would test key API endpoints
        pass
    
    def _check_ml_models(self):
        """Check ML model availability and performance"""
        active_models = AIModelRegistry.objects.filter(
            tenant=self.tenant,
            status='PRODUCTION'
        )
        
        for model in active_models:
            # Check model health (implementation would go here)
            pass
    
    def _check_job_queue(self):
        """Check job queue health"""
        failed_jobs = AIJobQueue.objects.filter(
            tenant=self.tenant,
            status='FAILED',
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if failed_jobs > 10:
            raise Exception(f"Too many failed jobs: {failed_jobs} in last hour")
    
    def analyze_trends(self):
        """AI-powered trend analysis of health metrics"""
        # Implementation would analyze historical health data
        # to identify trends and predict potential issues
        pass