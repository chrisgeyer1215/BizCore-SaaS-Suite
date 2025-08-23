"""
Ticket Signals
Handle support ticket lifecycle events and SLA automation
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..models import Ticket, Activity, AuditTrail, SLA, TicketComment
from ..tasks.workflow_tasks import process_workflow_triggers_task
from ..tasks.notification_tasks import send_notification_task, process_escalations_task
from ..tasks.reminder_tasks import send_sla_breach_notifications_task

logger = logging.getLogger(__name__)

# Custom signals
ticket_assigned = Signal()
ticket_status_changed = Signal()
ticket_escalated = Signal()
ticket_resolved = Signal()
ticket_sla_breached = Signal()
ticket_satisfaction_rated = Signal()


@receiver(post_save, sender=Ticket)
def handle_ticket_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle ticket creation and updates
    """
    try:
        if created:
            # Ticket created
            logger.info(f"Ticket created: #{instance.id} - {instance.subject} - Priority: {instance.priority}")
            
            # Set SLA due date if not set
            if not instance.sla_due_date and instance.priority:
                instance.sla_due_date = calculate_sla_due_date(instance.priority, instance.created_at)
                instance.save(update_fields=['sla_due_date'])
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='ticket',
                object_id=instance.id,
                changes={
                    'created': True,
                    'subject': instance.subject,
                    'priority': instance.priority,
                    'category': instance.category.name if instance.category else None,
                    'customer': instance.customer.name if instance.customer else None,
                    'sla_due_date': instance.sla_due_date.isoformat() if instance.sla_due_date else None
                },
                timestamp=timezone.now()
            )
            
            # Create initial activity
            transaction.on_commit(lambda: Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Support ticket created: #{instance.id}",
                description=f"New {instance.priority} priority ticket: {instance.subject}",
                activity_type='ticket',
                entity_type='ticket',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.created_by,
                status='completed',
                completed_at=timezone.now(),
                priority='high' if instance.priority == 'critical' else 'medium'
            ))
            
            # Auto-assign ticket if rules exist
            if not instance.assigned_to:
                auto_assigned_agent = auto_assign_ticket(instance)
                if auto_assigned_agent:
                    instance.assigned_to = auto_assigned_agent
                    instance.assigned_at = timezone.now()
                    instance.save(update_fields=['assigned_to', 'assigned_at'])
            
            # Send notification to assigned agent
            if instance.assigned_to:
                transaction.on_commit(lambda: send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='ticket_assigned',
                    title=f"New Ticket Assigned: #{instance.id}",
                    message=f"Priority: {instance.priority.upper()} - {instance.subject}",
                    related_object_type='ticket',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='critical' if instance.priority == 'critical' else 'high'
                ))
            
            # Send acknowledgment to customer
            if instance.customer and hasattr(instance.customer, 'email'):
                transaction.on_commit(lambda: send_notification_task.delay(
                    user_id=None,  # System notification
                    notification_type='ticket_created_customer',
                    title=f"Support Ticket Created: #{instance.id}",
                    message=f"Your support request has been received and assigned ticket #{instance.id}.",
                    tenant_id=instance.tenant.id,
                    priority='low',
                    channels=['email'],
                    recipient_email=instance.customer.email
                ))
            
            # Trigger workflow processing
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='ticket_created',
                entity_data={
                    'entity_type': 'ticket',
                    'entity_id': instance.id,
                    'subject': instance.subject,
                    'priority': instance.priority,
                    'category': instance.category.name if instance.category else None,
                    'customer_id': instance.customer.id if instance.customer else None,
                    'assigned_to': instance.assigned_to.id if instance.assigned_to else None,
                    'created_by': instance.created_by.id if instance.created_by else None
                }
            ))
            
        else:
            # Ticket updated
            logger.info(f"Ticket updated: #{instance.id} - {instance.subject}")
            
            # Trigger workflow processing for updates
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='ticket_updated',
                entity_data={
                    'entity_type': 'ticket',
                    'entity_id': instance.id,
                    'subject': instance.subject,
                    'status': instance.status,
                    'priority': instance.priority,
                    'modified_by': instance.modified_by.id if instance.modified_by else None
                }
            ))
            
    except Exception as e:
        logger.error(f"Error in ticket post_save signal: {e}")


@receiver(pre_save, sender=Ticket)
def handle_ticket_changes(sender, instance, **kwargs):
    """
    Detect and handle ticket changes before saving
    """
    try:
        if instance.pk:  # Only for existing tickets
            try:
                old_ticket = Ticket.objects.get(pk=instance.pk)
                
                # Check if status changed
                if old_ticket.status != instance.status:
                    logger.info(f"Ticket status changed: {old_ticket.status} -> {instance.status} for ticket #{instance.id}")
                    
                    # Set status change timestamps
                    if instance.status in ['resolved', 'closed'] and not instance.resolved_at:
                        instance.resolved_at = timezone.now()
                        instance.resolution_time = calculate_resolution_time(instance.created_at, instance.resolved_at)
                    
                    if instance.status == 'in_progress' and not instance.first_response_at:
                        instance.first_response_at = timezone.now()
                        instance.first_response_time = calculate_resolution_time(instance.created_at, instance.first_response_at)
                    
                    # Send status change signal
                    transaction.on_commit(lambda: ticket_status_changed.send(
                        sender=sender,
                        instance=instance,
                        old_status=old_ticket.status,
                        new_status=instance.status
                    ))
                
                # Check if assignment changed
                if old_ticket.assigned_to != instance.assigned_to:
                    if instance.assigned_to and not instance.assigned_at:
                        instance.assigned_at = timezone.now()
                    
                    transaction.on_commit(lambda: ticket_assigned.send(
                        sender=sender,
                        instance=instance,
                        old_assignee=old_ticket.assigned_to,
                        new_assignee=instance.assigned_to
                    ))
                
                # Check if priority escalated
                priority_levels = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
                old_priority_level = priority_levels.get(old_ticket.priority, 1)
                new_priority_level = priority_levels.get(instance.priority, 1)
                
                if new_priority_level > old_priority_level:
                    instance.escalated_at = timezone.now()
                    instance.is_escalated = True
                    
                    transaction.on_commit(lambda: ticket_escalated.send(
                        sender=sender,
                        instance=instance,
                        old_priority=old_ticket.priority,
                        new_priority=instance.priority
                    ))
                
                # Check for SLA breach
                if (instance.sla_due_date and instance.sla_due_date < timezone.now() and
                    not instance.sla_breached and instance.status not in ['resolved', 'closed']):
                    
                    instance.sla_breached = True
                    instance.sla_breached_at = timezone.now()
                    
                    transaction.on_commit(lambda: ticket_sla_breached.send(
                        sender=sender,
                        instance=instance,
                        breach_time=instance.sla_breached_at
                    ))
                
                # Check if satisfaction rating was added
                if (not old_ticket.satisfaction_rating and instance.satisfaction_rating and
                    instance.status in ['resolved', 'closed']):
                    
                    transaction.on_commit(lambda: ticket_satisfaction_rated.send(
                        sender=sender,
                        instance=instance,
                        rating=instance.satisfaction_rating
                    ))
                    
            except Ticket.DoesNotExist:
                pass  # New ticket
                
    except Exception as e:
        logger.error(f"Error in ticket pre_save signal: {e}")


@receiver(ticket_status_changed)
def handle_ticket_status_changed_signal(sender, instance, old_status, new_status, **kwargs):
    """
    Handle ticket status changes
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='status_change',
            object_type='ticket',
            object_id=instance.id,
            changes={
                'field': 'status',
                'old_value': old_status,
                'new_value': new_status,
                'changed_at': timezone.now().isoformat()
            },
            timestamp=timezone.now()
        )
        
        # Create activity for status change
        status_messages = {
            'open': 'Ticket opened',
            'in_progress': 'Work started on ticket',
            'pending': 'Ticket pending customer response',
            'resolved': 'Ticket resolved',
            'closed': 'Ticket closed'
        }
        
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Ticket status changed: {old_status} → {new_status}",
            description=status_messages.get(new_status, f"Status changed to {new_status}"),
            activity_type='status_change',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Handle specific status transitions
        if new_status in ['resolved', 'closed']:
            ticket_resolved.send(sender=sender, instance=instance, old_status=old_status)
        
        # Send notification to customer for important status changes
        if new_status in ['in_progress', 'resolved', 'closed'] and instance.customer:
            customer_messages = {
                'in_progress': 'Our team has started working on your support request.',
                'resolved': 'Your support request has been resolved. Please review the solution.',
                'closed': 'Your support request has been closed. Thank you for contacting us.'
            }
            
            if hasattr(instance.customer, 'email') and instance.customer.email:
                send_notification_task.delay(
                    user_id=None,
                    notification_type=f'ticket_status_{new_status}_customer',
                    title=f"Ticket #{instance.id} Status Update",
                    message=customer_messages.get(new_status, f"Your ticket status has been updated to {new_status}."),
                    tenant_id=instance.tenant.id,
                    priority='medium',
                    channels=['email'],
                    recipient_email=instance.customer.email
                )
        
        # Send notification to assigned agent for important changes
        if instance.assigned_to and new_status == 'pending':
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='ticket_pending',
                title=f"Ticket Pending: #{instance.id}",
                message="Ticket is pending customer response. Follow up if no response received.",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
        # Trigger workflows
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='ticket_status_changed',
            entity_data={
                'entity_type': 'ticket',
                'entity_id': instance.id,
                'old_status': old_status,
                'new_status': new_status,
                'priority': instance.priority,
                'customer_id': instance.customer.id if instance.customer else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling ticket status change signal: {e}")


@receiver(ticket_resolved)
def handle_ticket_resolved_signal(sender, instance, old_status, **kwargs):
    """
    Handle ticket resolution
    """
    try:
        logger.info(f"Ticket resolved: #{instance.id} - Resolution time: {instance.resolution_time} minutes")
        
        # Create resolution activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"✅ Ticket Resolved: #{instance.id}",
            description=f"Ticket resolved in {instance.resolution_time} minutes. Solution provided.",
            activity_type='resolution',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='medium'
        )
        
        # Send notification to assigned agent
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='ticket_resolved',
                title=f"✅ Ticket Resolved: #{instance.id}",
                message=f"Great job! You resolved the ticket in {instance.resolution_time} minutes.",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
        # Create follow-up activity for satisfaction survey
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Send satisfaction survey: Ticket #{instance.id}",
            description="Send customer satisfaction survey for resolved ticket",
            activity_type='survey',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by or instance.assigned_to,
            due_date=timezone.now() + timedelta(hours=2),
            status='pending',
            priority='low'
        )
        
        # Update agent performance metrics
        if instance.assigned_to:
            update_agent_performance_metrics(instance.assigned_to, instance)
        
        # Check if resolution was within SLA
        sla_met = not instance.sla_breached
        if sla_met:
            logger.info(f"SLA met for ticket #{instance.id}")
        else:
            logger.warning(f"SLA breached for ticket #{instance.id}")
        
    except Exception as e:
        logger.error(f"Error handling ticket resolution signal: {e}")


@receiver(ticket_assigned)
def handle_ticket_assigned_signal(sender, instance, old_assignee, new_assignee, **kwargs):
    """
    Handle ticket assignment changes
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='assignment_change',
            object_type='ticket',
            object_id=instance.id,
            changes={
                'field': 'assigned_to',
                'old_value': old_assignee.id if old_assignee else None,
                'new_value': new_assignee.id if new_assignee else None,
                'old_assignee_name': old_assignee.get_full_name() if old_assignee else None,
                'new_assignee_name': new_assignee.get_full_name() if new_assignee else None
            },
            timestamp=timezone.now()
        )
        
        # Create activity
        if old_assignee and new_assignee:
            description = f"Ticket reassigned from {old_assignee.get_full_name()} to {new_assignee.get_full_name()}"
        elif new_assignee:
            description = f"Ticket assigned to {new_assignee.get_full_name()}"
        else:
            description = f"Ticket unassigned from {old_assignee.get_full_name()}"
        
        Activity.objects.create(
            tenant=instance.tenant,
            subject="Ticket assignment changed",
            description=description,
            activity_type='assignment',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=new_assignee,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Send notifications
        if new_assignee:
            priority = 'critical' if instance.priority == 'critical' else 'high'
            send_notification_task.delay(
                user_id=new_assignee.id,
                notification_type='ticket_assigned',
                title=f"Ticket Assigned: #{instance.id}",
                message=f"Priority: {instance.priority.upper()} - {instance.subject}",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority=priority
            )
        
        # Notify previous assignee if reassigned
        if old_assignee and new_assignee and old_assignee != new_assignee:
            send_notification_task.delay(
                user_id=old_assignee.id,
                notification_type='ticket_reassigned',
                title=f"Ticket Reassigned: #{instance.id}",
                message=f"Ticket has been reassigned to {new_assignee.get_full_name()}.",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
    except Exception as e:
        logger.error(f"Error handling ticket assignment signal: {e}")


@receiver(ticket_escalated)
def handle_ticket_escalated_signal(sender, instance, old_priority, new_priority, **kwargs):
    """
    Handle ticket escalation
    """
    try:
        logger.warning(f"Ticket escalated: #{instance.id} - {old_priority} → {new_priority}")
        
        # Create escalation activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"🔥 Ticket Escalated: #{instance.id}",
            description=f"Ticket priority escalated from {old_priority} to {new_priority}",
            activity_type='escalation',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='critical'
        )
        
        # Send escalation notifications
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='ticket_escalated',
                title=f"🔥 Ticket Escalated: #{instance.id}",
                message=f"Priority escalated to {new_priority.upper()}. Immediate attention required!",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='critical'
            )
        
        # Notify manager for critical escalations
        if new_priority == 'critical':
            manager = getattr(instance.assigned_to, 'manager', None)
            if manager:
                send_notification_task.delay(
                    user_id=manager.id,
                    notification_type='critical_ticket_escalation',
                    title=f"🚨 Critical Escalation: Ticket #{instance.id}",
                    message=f"Ticket escalated to CRITICAL priority. Agent: {instance.assigned_to.get_full_name() if instance.assigned_to else 'Unassigned'}",
                    related_object_type='ticket',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='critical'
                )
        
        # Auto-reassign to senior agent for critical tickets
        if new_priority == 'critical' and not instance.assigned_to:
            senior_agent = find_available_senior_agent(instance.tenant)
            if senior_agent:
                instance.assigned_to = senior_agent
                instance.assigned_at = timezone.now()
                instance.save(update_fields=['assigned_to', 'assigned_at'])
        
        # Trigger escalation workflows
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='ticket_escalated',
            entity_data={
                'entity_type': 'ticket',
                'entity_id': instance.id,
                'old_priority': old_priority,
                'new_priority': new_priority,
                'customer_id': instance.customer.id if instance.customer else None,
                'escalated_at': instance.escalated_at.isoformat() if instance.escalated_at else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling ticket escalation signal: {e}")


@receiver(ticket_sla_breached)
def handle_ticket_sla_breached_signal(sender, instance, breach_time, **kwargs):
    """
    Handle SLA breach
    """
    try:
        logger.error(f"SLA BREACHED: Ticket #{instance.id} - Breached at: {breach_time}")
        
        # Create SLA breach activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"🚨 SLA BREACHED: Ticket #{instance.id}",
            description=f"SLA was breached at {breach_time}. Immediate action required!",
            activity_type='sla_breach',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.assigned_to,
            status='pending',
            completed_at=timezone.now(),
            priority='critical'
        )
        
        # Send critical notifications
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='sla_breach',
                title=f"🚨 SLA BREACH: Ticket #{instance.id}",
                message=f"SLA has been breached! Immediate action required for {instance.priority} priority ticket.",
                related_object_type='ticket',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='critical'
            )
        
        # Notify management
        process_escalations_task.delay(tenant_id=instance.tenant.id)
        
        # Auto-escalate priority if not already critical
        if instance.priority != 'critical':
            instance.priority = 'critical'
            instance.is_escalated = True
            instance.escalated_at = timezone.now()
            instance.save(update_fields=['priority', 'is_escalated', 'escalated_at'])
        
        # Trigger SLA breach workflows
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='ticket_sla_breached',
            entity_data={
                'entity_type': 'ticket',
                'entity_id': instance.id,
                'breach_time': breach_time.isoformat(),
                'priority': instance.priority,
                'original_sla_due': instance.sla_due_date.isoformat() if instance.sla_due_date else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling SLA breach signal: {e}")


@receiver(ticket_satisfaction_rated)
def handle_ticket_satisfaction_rated_signal(sender, instance, rating, **kwargs):
    """
    Handle customer satisfaction rating
    """
    try:
        logger.info(f"Satisfaction rating received: Ticket #{instance.id} - Rating: {rating}/5")
        
        # Create activity for satisfaction rating
        rating_text = "Excellent" if rating >= 4.5 else "Good" if rating >= 3.5 else "Fair" if rating >= 2.5 else "Poor"
        
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Customer satisfaction: {rating_text} ({rating}/5)",
            description=f"Customer rated their satisfaction as {rating}/5 stars",
            activity_type='feedback',
            entity_type='ticket',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.assigned_to,
            status='completed',
            completed_at=timezone.now(),
            priority='low'
        )
        
        # Send feedback to agent
        if instance.assigned_to:
            if rating >= 4:
                # Positive feedback
                send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='positive_feedback',
                    title=f"⭐ Great Job! Customer Satisfaction: {rating}/5",
                    message=f"Customer gave you {rating}/5 stars for ticket #{instance.id}. Keep up the excellent work!",
                    related_object_type='ticket',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='low'
                )
            elif rating <= 2:
                # Negative feedback - needs attention
                send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='negative_feedback',
                    title=f"⚠️ Low Satisfaction Rating: {rating}/5",
                    message=f"Customer gave {rating}/5 stars for ticket #{instance.id}. Please review and improve.",
                    related_object_type='ticket',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='medium'
                )
                
                # Notify manager for very low ratings
                if rating <= 1:
                    manager = getattr(instance.assigned_to, 'manager', None)
                    if manager:
                        send_notification_task.delay(
                            user_id=manager.id,
                            notification_type='very_low_satisfaction',
                            title=f"🚨 Very Low Satisfaction: {rating}/5 - Ticket #{instance.id}",
                            message=f"Customer gave very low satisfaction rating. Agent: {instance.assigned_to.get_full_name()}",
                            related_object_type='ticket',
                            related_object_id=instance.id,
                            tenant_id=instance.tenant.id,
                            priority='high'
                        )
        
        # Update agent satisfaction metrics
        if instance.assigned_to:
            update_agent_satisfaction_metrics(instance.assigned_to, rating)
        
        # Create follow-up for low ratings
        if rating <= 2:
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Follow up on low satisfaction rating: Ticket #{instance.id}",
                description=f"Customer gave {rating}/5 stars. Follow up to understand issues and improve.",
                activity_type='call',
                entity_type='ticket',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.assigned_to,
                due_date=timezone.now() + timedelta(hours=24),
                status='pending',
                priority='medium'
            )
        
    except Exception as e:
        logger.error(f"Error handling satisfaction rating signal: {e}")


def calculate_sla_due_date(priority, created_at):
    """
    Calculate SLA due date based on priority
    """
    sla_hours = {
        'critical': 2,   # 2 hours
        'high': 8,       # 8 hours
        'medium': 24,    # 24 hours
        'low': 72        # 72 hours
    }
    
    hours = sla_hours.get(priority, 24)
    return created_at + timedelta(hours=hours)


def calculate_resolution_time(created_at, resolved_at):
    """
    Calculate resolution time in minutes
    """
    if not resolved_at or not created_at:
        return None
    
    time_diff = resolved_at - created_at
    return int(time_diff.total_seconds() / 60)


def auto_assign_ticket(ticket):
    """
    Auto-assign ticket based on rules
    """
    try:
        # Simple round-robin assignment based on workload
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        
        User = get_user_model()
        
        # Find agents with support role
        agents = User.objects.filter(
            memberships__tenant=ticket.tenant,
            memberships__role__in=['support_agent', 'support_manager'],
            memberships__is_active=True,
            is_active=True
        ).annotate(
            active_tickets=Count('tickets_assigned', filter=Q(
                tickets_assigned__status__in=['open', 'in_progress', 'pending']
            ))
        ).order_by('active_tickets')
        
        # Return agent with least active tickets
        return agents.first() if agents.exists() else None
        
    except Exception as e:
        logger.error(f"Error in auto-assignment: {e}")
        return None


def find_available_senior_agent(tenant):
    """
    Find available senior agent for critical tickets
    """
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        
        User = get_user_model()
        
        # Find senior agents or managers
        senior_agents = User.objects.filter(
            memberships__tenant=tenant,
            memberships__role__in=['support_manager', 'senior_support_agent'],
            memberships__is_active=True,
            is_active=True
        ).annotate(
            critical_tickets=Count('tickets_assigned', filter=Q(
                tickets_assigned__priority='critical',
                tickets_assigned__status__in=['open', 'in_progress']
            ))
        ).order_by('critical_tickets')
        
        return senior_agents.first() if senior_agents.exists() else None
        
    except Exception as e:
        logger.error(f"Error finding senior agent: {e}")
        return None


def update_agent_performance_metrics(agent, ticket):
    """
    Update agent performance metrics
    """
    try:
        # This would update a separate AgentPerformance model
        # Implementation depends on your performance tracking requirements
        pass
    except Exception as e:
        logger.error(f"Error updating agent performance: {e}")


def update_agent_satisfaction_metrics(agent, rating):
    """
    Update agent satisfaction metrics
    """
    try:
        # This would update agent satisfaction averages
        # Implementation depends on your metrics tracking
        pass
    except Exception as e:
        logger.error(f"Error updating satisfaction metrics: {e}")


@receiver(post_delete, sender=Ticket)
def handle_ticket_deleted(sender, instance, **kwargs):
    """
    Handle ticket deletion
    """
    try:
        logger.info(f"Ticket deleted: #{instance.id} - {instance.subject}")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='ticket',
            object_id=instance.id,
            changes={
                'deleted': True,
                'subject': instance.subject,
                'priority': instance.priority,
                'status': instance.status,
                'customer': instance.customer.name if instance.customer else None
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in ticket post_delete signal: {e}")