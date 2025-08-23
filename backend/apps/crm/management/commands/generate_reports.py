"""
Automated Report Generation Management Command
Generate and distribute comprehensive CRM reports with scheduling and customization.
"""

import logging
import json
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from io import StringIO, BytesIO
import zipfile

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, Max, Min, Case, When, Value
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import get_user_model

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from crm.models.lead_model import Lead, LeadSource
from crm.models.account_model import Account, Contact
from crm.models.opportunity_model import Opportunity, Pipeline
from crm.models.activity_model import Activity
from crm.models.campaign_model import Campaign
from crm.models.ticket_model import Ticket
from crm.models.analytics_model import Report
from crm.models.user_model import CRMUserProfile
from crm.services.analytics_service import AnalyticsService

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate comprehensive CRM reports with automated distribution'

    def add_arguments(self, parser):
        # Report types
        parser.add_argument(
            '--report-type',
            choices=[
                'sales_performance', 'lead_analytics', 'pipeline_report',
                'activity_summary', 'campaign_performance', 'user_productivity',
                'executive_dashboard', 'custom', 'all'
            ],
            help='Type of report to generate',
            default='sales_performance'
        )
        
        # Time period options
        parser.add_argument(
            '--period',
            choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom'],
            help='Report time period',
            default='monthly'
        )
        
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for custom period (YYYY-MM-DD)',
            default=None
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for custom period (YYYY-MM-DD)',
            default=None
        )
        
        # Output options
        parser.add_argument(
            '--format',
            choices=['pdf', 'html', 'csv', 'json', 'xlsx'],
            help='Report output format',
            default='pdf'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Output directory for reports',
            default='./reports/'
        )
        
        # Distribution options
        parser.add_argument(
            '--email-to',
            type=str,
            help='Comma-separated email addresses to send reports to',
            default=None
        )
        
        parser.add_argument(
            '--email-template',
            type=str,
            help='Email template for report distribution',
            default='report_distribution'
        )
        
        # Filtering options
        parser.add_argument(
            '--user-ids',
            type=str,
            help='Comma-separated user IDs to include in report',
            default=None
        )
        
        parser.add_argument(
            '--team-filter',
            type=str,
            help='Filter by team or department',
            default=None
        )
        
        parser.add_argument(
            '--include-charts',
            action='store_true',
            help='Include charts and visualizations in reports',
        )
        
        # Advanced options
        parser.add_argument(
            '--custom-config',
            type=str,
            help='JSON file with custom report configuration',
            default=None
        )
        
        parser.add_argument(
            '--scheduled',
            action='store_true',
            help='Mark as scheduled report (affects naming and content)',
        )
        
        parser.add_argument(
            '--comparison-period',
            action='store_true',
            help='Include comparison with previous period',
        )

    def handle(self, *args, **options):
        try:
            self.analytics_service = AnalyticsService()
            self.generate_reports(**options)
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            raise CommandError(f'Report generation failed: {str(e)}')

    def generate_reports(self, **options):
        """Main report generation orchestrator"""
        report_type = options['report_type']
        
        self.stdout.write('📊 Starting CRM report generation...')
        
        # Validate format requirements
        self._validate_format_requirements(options)
        
        # Parse time period
        start_date, end_date = self._parse_time_period(options)
        
        # Load custom configuration if provided
        custom_config = self._load_custom_config(options.get('custom_config'))
        
        # Generate reports
        if report_type == 'all':
            report_types = [
                'sales_performance', 'lead_analytics', 'pipeline_report',
                'activity_summary', 'campaign_performance', 'user_productivity'
            ]
        else:
            report_types = [report_type]
        
        generated_reports = []
        
        for rtype in report_types:
            self.stdout.write(f'\n📈 Generating {rtype} report...')
            
            try:
                report_data = self._generate_report_data(
                    rtype, start_date, end_date, options, custom_config
                )
                
                report_file = self._generate_report_file(
                    rtype, report_data, options, start_date, end_date
                )
                
                generated_reports.append({
                    'type': rtype,
                    'file_path': report_file,
                    'data': report_data
                })
                
                self.stdout.write(f'✅ {rtype} report generated: {report_file}')
                
            except Exception as e:
                logger.error(f"Failed to generate {rtype} report: {str(e)}")
                self.stdout.write(f'❌ Failed to generate {rtype} report: {str(e)}')
        
        # Email distribution if requested
        if options['email_to']:
            self._distribute_reports(generated_reports, options)
        
        # Print summary
        self._print_generation_summary(generated_reports, options)

    def _validate_format_requirements(self, options: Dict):
        """Validate format-specific requirements"""
        format_type = options['format']
        
        if format_type == 'pdf' and not PDF_AVAILABLE:
            raise CommandError(
                'PDF generation requires reportlab. Install with: pip install reportlab'
            )
        
        if options['include_charts'] and not CHARTS_AVAILABLE:
            raise CommandError(
                'Chart generation requires matplotlib and seaborn. '
                'Install with: pip install matplotlib seaborn'
            )

    def _parse_time_period(self, options: Dict) -> Tuple[datetime, datetime]:
        """Parse time period options"""
        period = options['period']
        now = timezone.now()
        
        if period == 'custom':
            if not options['start_date'] or not options['end_date']:
                raise CommandError('Custom period requires --start-date and --end-date')
            
            try:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
                return start_date, end_date
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
        
        elif period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        elif period == 'weekly':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        elif period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        elif period == 'quarterly':
            quarter = (now.month - 1) // 3 + 1
            start_date = now.replace(month=(quarter-1)*3+1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        elif period == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        return start_date, end_date

    def _load_custom_config(self, config_file: Optional[str]) -> Optional[Dict]:
        """Load custom report configuration"""
        if not config_file:
            return None
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.stdout.write(f'✅ Loaded custom configuration: {config_file}')
                return config
        except FileNotFoundError:
            self.stdout.write(f'⚠️ Custom config file not found: {config_file}')
            return None
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in config file: {str(e)}')

    def _generate_report_data(self, report_type: str, start_date: datetime, 
                            end_date: datetime, options: Dict, 
                            custom_config: Optional[Dict]) -> Dict:
        """Generate report data based on type"""
        generators = {
            'sales_performance': self._generate_sales_performance_data,
            'lead_analytics': self._generate_lead_analytics_data,
            'pipeline_report': self._generate_pipeline_report_data,
            'activity_summary': self._generate_activity_summary_data,
            'campaign_performance': self._generate_campaign_performance_data,
            'user_productivity': self._generate_user_productivity_data,
            'executive_dashboard': self._generate_executive_dashboard_data,
        }
        
        generator = generators.get(report_type)
        if not generator:
            raise CommandError(f'Unknown report type: {report_type}')
        
        return generator(start_date, end_date, options, custom_config)

    def _generate_sales_performance_data(self, start_date: datetime, end_date: datetime,
                                       options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate comprehensive sales performance report data"""
        # Base opportunity queryset
        opportunities = Opportunity.objects.filter(
            created_at__range=[start_date, end_date]
        ).select_related('account', 'assigned_to', 'stage')
        
        # Apply user filter if specified
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            opportunities = opportunities.filter(assigned_to__user__id__in=user_ids)
        
        # Calculate key metrics
        total_opportunities = opportunities.count()
        total_pipeline_value = opportunities.aggregate(total=Sum('value'))['total'] or 0
        
        won_opportunities = opportunities.filter(stage__stage_type='WON')
        won_count = won_opportunities.count()
        won_value = won_opportunities.aggregate(total=Sum('value'))['total'] or 0
        
        lost_opportunities = opportunities.filter(stage__stage_type='LOST')
        lost_count = lost_opportunities.count()
        lost_value = lost_opportunities.aggregate(total=Sum('value'))['total'] or 0
        
        # Calculate rates
        win_rate = (won_count / max(1, won_count + lost_count)) * 100
        average_deal_size = won_value / max(1, won_count)
        
        # Performance by user
        user_performance = []
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            users = CRMUserProfile.objects.filter(user__id__in=user_ids)
        else:
            users = CRMUserProfile.objects.filter(
                user__is_active=True
            ).select_related('user')
        
        for user in users:
            user_opps = opportunities.filter(assigned_to=user)
            user_won = user_opps.filter(stage__stage_type='WON')
            user_lost = user_opps.filter(stage__stage_type='LOST')
            
            user_won_count = user_won.count()
            user_lost_count = user_lost.count()
            user_win_rate = (user_won_count / max(1, user_won_count + user_lost_count)) * 100
            
            user_performance.append({
                'user_name': f"{user.user.first_name} {user.user.last_name}",
                'user_email': user.user.email,
                'total_opportunities': user_opps.count(),
                'won_opportunities': user_won_count,
                'won_value': user_won.aggregate(total=Sum('value'))['total'] or 0,
                'lost_opportunities': user_lost_count,
                'win_rate': user_win_rate,
                'average_deal_size': (user_won.aggregate(total=Sum('value'))['total'] or 0) / max(1, user_won_count),
            })
        
        # Performance by pipeline stage
        stage_performance = list(
            opportunities.values('stage__name', 'stage__stage_type')
            .annotate(
                count=Count('id'),
                total_value=Sum('value'),
                avg_value=Avg('value')
            )
            .order_by('stage__order')
        )
        
        # Monthly trend analysis
        monthly_trends = self._calculate_monthly_trends(opportunities, start_date, end_date)
        
        # Comparison with previous period if requested
        comparison_data = None
        if options['comparison_period']:
            comparison_data = self._get_previous_period_comparison(
                start_date, end_date, 'sales_performance', options
            )
        
        return {
            'report_type': 'sales_performance',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_opportunities': total_opportunities,
                'total_pipeline_value': float(total_pipeline_value),
                'won_opportunities': won_count,
                'won_value': float(won_value),
                'lost_opportunities': lost_count,
                'lost_value': float(lost_value),
                'win_rate': round(win_rate, 2),
                'average_deal_size': round(float(average_deal_size), 2),
            },
            'user_performance': sorted(user_performance, key=lambda x: x['won_value'], reverse=True),
            'stage_performance': stage_performance,
            'monthly_trends': monthly_trends,
            'comparison': comparison_data,
        }

    def _generate_lead_analytics_data(self, start_date: datetime, end_date: datetime,
                                    options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate lead analytics report data"""
        # Base lead queryset
        leads = Lead.objects.filter(
            created_at__range=[start_date, end_date]
        ).select_related('source', 'assigned_to')
        
        # Apply filters
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            leads = leads.filter(assigned_to__user__id__in=user_ids)
        
        # Key metrics
        total_leads = leads.count()
        qualified_leads = leads.filter(status='QUALIFIED').count()
        converted_leads = leads.filter(status='CONVERTED').count()
        
        qualification_rate = (qualified_leads / max(1, total_leads)) * 100
        conversion_rate = (converted_leads / max(1, total_leads)) * 100
        
        # Lead source analysis
        source_analysis = list(
            leads.values('source__name')
            .annotate(
                count=Count('id'),
                qualified_count=Count(Case(When(status='QUALIFIED', then=1))),
                converted_count=Count(Case(When(status='CONVERTED', then=1))),
                avg_score=Avg('score')
            )
            .order_by('-count')
        )
        
        # Calculate source ROI
        for source in source_analysis:
            source_obj = LeadSource.objects.filter(name=source['source__name']).first()
            if source_obj and source_obj.cost_per_lead:
                total_cost = float(source_obj.cost_per_lead) * source['count']
                # Estimate revenue from conversions (simplified)
                estimated_revenue = source['converted_count'] * 5000  # Assumed average deal value
                roi = ((estimated_revenue - total_cost) / max(1, total_cost)) * 100
                source['roi'] = round(roi, 2)
                source['total_cost'] = total_cost
                source['estimated_revenue'] = estimated_revenue
            else:
                source['roi'] = 0
                source['total_cost'] = 0
                source['estimated_revenue'] = 0
        
        # Lead scoring analysis
        score_distribution = {
            'hot_leads': leads.filter(score__gte=80).count(),
            'warm_leads': leads.filter(score__gte=60, score__lt=80).count(),
            'cold_leads': leads.filter(score__gte=40, score__lt=60).count(),
            'poor_leads': leads.filter(score__lt=40).count(),
        }
        
        # Status distribution
        status_distribution = list(
            leads.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Industry analysis
        industry_analysis = list(
            leads.exclude(industry='')
            .values('industry')
            .annotate(
                count=Count('id'),
                conversion_rate=Count(Case(When(status='CONVERTED', then=1))) * 100.0 / Count('id')
            )
            .order_by('-count')[:10]
        )
        
        return {
            'report_type': 'lead_analytics',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_leads': total_leads,
                'qualified_leads': qualified_leads,
                'converted_leads': converted_leads,
                'qualification_rate': round(qualification_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
                'average_score': round(leads.aggregate(avg=Avg('score'))['avg'] or 0, 2),
            },
            'source_analysis': source_analysis,
            'score_distribution': score_distribution,
            'status_distribution': status_distribution,
            'industry_analysis': industry_analysis,
        }

    def _generate_pipeline_report_data(self, start_date: datetime, end_date: datetime,
                                     options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate pipeline analysis report data"""
        # Current pipeline snapshot
        current_opportunities = Opportunity.objects.filter(
            stage__stage_type='OPEN'
        ).select_related('stage', 'assigned_to', 'account')
        
        # Apply filters
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            current_opportunities = current_opportunities.filter(assigned_to__user__id__in=user_ids)
        
        # Pipeline by stage
        pipeline_by_stage = list(
            current_opportunities.values('stage__name', 'stage__probability')
            .annotate(
                count=Count('id'),
                total_value=Sum('value'),
                avg_value=Avg('value'),
                weighted_value=Sum(F('value') * F('stage__probability') / 100)
            )
            .order_by('stage__order')
        )
        
        # Pipeline velocity analysis
        closed_opportunities = Opportunity.objects.filter(
            actual_close_date__range=[start_date, end_date],
            stage__stage_type__in=['WON', 'LOST']
        ).select_related('stage')
        
        avg_sales_cycle = self._calculate_average_sales_cycle(closed_opportunities)
        
        # Forecast analysis
        forecast_data = {
            'current_quarter_forecast': self._calculate_quarterly_forecast(current_opportunities),
            'pipeline_coverage': self._calculate_pipeline_coverage(current_opportunities),
            'stage_conversion_rates': self._calculate_stage_conversion_rates(),
        }
        
        # Deal aging analysis
        aging_analysis = self._analyze_deal_aging(current_opportunities)
        
        return {
            'report_type': 'pipeline_report',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'current_pipeline': {
                'total_opportunities': current_opportunities.count(),
                'total_value': float(current_opportunities.aggregate(total=Sum('value'))['total'] or 0),
                'weighted_value': float(sum(stage['weighted_value'] or 0 for stage in pipeline_by_stage)),
            },
            'pipeline_by_stage': pipeline_by_stage,
            'velocity_metrics': {
                'average_sales_cycle_days': avg_sales_cycle,
                'deals_closed_this_period': closed_opportunities.count(),
            },
            'forecast': forecast_data,
            'aging_analysis': aging_analysis,
        }

    def _generate_activity_summary_data(self, start_date: datetime, end_date: datetime,
                                      options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate activity summary report data"""
        # Base activity queryset
        activities = Activity.objects.filter(
            created_at__range=[start_date, end_date]
        ).select_related('activity_type', 'assigned_to')
        
        # Apply filters
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            activities = activities.filter(assigned_to__user__id__in=user_ids)
        
        # Key metrics
        total_activities = activities.count()
        completed_activities = activities.filter(status='COMPLETED').count()
        completion_rate = (completed_activities / max(1, total_activities)) * 100
        
        # Activity by type
        activity_by_type = list(
            activities.values('activity_type__name')
            .annotate(
                count=Count('id'),
                completed=Count(Case(When(status='COMPLETED', then=1))),
                completion_rate=Count(Case(When(status='COMPLETED', then=1))) * 100.0 / Count('id')
            )
            .order_by('-count')
        )
        
        # User productivity
        user_productivity = list(
            activities.values('assigned_to__user__first_name', 'assigned_to__user__last_name')
            .annotate(
                total_activities=Count('id'),
                completed_activities=Count(Case(When(status='COMPLETED', then=1))),
                completion_rate=Count(Case(When(status='COMPLETED', then=1))) * 100.0 / Count('id')
            )
            .order_by('-total_activities')
        )
        
        # Daily activity trends
        daily_trends = self._calculate_daily_activity_trends(activities, start_date, end_date)
        
        return {
            'report_type': 'activity_summary',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_activities': total_activities,
                'completed_activities': completed_activities,
                'completion_rate': round(completion_rate, 2),
                'avg_activities_per_day': round(total_activities / max(1, (end_date - start_date).days), 2),
            },
            'activity_by_type': activity_by_type,
            'user_productivity': user_productivity,
            'daily_trends': daily_trends,
        }

    def _generate_campaign_performance_data(self, start_date: datetime, end_date: datetime,
                                          options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate campaign performance report data"""
        # Base campaign queryset
        campaigns = Campaign.objects.filter(
            start_date__range=[start_date, end_date]
        ).select_related('campaign_type', 'owner')
        
        # Campaign performance metrics
        campaign_performance = []
        
        for campaign in campaigns:
            members_count = campaign.members.count()
            responded_count = campaign.members.filter(status='RESPONDED').count()
            converted_count = campaign.members.filter(status='CONVERTED').count()
            
            response_rate = (responded_count / max(1, members_count)) * 100
            conversion_rate = (converted_count / max(1, members_count)) * 100
            
            # Calculate ROI
            total_cost = float(campaign.actual_cost or campaign.budget or 0)
            estimated_revenue = converted_count * 5000  # Simplified calculation
            roi = ((estimated_revenue - total_cost) / max(1, total_cost)) * 100 if total_cost > 0 else 0
            
            campaign_performance.append({
                'campaign_name': campaign.name,
                'campaign_type': campaign.campaign_type.name if campaign.campaign_type else '',
                'status': campaign.status,
                'members_count': members_count,
                'responded_count': responded_count,
                'converted_count': converted_count,
                'response_rate': round(response_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
                'budget': float(campaign.budget or 0),
                'actual_cost': float(campaign.actual_cost or 0),
                'roi': round(roi, 2),
                'estimated_revenue': estimated_revenue,
            })
        
        # Summary metrics
        total_budget = campaigns.aggregate(total=Sum('budget'))['total'] or 0
        total_cost = campaigns.aggregate(total=Sum('actual_cost'))['total'] or 0
        budget_utilization = (float(total_cost) / max(1, float(total_budget))) * 100
        
        return {
            'report_type': 'campaign_performance',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_campaigns': campaigns.count(),
                'total_budget': float(total_budget),
                'total_cost': float(total_cost),
                'budget_utilization': round(budget_utilization, 2),
            },
            'campaign_performance': sorted(campaign_performance, key=lambda x: x['roi'], reverse=True),
        }

    def _generate_user_productivity_data(self, start_date: datetime, end_date: datetime,
                                       options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate user productivity report data"""
        # Get users to analyze
        if options['user_ids']:
            user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
            users = CRMUserProfile.objects.filter(user__id__in=user_ids)
        else:
            users = CRMUserProfile.objects.filter(user__is_active=True).select_related('user')
        
        user_productivity = []
        
        for user in users:
            # Activity metrics
            user_activities = Activity.objects.filter(
                assigned_to=user,
                created_at__range=[start_date, end_date]
            )
            
            activities_completed = user_activities.filter(status='COMPLETED').count()
            activities_total = user_activities.count()
            activity_completion_rate = (activities_completed / max(1, activities_total)) * 100
            
            # Lead metrics
            user_leads = Lead.objects.filter(
                assigned_to=user,
                created_at__range=[start_date, end_date]
            )
            
            leads_converted = user_leads.filter(status='CONVERTED').count()
            lead_conversion_rate = (leads_converted / max(1, user_leads.count())) * 100
            
            # Opportunity metrics
            user_opportunities = Opportunity.objects.filter(
                assigned_to=user,
                created_at__range=[start_date, end_date]
            )
            
            opportunities_won = user_opportunities.filter(stage__stage_type='WON')
            won_value = opportunities_won.aggregate(total=Sum('value'))['total'] or 0
            
            user_productivity.append({
                'user_name': f"{user.user.first_name} {user.user.last_name}",
                'user_email': user.user.email,
                'activities_total': activities_total,
                'activities_completed': activities_completed,
                'activity_completion_rate': round(activity_completion_rate, 2),
                'leads_assigned': user_leads.count(),
                'leads_converted': leads_converted,
                'lead_conversion_rate': round(lead_conversion_rate, 2),
                'opportunities_created': user_opportunities.count(),
                'opportunities_won': opportunities_won.count(),
                'revenue_generated': float(won_value),
            })
        
        return {
            'report_type': 'user_productivity',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'user_productivity': sorted(user_productivity, key=lambda x: x['revenue_generated'], reverse=True),
        }

    def _generate_executive_dashboard_data(self, start_date: datetime, end_date: datetime,
                                         options: Dict, custom_config: Optional[Dict]) -> Dict:
        """Generate executive dashboard report data"""
        # High-level metrics
        total_revenue = Opportunity.objects.filter(
            stage__stage_type='WON',
            actual_close_date__range=[start_date, end_date]
        ).aggregate(total=Sum('value'))['total'] or 0
        
        total_pipeline = Opportunity.objects.filter(
            stage__stage_type='OPEN'
        ).aggregate(total=Sum('value'))['total'] or 0
        
        new_leads = Lead.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        new_customers = Account.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        # Growth metrics (compared to previous period)
        prev_start = start_date - (end_date - start_date)
        prev_end = start_date
        
        prev_revenue = Opportunity.objects.filter(
            stage__stage_type='WON',
            actual_close_date__range=[prev_start, prev_end]
        ).aggregate(total=Sum('value'))['total'] or 0
        
        revenue_growth = ((float(total_revenue) - float(prev_revenue)) / max(1, float(prev_revenue))) * 100
        
        return {
            'report_type': 'executive_dashboard',
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'generated_at': timezone.now().isoformat(),
            'kpis': {
                'total_revenue': float(total_revenue),
                'total_pipeline': float(total_pipeline),
                'new_leads': new_leads,
                'new_customers': new_customers,
                'revenue_growth': round(revenue_growth, 2),
            },
        }

    def _generate_report_file(self, report_type: str
                            options: Dict, start_date: datetime, end_date: datetime) -> str:
        """Generate report file in specified format"""
        format_type = options['format']
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report_type}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{timestamp}"
        
        if options['scheduled']:
            filename = f"scheduled_{filename}"
        
        # Generate charts if requested
        chart_paths = []
        if options['include_charts']:
            chart_paths = self._generate_charts(report_type, report_data)
        
        # Generate file based on format
        if format_type == 'pdf':
            return self._generate_pdf_report(filename, report_data, chart_paths, options)
        elif format_type == 'html':
            return self._generate_html_report(filename, report_data, chart_paths, options)
        elif format_type == 'csv':
            return self._generate_csv_report(filename, report_data, options)
        elif format_type == 'json':
            return self._generate_json_report(filename, report_data, options)
        elif format_type == 'xlsx':
            return self._generate_xlsx_report(filename, report_data, options)
        else:
            raise CommandError(f'Unsupported format: {format_type}')

    # Helper methods (continuing from previous implementation)
    def _calculate_monthly_trends(self, queryset, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Calculate monthly trends for opportunities"""
        monthly_data = []
        current = start_date.replace(day=1)
        
        while current <= end_date:
            next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
            
            month_opps = queryset.filter(
                created_at__gte=current,
                created_at__lt=next_month
            )
            
            monthly_data.append({
                'month': current.strftime('%Y-%m'),
                'opportunities_created': month_opps.count(),
                'total_value': float(month_opps.aggregate(total=Sum('value'))['total'] or 0),
                'won_count': month_opps.filter(stage__stage_type='WON').count(),
                'won_value': float(month_opps.filter(stage__stage_type='WON').aggregate(total=Sum('value'))['total'] or 0),
            })
            
            current = next_month
        
        return monthly_data

    def _get_previous_period_comparison(self, start_date: datetime, end_date: datetime, 
                                      report_type: str, options: Dict) -> Dict:
        """Get comparison data from previous period"""
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        # Generate data for previous period
        prev_data = self._generate_report_data(report_type, prev_start, prev_end, options, None)
        
        return {
            'previous_period': f"{prev_start.strftime('%Y-%m-%d')} to {prev_end.strftime('%Y-%m-%d')}",
            'data': prev_data
        }

    def _calculate_average_sales_cycle(self, opportunities) -> float:
        """Calculate average sales cycle in days"""
        cycles = []
        
        for opp in opportunities.filter(actual_close_date__isnull=False):
            cycle_days = (opp.actual_close_date - opp.created_at).days
            if cycle_days > 0:
                cycles.append(cycle_days)
        
        return sum(cycles) / len(cycles) if cycles else 0

    def _calculate_quarterly_forecast(self, opportunities) -> Dict:
        """Calculate quarterly forecast based on current pipeline"""
        # Simplified forecast calculation
        weighted_pipeline = opportunities.aggregate(
            weighted=Sum(F('value') * F('stage__probability') / 100)
        )['weighted'] or 0
        
        return {
            'weighted_pipeline': float(weighted_pipeline),
            'forecast_confidence': 'Medium',  # This would be calculated based on historical accuracy
        }

    def _calculate_pipeline_coverage(self, opportunities) -> float:
        """Calculate pipeline coverage ratio"""
        # This would typically compare pipeline to quota
        # Simplified calculation for demonstration
        quarterly_quota = 1000000  # This would come from user settings or config
        current_pipeline = opportunities.aggregate(total=Sum('value'))['total'] or 0
        
        return (float(current_pipeline) / quarterly_quota) * 100 if quarterly_quota > 0 else 0

    def _calculate_stage_conversion_rates(self) -> List[Dict]:
        """Calculate historical stage conversion rates"""
        # This would analyze historical data to calculate conversion rates between stages
        # Simplified example
        return [
            {'from_stage': 'Lead', 'to_stage': 'Qualified', 'conversion_rate': 25.0},
            {'from_stage': 'Qualified', 'to_stage': 'Proposal', 'conversion_rate': 60.0},
            {'from_stage': 'Proposal', 'to_stage': 'Negotiation', 'conversion_rate': 40.0},
            {'from_stage': 'Negotiation', 'to_stage': 'Closed Won', 'conversion_rate': 70.0},
        ]

    def _analyze_deal_aging(self, opportunities) -> Dict:
        """Analyze how long deals have been in current stage"""
        aging_buckets = {
            'fresh': 0,      # < 30 days
            'aging': 0,      # 30-60 days
            'stale': 0,      # 60-90 days
            'very_stale': 0  # > 90 days
        }
        
        current_time = timezone.now()
        
        for opp in opportunities:
            days_in_stage = (current_time - opp.updated_at).days
            
            if days_in_stage < 30:
                aging_buckets['fresh'] += 1
            elif days_in_stage < 60:
                aging_buckets['aging'] += 1
            elif days_in_stage < 90:
                aging_buckets['stale'] += 1
            else:
                aging_buckets['very_stale'] += 1
        
        return aging_buckets

    def _calculate_daily_activity_trends(self, activities, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Calculate daily activity trends"""
        daily_data = []
        current = start_date
        
        while current.date() <= end_date.date():
            day_activities = activities.filter(
                created_at__date=current.date()
            )
            
            daily_data.append({
                'date': current.strftime('%Y-%m-%d'),
                'total_activities': day_activities.count(),
                'completed_activities': day_activities.filter(status='COMPLETED').count(),
            })
            
            current += timedelta(days=1)
        
        return daily_data

    def _generate_charts(self, report_type: str, report_Generate charts for the report"""
        if not CHARTS_AVAILABLE:
            return []
        
        chart_paths = []
        
        try:
            # Set style
            plt.style.use('seaborn-v0_8')
            
            if report_type == 'sales_performance':
                chart_paths.extend(self._generate_sales_charts(report_data))
            elif report_type == 'lead_analytics':
                chart_paths.extend(self._generate_lead_charts(report_data))
            elif report_type == 'pipeline_report':
                chart_paths.extend(self._generate_pipeline_charts(report_data))
            
        except Exception as e:
            logger.warning(f"Failed to generate charts: {str(e)}")
        
        return chart_paths

    def _generate_sales_charts( -> List[str]:
        """Generate sales performance charts"""
        chart_paths = []
        
        # Win rate by user chart
        if report_data.get('user_performance'):
            fig, ax = plt.subplots(figsize=(12, 6))
            
            users = [up['user_name'] for up in report_data['user_performance'][:10]]
            win_rates = [up['win_rate'] for up in report_data['user_performance'][:10]]
            
            bars = ax.bar(users, win_rates, color='steelblue')
            ax.set_title('Win Rate by Sales Rep', fontsize=16, fontweight='bold')
            ax.set_ylabel('Win Rate (%)')
            ax.set_xlabel('Sales Representative')
            plt.xticks(rotation=45, ha='right')
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom')
            
            plt.tight_layout()
            chart_path = './reports/charts/win_rate_by_user.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            chart_paths.append(chart_path)
        
        return chart_paths

    def _generate_lead_charts(self, reportstr]:
        """Generate lead analytics charts"""
        chart_paths = []
        
        # Lead source performance
        if report_data.get('source_analysis'):
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            sources = [sa['source__name'] for sa in report_data['source_analysis'][:8]]
            counts = [sa['count'] for sa in report_data['source_analysis'][:8]]
            conversion_rates = [sa['converted_count']/max(1, sa['count'])*100 for sa in report_data['source_analysis'][:8]]
            
            # Lead volume by source
            ax1.bar(sources, counts, color='lightcoral')
            ax1.set_title('Lead Volume by Source', fontweight='bold')
            ax1.set_ylabel('Number of Leads')
            plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
            
            # Conversion rate by source
            ax2.bar(sources, conversion_rates, color='lightgreen')
            ax2.set_title('Conversion Rate by Source', fontweight='bold')
            ax2.set_ylabel('Conversion Rate (%)')
            plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
            
            plt.tight_layout()
            chart_path = './reports/charts/lead_source_analysis.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            chart_paths.append(chart_path)
        
        return chart_paths

    def _[str]:
        """Generate pipeline charts"""
        chart_paths = []
        
        # Pipeline by stage
        if report_data.get('pipeline_by_stage'):
            fig, ax = plt.subplots(figsize=(12, 8))
            
            stages = [pbs['stage__name'] for pbs in report_data['pipeline_by_stage']]
            values = [pbs['total_value'] for pbs in report_data['pipeline_by_stage']]
            
            # Create horizontal bar chart
            bars = ax.barh(stages, values, color='skyblue')
            ax.set_title('Pipeline Value by Stage', fontsize=16, fontweight='bold')
            ax.set_xlabel('Pipeline Value ($)')
            
            # Add value labels
            for bar in bars:
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2.,
                       f'${width:,.0f}', ha='left', va='center')
            
            plt.tight_layout()
            chart_path = './reports/charts/pipeline_by_stage.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            chart_paths.append(chart_path)
        
        return chart_paths

    def _generate, 
                           chart_paths: List[str], options: Dict) -> str:
        """Generate PDF report"""
        if not PDF_AVAILABLE:
            raise CommandError('PDF generation not available. Install reportlab.')
        
        import os
        os.makedirs(options['output_dir'], exist_ok=True)
        
        file_path = os.path.join(options['output_dir'], f'{filename}.pdf')
        
        # Create PDF document
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.darkblue
        )
        
        story.append(Paragraph(f"CRM {report_data['report_type'].replace('_', ' ').title()} Report", title_style))
        story.append(Paragraph(f"Period: {report_data['period']}", styles['Normal']))
        story.append(Paragraph(f"Generated: {report_data['generated_at']}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary section
        if
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            
            summary_data = []
            for key, value in report_data['summary'].items():
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, float) and 'rate' in key:
                    formatted_value = f"{value:.2f}%"
                elif isinstance(value, (int, float)) and ('value' in key or 'revenue' in key):
                    formatted_value = f"${value:,.2f}"
                else:
                    formatted_value = f"{value:,}" if isinstance(value, (int, float)) else str(value)
                
                summary_data.append([formatted_key, formatted_value])
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
  story.append(PageBreak())
        
        # Add charts if available
        if chart_paths:
            story.append(Paragraph("Charts and Visualizations", styles['Heading2']))
            
            for chart_path in chart_paths:
                if os.path.exists(chart_path):
                    from reportlab.platypus import Image
                    img = Image(chart_path, width=6*inch, height=3.5*inch)
                    story.append(img)
                    story.append(Spacer(1, 12))
            
            story.append(PageBreak())
        
        # Add detailed sections based on report type
        if report_data['report_type'] == 'sales_performance':
            self._add_sales_performance_details(story, report_data, styles)
        elif report_data['report_type'] == 'lead_analytics':
            self._add_lead_analytics_details(story, report_data, styles)
        elif report_data['report_type'] == 'pipeline_report':
            self._add_pipeline_details(story, report_data, styles)
        
        # Build PDF
        doc.build(story)
        
        return file_path

    def _add_sales_performance_details(self, story, report_data, styles):
        """Add sales performance details to PDF"""
        # User performance table
        if report_data.get('user_performance'):
            story.append(Paragraph("Sales Representative Performance", styles['Heading2']))
            
            user_data = [['Rep Name', 'Opportunities', 'Won', 'Won Value', 'Win Rate', 'Avg Deal Size']]
            
            for up in report_data['user_performance'][:10]:  # Top 10
                user_data.append([
                    up['user_name'],
                    str(up['total_opportunities']),
                    str(up['won_opportunities']),
                    f"${up['won_value']:,.2f}",
                    f"{up['win_rate']:.1f}%",
                    f"${up['average_deal_size']:,.2f}"
                ])
            
            user_table = Table(user_data)
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(user_table)
            story.append(Spacer(1, 20))

    def _add_lead_analytics_details(self, story, report_data, styles):
        """Add lead analytics details to PDF"""
        # Source analysis table
        if report_data.get('source_analysis'):
            story.append(Paragraph("Lead Source Analysis", styles['Heading2']))
            
            source_data = [['Source', 'Leads', 'Qualified', 'Converted', 'Conversion Rate', 'ROI']]
            
            for sa in report_data['source_analysis'][:10]:
                conversion_rate = (sa['converted_count'] / max(1, sa['count'])) * 100
                source_data.append([
                    sa['source__name'] or 'Unknown',
                    str(sa['count']),
                    str(sa['qualified_count']),
                    str(sa['converted_count']),
                    f"{conversion_rate:.1f}%",
                    f"{sa.get('roi', 0):.1f}%"
                ])
            
            source_table = Table(source_data)
            source_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(source_table)
            story.append(Spacer(1, 20))

    def _add_pipeline_details(self, story, report_data, styles):
        """Add pipeline details to PDF"""
        # Pipeline by stage table
        if report_data.get('pipeline_by_stage'):
            story.append(Paragraph("Pipeline by Stage", styles['Heading2']))
            
            pipeline_data = [['Stage', 'Count', 'Total Value', 'Avg Value', 'Weighted Value']]
            
            for pbs in report_data['pipeline_by_stage']:
                pipeline_data.append([
                    pbs['stage__name'],
                    str(pbs['count']),
                    f"${pbs['total_value']:,.2f}",
                    f"${pbs['avg_value']:,.2f}",
                    f"${pbs['weighted_value']:,.2f}"
                ])
            
            pipeline_table = Table(pipeline_data)
            pipeline_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(pipeline_table)

    def _generate_html_report(self, filename: str
                            chart_paths: List[str], options: Dict) -> str:
        """Generate HTML report"""
        import os
        os.makedirs(options['output_dir'], exist_ok=True)
        
        file_path = os.path.join(options['output_dir'], f'{filename}.html')
        
        # Render HTML template
        html_content = render_to_string('crm/reports/base_report.html', {
            'report_data': report_data,
            'chart_paths': chart_paths,
            'generated_at': timezone.now(),
            'options': options
        })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return file_path

    def _generate_csv_report(self, filename: str: Dict) -> str:
        """Generate CSV report"""
        import os
        os.makedirs(options['output_dir'], exist_ok=True)
        
        file_path = os.path.join(options['output_dir'], f'{filename}.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            # Write based on report type
            if report_data['report_type'] == 'sales_performance':
                self._write_sales_performance_csv(csvfile, report_data)
            elif report_data['report_type'] == 'lead_analytics':
                self._write_lead_analytics_csv(csvfile, report_data)
            else:
                # Generic CSV writer
                writer = csv.writer(csvfile)
                writer.writerow(['Report Type', report_data['report_type']])
                writer.writerow(['Period', report_data['period']])
                writer.writerow(['Generated At', report_data['generated_at']])
                writer.writerow([])  # Empty row
                
                # Write summary
                if report_data.get('summary'):
                    writer.writerow(['SUMMARY'])
                    for key, value in report_data['summary'].items():
                        writer.writerow([key.replace('_', ' ').title(), value])
        
        return file_path

    def _write_sales_performance_csv(self, csvfile, report_data):
        """Write sales performance data to CSV"""
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow(['Sales Performance Report'])
        writer.writerow(['Period:', report_data['period']])
        writer.writerow(['Generated:', report_data['generated_at']])
        writer.writerow([])
        
        # Summary
        writer.writerow(['SUMMARY'])
        for key, value in report_data['summary'].items():
            writer.writerow([key.replace('_', ' ').title(), value])
        writer.writerow([])
        
        # User performance
        if report_data.get('user_performance'):
            writer.writerow(['USER PERFORMANCE'])
            writer.writerow([
                'User Name', 'Total Opportunities', 'Won Opportunities', 
                'Won Value', 'Win Rate', 'Average Deal Size'
            ])
            
            for up in report_data['user_performance']:
                writer.writerow([
                    up['user_name'],
                    up['total_opportunities'],
                    up['won_opportunities'],
                    up['won_value'],
                    up['win_rate'],
                    up['average_deal_size']
                ])

    def _write_lead_analytics_csv(self, csvfile, report_data):
        """Write lead analytics data to CSV"""
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow(['Lead Analytics Report'])
        writer.writerow(['Period:', report_data['period']])
        writer.writerow(['Generated:', report_data['generated_at']])
        writer.writerow([])
        
        # Summary
        writer.writerow(['SUMMARY'])
        for key, value in report_data['summary'].items():
            writer.writerow([key.replace('_', ' ').title(), value])
        writer.writerow([])
        
        # Source analysis
        if report_data.get('source_analysis'):
            writer.writerow(['SOURCE ANALYSIS'])
            writer.writerow([
                'Source', 'Count', 'Qualified', 'Converted', 
                'Average Score', 'ROI', 'Total Cost', 'Estimated Revenue'
            ])
            
            for sa in report_data['source_analysis']:
                writer.writerow([
                    sa['source__name'] or 'Unknown',
                    sa['count'],
                    sa['qualified_count'],
                    sa['converted_count'],
                    sa.get('avg_score', 0),
                    sa.get('roi', 0),
                    sa.get('total_cost', 0),
                    sa.get('estimated_revenue', 0)
                ])

    def _generate_json_report(self, filename: str"""Generate JSON report"""
        import os
        os.makedirs(options['output_dir'], exist_ok=True)
        
        file_path = os.path.join(options['output_dir'], f'{filename}.json')
        
        # Convert Decimal objects to float for JSON serialization
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=decimal_default, ensure_ascii=False)
        
        return file_path

    def _generate_xlsx_report(self, filename: str: Dict) -> str:
        """Generate Excel report"""
        try:
            import xlsxwriter
        except ImportError:
            raise CommandError('Excel generation requires xlsxwriter. Install with: pip install xlsxwriter')
        
        import os
        os.makedirs(options['output_dir'], exist_ok=True)
        
        file_path = os.path.join(options['output_dir'], f'{filename}.xlsx')
        
        workbook = xlsxwriter.Workbook(file_path)
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BD',
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'bg_color': '#4F81BD',
            'font_color': 'white'
        })
        
        # Summary worksheet
        summary_ws = workbook.add_worksheet('Summary')
        self._write_excel_summary(summary_ws, report_data, title_format, header_format)
        
        # Data worksheets based on report type
        if report_data['report_type'] == 'sales_performance':
            self._write_sales_excel_sheets(workbook, report_data, header_format)
        elif report_data['report_type'] == 'lead_analytics':
            self._write_lead_excel_sheets(workbook, report_data, header_format)
        
        workbook.close()
        return file_path

    def _write_excel_summary(self, worksheet, report_data, title_format, header_format):
        """Write summary data to Excel worksheet"""
        # Title
        worksheet.write(0, 0, f"{report_data['report_type'].replace('_', ' ').title()} Report", title_format)
        worksheet.write(1, 0, f"Period: {report_data['period']}")
        worksheet.write(2, 0, f"Generated: {report_data['generated_at']}")
        
        # Summary data
        if report_data.get('summary'):
            row = 5
            worksheet.write(row, 0, 'SUMMARY', header_format)
            row += 1
            
            for key, value in report_data['summary'].items():
                worksheet.write(row, 0, key.replace('_', ' ').title())
                
                if isinstance(value, (int, float)):
                    if 'rate' in key.lower():
                        worksheet.write(row, 1, f"{value:.2f}%")
                    elif 'value' in key.lower() or 'revenue' in key.lower():
                        worksheet.write(row, 1, value)
                        worksheet.write(row, 2, f"${value:,.2f}")
                    else:
                        worksheet.write(row, 1, value)
                else:
                    worksheet.write(row, 1, value)
                
                row += 1

    def _write_sales_excel_sheets(self, workbook, report_data, header_format):
        """Write sales performance sheets to Excel"""
        # User performance sheet
        if report_data.get('user_performance'):
            user_ws = workbook.add_worksheet('User Performance')
            
            headers = ['User Name', 'Total Opportunities', 'Won Opportunities', 
                      'Won Value', 'Win Rate', 'Average Deal Size']
            
            for col, header in enumerate(headers):
                user_ws.write(0, col, header, header_format)
            
            for row, up in enumerate(report_data['user_performance'], 1):
                user_ws.write(row, 0, up['user_name'])
                user_ws.write(row, 1, up['total_opportunities'])
                user_ws.write(row, 2, up['won_opportunities'])
                user_ws.write(row, 3, up['won_value'])
                user_ws.write(row, 4, f"{up['win_rate']:.2f}%")
                user_ws.write(row, 5, up['average_deal_size'])

    def _write_lead_excel_sheets(self, workbook, report_data, header_format):
        """Write lead analytics sheets to Excel"""
        # Source analysis sheet
        if report_data.get('source_analysis'):
            source_ws = workbook.add_worksheet('Source Analysis')
            
            headers = ['Source', 'Count', 'Qualified', 'Converted', 
                      'Average Score', 'ROI', 'Total Cost', 'Estimated Revenue']
            
            for col, header in enumerate(headers):
                source_ws.write(0, col, header, header_format)
            
            for row, sa in enumerate(report_data['source_analysis'], 1):
                source_ws.write(row, 0, sa['source__name'] or 'Unknown')
                source_ws.write(row, 1, sa['count'])
                source_ws.write(row, 2, sa['qualified_count'])
                source_ws.write(row, 3, sa['converted_count'])
                source_ws.write(row, 4, sa.get('avg_score', 0))
                source_ws.write(row, 5, f"{sa.get('roi', 0):.2f}%")
                source_ws.write(row, 6, sa.get('total_cost', 0))
                source_ws.write(row, 7, sa.get('estimated_revenue', 0))

    def _distribute_reports(self, generated_reports: List[Dict], options: Dict):
        """Distribute reports via email"""
        email_addresses = [email.strip() for email in options['email_to'].split(',')]
        
        for email in email_addresses:
            try:
                self._send_report_email(email, generated_reports, options)
                self.stdout.write(f'📧 Report sent to: {email}')
            except Exception as e:
                logger.error(f"Failed to send report to {email}: {str(e)}")
                self.stdout.write(f'❌ Failed to send report to {email}: {str(e)}')

    def _send_report_email(self, email: str, reports: List[Dict], options: Dict):
        """Send individual report email"""
        # Prepare email content
        subject = f"CRM Reports - {timezone.now().strftime('%Y-%m-%d')}"
        
        if options['scheduled']:
            subject = f"Scheduled {subject}"
        
        # Render email template
        email_template = options.get('email_template', 'report_distribution')
        html_content = render_to_string(f'crm/emails/{email_template}.html', {
            'reports': reports,
            'generated_at': timezone.now(),
            'recipient_email': email,
        })
        
        # Create email message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email='noreply@yourcrm.com',
            to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        
        # Attach report files
        for report in reports:
            if os.path.exists(report['file_path']):
                msg.attach_file(report['file_path'])
        
        # Send email
        msg.send()

    def _print_generation_summary(self, generated_reports: List[Dict], options: Dict):
        """Print report generation summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 REPORT GENERATION SUMMARY')
        self.stdout.write('='*60)
        
        successful_reports = [r for r in generated_reports if 'file_path' in r]
        failed_reports = len(generated_reports) - len(successful_reports)
        
        self.stdout.write(f'Reports Requested: {len(generated_reports)}')
        self.stdout.write(f'Successfully Generated: {len(successful_reports)}')
        if failed_reports > 0:
            self.stdout.write(f'Failed: {failed_reports}')
        
        self.stdout.write(f'Output Format: {options["format"].upper()}')
        self.stdout.write(f'Output Directory: {options["output_dir"]}')
        
        if options['include_charts']:
            self.stdout.write('Charts: Included')
        
        # List generated files
        if successful_reports:
            self.stdout.write('\n📄 Generated Files:')
            total_size = 0
            
            for report in successful_reports:
                file_path = report['file_path']
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    
                    size_str = self._format_file_size(file_size)
                    self.stdout.write(f'  ✅ {report["type"]}: {file_path} ({size_str})')
                else:
                    self.stdout.write(f'  ❌ {report["type"]}: File not found')
            
            if total_size > 0:
                self.stdout.write(f'\nTotal Size: {self._format_file_size(total_size)}')
        
        # Email distribution summary
        if options['email_to']:
            email_count = len([e.strip() for e in options['email_to'].split(',') if e.strip()])
            self.stdout.write(f'\n📧 Email Distribution: {email_count} recipients')
        
        self.stdout.write('='*60)
        
        if failed_reports == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ All reports generated successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ {len(successful_reports)} reports generated, {failed_reports} failed'
                )
            )

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"