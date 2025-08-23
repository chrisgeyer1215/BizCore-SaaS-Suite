"""
Account Manager - Customer Account Management
Advanced customer relationship and account analytics
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class AccountManager(AnalyticsManager):
    """
    Advanced Account Manager
    Customer account management and analytics
    """
    
    def active_accounts(self):
        """Get active customer accounts"""
        return self.filter(status='active')
    
    def inactive_accounts(self):
        """Get inactive accounts"""
        return self.filter(status='inactive')
    
    def vip_accounts(self):
        """Get VIP/high-value accounts"""
        return self.filter(account_type='vip')
    
    def enterprise_accounts(self):
        """Get enterprise accounts"""
        return self.filter(account_type='enterprise')
    
    def high_value_accounts(self, threshold: Decimal = Decimal('100000')):
        """Get accounts above revenue threshold"""
        return self.annotate(
            total_revenue=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            ))
        ).filter(total_revenue__gte=threshold)
    
    def accounts_with_open_opportunities(self):
        """Get accounts with open opportunities"""
        return self.filter(
            opportunities__stage__is_closed=False
        ).distinct()
    
    def accounts_needing_attention(self, days: int = 30):
        """Get accounts needing attention (no recent activity)"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            Q(last_activity_date__lt=cutoff_date) |
            Q(last_activity_date__isnull=True)
        )
    
    def by_industry(self, industry: str):
        """Filter accounts by industry"""
        return self.filter(industry__name__iexact=industry)
    
    def by_size(self, size: str):
        """Filter accounts by company size"""
        return self.filter(company_size=size)
    
    def by_region(self, region: str):
        """Filter accounts by geographic region"""
        return self.filter(billing_country=region)
    
    def get_account_portfolio_summary(self, tenant, days: int = 30):
        """Get comprehensive account portfolio summary"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).aggregate(
            # Basic metrics
            total_accounts=Count('id'),
            active_accounts=Count('id', filter=Q(status='active')),
            new_accounts=Count('id', filter=Q(
                created_at__range=[start_date, end_date]
            )),
            
            # Revenue metrics
            total_lifetime_value=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            )),
            avg_account_value=Avg('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            )),
            
            # Opportunity metrics
            accounts_with_opportunities=Count('id', filter=Q(
                opportunities__isnull=False
            ), distinct=True),
            avg_opportunities_per_account=Avg('opportunities__count'),
            
            # Activity metrics
            accounts_with_recent_activity=Count('id', filter=Q(
                activities__created_at__gte=start_date
            ), distinct=True),
            avg_activities_per_account=Avg('activities__count'),
            
            # Account types
            enterprise_accounts=Count('id', filter=Q(account_type='enterprise')),
            vip_accounts=Count('id', filter=Q(account_type='vip')),
            standard_accounts=Count('id', filter=Q(account_type='standard'))
        )
    
    def get_account_health_scores(self, tenant):
        """Calculate health scores for all accounts"""
        accounts_with_metrics = self.for_tenant(tenant).annotate(
            # Revenue metrics
            total_revenue=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            )),
            open_pipeline_value=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_closed=False
            )),
            
            # Activity metrics
            recent_activities=Count('activities', filter=Q(
                activities__created_at__gte=timezone.now() - timedelta(days=30)
            )),
            last_activity_days_ago=timezone.now().date() - Max('activities__created_at__date'),
            
            # Opportunity metrics
            open_opportunities=Count('opportunities', filter=Q(
                opportunities__stage__is_closed=False
            )),
            won_opportunities=Count('opportunities', filter=Q(
                opportunities__stage__is_won=True
            )),
            
            # Support metrics
            open_tickets=Count('tickets', filter=Q(
                tickets__status__in=['open', 'pending', 'in_progress']
            )),
            resolved_tickets=Count('tickets', filter=Q(
                tickets__status__in=['resolved', 'closed']
            ))
        )
        
        health_scores = []
        for account in accounts_with_metrics:
            score = self._calculate_account_health_score(account)
            health_scores.append({
                'account_id': account.id,
                'account_name': account.name,
                'health_score': score,
                'health_status': self._get_health_status(score),
                'total_revenue': account.total_revenue or 0,
                'recent_activities': account.recent_activities,
                'open_opportunities': account.open_opportunities
            })
        
        return sorted(health_scores, key=lambda x: x['health_score'], reverse=True)
    
    def _calculate_account_health_score(self, account):
        """Calculate individual account health score (0-100)"""
        score = 0
        
        # Revenue component (30 points)
        if account.total_revenue:
            if account.total_revenue > 100000:
                score += 30
            elif account.total_revenue > 50000:
                score += 25
            elif account.total_revenue > 10000:
                score += 20
            else:
                score += 10
        
        # Activity component (25 points)
        if account.recent_activities:
            if account.recent_activities >= 10:
                score += 25
            elif account.recent_activities >= 5:
                score += 20
            elif account.recent_activities >= 1:
                score += 15
            else:
                score += 5
        
        # Pipeline component (20 points)
        if account.open_opportunities:
            if account.open_opportunities >= 3:
                score += 20
            elif account.open_opportunities >= 1:
                score += 15
            else:
                score += 10
        
        # Support component (15 points)
        if account.open_tickets == 0:
            score += 15
        elif account.open_tickets <= 2:
            score += 10
        else:
            score += 5
        
        # Engagement component (10 points)
        if hasattr(account, 'last_activity_days_ago') and account.last_activity_days_ago:
            if account.last_activity_days_ago.days <= 7:
                score += 10
            elif account.last_activity_days_ago.days <= 30:
                score += 7
            elif account.last_activity_days_ago.days <= 60:
                score += 5
            else:
                score += 2
        
        return min(score, 100)
    
    def _get_health_status(self, score):
        """Convert health score to status"""
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Fair'
        elif score >= 20:
            return 'Poor'
        else:
            return 'Critical'
    
    def get_customer_segmentation(self, tenant):
        """Segment customers based on RFM analysis"""
        # Recency, Frequency, Monetary analysis
        segments = self.for_tenant(tenant).annotate(
            # Recency (days since last purchase)
            last_purchase_date=Max('opportunities__won_date', filter=Q(
                opportunities__stage__is_won=True
            )),
            recency_days=Case(
                When(last_purchase_date__isnull=False, 
                     then=timezone.now().date() - F('last_purchase_date')),
                default=365  # Default high recency for accounts with no purchases
            ),
            
            # Frequency (number of purchases)
            purchase_frequency=Count('opportunities', filter=Q(
                opportunities__stage__is_won=True
            )),
            
            # Monetary (total purchase value)
            total_value=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            ))
        )
        
        # Categorize into segments
        segmented_accounts = []
        for account in segments:
            # Simple RFM scoring (1-5 scale for each dimension)
            recency_score = self._score_recency(account.recency_days.days if account.recency_days else 365)
            frequency_score = self._score_frequency(account.purchase_frequency)
            monetary_score = self._score_monetary(account.total_value or 0)
            
            # Determine segment based on RFM scores
            segment = self._determine_customer_segment(recency_score, frequency_score, monetary_score)
            
            segmented_accounts.append({
                'account_id': account.id,
                'account_name': account.name,
                'segment': segment,
                'recency_score': recency_score,
                'frequency_score': frequency_score,
                'monetary_score': monetary_score,
                'total_value': account.total_value or 0,
                'last_purchase': account.last_purchase_date
            })
        
        # Group by segment
        segment_summary = {}
        for account in segmented_accounts:
            segment = account['segment']
            if segment not in segment_summary:
                segment_summary[segment] = {
                    'count': 0,
                    'total_value': 0,
                    'avg_value': 0,
                    'accounts': []
                }
            
            segment_summary[segment]['count'] += 1
            segment_summary[segment]['total_value'] += account['total_value']
            segment_summary[segment]['accounts'].append(account)
        
        # Calculate averages
        for segment in segment_summary:
            if segment_summary[segment]['count'] > 0:
                segment_summary[segment]['avg_value'] = (
                    segment_summary[segment]['total_value'] / segment_summary[segment]['count']
                )
        
        return segment_summary
    
    def _score_recency(self, days):
        """Score recency (1-5, 5 being most recent)"""
        if days <= 30:
            return 5
        elif days <= 90:
            return 4
        elif days <= 180:
            return 3
        elif days <= 365:
            return 2
        else:
            return 1
    
    def _score_frequency(self, frequency):
        """Score frequency (1-5, 5 being most frequent)"""
        if frequency >= 10:
            return 5
        elif frequency >= 5:
            return 4
        elif frequency >= 3:
            return 3
        elif frequency >= 1:
            return 2
        else:
            return 1
    
    def _score_monetary(self, value):
        """Score monetary value (1-5, 5 being highest value)"""
        if value >= 100000:
            return 5
        elif value >= 50000:
            return 4
        elif value >= 25000:
            return 3
        elif value >= 10000:
            return 2
        elif value > 0:
            return 1
        else:
            return 0
    
    def _determine_customer_segment(self, r_score, f_score, m_score):
        """Determine customer segment based on RFM scores"""
        # High-value segments
        if r_score >= 4 and f_score >= 4 and m_score >= 4:
            return 'Champions'
        elif r_score >= 3 and f_score >= 3 and m_score >= 4:
            return 'Loyal Customers'
        elif r_score >= 4 and f_score <= 2 and m_score >= 4:
            return 'Big Spenders'
        elif r_score >= 4 and f_score >= 3 and m_score <= 3:
            return 'New Customers'
        elif r_score >= 3 and f_score >= 2 and m_score >= 2:
            return 'Potential Loyalists'
        
        # Medium-value segments
        elif r_score >= 2 and f_score >= 2 and m_score >= 2:
            return 'Need Attention'
        elif r_score <= 2 and f_score >= 3 and m_score >= 3:
            return 'At Risk'
        elif r_score <= 2 and f_score >= 4 and m_score >= 4:
            return 'Cannot Lose Them'
        
        # Low-value segments
        elif r_score <= 2 and f_score <= 2 and m_score >= 3:
            return 'Hibernating'
        else:
            return 'Lost'
    
    def get_churn_risk_analysis(self, tenant, days: int = 90):
        """Identify accounts at risk of churning"""
        churn_indicators = self.for_tenant(tenant).annotate(
            days_since_last_activity=timezone.now().date() - Max('activities__created_at__date'),
            days_since_last_purchase=timezone.now().date() - Max('opportunities__won_date', filter=Q(
                opportunities__stage__is_won=True
            )),
            recent_activities=Count('activities', filter=Q(
                activities__created_at__gte=timezone.now() - timedelta(days=30)
            )),
            open_tickets=Count('tickets', filter=Q(
                tickets__status__in=['open', 'pending']
            )),
            total_value=Sum('opportunities__value', filter=Q(
                opportunities__stage__is_won=True
            ))
        )
        
        at_risk_accounts = []
        for account in churn_indicators:
            risk_score = self._calculate_churn_risk_score(account)
            
            if risk_score >= 60:  # High risk threshold
                at_risk_accounts.append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'risk_score': risk_score,
                    'risk_level': self._get_risk_level(risk_score),
                    'days_since_last_activity': account.days_since_last_activity.days if account.days_since_last_activity else None,
                    'total_value': account.total_value or 0,
                    'open_tickets': account.open_tickets,
                    'recommended_actions': self._get_churn_prevention_actions(risk_score, account)
                })
        
        return sorted(at_risk_accounts, key=lambda x: x['risk_score'], reverse=True)
    
    def _calculate_churn_risk_score(self, account):
        """Calculate churn risk score (0-100, higher = more risk)"""
        risk_score = 0
        
        # Activity recency (40 points)
        if account.days_since_last_activity:
            if account.days_since_last_activity.days > 90:
                risk_score += 40
            elif account.days_since_last_activity.days > 60:
                risk_score += 30
            elif account.days_since_last_activity.days > 30:
                risk_score += 20
            else:
                risk_score += 10
        else:
            risk_score += 45  # No activity recorded
        
        # Purchase recency (30 points)
        if account.days_since_last_purchase:
            if account.days_since_last_purchase.days > 365:
                risk_score += 30
            elif account.days_since_last_purchase.days > 180:
                risk_score += 25
            elif account.days_since_last_purchase.days > 90:
                risk_score += 15
            else:
                risk_score += 5
        else:
            risk_score += 35  # No purchases
        
        # Recent activity level (20 points)
        if account.recent_activities == 0:
            risk_score += 20
        elif account.recent_activities <= 2:
            risk_score += 15
        elif account.recent_activities <= 5:
            risk_score += 10
        else:
            risk_score += 0
        
        # Support issues (10 points)
        if account.open_tickets > 3:
            risk_score += 10
        elif account.open_tickets > 1:
            risk_score += 5
        
        return min(risk_score, 100)
    
    def _get_risk_level(self, risk_score):
        """Convert risk score to risk level"""
        if risk_score >= 80:
            return 'Critical'
        elif risk_score >= 60:
            return 'High'
        elif risk_score >= 40:
            return 'Medium'
        else:
            return 'Low'
    
    def _get_churn_prevention_actions(self, risk_score, account):
        """Recommend churn prevention actions"""
        actions = []
        
        if risk_score >= 80:
            actions.append('Schedule immediate executive call')
            actions.append('Offer special retention discount')
            actions.append('Assign dedicated success manager')
        elif risk_score >= 60:
            actions.append('Personal outreach from account manager')
            actions.append('Review and address any open issues')
            actions.append('Schedule value demonstration')
        elif risk_score >= 40:
            actions.append('Send personalized re-engagement email')
            actions.append('Invite to upcoming webinar or event')
            actions.append('Check in on product satisfaction')
        
        # Specific actions based on account attributes
        if account.open_tickets > 0:
            actions.append('Priority resolution of support tickets')
        
        if account.days_since_last_activity and account.days_since_last_activity.days > 60:
            actions.append('Schedule product training session')
        
        return actions
    
    def bulk_update_account_health(self, tenant):
        """Bulk update health scores for all accounts"""
        health_scores = self.get_account_health_scores(tenant)
        updated_count = 0
        
        for account_data in health_scores:
            account = self.get(id=account_data['account_id'])
            account.health_score = account_data['health_score']
            account.health_status = account_data['health_status']
            account.save(update_fields=['health_score', 'health_status', 'modified_at'])
            updated_count += 1
        
        return updated_count