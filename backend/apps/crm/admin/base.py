# ============================================================================
# backend/apps/crm/admin/base.py - Enhanced Base Admin Classes with Security
# ============================================================================

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import models
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Any, Optional
import json
import logging

from ..permissions.role_based import DynamicRolePermission
from ..models import AuditLog, TaskExecution, DataAccessLog

logger = logging.getLogger(__name__)
User = get_user_model()


class CRMAdminSite(AdminSite):
    """
    Enhanced admin site with comprehensive security, analytics, and multi-tenant support
    """
    
    site_header = 'CRM Administration Portal'
    site_title = 'CRM Admin'
    index_title = 'CRM Management Dashboard'
    site_url = '/admin/'
    
    def __init__(self, name='crm_admin'):
        super().__init__(name)
        self.permission_checker = DynamicRolePermission()
        
    def has_permission(self, request):
        """Enhanced permission checking with role validation"""
        try:
            # Basic authentication check
            if not request.user.is_active or not request.user.is_authenticated:
                return False
            
            # Check if user has admin access
            if request.user.is_superuser:
                return True
            
            # Check CRM admin permissions
            if request.user.has_perm('crm.view_admin_dashboard'):
                return True
            
            # Check role-based admin access
            if hasattr(request, 'user_roles'):
                admin_roles = ['SYSTEM_ADMIN', 'TENANT_ADMIN']
                return any(role in request.user_roles for role in admin_roles)
            
            return False
            
        except Exception as e:
            logger.error(f"Admin permission check failed: {e}")
            return False
    
    def index(self, request, extra_context=None):
        """Enhanced admin index with comprehensive dashboard"""
        if not self.has_permission(request):
            raise PermissionDenied("Access denied to admin interface")
        
        # Get dashboard data
        dashboard_context = self._get_dashboard_context(request)
        
        # Merge with extra context
        if extra_context:
            dashboard_context.update(extra_context)
        
        return render(request, 'crm_admin/dashboard.html', dashboard_context)
    
    def get_urls(self):
        """Add custom admin URLs"""
        urls = super().get_urls()
        
        custom_urls = [
            path('analytics/', self.analytics_view, name='crm_analytics'),
            path('system-health/', self.system_health_view, name='system_health'),
            path('audit-logs/', self.audit_logs_view, name='audit_logs'),
            path('performance/', self.performance_view, name='performance'),
            path('security-monitor/', self.security_monitor_view, name='security_monitor'),
            path('bulk-operations/', self.bulk_operations_view, name='bulk_operations'),
            path('export-data/', self.export_data_view, name='export_data'),
            path('import-data/', self.import_data_view, name='import_data'),
        ]
        
        return custom_urls + urls
    
    def _get_dashboard_context(self, request) -> Dict:
        """Generate comprehensive dashboard context"""
        try:
            tenant = getattr(request, 'tenant', None)
            
            # System overview
            system_stats = self._get_system_statistics(tenant)
            
            # Recent activity
            recent_activity = self._get_recent_activity(tenant)
            
            # Performance metrics
            performance_metrics = self._get_performance_metrics(tenant)
            
            # Security alerts
            security_alerts = self._get_security_alerts(tenant)
            
            # Task monitoring
            task_stats = self._get_task_statistics(tenant)
            
            return {
                'system_stats': system_stats,
                'recent_activity': recent_activity,
                'performance_metrics': performance_metrics,
                'security_alerts': security_alerts,
                'task_stats': task_stats,
                'dashboard_generated_at': timezone.now(),
                'user_permissions': self._get_user_permissions(request.user),
                'quick_actions': self._get_quick_actions(request.user)
            }
            
        except Exception as e:
            logger.error(f"Dashboard context generation failed: {e}")
            return {'error': 'Dashboard data unavailable'}
    
    def analytics_view(self, request):
        """Advanced analytics dashboard"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        # Generate analytics data
        analytics_data = self._generate_analytics_data(request)
        
        return render(request, 'crm_admin/analytics.html', {
            'analytics_data': analytics_data,
            'title': 'CRM Analytics Dashboard'
        })
    
    def system_health_view(self, request):
        """System health monitoring dashboard"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        health_data = self._get_system_health_data(request)
        
        return render(request, 'crm_admin/system_health.html', {
            'health_data': health_data,
            'title': 'System Health Monitor'
        })
    
    def audit_logs_view(self, request):
        """Comprehensive audit logs viewer"""
        if not request.user.has_perm('crm.view_auditlog'):
            raise PermissionDenied()
        
        # Get audit logs with filters
        logs = self._get_filtered_audit_logs(request)
        
        return render(request, 'crm_admin/audit_logs.html', {
            'audit_logs': logs,
            'title': 'Audit Logs'
        })
    
    def register_models(self):
        """Register all CRM models with appropriate admin classes"""
        from .. import models
        
        # Core models
        self.register(models.CRMConfiguration, CRMConfigurationAdmin)
        self.register(models.CRMUserProfile, CRMUserProfileAdmin)
        
        # Lead management
        self.register(models.Lead, LeadAdmin)
        self.register(models.LeadSource, LeadSourceAdmin)
        self.register(models.LeadScoringRule, LeadScoringRuleAdmin)
        
        # Account management
        self.register(models.Account, AccountAdmin)
        self.register(models.Contact, ContactAdmin)
        self.register(models.Industry, IndustryAdmin)
        
        # Opportunity management
        self.register(models.Opportunity, OpportunityAdmin)
        self.register(models.Pipeline, PipelineAdmin)
        self.register(models.PipelineStage, PipelineStageAdmin)
        
        # Activity management
        self.register(models.Activity, ActivityAdmin)
        self.register(models.ActivityType, ActivityTypeAdmin)
        self.register(models.EmailLog, EmailLogAdmin)
        
        # Campaign management
        self.register(models.Campaign, CampaignAdmin)
        self.register(models.EmailTemplate, EmailTemplateAdmin)
        
        # Support management
        self.register(models.Ticket, TicketAdmin)
        self.register(models.TicketCategory, TicketCategoryAdmin)
        self.register(models.SLA, SLAAdmin)
        
        # System models
        self.register(models.AuditLog, AuditLogAdmin)
        self.register(models.TaskExecution, TaskExecutionAdmin)


class BaseModelAdmin(admin.ModelAdmin):
    """
    Enhanced base model admin with security, audit logging, and advanced features
    """
    
    # Enhanced list display configuration
    list_per_page = 25
    list_max_show_all = 100
    show_full_result_count = True
    
    # Advanced filtering
    list_filter = ['created_at', 'updated_at', 'is_active']
    date_hierarchy = 'created_at'
    
    # Search configuration
    search_fields = ['id']
    search_help_text = "Search by ID, name, or other key fields"
    
    # Enhanced form configuration
    save_as = True
    save_as_continue = True
    save_on_top = True
    
    # Field organization
    readonly_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.permission_checker = DynamicRolePermission()
    
    def get_queryset(self, request):
        """Enhanced queryset with security filtering"""
        qs = super().get_queryset(request)
        
        # Apply tenant filtering if applicable
        if hasattr(self.model, 'tenant') and hasattr(request, 'tenant'):
            qs = qs.filter(tenant=request.tenant)
        
        # Apply user-based filtering for non-admin users
        if not request.user.is_superuser:
            qs = self._apply_user_filtering(qs, request)
        
        return qs
    
    def has_view_permission(self, request, obj=None):
        """Enhanced view permission with role-based access"""
        try:
            # Superuser always has access
            if request.user.is_superuser:
                return True
            
            # Check basic permission
            basic_permission = super().has_view_permission(request, obj)
            if not basic_permission:
                return False
            
            # Check role-based permissions
            if hasattr(request, 'user_roles'):
                view_roles = ['SYSTEM_ADMIN', 'TENANT_ADMIN', 'ANALYST']
                if any(role in request.user_roles for role in view_roles):
                    return True
            
            # Object-level permission check
            if obj:
                return self._check_object_permission(request, obj, 'view')
            
            return True
            
        except Exception as e:
            logger.error(f"View permission check failed: {e}")
            return False
    
    def has_change_permission(self, request, obj=None):
        """Enhanced change permission with audit logging"""
        try:
            if not super().has_change_permission(request, obj):
                return False
            
            # Role-based change permissions
            if hasattr(request, 'user_roles'):
                change_roles = ['SYSTEM_ADMIN', 'TENANT_ADMIN']
                if not any(role in request.user_roles for role in change_roles):
                    return False
            
            # Object-level permission check
            if obj:
                return self._check_object_permission(request, obj, 'change')
            
            return True
            
        except Exception as e:
            logger.error(f"Change permission check failed: {e}")
            return False
    
    def save_model(self, request, obj, form, change):
        """Enhanced save with audit logging and validation"""
        try:
            # Set user fields
            if not change and hasattr(obj, 'created_by'):
                obj.created_by = request.user
            
            if hasattr(obj, 'updated_by'):
                obj.updated_by = request.user
            
            # Set tenant if applicable
            if hasattr(obj, 'tenant') and not obj.tenant:
                obj.tenant = getattr(request, 'tenant', None)
            
            # Save the object
            old_obj = None
            if change:
                old_obj = self.model.objects.get(pk=obj.pk)
            
            super().save_model(request, obj, form, change)
            
            # Log the change
            self._log_model_change(request, obj, old_obj, change)
            
        except Exception as e:
            logger.error(f"Model save failed: {e}")
            raise
    
    def delete_model(self, request, obj):
        """Enhanced delete with audit logging"""
        try:
            # Log before deletion
            self._log_model_deletion(request, obj)
            
            # Perform soft delete if supported
            if hasattr(obj, 'is_active'):
                obj.is_active = False
                obj.deleted_by = request.user
                obj.deleted_at = timezone.now()
                obj.save()
            else:
                super().delete_model(request, obj)
            
        except Exception as e:
            logger.error(f"Model deletion failed: {e}")
            raise
    
    def get_list_display(self, request):
        """Dynamic list display based on permissions"""
        list_display = list(super().get_list_display(request))
        
        # Add status indicators for admins
        if request.user.is_superuser or 'ADMIN' in getattr(request, 'user_roles', []):
            if 'status_indicator' not in list_display:
                list_display.append('status_indicator')
        
        # Add audit fields for compliance users
        if 'COMPLIANCE_OFFICER' in getattr(request, 'user_roles', []):
            list_display.extend(['created_by', 'updated_at'])
        
        return list_display
    
    def status_indicator(self, obj):
        """Enhanced status indicator with visual cues"""
        if hasattr(obj, 'is_active'):
            if obj.is_active:
                return format_html(
                    '<span style="color: green; font-weight: bold;">●</span> Active'
                )
            else:
                return format_html(
                    '<span style="color: red; font-weight: bold;">●</span> Inactive'
                )
        return '-'
    
    status_indicator.short_description = 'Status'
    
    def _apply_user_filtering(self, queryset, request):
        """Apply user-based filtering for security"""
        try:
            user_roles = getattr(request, 'user_roles', [])
            
            # Managers see all data in their domain
            if any('MANAGER' in role for role in user_roles):
                return queryset
            
            # Regular users see only their own data
            if hasattr(queryset.model, 'created_by'):
                return queryset.filter(created_by=request.user)
            
            if hasattr(queryset.model, 'assigned_to'):
                return queryset.filter(assigned_to=request.user)
            
            return queryset
            
        except Exception as e:
            logger.error(f"User filtering failed: {e}")
            return queryset
    
    def _log_model_change(self, request, obj, old_obj, is_update):
        """Log model changes for audit purposes"""
        try:
            changes = {}
            
            if is_update and old_obj:
                # Calculate field changes
                for field in obj._meta.fields:
                    field_name = field.name
                    old_value = getattr(old_obj, field_name, None)
                    new_value = getattr(obj, field_name, None)
                    
                    if old_value != new_value:
                        changes[field_name] = {
                            'old': str(old_value),
                            'new': str(new_value)
                        }
            
            # Create audit log
            AuditLog.objects.create(
                event_type='DATA_MODIFICATION',
                event_subtype='UPDATE' if is_update else 'CREATE',
                user=request.user,
                tenant=getattr(request, 'tenant', None),
                object_type=obj.__class__.__name__,
                object_id=obj.pk,
                timestamp=timezone.now(),
                ip_address=self._get_client_ip(request),
                additional_data={
                    'model': obj.__class__.__name__,
                    'changes': changes,
                    'admin_interface': True
                }
            )
            
        except Exception as e:
            logger.error(f"Model change logging failed: {e}")


class TenantAwareAdmin(BaseModelAdmin):
    """
    Admin class for tenant-aware models with enhanced multi-tenancy support
    """
    
    def get_queryset(self, request):
        """Tenant-aware queryset"""
        qs = super().get_queryset(request)
        
        if hasattr(request, 'tenant') and hasattr(self.model, 'tenant'):
            qs = qs.filter(tenant=request.tenant)
        
        return qs
    
    def save_model(self, request, obj, form, change):
        """Ensure tenant is set correctly"""
        if hasattr(obj, 'tenant') and hasattr(request, 'tenant'):
            if not obj.tenant:
                obj.tenant = request.tenant
            elif obj.tenant != request.tenant:
                raise PermissionDenied("Cannot modify objects from different tenants")
        
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form for tenant-aware models"""
        form = super().get_form(request, obj, **kwargs)
        
        # Hide tenant field for non-superusers
        if not request.user.is_superuser and 'tenant' in form.base_fields:
            form.base_fields['tenant'].widget = form.base_fields['tenant'].hidden_widget()
        
        return form


class CRMConfigurationAdmin(TenantAwareAdmin):
    """Enhanced admin for CRM configuration with validation"""
    
    list_display = ['company_name', 'tenant', 'lead_scoring_enabled', 
                   'email_integration_enabled', 'updated_at', 'status_indicator']
    list_filter = ['lead_scoring_enabled', 'email_integration_enabled', 
                   'opportunity_forecast_enabled', 'updated_at']
    search_fields = ['company_name', 'tenant__name']
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'company_logo', 'website', 'industry')
        }),
        ('Lead Management', {
            'fields': ('lead_auto_assignment', 'lead_assignment_method', 
                      'lead_scoring_enabled', 'lead_scoring_threshold',
                      'duplicate_lead_detection')
        }),
        ('Opportunity Management', {
            'fields': ('opportunity_auto_number', 'opportunity_probability_tracking',
                      'opportunity_forecast_enabled', 'default_opportunity_stage')
        }),
        ('Communication Settings', {
            'fields': ('email_integration_enabled', 'email_tracking_enabled',
                      'activity_reminders_enabled', 'default_reminder_minutes')
        }),
        ('System Settings', {
            'fields': ('timezone', 'currency', 'date_format', 'time_format', 'language'),
            'classes': ('collapse',)
        }),
        ('Advanced Settings', {
            'fields': ('campaign_tracking_enabled', 'ticket_auto_assignment',
                      'territory_management_enabled'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Only allow one configuration per tenant"""
        if hasattr(request, 'tenant'):
            existing_config = self.model.objects.filter(tenant=request.tenant).exists()
            if existing_config:
                return False
        return super().has_add_permission(request)


# Enhanced inline admin classes
class EnhancedTabularInline(admin.TabularInline):
    """Enhanced tabular inline with security and validation"""
    
    extra = 0
    show_change_link = True
    
    def get_queryset(self, request):
        """Apply security filtering to inline querysets"""
        qs = super().get_queryset(request)
        
        if hasattr(self.model, 'tenant') and hasattr(request, 'tenant'):
            qs = qs.filter(tenant=request.tenant)
        
        return qs
    
    def has_view_permission(self, request, obj=None):
        """Enhanced inline view permissions"""
        return request.user.has_perm(f'{self.model._meta.app_label}.view_{self.model._meta.model_name}')
    
    def has_change_permission(self, request, obj=None):
        """Enhanced inline change permissions"""
        return request.user.has_perm(f'{self.model._meta.app_label}.change_{self.model._meta.model_name}')


class EnhancedStackedInline(admin.StackedInline):
    """Enhanced stacked inline with security and validation"""
    
    extra = 0
    show_change_link = True
    
    def get_queryset(self, request):
        """Apply security filtering to inline querysets"""
        qs = super().get_queryset(request)
        
        if hasattr(self.model, 'tenant') and hasattr(request, 'tenant'):
            qs = qs.filter(tenant=request.tenant)
        
        return qs


# Custom admin widgets and filters
class AdvancedDateRangeFilter(admin.SimpleListFilter):
    """Advanced date range filter with presets"""
    
    title = 'Date Range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_quarter', 'This Quarter'),
            ('this_year', 'This Year'),
        ]
    
    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        elif self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif self.value() == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_week)
        elif self.value() == 'this_month':
            start_month = today.replace(day=1)
            return queryset.filter(created_at__date__gte=start_month)
        # Add more date range logic...
        
        return queryset