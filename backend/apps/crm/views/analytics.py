# ============================================================================
# backend/apps/crm/views/analytics.py - Analytics & Reporting Views  
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, View
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField, DateField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, Extract
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json
from datetime import datetime, timedelta
import calendar

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import Report, Dashboard, Forecast, PerformanceMetric
from ..serializers import ReportSerializer, DashboardSerializer, ForecastSerializer, PerformanceMetricSerializer
from ..permissions import AnalyticsPermission
from ..services import AnalyticsService, ReportService


class AnalyticsDashboardView(CRMBaseMixin, View):
    """Main analytics dashboard with comprehensive metrics"""
    
    template_name = 'crm/analytics/dashboard.html'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(context)
            
        return render(request, self.template_name, context)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        user = self.request.user
        
        # Date range from request or default to last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        date_range = self.request.GET.get('date_range')
        if date_range:
            if date_range == '7d':
                start_date = end_date - timedelta(days=7)
            elif date_range == '30d':
                start_date = end_date - timedelta(days=30)
            elif date_range == '90d':
                start_date = end_date - timedelta(days=90)
            elif date_range == '1y':
                start_date = end_date - timedelta(days=365)
        
        context = {
            'overview_metrics': self.get_overview_metrics(tenant, start_date, end_date),
            'sales_analytics': self.get_sales_analytics(tenant, start_date, end_date),
            'pipeline_analytics': self.get_pipeline_analytics(tenant),
            'activity_analytics': self.get_activity_analytics(tenant, start_date, end_date),
            'team_performance': self.get_team_performance(tenant, start_date, end_date),
            'customer_analytics': self.get_customer_analytics(tenant, start_date, end_date),
            'product_performance': self.get_product_performance(tenant, start_date, end_date),
            'trend_analysis': self.get_trend_analysis(tenant, start_date, end_date),
            'forecasting_data': self.get_forecasting_data(tenant),
            'date_range': {
                'start_date': start_date,
                'end_date': end_date,
                'selected': date_range or '30d'
            }
        }
        
        return context
    
    def get_overview_metrics(self, tenant, start_date, end_date):
        """Get high-level overview metrics"""
        # Current period metrics
        current_metrics = {
            'total_revenue': tenant.opportunities.filter(
                is_won=True,
                closed_date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            
            'total_deals': tenant.opportunities.filter(
                closed_date__range=[start_date, end_date]
            ).count(),
            
            'won_deals': tenant.opportunities.filter(
                is_won=True,
                closed_date__range=[start_date, end_date]
            ).count(),
            
            'new_leads': tenant.leads.filter(
                created_at__date__range=[start_date, end_date]
            ).count(),
            
            'new_accounts': tenant.accounts.filter(
                created_at__date__range=[start_date, end_date]
            ).count(),
            
            'activities_completed': tenant.activities.filter(
                status='COMPLETED',
                updated_at__date__range=[start_date, end_date]
            ).count(),
        }
        
        # Previous period for comparison
        period_length = (end_date - start_date).days
        previous_start = start_date - timedelta(days=period_length)
        previous_end = start_date
        
        previous_metrics = {
            'previous_revenue': tenant.opportunities.filter(
                is_won=True,
                closed_date__range=[previous_start, previous_end]
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            
            'previous_deals': tenant.opportunities.filter(
                closed_date__range=[previous_start, previous_end]
            ).count(),
            
            'previous_won_deals': tenant.opportunities.filter(
                is_won=True,
                closed_date__range=[previous_start, previous_end]
            ).count(),
            
            'previous_leads': tenant.leads.filter(
                created_at__date__range=[previous_start, previous_end]
            ).count(),
        }
        
        # Calculate growth rates
        def calculate_growth(current, previous):
            if previous > 0:
                return round(((current - previous) / previous) * 100, 1)
            return 0 if current == 0 else 100
        
        growth_rates = {
            'revenue_growth': calculate_growth(current_metrics['total_revenue'], previous_metrics['previous_revenue']),
            'deals_growth': calculate_growth(current_metrics['total_deals'], previous_metrics['previous_deals']),
            'leads_growth': calculate_growth(current_metrics['new_leads'], previous_metrics['previous_leads']),
        }
        
        # Win rate
        win_rate = (current_metrics['won_deals'] / current_metrics['total_deals'] * 100) if current_metrics['total_deals'] > 0 else 0
        
        return {
            **current_metrics,
            **growth_rates,
            'win_rate': round(win_rate, 1),
            'avg_deal_size': current_metrics['total_revenue'] / current_metrics['won_deals'] if current_metrics['won_deals'] > 0 else 0,
        }
    
    def get_sales_analytics(self, tenant, start_date, end_date):
        """Get detailed sales analytics"""
        # Monthly sales trend
        monthly_sales = tenant.opportunities.filter(
            is_won=True,
            closed_date__gte=start_date - timedelta(days=365)  # Get full year for trend
        ).annotate(
            month=TruncMonth('closed_date')
        ).values('month').annotate(
            revenue=Sum('amount'),
            deal_count=Count('id')
        ).order_by('month')
        
        # Sales by stage
        stage_performance = tenant.opportunities.filter(
            created_at__date__range=[start_date, end_date]
        ).values('stage__name').annotate(
            count=Count('id'),
            value=Sum('amount'),
            won_count=Count('id', filter=Q(is_won=True))
        ).order_by('-value')
        
        # Sales by source
        source_performance = tenant.opportunities.filter(
            is_won=True,
            closed_date__range=[start_date, end_date]
        ).values('lead__source__name').annotate(
            revenue=Sum('amount'),
            deal_count=Count('id')
        ).order_by('-revenue')
        
        return {
            'monthly_trend': list(monthly_sales),
            'stage_performance': list(stage_performance),
            'source_performance': list(source_performance),
            'sales_velocity': self.calculate_sales_velocity(tenant, start_date, end_date),
        }
    
    def get_pipeline_analytics(self, tenant):
        """Get pipeline analytics"""
        # Current pipeline by stage
        pipeline_stages = tenant.opportunities.filter(
            is_closed=False
        ).values('stage__name', 'stage__probability').annotate(
            count=Count('id'),
            value=Sum('amount'),
            avg_age=Avg(timezone.now().date() - F('created_at__date'))
        ).order_by('stage__sort_order')
        
        # Pipeline velocity
        pipeline_velocity = self.calculate_pipeline_velocity(tenant)
        
        # Stalled deals
        stalled_deals = tenant.opportunities.filter(
            is_closed=False,
            updated_at__lt=timezone.now() - timedelta(days=30)
        ).count()
        
        return {
            'pipeline_stages': list(pipeline_stages),
            'pipeline_velocity': pipeline_velocity,
            'stalled_deals': stalled_deals,
            'total_pipeline_value': tenant.opportunities.filter(is_closed=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'weighted_pipeline': self.calculate_weighted_pipeline(tenant),
        }
    
    def get_activity_analytics(self, tenant, start_date, end_date):
        """Get activity analytics"""
        # Activities by type
        activity_types = tenant.activities.filter(
            created_at__date__range=[start_date, end_date]
        ).values('activity_type__name').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED'))
        ).order_by('-count')
        
        # Daily activity volume
        daily_activities = tenant.activities.filter(
            created_at__date__range=[start_date, end_date]
        ).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED'))
        ).order_by('day')
        
        return {
            'activity_types': list(activity_types),
            'daily_volume': list(daily_activities),
            'completion_rate': self.calculate_activity_completion_rate(tenant, start_date, end_date),
            'overdue_activities': tenant.activities.filter(
                status='PLANNED',
                start_datetime__lt=timezone.now()
            ).count(),
        }
    
    def get_team_performance(self, tenant, start_date, end_date):
        """Get team performance metrics"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get active users with CRM activity
        active_users = User.objects.filter(
            tenant_memberships__tenant=tenant,
            tenant_memberships__is_active=True
        )
        
        team_metrics = []
        for user in active_users:
            user_metrics = {
                'user_id': user.id,
                'name': user.get_full_name(),
                'email': user.email,
                'leads': tenant.leads.filter(
                    owner=user,
                    created_at__date__range=[start_date, end_date]
                ).count(),
                'opportunities': tenant.opportunities.filter(
                    owner=user,
                    created_at__date__range=[start_date, end_date]
                ).count(),
                'won_deals': tenant.opportunities.filter(
                    owner=user,
                    is_won=True,
                    closed_date__range=[start_date, end_date]
                ).count(),
                'revenue': tenant.opportunities.filter(
                    owner=user,
                    is_won=True,
                    closed_date__range=[start_date, end_date]
                ).aggregate(Sum('amount'))['amount__sum'] or 0,
                'activities': tenant.activities.filter(
                    assigned_to=user,
                    created_at__date__range=[start_date, end_date]
                ).count(),
            }
            
            # Calculate conversion rate
            if user_metrics['leads'] > 0:
                converted_leads = tenant.leads.filter(
                    owner=user,
                    converted_opportunity__isnull=False,
                    created_at__date__range=[start_date, end_date]
                ).count()
                user_metrics['conversion_rate'] = (converted_leads / user_metrics['leads']) * 100
            else:
                user_metrics['conversion_rate'] = 0
            
            team_metrics.append(user_metrics)
        
        # Sort by revenue
        team_metrics.sort(key=lambda x: x['revenue'], reverse=True)
        
        return team_metrics
    
    def get_customer_analytics(self, tenant, start_date, end_date):
        """Get customer analytics"""
        # Customer acquisition
        new_customers = tenant.accounts.filter(
            created_at__date__range=[start_date, end_date]
        ).count()
        
        # Customer value analysis
        customer_values = tenant.accounts.annotate(
            total_value=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(total_value__gt=0).order_by('-total_value')
        
        # Industry analysis
        industry_performance = tenant.accounts.filter(
            industry__isnull=False
        ).values('industry__name').annotate(
            account_count=Count('id'),
            revenue=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).order_by('-revenue')
        
        return {
            'new_customers': new_customers,
            'top_customers': customer_values[:10],
            'industry_performance': list(industry_performance),
            'customer_lifetime_value': self.calculate_customer_lifetime_value(tenant),
        }
    
    def get_product_performance(self, tenant, start_date, end_date):
        """Get product performance analytics"""
        # Top products by revenue
        top_products = tenant.products.annotate(
            revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        opportunity_products__opportunity__closed_date__range=[start_date, end_date],
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(revenue__gt=0).order_by('-revenue')[:10]
        
        # Product category performance
        category_performance = tenant.product_categories.annotate(
            revenue=Sum(
                Case(
                    When(
                        products__opportunity_products__opportunity__is_won=True,
                        products__opportunity_products__opportunity__closed_date__range=[start_date, end_date],
                        then=F('products__opportunity_products__price') * F('products__opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(revenue__gt=0).order_by('-revenue')
        
        return {
            'top_products': top_products,
            'category_performance': list(category_performance),
            'product_mix_analysis': self.get_product_mix_analysis(tenant, start_date, end_date),
        }
    
    def get_trend_analysis(self, tenant, start_date, end_date):
        """Get trend analysis data"""
        # Weekly trends
        weekly_trends = []
        current_week = start_date
        
        while current_week <= end_date:
            week_end = min(current_week + timedelta(days=6), end_date)
            
            week_data = {
                'week_start': current_week,
                'week_end': week_end,
                'leads': tenant.leads.filter(
                    created_at__date__range=[current_week, week_end]
                ).count(),
                'opportunities': tenant.opportunities.filter(
                    created_at__date__range=[current_week, week_end]
                ).count(),
                'revenue': tenant.opportunities.filter(
                    is_won=True,
                    closed_date__range=[current_week, week_end]
                ).aggregate(Sum('amount'))['amount__sum'] or 0,
                'activities': tenant.activities.filter(
                    created_at__date__range=[current_week, week_end]
                ).count(),
            }
            
            weekly_trends.append(week_data)
            current_week = week_end + timedelta(days=1)
        
        return {
            'weekly_trends': weekly_trends,
            'growth_trajectory': self.calculate_growth_trajectory(weekly_trends),
            'seasonality_analysis': self.get_seasonality_analysis(tenant),
        }
    
    def get_forecasting_data(self, tenant):
        """Get forecasting data"""
        service = AnalyticsService()
        
        return {
            'revenue_forecast': service.forecast_revenue(tenant),
            'pipeline_forecast': service.forecast_pipeline_conversion(tenant),
            'quota_achievement': service.calculate_quota_achievement(tenant),
        }
    
    def calculate_sales_velocity(self, tenant, start_date, end_date):
        """Calculate average sales velocity"""
        closed_deals = tenant.opportunities.filter(
            is_closed=True,
            closed_date__range=[start_date, end_date]
        ).annotate(
            cycle_time=F('closed_date') - F('created_at__date')
        )
        
        if closed_deals.exists():
            avg_cycle = closed_deals.aggregate(Avg('cycle_time'))['cycle_time__avg']
            return avg_cycle.days if avg_cycle else 0
        
        return 0
    
    def calculate_pipeline_velocity(self, tenant):
        """Calculate pipeline velocity metrics"""
        opportunities = tenant.opportunities.filter(is_closed=False)
        
        if not opportunities.exists():
            return {'avg_age': 0, 'velocity_score': 0}
        
        avg_age = opportunities.aggregate(
            avg_age=Avg(timezone.now().date() - F('created_at__date'))
        )['avg_age']
        
        # Simple velocity score based on age and probability
        velocity_score = opportunities.aggregate(
            score=Avg(F('stage__probability') / (F('created_at__date') - timezone.now().date() + 1))
        )['score'] or 0
        
        return {
            'avg_age': avg_age.days if avg_age else 0,
            'velocity_score': float(velocity_score) if velocity_score else 0
        }
    
    def calculate_weighted_pipeline(self, tenant):
        """Calculate weighted pipeline value"""
        return tenant.opportunities.filter(
            is_closed=False
        ).annotate(
            weighted_value=F('amount') * F('stage__probability') / 100
        ).aggregate(Sum('weighted_value'))['weighted_value__sum'] or 0
    
    def calculate_activity_completion_rate(self, tenant, start_date, end_date):
        """Calculate activity completion rate"""
        total_activities = tenant.activities.filter(
            created_at__date__range=[start_date, end_date]
        ).count()
        
        completed_activities = tenant.activities.filter(
            created_at__date__range=[start_date, end_date],
            status='COMPLETED'
        ).count()
        
        if total_activities > 0:
            return round((completed_activities / total_activities) * 100, 1)
        
        return 0
    
    def calculate_customer_lifetime_value(self, tenant):
        """Calculate average customer lifetime value"""
        customer_values = tenant.accounts.annotate(
            total_value=Sum(
                Case(
                    When(opportunities__is_won=True, then='opportunities__amount'),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(total_value__gt=0)
        
        if customer_values.exists():
            return customer_values.aggregate(Avg('total_value'))['total_value__avg'] or 0
        
        return 0
    
    def get_product_mix_analysis(self, tenant, start_date, end_date):
        """Get product mix analysis"""
        # Revenue by product for period
        product_revenue = tenant.products.annotate(
            period_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        opportunity_products__opportunity__closed_date__range=[start_date, end_date],
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(period_revenue__gt=0)
        
        total_revenue = product_revenue.aggregate(Sum('period_revenue'))['period_revenue__sum'] or 0
        
        mix_data = []
        for product in product_revenue:
            percentage = (product.period_revenue / total_revenue * 100) if total_revenue > 0 else 0
            mix_data.append({
                'product_name': product.name,
                'revenue': float(product.period_revenue),
                'percentage': round(percentage, 1)
            })
        
        return sorted(mix_data, key=lambda x: x['revenue'], reverse=True)
    
    def calculate_growth_trajectory(self, weekly_trends):
        """Calculate growth trajectory from weekly trends"""
        if len(weekly_trends) < 2:
            return 0
        
        first_week = weekly_trends[0]['revenue']
        last_week = weekly_trends[-1]['revenue']
        
        if first_week > 0:
            return round(((last_week - first_week) / first_week) * 100, 1)
        
        return 0
    
    def get_seasonality_analysis(self, tenant):
        """Get seasonality analysis"""
        # Monthly revenue for past 2 years
        monthly_data = tenant.opportunities.filter(
            is_won=True,
            closed_date__gte=timezone.now().date() - timedelta(days=730)
        ).annotate(
            month=Extract('closed_date__month')
        ).values('month').annotate(
            avg_revenue=Avg('amount'),
            total_revenue=Sum('amount'),
            deal_count=Count('id')
        ).order_by('month')
        
        season_name = calendar.month_name[data['month']]
            seasonality[month_name] = {
                'avg_revenue': float(data['avg_revenue'] or 0),
                'total_revenue': float(data['total_revenue'] or 0),
                'deal_count': data['deal_count']
            }
        
        return seasonality


class ReportListView(CRMBaseMixin, ListView):
    """Report list view with filtering and management"""
    
    model = Report
    template_name = 'crm/analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations
        queryset = queryset.annotate(
            execution_count=Count('executions'),
            last_executed=F('executions__executed_at')
        ).select_related('created_by').prefetch_related('shared_with')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        # Filter by ownership/sharing
        ownership = self.request.GET.get('ownership', 'all')
        if ownership == 'my':
            queryset = queryset.filter(created_by=self.request.user)
        elif ownership == 'shared':
            queryset = queryset.filter(
                Q(is_public=True) | Q(shared_with=self.request.user)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        reports = self.get_queryset()
        context.update({
            'total_reports': reports.count(),
            'my_reports': reports.filter(created_by=self.request.user).count(),
            'public_reports': reports.filter(is_public=True).count(),
            'report_types': Report.REPORT_TYPES,
            'report_categories': Report.REPORT_CATEGORIES,
            'recent_reports': reports[:5],
        })
        
        return context


class ReportDetailView(CRMBaseMixin, DetailView):
    """Report detail view with execution and results"""
    
    model = Report
    template_name = 'crm/analytics/report_detail.html'
    context_object_name = 'report'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('created_by').prefetch_related(
                'shared_with', 'executions'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        
        # Execute report if requested
        if self.request.GET.get('execute'):
            report_data = self.execute_report(report)
            context['report_data'] = report_data
            context['executed'] = True
        
        context.update({
            'execution_history': report.executions.order_by('-executed_at')[:10],
            'can_edit': self.can_edit_report(report),
            'can_execute': self.can_execute_report(report),
            'sharing_info': self.get_sharing_info(report),
        })
        
        return context
    
    def execute_report(self, report):
        """Execute report and return results"""
        service = ReportService()
        
        try:
            # Parse report configuration
            config = json.loads(report.configuration) if report.configuration else {}
            
            # Execute based on report type
            if report.report_type == 'SALES':
                results = service.execute_sales_report(report, config, self.request.tenant)
            elif report.report_type == 'PIPELINE':
                results = service.execute_pipeline_report(report, config, self.request.tenant)
            elif report.report_type == 'ACTIVITY':
                results = service.execute_activity_report(report, config, self.request.tenant)
            elif report.report_type == 'CUSTOMER':
                results = service.execute_customer_report(report, config, self.request.tenant)
            else:
                results = {'error': 'Unsupported report type'}
            
            # Log execution
            from ..models import ReportExecution
            ReportExecution.objects.create(
                report=report,
                executed_by=self.request.user,
                execution_time=timezone.now(),
                tenant=self.request.tenant
            )
            
            return results
            
        except Exception as e:
            return {'error': str(e)}
    
    def can_edit_report(self, report):
        """Check if user can edit report"""
        return (
            report.created_by == self.request.user or
            self.request.user.has_perm('crm.change_report')
        )
    
    def can_execute_report(self, report):
        """Check if user can execute report"""
        return (
            report.is_public or
            report.created_by == self.request.user or
            report.shared_with.filter(id=self.request.user.id).exists() or
            self.request.user.has_perm('crm.execute_report')
        )
    
    def get_sharing_info(self, report):
        """Get report sharing information"""
        return {
            'is_public': report.is_public,
            'shared_with_count': report.shared_with.count(),
            'shared_users': report.shared_with.all()[:5],  # Show first 5
        }


class ReportBuilderView(CRMBaseMixin, View):
    """Interactive report builder"""
    
    template_name = 'crm/analytics/report_builder.html'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle report creation/update"""
        report_data = json.loads(request.POST.get('report_data', '{}'))
        
        try:
            with transaction.atomic():
                # Create or update report
                if request.POST.get('report_id'):
                    # Update existing report
                    report = get_object_or_404(
                        Report.objects.filter(tenant=request.tenant),
                        id=request.POST['report_id']
                    )
                    
                    # Check permissions
                    if report.created_by != request.user and not request.user.has_perm('crm.change_report'):
                        return JsonResponse({'error': 'Permission denied'}, status=403)
                    
                    report.name = report_data.get('name', report.name)
                    report.description = report_data.get('description', report.description)
                    report.configuration = json.dumps(report_data.get('configuration', {}))
                    report.updated_by = request.user
                    report.save()
                    
                    message = 'Report updated successfully'
                
                else:
                    # Create new report
                    report = Report.objects.create(
                        name=report_data.get('name', 'Untitled Report'),
                        description=report_data.get('description', ''),
                        report_type=report_data.get('type', 'CUSTOM'),
                        category=report_data.get('category', 'GENERAL'),
                        configuration=json.dumps(report_data.get('configuration', {})),
                        tenant=request.tenant,
                        created_by=request.user
                    )
                    
                    message = 'Report created successfully'
                
                # Handle sharing
                shared_user_ids = report_data.get('shared_with', [])
                if shared_user_ids:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    shared_users = User.objects.filter(id__in=shared_user_ids)
                    report.shared_with.set(shared_users)
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'report_id': report.id,
                    'redirect_url': reverse_lazy('crm:report-detail', kwargs={'pk': report.id})
                })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    def get_context_data(self, **kwargs):
        context = {
            'data_sources': self.get_available_data_sources(),
            'chart_types': self.get_available_chart_types(),
            'filter_options': self.get_filter_options(),
            'aggregation_functions': self.get_aggregation_functions(),
        }
        
        # If editing existing report
        report_id = self.request.GET.get('report_id')
        if report_id:
            try:
                report = Report.objects.get(id=report_id, tenant=self.request.tenant)
                context['existing_report'] = report
                context['report_config'] = json.loads(report.configuration) if report.configuration else {}
            except Report.DoesNotExist:
                pass
        
        return context
    
    def get_available_data_sources(self):
        """Get available data sources for reports"""
        return [
            {'id': 'leads', 'name': 'Leads', 'fields': self.get_model_fields('Lead')},
            {'id': 'accounts', 'name': 'Accounts', 'fields': self.get_model_fields('Account')},
            {'id': 'opportunities', 'name': 'Opportunities', 'fields': self.get_model_fields('Opportunity')},
            {'id': 'activities', 'name': 'Activities', 'fields': self.get_model_fields('Activity')},
            {'id': 'campaigns', 'name': 'Campaigns', 'fields': self.get_model_fields('Campaign')},
            {'id': 'products', 'name': 'Products', 'fields': self.get_model_fields('Product')},
        ]
    
    def get_model_fields(self, model_name):
        """Get available fields for a model"""
        from .. import models
        
        model_class = getattr(models, model_name)
        fields = []
        
        for field in model_class._meta.fields:
            if not field.name.endswith('_id') and field.name not in ['tenant', 'created_by', 'updated_by']:
                field_info = {
                    'name': field.name,
                    'verbose_name': field.verbose_name,
                    'type': field.__class__.__name__.lower(),
                    'is_relation': field.many_to_one or field.one_to_one,
                }
                fields.append(field_info)
        
        return fields
    
    def get_available_chart_types(self):
        """Get available chart types"""
        return [
            {'id': 'bar', 'name': 'Bar Chart', 'icon': 'bar-chart'},
            {'id': 'line', 'name': 'Line Chart', 'icon': 'trending-up'},
            {'id': 'pie', 'name': 'Pie Chart', 'icon': 'pie-chart'},
            {'id': 'area', 'name': 'Area Chart', 'icon': 'activity'},
            {'id': 'scatter', 'name': 'Scatter Plot', 'icon': 'circle'},
            {'id': 'table', 'name': 'Data Table', 'icon': 'grid'},
            {'id': 'metric', 'name': 'Single Metric', 'icon': 'hash'},
        ]
    
    def get_filter_options(self):
        """Get available filter options"""
        return [
            {'id': 'date_range', 'name': 'Date Range', 'type': 'daterange'},
            {'id': 'user', 'name': 'User/Owner', 'type': 'select'},
            {'id': 'status', 'name': 'Status', 'type': 'select'},
            {'id': 'stage', 'name': 'Stage', 'type': 'select'},
            {'id': 'source', 'name': 'Source', 'type': 'select'},
            {'id': 'industry', 'name': 'Industry', 'type': 'select'},
            {'id': 'amount', 'name': 'Amount Range', 'type': 'numberrange'},
        ]
    
    def get_aggregation_functions(self):
        """Get available aggregation functions"""
        return [
            {'id': 'count', 'name': 'Count', 'description': 'Count of records'},
            {'id': 'sum', 'name': 'Sum', 'description': 'Sum of values'},
            {'id': 'avg', 'name': 'Average', 'description': 'Average value'},
            {'id': 'min', 'name': 'Minimum', 'description': 'Minimum value'},
            {'id': 'max', 'name': 'Maximum', 'description': 'Maximum value'},
            {'id': 'distinct', 'name': 'Distinct Count', 'description': 'Count of unique values'},
        ]


class DashboardListView(CRMBaseMixin, ListView):
    """Dashboard list view"""
    
    model = Dashboard
    template_name = 'crm/analytics/dashboard_list.html'
    context_object_name = 'dashboards'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        ownership = self.request.GET.get('ownership', 'all')
        if ownership == 'my':
            queryset = queryset.filter(created_by=self.request.user)
        elif ownership == 'shared':
            queryset = queryset.filter(
                Q(is_public=True) | Q(shared_with=self.request.user)
            )
        
        return queryset.select_related('created_by').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        dashboards = self.get_queryset()
        context.update({
            'total_dashboards': dashboards.count(),
            'my_dashboards': dashboards.filter(created_by=self.request.user).count(),
            'public_dashboards': dashboards.filter(is_public=True).count(),
        })
        
        return context


class DashboardDetailView(CRMBaseMixin, DetailView):
    """Dashboard detail view with widgets"""
    
    model = Dashboard
    template_name = 'crm/analytics/dashboard_detail.html'
    context_object_name = 'dashboard'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('created_by').prefetch_related('shared_with'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.object
        
        # Load dashboard configuration
        config = json.loads(dashboard.configuration) if dashboard.configuration else {}
        
        context.update({
            'dashboard_config': config,
            'widgets': self.get_dashboard_widgets(dashboard, config),
            'can_edit': self.can_edit_dashboard(dashboard),
            'sharing_info': self.get_sharing_info(dashboard),
        })
        
        return context
    
    def get_dashboard_widgets(self, dashboard, config):
        """Get dashboard widgets with data"""
        widgets = config.get('widgets', [])
        service = AnalyticsService()
        
        widget_data = []
        for widget in widgets:
            try:
                data = service.get_widget_data(widget, self.request.tenant)
                widget_data.append({
                    'config': widget,
                    'data': data
                })
            except Exception as e:
                widget_data.append({
                    'config': widget,
                    'error': str(e)
                })
        
        return widget_data
    
    def can_edit_dashboard(self, dashboard):
        """Check if user can edit dashboard"""
        return (
            dashboard.created_by == self.request.user or
            self.request.user.has_perm('crm.change_dashboard')
        )
    
    def get_sharing_info(self, dashboard):
        """Get dashboard sharing information"""
        return {
            'is_public': dashboard.is_public,
            'shared_with_count': dashboard.shared_with.count(),
            'shared_users': dashboard.shared_with.all()[:5],
        }


class ForecastingView(CRMBaseMixin, View):
    """Sales forecasting view"""
    
    template_name = 'crm/analytics/forecasting.html'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        service = AnalyticsService()
        
        # Forecasting period
        forecast_months = int(self.request.GET.get('months', 6))
        
        context = {
            'revenue_forecast': service.generate_revenue_forecast(tenant, forecast_months),
            'pipeline_forecast': service.generate_pipeline_forecast(tenant),
            'quota_tracking': service.get_quota_tracking(tenant),
            'forecast_accuracy': service.calculate_forecast_accuracy(tenant),
            'team_forecasts': service.get_team_forecasts(tenant, forecast_months),
            'product_forecasts': service.get_product_forecasts(tenant, forecast_months),
            'forecast_scenarios': service.get_forecast_scenarios(tenant),
        }
        
        return context


# Continue with ViewSets for API endpoints...

class ReportViewSet(CRMBaseViewSet):
    """Report API viewset"""
    
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute report"""
        report = self.get_object()
        service = ReportService()
        
        try:
            config = json.loads(report.configuration) if report.configuration else {}
            results = service.execute_report(report, config, request.tenant)
            
            # Log execution
            from ..models import ReportExecution
            ReportExecution.objects.create(
                report=report,
                executed_by=request.user,
                execution_time=timezone.now(),
                tenant=request.tenant
            )
            
            return Response({
                'success': True,
                'results': results,
                'executed_at': timezone.now()
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share report with users"""
        report = self.get_object()
        user_ids = request.data.get('user_ids', [])
        is_public = request.data.get('is_public', False)
        
        try:
            with transaction.atomic():
                # Update public status
                report.is_public = is_public
                report.save()
                
                # Share with specific users
                if user_ids:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    users = User.objects.filter(id__in=user_ids)
                    report.shared_with.add(*users)
                
                return Response({
                    'success': True,
                    'message': 'Report sharing updated successfully'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DashboardViewSet(CRMBaseViewSet):
    """Dashboard API viewset"""
    
    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['get'])
    def widgets(self, request, pk=None):
        """Get dashboard widget data"""
        dashboard = self.get_object()
        
        try:
            config = json.loads(dashboard.configuration) if dashboard.configuration else {}
            widgets = config.get('widgets', [])
            
            service = AnalyticsService()
            widget_data = []
            
            for widget in widgets:
                data = service.get_widget_data(widget, request.tenant)
                widget_data.append({
                    'widget_id': widget.get('id'),
                    'data': data
                })
            
            return Response(widget_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ForecastViewSet(CRMBaseViewSet):
    """Forecast API viewset"""
    
    queryset = Forecast.objects.all()
    serializer_class = ForecastSerializer
    ordering_fields = ['forecast_date', 'created_at']
    ordering = ['-forecast_date']
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate new forecast"""
        forecast_type = request.data.get('type', 'REVENUE')
        period_months = int(request.data.get('months', 6))
        
        try:
            service = AnalyticsService()
            
            if forecast_type == 'REVENUE':
                forecast_data = service.generate_revenue_forecast(request.tenant, period_months)
            elif forecast_type == 'PIPELINE':
                forecast_data = service.generate_pipeline_forecast(request.tenant)
            else:
                return Response(
                    {'error': 'Invalid forecast type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save forecast
            forecast = Forecast.objects.create(
                name=f'{forecast_type.title()} Forecast - {timezone.now().date()}',
                forecast_type=forecast_type,
                forecast_data=json.dumps(forecast_data),
                forecast_date=timezone.now().date(),
                accuracy_score=0.0,  # Will be updated as actual data comes in
                tenant=request.tenant,
                created_by=request.user
            )
            
            serializer = self.get_serializer(forecast)
            return Response({
                'success': True,
                'forecast': serializer.data,
                'message': 'Forecast generated successfully'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PerformanceMetricViewSet(CRMBaseViewSet):
    """Performance Metric API viewset"""
    
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    ordering_fields = ['metric_date', 'created_at']
    ordering = ['-metric_date']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get performance metrics summary"""
        # Date range
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)
        
        metrics = self.get_queryset().filter(
            metric_date__gte=start_date
        ).values('metric_name').annotate(
            avg_value=Avg('metric_value'),
            latest_value=F('metric_value'),
            trend=Case(
                When(metric_value__gt=Avg('metric_value'), then='up'),
                When(metric_value__lt=Avg('metric_value'), then='down'),
                default='stable'
            )
        )
        
        return Response(list(metrics))