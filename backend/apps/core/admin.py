from django.contrib import admin
from .models import Tenant, Domain, TenantSettings, TenantUsage


class TenantAdminMixin:
    """Base admin mixin for tenant-aware models"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # In a real implementation, you would filter by current tenant
        # For now, return all records
        return qs
    
    def save_model(self, request, obj, form, change):
        # In a real implementation, you would set the tenant from request
        # For now, just save normally
        super().save_model(request, obj, form, change)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'plan', 'status', 'created_at']
    list_filter = ['plan', 'status', 'created_at']
    search_fields = ['name', 'slug', 'company_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'domain_type', 'is_verified', 'created_at']
    list_filter = ['domain_type', 'is_verified', 'created_at']
    search_fields = ['domain', 'tenant__name']


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'primary_color', 'api_rate_limit', 'created_at']
    list_filter = ['created_at']
    search_fields = ['tenant__name']


@admin.register(TenantUsage)
class TenantUsageAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'active_users_count', 'storage_used_gb', 'api_calls_count', 'billing_period_start']
    list_filter = ['billing_period_start', 'created_at']
    search_fields = ['tenant__name']
