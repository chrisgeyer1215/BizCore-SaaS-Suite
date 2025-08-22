# ============================================================================
# backend/apps/crm/services/ticket_service.py - Comprehensive Ticket Management
# ============================================================================

from django.db import transaction
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Max
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Optional
import statistics
from collections import defaultdict

from .base import BaseService, ServiceException
from ..models import Ticket, TicketCategory, SLA, TicketComment, KnowledgeBase


class TicketService(BaseService):
    """Comprehensive ticket management with AI-powered support and automation"""
    
    def create_intelligent_ticket(self, ticket_data: Dict, auto_assign: bool = True,
                                auto_categorize: bool = True, auto_priority: bool = True) -> Ticket:
        """Create ticket with intelligent auto-assignment, categorization, and prioritization"""
        try:
            with transaction.atomic():
                # AI-powered categorization
                if auto_categorize and not ticket_data.get('category'):
                    suggested_category = self.suggest_ticket_category(
                        subject=ticket_data.get('subject', ''),
                        description=ticket_data.get('description', '')
                    )
                    if suggested_category:
                        ticket_data['category'] = suggested_category
                
                # AI-powered priority assessment
                if auto_priority and not ticket_data.get('priority'):
                    suggested_priority = self.assess_ticket_priority(ticket_data)
                    ticket_data['priority'] = suggested_priority
                
                # Create ticket
                ticket = Ticket.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **ticket_data
                )
                
                # Auto-assign ticket
                if auto_assign:
                    assigned_agent = self.intelligent_ticket_assignment(ticket)
                    if assigned_agent:
                        ticket.assigned_to = assigned_agent
                        ticket.save()
                
                # Set SLA based on priority and category
                self.set_sla_deadlines(ticket)
                
                # Auto-suggest knowledge base articles
                suggested_articles = self.suggest_knowledge_base_articles(ticket)
                if suggested_articles:
                    self.create_ticket_comment(
                        ticket, 
                        f"Suggested articles: {', '.join([a.title for a in suggested_articles[:3]])}",
                        comment_type='SYSTEM_SUGGESTION'
                    )
                
                # Initialize ticket tracking
                self.initialize_ticket_tracking(ticket)
                
                # Send notifications
                self.send_ticket_notifications(ticket, 'created')
                
                self.log_activity('CREATE_TICKET', 'Ticket', ticket.id, {
                    'ticket_number': ticket.ticket_number,
                    'priority': ticket.priority,
                    'auto_assigned': assigned_agent is not None,
                    'suggested_category': suggested_category.name if auto_categorize and suggested_category else None
                })
                
                return ticket
                
        except Exception as e:
            raise ServiceException(f"Failed to create intelligent ticket: {str(e)}")
    
    def suggest_ticket_category(self, subject: str, description: str) -> Optional['TicketCategory']:
        """AI-powered ticket categorization based on content analysis"""
        try:
            # Combine subject and description for analysis
            content = f"{subject} {description}".lower()
            
            # Get all categories with their keywords
            categories = TicketCategory.objects.filter(tenant=self.tenant, is_active=True)
            
            category_scores = {}
            
            for category in categories:
                score = 0
                
                # Analyze category name match
                if category.name.lower() in content:
                    score += 50
                
                # Keyword matching (this would be more sophisticated in production)
                keyword_mappings = {
                    'technical': ['bug', 'error', 'crash', 'broken', 'not working', 'technical', 'system'],
                    'billing': ['payment', 'invoice', 'charge', 'billing', 'refund', 'subscription'],
                    'account': ['login', 'password', 'account', 'access', 'permission', 'user'],
                    'feature': ['feature', 'enhancement', 'improvement', 'suggestion', 'request'],
                    'general': ['question', 'help', 'how to', 'general', 'inquiry']
                }
                
                for keyword_category, keywords in keyword_mappings.items():
                    if keyword_category in category.name.lower():
                        for keyword in keywords:
                            if keyword in content:
                                score += 10
                
                # Historical categorization patterns
                similar_tickets = Ticket.objects.filter(
                    category=category,
                    tenant=self.tenant
                ).filter(
                    Q(subject__icontains=subject[:20]) |
                    Q(description__icontains=description[:50])
                ).count()
                
                score += similar_tickets * 5
                
                category_scores[category] = score
            
            # Return category with highest score if above threshold
            if category_scores:
                best_category = max(category_scores.items(), key=lambda x: x[1])
                if best_category[1] > 30:  # Confidence threshold
                    return best_category[0]
            
        except Exception as e:
            logger.warning(f"Failed to suggest ticket category: {e}")
        
        return None
    
    def assess_ticket_priority:
        """Assess ticket priority using AI analysis"""
        priority_score = 0
        
        subject = ticket_data.get('subject', '').lower()
        description = ticket_data.get('description', '').lower()
        content = f"{subject} {description}"
        
        # Critical keywords
        critical_keywords = ['critical', 'urgent', 'down', 'outage', 'crash', 'security', 'breach']
        high_keywords = ['important', 'broken', 'error', 'bug', 'issue', 'problem']
        medium_keywords = ['question', 'help', 'support', 'assistance']
        
        for keyword in critical_keywords:
            if keyword in content:
                priority_score += 40
        
        for keyword in high_keywords:
            if keyword in content:
                priority_score += 20
        
        for keyword in medium_keywords:
            if keyword in content:
                priority_score += 10
        
        # Account-based priority boost
        if ticket_data.get('account'):
            account = ticket_data['account']
            if hasattr(account, 'account_type'):
                if account.account_type == 'ENTERPRISE':
                    priority_score += 30
                elif account.account_type == 'PREMIUM':
                    priority_score += 20
        
        # Time sensitivity indicators
        time_sensitive_words = ['asap', 'immediately', 'today', 'now', 'urgent']
        for word in time_sensitive_words:
            if word in content:
                priority_score += 15
        
        # Return priority based on score
        if priority_score >= 80:
            return 'CRITICAL'
        elif priority_score >= 50:
            return 'HIGH'
        elif priority_score >= 20:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def intelligent_ticket_assignment(self, ticket: Ticket) -> Optional['User']:
        """Intelligent ticket assignment based on workload, expertise, and availability"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get available support agents
            support_agents = User.objects.filter(
                tenant_memberships__tenant=self.tenant,
                tenant_memberships__is_active=True,
                crm_profile__role__name__in=['SUPPORT_AGENT', 'MANAGER', 'ADMIN']
            )
            
            if not support_agents.exists():
                return None
            
            # Score each agent
            agent_scores = {}
            
            for agent in support_agents:
                score = 100  # Base score
                
                # Workload factor
                current_tickets = Ticket.objects.filter(
                    assigned_to=agent,
                    status__in=['OPEN', 'IN_PROGRESS'],
                    tenant=self.tenant
                ).count()
                
                # Penalty for high workload
                score -= current_tickets * 10
                
                # Expertise factor
                category_expertise = self.get_agent_category_expertise(agent, ticket.category)
                score += category_expertise
                
                # Priority handling experience
                priority_experience = self.get_agent_priority_experience(agent, ticket.priority)
                score += priority_experience
                
                # Recent performance factor
                recent_performance = self.get_agent_recent_performance(agent)
                score += recent_performance
                
                # Availability factor (working hours, time zone)
                availability_score = self.calculate_agent_availability(agent)
                score *= availability_score
                
                agent_scores[agent] = max(0, score)
            
            # Return agent with highest score
            if agent_scores:
                best_agent = max(agent_scores.items(), key=lambda x: x[1])
                return best_agent[0]
            
        except Exception as e:
            logger.warning(f"Failed to assign ticket intelligently: {e}")
        
        return None
    
    def get_agent_category_expertise(self, agent, category) -> int:
        """Calculate agent's expertise in handling specific category"""
        if not category:
            return 0
        
        # Count resolved tickets in this category
        resolved_in_category = Ticket.objects.filter(
            assigned_to=agent,
            category=category,
            status='RESOLVED',
            tenant=self.tenant
        ).count()
        
        # Calculate average resolution time
        avg_resolution_time = Ticket.objects.filter(
            assigned_to=agent,
            category=category,
            status='RESOLVED',
            tenant=self.tenant,
            resolved_date__isnull=False
        ).aggregate(
            avg_time=Avg(F('resolved_date') - F('created_at'))
        )['avg_time']
        
        expertise_score = resolved_in_category * 5
        
        # Bonus for fast resolution
        if avg_resolution_time:
            avg_hours = avg_resolution_time.total_seconds() / 3600
            if avg_hours < 24:
                expertise_score += 20
            elif avg_hours < 48:
                expertise_score += 10
        
        return min(50, expertise_score)
    
    def resolve_ticket_with_intelligence(self, ticket: Ticket, resolution_data: Dict,
                                       auto_learn: bool = True) -> Ticket:
        """Resolve ticket with intelligent learning and knowledge base updates"""
        self.validate_tenant_access(ticket)
        
        try:
            with transaction.atomic():
                # Update ticket
                ticket.status = 'RESOLVED'
                ticket.resolved_date = timezone.now()
                ticket.resolution = resolution_data.get('resolution', '')
                ticket.resolution_type = resolution_data.get('resolution_type', 'SOLVED')
                
                # Calculate resolution time
                if ticket.created_at:
                    resolution_time = ticket.resolved_date - ticket.created_at
                    ticket.resolution_time_hours = resolution_time.total_seconds() / 3600
                
                ticket.save()
                
                # Add resolution comment
                self.create_ticket_comment(
                    ticket,
                    f"Ticket resolved: {resolution_data.get('resolution', '')}",
                    comment_type='RESOLUTION'
                )
                
                # Auto-learn from resolution
                if auto_learn:
                    self.learn_from_ticket_resolution(ticket, resolution_data)
                
                # Update SLA compliance
                self.check_sla_compliance(ticket)
                
                # Update agent performance metrics
                self.update_agent_performance_metrics(ticket)
                
                # Send notifications
                self.send_ticket_notifications(ticket, 'resolved')
                
                # Auto-create knowledge base article if valuable
                if resolution_data.get('create_kb_article'):
                    self.auto_create_knowledge_article(ticket, resolution_data)
                
                self.log_activity('RESOLVE_TICKET', 'Ticket', ticket.id, {
                    'resolution_time_hours': ticket.resolution_time_hours,
                    'resolution_type': ticket.resolution_type,
                    'sla_met': not ticket.sla_breached
                })
                
                return ticket
                
        except Exception as e:
            raise ServiceException(f"Failed to resolve ticket: {str(e)}")
    
    def learn_from_ticket_resolution(self, ticket: Ticket, resolution to improve future automation"""
        try:
            # Update category prediction model
            self.update_categorization_model(ticket)
            
            # Update priority assessment model
            self.update_priority_model(ticket)
            
            # Update assignment algorithm
            self.update_assignment_algorithm(ticket)
            
            # Identify common patterns
            self.identify_resolution_patterns(ticket, resolution_data)
            
        except Exception as e:
            logger.warning(f"Failed to learn from ticket resolution: {e}")
    
    def auto_create_):
        """Automatically create knowledge base article from ticket resolution"""
        try:
            # Check if this is a valuable resolution to document
            if self.should_create_kb_article(ticket):
                article_data = {
                    'title': f"How to resolve: {ticket.subject}",
                    'content': self.generate_kb_article_content(ticket, resolution_data),
                    'category': ticket.category,
                    'tags': self.generate_kb_tags(ticket),
                    'article_type': 'SOLUTION',
                    'status': 'DRAFT'  # Require review before publishing
                }
                
                KnowledgeBase.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **article_data
                )
                
                logger.info(f"Auto-created KB article for ticket {ticket.ticket_number}")
                
        except Exception as e:
            logger.warning(f"Failed to auto-create KB article: {e}")
    
    def should_create_kb_article(self, ticket: Ticket) -> bool:
        """Determine if ticket resolution should become a KB article"""
        # Check if similar tickets exist
        similar_tickets = Ticket.objects.filter(
            tenant=self.tenant,
            category=ticket.category,
            status='RESOLVED'
        ).filter(
            Q(subject__icontains=ticket.subject[:20]) |
            Q(description__icontains=ticket.description[:50])
        ).count()
        
        # Create article if we see recurring issues
        return similar_tickets >= 3
    
    def get_comprehensive_ticket_analytics(self, date_from=None, date_to=None,
                                         include_predictions: bool = True) -> Dict:
        """Get comprehensive ticket analytics with AI insights"""
        queryset = Ticket.objects.filter(tenant=self.tenant)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        analytics = {
            'volume_metrics': self.get_ticket_volume_metrics(queryset),
            'performance_metrics': self.get_performance_metrics(queryset),
            'sla_metrics': self.get_sla_metrics(queryset),
            'agent_performance': self.get_agent_performance_metrics(queryset),
            'category_analysis': self.get_category_analysis(queryset),
            'trend_analysis': self.get_ticket_trend_analysis(queryset),
            'customer_satisfaction': self.get_satisfaction_metrics(queryset)
        }
        
        if include_predictions:
            analytics['predictions'] = {
                'volume_forecast': self.predict_ticket_volume(),
                'workload_forecast': self.predict_agent_workload(),
                'escalation_risks': self.predict_escalation_risks(),
                'sla_risk_assessment': self.assess_sla_risks()
            }
        
        return analytics
    
    def predict_ticket_volume(self) -> Dict:
        """Predict future ticket volume based on historical patterns"""
        try:
            # Analyze historical patterns
            historical_data = Ticket.objects.filter(
                tenant=self.tenant,
                created_at__gte=timezone.now() - timedelta(days=90)
            ).extra({
                'day': 'date(created_at)'
            }).values('day').annotate(
                count=Count('id')
            ).order_by('day')
            
            if len(historical_data) < 30:
                return {'error': 'Insufficient historical data'}
            
            # Simple trend analysis (in production, use proper forecasting models)
            daily_counts = [item['count'] for item in historical_data]
            avg_daily = statistics.mean(daily_counts)
            trend = (daily_counts[-7:] - daily_counts[:7]) / 7  # Weekly trend
            
            # Predict next 30 days
            predictions = []
            for i in range(1, 31):
                predicted_volume = avg_daily + (trend * i)
                predictions.append({
                    'date': (timezone.now().date() + timedelta(days=i)).isoformat(),
                    'predicted_volume': max(0, int(predicted_volume)),
                    'confidence': max(0.5, 1 - (i * 0.02))  # Decreasing confidence over time
                })
            
            return {
                'daily_average': avg_daily,
                'trend': 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
                'predictions': predictions
            }
            
        except Exception as e:
            logger.warning(f"Failed to predict ticket volume: {e}")
            return {'error': str(e)}
    
    def predict_escalation_risks(self) -> List[Dict]:
        """Predict which tickets are at risk of escalation"""
        at_risk_tickets = []
        
        try:
            # Get open tickets
            open_tickets = Ticket.objects.filter(
                tenant=self.tenant,
                status__in=['OPEN', 'IN_PROGRESS']
            )
            
            for ticket in open_tickets:
                risk_score = 0
                risk_factors = []
                
                # Age factor
                age_hours = (timezone.now() - ticket.created_at).total_seconds() / 3600
                if age_hours > 48:
                    risk_score += 30
                    risk_factors.append('Ticket age > 48 hours')
                elif age_hours > 24:
                    risk_score += 15
                    risk_factors.append('Ticket age > 24 hours')
                
                # Priority factor
                if ticket.priority in ['CRITICAL', 'HIGH']:
                    risk_score += 25
                    risk_factors.append(f'{ticket.priority} priority')
                
                # SLA factor
                if ticket.sla_breached:
                    risk_score += 40
                    risk_factors.append('SLA already breached')
                elif self.is_approaching_sla_breach(ticket):
                    risk_score += 20
                    risk_factors.append('Approaching SLA deadline')
                
                # Customer type factor
                if ticket.account and hasattr(ticket.account, 'account_type'):
                    if ticket.account.account_type == 'ENTERPRISE':
                        risk_score += 15
                        risk_factors.append('Enterprise customer')
                
                # Comment activity factor
                recent_comments = ticket.comments.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
                
                if recent_comments == 0 and age_hours > 12:
                    risk_score += 10
                    risk_factors.append('No recent activity')
                
                # Add to at-risk list if score is high enough
                if risk_score >= 40:
                    at_risk_tickets.append({
                        'ticket_id': ticket.id,
                        'ticket_number': ticket.ticket_number,
                        'risk_score': risk_score,
                        'risk_factors': risk_factors,
                        'recommended_actions': self.get_risk_mitigation_actions(risk_score, risk_factors)
                    })
            
            # Sort by risk score
            at_risk_tickets.sort(key=lambda x: x['risk_score'], reverse=True)
            
        except Exception as e:
            logger.warning(f"Failed to predict escalation risks: {e}")
        
        return at_risk_tickets
    
    # Helper methods for ticket service
    def set_sla_deadlines(self, ticket: Ticket):
        """Set SLA deadlines based on priority and category"""
        try:
            sla = SLA.objects.filter(
                category=ticket.category,
                priority=ticket.priority,
                tenant=self.tenant,
                is_active=True
            ).first()
            
            if sla:
                ticket.sla = sla
                ticket.due_date = ticket.created_at + timedelta(hours=sla.response_time_hours)
                ticket.escalation_date = ticket.created_at + timedelta(hours=sla.resolution_time_hours * 0.8)
                ticket.save()
                
        except Exception as e:
            logger.warning(f"Failed to set SLA deadlines: {e}")
    
    def create_ticket_comment(self, ticket: Ticket, content: str, comment_type: str = 'COMMENT'):
        """Create ticket comment with proper logging"""
        return TicketComment.objects.create(
            ticket=ticket,
            comment=content,
            comment_type=comment_type,
            tenant=self.tenant,
            created_by=self.user
        )

