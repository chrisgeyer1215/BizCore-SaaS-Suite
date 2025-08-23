"""
Activity Signals
Handle activity lifecycle events and communication automation
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
import logging

from ..models import Activity, AuditTrail, Lead, Opportunity, Account, Contact
from ..tasks.workflow_tasks import process_workflow_triggers_task
from ..tasks.notification_tasks import send_notification_task
from ..tasks.reminder_tasks import send_activity_reminders_task

logger = logging.getLogger(__name__)

# Custom signals
activity_completed = Signal()
activity_overdue = Signal()
activity_assigned = Signal()
activity_reminder_sent = Signal()


@receiver(post_save, sender=Activity)
def handle_activity_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle activity creation and updates
    """
    try:
        if created:
            # Activity created
            logger.info(f"Activity created: {instance.subject} ({instance.id}) - Type: {instance.activity_type}")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='activity',
                object_id=instance.id,
                changes={
                    'created': True,
                    'subject': instance.subject,
                    'activity_type': instance.activity_type,
                    'entity_type': instance.entity_type,
                    'entity_id': instance.entity_id,
                    'assigned_to': instance.assigned_to.get_full_name() if instance.assigned_to else None
                },
                timestamp=timezone.now()
            )
            
            # Update last activity date on related entity
            transaction.on_commit(lambda: update_entity_last_activity_date(
                instance.entity_type,
                instance.entity_id,
                instance.tenant
            ))
            
            # Send notification to assigned user if different from creator
            if instance.assigned_to and instance.assigned_to != instance.created_by:
                transaction.on_commit(lambda: send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='activity_assigned',
                    title=f"New {instance.activity_type.title()}: {instance.subject}",
                    message=f"A new {instance.activity_type} has been assigned to you.",
                    related_object_type='activity',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='medium' if instance.priority == 'high' else 'low'
                ))
            
            # Trigger workflow processing
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='activity_created',
                entity_data={
                    'entity_type': 'activity',
                    'entity_id': instance.id,
                    'activity_type': instance.activity_type,
                    'subject': instance.subject,
                    'related_entity_type': instance.entity_type,
                    'related_entity_id': instance.entity_id,
                    'assigned_to': instance.assigned_to.id if instance.assigned_to else None,
                    'priority': instance.priority,
                    'due_date': instance.due_date.isoformat() if instance.due_date else None
                }
            ))
            
        else:
            # Activity updated
            logger.info(f"Activity updated: {instance.subject} ({instance.id})")
            
            # Trigger workflow processing for updates
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='activity_updated',
                entity_data={
                    'entity_type': 'activity',
                    'entity_id': instance.id,
                    'activity_type': instance.activity_type,
                    'subject': instance.subject,
                    'status': instance.status,
                    'modified_by': instance.modified_by.id if instance.modified_by else None
                }
            ))
            
    except Exception as e:
        logger.error(f"Error in activity post_save signal: {e}")


@receiver(pre_save, sender=Activity)
def handle_activity_status_change(sender, instance, **kwargs):
    """
    Detect and handle activity status changes
    """
    try:
        if instance.pk:  # Only for existing activities
            try:
                old_activity = Activity.objects.get(pk=instance.pk)
                
                # Check if status changed to completed
                if old_activity.status != 'completed' and instance.status == 'completed':
                    logger.info(f"Activity completed: {instance.subject} ({instance.id})")
                    
                    # Set completion timestamp
                    if not instance.completed_at:
                        instance.completed_at = timezone.now()
                    
                    # Send completion signal
                    transaction.on_commit(lambda: activity_completed.send(
                        sender=sender,
                        instance=instance,
                        old_status=old_activity.status
                    ))
                
                # Check if assignment changed
                if old_activity.assigned_to != instance.assigned_to:
                    transaction.on_commit(lambda: activity_assigned.send(
                        sender=sender,
                        instance=instance,
                        old_assignee=old_activity.assigned_to,
                        new_assignee=instance.assigned_to
                    ))
                
                # Check if activity became overdue
                if (instance.due_date and instance.due_date < timezone.now() and
                    instance.status in ['pending', 'open'] and
                    old_activity.status in ['pending', 'open'] and
                    not getattr(instance, '_overdue_signal_sent', False)):
                    
                    transaction.on_commit(lambda: activity_overdue.send(
                        sender=sender,
                        instance=instance
                    ))
                    
            except Activity.DoesNotExist:
                pass  # New activity
                
    except Exception as e:
        logger.error(f"Error in activity pre_save signal: {e}")


@receiver(activity_completed)
def handle_activity_completed_signal(sender, instance, old_status, **kwargs):
    """
    Handle activity completion
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='status_change',
            object_type='activity',
            object_id=instance.id,
            changes={
                'field': 'status',
                'old_value': old_status,
                'new_value': 'completed',
                'completed_at': instance.completed_at.isoformat() if instance.completed_at else None
            },
            timestamp=timezone.now()
        )
        
        # Update entity engagement metrics
        update_entity_engagement_metrics(
            instance.entity_type,
            instance.entity_id,
            instance.tenant,
            instance.activity_type
        )
        
        # Create follow-up activities based on type and outcome
        if instance.activity_type == 'call' and instance.outcome in ['interested', 'callback_requested']:
            # Schedule follow-up call
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Follow-up call: {instance.subject}",
                description=f"Follow-up on previous call - Outcome: {instance.outcome}",
                activity_type='call',
                entity_type=instance.entity_type,
                entity_id=instance.entity_id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by or instance.created_by,
                due_date=timezone.now() + timezone.timedelta(days=3),
                status='pending',
                priority=instance.priority
            )
            
        elif instance.activity_type == 'email' and instance.outcome == 'no_response':
            # Schedule follow-up email after a week
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Follow-up email: {instance.subject}",
                description="Follow-up email - no response to previous message",
                activity_type='email',
                entity_type=instance.entity_type,
                entity_id=instance.entity_id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by or instance.created_by,
                due_date=timezone.now() + timezone.timedelta(days=7),
                status='pending',
                priority='low'
            )
            
        elif instance.activity_type == 'meeting' and instance.outcome == 'next_steps_agreed':
            # Create task for next steps
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Execute next steps from meeting: {instance.subject}",
                description="Execute agreed next steps from meeting",
                activity_type='task',
                entity_type=instance.entity_type,
                entity_id=instance.entity_id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by or instance.created_by,
                due_date=timezone.now() + timezone.timedelta(days=2),
                status='pending',
                priority='high'
            )
        
        # Send completion notification if configured
        if instance.assigned_to and hasattr(instance, 'notify_on_completion') and instance.notify_on_completion:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='activity_completed',
                title=f"Activity Completed: {instance.subject}",
                message=f"Your {instance.activity_type} has been marked as completed.",
                related_object_type='activity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
        # Trigger workflows for activity completion
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='activity_completed',
            entity_data={
                'entity_type': 'activity',
                'entity_id': instance.id,
                'activity_type': instance.activity_type,
                'outcome': instance.outcome,
                'related_entity_type': instance.entity_type,
                'related_entity_id': instance.entity_id,
                'duration': instance.duration,
                'completed_by': instance.modified_by.id if instance.modified_by else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling activity completion signal: {e}")


@receiver(activity_overdue)
def handle_activity_overdue_signal(sender, instance, **kwargs):
    """
    Handle overdue activities
    """
    try:
        logger.warning(f"Activity overdue: {instance.subject} ({instance.id}) - Due: {instance.due_date}")
        
        # Mark as overdue processed to avoid duplicate signals
        instance._overdue_signal_sent = True
        
        # Create overdue activity notification
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"⚠️ OVERDUE: {instance.subject}",
            description=f"Activity was due on {instance.due_date} and is now overdue",
            activity_type='alert',
            entity_type=instance.entity_type,
            entity_id=instance.entity_id,
            assigned_to=instance.assigned_to,
            created_by=instance.assigned_to,  # System-generated
            status='pending',
            priority='high',
            due_date=timezone.now() + timezone.timedelta(hours=2)
        )
        
        # Send overdue notification
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='activity_overdue',
                title=f"⚠️ Overdue Activity: {instance.subject}",
                message=f"Your {instance.activity_type} was due on {instance.due_date.strftime('%B %d, %Y at %I:%M %p')} and is now overdue.",
                related_object_type='activity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='high'
            )
        
        # Notify manager if activity is high priority and significantly overdue
        overdue_hours = (timezone.now() - instance.due_date).total_seconds() / 3600
        if instance.priority == 'high' and overdue_hours > 24:
            # Find manager (this logic might need adjustment based on your org structure)
            manager = getattr(instance.assigned_to, 'manager', None)
            if manager:
                send_notification_task.delay(
                    user_id=manager.id,
                    notification_type='activity_overdue_escalation',
                    title=f"🔥 Escalation: Overdue High Priority Activity",
                    message=f"High priority {instance.activity_type} assigned to {instance.assigned_to.get_full_name()} is {int(overdue_hours)} hours overdue.",
                    related_object_type='activity',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='critical'
                )
        
        # Trigger workflows for overdue activities
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='activity_overdue',
            entity_data={
                'entity_type': 'activity',
                'entity_id': instance.id,
                'activity_type': instance.activity_type,
                'overdue_hours': overdue_hours,
                'priority': instance.priority,
                'assigned_to': instance.assigned_to.id if instance.assigned_to else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling activity overdue signal: {e}")


@receiver(activity_assigned)
def handle_activity_assigned_signal(sender, instance, old_assignee, new_assignee, **kwargs):
    """
    Handle activity assignment changes
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='assignment_change',
            object_type='activity',
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
        
        # Send notifications
        if new_assignee and new_assignee != old_assignee:
            send_notification_task.delay(
                user_id=new_assignee.id,
                notification_type='activity_assigned',
                title=f"{instance.activity_type.title()} Assigned: {instance.subject}",
                message=f"A {instance.activity_type} has been assigned to you.",
                related_object_type='activity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
        # Notify previous assignee if reassigned
        if old_assignee and new_assignee and old_assignee != new_assignee:
            send_notification_task.delay(
                user_id=old_assignee.id,
                notification_type='activity_reassigned',
                title=f"Activity Reassigned: {instance.subject}",
                message=f"Your {instance.activity_type} has been reassigned to {new_assignee.get_full_name()}.",
                related_object_type='activity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
    except Exception as e:
        logger.error(f"Error handling activity assignment signal: {e}")


def update_entity_last_activity_date(entity_type, entity_id, tenant):
    """
    Update the last activity date on related entities
    """
    try:
        if entity_type == 'lead':
            Lead.objects.filter(id=entity_id, tenant=tenant).update(
                last_activity_date=timezone.now()
            )
        elif entity_type == 'opportunity':
            Opportunity.objects.filter(id=entity_id, tenant=tenant).update(
                last_activity_date=timezone.now()
            )
        elif entity_type == 'account':
            Account.objects.filter(id=entity_id, tenant=tenant).update(
                last_activity_date=timezone.now()
            )
        elif entity_type == 'contact':
            Contact.objects.filter(id=entity_id, tenant=tenant).update(
                last_activity_date=timezone.now()
            )
            
    except Exception as e:
        logger.error(f"Error updating entity last activity date: {e}")


def update_entity_engagement_metrics(entity_type, entity_id, tenant, activity_type):
    """
    Update engagement metrics on related entities
    """
    try:
        from django.db.models import F
        
        if entity_type == 'contact':
            # Update contact engagement score
            Contact.objects.filter(id=entity_id, tenant=tenant).update(
                engagement_score=F('engagement_score') + get_activity_engagement_points(activity_type),
                last_engagement_date=timezone.now()
            )
        elif entity_type == 'account':
            # Update account engagement
            Account.objects.filter(id=entity_id, tenant=tenant).update(
                last_engagement_date=timezone.now()
            )
            
    except Exception as e:
        logger.error(f"Error updating entity engagement metrics: {e}")


def get_activity_engagement_points(activity_type):
    """
    Get engagement points for different activity types
    """
    points_map = {
        'call': 5,
        'meeting': 10,
        'email': 2,
        'task': 3,
        'note': 1,
        'demo': 15,
        'proposal': 20
    }
    return points_map.get(activity_type, 1)


@receiver(post_delete, sender=Activity)
def handle_activity_deleted(sender, instance, **kwargs):
    """
    Handle activity deletion
    """
    try:
        logger.info(f"Activity deleted: {instance.subject} ({instance.id})")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='activity',
            object_id=instance.id,
            changes={
                'deleted': True,
                'subject': instance.subject,
                'activity_type': instance.activity_type,
                'entity_type': instance.entity_type,
                'entity_id': instance.entity_id
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in activity post_delete signal: {e}")