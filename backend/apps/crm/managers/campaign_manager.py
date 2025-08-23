"""
Campaign Manager - Marketing Campaign Management
Advanced campaign tracking, analytics, and automation
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class CampaignManager(AnalyticsManager):
    """
    Advanced Campaign Manager
    Marketing campaign analytics and performance tracking
    """
    
    def active_campaigns(self):
        """Get active campaigns"""
        return self.filter(status='active')
    
    def completed_campaigns(self):
        """Get completed campaigns"""
        return self.filter(status='completed')
    
    def scheduled_campaigns(self):
        """Get scheduled/upcoming campaigns"""
        return self.filter(status='scheduled')
    
    def paused_campaigns(self):
        """Get paused campaigns"""
        return self.filter(status='paused')
    
    def email_campaigns(self):
        """Get email campaigns"""
        return self.filter(campaign_type='email')
    
    def social_campaigns(self):
        """Get social media campaigns"""
        return self.filter(campaign_type='social')
    
    def paid_campaigns(self):
        """Get paid advertising campaigns"""
        return self.filter(campaign_type='paid_ads')
    
    def content_campaigns(self):
        """Get content marketing campaigns"""
        return self.filter(campaign_type='content')
    
    def high_budget_campaigns(self, threshold: Decimal = Decimal('10000')):
        """Get campaigns above budget threshold"""
        return self.filter(budget__gte=threshold)
    
    def campaigns_ending_soon(self, days: int = 7):
        """Get campaigns ending within specified days"""
        end_date = timezone.now() + timedelta(days=days)
        return self.filter(
            end_date__lte=end_date,
            status='active'
        )
    
    def get_campaign_performance(self, tenant, days: int = 30):
        """Get comprehensive campaign performance metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).aggregate(
            # Basic metrics
            total_campaigns=Count('id'),
            active_campaigns=Count('id', filter=Q(status='active')),
            completed_campaigns=Count('id', filter=Q(status='completed')),
            
            # Budget metrics
            total_budget=Sum('budget'),
            total_spent=Sum('actual_cost'),
            avg_budget=Avg('budget'),
            budget_utilization=Case(
                When(budget__gt=0, then=Avg(F('actual_cost') / F('budget') * 100)),
                default=0
            ),
            
            # Performance metrics
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_leads=Sum('leads_generated'),
            total_conversions=Sum('conversions'),
            
            # Engagement metrics
            avg_ctr=Avg('click_through_rate'),
            avg_conversion_rate=Avg('conversion_rate'),
            avg_cost_per_lead=Avg('cost_per_lead'),
            avg_roi=Avg('roi_percentage'),
            
            # Email specific
            total_emails_sent=Sum('emails_sent', filter=Q(campaign_type='email')),
            total_emails_opened=Sum('emails_opened', filter=Q(campaign_type='email')),
            avg_open_rate=Avg('open_rate', filter=Q(campaign_type='email')),
            avg_bounce_rate=Avg('bounce_rate', filter=Q(campaign_type='email'))
        )
    
    def get_campaign_roi_analysis(self, tenant, days: int = 90):
        """Analyze ROI across campaigns"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        campaigns = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date],
            actual_cost__gt=0,
            revenue_generated__gt=0
        )
        
        roi_data = campaigns.aggregate(
            total_investment=Sum('actual_cost'),
            total_revenue=Sum('revenue_generated'),
            avg_roi=Avg('roi_percentage'),
            best_roi=Max('roi_percentage'),
            worst_roi=Min('roi_percentage'),
            profitable_campaigns=Count('id', filter=Q(roi_percentage__gt=0)),
            unprofitable_campaigns=Count('id', filter=Q(roi_percentage__lt=0))
        )
        
        # Calculate overall ROI
        if roi_data['total_investment'] and roi_data['total_investment'] > 0:
            roi_data['overall_roi'] = (
                (roi_data['total_revenue'] - roi_data['total_investment']) / 
                roi_data['total_investment']
            ) * 100
        else:
            roi_data['overall_roi'] = 0
        
        return roi_data
    
    def get_channel_performance(self, tenant, days: int = 30):
        """Compare performance across campaign channels"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).values('campaign_type').annotate(
            campaign_count=Count('id'),
            total_budget=Sum('budget'),
            total_spent=Sum('actual_cost'),
            total_leads=Sum('leads_generated'),
            total_conversions=Sum('conversions'),
            avg_ctr=Avg('click_through_rate'),
            avg_conversion_rate=Avg('conversion_rate'),
            avg_cost_per_lead=Avg('cost_per_lead'),
            avg_roi=Avg('roi_percentage'),
            total_revenue=Sum('revenue_generated')
        ).order_by('-total_revenue')
    
    def get_lead_attribution(self, tenant, days: int = 30):
        """Analyze lead attribution by campaign"""
        from ..models import Lead
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get leads generated by campaigns
        campaign_leads = Lead.objects.filter(
            tenant=tenant,
            campaign__isnull=False,
            created_at__range=[start_date, end_date]
        ).values(
            'campaign__name',
            'campaign__id',
            'campaign__campaign_type'
        ).annotate(
            leads_generated=Count('id'),
            qualified_leads=Count('id', filter=Q(status='qualified')),
            converted_leads=Count('id', filter=Q(status='converted')),
            avg_lead_score=Avg('score'),
            qualification_rate=Case(
                When(id__isnull=False, then=Avg(Case(
                    When(status='qualified', then=1),
                    default=0
                )) * 100),
                default=0
            )
        ).order_by('-leads_generated')
        
        return list(campaign_leads)
    
    def get_email_campaign_metrics(self, tenant, campaign_id: int = None):
        """Get detailed email campaign metrics"""
        queryset = self.for_tenant(tenant).filter(campaign_type='email')
        
        if campaign_id:
            queryset = queryset.filter(id=campaign_id)
        
        return queryset.aggregate(
            # Delivery metrics
            total_emails_sent=Sum('emails_sent'),
            total_delivered=Sum('emails_delivered'),
            total_bounced=Sum('emails_bounced'),
            avg_delivery_rate=Avg(
                Case(
                    When(emails_sent__gt=0, then=F('emails_delivered') / F('emails_sent') * 100),
                    default=0
                )
            ),
            
            # Engagement metrics
            total_opened=Sum('emails_opened'),
            total_clicked=Sum('emails_clicked'),
            total_unsubscribed=Sum('unsubscribes'),
            avg_open_rate=Avg('open_rate'),
            avg_click_rate=Avg('click_through_rate'),
            avg_unsubscribe_rate=Avg('unsubscribe_rate'),
            
            # Performance metrics
            total_leads_generated=Sum('leads_generated'),
            avg_cost_per_open=Avg('cost_per_open'),
            avg_cost_per_click=Avg('cost_per_click'),
            
            # A/B testing metrics
            subject_line_tests=Count('id', filter=Q(ab_test_type='subject_line')),
            content_tests=Count('id', filter=Q(ab_test_type='content')),
            send_time_tests=Count('id', filter=Q(ab_test_type='send_time'))
        )
    
    def get_campaign_lifecycle_analysis(self, tenant, campaign_id: int):
        """Analyze campaign performance throughout its lifecycle"""
        from ..models import CampaignMember, Activity
        
        campaign = self.for_tenant(tenant).get(id=campaign_id)
        
        # Get daily performance data
        daily_performance = CampaignMember.objects.filter(
            campaign=campaign
        ).extra(
            select={'day': 'date(joined_at)'}
        ).values('day').annotate(
            members_joined=Count('id'),
            emails_sent=Count('id', filter=Q(status='email_sent')),
            emails_opened=Count('id', filter=Q(status='email_opened')),
            emails_clicked=Count('id', filter=Q(status='email_clicked')),
            leads_generated=Count('id', filter=Q(converted_to_lead=True))
        ).order_by('day')
        
        # Get activity timeline
        campaign_activities = Activity.objects.filter(
            campaign=campaign
        ).values(
            'activity_type',
            'created_at__date'
        ).annotate(
            activity_count=Count('id')
        ).order_by('created_at__date')
        
        return {
            'daily_performance': list(daily_performance),
            'activity_timeline': list(campaign_activities),
            'total_duration': (campaign.end_date - campaign.start_date).days if campaign.end_date else None,
            'campaign_status': campaign.status
        }
    
    def optimize_campaign_budget(self, tenant, optimization_rules: dict):
        """
        Optimize budget allocation across campaigns
        
        optimization_rules format:
        {
            'target_metric': 'roi' | 'leads' | 'conversions',
            'min_roi_threshold': 15.0,
            'max_cost_per_lead': 50.0,
            'reallocation_percentage': 10.0
        }
        """
        active_campaigns = self.for_tenant(tenant).filter(status='active')
        
        # Identify high-performing campaigns
        high_performers = active_campaigns.filter(
            roi_percentage__gte=optimization_rules.get('min_roi_threshold', 15.0),
            cost_per_lead__lte=optimization_rules.get('max_cost_per_lead', 50.0)
        )
        
        # Identify low-performing campaigns
        low_performers = active_campaigns.exclude(
            id__in=high_performers.values('id')
        )
        
        recommendations = []
        reallocation_amount = Decimal('0')
        
        # Calculate reallocation from low performers
        for campaign in low_performers:
            if campaign.budget and campaign.budget > 0:
                reduction = campaign.budget * Decimal(
                    optimization_rules.get('reallocation_percentage', 10.0) / 100
                )
                reallocation_amount += reduction
                
                recommendations.append({
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'action': 'reduce_budget',
                    'current_budget': campaign.budget,
                    'recommended_reduction': reduction,
                    'reason': 'Low ROI or high cost per lead'
                })
        
        # Allocate to high performers
        if high_performers.exists() and reallocation_amount > 0:
            per_campaign_increase = reallocation_amount / high_performers.count()
            
            for campaign in high_performers:
                recommendations.append({
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'action': 'increase_budget',
                    'current_budget': campaign.budget,
                    'recommended_increase': per_campaign_increase,
                    'reason': 'High ROI and efficient cost per lead'
                })
        
        return {
            'recommendations': recommendations,
            'total_reallocation': reallocation_amount,
            'high_performers': high_performers.count(),
            'low_performers': low_performers.count()
        }
    
    def bulk_pause_underperforming_campaigns(self, tenant, performance_thresholds: dict):
        """
        Bulk pause campaigns that don't meet performance thresholds
        
        thresholds format:
        {
            'min_roi': -50.0,
            'max_cost_per_lead': 100.0,
            'min_conversion_rate': 1.0
        }
        """
        underperforming = self.for_tenant(tenant).filter(
            status='active'
        )
        
        if 'min_roi' in performance_thresholds:
            underperforming = underperforming.filter(
                roi_percentage__lt=performance_thresholds['min_roi']
            )
        
        if 'max_cost_per_lead' in performance_thresholds:
            underperforming = underperforming.filter(
                cost_per_lead__gt=performance_thresholds['max_cost_per_lead']
            )
        
        if 'min_conversion_rate' in performance_thresholds:
            underperforming = underperforming.filter(
                conversion_rate__lt=performance_thresholds['min_conversion_rate']
            )
        
        paused_count = underperforming.update(
            status='paused',
            paused_at=timezone.now(),
            pause_reason='Automated pause - performance below thresholds'
        )
        
        return {
            'paused_campaigns': paused_count,
            'thresholds_applied': performance_thresholds
        }
    
    def create_lookalike_campaign(self, source_campaign_id: int, modifications: dict):
        """
        Create a new campaign based on a successful existing campaign
        
        modifications format:
        {
            'name': 'New Campaign Name',
            'budget': 5000.00,
            'target_audience': {...},
            'start_date': datetime,
            'variations': ['subject_line', 'content', 'timing']
        }
        """
        source_campaign = self.get(id=source_campaign_id)
        
        # Create new campaign with modified attributes
        new_campaign_data = {
            'tenant': source_campaign.tenant,
            'name': modifications.get('name', f"{source_campaign.name} - Copy"),
            'campaign_type': source_campaign.campaign_type,
            'description': f"Based on successful campaign: {source_campaign.name}",
            'budget': modifications.get('budget', source_campaign.budget),
            'target_audience': modifications.get('target_audience', source_campaign.target_audience),
            'start_date': modifications.get('start_date', timezone.now()),
            'status': 'draft',
            'created_by': modifications.get('created_by'),
            
            # Copy successful attributes
            'email_template': source_campaign.email_template,
            'landing_page': source_campaign.landing_page,
            'tracking_parameters': source_campaign.tracking_parameters
        }
        
        new_campaign = self.create(**new_campaign_data)
        
        return {
            'new_campaign': new_campaign,
            'source_campaign': source_campaign,
            'copied_attributes': list(new_campaign_data.keys())
        }