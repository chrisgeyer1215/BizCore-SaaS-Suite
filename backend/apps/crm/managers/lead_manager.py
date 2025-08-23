"""
Lead Manager - Advanced Lead Management Queries
Handles lead qualification, scoring, and assignment logic
"""

from django.db.models import Q, Count, Sum, Avg, Case, When, IntegerField, F
from django.utils import timezone
from datetime import timedelta
from typing import List, Dict, Optional
from .base import AnalyticsManager


class LeadManager(AnalyticsManager):
    """
    Advanced Lead Manager
    Provides lead-specific queries and business logic
    """
    
    def qualified_leads(self):
        """Get qualified leads only"""
        return self.filter(status='qualified')
    
    def unqualified_leads(self):
        """Get unqualified leads"""
        return self.filter(status='unqualified')
    
    def new_leads(self):
        """Get new/uncontacted leads"""
        return self.filter(status='new')
    
    def hot_leads(self):
        """Get high-priority/hot leads"""
        return self.filter(
            Q(priority='high') | Q(score__gte=80)
        )
    
    def cold_leads(self, days: int = 30):
        """Get leads with no recent activity"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            Q(last_activity_date__lt=cutoff_date) | 
            Q(last_activity_date__isnull=True)
        )
    
    def by_source(self, source: str):
        """Filter leads by source"""
        return self.filter(source__name__iexact=source)
    
    def by_score_range(self, min_score: int = 0, max_score: int = 100):
        """Filter leads by score range"""
        return self.filter(score__range=[min_score, max_score])
    
    def assigned_to_user(self, user):
        """Get leads assigned to specific user"""
        return self.filter(assigned_to=user)
    
    def unassigned_leads(self):
        """Get unassigned leads"""
        return self.filter(assigned_to__isnull=True)
    
    def overdue_leads(self):
        """Get leads with overdue follow-up dates"""
        return self.filter(
            next_follow_up_date__lt=timezone.now(),
            status__in=['new', 'contacted', 'qualified']
        )
    
    def get_lead_sources_performance(self, tenant, days: int = 30):
        """Analyze performance by lead source"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).values(
            'source__name'
        ).annotate(
            total_leads=Count('id'),
            qualified_leads=Count('id', filter=Q(status='qualified')),
            converted_leads=Count('id', filter=Q(status='converted')),
            avg_score=Avg('score'),
            avg_qualification_time=Avg('qualification_time')
        ).order_by('-total_leads')
    
    def get_conversion_funnel(self, tenant, days: int = 30):
        """Get lead conversion funnel data"""
        stages = ['new', 'contacted', 'qualified', 'converted', 'lost']
        return self.get_funnel_data(tenant, stages, days)
    
    def get_scoring_distribution(self, tenant):
        """Get lead scoring distribution"""
        return self.for_tenant(tenant).aggregate(
            score_0_20=Count('id', filter=Q(score__range=[0, 20])),
            score_21_40=Count('id', filter=Q(score__range=[21, 40])),
            score_41_60=Count('id', filter=Q(score__range=[41, 60])),
            score_61_80=Count('id', filter=Q(score__range=[61, 80])),
            score_81_100=Count('id', filter=Q(score__range=[81, 100])),
            avg_score=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score')
        )
    
    def leads_requiring_attention(self, user=None):
        """Get leads requiring immediate attention"""
        queryset = self.filter(
            Q(priority='high') |
            Q(next_follow_up_date__lte=timezone.now()) |
            Q(score__gte=80, status='new') |
            Q(last_activity_date__lt=timezone.now() - timedelta(days=7))
        )
        
        if user:
            queryset = queryset.filter(assigned_to=user)
        
        return queryset.order_by('-priority', '-score', 'next_follow_up_date')
    
    def get_lead_velocity(self, tenant, days: int = 30):
        """Calculate average time from lead creation to qualification"""
        qualified_leads = self.for_tenant(tenant).filter(
            status='qualified',
            qualified_at__isnull=False
        )
        
        if not qualified_leads.exists():
            return None
        
        velocity_data = qualified_leads.aggregate(
            avg_qualification_days=Avg(
                F('qualified_at') - F('created_at'),
                output_field=DurationField()
            ),
            total_qualified=Count('id')
        )
        
        return velocity_data
    
    def get_assignment_workload(self, tenant):
        """Get lead assignment workload by user"""
        return self.for_tenant(tenant).filter(
            assigned_to__isnull=False,
            status__in=['new', 'contacted', 'qualified']
        ).values(
            'assigned_to__first_name',
            'assigned_to__last_name',
            'assigned_to__id'
        ).annotate(
            active_leads=Count('id'),
            high_priority_leads=Count('id', filter=Q(priority='high')),
            avg_score=Avg('score'),
            overdue_leads=Count('id', filter=Q(next_follow_up_date__lt=timezone.now()))
        ).order_by('-active_leads')
    
    def auto_assign_leads(self, lead_ids: List[int], assignment_rules: Dict):
        """
        Auto-assign leads based on rules
        
        assignment_rules format:
        {
            'method': 'round_robin' | 'least_loaded' | 'by_territory',
            'users': [user_ids],
            'territory_mapping': {territory_id: [user_ids]},
            'criteria': {...}
        }
        """
        leads_to_assign = self.filter(id__in=lead_ids, assigned_to__isnull=True)
        
        if assignment_rules['method'] == 'round_robin':
            return self._round_robin_assignment(leads_to_assign, assignment_rules['users'])
        elif assignment_rules['method'] == 'least_loaded':
            return self._least_loaded_assignment(leads_to_assign, assignment_rules['users'])
        elif assignment_rules['method'] == 'by_territory':
            return self._territory_based_assignment(leads_to_assign, assignment_rules['territory_mapping'])
        
        return {'assigned': 0, 'errors': ['Invalid assignment method']}
    
    def _round_robin_assignment(self, leads, users):
        """Round-robin lead assignment"""
        if not users:
            return {'assigned': 0, 'errors': ['No users provided']}
        
        assigned_count = 0
        user_index = 0
        
        for lead in leads:
            user_id = users[user_index % len(users)]
            lead.assigned_to_id = user_id
            lead.assigned_at = timezone.now()
            lead.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
            
            assigned_count += 1
            user_index += 1
        
        return {'assigned': assigned_count, 'errors': []}
    
    def _least_loaded_assignment(self, leads, users):
        """Assign to user with least active leads"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get current workload for each user
        workloads = {}
        for user_id in users:
            workload = self.filter(
                assigned_to_id=user_id,
                status__in=['new', 'contacted', 'qualified']
            ).count()
            workloads[user_id] = workload
        
        assigned_count = 0
        
        for lead in leads:
            # Find user with minimum workload
            min_user_id = min(workloads, key=workloads.get)
            
            lead.assigned_to_id = min_user_id
            lead.assigned_at = timezone.now()
            lead.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
            
            # Update workload count
            workloads[min_user_id] += 1
            assigned_count += 1
        
        return {'assigned': assigned_count, 'errors': []}
    
    def _territory_based_assignment(self, leads, territory_mapping):
        """Assign leads based on territory mapping"""
        assigned_count = 0
        errors = []
        
        for lead in leads:
            territory_id = getattr(lead, 'territory_id', None)
            
            if territory_id and territory_id in territory_mapping:
                available_users = territory_mapping[territory_id]
                if available_users:
                    # Use round-robin within territory
                    user_id = available_users[assigned_count % len(available_users)]
                    lead.assigned_to_id = user_id
                    lead.assigned_at = timezone.now()
                    lead.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
                    assigned_count += 1
                else:
                    errors.append(f"No users available for territory {territory_id}")
            else:
                errors.append(f"Lead {lead.id} has no territory or unmapped territory")
        
        return {'assigned': assigned_count, 'errors': errors}
    
    def calculate_lead_scores(self, tenant, score_rules: Dict):
        """
        Recalculate lead scores based on rules
        
        score_rules format:
        {
            'source_scores': {'website': 10, 'referral': 20, ...},
            'company_size_scores': {'1-10': 5, '11-50': 15, ...},
            'activity_multipliers': {'email_open': 1.1, 'website_visit': 1.2},
            'demographic_scores': {...}
        }
        """
        leads = self.for_tenant(tenant).filter(status__in=['new', 'contacted'])
        updated_count = 0
        
        for lead in leads:
            new_score = self._calculate_individual_score(lead, score_rules)
            
            if new_score != lead.score:
                lead.score = new_score
                lead.score_updated_at = timezone.now()
                lead.save(update_fields=['score', 'score_updated_at', 'modified_at'])
                updated_count += 1
        
        return {'updated_count': updated_count}
    
    def _calculate_individual_score(self, lead, rules):
        """Calculate score for individual lead"""
        score = 0
        
        # Source score
        if lead.source and rules.get('source_scores'):
            score += rules['source_scores'].get(lead.source.name, 0)
        
        # Company size score
        if lead.company_size and rules.get('company_size_scores'):
            score += rules['company_size_scores'].get(lead.company_size, 0)
        
        # Add other scoring logic based on lead attributes
        # This would be customized based on your specific scoring criteria
        
        return min(max(score, 0), 100)  # Keep score between 0-100