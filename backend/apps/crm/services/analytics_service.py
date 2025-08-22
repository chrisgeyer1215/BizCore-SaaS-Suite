# ============================================================================
# backend/apps/crm/services/analytics_service.py - Analytics & Reporting Service
# ============================================================================

from typing import Dict, List, Any, Optional
from django.db import models, connection
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import datetime, timedelta
import json

from .base import BaseService, CacheableMixin
from ..models import (
    Lead, Account, Opportunity, Campaign, Activity, 
    Report, Dashboard, PerformanceMetric, Forecast
)


class AnalyticsService(BaseService, CacheableMixin):
    """Comprehensive analytics and reporting service"""
    
    def generate_sales_dashboard(self, filters: Dict = None) -> Dict:
        """Generate comprehensive sales dashboard data"""
        cache_key = self.get_cache_key('sales_dashboard', str(filters or {}))
        cached_data = self.get_from_cache(cache_key)
        
        ifd_data
        
        # Apply date filters
        date_filter = self._get_date_filter(filters)
        
        # Key metrics
        metrics = self._calculate_sales_metrics(date_filter)
        
        # Pipeline analysis
        pipeline_data = self._analyze_sales_pipeline(date_filter)
        
        # Performance by team/individual
        performance_data = self._analyze_sales_performance(date_filter)
        
        # Forecasting
        forecast_data = self._generate_sales_forecast(filters)
        
        # Activity trends
        activity_trends = self._analyze_activity_trends(date_filter)
        
        dashboard_data = {
            'generated_at': timezone.now().isoformat(),
            'period': filters.get('period', 'current_month'),
            'key_metrics': metrics,
            'pipeline_analysis': pipeline_data,
            'performance_analysis': performance_data,
            'forecast': forecast_data,
            'activity_trends': activity_trends,
        }
        
        # Cache for 1 hour
        self.set_cache(cache_key, dashboard_data, 3600)
        return dashboard_data
    
    def generate_marketing_dashboard(self, filters: Dict = None) -> Dict:
        """Generate marketing performance dashboard"""
        cache_key = self.get_cache_key('marketing_dashboard', str(filters or {}))
        cached_data = self.get_from_cache(cache_key)
        
         cached_data
        
        date_filter = self._get_date_filter(filters)
        
        # Campaign performance
        campaign_metrics = self._analyze_campaign_performance(date_filter)
        
        # Lead generation metrics
        lead_metrics = self._analyze_lead_generation(date_filter)
        
        # Channel effectiveness
        channel_analysis = self._analyze_marketing_channels(date_filter)
        
        # Conversion funnel
        funnel_data = self._analyze_conversion_funnel(date_filter)
        
        # ROI analysis
        roi_analysis = self._analyze_marketing_roi(date_filter)
        
        dashboard_data = {
            'generated_at': timezone.now().isoformat(),
            'period': filters.get('period', 'current_month'),
            'campaign_performance': campaign_metrics,
            'lead_generation': lead_metrics,
            'channel_analysis': channel_analysis,
            'conversion_funnel': funnel_data,
            'roi_analysis': roi_analysis,
        }
        
        self.set_cache(cache_key, dashboard_data, 3600)
        return dashboard_data
    
    def generate_executive_dashboard(self, filters: Dict = None) -> Dict:
        """Generate high-level executive dashboard"""
        cache_key = self.get_cache_key('executive_dashboard', str(filters or {}))
        cached_data = self.get_from_cache(cache_key)
        date_filter = self._get_date_filter(filters)
        
        # Revenue metrics
        revenue_data = self._analyze_revenue_metrics(date_filter)
        
        # Growth indicators
        growth_data = self._analyze_growth_metrics(date_filter)
        
        # Customer metrics
        customer_data = self._analyze_customer_metrics(date_filter)
        
        # Goal achievement
        goal_data = self._analyze_goal_achievement(date_filter)
        
        # Operational efficiency
        efficiency_data = self._analyze_operational_efficiency(date_filter)
        
        dashboard_data = {
            'generated_at': timezone.now().isoformat(),
            'period': filters.get('period', 'current_quarter'),
            'revenue_metrics': revenue_data,
            'growth_indicators': growth_data,
            'customer_metrics': customer_data,
            'goal_achievement': goal_data,
            'operational_efficiency': efficiency_data,
        }
        
        self.set_cache(cache_key, dashboard_data, 1800)  # Cache for 30 minutes
        return dashboard_data
    
    def generate_custom_report(self, report_config: Dict) -> Dict:
        """Generate custom report based on configuration"""
        report_type = report_config.get('type', 'TABULAR')
        data_source = report_config.get('data_source')
        columns = report_config.get('columns', [])
        filters = report_config.get('filters', {})
        grouping = report_config.get('grouping', [])
        aggregations = report_config.get('aggregations', [])
        
        # Get base queryset
        queryset = self._get_report_queryset(data_source, filters)
        
        if report_type == 'TABULAR':
            return self._generate_tabular_report(queryset, columns, grouping)
        elif report_type == 'SUMMARY':
            return self._generate_summary_report(queryset, aggregations, grouping)
        elif report_type == 'TREND':
            return self._generate_trend_report(queryset, report_config)
        elif report_type == 'COMPARISON':
            return self._generate_comparison_report(queryset, report_config)
        else:
            raise CRMServiceException(f"Unsupported report type: {report_type}")
    
    def calculate_kpi_metrics(self, kpi_config: Dict) -> Dict:
        """Calculate KPI metrics based on configuration"""
        metrics = {}
        
        for kpi in kpi_config.get('kpis', []):
            try:
                metric_value = self._calculate_single_kpi(kpi)
                metrics[kpi['name']] = {
                    'value': metric_value,
                    'target': kpi.get('target'),
                    'achievement_percentage': self._calculate_achievement_percentage(
                        metric_value, kpi.get('target')
                    ),
                    'trend': self._calculate_kpi_trend(kpi),
                    'status': self._determine_kpi_status(metric_value, kpi),
                }
            except Exception as e:
                self.logger.error(f"Error calculating KPI {kpi['name']}: {e}")
                metrics[kpi['name']] = {
                    'value': None,
                    'error': str(e),
                    'status': 'error'
                }
        
        return metrics
    
    def _calculate_sales_metrics(self, date_filter: Dict) -> Dict:
        """Calculate key sales metrics"""
        opportunities = Opportunity.objects.filter(
            tenant=self.tenant,
            **date_filter
        )
        
        # Basic metrics
        total_opportunities = opportunities.count()
        total_pipeline_value = opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        won_opportunities = opportunities.filter(is_won=True)
        total_revenue = won_opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Conversion metrics
        win_rate = (won_opportunities.count() / total_opportunities * 100) if total_opportunities > 0 else 0
        
        # Average metrics
        avg_deal_size = won_opportunities.aggregate(
            avg=models.Avg('amount')
        )['avg'] or Decimal('0.00')
        
        # Sales cycle analysis
        closed_opportunities = opportunities.filter(is_closed=True)
        avg_sales_cycle = self._calculate_average_sales_cycle(closed_opportunities)
        
        return {
            'total_opportunities': total_opportunities,
            'total_pipeline_value': float(total_pipeline_value),
            'total_revenue': float(total_revenue),
            'won_opportunities': won_opportunities.count(),
            'win_rate': round(win_rate, 2),
            'average_deal_size': float(avg_deal_size),
            'average_sales_cycle_days': avg_sales_cycle,
        }
    
    def _analyze_sales_pipeline(self, date_filter: Dict) -> Dict:
        """Analyze sales pipeline distribution and health"""
        opportunities = Opportunity.objects.filter(
            tenant=self.tenant,
            is_closed=False,
            **date_filter
        )
        
        # Stage distribution
        stage_distribution = opportunities.values(
            'stage__name',
            'stage__probability'
        ).annotate(
            count=models.Count('id'),
            total_value=models.Sum('amount'),
            avg_value=models.Avg('amount')
        ).order_by('stage__sort_order')
        
        # Pipeline health indicators
        total_pipeline = opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        weighted_pipeline = opportunities.aggregate(
            weighted=models.Sum(
                models.F('amount') * models.F('probability') / 100.0,
                output_field=models.DecimalField(max_digits=15, decimal_places=2)
            )
        )['weighted'] or Decimal('0.00')
        
        # Aging analysis
        aging_buckets = self._analyze_opportunity_aging(opportunities)
        
        return {
            'stage_distribution': list(stage_distribution),
            'total_pipeline_value': float(total_pipeline),
            'weighted_pipeline_value': float(weighted_pipeline),
            'aging_analysis': aging_buckets,
            'pipeline_velocity': self._calculate_pipeline_velocity(opportunities),
        }
    
    def _analyze_sales_performance(self, date_filter: Dict) -> Dict:
        """Analyze individual and team sales performance"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Individual performance
        user_performance = User.objects.filter(
            owned_opportunities__tenant=self.tenant,
            **self._prefix_filter_keys('owned_opportunities', date_filter)
        ).annotate(
            total_opportunities=models.Count('owned_opportunities'),
            won_opportunities=models.Count(
                'owned_opportunities',
                filter=models.Q(owned_opportunities__is_won=True)
            ),
            total_revenue=models.Sum(
                'owned_opportunities__amount',
                filter=models.Q(owned_opportunities__is_won=True)
            ),
            pipeline_value=models.Sum('owned_opportunities__amount')
        ).order_by('-total_revenue')[:10]
        
        # Team performance (if territories are set up)
        team_performance = self._analyze_team_performance(date_filter)
        
        return {
            'individual_performance': [
                {
                    'user_name': user.get_full_name(),
                    'total_opportunities': user.total_opportunities,
                    'won_opportunities': user.won_opportunities,
                    'total_revenue': float(user.total_revenue or 0),
                    'pipeline_value': float(user.pipeline_value or 0),
                    'win_rate': (user.won_opportunities / user.total_opportunities * 100) 
                               if user.total_opportunities > 0 else 0,
                }
                for user in user_performance
            ],
            'team_performance': team_performance,
        }
    
    def _generate_sales_forecast(self, filters: Dict) -> Dict:
        """Generate sales forecast based on current pipeline"""
        # This would integrate with the ForecastService
        from .forecast_service import ForecastService
        
        forecast_service = ForecastService(self.tenant, self.user)
        
        # Get next quarter forecast
        forecast_data = forecast_service.generate_pipeline_forecast({
            'horizon_months': 3,
            'include_confidence_intervals': True,
        })
        
        return forecast_data
    
    def _analyze_campaign_performance(self, date_filter: Dict) -> Dict:
        """Analyze marketing campaign performance"""
        campaigns = Campaign.objects.filter(
            tenant=self.tenant,
            **date_filter
        )
        
        # Overall metrics
        total_campaigns = campaigns.count()
        active_campaigns = campaigns.filter(status='ACTIVE').count()
        
        # Email metrics
        total_emails_sent = campaigns.aggregate(
            total=models.Sum('emails_sent')
        )['total'] or 0
        
        total_opened = campaigns.aggregate(
            total=models.Sum('emails_opened')
        )['total'] or 0
        
        total_clicked = campaigns.aggregate(
            total=models.Sum('emails_clicked')
        )['total'] or 0
        
        # Calculate rates
        open_rate = (total_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0
        click_rate = (total_clicked / total_emails_sent * 100) if total_emails_sent > 0 else 0
        
        # Campaign ROI
        total_spent = campaigns.aggregate(
            total=models.Sum('budget_spent')
        )['total'] or Decimal('0.00')
        
        total_revenue = campaigns.aggregate(
            total=models.Sum('total_revenue')
        )['total'] or Decimal('0.00')
        
        roi = ((total_revenue - total_spent) / total_spent * 100) if total_spent > 0 else 0
        
        # Top performing campaigns
        top_campaigns = campaigns.annotate(
            campaign_roi=models.Case(
                models.When(budget_spent=0, then=0),
                default=((models.F('total_revenue') - models.F('budget_spent')) / 
                        models.F('budget_spent') * 100),
                output_field=models.FloatField()
            )
        ).order_by('-campaign_roi')[:5]
        
        return {
            'summary': {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'total_emails_sent': total_emails_sent,
                'overall_open_rate': round(open_rate, 2),
                'overall_click_rate': round(click_rate, 2),
                'total_spent': float(total_spent),
                'total_revenue': float(total_revenue),
                'overall_roi': round(roi, 2),
            },
            'top_campaigns': [
                {
                    'name': campaign.name,
                    'type': campaign.campaign_type,
                    'roi': round(campaign.campaign_roi, 2) if hasattr(campaign, 'campaign_roi') else 0,
                    'revenue': float(campaign.total_revenue),
                    'spent': float(campaign.budget_spent),
                }
                for campaign in top_campaigns
            ]
        }
    
    def _analyze_lead_generation(self, date_filter: Dict) -> Dict:
        """Analyze lead generation metrics"""
        leads = Lead.objects.filter(
            tenant=self.tenant,
            **date_filter
        )
        
        # Basic metrics
        total_leads = leads.count()
        qualified_leads = leads.filter(status='QUALIFIED').count()
        converted_leads = leads.filter(status='CONVERTED').count()
        
        # Conversion rates
        qualification_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Source analysis
        source_performance = leads.values(
            'source__name'
        ).annotate(
            total_leads=models.Count('id'),
            qualified_leads=models.Count(
                'id', filter=models.Q(status='QUALIFIED')
            ),
            converted_leads=models.Count(
                'id', filter=models.Q(status='CONVERTED')
            ),
        ).order_by('-total_leads')
        
        # Score distribution
        score_distribution = {
            'cold': leads.filter(score__lt=25).count(),
            'warm': leads.filter(score__gte=25, score__lt=50).count(),
            'hot': leads.filter(score__gte=50, score__lt=75).count(),
            'very_hot': leads.filter(score__gte=75).count(),
        }
        
        return {
            'summary': {
                'total_leads': total_leads,
                'qualified_leads': qualified_leads,
                'converted_leads': converted_leads,
                'qualification_rate': round(qualification_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
            },
            'source_performance': list(source_performance),
            'score_distribution': score_distribution,
        }
    
    def _get_date_filter(self, filters: Dict) -> Dict:
        """Convert filter period to date filter"""
        if not filters:
            return {}
        
        period = filters.get('period', 'current_month')
        now = timezone.now()
        
        if period == 'current_month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return {'created_at__gte': start_date}
        elif period == 'last_month':
            end_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_date = (end_date - timedelta(days=1)).replace(day=1)
            return {'created_at__gte': start_date, 'created_at__lt': end_date}
        elif period == 'current_quarter':
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=quarter_start_month, day=1, 
                                   hour=0, minute=0, second=0, microsecond=0)
            return {'created_at__gte': start_date}
        elif period == 'current_year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return {'created_at__gte': start_date}
        elif period == 'custom':
            date_filter = {}
            if filters.get('start_date'):
                date_filter['created_at__gte'] = filters['start_date']
            if filters.get('end_date'):
                date_filter['created_at__lte'] = filters['end_date']
            return date_filter
        
        return {}
    
    def _calculate_average_sales_cycle(self, opportunities) -> int:
        """Calculate average sales cycle in days"""
        closed_opportunities = opportunities.filter(
            closed_date__isnull=False
        )
        
        if not closed_opportunities.exists():
            return 0
        
        total_days = 0
        count = 0
        
        for opp in closed_opportunities:
            days = (opp.closed_date.date() - opp.created_date).days
            if days > 0:  # Exclude same-day closes
                total_days += days
                count += 1
        
        return total_days // count if count > 0 else 0
    
    def _calculate_single_kpi(self, kpi_config: Dict) -> Any:
        """Calculate individual KPI value"""
        metric_type = kpi_config.get('type')
        data_source = kpi_config.get('data_source')
        calculation = kpi_config.get('calculation')
        filters = kpi_config.get('filters', {})
        
        queryset = self._get_report_queryset(data_source, filters)
        
        if calculation == 'COUNT':
            return queryset.count()
        elif calculation == 'SUM':
            field = kpi_config.get('field')
            return queryset.aggregate(total=models.Sum(field))['total'] or 0
        elif calculation == 'AVG':
            field = kpi_config.get('field')
            return queryset.aggregate(avg=models.Avg(field))['avg'] or 0
        elif calculation == 'PERCENTAGE':
            # Custom percentage calculation
            numerator_filter = kpi_config.get('numerator_filter', {})
            numerator = queryset.filter(**numerator_filter).count()
            denominator = queryset.count()
            return (numerator / denominator * 100) if denominator > 0 else 0
        
        return None
    
    def _get_report_queryset(self, data_source: str, filters: Dict):
        """Get queryset for report data source"""
        model_map = {
            'leads': Lead,
            'accounts': Account,
            'opportunities': Opportunity,
            'campaigns': Campaign,
            'activities': Activity,
        }
        
        model_class = model_map.get(data_source.lower())
        if not model_class:
            raise CRMServiceException(f"Unknown data source: {data_source}")
        
        queryset = model_class.objects.filter(tenant=self.tenant)
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(model_class, field.split('__')[0]):
                queryset = queryset.filter(**{field: value})
        
        return queryset