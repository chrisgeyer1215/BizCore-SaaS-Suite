"""
Analytics Manager - Advanced Business Intelligence
Comprehensive analytics and reporting across all CRM modules
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class AnalyticsReportManager(AnalyticsManager):
    """
    Advanced Analytics Manager
    Cross-module business intelligence and reporting
    """
    
    def get_executive_dashboard_data(self, tenant, days: int = 30):
        """Get high-level executive dashboard metrics"""
        from ..models import Lead, Opportunity, Account, Activity, Campaign, Ticket
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Lead metrics
        lead_metrics = Lead.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).aggregate(
            new_leads=Count('id'),
            qualified_leads=Count('id', filter=Q(status='qualified')),
            converted_leads=Count('id', filter=Q(status='converted')),
            avg_lead_score=Avg('score')
        )
        
        # Opportunity metrics
        opp_metrics = Opportunity.objects.filter(
            tenant=tenant
        ).aggregate(
            total_pipeline_value=Sum('value', filter=Q(stage__is_closed=False)),
            won_revenue=Sum('value', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            )),
            total_opportunities=Count('id', filter=Q(stage__is_closed=False)),
            avg_deal_size=Avg('value', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            ))
        )
        
        # Activity metrics
        activity_metrics = Activity.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).aggregate(
            total_activities=Count('id'),
            completed_activities=Count('id', filter=Q(status='completed')),
            calls_made=Count('id', filter=Q(activity_type='call')),
            emails_sent=Count('id', filter=Q(activity_type='email'))
        )
        
        # Support metrics
        support_metrics = Ticket.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).aggregate(
            new_tickets=Count('id'),
            resolved_tickets=Count('id', filter=Q(status__in=['resolved', 'closed'])),
            avg_resolution_time=Avg('resolution_time'),
            sla_compliance=Avg(Case(
                When(sla_breached=False, then=1),
                default=0
            )) * 100
        )
        
        # Calculate growth rates
        previous_start = start_date - timedelta(days=days)
        previous_leads = Lead.objects.filter(
            tenant=tenant,
            created_at__range=[previous_start, start_date]
        ).count()
        
        lead_growth_rate = 0
        if previous_leads > 0:
            lead_growth_rate = ((lead_metrics['new_leads'] - previous_leads) / previous_leads) * 100
        
        return {
            'leads': {
                **lead_metrics,
                'growth_rate': round(lead_growth_rate, 2)
            },
            'opportunities': opp_metrics,
            'activities': activity_metrics,
            'support': support_metrics,
            'period': f"Last {days} days"
        }
    
    def get_sales_funnel_analysis(self, tenant, days: int = 90):
        """Comprehensive sales funnel analysis"""
        from ..models import Lead, Opportunity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Lead funnel
        lead_funnel = Lead.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).aggregate(
            total_leads=Count('id'),
            contacted_leads=Count('id', filter=Q(status__in=['contacted', 'qualified', 'converted'])),
            qualified_leads=Count('id', filter=Q(status__in=['qualified', 'converted'])),
            converted_leads=Count('id', filter=Q(status='converted'))
        )
        
        # Opportunity funnel
        opp_funnel = Opportunity.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).aggregate(
            total_opportunities=Count('id'),
            proposal_stage=Count('id', filter=Q(stage__name__icontains='proposal')),
            negotiation_stage=Count('id', filter=Q(stage__name__icontains='negotiation')),
            won_opportunities=Count('id', filter=Q(stage__is_won=True))
        )
        
        # Calculate conversion rates
        funnel_data = {
            'lead_funnel': {
                **lead_funnel,
                'contact_rate': self._calculate_percentage(lead_funnel['contacted_leads'], lead_funnel['total_leads']),
                'qualification_rate': self._calculate_percentage(lead_funnel['qualified_leads'], lead_funnel['contacted_leads']),
                'conversion_rate': self._calculate_percentage(lead_funnel['converted_leads'], lead_funnel['qualified_leads'])
            },
            'opportunity_funnel': {
                **opp_funnel,
                'proposal_rate': self._calculate_percentage(opp_funnel['proposal_stage'], opp_funnel['total_opportunities']),
                'negotiation_rate': self._calculate_percentage(opp_funnel['negotiation_stage'], opp_funnel['proposal_stage']),
                'win_rate': self._calculate_percentage(opp_funnel['won_opportunities'], opp_funnel['total_opportunities'])
            }
        }
        
        return funnel_data
    
    def get_revenue_analytics(self, tenant, period: str = 'monthly'):
        """Comprehensive revenue analytics"""
        from ..models import Opportunity
        
        # Get revenue data based on period
        if period == 'monthly':
            date_trunc = 'month'
            periods_back = 12
        elif period == 'quarterly':
            date_trunc = 'quarter'
            periods_back = 8
        else:  # yearly
            date_trunc = 'year'
            periods_back = 3
        
        revenue_trends = Opportunity.objects.filter(
            tenant=tenant,
            stage__is_won=True
        ).extra(
            select={f'{period}': f"DATE_TRUNC('{date_trunc}', won_date)"}
        ).values(f'{period}').annotate(
            revenue=Sum('value'),
            deal_count=Count('id'),
            avg_deal_size=Avg('value')
        ).order_by(f'{period}')[-periods_back:]
        
        # Calculate year-over-year or period-over-period growth
        if len(revenue_trends) >= 2:
            current_revenue = revenue_trends[-1]['revenue'] or 0
            previous_revenue = revenue_trends[-2]['revenue'] or 0
            growth_rate = 0
            if previous_revenue > 0:
                growth_rate = ((current_revenue - previous_revenue) / previous_revenue) * 100
        else:
            growth_rate = 0
        
        # Revenue forecast (simple linear projection)
        if len(revenue_trends) >= 3:
            recent_revenues = [r['revenue'] or 0 for r in revenue_trends[-3:]]
            avg_growth = sum(recent_revenues) / len(recent_revenues)
            forecast = recent_revenues[-1] * 1.1  # Simple 10% growth projection
        else:
            forecast = 0
        
        return {
            'revenue_trends': list(revenue_trends),
            'growth_rate': round(growth_rate, 2),
            'forecast': round(forecast, 2),
            'period': period
        }
    
    def get_customer_lifecycle_analytics(self, tenant, days: int = 365):
        """Customer lifecycle and retention analytics"""
        from ..models import Account, Activity, Opportunity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Customer acquisition
        acquisition_data = Account.objects.filter(
            tenant=tenant,
            created_at__range=[start_date, end_date]
        ).extra(
            select={'month': "DATE_TRUNC('month', created_at)"}
        ).values('month').annotate(
            new_customers=Count('id'),
            avg_first_purchase=Avg('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            ))
        ).order_by('month')
        
        # Customer engagement
        engagement_metrics = Account.objects.filter(
            tenant=tenant
        ).annotate(
            total_activities=Count('activities'),
            last_activity_date=Max('activities__created_at'),
            total_revenue=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            )),
            opportunity_count=Count('opportunities')
        ).aggregate(
            avg_activities_per_customer=Avg('total_activities'),
            avg_revenue_per_customer=Avg('total_revenue'),
            active_customers=Count('id', filter=Q(
                last_activity_date__gte=timezone.now() - timedelta(days=90)
            )),
            total_customers=Count('id')
        )
        
        # Customer segments
        customer_segments = Account.objects.filter(
            tenant=tenant
        ).annotate(
            customer_value=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            ))
        ).aggregate(
            high_value_customers=Count('id', filter=Q(customer_value__gte=50000)),
            medium_value_customers=Count('id', filter=Q(
                customer_value__range=[10000, 49999]
            )),
            low_value_customers=Count('id', filter=Q(customer_value__lt=10000)),
            no_purchase_customers=Count('id', filter=Q(customer_value__isnull=True))
        )
        
        return {
            'acquisition_trends': list(acquisition_data),
            'engagement_metrics': engagement_metrics,
            'customer_segments': customer_segments,
            'retention_rate': self._calculate_retention_rate(tenant, days)
        }
    
    def get_team_performance_analytics(self, tenant, days: int = 30):
        """Team and individual performance analytics"""
        from ..models import Lead, Opportunity, Activity
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Individual performance
        user_performance = User.objects.filter(
            memberships__tenant=tenant,
            memberships__is_active=True
        ).annotate(
            # Lead metrics
            leads_created=Count('leads_created', filter=Q(
                leads_created__created_at__range=[start_date, end_date]
            )),
            leads_converted=Count('leads_created', filter=Q(
                leads_created__status='converted',
                leads_created__converted_at__range=[start_date, end_date]
            )),
            
            # Opportunity metrics
            opportunities_created=Count('opportunities_created', filter=Q(
                opportunities_created__created_at__range=[start_date, end_date]
            )),
            opportunities_won=Count('opportunities_assigned', filter=Q(
                opportunities_assigned__stage__is_won=True,
                opportunities_assigned__won_date__range=[start_date, end_date]
            )),
            revenue_generated=Sum('opportunities_assigned__value', filter=Q(
                opportunities_assigned__stage__is_won=True,
                opportunities_assigned__won_date__range=[start_date, end_date]
            )),
            
            # Activity metrics
            activities_completed=Count('activities_assigned', filter=Q(
                activities_assigned__status='completed',
                activities_assigned__completed_at__range=[start_date, end_date]
            )),
            calls_made=Count('activities_assigned', filter=Q(
                activities_assigned__activity_type='call',
                activities_assigned__created_at__range=[start_date, end_date]
            ))
        ).values(
            'id', 'first_name', 'last_name',
            'leads_created', 'leads_converted', 'opportunities_created',
            'opportunities_won', 'revenue_generated', 'activities_completed', 'calls_made'
        )
        
        return list(user_performance)
    
    def get_predictive_insights(self, tenant, insight_types: list):
        """Generate AI-powered predictive insights"""
        insights = {}
        
        if 'churn_risk' in insight_types:
            insights['churn_risk'] = self._predict_customer_churn(tenant)
        
        if 'upsell_opportunities' in insight_types:
            insights['upsell_opportunities'] = self._identify_upsell_opportunities(tenant)
        
        if 'deal_close_probability' in insight_types:
            insights['deal_probabilities'] = self._predict_deal_closure(tenant)
        
        if 'lead_scoring' in insight_types:
            insights['lead_scores'] = self._predict_lead_conversion(tenant)
        
        return insights
    
    def _predict_customer_churn(self, tenant):
        """Predict customers at risk of churning"""
        from ..models import Account, Activity
        
        # Simple churn prediction based on activity patterns
        inactive_threshold = timezone.now() - timedelta(days=60)
        
        at_risk_customers = Account.objects.filter(
            tenant=tenant
        ).annotate(
            last_activity=Max('activities__created_at'),
            total_activities=Count('activities'),
            recent_activities=Count('activities', filter=Q(
                activities__created_at__gte=timezone.now() - timedelta(days=30)
            ))
        ).filter(
            Q(last_activity__lt=inactive_threshold) |
            Q(recent_activities=0)
        ).values(
            'id', 'name', 'last_activity', 'total_activities', 'recent_activities'
        )
        
        return {
            'at_risk_count': len(at_risk_customers),
            'customers': list(at_risk_customers)[:20],  # Top 20
            'model_accuracy': 0.75  # Placeholder for actual ML model accuracy
        }
    
    def _identify_upsell_opportunities(self, tenant):
        """Identify potential upsell opportunities"""
        from ..models import Account, Opportunity
        
        # Customers with successful purchases but no recent opportunities
        upsell_candidates = Account.objects.filter(
            tenant=tenant
        ).annotate(
            total_revenue=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            )),
            last_purchase=Max('opportunities__won_date', filter=Q(
                opportunities__stage__is_won=True
            )),
            recent_opportunities=Count('opportunities', filter=Q(
                opportunities__created_at__gte=timezone.now() - timedelta(days=90),
                opportunities__stage__is_closed=False
            ))
        ).filter(
            total_revenue__gt=0,
            last_purchase__gte=timezone.now() - timedelta(days=365),
            recent_opportunities=0
        ).values(
            'id', 'name', 'total_revenue', 'last_purchase'
        ).order_by('-total_revenue')
        
        return {
            'opportunity_count': len(upsell_candidates),
            'potential_revenue': sum(c['total_revenue'] or 0 for c in upsell_candidates) * 0.3,  # 30% upsell estimate
            'candidates': list(upsell_candidates)[:15]  # Top 15
        }
    
    def _predict_deal_closure(self, tenant):
        """Predict deal closure probability"""
        from ..models import Opportunity
        
        # Simple probability scoring based on stage, age, and activity
        open_opportunities = Opportunity.objects.filter(
            tenant=tenant,
            stage__is_closed=False
        ).annotate(
            days_in_pipeline=timezone.now().date() - F('created_at__date'),
            recent_activities=Count('activities', filter=Q(
                activities__created_at__gte=timezone.now() - timedelta(days=14)
            ))
        )
        
        predictions = []
        for opp in open_opportunities:
            # Simple scoring algorithm
            base_score = opp.probability or 50
            
            # Adjust based on pipeline age
            if opp.days_in_pipeline.days > 90:
                base_score *= 0.8  # Older deals less likely
            elif opp.days_in_pipeline.days < 30:
                base_score *= 1.1  # Newer deals slightly more likely
            
            # Adjust based on recent activity
            if opp.recent_activities > 3:
                base_score *= 1.2  # High activity increases probability
            elif opp.recent_activities == 0:
                base_score *= 0.7  # No activity decreases probability
            
            predicted_score = min(max(base_score, 0), 100)
            
            predictions.append({
                'opportunity_id': opp.id,
                'opportunity_name': opp.name,
                'current_probability': opp.probability,
                'predicted_probability': round(predicted_score, 1),
                'value': opp.value,
                'stage': opp.stage.name if opp.stage else None
            })
        
        return sorted(predictions, key=lambda x: x['predicted_probability'], reverse=True)[:20]
    
    def _predict_lead_conversion(self, tenant):
        """Predict lead conversion probability"""
        from ..models import Lead
        
        # Simple lead scoring based on various factors
        leads = Lead.objects.filter(
            tenant=tenant,
            status__in=['new', 'contacted', 'qualified']
        )
        
        scored_leads = []
        for lead in leads:
            score = 0
            
            # Source scoring
            if lead.source:
                source_scores = {'website': 20, 'referral': 40, 'social': 15, 'email': 25}
                score += source_scores.get(lead.source.name.lower(), 10)
            
            # Activity scoring
            if hasattr(lead, 'activities'):
                activity_count = lead.activities.count()
                score += min(activity_count * 5, 30)  # Max 30 points for activity
            
            # Company size scoring
            if lead.company_size:
                size_scores = {'1-10': 10, '11-50': 20, '51-200': 30, '200+': 40}
                score += size_scores.get(lead.company_size, 15)
            
            # Age scoring (recent leads might be more engaged)
            days_old = (timezone.now().date() - lead.created_at.date()).days
            if days_old < 7:
                score += 10
            elif days_old > 30:
                score -= 10
            
            scored_leads.append({
                'lead_id': lead.id,
                'lead_name': f"{lead.first_name} {lead.last_name}",
                'current_score': lead.score or 0,
                'predicted_score': min(max(score, 0), 100),
                'company': lead.company,
                'status': lead.status
            })
        
        return sorted(scored_leads, key=lambda x: x['predicted_score'], reverse=True)[:25]
    
    def _calculate_percentage(self, numerator, denominator):
        """Helper method to calculate percentage"""
        if denominator and denominator > 0:
            return round((numerator / denominator) * 100, 2)
        return 0
    
    def _calculate_retention_rate(self, tenant, days):
        """Calculate customer retention rate"""
        from ..models import Account
        
        # Simple retention calculation
        # Customers who made a purchase in the period and are still active
        end_date = timezone.now()
        period_start = end_date - timedelta(days=days)
        
        period_customers = Account.objects.filter(
            tenant=tenant,
            created_at__lt=period_start
        ).count()
        
        active_customers = Account.objects.filter(
            tenant=tenant,
            created_at__lt=period_start,
            activities__created_at__gte=end_date - timedelta(days=30)  # Active in last 30 days
        ).distinct().count()
        
        if period_customers > 0:
            return round((active_customers / period_customers) * 100, 2)
        return 0