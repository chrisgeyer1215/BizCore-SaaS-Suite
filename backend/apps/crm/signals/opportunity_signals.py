"""
Opportunity Signals
Handle opportunity lifecycle events and sales automation
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
import logging

from ..models import Opportunity, Activity, AuditTrail
from ..tasks.workflow_tasks import process_workflow_triggers_task
from ..tasks.scoring_tasks import update_opportunity_probabilities_task
from ..tasks.notification_tasks import send_notification_task

logger = logging.getLogger(__name__)

# Custom signals
opportunity_stage_changed = Signal()
opportunity_assigned = Signal()
opportunity_won = Signal()
opportunity_lost = Signal()
opportunity_probability_changed = Signal()


@receiver(post_save, sender=Opportunity)
def handle_opportunity_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle opportunity creation and updates
    """
    try:
        if created:
            # Opportunity created
            logger.info(f"Opportunity created: {instance.name} ({instance.id}) - Value: {instance.value}")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='opportunity',
                object_id=instance.id,
                changes={
                    'created': True,
                    'name': instance.name,
                    'value': float(instance.value) if instance.value else None,
                    'stage': instance.stage.name if instance.stage else None,
                    'account': instance.account.name if instance.account else None
                },
                timestamp=timezone.now()
            )
            
            # Create initial activity
            transaction.on_commit(lambda: Activity.objects.create(
                tenant=instance.tenant,
                subject=f"New opportunity created: {instance.name}",
                description=f"Opportunity worth {instance.value} created in {instance.stage.name if instance.stage else 'Unknown'} stage",
                activity_type='milestone',
                entity_type='opportunity',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.created_by,
                status='completed',
                completed_at=timezone.now(),
                priority='medium'
            ))
            
            # Send notification to assigned user
            if instance.assigned_to:
                transaction.on_commit(lambda: send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='opportunity_assigned',
                    title=f"New Opportunity: {instance.name}",
                    message=f"Opportunity worth {instance.value} has been assigned to you.",
                    related_object_type='opportunity',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='medium'
                ))
            
            # Trigger workflow processing
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='opportunity_created',
                entity_data={
                    'entity_type': 'opportunity',
                    'entity_id': instance.id,
                    'name': instance.name,
                    'value': float(instance.value) if instance.value else None,
                    'stage': instance.stage.name if instance.stage else None,
                    'probability': instance.probability,
                    'created_by': instance.created_by.id if instance.created_by else None
                }
            ))
            
        else:
            # Opportunity updated
            logger.info(f"Opportunity updated: {instance.name} ({instance.id})")
            
            # Trigger workflow processing for updates
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='opportunity_updated',
                entity_data={
                    'entity_type': 'opportunity',
                    'entity_id': instance.id,
                    'name': instance.name,
                    'value': float(instance.value) if instance.value else None,
                    'stage': instance.stage.name if instance.stage else None,
                    'probability': instance.probability,
                    'modified_by': instance.modified_by.id if instance.modified_by else None
                }
            ))
            
    except Exception as e:
        logger.error(f"Error in opportunity post_save signal: {e}")


@receiver(pre_save, sender=Opportunity)
def handle_opportunity_changes(sender, instance, **kwargs):
    """
    Detect and handle opportunity changes before saving
    """
    try:
        if instance.pk:  # Only for existing opportunities
            try:
                old_opportunity = Opportunity.objects.get(pk=instance.pk)
                
                # Check if stage changed
                if old_opportunity.stage != instance.stage:
                    logger.info(f"Opportunity stage changed: {old_opportunity.stage} -> {instance.stage} for {instance.name}")
                    
                    # Set stage change timestamp
                    instance.stage_changed_at = timezone.now()
                    
                    # Check if opportunity was won or lost
                    if instance.stage and instance.stage.is_won and not old_opportunity.stage.is_won:
                        instance.won_date = timezone.now()
                        transaction.on_commit(lambda: opportunity_won.send(
                            sender=sender,
                            instance=instance,
                            old_stage=old_opportunity.stage
                        ))
                    elif instance.stage and instance.stage.is_lost and not old_opportunity.stage.is_lost:
                        instance.lost_date = timezone.now()
                        transaction.on_commit(lambda: opportunity_lost.send(
                            sender=sender,
                            instance=instance,
                            old_stage=old_opportunity.stage
                        ))
                    
                    # Send stage change signal
                    transaction.on_commit(lambda: opportunity_stage_changed.send(
                        sender=sender,
                        instance=instance,
                        old_stage=old_opportunity.stage,
                        new_stage=instance.stage
                    ))
                
                # Check if assignment changed
                if old_opportunity.assigned_to != instance.assigned_to:
                    transaction.on_commit(lambda: opportunity_assigned.send(
                        sender=sender,
                        instance=instance,
                        old_assignee=old_opportunity.assigned_to,
                        new_assignee=instance.assigned_to
                    ))
                
                # Check if probability changed significantly
                old_prob = old_opportunity.probability or 0
                new_prob = instance.probability or 0
                if abs(old_prob - new_prob) >= 15:  # 15% threshold
                    transaction.on_commit(lambda: opportunity_probability_changed.send(
                        sender=sender,
                        instance=instance,
                        old_probability=old_prob,
                        new_probability=new_prob
                    ))
                    
            except Opportunity.DoesNotExist:
                pass  # New opportunity, no old version
                
    except Exception as e:
        logger.error(f"Error in opportunity pre_save signal: {e}")


@receiver(opportunity_stage_changed)
def handle_opportunity_stage_changed_signal(sender, instance, old_stage, new_stage, **kwargs):
    """
    Handle opportunity stage changes
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='stage_change',
            object_type='opportunity',
            object_id=instance.id,
            changes={
                'field': 'stage',
                'old_value': old_stage.name if old_stage else None,
                'new_value': new_stage.name if new_stage else None,
                'old_stage_id': old_stage.id if old_stage else None,
                'new_stage_id': new_stage.id if new_stage else None
            },
            timestamp=timezone.now()
        )
        
        # Create activity for stage change
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Opportunity stage changed: {old_stage.name if old_stage else 'None'} → {new_stage.name if new_stage else 'None'}",
            description=f"Opportunity moved to {new_stage.name if new_stage else 'Unknown'} stage",
            activity_type='stage_change',
            entity_type='opportunity',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='medium'
        )
        
        # Create follow-up activity based on stage
        if new_stage:
            if 'proposal' in new_stage.name.lower():
                # Create proposal follow-up
                Activity.objects.create(
                    tenant=instance.tenant,
                    subject=f"Follow up on proposal: {instance.name}",
                    description="Follow up on proposal status and next steps",
                    activity_type='call',
                    entity_type='opportunity',
                    entity_id=instance.id,
                    assigned_to=instance.assigned_to,
                    created_by=instance.modified_by,
                    due_date=timezone.now() + timezone.timedelta(days=3),
                    status='pending',
                    priority='high'
                )
            elif 'negotiation' in new_stage.name.lower():
                # Create negotiation follow-up
                Activity.objects.create(
                    tenant=instance.tenant,
                    subject=f"Continue negotiation: {instance.name}",
                    description="Continue negotiation and work towards closing",
                    activity_type='call',
                    entity_type='opportunity',
                    entity_id=instance.id,
                    assigned_to=instance.assigned_to,
                    created_by=instance.modified_by,
                    due_date=timezone.now() + timezone.timedelta(days=2),
                    status='pending',
                    priority='high'
                )
        
        # Trigger workflows
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='opportunity_stage_changed',
            entity_data={
                'entity_type': 'opportunity',
                'entity_id': instance.id,
                'name': instance.name,
                'old_stage': old_stage.name if old_stage else None,
                'new_stage': new_stage.name if new_stage else None,
                'value': float(instance.value) if instance.value else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling opportunity stage change signal: {e}")


@receiver(opportunity_won)
def handle_opportunity_won_signal(sender, instance, old_stage, **kwargs):
    """
    Handle opportunity won
    """
    try:
        logger.info(f"🎉 Opportunity WON: {instance.name} - Value: {instance.value}")
        
        # Create celebration activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"🎉 OPPORTUNITY WON: {instance.name}",
            description=f"Congratulations! Opportunity worth {instance.value} has been won!",
            activity_type='milestone',
            entity_type='opportunity',
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
                notification_type='opportunity_won',
                title=f"🎉 Congratulations! Opportunity Won: {instance.name}",
                message=f"You've won an opportunity worth {instance.value}! Excellent work!",
                related_object_type='opportunity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='high'
            )
        
        # Create follow-up activities for implementation/delivery
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Begin implementation: {instance.name}",
            description="Start implementation/delivery process for won opportunity",
            activity_type='task',
            entity_type='opportunity',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            due_date=timezone.now() + timezone.timedelta(days=3),
            status='pending',
            priority='high'
        )
        
        # Update account revenue if applicable
        if instance.account:
            from django.db.models import F
            from ..models import Account
            Account.objects.filter(id=instance.account.id).update(
                total_revenue=F('total_revenue') + instance.value
            )
        
    except Exception as e:
        logger.error(f"Error handling opportunity won signal: {e}")


@receiver(opportunity_lost)
def handle_opportunity_lost_signal(sender, instance, old_stage, **kwargs):
    """
    Handle opportunity lost
    """
    try:
        logger.info(f"💔 Opportunity LOST: {instance.name} - Value: {instance.value}")
        
        # Create loss activity
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"💔 Opportunity Lost: {instance.name}",
            description=f"Opportunity worth {instance.value} was lost. Reason: {instance.lost_reason or 'Not specified'}",
            activity_type='milestone',
            entity_type='opportunity',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='medium'
        )
        
        # Send notification
        if instance.assigned_to:
            send_notification_task.delay(
                user_id=instance.assigned_to.id,
                notification_type='opportunity_lost',
                title=f"Opportunity Lost: {instance.name}",
                message=f"Opportunity worth {instance.value} was lost. Consider lessons learned for future opportunities.",
                related_object_type='opportunity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
        # Create follow-up activity for lessons learned
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Post-mortem: {instance.name}",
            description="Analyze why this opportunity was lost and document lessons learned",
            activity_type='task',
            entity_type='opportunity',
            entity_id=instance.id,
            assigned_to=instance.assigned_to,
            created_by=instance.modified_by,
            due_date=timezone.now() + timezone.timedelta(days=5),
            status='pending',
            priority='low'
        )
        
    except Exception as e:
        logger.error(f"Error handling opportunity lost signal: {e}")


@receiver(opportunity_assigned)
def handle_opportunity_assigned_signal(sender, instance, old_assignee, new_assignee, **kwargs):
    """
    Handle opportunity assignment changes
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='assignment_change',
            object_type='opportunity',
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
            description = f"Opportunity reassigned from {old_assignee.get_full_name()} to {new_assignee.get_full_name()}"
        elif new_assignee:
            description = f"Opportunity assigned to {new_assignee.get_full_name()}"
        else:
            description = f"Opportunity unassigned from {old_assignee.get_full_name()}"
        
        Activity.objects.create(
            tenant=instance.tenant,
            subject="Opportunity assignment changed",
            description=description,
            activity_type='assignment',
            entity_type='opportunity',
            entity_id=instance.id,
            assigned_to=new_assignee,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Send notifications
        if new_assignee:
            send_notification_task.delay(
                user_id=new_assignee.id,
                notification_type='opportunity_assigned',
                title=f"Opportunity Assigned: {instance.name}",
                message=f"Opportunity worth {instance.value} has been assigned to you.",
                related_object_type='opportunity',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
    except Exception as e:
        logger.error(f"Error handling opportunity assignment signal: {e}")


@receiver(opportunity_probability_changed)
def handle_opportunity_probability_changed_signal(sender, instance, old_probability, new_probability, **kwargs):
    """
    Handle significant probability changes
    """
    try:
        # Create activity for significant changes
        if new_probability >= 75 and old_probability < 75:
            # High probability opportunity
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"🎯 High probability opportunity: {instance.name} ({new_probability}%)",
                description=f"Opportunity probability increased from {old_probability}% to {new_probability}% - Focus on closing!",
                activity_type='alert',
                entity_type='opportunity',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by,
                status='pending',
                priority='high',
                due_date=timezone.now() + timezone.timedelta(hours=4)
            )
            
            # Send high priority notification
            if instance.assigned_to:
                send_notification_task.delay(
                    user_id=instance.assigned_to.id,
                    notification_type='opportunity_high_probability',
                    title=f"🎯 High Probability Opportunity: {instance.name}",
                    message=f"Opportunity probability is now {new_probability}%! Focus on closing this deal.",
                    related_object_type='opportunity',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='high'
                )
        
        elif new_probability <= 25 and old_probability > 25:
            # Low probability - needs attention
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"⚠️ Low probability opportunity: {instance.name} ({new_probability}%)",
                description=f"Opportunity probability decreased from {old_probability}% to {new_probability}% - Needs attention!",
                activity_type='alert',
                entity_type='opportunity',
                entity_id=instance.id,
                assigned_to=instance.assigned_to,
                created_by=instance.modified_by,
                status='pending',
                priority='medium',
                due_date=timezone.now() + timezone.timedelta(days=1)
            )
        
    except Exception as e:
        logger.error(f"Error handling opportunity probability change signal: {e}")


@receiver(post_delete, sender=Opportunity)
def handle_opportunity_deleted(sender, instance, **kwargs):
    """
    Handle opportunity deletion
    """
    try:
        logger.info(f"Opportunity deleted: {instance.name} ({instance.id})")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='opportunity',
            object_id=instance.id,
            changes={
                'deleted': True,
                'name': instance.name,
                'value': float(instance.value) if instance.value else None,
                'stage': instance.stage.name if instance.stage else None
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in opportunity post_delete signal: {e}")