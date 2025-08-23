"""
Lead Signals
Handle lead lifecycle events and automation triggers
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
import logging

from ..models import Lead, Activity, WorkflowExecution, AuditTrail
from ..tasks.workflow_tasks import process_workflow_triggers_task
from ..tasks.scoring_tasks import calculate_lead_scores_task
from ..tasks.notification_tasks import send_notification_task

logger = logging.getLogger(__name__)

# Custom signals
lead_status_changed = Signal()
lead_assigned = Signal()
lead_scored = Signal()
lead_converted = Signal()
lead_qualified = Signal()


@receiver(post_save, sender=Lead)
def handle_lead_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle lead creation and updates
    """
    try:
        if created:
            # Lead created
            logger.info(f"Lead created: {instance.first_name} {instance.last_name} ({instance.id})")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='lead',
                object_id=instance.id,
                changes={
                    'created': True,
                    'email': instance.email,
                    'company': instance.company,
                    'source': instance.source.name if instance.source else None
                },
                timestamp=timezone.now()
            )
            
            # Trigger workflow processing
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='lead_created',
                entity_data={
                    'entity_type': 'lead',
                    'entity_id': instance.id,
                    'email': instance.email,
                    'company': instance.company,
                    'source': instance.source.name if instance.source else None,
                    'created_by': instance.created_by.id if instance.created_by else None
                }
            ))
            
            # Schedule lead scoring if not already scored
            if not instance.score:
                transaction.on_commit(lambda: calculate_lead_scores_task.delay(
                    tenant_id=instance.tenant.id,
                    lead_ids=[instance.id]
                ))
            
            # Create welcome activity
            transaction.on_commit(lambda: Activity.objects.create(
                tenant=instance.tenant,
                subject=f"New lead: {instance.first_name} {instance.last_name}",
                description=f"Lead created from {instance.source.name if instance.source else 'Unknown source'}",
                activity_type='note',
                entity_type='lead',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.created_by,
                status='completed',
                completed_at=timezone.now()
            ))
            
            # Send notification to assigned user
            if instance.assigned_to:
                transaction.on_commit(lambda: send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='lead_assigned',
                    title=f"New Lead Assigned: {instance.first_name} {instance.last_name}",
                    message=f"A new lead from {instance.company or 'Unknown company'} has been assigned to you.",
                    related_object_type='lead',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='medium'
                ))
        
        else:
            # Lead updated
            logger.info(f"Lead updated: {instance.first_name} {instance.last_name} ({instance.id})")
            
            # Trigger workflow processing for updates
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='lead_updated',
                entity_data={
                    'entity_type': 'lead',
                    'entity_id': instance.id,
                    'email': instance.email,
                    'company': instance.company,
                    'status': instance.status,
                    'score': instance.score,
                    'modified_by': instance.modified_by.id if instance.modified_by else None
                }
            ))
            
    except Exception as e:
        logger.error(f"Error in lead post_save signal: {e}")


@receiver(pre_save, sender=Lead)
def handle_lead_status_change(sender, instance, **kwargs):
    """
    Detect and handle lead status changes
    """
    try:
        if instance.pk:  # Only for existing leads
            try:
                old_lead = Lead.objects.get(pk=instance.pk)
                
                # Check if status changed
                if old_lead.status != instance.status:
                    logger.info(f"Lead status changed: {old_lead.status} -> {instance.status} for lead {instance.id}")
                    
                    # Set status change timestamp
                    if instance.status == 'qualified' and not instance.qualified_at:
                        instance.qualified_at = timezone.now()
                    elif instance.status == 'converted' and not instance.converted_at:
                        instance.converted_at = timezone.now()
                    
                    # Send custom signal
                    transaction.on_commit(lambda: lead_status_changed.send(
                        sender=sender,
                        instance=instance,
                        old_status=old_lead.status,
                        new_status=instance.status
                    ))
                
                # Check if assignment changed
                if old_lead.assigned_to != instance.assigned_to:
                    if instance.assigned_to:
                        instance.assigned_at = timezone.now()
                        
                        # Send custom signal
                        transaction.on_commit(lambda: lead_assigned.send(
                            sender=sender,
                            instance=instance,
                            old_assignee=old_lead.assigned_to,
                            new_assignee=instance.assigned_to
                        ))
                
                # Check if score changed significantly
                old_score = old_lead.score or 0
                new_score = instance.score or 0
                if abs(old_score - new_score) >= 10:  # 10 point threshold
                    transaction.on_commit(lambda: lead_scored.send(
                        sender=sender,
                        instance=instance,
                        old_score=old_score,
                        new_score=new_score
                    ))
                    
            except Lead.DoesNotExist:
                pass  # New lead, no old version to compare
                
    except Exception as e:
        logger.error(f"Error in lead pre_save signal: {e}")


@receiver(lead_status_changed)
def handle_lead_status_changed_signal(sender, instance, old_status, new_status, **kwargs):
    """
    Handle lead status change custom signal
    """
    try:
        # Create audit trail for status change
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='status_change',
            object_type='lead',
            object_id=instance.id,
            changes={
                'field': 'status',
                'old_value': old_status,
                'new_value': new_status
            },
            timestamp=timezone.now()
        )
        
        # Create activity for status change
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Lead status changed: {old_status} → {new_status}",
            description=f"Lead status updated from {old_status} to {new_status}",
            activity_type='status_change',
            entity_type='lead',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Handle specific status transitions
        if new_status == 'qualified':
            lead_qualified.send(sender=sender, instance=instance, old_status=old_status)
        elif new_status == 'converted':
            lead_converted.send(sender=sender, instance=instance, old_status=old_status)
        
        # Trigger workflows for status change
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='lead_status_changed',
            entity_data={
                'entity_type': 'lead',
                'entity_id': instance.id,
                'old_status': old_status,
                'new_status': new_status,
                'email': instance.email,
                'company': instance.company
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling lead status change signal: {e}")


@receiver(lead_assigned)
def handle_lead_assigned_signal(sender, instance, old_assignee, new_assignee, **kwargs):
    """
    Handle lead assignment change
    """
    try:
        # Create audit trail for assignment change
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='assignment_change',
            object_type='lead',
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
        
        # Create activity for assignment change
        if old_assignee and new_assignee:
            description = f"Lead reassigned from {old_assignee.get_full_name()} to {new_assignee.get_full_name()}"
        elif new_assignee:
            description = f"Lead assigned to {new_assignee.get_full_name()}"
        else:
            description = f"Lead unassigned from {old_assignee.get_full_name()}"
        
        Activity.objects.create(
            tenant=instance.tenant,
            subject="Lead assignment changed",
            description=description,
            activity_type='assignment',
            entity_type='lead',
            entity_id=instance.id,
            assigned_to=new_assignee,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Send notification to new assignee
        if new_assignee:
            send_notification_task.delay(
                user_id=new_assignee.id,
                notification_type='lead_assigned',
                title=f"Lead Assigned: {instance.first_name} {instance.last_name}",
                message=f"Lead from {instance.company or 'Unknown company'} has been assigned to you.",
                related_object_type='lead',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
        # Send notification to old assignee if reassigned
        if old_assignee and new_assignee and old_assignee != new_assignee:
            send_notification_task.delay(
                user_id=old_assignee.id,
                notification_type='lead_reassigned',
                title=f"Lead Reassigned: {instance.first_name} {instance.last_name}",
                message=f"Lead has been reassigned to {new_assignee.get_full_name()}.",
                related_object_type='lead',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='low'
            )
        
    except Exception as e:
        logger.error(f"Error handling lead assignment signal: {e}")


@receiver(lead_qualified)
def handle_lead_qualified_signal(sender, instance, old_status, **kwargs):
    """
    Handle lead qualification
    """
    try:
        logger.info(f"Lead qualified: {instance.first_name} {instance.last_name} ({instance.id})")
        
        # Create activity for qualification
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Lead qualified: {instance.first_name} {instance.last_name}",
            description=f"Lead has been qualified and is ready for opportunity creation",
            activity_type='milestone',
            entity_type='lead',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='high'
        )
        
        # Send notification to assigned user
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='lead_qualified',
                title=f"Lead Qualified: {instance.first_name} {instance.last_name}",
                message=f"Lead is now qualified and ready for opportunity creation.",
                related_object_type='lead',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='high'
            )
        
        # Create follow-up activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Follow up on qualified lead: {instance.first_name} {instance.last_name}",
            description="Create opportunity for qualified lead",
            activity_type='task',
            entity_type='lead',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            due_date=timezone.now() + timezone.timedelta(hours=24),
            status='pending',
            priority='high'
        )
        
    except Exception as e:
        logger.error(f"Error handling lead qualification signal: {e}")


@receiver(lead_converted)
def handle_lead_converted_signal(sender, instance, old_status, **kwargs):
    """
    Handle lead conversion
    """
    try:
        logger.info(f"Lead converted: {instance.first_name} {instance.last_name} ({instance.id})")
        
        # Create activity for conversion
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"🎉 Lead converted: {instance.first_name} {instance.last_name}",
            description=f"Lead has been successfully converted to opportunity/customer",
            activity_type='milestone',
            entity_type='lead',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='high'
        )
        
        # Send congratulations notification
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='lead_converted',
                title=f"🎉 Congratulations! Lead Converted: {instance.first_name} {instance.last_name}",
                message=f"Your lead has been successfully converted. Great work!",
                related_object_type='lead',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='high'
            )
        
        # Update lead conversion metrics
        from ..models import LeadSource
        if instance.source:
            # This could be done in a background task for performance
            LeadSource.objects.filter(id=instance.source.id).update(
                conversions=F('conversions') + 1
            )
        
    except Exception as e:
        logger.error(f"Error handling lead conversion signal: {e}")


@receiver(lead_scored)
def handle_lead_scored_signal(sender, instance, old_score, new_score, **kwargs):
    """
    Handle significant lead score changes
    """
    try:
        # Create activity for significant score changes
        if new_score >= 80 and old_score < 80:
            # Lead became hot
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"🔥 Hot lead: {instance.first_name} {instance.last_name} (Score: {new_score})",
                description=f"Lead score increased from {old_score} to {new_score} - High priority follow-up needed",
                activity_type='alert',
                entity_type='lead',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by,
                status='pending',
                priority='high',
                due_date=timezone.now() + timezone.timedelta(hours=2)
            )
            
            # Send high priority notification
            if instance.assigned_to:
                send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='lead_hot',
                    title=f"🔥 Hot Lead Alert: {instance.first_name} {instance.last_name}",
                    message=f"Lead score increased to {new_score}! High priority follow-up recommended.",
                    related_object_type='lead',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='high'
                )
        
    except Exception as e:
        logger.error(f"Error handling lead scoring signal: {e}")


@receiver(post_delete, sender=Lead)
def handle_lead_deleted(sender, instance, **kwargs):
    """
    Handle lead deletion
    """
    try:
        logger.info(f"Lead deleted: {instance.first_name} {instance.last_name} ({instance.id})")
        
        # Create audit trail for deletion
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='lead',
            object_id=instance.id,
            changes={
                'deleted': True,
                'email': instance.email,
                'company': instance.company,
                'status': instance.status
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in lead post_delete signal: {e}")