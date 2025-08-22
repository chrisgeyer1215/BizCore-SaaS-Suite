# ============================================================================
# backend/apps/crm/views/base.py - Enhanced Base Views and Mixins
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Count, Sum, Avg, F
from django.core.cache import cache
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.views import TenantMixin, PaginationMixin
from apps.core.permissions import TenantPermission
from ..models import CRMConfiguration
from ..serializers import CRMConfigurationSerializer
from ..permissions import CRMPermission


class CRMBaseMixin(TenantMixin, LoginRequiredMixin):
    """Enhanced base mixin for all CRM views"""
    
    def get_crm_config(self):
        """Get CRM configuration for current tenant"""
        cache_key = f"crm_config_{self.request.tenant.id}"
        config = cache.get(cache_key)
        
        if not config:
            config = CRMConfiguration.objects.filter(tenant=self.request.tenant).first()
            if config:
                cache.set(cache_key, config, 300)  # Cache for 5 minutes
        
        return config
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['crm_config'] = self.get_crm_config()
        context['current_user_profile'] = getattr(self.request.user, 'crm_profile', None)
        context['tenant'] = self.request.tenant
        return context
    
    def get_queryset(self):
        """Ensure all queries are tenant-aware"""
        queryset = super().get_queryset()
        if hasattr(queryset.model, 'tenant'):
            queryset = queryset.filter(tenant=self.request.tenant)
        return queryset


class CRMBaseViewSet(viewsets.ModelViewSet):
    """Enhanced base viewset for CRM APIs"""
    
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    
    def get_queryset(self):
        """Ensure all queries are tenant-aware"""
        queryset = super().get_queryset()
        if hasattr(self.queryset.model, 'tenant'):
            return queryset.filter(tenant=self.request.tenant)
        return queryset
    
    def perform_create(self, serializer):
        """Add tenant and user info on creation"""
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Add user info on update"""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get model statistics"""
        queryset = self.get_queryset()
        stats = {
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count() if hasattr(queryset.model, 'is_active') else queryset.count(),
            'created_today': queryset.filter(created_at__date=timezone.now().date()).count(),
            'created_this_week': queryset.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count(),
            'created_this_month': queryset.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30)).count(),
        }
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update multiple records"""
        ids = request.data.get('ids', [])
        updates = request.data.get('updates', {})
        
        if not ids or not updates:
            return Response(
                {'error': 'IDs and updates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                queryset = self.get_queryset().filter(id__in=ids)
                updated_count = queryset.update(**updates, updated_by=request.user)
                
                return Response({
                    'success': True,
                    'updated_count': updated_count,
                    'message': f'Successfully updated {updated_count} records'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete multiple records"""
        ids = request.data.get('ids', [])
        
        if not ids:
            return Response(
                {'error': 'IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                queryset = self.get_queryset().filter(id__in=ids)
                deleted_count = queryset.count()
                
                # Soft delete if supported
                if hasattr(queryset.model, 'is_active'):
                    queryset.update(is_active=False, updated_by=request.user)
                else:
                    queryset.delete()
                
                return Response({
                    'success': True,
                    'deleted_count': deleted_count,
                    'message': f'Successfully deleted {deleted_count} records'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CRMConfigurationView(CRMBaseMixin, UpdateView):
    """Enhanced CRM Configuration Management"""
    
    model = CRMConfiguration
    template_name = 'crm/configuration.html'
    fields = [
        'company_name', 'company_logo', 'website', 'industry',
        'lead_auto_assignment', 'lead_assignment_method', 'lead_scoring_enabled',
        'lead_scoring_threshold', 'duplicate_lead_detection',
        'opportunity_auto_number', 'opportunity_probability_tracking',
        'opportunity_forecast_enabled', 'default_opportunity_stage',
        'email_integration_enabled', 'email_tracking_enabled',
        'activity_reminders_enabled', 'default_reminder_minutes',
        'campaign_tracking_enabled', 'ticket_auto_assignment',
        'territory_management_enabled', 'timezone', 'currency',
        'date_format', 'time_format', 'language'
    ]
    
    def get_object(self, queryset=None):
        config, created = CRMConfiguration.objects.get_or_create(
            tenant=self.request.tenant,
            defaults={'company_name': self.request.tenant.name}
        )
        return config
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.updated_by = self.request.user
        
        # Clear cache after update
        cache_key = f"crm_config_{self.request.tenant.id}"
        cache.delete(cache_key)
        
        messages.success(self.request, 'CRM configuration updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('crm:configuration')


class CRMHealthCheckView(CRMBaseMixin, View):
    """Enhanced system health check with detailed metrics"""
    
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        
        # System statistics
        stats = {
            'database': self.get_database_stats(tenant),
            'cache': self.get_cache_stats(),
            'performance': self.get_performance_stats(tenant),
            'recent_activity': self.get_recent_activity(tenant),
        }
        
        # System health indicators
        health = {
            'overall_status': self.calculate_overall_health(stats),
            'database_status': 'healthy' if stats['database']['connection'] else 'error',
            'cache_status': stats['cache']['status'],
            'last_updated': timezone.now().isoformat(),
        }
        
        context = {
            'stats': stats,
            'health': health,
            'recommendations': self.get_recommendations(stats),
        }
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(context)
        
        return render(request, 'crm/health_check.html', context)
    
    def get_database_stats(self, tenant):
        """Get database-related statistics"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return {
                'connection': True,
                'leads_count': tenant.leads.count(),
                'accounts_count': tenant.accounts.count(),
                'opportunities_count': tenant.opportunities.count(),
                'activities_count': tenant.activities.count(),
                'campaigns_count': tenant.campaigns.count(),
                'tickets_count': tenant.tickets.count(),
                'total_records': self.get_total_records_count(tenant),
            }
        except Exception as e:
            return {
                'connection': False,
                'error': str(e)
            }
    
    def get_cache_stats(self):
        """Get cache-related statistics"""
        try:
            cache.set('health_check', 'ok', 60)
            test_value = cache.get('health_check')
            
            return {
                'status': 'healthy' if test_value == 'ok' else 'warning',
                'working': test_value == 'ok',
            }
        except Exception as e:
            return {
                'status': 'error',
                'working': False,
                'error': str(e)
            }
    
    def get_performance_stats(self, tenant):
        """Get performance-related statistics"""
        return {
            'avg_response_time': 150,  # Would be calculated from actual metrics
            'query_efficiency': 95,    # Database query efficiency
            'memory_usage': 60,        # Memory usage percentage
            'cpu_usage': 25,          # CPU usage percentage
        }
    
    def get_recent_activity(self, tenant):
        """Get recent system activity"""
        recent_activities = []
        
        try:
            # Recent leads
            recent_leads = tenant.leads.order_by('-created_at')[:5]
            for lead in recent_leads:
                recent_activities.append({
                    'type': 'lead_created',
                    'description': f'New lead: {lead.full_name}',
                    'timestamp': lead.created_at,
                    'user': lead.created_by.get_full_name() if lead.created_by else 'System'
                })
            
            # Recent opportunities
            recent_opps = tenant.opportunities.order_by('-created_at')[:5]
            for opp in recent_opps:
                recent_activities.append({
                    'type': 'opportunity_created',
                    'description': f'New opportunity: {opp.name}',
                    'timestamp': opp.created_at,
                    'user': opp.created_by.get_full_name() if opp.created_by else 'System'
                })
            
            # Sort by timestamp
            recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            recent_activities = [{'error': str(e)}]
        
        return recent_activities[:10]
    
    def get_total_records_count(self, tenant):
        """Get total number of records across all models"""
        total = 0
        total += tenant.leads.count()
        total += tenant.accounts.count()
        total += tenant.opportunities.count()
        total += tenant.activities.count()
        total += tenant.campaigns.count()
        total += tenant.tickets.count()
        return total
    
    def calculate_overall_health(self, stats):
        """Calculate overall system health score"""
        score = 100
        
        if not stats['database']['connection']:
            score -= 50
        
        if stats['cache']['status'] != 'healthy':
            score -= 20
        
        performance = stats['performance']
        if performance['avg_response_time'] > 500:
            score -= 15
        
        if performance['memory_usage'] > 80:
            score -= 10
        
        if score >= 90:
            return 'excellent'
        elif score >= 70:
            return 'good'
        elif score >= 50:
            return 'warning'
        else:
            return 'critical'
    
    def get_recommendations(self, stats):
        """Get system optimization recommendations"""
        recommendations = []
        
        if stats['performance']['avg_response_time'] > 300:
            recommendations.append({
                'type': 'performance',
                'message': 'Consider optimizing database queries or adding indexes',
                'priority': 'high'
            })
        
        if stats['performance']['memory_usage'] > 80:
            recommendations.append({
                'type': 'memory',
                'message': 'Memory usage is high, consider scaling or optimization',
                'priority': 'medium'
            })
        
        if stats['cache']['status'] != 'healthy':
            recommendations.append({
                'type': 'cache',
                'message': 'Cache system needs attention',
                'priority': 'high'
            })
        
        total_records = stats['database'].get('total_records', 0)
        if total_records > 100000:
            recommendations.append({
                'type': 'data',
                'message': 'Consider data archiving or cleanup strategies',
                'priority': 'low'
            })
        
        return recommendations


class CRMDashboardView(CRMBaseMixin, View):
    """Enhanced CRM Dashboard with comprehensive metrics"""
    
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        user = request.user
        
        # Get dashboard data
        context = {
            'user_stats': self.get_user_stats(tenant, user),
            'company_stats': self.get_company_stats(tenant),
            'performance_metrics': self.get_performance_metrics(tenant, user),
            'recent_activities': self.get_recent_activities(tenant, user),
            'upcoming_tasks': self.get_upcoming_tasks(tenant, user),
            'pipeline_overview': self.get_pipeline_overview(tenant),
            'quick_actions': self.get_quick_actions(user),
            'notifications': self.get_notifications(tenant, user),
        }
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(context)
        
        return render(request, 'crm/dashboard.html', context)
    
    def get_user_stats(self, tenant, user):
        """Get user-specific statistics"""
        today = timezone.now().date()
        this_week = timezone.now() - timezone.timedelta(days=7)
        this_month = timezone.now() - timezone.timedelta(days=30)
        
        return {
            'leads': {
                'total': tenant.leads.filter(owner=user).count(),
                'new_today': tenant.leads.filter(owner=user, created_at__date=today).count(),
                'this_week': tenant.leads.filter(owner=user, created_at__gte=this_week).count(),
            },
            'opportunities': {
                'total': tenant.opportunities.filter(owner=user, is_closed=False).count(),
                'value': tenant.opportunities.filter(owner=user, is_closed=False).aggregate(
                    Sum('amount'))['amount__sum'] or 0,
                'this_month': tenant.opportunities.filter(owner=user, created_at__gte=this_month).count(),
            },
            'activities': {
                'today': tenant.activities.filter(assigned_to=user, start_datetime__date=today).count(),
                'this_week': tenant.activities.filter(assigned_to=user, start_datetime__gte=this_week).count(),
                'overdue': tenant.activities.filter(
                    assigned_to=user,
                    status='PLANNED',
                    start_datetime__lt=timezone.now()
                ).count(),
            },
            'targets': self.get_user_targets(tenant, user),
        }
    
    def get_company_stats(self, tenant):
        """Get company-wide statistics"""
        return {
            'total_pipeline_value': tenant.opportunities.filter(is_closed=False).aggregate(
                Sum('amount'))['amount__sum'] or 0,
            'monthly_revenue': tenant.opportunities.filter(
                is_won=True,
                closed_date__month=timezone.now().month,
                closed_date__year=timezone.now().year
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'conversion_rate': self.calculate_conversion_rate(tenant),
            'active_campaigns': tenant.campaigns.filter(status='ACTIVE').count(),
            'open_tickets': tenant.tickets.filter(status__in=['OPEN', 'IN_PROGRESS']).count(),
        }
    
    def get_performance_metrics(self, tenant, user):
        """Get performance metrics"""
        # User performance
        user_opps_won = tenant.opportunities.filter(
            owner=user,
            is_won=True,
            closed_date__month=timezone.now().month
        )
        
        user_quota = getattr(user.crm_profile, 'sales_quota', 0) if hasattr(user, 'crm_profile') else 0
        user_achievement = user_opps_won.aggregate(Sum('amount'))['amount__sum'] or 0
        
        return {
            'quota_achievement': (user_achievement / user_quota * 100) if user_quota > 0 else 0,
            'deals_won_this_month': user_opps_won.count(),
            'average_deal_size': user_opps_won.aggregate(Avg('amount'))['amount__avg'] or 0,
            'activities_completion_rate': self.calculate_activity_completion_rate(tenant, user),
        }
    
    def get_recent_activities(self, tenant, user):
        """Get recent activities for dashboard"""
        activities = tenant.activities.filter(
            Q(assigned_to=user) | Q(created_by=user)
        ).select_related(
            'activity_type', 'assigned_to'
        ).order_by('-created_at')[:10]
        
        return [{
            'id': activity.id,
            'subject': activity.subject,
            'type': activity.activity_type.name,
            'status': activity.status,
            'assigned_to': activity.assigned_to.get_full_name() if activity.assigned_to else '',
            'created_at': activity.created_at,
            'url': reverse_lazy('crm:activity-detail', kwargs={'pk': activity.id})
        } for activity in activities]
    
    def get_upcoming_tasks(self, tenant, user):
        """Get upcoming tasks and activities"""
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        next_week = timezone.now() + timezone.timedelta(days=7)
        
        upcoming = tenant.activities.filter(
            assigned_to=user,
            status='PLANNED',
            start_datetime__range=[timezone.now(), next_week]
        ).order_by('start_datetime')[:10]
        
        return [{
            'id': task.id,
            'subject': task.subject,
            'type': task.activity_type.name,
            'due_date': task.start_datetime,
            'is_overdue': task.start_datetime < timezone.now(),
            'is_due_today': task.start_datetime.date() == timezone.now().date(),
            'url': reverse_lazy('crm:activity-detail', kwargs={'pk': task.id})
        } for task in upcoming]
    
    def get_pipeline_overview(self, tenant):
        """Get sales pipeline overview"""
        pipelines = tenant.pipelines.filter(is_active=True).prefetch_related('stages')
        
        pipeline_data = []
        for pipeline in pipelines:
            stages_data = []
            for stage in pipeline.stages.all().order_by('sort_order'):
                stage_opps = tenant.opportunities.filter(
                    pipeline=pipeline,
                    stage=stage,
                    is_closed=False
                )
                
                stages_data.append({
                    'name': stage.name,
                    'count': stage_opps.count(),
                    'value': stage_opps.aggregate(Sum('amount'))['amount__sum'] or 0,
                    'probability': stage.probability,
                })
            
            pipeline_data.append({
                'name': pipeline.name,
                'stages': stages_data,
                'total_value': sum(s['value'] for s in stages_data),
                'total_count': sum(s['count'] for s in stages_data),
            })
        
        return pipeline_data
    
    def get_quick_actions(self, user):
        """Get context-aware quick actions"""
        actions = []
        
        if user.has_perm('crm.add_lead'):
            actions.append({
                'title': 'Add Lead',
                'url': reverse_lazy('crm:lead-create'),
                'icon': 'user-plus',
                'color': 'primary'
            })
        
        if user.has_perm('crm.add_opportunity'):
            actions.append({
                'title': 'Add Opportunity',
                'url': reverse_lazy('crm:opportunity-create'),
                'icon': 'target',
                'color': 'success'
            })
        
        if user.has_perm('crm.add_activity'):
            actions.append({
                'title': 'Log Activity',
                'url': reverse_lazy('crm:activity-create'),
                'icon': 'activity',
                'color': 'info'
            })
        
        if user.has_perm('crm.add_account'):
            actions.append({
                'title': 'Add Account',
                'url': reverse_lazy('crm:account-create'),
                'icon': 'building',
                'color': 'warning'
            })
        
        return actions
    
    def get_notifications(self, tenant, user):
        """Get user notifications"""
        notifications = []
        
        # Overdue activities
        overdue_count = tenant.activities.filter(
            assigned_to=user,
            status='PLANNED',
            start_datetime__lt=timezone.now()
        ).count()
        
        if overdue_count > 0:
            notifications.append({
                'type': 'warning',
                'message': f'You have {overdue_count} overdue activities',
                'action_url': reverse_lazy('crm:activity-list') + '?status=overdue',
                'action_text': 'View Activities'
            })
        
        # Opportunities closing soon
        closing_soon = tenant.opportunities.filter(
            owner=user,
            is_closed=False,
            close_date__lte=timezone.now().date() + timezone.timedelta(days=7)
        ).count()
        
        if closing_soon > 0:
            notifications.append({
                'type': 'info',
                'message': f'{closing_soon} opportunities are closing within a week',
                'action_url': reverse_lazy('crm:opportunity-list') + '?closing_soon=true',
                'action_text': 'View Opportunities'
            })
        
        # Unassigned leads
        if user.has_perm('crm.change_lead'):
            unassigned_leads = tenant.leads.filter(owner__isnull=True, status='NEW').count()
            if unassigned_leads > 0:
                notifications.append({
                    'type': 'warning',
                    'message': f'{unassigned_leads} leads need assignment',
                    'action_url': reverse_lazy('crm:lead-list') + '?owner=unassigned',
                    'action_text': 'Assign Leads'
                })
        
        return notifications
    
    def get_user_targets(self, tenant, user):
        """Get user targets and achievements"""
        if not hasattr(user, 'crm_profile'):
            return {}
        
        profile = user.crm_profile
        this_month_revenue = tenant.opportunities.filter(
            owner=user,
            is_won=True,
            closed_date__month=timezone.now().month,
            closed_date__year=timezone.now().year
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return {
            'monthly_quota': profile.sales_quota or 0,
            'monthly_achievement': this_month_revenue,
            'achievement_percentage': (this_month_revenue / profile.sales_quota * 100) if profile.sales_quota else 0,
        }
    
    def calculate_conversion_rate(self, tenant):
        """Calculate lead to opportunity conversion rate"""
        total_leads = tenant.leads.count()
        converted_leads = tenant.leads.filter(converted_opportunity__isnull=False).count()
        
        if total_leads > 0:
            return (converted_leads / total_leads) * 100
        return 0
    
    def calculate_activity_completion_rate(self, tenant, user):
        """Calculate activity completion rate for user"""
        this_month = timezone.now() - timezone.timedelta(days=30)
        total_activities = tenant.activities.filter(
            assigned_to=user,
            created_at__gte=this_month
        ).count()
        
        completed_activities = tenant.activities.filter(
            assigned_to=user,
            status='COMPLETED',
            created_at__gte=this_month
        ).count()
        
        if total_activities > 0:
            return (completed_activities / total_activities) * 100
        return 0


class CRMExportView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Generic export functionality for CRM data"""
    
    permission_required = 'crm.export_data'
    
    def get(self, request, model_name):
        """Export data in various formats"""
        export_format = request.GET.get('format', 'csv')
        
        # Get model and queryset
        model_class = self.get_model_class(model_name)
        if not model_class:
            return JsonResponse({'error': 'Invalid model'}, status=400)
        
        queryset = model_class.objects.filter(tenant=request.tenant)
        
        # Apply filters if provided
        filters = {}
        for key, value in request.GET.items():
            if key.startswith('filter_'):
                field_name = key.replace('filter_', '')
                filters[field_name] = value
        
        if filters:
            queryset = queryset.filter(**filters)
        
        # Export data
        if export_format == 'csv':
            return self.export_csv(queryset, model_name)
        elif export_format == 'excel':
            return self.export_excel(queryset, model_name)
        elif export_format == 'json':
            return self.export_json(queryset, model_name)
        else:
            return JsonResponse({'error': 'Unsupported format'}, status=400)
    
    def get_model_class(self, model_name):
        """Get model class by name"""
        from .. import models
        
        model_mapping = {
            'leads': models.Lead,
            'accounts': models.Account,
            'contacts': models.Contact,
            'opportunities': models.Opportunity,
            'activities': models.Activity,
            'campaigns': models.Campaign,
            'tickets': models.Ticket,
        }
        
        return model_mapping.get(model_name)
    
    def export_csv(self, queryset, model_name):
        """Export data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{model_name}_{timezone.now().date()}.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        if queryset.exists():
            model = queryset.first()
            headers = [field.name for field in model._meta.fields]
            writer.writerow(headers)
            
            # Write data
            for obj in queryset:
                row = []
                for field in model._meta.fields:
                    value = getattr(obj, field.name)
                    if value is None:
                        value = ''
                    elif hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row.append(str(value))
                writer.writerow(row)
        
        return response
    
    def export_excel(self, queryset, model_name):
        """Export data as Excel"""
        try:
            import openpyxl
            from django.http import HttpResponse
            
            workbook = openpyxl.Workbook()
            worksheet = workbook.active
            worksheet.title = model_name.capitalize()
            
            # Write headers
            if queryset.exists():
                model = queryset.first()
                headers = [field.name for field in model._meta.fields]
                worksheet.append(headers)
                
                # Write data
                for obj in queryset:
                    row = []
                    for field in model._meta.fields:
                        value = getattr(obj, field.name)
                        if value is None:
                            value = ''
                        elif hasattr(value, 'strftime'):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        row.append(str(value))
                    worksheet.append(row)
            
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{model_name}_{timezone.now().date()}.xlsx"'
            
            workbook.save(response)
            return response
            
        except ImportError:
            return JsonResponse({'error': 'Excel export not available'}, status=400)
    
    def export_json(self, queryset, model_name):
        """Export data as JSON"""
        from django.core import serializers
        from django.http import JsonResponse
        
        data = serializers.serialize('json', queryset)
        
        response = JsonResponse({'data': data})
        response['Content-Disposition'] = f'attachment; filename="{model_name}_{timezone.now().date()}.json"'
        
        return response