"""
Ticket Manager - Customer Support Management
Advanced ticket handling, SLA tracking, and support analytics
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from .base import AnalyticsManager


class TicketManager(AnalyticsManager):
    """
    Advanced Ticket Manager
    Customer support ticket management and analytics
    """
    
    def open_tickets(self):
        """Get open tickets"""
        return self.filter(status__in=['open', 'pending', 'in_progress'])
    
    def closed_tickets(self):
        """Get closed/resolved tickets"""
        return self.filter(status__in=['closed', 'resolved'])
    
    def high_priority_tickets(self):
        """Get high priority tickets"""
        return self.filter(priority='high')
    
    def critical_tickets(self):
        """Get critical priority tickets"""
        return self.filter(priority='critical')
    
    def overdue_tickets(self):
        """Get tickets that are overdue based on SLA"""
        return self.filter(
            sla_due_date__lt=timezone.now(),
            status__in=['open', 'pending', 'in_progress']
        )
    
    def escalated_tickets(self):
        """Get escalated tickets"""
        return self.filter(is_escalated=True)
    
    def unassigned_tickets(self):
        """Get unassigned tickets"""
        return self.filter(assigned_to__isnull=True)
    
    def by_category(self, category):
        """Filter tickets by category"""
        return self.filter(category=category)
    
    def by_agent(self, agent):
        """Get tickets assigned to specific agent"""
        return self.filter(assigned_to=agent)
    
    def by_customer(self, customer):
        """Get tickets for specific customer"""
        return self.filter(customer=customer)
    
    def first_response_pending(self):
        """Get tickets awaiting first response"""
        return self.filter(
            first_response_at__isnull=True,
            status='open'
        )
    
    def get_support_metrics(self, tenant, days: int = 30):
        """Get comprehensive support metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        period_tickets = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        return period_tickets.aggregate(
            # Volume metrics
            total_tickets=Count('id'),
            open_tickets=Count('id', filter=Q(status__in=['open', 'pending', 'in_progress'])),
            closed_tickets=Count('id', filter=Q(status__in=['closed', 'resolved'])),
            
            # Priority distribution
            critical_tickets=Count('id', filter=Q(priority='critical')),
            high_priority_tickets=Count('id', filter=Q(priority='high')),
            medium_priority_tickets=Count('id', filter=Q(priority='medium')),
            low_priority_tickets=Count('id', filter=Q(priority='low')),
            
            # SLA metrics
            overdue_tickets=Count('id', filter=Q(
                sla_due_date__lt=timezone.now(),
                status__in=['open', 'pending', 'in_progress']
            )),
            sla_breached_tickets=Count('id', filter=Q(sla_breached=True)),
            
            # Response time metrics
            avg_first_response_time=Avg('first_response_time'),
            avg_resolution_time=Avg('resolution_time', filter=Q(
                status__in=['closed', 'resolved']
            )),
            
            # Agent metrics
            avg_agent_response_time=Avg('agent_response_time'),
            escalated_tickets=Count('id', filter=Q(is_escalated=True)),
            
            # Customer satisfaction
            avg_satisfaction_rating=Avg('satisfaction_rating', filter=Q(
                satisfaction_rating__isnull=False
            )),
            total_rated_tickets=Count('id', filter=Q(
                satisfaction_rating__isnull=False
            ))
        )
    
    def get_sla_performance(self, tenant, days: int = 30):
        """Analyze SLA performance metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        tickets = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        # Calculate SLA compliance by priority
        sla_metrics = tickets.values('priority').annotate(
            total_tickets=Count('id'),
            sla_met=Count('id', filter=Q(sla_breached=False)),
            sla_breached=Count('id', filter=Q(sla_breached=True)),
            avg_response_time=Avg('first_response_time'),
            avg_resolution_time=Avg('resolution_time'),
            compliance_rate=Case(
                When(id__isnull=False, then=Avg(Case(
                    When(sla_breached=False, then=1),
                    default=0
                )) * 100),
                default=0
            )
        ).order_by('priority')
        
        return list(sla_metrics)
    
    def get_agent_performance(self, tenant, days: int = 30):
        """Get agent performance metrics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            assigned_to__isnull=False,
            created_at__range=[start_date, end_date]
        ).values(
            'assigned_to__first_name',
            'assigned_to__last_name',
            'assigned_to__id'
        ).annotate(
            # Ticket volume
            total_tickets=Count('id'),
            open_tickets=Count('id', filter=Q(status__in=['open', 'pending', 'in_progress'])),
            closed_tickets=Count('id', filter=Q(status__in=['closed', 'resolved'])),
            
            # Performance metrics
            avg_first_response_time=Avg('first_response_time'),
            avg_resolution_time=Avg('resolution_time', filter=Q(
                status__in=['closed', 'resolved']
            )),
            
            # Quality metrics
            avg_satisfaction_rating=Avg('satisfaction_rating', filter=Q(
                satisfaction_rating__isnull=False
            )),
            escalated_count=Count('id', filter=Q(is_escalated=True)),
            
            # SLA metrics
            sla_breaches=Count('id', filter=Q(sla_breached=True)),
            sla_compliance_rate=Case(
                When(id__isnull=False, then=Avg(Case(
                    When(sla_breached=False, then=1),
                    default=0
                )) * 100),
                default=0
            ),
            
            # Productivity
            resolution_rate=Case(
                When(id__isnull=False, then=Avg(Case(
                    When(status__in=['closed', 'resolved'], then=1),
                    default=0
                )) * 100),
                default=0
            )
        ).order_by('-total_tickets')
    
    def get_category_analysis(self, tenant, days: int = 30):
        """Analyze tickets by category"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).values(
            'category__name'
        ).annotate(
            ticket_count=Count('id'),
            avg_resolution_time=Avg('resolution_time'),
            avg_satisfaction=Avg('satisfaction_rating'),
            escalation_rate=Avg(Case(
                When(is_escalated=True, then=1),
                default=0
            )) * 100,
            sla_breach_rate=Avg(Case(
                When(sla_breached=True, then=1),
                default=0
            )) * 100
        ).order_by('-ticket_count')
    
    def get_customer_satisfaction_trends(self, tenant, days: int = 90):
        """Analyze customer satisfaction trends"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Daily satisfaction ratings
        daily_satisfaction = self.for_tenant(tenant).filter(
            resolved_at__range=[start_date, end_date],
            satisfaction_rating__isnull=False
        ).extra(
            select={'day': 'date(resolved_at)'}
        ).values('day').annotate(
            avg_rating=Avg('satisfaction_rating'),
            total_ratings=Count('id'),
            excellent_count=Count('id', filter=Q(satisfaction_rating__gte=4.5)),
            poor_count=Count('id', filter=Q(satisfaction_rating__lte=2.0))
        ).order_by('day')
        
        return list(daily_satisfaction)
    
    def identify_escalation_triggers(self, tenant, days: int = 30):
        """Identify common escalation triggers"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        escalated_tickets = self.for_tenant(tenant).filter(
            is_escalated=True,
            escalated_at__range=[start_date, end_date]
        )
        
        triggers = escalated_tickets.aggregate(
            sla_breach_escalations=Count('id', filter=Q(
                sla_breached=True,
                escalation_reason__icontains='sla'
            )),
            customer_request_escalations=Count('id', filter=Q(
                escalation_reason__icontains='customer'
            )),
            complexity_escalations=Count('id', filter=Q(
                escalation_reason__icontains='complex'
            )),
            agent_request_escalations=Count('id', filter=Q(
                escalation_reason__icontains='agent'
            )),
            total_escalations=Count('id')
        )
        
        # Most common categories for escalation
        category_escalations = escalated_tickets.values(
            'category__name'
        ).annotate(
            escalation_count=Count('id'),
            escalation_rate=Count('id') * 100.0 / Count('category__tickets')
        ).order_by('-escalation_count')
        
        return {
            'trigger_analysis': triggers,
            'category_escalations': list(category_escalations)
        }
    
    def auto_assign_tickets(self, assignment_rules: dict):
        """
        Auto-assign unassigned tickets based on rules
        
        assignment_rules format:
        {
            'method': 'round_robin' | 'least_loaded' | 'skill_based',
            'agents': [agent_ids],
            'skill_mapping': {category_id: [agent_ids]},
            'workload_limits': {agent_id: max_tickets}
        }
        """
        unassigned = self.filter(assigned_to__isnull=True, status='open')
        
        if assignment_rules['method'] == 'round_robin':
            return self._round_robin_ticket_assignment(unassigned, assignment_rules['agents'])
        elif assignment_rules['method'] == 'least_loaded':
            return self._least_loaded_ticket_assignment(unassigned, assignment_rules['agents'])
        elif assignment_rules['method'] == 'skill_based':
            return self._skill_based_assignment(unassigned, assignment_rules['skill_mapping'])
        
        return {'assigned': 0, 'errors': ['Invalid assignment method']}
    
    def _round_robin_ticket_assignment(self, tickets, agents):
        """Round-robin ticket assignment"""
        if not agents:
            return {'assigned': 0, 'errors': ['No agents provided']}
        
        assigned_count = 0
        agent_index = 0
        
        for ticket in tickets:
            agent_id = agents[agent_index % len(agents)]
            ticket.assigned_to_id = agent_id
            ticket.assigned_at = timezone.now()
            ticket.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
            
            assigned_count += 1
            agent_index += 1
        
        return {'assigned': assigned_count, 'errors': []}
    
    def _least_loaded_ticket_assignment(self, tickets, agents):
        """Assign to agent with least open tickets"""
        # Get current workload for each agent
        workloads = {}
        for agent_id in agents:
            workload = self.filter(
                assigned_to_id=agent_id,
                status__in=['open', 'pending', 'in_progress']
            ).count()
            workloads[agent_id] = workload
        
        assigned_count = 0
        
        for ticket in tickets:
            # Find agent with minimum workload
            min_agent_id = min(workloads, key=workloads.get)
            
            ticket.assigned_to_id = min_agent_id
            ticket.assigned_at = timezone.now()
            ticket.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
            
            # Update workload count
            workloads[min_agent_id] += 1
            assigned_count += 1
        
        return {'assigned': assigned_count, 'errors': []}
    
    def _skill_based_assignment(self, tickets, skill_mapping):
        """Assign tickets based on agent skills/expertise"""
        assigned_count = 0
        errors = []
        
        for ticket in tickets:
            category_id = ticket.category_id
            
            if category_id and category_id in skill_mapping:
                available_agents = skill_mapping[category_id]
                if available_agents:
                    # Use least loaded within skilled agents
                    workloads = {}
                    for agent_id in available_agents:
                        workload = self.filter(
                            assigned_to_id=agent_id,
                            status__in=['open', 'pending', 'in_progress']
                        ).count()
                        workloads[agent_id] = workload
                    
                    min_agent_id = min(workloads, key=workloads.get)
                    ticket.assigned_to_id = min_agent_id
                    ticket.assigned_at = timezone.now()
                    ticket.save(update_fields=['assigned_to', 'assigned_at', 'modified_at'])
                    assigned_count += 1
                else:
                    errors.append(f"No skilled agents available for category {category_id}")
            else:
                errors.append(f"Ticket {ticket.id} has no category or unmapped category")
        
        return {'assigned': assigned_count, 'errors': errors}
    
    def bulk_escalate_overdue_tickets(self, tenant, escalation_rules: dict):
        """
        Bulk escalate overdue tickets
        
        escalation_rules format:
        {
            'sla_overdue_hours': 4,
            'escalate_to': manager_id,
            'priority_escalation': {'high': 2, 'critical': 1},  # hours overdue
            'notification_recipients': [user_ids]
        }
        """
        now = timezone.now()
        escalated_tickets = []
        
        # Find overdue tickets based on priority
        for priority, hours_threshold in escalation_rules.get('priority_escalation', {}).items():
            threshold_time = now - timedelta(hours=hours_threshold)
            
            overdue_tickets = self.for_tenant(tenant).filter(
                priority=priority,
                sla_due_date__lt=threshold_time,
                status__in=['open', 'pending', 'in_progress'],
                is_escalated=False
            )
            
            # Escalate these tickets
            escalated_count = overdue_tickets.update(
                is_escalated=True,
                escalated_at=now,
                escalation_reason=f'SLA breach - {hours_threshold}+ hours overdue',
                escalated_to_id=escalation_rules.get('escalate_to')
            )
            
            escalated_tickets.append({
                'priority': priority,
                'escalated_count': escalated_count,
                'threshold_hours': hours_threshold
            })
        
        return {
            'escalation_results': escalated_tickets,
            'total_escalated': sum(result['escalated_count'] for result in escalated_tickets)
        }
    
    def generate_sla_report(self, tenant, days: int = 30):
        """Generate comprehensive SLA performance report"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        tickets = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        # Overall SLA metrics
        overall_metrics = tickets.aggregate(
            total_tickets=Count('id'),
            sla_met_count=Count('id', filter=Q(sla_breached=False)),
            sla_breached_count=Count('id', filter=Q(sla_breached=True)),
            avg_first_response_time=Avg('first_response_time'),
            avg_resolution_time=Avg('resolution_time'),
            overall_compliance_rate=Avg(Case(
                When(sla_breached=False, then=1),
                default=0
            )) * 100
        )
        
        # SLA by priority
        priority_sla = tickets.values('priority').annotate(
            ticket_count=Count('id'),
            sla_compliance_rate=Avg(Case(
                When(sla_breached=False, then=1),
                default=0
            )) * 100,
            avg_response_time=Avg('first_response_time'),
            avg_resolution_time=Avg('resolution_time')
        ).order_by('priority')
        
        # SLA by agent
        agent_sla = tickets.filter(
            assigned_to__isnull=False
        ).values(
            'assigned_to__first_name',
            'assigned_to__last_name'
        ).annotate(
            ticket_count=Count('id'),
            sla_compliance_rate=Avg(Case(
                When(sla_breached=False, then=1),
                default=0
            )) * 100,
            avg_response_time=Avg('first_response_time')
        ).order_by('-sla_compliance_rate')
        
        return {
            'overall_metrics': overall_metrics,
            'priority_breakdown': list(priority_sla),
            'agent_performance': list(agent_sla),
            'report_period': f"{start_date.date()} to {end_date.date()}"
        }