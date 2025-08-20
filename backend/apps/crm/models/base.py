# ============================================================================
# backend/apps/crm/models/base.py - Core CRM Configuration Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code

User = get_user_model()


class CRMConfiguration(TenantBaseModel):
    """Enhanced tenant-specific CRM configuration"""
    
    LEAD_ASSIGNMENT_METHODS = [
        ('ROUND_ROBIN', 'Round Robin'),
        ('TERRITORY', 'Territory Based'),
        ('MANUAL', 'Manual Assignment'),
        ('SCORING', 'Score Based'),
        ('WORKLOAD', 'Workload Based'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('CAD', 'Canadian Dollar'),
        ('AUD', 'Australian Dollar'),
        ('JPY', 'Japanese Yen'),
        ('INR', 'Indian Rupee'),
        ('CNY', 'Chinese Yuan'),
    ]
    
    # Company Information
    company_name = models.CharField(max_length=200)
    company_logo = models.ImageField(upload_to='crm/logos/', blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    
    # Lead Configuration
    lead_auto_assignment = models.BooleanField(default=True)
    lead_assignment_method = models.CharField(
        max_length=20,
        choices=LEAD_ASSIGNMENT_METHODS,
        default='ROUND_ROBIN'
    )
    lead_scoring_enabled = models.BooleanField(default=True)
    lead_scoring_threshold = models.IntegerField(default=50)
    duplicate_lead_detection = models.BooleanField(default=True)
    
    # Opportunity Configuration
    opportunity_auto_number = models.BooleanField(default=True)
    opportunity_probability_tracking = models.BooleanField(default=True)
    opportunity_forecast_enabled = models.BooleanField(default=True)
    default_opportunity_stage = models.CharField(max_length=100, default='Prospecting')
    
    # Pipeline Configuration
    default_pipeline_stages = models.JSONField(default=list)
    stage_probability_mapping = models.JSONField(default=dict)
    sales_cycle_tracking = models.BooleanField(default=True)
    
    # Email & Communication
    email_integration_enabled = models.BooleanField(default=True)
    email_tracking_enabled = models.BooleanField(default=True)
    email_signature = models.TextField(blank=True)
    auto_email_responses = models.BooleanField(default=False)
    sms_integration_enabled = models.BooleanField(default=False)
    
    # Activity Configuration
    activity_reminders_enabled = models.BooleanField(default=True)
    default_reminder_minutes = models.IntegerField(default=15)
    auto_activity_logging = models.BooleanField(default=True)
    calendar_sync_enabled = models.BooleanField(default=False)
    
    # Campaign Configuration
    campaign_tracking_enabled = models.BooleanField(default=True)
    email_campaign_enabled = models.BooleanField(default=True)
    campaign_roi_tracking = models.BooleanField(default=True)
    
    # Customer Service Configuration
    ticket_auto_assignment = models.BooleanField(default=True)
    ticket_escalation_enabled = models.BooleanField(default=True)
    sla_tracking_enabled = models.BooleanField(default=True)
    knowledge_base_enabled = models.BooleanField(default=True)
    
    # Integration Settings
    finance_integration_enabled = models.BooleanField(default=True)
    inventory_integration_enabled = models.BooleanField(default=True)
    ecommerce_integration_enabled = models.BooleanField(default=True)
    accounting_sync_enabled = models.BooleanField(default=True)
    
    # Territory Management
    territory_management_enabled = models.BooleanField(default=False)
    territory_assignment_method = models.CharField(max_length=20, default='GEOGRAPHIC')
    
    # Security & Privacy
    data_encryption_enabled = models.BooleanField(default=True)
    audit_trail_enabled = models.BooleanField(default=True)
    gdpr_compliance_enabled = models.BooleanField(default=False)
    data_retention_days = models.IntegerField(default=2555)  # 7 years
    
    # Regional Settings
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    date_format = models.CharField(max_length=20, default='%Y-%m-%d')
    time_format = models.CharField(max_length=20, default='%H:%M')
    language = models.CharField(max_length=10, default='en')
    
    # Performance Settings
    dashboard_refresh_interval = models.IntegerField(default=300)  # 5 minutes
    report_cache_duration = models.IntegerField(default=3600)  # 1 hour
    bulk_operation_limit = models.IntegerField(default=1000)
    
    # Notification Settings
    notification_preferences = models.JSONField(default=dict)
    email_notification_enabled = models.BooleanField(default=True)
    browser_notification_enabled = models.BooleanField(default=True)
    mobile_notification_enabled = models.BooleanField(default=True)
    
    # Custom Fields Configuration
    enable_custom_fields = models.BooleanField(default=True)
    max_custom_fields_per_entity = models.IntegerField(default=50)
    
    # Backup & Recovery
    auto_backup_enabled = models.BooleanField(default=True)
    backup_frequency_hours = models.IntegerField(default=24)
    
    class Meta:
        verbose_name = 'CRM Configuration'
        verbose_name_plural = 'CRM Configurations'
        
    def __str__(self):
        return f'CRM Config - {self.company_name}'
    
    def get_default_pipeline_stages(self):
        """Get default pipeline stages"""
        if not self.default_pipeline_stages:
            return [
                {'name': 'Prospecting', 'probability': 10},
                {'name': 'Qualification', 'probability': 25},
                {'name': 'Proposal', 'probability': 50},
                {'name': 'Negotiation', 'probability': 75},
                {'name': 'Closed Won', 'probability': 100},
                {'name': 'Closed Lost', 'probability': 0},
            ]
        return self.default_pipeline_stages