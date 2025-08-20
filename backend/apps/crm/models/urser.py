# ============================================================================
# backend/apps/crm/models/user.py - User Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class CRMRole(TenantBaseModel, SoftDeleteMixin):
    """Enhanced CRM-specific roles with granular permissions"""
    
    # Role Information
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)
    
    # Lead Permissions
    can_view_all_leads = models.BooleanField(default=False)
    can_edit_all_leads = models.BooleanField(default=False)
    can_delete_leads = models.BooleanField(default=False)
    can_assign_leads = models.BooleanField(default=False)
    can_convert_leads = models.BooleanField(default=False)
    can_import_leads = models.BooleanField(default=False)
    can_export_leads = models.BooleanField(default=False)
    
    # Account & Contact Permissions
    can_view_all_accounts = models.BooleanField(default=False)
    can_edit_all_accounts = models.BooleanField(default=False)
    can_delete_accounts = models.BooleanField(default=False)
    can_manage_contacts = models.BooleanField(default=False)
    
    # Opportunity Permissions
    can_view_all_opportunities = models.BooleanField(default=False)
    can_edit_all_opportunities = models.BooleanField(default=False)
    can_delete_opportunities = models.BooleanField(default=False)
    can_manage_pipeline = models.BooleanField(default=False)
    can_view_forecasts = models.BooleanField(default=False)
    
    # Campaign Permissions
    can_manage_campaigns = models.BooleanField(default=False)
    can_send_emails = models.BooleanField(default=False)
    can_view_campaign_analytics = models.BooleanField(default=False)
    
    # Customer Service Permissions
    can_manage_tickets = models.BooleanField(default=False)
    can_view_all_tickets = models.BooleanField(default=False)
    can_escalate_tickets = models.BooleanField(default=False)
    can_manage_sla = models.BooleanField(default=False)
    
    # Reporting & Analytics
    can_view_reports = models.BooleanField(default=False)
    can_create_reports = models.BooleanField(default=False)
    can_view_dashboards = models.BooleanField(default=False)
    can_manage_dashboards = models.BooleanField(default=False)
    
    # Administration
    can_manage_settings = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_manage_roles = models.BooleanField(default=False)
    can_manage_territories = models.BooleanField(default=False)
    can_manage_workflows = models.BooleanField(default=False)
    
    # Data Management
    can_import_data = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    can_delete_data = models.BooleanField(default=False)
    can_view_audit_trail = models.BooleanField(default=False)
    
    # Integration Permissions
    can_manage_integrations = models.BooleanField(default=False)
    can_access_api = models.BooleanField(default=False)
    
    # Advanced Permissions (stored as JSON for flexibility)
    custom_permissions = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_crm_role'
            ),
        ]
        
    def __str__(self):
        return self.display_name or self.name
    
    def has_permission(self, permission):
        """Check if role has specific permission"""
        return getattr(self, permission, False) or self.custom_permissions.get(permission, False)


class CRMUserProfile(TenantBaseModel):
    """Enhanced user profile for CRM with performance tracking"""
    
    PROFILE_TYPES = [
        ('SALES_REP', 'Sales Representative'),
        ('SALES_MANAGER', 'Sales Manager'),
        ('MARKETING', 'Marketing'),
        ('CUSTOMER_SERVICE', 'Customer Service'),
        ('ADMIN', 'Administrator'),
        ('EXECUTIVE', 'Executive'),
    ]
    
    # User Association
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='crm_profile'
    )
    
    # CRM Role
    crm_role = models.ForeignKey(
        CRMRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    # Profile Information
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPES)
    employee_id = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members'
    )
    
    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    mobile_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    extension = models.CharField(max_length=10, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Location & Territory
    office_location = models.CharField(max_length=200, blank=True)
    territory = models.ForeignKey(
        'Territory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_users'
    )
    time_zone = models.CharField(max_length=50, default='UTC')
    
    # Sales Performance
    sales_quota = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Performance Metrics (Auto-calculated)
    total_leads_assigned = models.IntegerField(default=0)
    total_leads_converted = models.IntegerField(default=0)
    total_opportunities_won = models.IntegerField(default=0)
    total_revenue_generated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_deal_size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Activity Metrics
    total_activities_logged = models.IntegerField(default=0)
    total_emails_sent = models.IntegerField(default=0)
    total_calls_made = models.IntegerField(default=0)
    total_meetings_held = models.IntegerField(default=0)
    
    # Preferences
    default_dashboard = models.CharField(max_length=100, blank=True)
    notification_preferences = models.JSONField(default=dict)
    ui_preferences = models.JSONField(default=dict)
    
    # System Settings
    is_active = models.BooleanField(default=True)
    last_login_crm = models.DateTimeField(null=True, blank=True)
    login_count = models.IntegerField(default=0)
    
    # Social & Communication
    linkedin_profile = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)
    
    # Targets & Goals
    monthly_target = models.JSONField(default=dict)
    quarterly_target = models.JSONField(default=dict)
    annual_target = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'CRM User Profile'
        verbose_name_plural = 'CRM User Profiles'
        
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.profile_type}'
    
    @property
    def lead_conversion_percentage(self):
        """Calculate lead conversion rate"""
        if self.total_leads_assigned > 0:
            return (self.total_leads_converted / self.total_leads_assigned) * 100
        return 0
    
    @property
    def quota_achievement_percentage(self):
        """Calculate quota achievement"""
        if self.sales_quota and self.sales_quota > 0:
            return (self.total_revenue_generated / self.sales_quota) * 100
        return 0
    
    def update_performance_metrics(self):
        """Update performance metrics from related records"""
        # This would be called by signals or scheduled tasks
        pass