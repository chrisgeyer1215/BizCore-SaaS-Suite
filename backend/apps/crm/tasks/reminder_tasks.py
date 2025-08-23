"""
Reminder Tasks
Handle activity reminders, follow-ups, and scheduled notifications
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import logging
from datetime import timedelta

from .base import TenantAwareTask, ScheduledTask
from ..models import (
    Activity, Lead, Opportunity, Ticket, Account,
    ReminderSettings, ScheduledReminder
)
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=ScheduledTask, bind=True)
def send_activity_reminders_task(self, tenant_id=None):
    """
    Send reminders for upcoming and overdue activities
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        
        # Get activities needing reminders
        now = timezone.now()
        
        # Activities due today
        due_today = Activity.objects.filter(
            due_date__date=now.date(),
            status__in=['pending', 'open'],
            reminder_sent=False
        )
        
        # Overdue activities
        overdue = Activity.objects.filter(
            due_date__lt=now,
            status__in=['pending', 'open'],
            overdue_reminder_sent=False
        )
        
        # Activities due in next hour
        due_soon = Activity.objects.filter(
            due_date__range=[now, now + timedelta(hours=1)],
            status__in=['pending', 'open'],
            immediate_reminder_sent=False
        )
        
        if tenant:
            due_today = due_today.filter(tenant=tenant)
            overdue = overdue.filter(tenant=tenant)
            due_soon = due_soon.filter(tenant=tenant)
        
        from .email_tasks import send_email_task
        
        reminders_sent = 0
        
        # Process due today activities
        for activity in due_today:
            try:
                if activity.assigned_to and activity.assigned_to.email:
                    send_email_task.delay(
                        recipient_email=activity.assigned_to.email,
                        subject=f"Activity Due Today: {activity.subject}",
                        message="",
                        template_id='activity_due_today',
                        context={
                            'activity': {
                                'id': activity.id,
                                'subject': activity.subject,
                                'description': activity.description,
                                'due_date': activity.due_date.isoformat(),
                                'priority': activity.priority,
                                'type': activity.activity_type
                            },
                            'user_name': activity.assigned_to.get_full_name(),
                            'activity_url': f"{settings.FRONTEND_URL}/activities/{activity.id}"
                        },
                        tenant_id=activity.tenant_id if activity.tenant else None
                    )
                    
                    activity.reminder_sent = True
                    activity.reminder_sent_at = now
                    activity.save(update_fields=['reminder_sent', 'reminder_sent_at'])
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send reminder for activity {activity.id}: {e}")
        
        # Process overdue activities
        for activity in overdue:
            try:
                if activity.assigned_to and activity.assigned_to.email:
                    # Calculate how overdue
                    overdue_hours = (now - activity.due_date).total_seconds() / 3600
                    
                    send_email_task.delay(
                        recipient_email=activity.assigned_to.email,
                        subject=f"OVERDUE Activity: {activity.subject}",
                        message="",
                        template_id='activity_overdue',
                        context={
                            'activity': {
                                'id': activity.id,
                                'subject': activity.subject,
                                'description': activity.description,
                                'due_date': activity.due_date.isoformat(),
                                'priority': activity.priority,
                                'type': activity.activity_type,
                                'overdue_hours': int(overdue_hours)
                            },
                            'user_name': activity.assigned_to.get_full_name(),
                            'activity_url': f"{settings.FRONTEND_URL}/activities/{activity.id}"
                        },
                        tenant_id=activity.tenant_id if activity.tenant else None
                    )
                    
                    activity.overdue_reminder_sent = True
                    activity.overdue_reminder_sent_at = now
                    activity.save(update_fields=['overdue_reminder_sent', 'overdue_reminder_sent_at'])
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send overdue reminder for activity {activity.id}: {e}")
        
        # Process due soon activities
        for activity in due_soon:
            try:
                if activity.assigned_to and activity.assigned_to.email:
                    minutes_until_due = int((activity.due_date - now).total_seconds() / 60)
                    
                    send_email_task.delay(
                        recipient_email=activity.assigned_to.email,
                        subject=f"Activity Due in {minutes_until_due} minutes: {activity.subject}",
                        message="",
                        template_id='activity_due_soon',
                        context={
                            'activity': {
                                'id': activity.id,
                                'subject': activity.subject,
                                'due_date': activity.due_date.isoformat(),
                                'minutes_until_due': minutes_until_due
                            },
                            'user_name': activity.assigned_to.get_full_name(),
                            'activity_url': f"{settings.FRONTEND_URL}/activities/{activity.id}"
                        },
                        tenant_id=activity.tenant_id if activity.tenant else None
                    )
                    
                    activity.immediate_reminder_sent = True
                    activity.save(update_fields=['immediate_reminder_sent'])
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send immediate reminder for activity {activity.id}: {e}")
        
        logger.info(f"Sent {reminders_sent} activity reminders")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'due_today': due_today.count(),
            'overdue': overdue.count(),
            'due_soon': due_soon.count()
        }
        
    except Exception as e:
        logger.error(f"Activity reminders task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_follow_up_reminders_task(self, tenant_id):
    """
    Send follow-up reminders for leads and opportunities
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        now = timezone.now()
        
        # Leads needing follow-up
        leads_needing_followup = Lead.objects.filter(
            tenant=tenant,
            next_follow_up_date__lte=now,
            status__in=['new', 'contacted', 'qualified'],
            follow_up_reminder_sent=False
        )
        
        # Opportunities needing follow-up
        opps_needing_followup = Opportunity.objects.filter(
            tenant=tenant,
            next_follow_up_date__lte=now,
            stage__is_closed=False,
            follow_up_reminder_sent=False
        )
        
        from .email_tasks import send_email_task
        
        reminders_sent = 0
        
        # Process lead follow-ups
        for lead in leads_needing_followup:
            try:
                if lead.assigned_to and lead.assigned_to.email:
                    # Calculate days since last contact
                    days_since_contact = 0
                    if lead.last_activity_date:
                        days_since_contact = (now.date() - lead.last_activity_date.date()).days
                    
                    send_email_task.delay(
                        recipient_email=lead.assigned_to.email,
                        subject=f"Follow-up Reminder: {lead.first_name} {lead.last_name}",
                        message="",
                        template_id='lead_followup_reminder',
                        context={
                            'lead': {
                                'id': lead.id,
                                'name': f"{lead.first_name} {lead.last_name}",
                                'company': lead.company,
                                'status': lead.status,
                                'score': lead.score,
                                'days_since_contact': days_since_contact
                            },
                            'user_name': lead.assigned_to.get_full_name(),
                            'lead_url': f"{settings.FRONTEND_URL}/leads/{lead.id}"
                        },
                        tenant_id=tenant.id
                    )
                    
                    # Create follow-up activity
                    Activity.objects.create(
                        tenant=tenant,
                        subject=f"Follow up with {lead.first_name} {lead.last_name}",
                        activity_type='call',
                        assigned_to=lead.assigned_to,
                        entity_type='lead',
                        entity_id=lead.id,
                        due_date=now + timedelta(hours=2),
                        priority='medium',
                        created_by=lead.assigned_to
                    )
                    
                    lead.follow_up_reminder_sent = True
                    lead.save(update_fields=['follow_up_reminder_sent'])
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send follow-up reminder for lead {lead.id}: {e}")
        
        # Process opportunity follow-ups
        for opp in opps_needing_followup:
            try:
                if opp.assigned_to and opp.assigned_to.email:
                    days_until_close = 0
                    if opp.close_date:
                        days_until_close = (opp.close_date - now.date()).days
                    
                    send_email_task.delay(
                        recipient_email=opp.assigned_to.email,
                        subject=f"Opportunity Follow-up: {opp.name}",
                        message="",
                        template_id='opportunity_followup_reminder',
                        context={
                            'opportunity': {
                                'id': opp.id,
                                'name': opp.name,
                                'value': opp.value,
                                'stage': opp.stage.name if opp.stage else 'Unknown',
                                'probability': opp.probability,
                                'days_until_close': days_until_close,
                                'account_name': opp.account.name if opp.account else 'Unknown'
                            },
                            'user_name': opp.assigned_to.get_full_name(),
                            'opportunity_url': f"{settings.FRONTEND_URL}/opportunities/{opp.id}"
                        },
                        tenant_id=tenant.id
                    )
                    
                    # Create follow-up activity
                    Activity.objects.create(
                        tenant=tenant,
                        subject=f"Follow up on opportunity: {opp.name}",
                        activity_type='call',
                        assigned_to=opp.assigned_to,
                        entity_type='opportunity',
                        entity_id=opp.id,
                        due_date=now + timedelta(hours=4),
                        priority='high' if opp.value > 50000 else 'medium',
                        created_by=opp.assigned_to
                    )
                    
                    opp.follow_up_reminder_sent = True
                    opp.save(update_fields=['follow_up_reminder_sent'])
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send follow-up reminder for opportunity {opp.id}: {e}")
        
        logger.info(f"Sent {reminders_sent} follow-up reminders")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'lead_followups': leads_needing_followup.count(),
            'opportunity_followups': opps_needing_followup.count()
        }
        
    except Exception as e:
        logger.error(f"Follow-up reminders task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_sla_breach_notifications_task(self, tenant_id):
    """
    Send notifications for SLA breaches
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        now = timezone.now()
        
        # Find tickets with SLA breaches
        sla_breached_tickets = Ticket.objects.filter(
            tenant=tenant,
            sla_due_date__lt=now,
            status__in=['open', 'pending', 'in_progress'],
            sla_breach_notified=False
        )
        
        # Find tickets approaching SLA breach (within 1 hour)
        sla_warning_tickets = Ticket.objects.filter(
            tenant=tenant,
            sla_due_date__range=[now, now + timedelta(hours=1)],
            status__in=['open', 'pending', 'in_progress'],
            sla_warning_sent=False
        )
        
        from .email_tasks import send_email_task
        from .notification_tasks import send_notification_task
        
        notifications_sent = 0
        
        # Process SLA breach notifications
        for ticket in sla_breached_tickets:
            try:
                # Calculate breach time
                breach_hours = (now - ticket.sla_due_date).total_seconds() / 3600
                
                # Notify assigned agent
                if ticket.assigned_to and ticket.assigned_to.email:
                    send_email_task.delay(
                        recipient_email=ticket.assigned_to.email,
                        subject=f"SLA BREACH: Ticket #{ticket.id}",
                        message="",
                        template_id='sla_breach_notification',
                        context={
                            'ticket': {
                                'id': ticket.id,
                                'subject': ticket.subject,
                                'priority': ticket.priority,
                                'customer_name': ticket.customer.name if ticket.customer else 'Unknown',
                                'breach_hours': int(breach_hours),
                                'sla_due_date': ticket.sla_due_date.isoformat()
                            },
                            'agent_name': ticket.assigned_to.get_full_name(),
                            'ticket_url': f"{settings.FRONTEND_URL}/tickets/{ticket.id}"
                        },
                        tenant_id=tenant.id
                    )
                
                # Notify manager
                if ticket.assigned_to and hasattr(ticket.assigned_to, 'manager'):
                    send_notification_task.delay(
                        user_id=ticket.assigned_to.manager.id,
                        notification_type='sla_breach',
                        title=f"SLA Breach: Ticket #{ticket.id}",
                        message=f"Ticket has breached SLA by {int(breach_hours)} hours",
                        related_object_type='ticket',
                        related_object_id=ticket.id,
                        tenant_id=tenant.id
                    )
                
                # Mark as SLA breached and notified
                ticket.sla_breached = True
                ticket.sla_breach_notified = True
                ticket.sla_breached_at = now
                ticket.save(update_fields=['sla_breached', 'sla_breach_notified', 'sla_breached_at'])
                notifications_sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send SLA breach notification for ticket {ticket.id}: {e}")
        
        # Process SLA warning notifications
        for ticket in sla_warning_tickets:
            try:
                if ticket.assigned_to and ticket.assigned_to.email:
                    minutes_to_breach = int((ticket.sla_due_date - now).total_seconds() / 60)
                    
                    send_email_task.delay(
                        recipient_email=ticket.assigned_to.email,
                        subject=f"SLA Warning: Ticket #{ticket.id} due in {minutes_to_breach} minutes",
                        message="",
                        template_id='sla_warning_notification',
                        context={
                            'ticket': {
                                'id': ticket.id,
                                'subject': ticket.subject,
                                'priority': ticket.priority,
                                'customer_name': ticket.customer.name if ticket.customer else 'Unknown',
                                'minutes_to_breach': minutes_to_breach
                            },
                            'agent_name': ticket.assigned_to.get_full_name(),
                            'ticket_url': f"{settings.FRONTEND_URL}/tickets/{ticket.id}"
                        },
                        tenant_id=tenant.id
                    )
                    
                    ticket.sla_warning_sent = True
                    ticket.save(update_fields=['sla_warning_sent'])
                    notifications_sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send SLA warning for ticket {ticket.id}: {e}")
        
        logger.info(f"Sent {notifications_sent} SLA notifications")
        
        return {
            'status': 'completed',
            'notifications_sent': notifications_sent,
            'breached_tickets': sla_breached_tickets.count(),
            'warning_tickets': sla_warning_tickets.count()
        }
        
    except Exception as e:
        logger.error(f"SLA breach notifications task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_scheduled_activities_task(self, tenant_id):
    """
    Process and create scheduled activities
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        now = timezone.now()
        
        # Find scheduled activities that should be created
        scheduled_activities = ScheduledReminder.objects.filter(
            tenant=tenant,
            scheduled_time__lte=now,
            executed=False,
            is_active=True
        )
        
        created_count = 0
        
        for scheduled in scheduled_activities:
            try:
                # Create the activity
                activity = Activity.objects.create(
                    tenant=tenant,
                    subject=scheduled.subject,
                    description=scheduled.description,
                    activity_type=scheduled.activity_type,
                    assigned_to=scheduled.assigned_to,
                    entity_type=scheduled.entity_type,
                    entity_id=scheduled.entity_id,
                    due_date=scheduled.activity_due_date or (now + timedelta(hours=1)),
                    priority=scheduled.priority or 'medium',
                    created_by=scheduled.created_by
                )
                
                # Mark scheduled reminder as executed
                scheduled.executed = True
                scheduled.executed_at = now
                scheduled.created_activity = activity
                scheduled.save(update_fields=['executed', 'executed_at', 'created_activity'])
                
                created_count += 1
                
                logger.info(f"Created scheduled activity: {activity.subject}")
                
            except Exception as e:
                logger.error(f"Failed to create scheduled activity {scheduled.id}: {e}")
        
        return {
            'status': 'completed',
            'activities_created': created_count
        }
        
    except Exception as e:
        logger.error(f"Scheduled activities processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_birthday_reminders_task(self, tenant_id):
    """
    Send birthday reminders for contacts
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        today = timezone.now().date()
        
        # Find contacts with birthdays today
        birthday_contacts = Contact.objects.filter(
            tenant=tenant,
            date_of_birth__day=today.day,
            date_of_birth__month=today.month,
            is_active=True
        )
        
        from .email_tasks import send_email_task
        
        reminders_sent = 0
        
        for contact in birthday_contacts:
            try:
                # Find the assigned user (account owner or recent activity user)
                assigned_user = None
                
                if hasattr(contact, 'account') and contact.account and contact.account.assigned_to:
                    assigned_user = contact.account.assigned_to
                else:
                    # Find user who last interacted with this contact
                    recent_activity = Activity.objects.filter(
                        tenant=tenant,
                        entity_type='contact',
                        entity_id=contact.id,
                        assigned_to__isnull=False
                    ).order_by('-created_at').first()
                    
                    if recent_activity:
                        assigned_user = recent_activity.assigned_to
                
                if assigned_user and assigned_user.email:
                    # Calculate age
                    age = today.year - contact.date_of_birth.year
                    if today < contact.date_of_birth.replace(year=today.year):
                        age -= 1
                    
                    send_email_task.delay(
                        recipient_email=assigned_user.email,
                        subject=f"🎂 Birthday Reminder: {contact.first_name} {contact.last_name}",
                        message="",
                        template_id='birthday_reminder',
                        context={
                            'contact': {
                                'name': f"{contact.first_name} {contact.last_name}",
                                'company': contact.account.name if hasattr(contact, 'account') and contact.account else '',
                                'age': age,
                                'email': contact.email,
                                'phone': contact.phone
                            },
                            'user_name': assigned_user.get_full_name(),
                            'contact_url': f"{settings.FRONTEND_URL}/contacts/{contact.id}"
                        },
                        tenant_id=tenant.id
                    )
                    
                    # Create a birthday follow-up activity
                    Activity.objects.create(
                        tenant=tenant,
                        subject=f"🎂 Send birthday wishes to {contact.first_name} {contact.last_name}",
                        description=f"It's {contact.first_name}'s birthday today! Consider sending a personal message.",
                        activity_type='call',
                        assigned_to=assigned_user,
                        entity_type='contact',
                        entity_id=contact.id,
                        due_date=timezone.now() + timedelta(hours=2),
                        priority='low',
                        created_by=assigned_user
                    )
                    
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send birthday reminder for contact {contact.id}: {e}")
        
        logger.info(f"Sent {reminders_sent} birthday reminders")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'birthdays_today': birthday_contacts.count()
        }
        
    except Exception as e:
        logger.error(f"Birthday reminders task failed: {e}")
        raise