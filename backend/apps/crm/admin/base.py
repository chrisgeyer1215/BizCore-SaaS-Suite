# ============================================================================
# backend/apps/crm/admin/base.py - Enhanced Base Admin Classes with Security
# ============================================================================

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import models
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.contrib import messages
from django.forms import widgets
from django.template.response import TemplateResponse
from datetime import timedelta, datetime
from typing import Dict, List, Any, Optional
import json
import logging

# Import permission classes
from ..permissions.role_based import DynamicRolePermission
from ..permissions.base import CRMPermission

# Import models (these would need to be created)
try:
    from ..models import (
        AuditLog, APIUsageLog, DataExportLog, CRMConfiguration,
        CRMUserProfile, Lead, LeadSource, LeadScoringRule, Account,
        Contact, Industry, Opportunity, Pipeline, PipelineStage,
        Activity, ActivityType, EmailLog, Campaign, EmailTemplate,
        Ticket, TicketCategory, SLA, TaskExecution
    )
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Some models not found during import: {e}")

logger = logging.getLogger(__name__)
User = get_user_model()


class CRMAdminSite(AdminSite):
    """
    Enhanced admin site with comprehensive security, analytics, and multi-tenant support
    """
    
    site_header = 'SaaS-AICE CRM Administration Portal'
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
            
            # Check CRM profile permissions
            if hasattr(request.user, 'crm_profile'):
                admin_roles = ['system_admin', 'crm_admin', 'tenant_admin']
                return request.user.crm_profile.role in admin_roles
            
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
            path('analytics/', self.admin_view(self.analytics_view), name='crm_analytics'),
            path('system-health/', self.admin_view(self.system_health_view), name='system_health'),
            path('audit-logs/', self.admin_view(self.audit_logs_view), name='audit_logs'),
            path('performance/', self.admin_view(self.performance_view), name='performance'),
            path('security-monitor/', self.admin_view(self.security_monitor_view), name='security_monitor'),
            path('bulk-operations/', self.admin_view(self.bulk_operations_view), name='bulk_operations'),
            path('export-data/', self.admin_view(self.export_data_view), name='export_data'),
            path('import-data/', self.admin_view(self.import_data_view), name='import_data'),
            path('api/dashboard-stats/', self.dashboard_stats_api, name='dashboard_stats_api'),
            path('api/system-status/', self.system_status_api, name='system_status_api'),
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
    
    def _get_system_statistics(self, tenant) -> Dict:
        """Get comprehensive system statistics"""
        try:
            stats = {}
            
            # Core CRM stats
            if 'Lead' in globals():
                stats['total_leads'] = Lead.objects.count()
                stats['qualified_leads'] = Lead.objects.filter(status='qualified').count()
            
            if 'Account' in globals():
                stats['total_accounts'] = Account.objects.count()
                stats['active_accounts'] = Account.objects.filter(status='active').count()
            
            if 'Opportunity' in globals():
                stats['total_opportunities'] = Opportunity.objects.count()
                stats['open_opportunities'] = Opportunity.objects.exclude(
                    stage__in=['won', 'lost']
                ).count()
            
            if 'Ticket' in globals():
                stats['open_tickets'] = Ticket.objects.filter(
                    status__in=['new', 'open', 'in_progress']
                ).count()
            
            # Recent activity stats (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            if 'Activity' in globals():
                stats['recent_activities'] = Activity.objects.filter(
                    created_at__gte=thirty_days_ago
                ).count()
            
            return stats
            
        except Exception as e:
            logger.error(f"System statistics generation failed: {e}")
            return {}
    
    def _get_recent_activity(self, tenant, limit=10) -> List:
        """Get recent system activity"""
        try:
            activities = []
            
            if 'AuditLog' in globals():
                recent_logs = AuditLog.objects.select_related('user').order_by(
                    '-timestamp'
                )[:limit]
                
                for log in recent_logs:
                    activities.append({
                        'type': log.event_type,
                        'user': log.user.get_full_name() if log.user else 'System',
                        'description': log.event_subtype,
                        'timestamp': log.timestamp,
                        'object_type': log.object_type,
                        'ip_address': log.ip_address
                    })
            
            return activities
            
        except Exception as e:
            logger.error(f"Recent activity fetch failed: {e}")
            return []
    
    def _get_performance_metrics(self, tenant) -> Dict:
        """Get system performance metrics"""
        try:
            metrics = {}
            
            # Database performance
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_session")
                metrics['active_sessions'] = cursor.fetchone()[0]
            
            # API usage metrics
            if 'APIUsageLog' in globals():
                today = timezone.now().date()
                metrics['api_calls_today'] = APIUsageLog.objects.filter(
                    timestamp__date=today
                ).count()
            
            # Task execution metrics
            if 'TaskExecution' in globals():
                metrics['pending_tasks'] = TaskExecution.objects.filter(
                    status='pending'
                ).count()
                metrics['failed_tasks'] = TaskExecution.objects.filter(
                    status='failed'
                ).count()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Performance metrics generation failed: {e}")
            return {}
    
    def _get_security_alerts(self, tenant) -> List:
        """Get security alerts and warnings"""
        try:
            alerts = []
            
            # Check for failed login attempts
            if 'AuditLog' in globals():
                recent_failures = AuditLog.objects.filter(
                    event_type='AUTHENTICATION_FAILURE',
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count()
                
                if recent_failures > 50:
                    alerts.append({
                        'level': 'warning',
                        'message': f'{recent_failures} failed login attempts in last 24 hours',
                        'type': 'authentication'
                    })
            
            # Check for unusual data access patterns
            unusual_access = AuditLog.objects.filter(
                event_type='DATA_ACCESS',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).values('user').annotate(
                access_count=Count('id')
            ).filter(access_count__gt=100)
            
            if unusual_access.exists():
                alerts.append({
                    'level': 'high',
                    'message': 'Unusual data access pattern detected',
                    'type': 'data_access'
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Security alerts generation failed: {e}")
            return []
    
    def _get_task_statistics(self, tenant) -> Dict:
        """Get background task statistics"""
        try:
            stats = {}
            
            if 'TaskExecution' in globals():
                stats['total_tasks'] = TaskExecution.objects.count()
                stats['completed_tasks'] = TaskExecution.objects.filter(
                    status='completed'
                ).count()
                stats['failed_tasks'] = TaskExecution.objects.filter(
                    status='failed'
                ).count()
                stats['running_tasks'] = TaskExecution.objects.filter(
                    status='running'
                ).count()
            
            return stats
            
        except Exception as e:
            logger.error(f"Task statistics generation failed: {e}")
            return {}
    
    def _get_user_permissions(self, user) -> List:
        """Get user's admin permissions"""
        try:
            permissions = []
            
            if user.is_superuser:
                permissions.append('all')
                return permissions
            
            # Check specific permissions
            if user.has_perm('crm.view_analytics'):
                permissions.append('analytics')
            
            if user.has_perm('crm.manage_users'):
                permissions.append('user_management')
            
            if user.has_perm('crm.system_admin'):
                permissions.append('system_admin')
            
            return permissions
            
        except Exception as e:
            logger.error(f"User permissions fetch failed: {e}")
            return []
    
    def _get_quick_actions(self, user) -> List:
        """Get quick action buttons for user"""
        actions = []
        
        if user.has_perm('crm.add_lead'):
            actions.append({
                'name': 'Add Lead',
                'url': reverse('admin:crm_lead_add'),
                'icon': 'fas fa-plus'
            })
        
        if user.has_perm('crm.add_account'):
            actions.append({
                'name': 'Add Account', 
                'url': reverse('admin:crm_account_add'),
                'icon': 'fas fa-building'
            })
        
        if user.has_perm('crm.view_analytics'):
            actions.append({
                'name': 'View Analytics',
                'url': reverse('admin:crm_analytics'),
                'icon': 'fas fa-chart-bar'
            })
        
        return actions
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def analytics_view(self, request):
        """Advanced analytics dashboard"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        # Generate analytics data
        analytics_data = self._generate_analytics_data(request)
        
        context = {
            'title': 'CRM Analytics Dashboard',
            'analytics_data': analytics_data,
            'opts': {'app_label': 'crm', 'model_name': 'analytics'},
        }
        
        return TemplateResponse(request, 'crm_admin/analytics.html', context)
    
    def _generate_analytics_data(self, request) -> Dict:
        """Generate comprehensive analytics data"""
        try:
            data = {}
            
            # Lead analytics
            if 'Lead' in globals():
                data['lead_conversion_rate'] = self._calculate_lead_conversion_rate()
                data['leads_by_source'] = self._get_leads_by_source()
            
            # Opportunity analytics
            if 'Opportunity' in globals():
                data['pipeline_value'] = self._calculate_pipeline_value()
                data['win_rate'] = self._calculate_win_rate()
            
            # Activity analytics
            if 'Activity' in globals():
                data['activity_trends'] = self._get_activity_trends()
            
            return data
            
        except Exception as e:
            logger.error(f"Analytics data generation failed: {e}")
            return {}
    
    def _calculate_lead_conversion_rate(self) -> float:
        """Calculate lead conversion rate"""
        try:
            total_leads = Lead.objects.count()
            converted_leads = Lead.objects.filter(status='converted').count()
            
            if total_leads > 0:
                return (converted_leads / total_leads) * 100
            return 0.0
            
        except Exception as e:
            logger.error(f"Lead conversion rate calculation failed: {e}")
            return 0.0
    
    def system_health_view(self, request):
        """System health monitoring dashboard"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        health_data = self._get_system_health_data(request)
        
        context = {
            'title': 'System Health Monitor',
            'health_data': health_data,
            'opts': {'app_label': 'crm', 'model_name': 'system_health'},
        }
        
        return TemplateResponse(request, 'crm_admin/system_health.html', context)
    
    def _get_system_health_data(self, request) -> Dict:
        """Get comprehensive system health data"""
        try:
            from django.db import connection
            import psutil
            import os
            
            health_data = {}
            
            # Database health
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                health_data['database_version'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM pg_stat_activity")
                health_data['active_connections'] = cursor.fetchone()[0]
            
            # System resources
            health_data['cpu_usage'] = psutil.cpu_percent(interval=1)
            health_data['memory_usage'] = psutil.virtual_memory().percent
            health_data['disk_usage'] = psutil.disk_usage('/').percent
            
            # Application health
            health_data['uptime'] = self._get_application_uptime()
            health_data['cache_status'] = self._check_cache_status()
            
            return health_data
            
        except Exception as e:
            logger.error(f"System health data fetch failed: {e}")
            return {'error': 'Health data unavailable'}
    
    def audit_logs_view(self, request):
        """Comprehensive audit logs viewer"""
        if not request.user.has_perm('crm.view_auditlog'):
            raise PermissionDenied()
        
        # Get audit logs with filters
        logs = self._get_filtered_audit_logs(request)
        
        context = {
            'title': 'Audit Logs',
            'audit_logs': logs,
            'opts': {'app_label': 'crm', 'model_name': 'audit_logs'},
        }
        
        return TemplateResponse(request, 'crm_admin/audit_logs.html', context)
    
    def _get_filtered_audit_logs(self, request):
        """Get filtered audit logs"""
        try:
            if 'AuditLog' not in globals():
                return []
            
            logs = AuditLog.objects.select_related('user').order_by('-timestamp')
            
            # Apply filters from request
            event_type = request.GET.get('event_type')
            if event_type:
                logs = logs.filter(event_type=event_type)
            
            user_id = request.GET.get('user_id')
            if user_id:
                logs = logs.filter(user_id=user_id)
            
            date_from = request.GET.get('date_from')
            if date_from:
                logs = logs.filter(timestamp__date__gte=date_from)
            
            date_to = request.GET.get('date_to')
            if date_to:
                logs = logs.filter(timestamp__date__lte=date_to)
            
            return logs[:100]  # Limit to recent 100 logs
            
        except Exception as e:
            logger.error(f"Audit logs filtering failed: {e}")
            return []
    
    def performance_view(self, request):
        """Performance monitoring view"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        performance_data = self._get_detailed_performance_data()
        
        context = {
            'title': 'Performance Monitor',
            'performance_data': performance_data,
            'opts': {'app_label': 'crm', 'model_name': 'performance'},
        }
        
        return TemplateResponse(request, 'crm_admin/performance.html', context)
    
    def security_monitor_view(self, request):
        """Security monitoring view"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        security_data = self._get_security_monitoring_data()
        
        context = {
            'title': 'Security Monitor',
            'security_data': security_data,
            'opts': {'app_label': 'crm', 'model_name': 'security'},
        }
        
        return TemplateResponse(request, 'crm_admin/security.html', context)
    
    def bulk_operations_view(self, request):
        """Bulk operations management view"""
        if not self.has_permission(request):
            raise PermissionDenied()
        
        context = {
            'title': 'Bulk Operations',
            'opts': {'app_label': 'crm', 'model_name': 'bulk_operations'},
        }
        
        return TemplateResponse(request, 'crm_admin/bulk_operations.html', context)
    
    def export_data_view(self, request):
        """Data export interface"""
        if not request.user.has_perm('crm.export_data'):
            raise PermissionDenied()
        
        context = {
            'title': 'Data Export',
            'opts': {'app_label': 'crm', 'model_name': 'export'},
        }
        
        return TemplateResponse(request, 'crm_admin/export_data.html', context)
    
    def import_data_view(self, request):
        """Data import interface"""
        if not request.user.has_perm('crm.import_data'):
            raise PermissionDenied()
        
        context = {
            'title': 'Data Import',
            'opts': {'app_label': 'crm', 'model_name': 'import'},
        }
        
        return TemplateResponse(request, 'crm_admin/import_data.html', context)
    
    def dashboard_stats_api(self, request):
        """API endpoint for dashboard statistics"""
        if not self.has_permission(request):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        stats = self._get_system_statistics(getattr(request, 'tenant', None))
        return JsonResponse(stats)
    
    def system_status_api(self, request):
        """API endpoint for system status"""
        if not self.has_permission(request):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        }
        
        return JsonResponse(status)
    
    def register_models(self):
        """Register all CRM models with appropriate admin classes"""
        try:
            # Import admin classes
            from .user import CRMUserProfileAdmin
            from .account import AccountAdmin
            from .lead import LeadAdmin, LeadSourceAdmin, LeadScoringRuleAdmin
            from .opportunity import OpportunityAdmin, PipelineAdmin, PipelineStageAdmin
            from .activity import ActivityAdmin, ActivityTypeAdmin, EmailLogAdmin
            from .campaign import CampaignAdmin, EmailTemplateAdmin
            from .ticket import TicketAdmin, TicketCategoryAdmin, SLAAdmin
            from .system import TaskExecutionAdmin, AuditLogAdmin
            
            # Core models
            if 'CRMConfiguration' in globals():
                self.register(CRMConfiguration, CRMConfigurationAdmin)
            
            if 'CRMUserProfile' in globals():
                self.register(CRMUserProfile, CRMUserProfileAdmin)
            
            # Lead management
            if 'Lead' in globals():
                self.register(Lead, LeadAdmin)
            if 'LeadSource' in globals():
                self.register(LeadSource, LeadSourceAdmin)
            if 'LeadScoringRule' in globals():
                self.register(LeadScoringRule, LeadScoringRuleAdmin)
            
            # Account management  
            if 'Account' in globals():
                self.register(Account, AccountAdmin)
            if 'Contact' in globals():
                from .account import ContactAdmin
                self.register(Contact, ContactAdmin)
            if 'Industry' in globals():
                from .account import IndustryAdmin
                self.register(Industry, IndustryAdmin)
            
            # Opportunity management
            if 'Opportunity' in globals():
                self.register(Opportunity, OpportunityAdmin)
            if 'Pipeline' in globals():
                self.register(Pipeline, PipelineAdmin)
            if 'PipelineStage' in globals():
                self.register(PipelineStage, PipelineStageAdmin)
            
            # Activity management
            if 'Activity' in globals():
                self.register(Activity, ActivityAdmin)
            if 'ActivityType' in globals():
                self.register(ActivityType, ActivityTypeAdmin)
            if 'EmailLog' in globals():
                self.register(EmailLog, EmailLogAdmin)
            
            # Campaign management
            if 'Campaign' in globals():
                self.register(Campaign, CampaignAdmin)
            if 'EmailTemplate' in globals():
                self.register(EmailTemplate, EmailTemplateAdmin)
            
            # Support management
            if 'Ticket' in globals():
                self.register(Ticket, TicketAdmin)
            if 'TicketCategory' in globals():
                self.register(TicketCategory, TicketCategoryAdmin)
            if 'SLA' in globals():
                self.register(SLA, SLAAdmin)
            
            # System models
            if 'AuditLog' in globals():
                self.register(AuditLog, AuditLogAdmin)
            if 'TaskExecution' in globals():
                self.register(TaskExecution, TaskExecutionAdmin)
                
        except ImportError as e:
            logger.warning(f"Some admin classes not found during registration: {e}")


class BaseModelAdmin(admin.ModelAdmin):
    """
    Enhanced base model admin with security, audit logging, and advanced features
    """
    
    # Enhanced list display configuration
    list_per_page = 25
    list_max_show_all = 100
    show_full_result_count = True
    
    # Advanced filtering
    list_filter = ['created_at', 'updated_at']
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
        try:
            self.permission_checker = DynamicRolePermission()
        except:
            self.permission_checker = CRMPermission()
    
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
            
            # Check CRM profile roles
            if hasattr(request.user, 'crm_profile'):
                view_roles = ['system_admin', 'crm_admin', 'tenant_admin', 'analyst']
                if request.user.crm_profile.role in view_roles:
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
            
            # Check CRM profile roles
            if hasattr(request.user, 'crm_profile'):
                change_roles = ['system_admin', 'crm_admin', 'tenant_admin']
                if request.user.crm_profile.role not in change_roles:
                    return False
            
            # Object-level permission check
            if obj:
                return self._check_object_permission(request, obj, 'change')
            
            return True
            
        except Exception as e:
            logger.error(f"Change permission check failed: {e}")
            return False
    
    def _check_object_permission(self, request, obj, action):
        """Check object-level permissions"""
        try:
            # Owner can view/change their objects
            if hasattr(obj, 'created_by') and obj.created_by == request.user:
                return True
            
            # Check assigned user
            if hasattr(obj, 'assigned_to') and obj.assigned_to == request.user:
                return True
            
            # Manager can access team objects
            if hasattr(request.user, 'crm_profile'):
                if request.user.crm_profile.role in ['manager', 'admin']:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Object permission check failed: {e}")
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
                try:
                    old_obj = self.model.objects.get(pk=obj.pk)
                except self.model.DoesNotExist:
                    pass
            
            super().save_model(request, obj, form, change)
            
            # Log the change
            self._log_model_change(request, obj, old_obj, change)
            
        except Exception as e:
            logger.error(f"Model save failed: {e}")
            messages.error(request, f"Save failed: {str(e)}")
            raise
    
    def delete_model(self, request, obj):
        """Enhanced delete with audit logging"""
        try:
            # Log before deletion
            self._log_model_deletion(request, obj)
            
            # Perform soft delete if supported
            if hasattr(obj, 'is_active'):
                obj.is_active = False
                if hasattr(obj, 'deleted_by'):
                    obj.deleted_by = request.user
                if hasattr(obj, 'deleted_at'):
                    obj.deleted_at = timezone.now()
                obj.save()
            else:
                super().delete_model(request, obj)
            
        except Exception as e:
            logger.error(f"Model deletion failed: {e}")
            messages.error(request, f"Delete failed: {str(e)}")
            raise
    
    def get_list_display(self, request):
        """Dynamic list display based on permissions"""
        list_display = list(super().get_list_display(request))
        
        # Add status indicators for admins
        if request.user.is_superuser or self._is_admin_user(request):
            if 'status_indicator' not in list_display:
                list_display.append('status_indicator')
        
        # Add audit fields for compliance users
        if self._is_compliance_user(request):
            if 'created_by' not in list_display:
                list_display.append('created_by')
            if 'updated_at' not in list_display:
                list_display.append('updated_at')
        
        return list_display
    
    def _is_admin_user(self, request):
        """Check if user is admin"""
        if hasattr(request, 'user_roles'):
            return any('ADMIN' in role for role in request.user_roles)
        
        if hasattr(request.user, 'crm_profile'):
            return 'admin' in request.user.crm_profile.role.lower()
        
        return False
    
    def _is_compliance_user(self, request):
        """Check if user is compliance officer"""
        if hasattr(request, 'user_roles'):
            return 'COMPLIANCE_OFFICER' in request.user_roles
        
        if hasattr(request.user, 'crm_profile'):
            return 'compliance' in request.user.crm_profile.role.lower()
        
        return False
    
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
        
        if hasattr(obj, 'status'):
            status_colors = {
                'active': 'green',
                'inactive': 'red',
                'pending': 'orange',
                'draft': 'gray'
            }
            color = status_colors.get(str(obj.status).lower(), 'black')
            return format_html(
                f'<span style="color: {color}; font-weight: bold;">●</span> {obj.status}'
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
            
            # Check CRM profile roles
            if hasattr(request.user, 'crm_profile'):
                if 'manager' in request.user.crm_profile.role.lower():
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
            if 'AuditLog' not in globals():
                return
            
            changes = {}
            
            if is_update and old_obj:
                # Calculate field changes
                for field in obj._meta.fields:
                    field_name = field.name
                    old_value = getattr(old_obj, field_name, None)
                    new_value = getattr(obj, field_name, None)
                    
                    if old_value != new_value:
                        changes[field_name] = {
                            'old': str(old_value) if old_value is not None else None,
                            'new': str(new_value) if new_value is not None else None
                        }
            
            # Create audit log
            AuditLog.objects.create(
                event_type='DATA_MODIFICATION',
                event_subtype='UPDATE' if is_update else 'CREATE',
                user=request.user,
                tenant=getattr(request, 'tenant', None),
                object_type=obj.__class__.__name__,
                object_id=str(obj.pk),
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
    
    def _log_model_deletion(self, request, obj):
        """Log model deletion"""
        try:
            if 'AuditLog' not in globals():
                return
            
            AuditLog.objects.create(
                event_type='DATA_DELETION',
                event_subtype='DELETE',
                user=request.user,
                tenant=getattr(request, 'tenant', None),
                object_type=obj.__class__.__name__,
                object_id=str(obj.pk),
                timestamp=timezone.now(),
                ip_address=self._get_client_ip(request),
                additional_data={
                    'model': obj.__class__.__name__,
                    'object_data': self._serialize_object_data(obj),
                    'admin_interface': True
                }
            )
            
        except Exception as e:
            logger.error(f"Model deletion logging failed: {e}")
    
    def _serialize_object_data(self, obj):
        """Serialize object data for logging"""
        try:
            data = {}
            for field in obj._meta.fields:
                field_name = field.name
                field_value = getattr(obj, field_name, None)
                data[field_name] = str(field_value) if field_value is not None else None
            return data
        except Exception as e:
            logger.error(f"Object serialization failed: {e}")
            return {}
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


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
            form.base_fields['tenant'].widget = widgets.HiddenInput()
        
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
        if hasattr(request, 'tenant') and 'CRMConfiguration' in globals():
            existing_config = CRMConfiguration.objects.filter(tenant=request.tenant).exists()
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
        elif self.value() == 'last_week':
            start_week = today - timedelta(days=today.weekday() + 7)
            end_week = today - timedelta(days=today.weekday() + 1)
            return queryset.filter(created_at__date__gte=start_week, created_at__date__lte=end_week)
        elif self.value() == 'this_month':
            start_month = today.replace(day=1)
            return queryset.filter(created_at__date__gte=start_month)
        elif self.value() == 'last_month':
            if today.month == 1:
                start_month = today.replace(year=today.year-1, month=12, day=1)
                end_month = today.replace(day=1) - timedelta(days=1)
            else:
                start_month = today.replace(month=today.month-1, day=1)
                end_month = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(created_at__date__gte=start_month, created_at__date__lte=end_month)
        elif self.value() == 'this_quarter':
            quarter_start = timezone.datetime(today.year, 3 * ((today.month - 1) // 3) + 1, 1).date()
            return queryset.filter(created_at__date__gte=quarter_start)
        elif self.value() == 'this_year':
            year_start = today.replace(month=1, day=1)
            return queryset.filter(created_at__date__gte=year_start)
        
        return queryset


# Export the main admin site instance
crm_admin_site = CRMAdminSite()