# ============================================================================
# backend/apps/crm/views/system.py - System Administration Views
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, View
from django.db.models import Q, Count, Sum, Avg, F, Max, Min
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction, connection
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.management import call_command
from django.conf import settings
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json
import csv
import io
from datetime import datetime, timedelta

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import AuditTrail, DataExportLog, APIUsageLog, SyncLog
from ..serializers import AuditTrailSerializer, DataExportLogSerializer, APIUsageLogSerializer, SyncLogSerializer
from ..permissions import SystemAdminPermission
from ..services import SystemService, DataExportService, AuditService


class SystemDashboardView(CRMBaseMixin, PermissionRequiredMixin, View):
    """System administration dashboard"""
    
    template_name = 'crm/system/dashboard.html'
    permission_required = 'crm.view_system_admin'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(context)
            
        return render(request, self.template_name, context)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        
        context = {
            'system_overview': self.get_system_overview(tenant),
            'database_statistics': self.get_database_statistics(tenant),
            'api_usage_stats': self.get_api_usage_stats(tenant),
            'user_activity': self.get_user_activity_stats(tenant),
            'storage_usage': self.get_storage_usage(tenant),
            'system_health': self.get_system_health(tenant),
            'recent_activities': self.get_recent_system_activities(tenant),
            'performance_metrics': self.get_performance_metrics(tenant),
            'security_overview': self.get_security_overview(tenant),
        }
        
        return context
    
    def get_system_overview(self, tenant):
        """Get high-level system overview"""
        # Get counts for all major entities
        overview = {
            'total_users': tenant.tenant_memberships.filter(is_active=True).count(),
            'total_leads': tenant.leads.count(),
            'total_accounts': tenant.accounts.count(),
            'total_opportunities': tenant.opportunities.count(),
            'total_activities': tenant.activities.count(),
            'total_campaigns': tenant.campaigns.count(),
            'total_tickets': tenant.tickets.count(),
            'total_products': tenant.products.count(),
        }
        
        # Calculate growth rates (30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        previous_counts = {
            'previous_leads': tenant.leads.filter(created_at__lt=thirty_days_ago).count(),
            'previous_accounts': tenant.accounts.filter(created_at__lt=thirty_days_ago).count(),
            'previous_opportunities': tenant.opportunities.filter(created_at__lt=thirty_days_ago).count(),
        }
        
        # Calculate growth rates
        def calculate_growth(current, previous):
            if previous > 0:
                return round(((current - previous) / previous) * 100, 1)
            return 0 if current == 0 else 100
        
        overview['leads_growth'] = calculate_growth(
            overview['total_leads'], previous_counts['previous_leads']
        )
        overview['accounts_growth'] = calculate_growth(
            overview['total_accounts'], previous_counts['previous_accounts']
        )
        overview['opportunities_growth'] = calculate_growth(
            overview['total_opportunities'], previous_counts['previous_opportunities']
        )
        
        return overview
    
    def get_database_statistics(self, tenant):
        """Get database statistics"""
        try:
            with connection.cursor() as cursor:
                # Get table sizes (PostgreSQL specific)
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables 
                    WHERE schemaname = %s
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """, [tenant.schema_name])
                
                table_sizes = cursor.fetchall()
                
                # Get total schema size
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(sum(pg_total_relation_size(schemaname||'.'||tablename))) as total_size
                    FROM pg_tables 
                    WHERE schemaname = %s
                """, [tenant.schema_name])
                
                total_size = cursor.fetchone()[0]
        
        except Exception as e:
            table_sizes = []
            total_size = "Unknown"
        
        return {
            'total_schema_size': total_size,
            'largest_tables': [
                {
                    'table_name': row[1],
                    'size': row[2],
                    'size_bytes': row[3]
                }
                for row in table_sizes
            ],
            'record_counts': self.get_record_counts(tenant),
        }
    
    def get_record_counts(self, tenant):
        """Get record counts for all main tables"""
        return {
            'leads': tenant.leads.count(),
            'accounts': tenant.accounts.count(),
            'contacts': tenant.contacts.count(),
            'opportunities': tenant.opportunities.count(),
            'activities': tenant.activities.count(),
            'campaigns': tenant.campaigns.count(),
            'tickets': tenant.tickets.count(),
            'products': tenant.products.count(),
            'workflows': tenant.workflow_rules.count(),
            'audit_trails': tenant.audit_trails.count(),
        }
    
    def get_api_usage_stats(self, tenant):
        """Get API usage statistics"""
        # Last 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        
        api_logs = tenant.api_usage_logs.filter(
            timestamp__gte=twenty_four_hours_ago
        )
        
        stats = {
            'total_requests': api_logs.count(),
            'unique_users': api_logs.values('user').distinct().count(),
            'avg_response_time': api_logs.aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0,
            'error_rate': self.calculate_api_error_rate(api_logs),
            'requests_by_endpoint': list(api_logs.values('endpoint').annotate(
                count=Count('id')
            ).order_by('-count')[:10]),
            'hourly_distribution': list(api_logs.annotate(
                hour=TruncHour('timestamp')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')),
        }
        
        return stats
    
    def calculate_api_error_rate(self, api_logs):
        """Calculate API error rate"""
        total_requests = api_logs.count()
        error_requests = api_logs.filter(status_code__gte=400).count()
        
        if total_requests > 0:
            return round((error_requests / total_requests) * 100, 2)
        return 0
    
    def get_user_activity_stats(self, tenant):
        """Get user activity statistics"""
        # Active users in different time periods
        now = timezone.now()
        
        active_users = {
            'last_hour': tenant.audit_trails.filter(
                timestamp__gte=now - timedelta(hours=1)
            ).values('user').distinct().count(),
            'last_24_hours': tenant.audit_trails.filter(
                timestamp__gte=now - timedelta(hours=24)
            ).values('user').distinct().count(),
            'last_7_days': tenant.audit_trails.filter(
                timestamp__gte=now - timedelta(days=7)
            ).values('user').distinct().count(),
            'last_30_days': tenant.audit_trails.filter(
                timestamp__gte=now - timedelta(days=30)
            ).values('user').distinct().count(),
        }
        
        # Most active users (last 7 days)
        most_active = tenant.audit_trails.filter(
            timestamp__gte=now - timedelta(days=7)
        ).values('user__first_name', 'user__last_name', 'user__email').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        # Activity by action type
        activity_by_action = tenant.audit_trails.filter(
            timestamp__gte=now - timedelta(days=7)
        ).values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'active_users': active_users,
            'most_active_users': list(most_active),
            'activity_by_action': list(activity_by_action),
        }
    
    def get_storage_usage(self, tenant):
        """Get storage usage statistics"""
        # Calculate document storage usage
        document_storage = tenant.documents.aggregate(
            total_size=Sum('file_size'),
            file_count=Count('id')
        )
        
        # Storage by document type
        storage_by_type = tenant.documents.values('file_type').annotate(
            total_size=Sum('file_size'),
            file_count=Count('id')
        ).order_by('-total_size')
        
        return {
            'total_documents': document_storage['file_count'] or 0,
            'total_storage_bytes': document_storage['total_size'] or 0,
            'total_storage_formatted': self.format_file_size(document_storage['total_size'] or 0),
            'storage_by_type': [
                {
                    'file_type': item['file_type'],
                    'size_bytes': item['total_size'],
                    'size_formatted': self.format_file_size(item['total_size']),
                    'file_count': item['file_count']
                }
                for item in storage_by_type
            ],
        }
    
    def format_file_size(self, bytes_size):
        """Format file size in human readable format"""
        if bytes_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(bytes_size, 1024)))
        p = math.pow(1024, i)
        s = round(bytes_size / p, 2)
        
        return f"{s} {size_names[i]}"
    
    def get_system_health(self, tenant):
        """Get system health indicators"""
        health_indicators = {}
        
        try:
            # Database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_indicators['database'] = {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            health_indicators['database'] = {'status': 'error', 'message': str(e)}
        
        # Cache health (if using cache)
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', 60)
            if cache.get('health_check') == 'ok':
                health_indicators['cache'] = {'status': 'healthy', 'message': 'Working'}
            else:
                health_indicators['cache'] = {'status': 'warning', 'message': 'Not responding'}
        except Exception as e:
            health_indicators['cache'] = {'status': 'error', 'message': str(e)}
        
        # Recent errors
        recent_errors = tenant.audit_trails.filter(
            timestamp__gte=timezone.now() - timedelta(hours=1),
            action_type='ERROR'
        ).count()
        
        if recent_errors == 0:
            health_indicators['errors'] = {'status': 'healthy', 'message': 'No recent errors'}
        elif recent_errors < 10:
            health_indicators['errors'] = {'status': 'warning', 'message': f'{recent_errors} errors in last hour'}
        else:
            health_indicators['errors'] = {'status': 'error', 'message': f'{recent_errors} errors in last hour'}
        
        return health_indicators
    
    def get_recent_system_activities(self, tenant):
        """Get recent system activities"""
        return tenant.audit_trails.select_related('user').filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-timestamp')[:20]
    
    def get_performance_metrics(self, tenant):
        """Get system performance metrics"""
        # API response times
        api_performance = tenant.api_usage_logs.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).aggregate(
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            min_response_time=Min('response_time_ms')
        )
        
        # Workflow execution performance
        workflow_performance = tenant.workflow_executions.filter(
            executed_at__gte=timezone.now() - timedelta(hours=24)
        ).aggregate(
            avg_execution_time=Avg('execution_time_ms'),
            total_executions=Count('id'),
            successful_executions=Count('id', filter=Q(status='SUCCESS'))
        )
        
        return {
            'api_performance': api_performance,
            'workflow_performance': workflow_performance,
            'workflow_success_rate': (
                workflow_performance['successful_executions'] / workflow_performance['total_executions'] * 100
                if workflow_performance['total_executions'] > 0 else 0
            ),
        }
    
    def get_security_overview(self, tenant):
        """Get security overview"""
        # Failed login attempts (would need login attempt logging)
        # Suspicious activities
        # Permission changes
        
        security_events = tenant.audit_trails.filter(
            timestamp__gte=timezone.now() - timedelta(days=7),
            action_type__in=['LOGIN_FAILED', 'PERMISSION_CHANGED', 'SUSPICIOUS_ACTIVITY']
        ).count()
        
        # Recent permission changes
        permission_changes = tenant.audit_trails.filter(
            timestamp__gte=timezone.now() - timedelta(days=7),
            action_type='PERMISSION_CHANGED'
        ).order_by('-timestamp')[:5]
        
        return {
            'security_events_count': security_events,
            'recent_permission_changes': permission_changes,
            'active_sessions': self.get_active_sessions_count(tenant),
        }
    
    def get_active_sessions_count(self, tenant):
        """Get count of active user sessions"""
        # This would require session tracking implementation
        return tenant.tenant_memberships.filter(is_active=True).count()


class AuditTrailListView(CRMBaseMixin, PermissionRequiredMixin, ListView):
    """Audit trail view for system administrators"""
    
    model = AuditTrail
    template_name = 'crm/system/audit_trail.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    permission_required = 'crm.view_audit_trail'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        queryset = queryset.select_related('user').order_by('-timestamp')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(model_name__icontains=search) |
                Q(action_type__icontains=search)
            )
        
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        action_type = self.request.GET.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        model_name = self.request.GET.get('model')
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter options
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        context.update({
            'users': User.objects.filter(
                tenant_memberships__tenant=self.request.tenant,
                tenant_memberships__is_active=True
            ).distinct(),
            'action_types': AuditTrail.objects.filter(
                tenant=self.request.tenant
            ).values_list('action_type', flat=True).distinct(),
            'model_names': AuditTrail.objects.filter(
                tenant=self.request.tenant
            ).values_list('model_name', flat=True).distinct(),
            'audit_statistics': self.get_audit_statistics(),
        })
        
        return context
    
    def get_audit_statistics(self):
        """Get audit trail statistics"""
        queryset = self.get_queryset()
        
        # Activity by action type
        activity_by_action = queryset.values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Activity by user
        activity_by_user = queryset.values(
            'user__first_name', 'user__last_name', 'user__email'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Daily activity (last 30 days)
        daily_activity = queryset.filter(
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return {
            'total_logs': queryset.count(),
            'activity_by_action': list(activity_by_action),
            'activity_by_user': list(activity_by_user),
            'daily_activity': list(daily_activity),
        }


class DataExportView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Data export management view"""
    
    template_name = 'crm/system/data_export.html'
    permission_required = 'crm.export_data'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle data export request"""
        export_type = request.POST.get('export_type')
        export_format = request.POST.get('export_format', 'csv')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        include_deleted = request.POST.get('include_deleted') == 'on'
        
        try:
            service = DataExportService()
            
            # Create export log
            export_log = DataExportLog.objects.create(
                export_type=export_type,
                export_format=export_format,
                date_from=date_from if date_from else None,
                date_to=date_to if date_to else None,
                include_deleted=include_deleted,
                status='PENDING',
                tenant=request.tenant,
                requested_by=request.user
            )
            
            # Start export process (could be async with Celery)
            export_result = service.export_data(
                tenant=request.tenant,
                export_type=export_type,
                export_format=export_format,
                date_from=date_from,
                date_to=date_to,
                include_deleted=include_deleted
            )
            
            # Update export log
            export_log.status = 'COMPLETED'
            export_log.file_path = export_result.get('file_path')
            export_log.record_count = export_result.get('record_count', 0)
            export_log.file_size = export_result.get('file_size', 0)
            export_log.completed_at = timezone.now()
            export_log.save()
            
            # Return file for download
            if export_format == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{export_type}_{timezone.now().date()}.csv"'
                
                with open(export_result['file_path'], 'r') as f:
                    response.write(f.read())
                
                return response
            
            messages.success(request, f'Data export completed successfully. {export_result["record_count"]} records exported.')
            
        except Exception as e:
            if 'export_log' in locals():
                export_log.status = 'FAILED'
                export_log.error_message = str(e)
                export_log.save()
            
            messages.error(request, f'Export failed: {str(e)}')
        
        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        
        # Get export history
        export_history = DataExportLog.objects.filter(
            tenant=tenant
        ).select_related('requested_by').order_by('-created_at')[:20]
        
        # Export statistics
        export_stats = {
            'total_exports': export_history.count(),
            'successful_exports': export_history.filter(status='COMPLETED').count(),
            'failed_exports': export_history.filter(status='FAILED').count(),
            'exports_by_type': list(export_history.values('export_type').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
        
        # Available export types
        export_types = [
            {'value': 'leads', 'name': 'Leads', 'description': 'All lead data'},
            {'value': 'accounts', 'name': 'Accounts', 'description': 'Account and contact data'},
            {'value': 'opportunities', 'name': 'Opportunities', 'description': 'Sales opportunity data'},
            {'value': 'activities', 'name': 'Activities', 'description': 'Activity and task data'},
            {'value': 'campaigns', 'name': 'Campaigns', 'description': 'Marketing campaign data'},
            {'value': 'tickets', 'name': 'Support Tickets', 'description': 'Customer service tickets'},
            {'value': 'products', 'name': 'Products', 'description': 'Product catalog data'},
            {'value': 'all', 'name': 'Complete Export', 'description': 'All CRM data'},
        ]
        
        return {
            'export_history': export_history,
            'export_stats': export_stats,
            'export_types': export_types,
            'available_formats': ['csv', 'json', 'excel'],
        }


class DataImportView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Data import management view"""
    
    template_name = 'crm/system/data_import.html'
    permission_required = 'crm.import_data'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle data import request"""
        import_type = request.POST.get('import_type')
        import_file = request.FILES.get('import_file')
        update_existing = request.POST.get('update_existing') == 'on'
        
        if not import_file:
            messages.error(request, 'Please select a file to import.')
            return self.get(request, *args, **kwargs)
        
        try:
            service = DataExportService()  # Also handles imports
            
            # Process import
            import_result = service.import_data(
                tenant=request.tenant,
                import_type=import_type,
                import_file=import_file,
                update_existing=update_existing,
                user=request.user
            )
            
            messages.success(
                request, 
                f'Import completed. {import_result["created_count"]} records created, '
                f'{import_result["updated_count"]} updated, '
                f'{import_result["error_count"]} errors.'
            )
            
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
        
        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        # Import templates and examples
        import_types = [
            {
                'value': 'leads',
                'name': 'Leads',
                'description': 'Import lead data',
                'required_fields': ['first_name', 'last_name', 'email'],
                'optional_fields': ['phone', 'company', 'source', 'status']
            },
            {
                'value': 'accounts',
                'name': 'Accounts',
                'description': 'Import account data',
                'required_fields': ['name'],
                'optional_fields': ['industry', 'website', 'phone', 'revenue']
            },
            {
                'value': 'products',
                'name': 'Products',
                'description': 'Import product catalog',
                'required_fields': ['name', 'sku', 'price'],
                'optional_fields': ['description', 'category', 'active']
            }
        ]
        
        return {
            'import_types': import_types,
        }


class SystemConfigurationView(CRMBaseMixin, PermissionRequiredMixin, View):
    """System configuration management"""
    
    template_name = 'crm/system/configuration.html'
    permission_required = 'crm.change_system_config'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle configuration updates"""
        try:
            service = SystemService()
            
            # Get configuration data from form
            config_data = {}
            for key, value in request.POST.items():
                if key.startswith('config_'):
                    config_key = key.replace('config_', '')
                    config_data[config_key] = value
            
            # Update configuration
            service.update_system_configuration(request.tenant, config_data)
            
            messages.success(request, 'System configuration updated successfully.')
            
        except Exception as e:
            messages.error(request, f'Configuration update failed: {str(e)}')
        
        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        
        # Current configuration
        current_config = {
            'auto_assign_leads': True,
            'lead_scoring_enabled': True,
            'email_notifications': True,
            'workflow_automation': True,
            'data_retention_days': 365,
            'max_file_upload_size': 10,  # MB
            'api_rate_limit': 1000,  # per hour
        }
        
        # Configuration categories
        config_categories = [
            {
                'name': 'Lead Management',
                'settings': [
                    {
                        'key': 'auto_assign_leads',
                        'name': 'Auto-assign Leads',
                        'type': 'boolean',
                        'description': 'Automatically assign new leads to available users',
                        'value': current_config.get('auto_assign_leads', False)
                    },
                    {
                        'key': 'lead_scoring_enabled',
                        'name': 'Lead Scoring',
                        'type': 'boolean',
                        'description': 'Enable automatic lead scoring',
                        'value': current_config.get('lead_scoring_enabled', False)
                    }
                ]
            },
            {
                'name': 'Notifications',
                'settings': [
                    {
                        'key': 'email_notifications',
                        'name': 'Email Notifications',
                        'type': 'boolean',
                        'description': 'Send email notifications for important events',
                        'value': current_config.get('email_notifications', True)
                    }
                ]
            },
            {
                'name': 'System Limits',
                'settings': [
                    {
                        'key': 'data_retention_days',
                        'name': 'Data Retention (Days)',
                        'type': 'number',
                        'description': 'How long to keep deleted records',
                        'value': current_config.get('data_retention_days', 365)
                    },
                    {
                        'key': 'max_file_upload_size',
                        'name': 'Max File Upload Size (MB)',
                        'type': 'number',
                        'description': 'Maximum file size for uploads',
                        'value': current_config.get('max_file_upload_size', 10)
                    },
                    {
                        'key': 'api_rate_limit',
                        'name': 'API Rate Limit (per hour)',
                        'type': 'number',
                        'description': 'Maximum API requests per hour per user',
                        'value': current_config.get('api_rate_limit', 1000)
                    }
                ]
            }
        ]
        
        return {
            'current_config': current_config,
            'config_categories': config_categories,
        }


class SystemMaintenanceView(CRMBaseMixin, PermissionRequiredMixin, View):
    """System maintenance and cleanup"""
    
    template_name = 'crm/system/maintenance.html'
    permission_required = 'crm.system_maintenance'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle maintenance actions"""
        action = request.POST.get('action')
        
        try:
            service = SystemService()
            
            if action == 'cleanup_deleted':
                result = service.cleanup_deleted_records(request.tenant)
                messages.success(request, f'Cleanup completed. {result["deleted_count"]} records removed.')
                
            elif action == 'optimize_database':
                result = service.optimize_database(request.tenant)
                messages.success(request, 'Database optimization completed.')
                
            elif action == 'cleanup_logs':
                result = service.cleanup_old_logs(request.tenant)
                messages.success(request, f'Log cleanup completed. {result["deleted_count"]} old log entries removed.')
                
            elif action == 'reindex_search':
                result = service.reindex_search_data(request.tenant)
                messages.success(request, 'Search reindexing completed.')
                
            else:
                messages.error(request, 'Unknown maintenance action.')
                
        except Exception as e:
            messages.error(request, f'Maintenance action failed: {str(e)}')
        
        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        
        # Maintenance statistics
        maintenance_stats = {
            'deleted_records': self.get_deleted_record_count(tenant),
            'old_logs': self.get_old_log_count(tenant),
            'storage_usage': self.get_storage_usage_stats(tenant),
            'last_maintenance': self.get_last_maintenance_date(tenant),
        }
        
        # Available maintenance actions
        maintenance_actions = [
            {
                'id': 'cleanup_deleted',
                'name': 'Cleanup Deleted Records',
                'description': 'Permanently remove soft-deleted records older than retention period',
                'risk_level': 'medium'
            },
            {
                'id': 'optimize_database',
                'name': 'Optimize Database',
                'description': 'Run database optimization and vacuum operations',
                'risk_level': 'low'
            },
            {
                'id': 'cleanup_logs',
                'name': 'Cleanup Old Logs',
                'description': 'Remove log entries older than 90 days',
                'risk_level': 'low'
            },
            {
                'id': 'reindex_search',
                'name': 'Reindex Search Data',
                'description': 'Rebuild search indexes for better performance',
                'risk_level': 'low'
            }
        ]
        
        return {
            'maintenance_stats': maintenance_stats,
            'maintenance_actions': maintenance_actions,
        }
    
    def get_deleted_record_count(self, tenant):
        """Count soft-deleted records eligible for cleanup"""
        count = 0
        
        # Check models with is_active field
        models_to_check = [
            tenant.leads, tenant.accounts, tenant.opportunities,
            tenant.activities, tenant.campaigns, tenant.tickets
        ]
        
        for model_manager in models_to_check:
            try:
                count += model_manager.filter(is_active=False).count()
            except:
                pass
        
        return count
    
    def get_old_log_count(self, tenant):
        """Count old log entries eligible for cleanup"""
        ninety_days_ago = timezone.now() - timedelta(days=90)
        return tenant.audit_trails.filter(timestamp__lt=ninety_days_ago).count()
    
    def get_storage_usage_stats(self, tenant):
        """Get storage usage statistics"""
        documents = tenant.documents.aggregate(
            total_size=Sum('file_size'),
            file_count=Count('id')
        )
        
        return {
            'total_files': documents['file_count'] or 0,
            'total_size': documents['total_size'] or 0,
            'total_size_formatted': self.format_file_size(documents['total_size'] or 0)
        }
    
    def format_file_size(self, bytes_size):
        """Format file size in human readable format"""
        import math
        if bytes_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(bytes_size, 1024)))
        p = math.pow(1024, i)
        s = round(bytes_size / p, 2)
        
        return f"{s} {size_names[i]}"
    
    def get_last_maintenance_date(self, tenant):
        """Get last maintenance date"""
        # This would come from a maintenance log if implemented
        return timezone.now() - timedelta(days=30)  # Placeholder


# API ViewSets for System Administration

class AuditTrailViewSet(CRMBaseViewSet):
    """Audit Trail API viewset"""
    
    queryset = AuditTrail.objects.all()
    serializer_class = AuditTrailSerializer
    permission_classes = [IsAuthenticated, SystemAdminPermission]
    ordering_fields = ['timestamp', 'user', 'action_type']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('user')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get audit trail statistics"""
        queryset = self.get_queryset()
        
        # Date range filter
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(timestamp__gte=start_date)
        
        stats = {
            'total_activities': queryset.count(),
            'unique_users': queryset.values('user').distinct().count(),
            'activities_by_action': list(queryset.values('action_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'activities_by_user': list(queryset.values(
                'user__first_name', 'user__last_name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10]),
            'daily_activity': list(queryset.annotate(
                date=TruncDate('timestamp')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')),
        }
        
        return Response(stats)


class DataExportLogViewSet(CRMBaseViewSet):
    """Data Export Log API viewset"""
    
    queryset = DataExportLog.objects.all()
    serializer_class = DataExportLogSerializer
    permission_classes = [IsAuthenticated, SystemAdminPermission]
    ordering_fields = ['created_at', 'export_type', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('requested_by')
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download export file"""
        export_log = self.get_object()
        
        if export_log.status != 'COMPLETED' or not export_log.file_path:
            return Response(
                {'error': 'Export file not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            import os
            if not os.path.exists(export_log.file_path):
                return Response(
                    {'error': 'Export file not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            with open(export_log.file_path, 'rb') as f:
                response = HttpResponse(f.read())
                response['Content-Type'] = 'application/octet-stream'
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(export_log.file_path)}"'
                return response
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class APIUsageLogViewSet(CRMBaseViewSet):
    """API Usage Log API viewset"""
    
    queryset = APIUsageLog.objects.all()
    serializer_class = APIUsageLogSerializer
    permission_classes = [IsAuthenticated, SystemAdminPermission]
    ordering_fields = ['timestamp', 'response_time_ms', 'status_code']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('user')
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get API usage analytics"""
        queryset = self.get_queryset()
        
        # Date range filter
        hours = int(request.query_params.get('hours', 24))
        start_time = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(timestamp__gte=start_time)
        
        analytics = {
            'total_requests': queryset.count(),
            'unique_users': queryset.values('user').distinct().count(),
            'avg_response_time': queryset.aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0,
            'error_rate': self.calculate_error_rate(queryset),
            'requests_by_endpoint': list(queryset.values('endpoint').annotate(
                count=Count('id'),
                avg_response_time=Avg('response_time_ms')
            ).order_by('-count')[:10]),
            'hourly_distribution': list(queryset.annotate(
                hour=TruncHour('timestamp')
            ).values('hour').annotate(
                count=Count('id'),
                avg_response_time=Avg('response_time_ms')
            ).order_by('hour')),
        }
        
        return Response(analytics)
    
    def calculate_error_rate(self, queryset):
        """Calculate API error rate"""
        total_requests = queryset.count()
        error_requests = queryset.filter(status_code__gte=400).count()
        
        if total_requests > 0:
            return round((error_requests / total_requests) * 100, 2)
        return 0


class SyncLogViewSet(CRMBaseViewSet):
    """Sync Log API viewset"""
    
    queryset = SyncLog.objects.all()
    serializer_class = SyncLogSerializer
    permission_classes = [IsAuthenticated, SystemAdminPermission]
    ordering_fields = ['sync_started_at', 'sync_completed_at', 'status']
    ordering = ['-sync_started_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('integration')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get sync summary"""
        queryset = self.get_queryset()
        
        # Recent syncs (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_syncs = queryset.filter(sync_started_at__gte=week_ago)
        
        summary = {
            'total_syncs': recent_syncs.count(),
            'successful_syncs': recent_syncs.filter(status='SUCCESS').count(),
            'failed_syncs': recent_syncs.filter(status='FAILED').count(),
            'avg_sync_duration': recent_syncs.filter(
                sync_completed_at__isnull=False
            ).aggregate(
                avg_duration=Avg(
                    F('sync_completed_at') - F('sync_started_at')
                )
            )['avg_duration'],
            'syncs_by_integration': list(recent_syncs.values(
                'integration__name'
            ).annotate(
                count=Count('id'),
                success_rate=Count('id', filter=Q(status='SUCCESS')) * 100.0 / Count('id')
            ).order_by('-count')),
        }
        
        return Response(summary)