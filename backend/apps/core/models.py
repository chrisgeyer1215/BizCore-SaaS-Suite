# apps/core/models.py

from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.contrib.auth.models import AbstractUser
import shortuuid
from django.utils.text import slugify


class TenantBaseModel(models.Model):
    """Base model for all tenant-specific models"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Mixin for soft deletion"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True


class Tenant(TenantMixin):
    """Tenant model for multi-tenancy"""
    
    PLAN_CHOICES = [
        ('free', 'Free Plan'),
        ('starter', 'Starter Plan'),
        ('professional', 'Professional Plan'),
        ('enterprise', 'Enterprise Plan'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial'),
        ('expired', 'Expired'),
    ]
    
    # Basic Info
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Plan & Status
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    
    # Limits based on plan
    max_users = models.PositiveIntegerField(default=5)
    max_storage_gb = models.PositiveIntegerField(default=1)
    max_api_calls_per_month = models.PositiveIntegerField(default=1000)
    
    # Billing
    trial_end_date = models.DateTimeField(null=True, blank=True)
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Feature flags
    features = models.JSONField(default=dict, blank=True)
    
    # Contact info
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Company info
    company_name = models.CharField(max_length=200, blank=True)
    company_address = models.TextField(blank=True)
    company_logo = models.ImageField(upload_to='tenant_logos/', null=True, blank=True)
    
    # Timezone and locale
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=3, default='USD')
    
    class Meta:
        db_table = 'public.core_tenant'
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    @property
    def is_trial_expired(self):
        if self.trial_end_date:
            from django.utils import timezone
            return timezone.now() > self.trial_end_date
        return False
    
    @property
    def is_subscription_active(self):
        if self.subscription_end_date:
            from django.utils import timezone
            return timezone.now() <= self.subscription_end_date
        return False
    
    def get_feature(self, feature_name, default=False):
        """Get feature flag value"""
        return self.features.get(feature_name, default)
    
    def set_feature(self, feature_name, value):
        """Set feature flag value"""
        self.features[feature_name] = value
        self.save(update_fields=['features'])


class Domain(DomainMixin):
    """Domain model for tenant routing"""
    
    DOMAIN_TYPE_CHOICES = [
        ('primary', 'Primary Domain'),
        ('subdomain', 'Subdomain'),
        ('custom', 'Custom Domain'),
    ]
    
    domain_type = models.CharField(max_length=20, choices=DOMAIN_TYPE_CHOICES, default='subdomain')
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'public.core_domain'
    
    def save(self, *args, **kwargs):
        if not self.verification_token:
            self.verification_token = shortuuid.uuid()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.domain} ({self.tenant.name})"


class TenantSettings(models.Model):
    """Tenant-specific settings"""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings')
    
    # Appearance
    primary_color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#64748B')
    logo_url = models.URLField(blank=True)
    favicon_url = models.URLField(blank=True)
    
    # Business settings
    business_hours_start = models.TimeField(default='09:00:00')
    business_hours_end = models.TimeField(default='17:00:00')
    business_days = models.JSONField(default=list)  # [1,2,3,4,5] for Mon-Fri
    
    # Notification settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # API settings
    api_rate_limit = models.PositiveIntegerField(default=100)  # requests per minute
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=100, blank=True)
    
    # Integration settings
    integrations = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'public.core_tenantsettings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"


class TenantUsage(models.Model):
    """Track tenant usage for billing and limits"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='usage_records')
    
    # Usage metrics
    active_users_count = models.PositiveIntegerField(default=0)
    storage_used_gb = models.FloatField(default=0.0)
    api_calls_count = models.PositiveIntegerField(default=0)
    
    # Feature usage
    emails_sent = models.PositiveIntegerField(default=0)
    sms_sent = models.PositiveIntegerField(default=0)
    reports_generated = models.PositiveIntegerField(default=0)
    
    # Billing period
    billing_period_start = models.DateTimeField()
    billing_period_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.core_tenantusage'
        unique_together = ['tenant', 'billing_period_start']
    
    def __str__(self):
        return f"Usage for {self.tenant.name} ({self.billing_period_start.strftime('%Y-%m')})"