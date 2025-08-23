"""
Automated Reminder System Management Command
Intelligent reminder processing with smart scheduling and personalization.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, F, Count, Min, Max
from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMultiAlternatives
from django.contrib.auth import get_user_model

from crm.models.lead_model import Lead
from crm.models.account_model import Account, Contact
from crm.models.opportunity_model import Opportunity
from crm.models.activity_model import Activity, ActivityType
from crm.models.ticket_model import Ticket
from crm.models.user_model import CRMUserProfile
from crm.services.activity_service import ActivityService
from crm.services.notification_service import NotificationService

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send intelligent reminders for follow-ups, tasks, and deadlines'

    def add_arguments(self, parser):
        # Reminder types
        parser.add_argument(
            '--type',
            choices=[
                'follow_ups', 'overdue_tasks', 'opportunity_deadlines',
                'lead_nurturing', 'ticket_sla', 'all'
            ],
            help='Type of reminders to send',
            default='all'
        )
        
        # Time-based options
        parser.add_argument(
            '--days-ahead',
            type=int,
            help='Days ahead to look for upcoming items',
            default=7
        )
        
        parser.add_argument(
            '--overdue-days',
            type=int,
            help='Days overdue to consider for reminders',
            default=3
        )
        
        # Delivery options
        parser.add_argument(
            '--method',
            choices=['email', 'in_app', 'both'],
            help='Reminder delivery method',
            default='both'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of reminders to send in each batch',
            default=50
        )
        
        # Filtering options
        parser.add_argument(
            '--user-ids',
            type=str,
            help='Comma-separated user IDs to send reminders to',
            default=None
        )
        
        parser.add_argument(
            '--priority',
            choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
            help='Only send reminders for items with this priority or higher',
            default=None
        )
        
        # Behavior options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview reminders without sending',
        )
        
        parser.add_argument(
            '--skip-weekend',
            action='store_true',
            help='Skip sending reminders on weekends',
        )
        
        parser.add_argument(
            '--smart-timing',
            action='store_true',
            help='Use intelligent timing based on user preferences',
        )
        
        parser.add_argument(
            '--personalized',
            action='store_true',
            help='Create personalized reminder content',
        )

    def handle(self, *args, **options):
        try:
            self.activity_service = ActivityService()
            self.notification_service = NotificationService()
            
            self.send_reminders(**options)
            
        except Exception as e:
            logger.error(f"Reminder processing failed: {str(e)}")
            raise CommandError(f'Reminder processing failed: {str(e)}')

    def send_reminders(self, **options):
        """Main reminder orchestrator"""
        reminder_type = options['type']
        
        self.stdout.write('📨 Starting intelligent reminder processing...')
        
        # Check if we should skip weekend sending
        if options['skip_weekend'] and self._is_weekend():
            self.stdout.write('⏭️ Skipping weekend reminder sending')
            return
        
        # Get users to process
        users_to_process = self._get_users_to_process(options)
        
        if not users_to_process:
            self.stdout.write('⚠️ No users found for reminder processing')
            return
        
        # Process reminders by type
        reminder_results = {}
        
        if reminder_type == 'all':
            types = ['follow_ups', 'overdue_tasks', 'opportunity_deadlines', 
                    'lead_nurturing', 'ticket_sla']
        else:
            types = [reminder_type]
        
        for rtype in types:
            self.stdout.write(f'\n🔔 Processing {rtype} reminders...')
            
            try:
                if rtype == 'follow_ups':
                    result = self._process_follow_up_reminders(users_to_process, options)
                elif rtype == 'overdue_tasks':
                    result = self._process_overdue_task_reminders(users_to_process, options)
                elif rtype == 'opportunity_deadlines':
                    result = self._process_opportunity_deadline_reminders(users_to_process, options)
                elif rtype == 'lead_nurturing':
                    result = self._process_lead_nurturing_reminders(users_to_process, options)
                elif rtype == 'ticket_sla':
                    result = self._process_ticket_sla_reminders(users_to_process, options)
                
                reminder_results[rtype] = result
                
            except Exception as e:
                logger.error(f"Failed to process {rtype} reminders: {str(e)}")
                reminder_results[rtype] = {'error': str(e)}
        
        # Print comprehensive summary
        self._print_reminder_summary(reminder_results, options)

    def _get_users_to_process(self, options: Dict) -> List[CRMUserProfile]:
        """Get list of users to send reminders to"""
        queryset = CRMUserProfile.objects.filter(
            user__is_active=True,
            receive_reminders=True
        ).select_related('user')
        
        # Filter by specific user IDs if provided
        if options['user_ids']:
            try:
                user_ids = [int(uid.strip()) for uid in options['user_ids'].split(',')]
                queryset = queryset.filter(user__id__in=user_ids)
            except ValueError:
                raise CommandError('Invalid user IDs format. Use comma-separated integers.')
        
        # Consider user timezone and preferences if smart timing is enabled
        if options['smart_timing']:
            # Filter users who should receive reminders at this time
            current_hour = timezone.now().hour
            queryset = queryset.filter(
                Q(preferred_reminder_time__isnull=True) |  # No preference = anytime
                Q(preferred_reminder_time__hour=current_hour)
            )
        
        return list(queryset)

    def _process_follow_up_reminders(self, users: List[CRMUserProfile], options: Dict) -> Dict:
        """Process follow-up reminders for activities and leads"""
        results = {
            'users_processed': 0,
            'reminders_sent': 0,
            'reminders_created': 0,
            'errors': 0
        }
        
        for user in users:
            try:
                # Find leads that need follow-up
                leads_needing_followup = self._find_leads_needing_followup(user, options)
                
                # Find overdue activities
                overdue_activities = self._find_overdue_activities(user, options)
                
                # Find upcoming activities that need preparation
                upcoming_activities = self._find_upcoming_activities(user, options)
                
                if leads_needing_followup or overdue_activities or upcoming_activities:
                    reminder_sent = self._send_follow_up_reminder(
                        user, 
                        leads_needing_followup, 
                        overdue_activities,
                        upcoming_activities,
                        options
                    )
                    
                    if reminder_sent:
                        results['reminders_sent'] += 1
                    results['reminders_created'] += 1
                
                results['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing follow-up reminders for user {user.id}: {str(e)}")
                results['errors'] += 1
        
        return results

    def _find_leads_needing_followup(self, user: CRMUserProfile, options: Dict) -> List[Lead]:
        """Find leads that need follow-up action"""
        days_ahead = options['days_ahead']
        
        # Calculate follow-up dates based on lead activity
        cutoff_date = timezone.now() - timedelta(days=3)  # No activity in 3 days
        
        leads = Lead.objects.filter(
            assigned_to=user,
            status__in=['NEW', 'CONTACTED', 'QUALIFIED'],
            is_deleted=False
        ).filter(
            Q(last_activity_date__lt=cutoff_date) |
            Q(last_activity_date__isnull=True)
        )
        
        # Prioritize hot leads
        hot_leads = leads.filter(score__gte=70).order_by('-score')[:5]
        warm_leads = leads.filter(score__gte=40, score__lt=70).order_by('-score')[:3]
        
        return list(hot_leads) + list(warm_leads)

    def _find_overdue_activities(self, user: CRMUserProfile, options: Dict) -> List[Activity]:
        """Find overdue activities for the user"""
        overdue_cutoff = timezone.now() - timedelta(days=options.get('overdue_days', 1))
        
        return list(Activity.objects.filter(
            assigned_to=user,
            status__in=['SCHEDULED', 'IN_PROGRESS'],
            scheduled_at__lt=overdue_cutoff,
            is_deleted=False
        ).select_related('activity_type', 'related_lead', 'related_opportunity')[:10])

    def _find_upcoming_activities(self, user: CRMUserProfile, options: Dict) -> List[Activity]:
        """Find upcoming activities that need preparation"""
        upcoming_start = timezone.now()
        upcoming_end = timezone.now() + timedelta(days=options['days_ahead'])
        
        return list(Activity.objects.filter(
            assigned_to=user,
            status='SCHEDULED',
            scheduled_at__range=[upcoming_start, upcoming_end],
            activity_type__name__in=['Meeting', 'Demo', 'Presentation'],  # Activities that need prep
            is_deleted=False
        ).select_related('activity_type', 'related_lead', 'related_opportunity')[:5])

    def _send_follow_up_reminder(self, user: CRMUserProfile, leads: List[Lead], 
                                overdue: List[Activity], upcoming: List[Activity], 
                                options: Dict) -> bool:
        """Send comprehensive follow-up reminder to user"""
        if options['dry_run']:
            self.stdout.write(
                f'  [DRY RUN] Would send follow-up reminder to {user.user.email} '
                f'({len(leads)} leads, {len(overdue)} overdue, {len(upcoming)} upcoming)'
            )
            return True
        
        # Prepare reminder content
        context = {
            'user': user,
            'leads_needing_followup': leads,
            'overdue_activities': overdue,
            'upcoming_activities': upcoming,
            'total_items': len(leads) + len(overdue) + len(upcoming),
        }
        
        # Add personalization if requested
        if options['personalized']:
            context.update(self._get_personalization_data(user))
        
        # Send email reminder
        if options['method'] in ['email', 'both']:
            success = self._send_email_reminder(
                user, 'follow_up_reminder', context, options
            )
            
            if not success:
                return False
        
        # Send in-app notification
        if options['method'] in ['in_app', 'both']:
            self._send_in_app_notification(user, 'follow_up_reminder', context)
        
        return True

    def _process_overdue_task_reminders(self, users: List[CRMUserProfile], options: Dict) -> Dict:
        """Process overdue task reminders"""
        results = {
            'users_processed': 0,
            'reminders_sent': 0,
            'tasks_found': 0,
            'errors': 0
        }
        
        overdue_cutoff = timezone.now() - timedelta(hours=2)  # 2 hours overdue
        
        for user in users:
            try:
                # Find overdue tasks
                overdue_tasks = Activity.objects.filter(
                    assigned_to=user,
                    activity_type__name='Task',
                    status__in=['SCHEDULED', 'IN_PROGRESS'],
                    scheduled_at__lt=overdue_cutoff,
                    is_deleted=False
                ).select_related('related_lead', 'related_opportunity', 'related_account')
                
                # Apply priority filter if specified
                if options['priority']:
                    priority_order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
                    min_priority_index = priority_order.index(options['priority'])
                    allowed_priorities = priority_order[min_priority_index:]
                    overdue_tasks = overdue_tasks.filter(priority__in=allowed_priorities)
                
                overdue_tasks = list(overdue_tasks[:10])  # Limit to 10 most overdue
                
                if overdue_tasks:
                    results['tasks_found'] += len(overdue_tasks)
                    
                    if self._send_overdue_task_reminder(user, overdue_tasks, options):
                        results['reminders_sent'] += 1
                
                results['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing overdue task reminders for user {user.id}: {str(e)}")
                results['errors'] += 1
        
        return results

    def _send_overdue_task_reminder(self, user: CRMUserProfile, 
                                  overdue_tasks: List[Activity], options: Dict) -> bool:
        """Send overdue task reminder"""
        if options['dry_run']:
            self.stdout.write(
                f'  [DRY RUN] Would send overdue task reminder to {user.user.email} '
                f'({len(overdue_tasks)} tasks)'
            )
            return True
        
        # Group tasks by priority
        critical_tasks = [t for t in overdue_tasks if t.priority == 'CRITICAL']
        high_tasks = [t for t in overdue_tasks if t.priority == 'HIGH']
        other_tasks = [t for t in overdue_tasks if t.priority not in ['CRITICAL', 'HIGH']]
        
        context = {
            'user': user,
            'critical_tasks': critical_tasks,
            'high_tasks': high_tasks,
            'other_tasks': other_tasks,
            'total_overdue': len(overdue_tasks),
        }
        
        # Add urgency-based messaging
        if critical_tasks:
            context['urgency_level'] = 'CRITICAL'
            context['urgency_message'] = 'You have critical overdue tasks that require immediate attention!'
        elif high_tasks:
            context['urgency_level'] = 'HIGH'
            context['urgency_message'] = 'You have high-priority overdue tasks.'
        else:
            context['urgency_level'] = 'MEDIUM'
            context['urgency_message'] = 'You have overdue tasks to complete.'
        
        # Send notifications
        if options['method'] in ['email', 'both']:
            success = self._send_email_reminder(user, 'overdue_tasks', context, options)
            if not success:
                return False
        
        if options['method'] in ['in_app', 'both']:
            self._send_in_app_notification(user, 'overdue_tasks', context)
        
        return True

    def _process_opportunity_deadline_reminders(self, users: List[CRMUserProfile], options: Dict) -> Dict:
        """Process opportunity deadline reminders"""
        results = {
            'users_processed': 0,
            'reminders_sent': 0,
            'opportunities_found': 0,
            'errors': 0
        }
        
        # Look for opportunities closing soon
        upcoming_deadline = timezone.now() + timedelta(days=options['days_ahead'])
        
        for user in users:
            try:
                # Find opportunities with approaching close dates
                approaching_opportunities = Opportunity.objects.filter(
                    assigned_to=user,
                    stage__stage_type='OPEN',
                    expected_close_date__lte=upcoming_deadline,
                    expected_close_date__gte=timezone.now(),
                    is_deleted=False
                ).select_related('account', 'stage').order_by('expected_close_date')
                
                # Find stale opportunities (no recent activity)
                stale_cutoff = timezone.now() - timedelta(days=7)
                stale_opportunities = Opportunity.objects.filter(
                    assigned_to=user,
                    stage__stage_type='OPEN',
                    updated_at__lt=stale_cutoff,
                    is_deleted=False
                ).select_related('account', 'stage').order_by('-value')[:5]
                
                approaching_opportunities = list(approaching_opportunities[:5])
                stale_opportunities = list(stale_opportunities)
                
                if approaching_opportunities or stale_opportunities:
                    results['opportunities_found'] += len(approaching_opportunities) + len(stale_opportunities)
                    
                    if self._send_opportunity_deadline_reminder(
                        user, approaching_opportunities, stale_opportunities, options
                    ):
                        results['reminders_sent'] += 1
                
                results['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing opportunity deadline reminders for user {user.id}: {str(e)}")
                results['errors'] += 1
        
        return results

    def _send_opportunity_deadline_reminder(self, user: CRMUserProfile, 
                                          approaching: List[Opportunity],
                                          stale: List[Opportunity], 
                                          options: Dict) -> bool:
        """Send opportunity deadline reminder"""
        if options['dry_run']:
            self.stdout.write(
                f'  [DRY RUN] Would send opportunity deadline reminder to {user.user.email} '
                f'({len(approaching)} approaching, {len(stale)} stale)'
            )
            return True
        
        # Calculate total potential revenue at risk
        approaching_value = sum(opp.value or 0 for opp in approaching)
        stale_value = sum(opp.value or 0 for opp in stale)
        
        context = {
            'user': user,
            'approaching_opportunities': approaching,
            'stale_opportunities': stale,
            'approaching_value': approaching_value,
            'stale_value': stale_value,
            'total_at_risk': approaching_value + stale_value,
        }
        
        # Add recommended actions
        context['recommended_actions'] = self._get_opportunity_recommendations(
            approaching + stale
        )
        
        # Send notifications
        if options['method'] in ['email', 'both']:
            success = self._send_email_reminder(user, 'opportunity_deadlines', context, options)
            if not success:
                return False
        
        if options['method'] in ['in_app', 'both']:
            self._send_in_app_notification(user, 'opportunity_deadlines', context)
        
        return True

    def _process_lead_nurturing_reminders(self, users: List[CRMUserProfile], options: Dict) -> Dict:
        """Process automated lead nurturing reminders"""
        results = {
            'users_processed': 0,
            'reminders_sent': 0,
            'leads_found': 0,
            'nurturing_sequences': 0,
            'errors': 0
        }
        
        for user in users:
            try:
                # Find leads in different nurturing stages
                nurturing_leads = self._identify_nurturing_opportunities(user, options)
                
                if nurturing_leads:
                    results['leads_found'] += sum(len(leads) for leads in nurturing_leads.values())
                    results['nurturing_sequences'] += len(nurturing_leads)
                    
                    if self._send_lead_nurturing_reminder(user, nurturing_leads, options):
                        results['reminders_sent'] += 1
                
                results['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing lead nurturing reminders for user {user.id}: {str(e)}")
                results['errors'] += 1
        
        return results

    def _identify_nurturing_opportunities(self, user: CRMUserProfile, options: Dict) -> Dict:
        """Identify leads that need different types of nurturing"""
        nurturing_opportunities = {}
        
        # New leads (first contact needed)
        new_leads = Lead.objects.filter(
            assigned_to=user,
            status='NEW',
            created_at__gte=timezone.now() - timedelta(hours=24),
            is_deleted=False
        )[:5]
        
        if new_leads:
            nurturing_opportunities['new_lead_welcome'] = list(new_leads)
        
        # Warm leads (re-engagement needed)
        warm_leads = Lead.objects.filter(
            assigned_to=user,
            status='CONTACTED',
            score__gte=40,
            last_activity_date__lt=timezone.now() - timedelta(days=5),
            is_deleted=False
        ).order_by('-score')[:3]
        
        if warm_leads:
            nurturing_opportunities['warm_lead_reengagement'] = list(warm_leads)
        
        # Cold leads (value-add content)
        cold_leads = Lead.objects.filter(
            assigned_to=user,
            status='CONTACTED',
            score__lt=40,
            last_activity_date__lt=timezone.now() - timedelta(days=14),
            is_deleted=False
        ).order_by('-created_at')[:3]
        
        if cold_leads:
            nurturing_opportunities['cold_lead_nurturing'] = list(cold_leads)
        
        return nurturing_opportunities

    def _send_lead_nurturing_reminder(self, user: CRMUserProfile, 
                                    nurturing_leads: Dict, options: Dict) -> bool:
        """Send lead nurturing reminder with suggested actions"""
        if options['dry_run']:
            total_leads = sum(len(leads) for leads in nurturing_leads.values())
            self.stdout.write(
                f'  [DRY RUN] Would send lead nurturing reminder to {user.user.email} '
                f'({total_leads} leads in {len(nurturing_leads)} sequences)'
            )
            return True
        
        context = {
            'user': user,
            'nurturing_opportunities': nurturing_leads,
            'total_leads': sum(len(leads) for leads in nurturing_leads.values()),
        }
        
        # Add nurturing suggestions for each category
        suggestions = {}
        
        if 'new_lead_welcome' in nurturing_leads:
            suggestions['new_lead_welcome'] = [
                'Send personalized welcome email',
                'Schedule discovery call',
                'Share relevant case study'
            ]
        
        if 'warm_lead_reengagement' in nurturing_leads:
            suggestions['warm_lead_reengagement'] = [
                'Share industry insights',
                'Invite to upcoming webinar',
                'Schedule product demo'
            ]
        
        if 'cold_lead_nurturing' in nurturing_leads:
            suggestions['cold_lead_nurturing'] = [
                'Send educational content',
                'Share customer success story',
                'Offer free consultation'
            ]
        
        context['suggested_actions'] = suggestions
        
        # Send notifications
        if options['method'] in ['email', 'both']:
            success = self._send_email_reminder(user, 'lead_nurturing', context, options)
            if not success:
                return False
        
        if options['method'] in ['in_app', 'both']:
            self._send_in_app_notification(user, 'lead_nurturing', context)
        
        return True

    def _process_ticket_sla_reminders(self, users: List[CRMUserProfile], options: Dict) -> Dict:
        """Process SLA deadline reminders for support tickets"""
        results = {
            'users_processed': 0,
            'reminders_sent': 0,
            'tickets_at_risk': 0,
            'sla_breaches': 0,
            'errors': 0
        }
        
        for user in users:
            try:
                # Find tickets at risk of SLA breach
                tickets_at_risk = self._find_tickets_at_risk(user, options)
                
                # Find tickets that have already breached SLA
                breached_tickets = self._find_sla_breached_tickets(user, options)
                
                if tickets_at_risk or breached_tickets:
                    results['tickets_at_risk'] += len(tickets_at_risk)
                    results['sla_breaches'] += len(breached_tickets)
                    
                    if self._send_ticket_sla_reminder(
                        user, tickets_at_risk, breached_tickets, options
                    ):
                        results['reminders_sent'] += 1
                
                results['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing ticket SLA reminders for user {user.id}: {str(e)}")
                results['errors'] += 1
        
        return results

    def _find_tickets_at_risk(self, user: CRMUserProfile, options: Dict) -> List[Ticket]:
        """Find tickets at risk of SLA breach"""
        # Look for tickets that will breach SLA within next few hours
        warning_hours = 2  # Warn 2 hours before SLA breach
        
        at_risk_tickets = []
        
        open_tickets = Ticket.objects.filter(
            assigned_to=user,
            status__in=['NEW', 'OPEN', 'IN_PROGRESS'],
            sla__isnull=False,
            is_deleted=False
        ).select_related('sla', 'category')
        
        for ticket in open_tickets:
            # Calculate time until SLA breach
            if not ticket.first_response_at:
                # Response SLA check
                response_deadline = ticket.created_at + timedelta(
                    hours=ticket.sla.response_time_hours
                )
                time_until_breach = response_deadline - timezone.now()
                
                if time_until_breach <= timedelta(hours=warning_hours) and time_until_breach > timedelta(0):
                    at_risk_tickets.append(ticket)
            
            elif not ticket.resolved_at:
                # Resolution SLA check
                resolution_deadline = ticket.created_at + timedelta(
                    hours=ticket.sla.resolution_time_hours
                )
                time_until_breach = resolution_deadline - timezone.now()
                
                if time_until_breach <= timedelta(hours=warning_hours) and time_until_breach > timedelta(0):
                    at_risk_tickets.append(ticket)
        
        return at_risk_tickets[:5]  # Limit to 5 most urgent

    def _find_sla_breached_tickets(self, user: CRMUserProfile, options: Dict) -> List[Ticket]:
        """Find tickets that have already breached SLA"""
        breached_tickets = []
        
        open_tickets = Ticket.objects.filter(
            assigned_to=user,
            status__in=['NEW', 'OPEN', 'IN_PROGRESS'],
            sla__isnull=False,
            is_deleted=False
        ).select_related('sla', 'category')
        
        for ticket in open_tickets:
            current_time = timezone.now()
            
            # Check response SLA breach
            if not ticket.first_response_at:
                response_deadline = ticket.created_at + timedelta(
                    hours=ticket.sla.response_time_hours
                )
                if current_time > response_deadline:
                    breached_tickets.append(ticket)
            
            # Check resolution SLA breach
            elif not ticket.resolved_at:
                resolution_deadline = ticket.created_at + timedelta(
                    hours=ticket.sla.resolution_time_hours
                )
                if current_time > resolution_deadline:
                    breached_tickets.append(ticket)
        
        return breached_tickets[:5]  # Limit to 5 most critical

    def _send_ticket_sla_reminder(self, user: CRMUserProfile, 
                                at_risk: List[Ticket], breached: List[Ticket], 
                                options: Dict) -> bool:
        """Send ticket SLA reminder"""
        if options['dry_run']:
            self.stdout.write(
                f'  [DRY RUN] Would send ticket SLA reminder to {user.user.email} '
                f'({len(at_risk)} at risk, {len(breached)} breached)'
            )
            return True
        
        context = {
            'user': user,
            'tickets_at_risk': at_risk,
            'breached_tickets': breached,
            'total_urgent': len(at_risk) + len(breached),
        }
        
        # Add escalation recommendations
        if breached:
            context['requires_escalation'] = True
            context['escalation_message'] = 'Immediate action required for SLA-breached tickets'
        elif at_risk:
            context['requires_attention'] = True
            context['attention_message'] = 'Tickets approaching SLA deadline'
        
        # Send notifications with appropriate urgency
        if options['method'] in ['email', 'both']:
            success = self._send_email_reminder(user, 'ticket_sla', context, options)
            if not success:
                return False
        
        if options['method'] in ['in_app', 'both']:
            # Use high priority for SLA notifications
            self._send_in_app_notification(user, 'ticket_sla', context, priority='HIGH')
        
        return True

    # Helper methods for reminder sending
    def _send_email_reminder(self, user: CRMUserProfile, reminder_type: str, 
                           context: Dict, options: Dict) -> bool:
        """Send email reminder using templates"""
        try:
            # Load email template
            template_name = f'crm/emails/{reminder_type}_reminder.html'
            subject_template = f'crm/emails/{reminder_type}_subject.txt'
            
            # Render content
            html_content = render_to_string(template_name, context)
            subject = render_to_string(subject_template, context).strip()
            
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email='noreply@yourcrm.com',
                to=[user.user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            
            # Send email
            msg.send()
            
            logger.info(f"Sent {reminder_type} email reminder to {user.user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email reminder to {user.user.email}: {str(e)}")
            return False

    def _send_in_app_notification(self, user: CRMUserProfile, reminder_type: str, 
                                context: Dict, priority: str = 'MEDIUM'):
        """Send in-app notification"""
        try:
            notification_data = {
                'type': reminder_type,
                'priority': priority,
                'user_id': user.user.id,
                'context': context,
            }
            
            # Use notification service to create in-app notification
            self.notification_service.create_notification(
                user=user.user,
                notification_type=reminder_type,
                title=self._get_notification_title(reminder_type, context),
                message=self._get_notification_message(reminder_type, context),
                data=notification_data,
                priority=priority
            )
            
        except Exception as e:
            logger.error(f"Failed to send in-app notification to {user.user.email}: {str(e)}")

    def _get_notification_title(self, reminder_type: str, context: Dict) -> str:
        """Generate notification title based on type and context"""
        titles = {
            'follow_up_reminder': f"You have {context.get('total_items', 0)} items requiring follow-up",
            'overdue_tasks': f"{context.get('total_overdue', 0)} overdue tasks need attention",
            'opportunity_deadlines': f"Opportunity deadlines approaching (${context.get('total_at_risk', 0):,.0f} at risk)",
            'lead_nurturing': f"{context.get('total_leads', 0)} leads ready for nurturing",
            'ticket_sla': f"{context.get('total_urgent', 0)} tickets require urgent attention"
        }
        
        return titles.get(reminder_type, 'CRM Reminder')

    def _get_notification_message(self, reminder_type: str, context: Dict) -> str:
        """Generate notification message based on type and context"""
        messages = {
            'follow_up_reminder': 'Check your dashboard for leads and activities requiring follow-up.',
            'overdue_tasks': 'You have overdue tasks that need to be completed.',
            'opportunity_deadlines': 'Some opportunities are approaching their close dates.',
            'lead_nurturing': 'Leads are ready for the next nurturing step.',
            'ticket_sla': 'Support tickets are approaching or have breached SLA deadlines.'
        }
        
        return messages.get(reminder_type, 'You have items that require attention.')

    def _get_personalization_data(self, user: CRMUserProfile) -> Dict:
        """Get personalization data for the user"""
        return {
            'user_timezone': user.timezone or 'UTC',
            'user_performance_this_month': self._get_user_performance_summary(user),
            'user_preferences': {
                'preferred_contact_method': getattr(user, 'preferred_contact_method', 'email'),
                'reminder_frequency': getattr(user, 'reminder_frequency', 'daily'),
            }
        }

    def _get_user_performance_summary(self, user: CRMUserProfile) -> Dict:
        """Get user's performance summary for personalization"""
        current_month = timezone.now().replace(day=1)
        
        return {
            'leads_converted_this_month': Lead.objects.filter(
                assigned_to=user,
                status='CONVERTED',
                updated_at__gte=current_month
            ).count(),
            'opportunities_won_this_month': Opportunity.objects.filter(
                assigned_to=user,
                stage__stage_type='WON',
                actual_close_date__gte=current_month
            ).count(),
            'activities_completed_this_month': Activity.objects.filter(
                assigned_to=user,
                status='COMPLETED',
                completed_at__gte=current_month
            ).count(),
        }

    def _get_opportunity_recommendations(self, opportunities: List[Opportunity]) -> List[str]:
        """Get recommended actions for opportunities"""
        recommendations = []
        
        for opp in opportunities[:3]:  # Top 3 opportunities
            if opp.stage.probability < 50:
                recommendations.append(
                    f"Schedule demo for {opp.name} to move forward in pipeline"
                )
            elif opp.stage.probability >= 75:
                recommendations.append(
                    f"Send proposal or contract for {opp.name} - high probability of closing"
                )
            else:
                recommendations.append(
                    f"Follow up on {opp.name} - needs attention to maintain momentum"
                )
        
        return recommendations

    def _is_weekend(self) -> bool:
        """Check if today is weekend"""
        return timezone.now().weekday() >= 5  # Saturday = 5, Sunday = 6

    def _print_reminder_summary(self, results: Dict, options: Dict):
        """Print comprehensive reminder summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📨 REMINDER SUMMARY')
        self.stdout.write('='*60)
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No reminders were sent'))
        
        total_reminders = 0
        total_users = 0
        total_errors = 0
        
        for reminder_type, result in results.items():
            if isinstance(result, dict) and 'error' not in result:
                self.stdout.write(f'\n📋 {reminder_type.upper().replace("_", " ")}:')
                
                for key, value in result.items():
                    display_key = key.replace('_', ' ').title()
                    self.stdout.write(f'  {display_key}: {value:,}')
                    
                    if 'reminders_sent' in key:
                        total_reminders += value
                    elif 'users_processed' in key:
                        total_users = max(total_users, value)  # Use max to avoid double counting
                    elif 'errors' in key:
                        total_errors += value
            
            elif isinstance(result, dict) and 'error' in result:
                self.stdout.write(f'\n❌ {reminder_type.upper().replace("_", " ")} FAILED:')
                self.stdout.write(f'  Error: {result["error"]}')
                total_errors += 1
        
        # Overall summary
        self.stdout.write(f'\n📊 OVERALL TOTALS:')
        self.stdout.write(f'Users Processed: {total_users:,}')
        self.stdout.write(f'Reminders Sent: {total_reminders:,}')
        if total_errors > 0:
            self.stdout.write(f'Errors: {total_errors:,}')
        
        # Delivery method summary
        method = options['method']
        self.stdout.write(f'Delivery Method: {method.title()}')
        
        if options['smart_timing']:
            self.stdout.write('Smart Timing: Enabled')
        
        if options['personalized']:
            self.stdout.write('Personalization: Enabled')
        
        self.stdout.write('='*60)
        
        if total_errors == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ All reminders processed successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ Reminders completed with {total_errors} errors'
                )
            )