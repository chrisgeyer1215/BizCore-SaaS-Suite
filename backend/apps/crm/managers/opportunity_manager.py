"""
Opportunity Manager - Sales Pipeline Management
Advanced opportunity tracking and forecasting
"""

from django.db.models import Q, Count, Sum, Avg, Case, When, DecimalField, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class OpportunityManager(AnalyticsManager):
    """
    Advanced Opportunity Manager
    Sales pipeline and forecasting functionality
    """
    
    def open_opportunities(self):
        """Get all open opportunities"""
        return self.filter(stage__is_closed=False)
    
    def won_opportunities(self):
        """Get won opportunities"""
        return self.filter(stage__is_won=True)
    
    def lost_opportunities(self):
        """Get lost opportunities"""
        return self.filter(stage__is_lost=True)
    
    def closing_this_month(self):
        """Opportunities closing this month"""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        return self.filter(
            close_date__range=[month_start, month_end],
            stage__is_closed=False
        )
    
    def closing_this_quarter(self):
        """Opportunities closing this quarter"""
        today = timezone.now().date()
        quarter = (today.month - 1) // 3 + 1
        quarter_start = today.replace(month=(quarter-1)*3+1, day=1)
        quarter_end = (quarter_start + timedelta(days=93)).replace(day=1) - timedelta(days=1)
        
        return self.filter(
            close_date__range=[quarter_start, quarter_end],
            stage__is_closed=False
        )
    
    def overdue_opportunities(self):
        """Opportunities past their close date"""
        return self.filter(
            close_date__lt=timezone.now().date(),
            stage__is_closed=False
        )
    
    def high_value_opportunities(self, threshold: Decimal = Decimal('50000')):
        """Opportunities above value threshold"""
        return self.filter(value__gte=threshold)
    
    def by_stage(self, stage_name: str):
        """Filter by pipeline stage"""
        return self.filter(stage__name__iexact=stage_name)
    
    def by_probability_range(self, min_prob: int = 0, max_prob: int = 100):
        """Filter by probability range"""
        return self.filter(probability__range=[min_prob, max_prob])
    
    def assigned_to_user(self, user):
        """Opportunities assigned to specific user"""
        return self.filter(assigned_to=user)
    
    def get_pipeline_summary(self, tenant, date_range: int = 30):
        """Get comprehensive pipeline summary"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=date_range)
        
        base_queryset = self.for_tenant(tenant)
        period_queryset = base_queryset.filter(
            created_at__range=[start_date, end_date]
        )
        
        return base_queryset.aggregate(
            # Overall pipeline metrics
            total_opportunities=Count('id'),
            total_pipeline_value=Sum('value', filter=Q(stage__is_closed=False)),
            total_won_value=Sum('value', filter=Q(stage__is_won=True)),
            total_lost_value=Sum('value', filter=Q(stage__is_lost=True)),
            
            # Period-specific metrics
            new_opportunities=Count('id', filter=Q(created_at__range=[start_date, end_date])),
            won_this_period=Count('id', filter=Q(
                won_date__range=[start_date, end_date],
                stage__is_won=True
            )),
            
            # Averages
            avg_opportunity_value=Avg('value'),
            avg_days_to_close=Avg('days_to_close', filter=Q(stage__is_closed=True)),
            avg_probability=Avg('probability', filter=Q(stage__is_closed=False)),
            
            # Win rates
            overall_win_rate=Case(
                When(
                    id__in=base_queryset.filter(stage__is_closed=True).values('id'),
                    then=Avg(Case(
                        When(stage__is_won=True, then=1),
                        default=0,
                        output_field=DecimalField()
                    )) * 100
                ),
                default=0,
                output_field=DecimalField()
            )
        )
    
    def get_pipeline_by_stage(self, tenant):
        """Get pipeline breakdown by stage"""
        return self.for_tenant(tenant).filter(
            stage__is_closed=False
        ).values(
            'stage__name',
            'stage__order',
            'stage__probability'
        ).annotate(
            opportunity_count=Count('id'),
            total_value=Sum('value'),
            avg_value=Avg('value'),
            avg_days_in_stage=Avg('days_in_current_stage')
        ).order_by('stage__order')
    
    def get_forecast_data(self, tenant, forecast_type: str = 'quarterly'):
        """
        Generate forecast data
        forecast_type: 'monthly', 'quarterly', 'yearly'
        """
        if forecast_type == 'quarterly':
            return self._get_quarterly_forecast(tenant)
        elif forecast_type == 'monthly':
            return self._get_monthly_forecast(tenant)
        elif forecast_type == 'yearly':
            return self._get_yearly_forecast(tenant)
    
    def _get_quarterly_forecast(self, tenant):
        """Generate quarterly forecast"""
        today = timezone.now().date()
        
        # Current quarter
        current_quarter = (today.month - 1) // 3 + 1
        quarter_start = today.replace(month=(current_quarter-1)*3+1, day=1)
        quarter_end = (quarter_start + timedelta(days=93)).replace(day=1) - timedelta(days=1)
        
        opportunities = self.for_tenant(tenant).filter(
            close_date__range=[quarter_start, quarter_end],
            stage__is_closed=False
        )
        
        return opportunities.aggregate(
            # Forecast calculations
            best_case=Sum('value'),
            most_likely=Sum(
                F('value') * F('probability') / 100,
                output_field=DecimalField()
            ),
            worst_case=Sum(
                F('value') * F('probability') / 100 * Decimal('0.7'),
                output_field=DecimalField()
            ),
            
            # Supporting data
            opportunity_count=Count('id'),
            avg_probability=Avg('probability'),
            total_weighted_value=Sum(
                F('value') * F('probability') / 100,
                output_field=DecimalField()
            )
        )
    
    def get_conversion_rates(self, tenant, days: int = 90):
        """Calculate stage-to-stage conversion rates"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all stage transitions in the period
        from ..models import Activity
        stage_changes = Activity.objects.filter(
            tenant=tenant,
            activity_type='stage_change',
            created_at__range=[start_date, end_date],
            opportunity__isnull=False
        ).values(
            'details__from_stage',
            'details__to_stage'
        ).annotate(
            transition_count=Count('id')
        )
        
        # Calculate conversion rates between stages
        conversion_data = {}
        for change in stage_changes:
            from_stage = change['details__from_stage']
            to_stage = change['details__to_stage']
            count = change['transition_count']
            
            if from_stage not {}
            
            conversion_data[from_stage][to_stage] = count
        
        return conversion_data
    
    def get_sales_velocity(self, tenant, days: int = 90):
        """Calculate sales velocity metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        won_opportunities = self.for_tenant(tenant).filter(
            won_date__range=[start_date, end_date],
            stage__is_won=True
        )
        
        if not won_opportunities.exists():
            return None
        
        metrics = won_opportunities.aggregate(
            total_deals=Count('id'),
            total_value=Sum('value'),
            avg_deal_size=Avg('value'),
            avg_days_to_close=Avg('days_to_close'),
            total_opportunities_created=Count('id', filter=Q(
                created_at__range=[start_date, end_date]
            ))
        )
        
        # Calculate velocity: (Number of Deals × Average Deal Size × Win Rate) / Sales Cycle Length
        win_rate = (metrics['total_deals'] / metrics['total_opportunities_created']) * 100 if metrics['total_opportunities_created'] > 0 else 0
        
        velocity = 0
        if metrics['avg_days_to_close'] and metrics['avg_days_to_close'] > 0:
            velocity = (metrics['total_deals'] * metrics['avg_deal_size'] * win_rate / 100) / metrics['avg_days_to_close']
        
        return {
            **metrics,
            'win_rate': round(win_rate, 2),
            'sales_velocity': round(velocity, 2),
            'period_days': days
        }
    
    def get_rep_performance(self, tenant, days: int = 90):
        """Get sales rep performance metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            assigned_to__isnull=False
        ).values(
            'assigned_to__first_name',
            'assigned_to__last_name',
            'assigned_to__id'
        ).annotate(
            # Opportunity metrics
            total_opportunities=Count('id'),
            won_opportunities=Count('id', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            )),
            lost_opportunities=Count('id', filter=Q(
                stage__is_lost=True,
                lost_date__range=[start_date, end_date]
            )),
            
            # Revenue metrics
            total_revenue=Sum('value', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            )),
            avg_deal_size=Avg('value', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            )),
            
            # Pipeline metrics
            active_pipeline_value=Sum('value', filter=Q(stage__is_closed=False)),
            avg_days_to_close=Avg('days_to_close', filter=Q(
                stage__is_won=True,
                won_date__range=[start_date, end_date]
            ))
        ).order_by('-total_revenue')
    
    def identify_at_risk_opportunities(self, tenant):
        """Identify opportunities at risk of being lost"""
        today = timezone.now().date()
        
        at_risk_opportunities = self.for_tenant(tenant).filter(
            stage__is_closed=False
        ).filter(
            Q(close_date__lt=today) |  # Overdue
            Q(
                last_activity_date__lt=today - timedelta(days=14),
                probability__lt=50
            ) |  # No activity + low probability
            Q(
                days_in_current_stage__gt=30,
                stage__name__in=['Proposal', 'Negotiation']
            )  # Stuck in late stages
        )
        
        return at_risk_opportunities.order_by('close_date', '-value')
    
    def bulk_update_probabilities(self, stage_probability_mapping: Dict[str, int]):
        """Bulk update probabilities based on stage mapping"""
        updated_count = 0
        
        for stage_name, probability in stage_probability_mapping.items():
            count = self.filter(
                stage__name=stage_name,
                stage__is_closed=False
            ).update(probability=probability)
            updated_count += count
        
        return updated_count
    
    def auto_advance_stale_opportunities(self, tenant, rules: Dict):
        """
        Auto-advance opportunities that have been in a stage too long
        
        rules format:
        {
            'stage_name': {'days_threshold': 30, 'action': 'advance'|'mark_lost'},
            ...
        }
        """
        today = timezone.now().date()
        actions_taken = []
        
        for stage_name, rule in rules.items():
            threshold_date = today - timedelta(days=rule['days_threshold'])
            
            stale_opps = self.for_tenant(tenant).filter(
                stage__name=stage_name,
                stage__is_closed=False,
                stage_changed_date__lt=threshold_date
            )
            
            if rule['action'] == 'advance':
                # Logic to advance to next stage
                # This would require knowledge of your pipeline stage sequence
                pass
            elif rule['action'] == 'mark_lost':
                count = stale_opps.update(
                    stage_id=self._get_lost_stage_id(),
                    lost_date=today,
                    lost_reason='Stale - auto-marked lost'
                )
                actions_taken.append({
                    'stage': stage_name,
                    'action': 'marked_lost',
                    'count': count
                })
        
        return actions_taken