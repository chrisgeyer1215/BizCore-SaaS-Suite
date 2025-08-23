"""
Campaign Signals
Handle campaign lifecycle events and marketing automation
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
import logging

from ..models import Campaign, CampaignMember, Activity, AuditTrail
from ..tasks.workflow_tasks import process_workflow_triggers_task
from ..tasks.notification_tasks import send_notification_task
from ..tasks.campaign_tasks import execute_campaign_task, process_campaign_analytics_task

logger = logging.getLogger(__name__)

# Custom signals
campaign_started = Signal()
campaign_completed = Signal()
campaign_member_added = Signal()
campaign_email_sent = Signal()
campaign_email_opened = Signal()
campaign_email_clicked = Signal()


@receiver(post_save, sender=Campaign)
def handle_campaign_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle campaign creation and updates
    """
    try:
        if created:
            # Campaign created
            logger.info(f"Campaign created: {instance.name} ({instance.id}) - Type: {instance.campaign_type}")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='campaign',
                object_id=instance.id,
                changes={
                    'created': True,
                    'name': instance.name,
                    'campaign_type': instance.campaign_type,
                    'status': instance.status,
                    'budget': float(instance.budget) if instance.budget else None,
                    'start_date': instance.start_date.isoformat() if instance.start_date else None
                },
                timestamp=timezone.now()
            )
            
            # Create initial activity
            transaction.on_commit(lambda: Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Campaign created: {instance.name}",
                description=f"New {instance.campaign_type} campaign created with budget of {instance.budget}",
                activity_type='campaign',
                entity_type='campaign',
                entity_id=instance.id,
                assigned_to=instance.created_by,
                created_by=instance.created_by,
                status='completed',
                completed_at=timezone.now()
            ))
            
            # Trigger workflow processing
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='campaign_created',
                entity_data={
                    'entity_type': 'campaign',
                    'entity_id': instance.id,
                    'name': instance.name,
                    'campaign_type': instance.campaign_type,
                    'status': instance.status,
                    'budget': float(instance.budget) if instance.budget else None,
                    'created_by': instance.created_by.id if instance.created_by else None
                }
            ))
            
        else:
            # Campaign updated
            logger.info(f"Campaign updated: {instance.name} ({instance.id})")
            
            # Trigger workflow processing for updates
            transaction.on_commit(lambda: process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='campaign_updated',
                entity_data={
                    'entity_type': 'campaign',
                    'entity_id': instance.id,
                    'name': instance.name,
                    'status': instance.status,
                    'modified_by': instance.modified_by.id if instance.modified_by else None
                }
            ))
            
    except Exception as e:
        logger.error(f"Error in campaign post_save signal: {e}")


@receiver(pre_save, sender=Campaign)
def handle_campaign_status_change(sender, instance, **kwargs):
    """
    Detect and handle campaign status changes
    """
    try:
        if instance.pk:  # Only for existing campaigns
            try:
                old_campaign = Campaign.objects.get(pk=instance.pk)
                
                # Check if status changed to active (started)
                if old_campaign.status != 'active' and instance.status == 'active':
                    logger.info(f"Campaign started: {instance.name} ({instance.id})")
                    
                    # Set start timestamp
                    if not instance.started_at:
                        instance.started_at = timezone.now()
                    
                    # Send start signal
                    transaction.on_commit(lambda: campaign_started.send(
                        sender=sender,
                        instance=instance,
                        old_status=old_campaign.status
                    ))
                
                # Check if status changed to completed
                elif old_campaign.status != 'completed' and instance.status == 'completed':
                    logger.info(f"Campaign completed: {instance.name} ({instance.id})")
                    
                    # Set completion timestamp
                    if not instance.completed_at:
                        instance.completed_at = timezone.now()
                    
                    # Send completion signal
                    transaction.on_commit(lambda: campaign_completed.send(
                        sender=sender,
                        instance=instance,
                        old_status=old_campaign.status
                    ))
                    
            except Campaign.DoesNotExist:
                pass  # New campaign
                
    except Exception as e:
        logger.error(f"Error in campaign pre_save signal: {e}")


@receiver(campaign_started)
def handle_campaign_started_signal(sender, instance, old_status, **kwargs):
    """
    Handle campaign start
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='status_change',
            object_type='campaign',
            object_id=instance.id,
            changes={
                'field': 'status',
                'old_value': old_status,
                'new_value': 'active',
                'started_at': instance.started_at.isoformat() if instance.started_at else None
            },
            timestamp=timezone.now()
        )
        
        # Create activity for campaign start
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"🚀 Campaign Started: {instance.name}",
            description=f"Campaign has been activated and is now running",
            activity_type='campaign',
            entity_type='campaign',
            entity_id=instance.id,
            assigned_to=instance.created_by,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='medium'
        )
        
        # Send notification to campaign owner
        if instance.created_by:
            send_notification_task.delay(
                user_id=instance.created_by.id,
                notification_type='campaign_started',
                title=f"🚀 Campaign Started: {instance.name}",
                message=f"Your {instance.campaign_type} campaign is now active and running.",
                related_object_type='campaign',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
        # Execute campaign if it's automated
        if instance.campaign_type in ['email', 'social'] and instance.auto_execute:
            execute_campaign_task.delay(
                campaign_id=instance.id,
                tenant_id=instance.tenant.id
            )
        
        # Trigger workflows for campaign start
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='campaign_started',
            entity_data={
                'entity_type': 'campaign',
                'entity_id': instance.id,
                'name': instance.name,
                'campaign_type': instance.campaign_type,
                'budget': float(instance.budget) if instance.budget else None,
                'member_count': instance.member_count or 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling campaign start signal: {e}")


@receiver(campaign_completed)
def handle_campaign_completed_signal(sender, instance, old_status, **kwargs):
    """
    Handle campaign completion
    """
    try:
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=instance.modified_by,
            action='status_change',
            object_type='campaign',
            object_id=instance.id,
            changes={
                'field': 'status',
                'old_value': old_status,
                'new_value': 'completed',
                'completed_at': instance.completed_at.isoformat() if instance.completed_at else None
            },
            timestamp=timezone.now()
        )
        
        # Create activity for campaign completion
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"✅ Campaign Completed: {instance.name}",
            description=f"Campaign has finished running and is now complete",
            activity_type='campaign',
            entity_type='campaign',
            entity_id=instance.id,
            assigned_to=instance.created_by,
            created_by=instance.modified_by,
            status='completed',
            completed_at=timezone.now(),
            priority='medium'
        )
        
        # Send notification to campaign owner
        if instance.created_by:
            send_notification_task.delay(
                user_id=instance.created_by.id,
                notification_type='campaign_completed',
                title=f"✅ Campaign Completed: {instance.name}",
                message=f"Your {instance.campaign_type} campaign has finished running. Check the results!",
                related_object_type='campaign',
                related_object_id=instance.id,
                tenant_id=instance.tenant.id,
                priority='medium'
            )
        
        # Schedule analytics processing
        process_campaign_analytics_task.delay(
            campaign_id=instance.id,
            tenant_id=instance.tenant.id
        )
        
        # Create follow-up activity for results review
        Activity.objects.create(
            tenant=instance.tenant,
            subject=f"Review campaign results: {instance.name}",
            description="Review campaign performance metrics and results",
            activity_type='task',
            entity_type='campaign',
            entity_id=instance.id,
            assigned_to=instance.created_by,
            created_by=instance.modified_by or instance.created_by,
            due_date=timezone.now() + timezone.timedelta(days=1),
            status='pending',
            priority='medium'
        )
        
        # Trigger workflows for campaign completion
        process_workflow_triggers_task.delay(
            tenant_id=instance.tenant.id,
            trigger_type='campaign_completed',
            entity_data={
                'entity_type': 'campaign',
                'entity_id': instance.id,
                'name': instance.name,
                'campaign_type': instance.campaign_type,
                'final_budget_spent': float(instance.actual_cost) if instance.actual_cost else 0,
                'leads_generated': instance.leads_generated or 0,
                'roi_percentage': instance.roi_percentage or 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling campaign completion signal: {e}")


@receiver(post_save, sender=CampaignMember)
def handle_campaign_member_added(sender, instance, created, **kwargs):
    """
    Handle campaign member addition
    """
    try:
        if created:
            logger.info(f"Member added to campaign: {instance.campaign.name} - Member ID: {instance.id}")
            
            # Update campaign member count
            from django.db.models import F
            Campaign.objects.filter(id=instance.campaign.id).update(
                member_count=F('member_count') + 1
            )
            
            # Send custom signal
            campaign_member_added.send(
                sender=sender,
                instance=instance,
                campaign=instance.campaign
            )
            
            # Create activity for member addition
            Activity.objects.create(
                tenant=instance.tenant,
                subject=f"Member added to campaign: {instance.campaign.name}",
                description=f"New member added to campaign",
                activity_type='campaign',
                entity_type='campaign',
                entity_id=instance.campaign.id,
                assigned_to=instance.campaign.created_by,
                created_by=instance.campaign.created_by,
                status='completed',
                completed_at=timezone.now()
            )
            
            # Trigger workflows
            process_workflow_triggers_task.delay(
                tenant_id=instance.tenant.id,
                trigger_type='campaign_member_added',
                entity_data={
                    'entity_type': 'campaign_member',
                    'entity_id': instance.id,
                    'campaign_id': instance.campaign.id,
                    'campaign_name': instance.campaign.name,
                    'member_email': instance.email if hasattr(instance, 'email') else None
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling campaign member addition: {e}")


@receiver(campaign_email_sent)
def handle_campaign_email_sent_signal(sender, campaign_member, campaign, **kwargs):
    """
    Handle campaign email sent event
    """
    try:
        logger.info(f"Campaign email sent: {campaign.name} - Member: {campaign_member.id}")
        
        # Update campaign email metrics
        from django.db.models import F
        Campaign.objects.filter(id=campaign.id).update(
            emails_sent=F('emails_sent') + 1
        )
        
        # Create activity for email sent
        Activity.objects.create(
            tenant=campaign.tenant,
            subject=f"Campaign email sent: {campaign.name}",
            description=f"Email sent to campaign member",
            activity_type='email',
            entity_type='campaign',
            entity_id=campaign.id,
            assigned_to=campaign.created_by,
            created_by=campaign.created_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Trigger workflows
        process_workflow_triggers_task.delay(
            tenant_id=campaign.tenant.id,
            trigger_type='campaign_email_sent',
            entity_data={
                'entity_type': 'campaign_email',
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'member_id': campaign_member.id,
                'email_sent_at': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling campaign email sent signal: {e}")


@receiver(campaign_email_opened)
def handle_campaign_email_opened_signal(sender, campaign_member, campaign, opened_at=None, **kwargs):
    """
    Handle campaign email opened event
    """
    try:
        logger.info(f"Campaign email opened: {campaign.name} - Member: {campaign_member.id}")
        
        # Update campaign email metrics
        from django.db.models import F
        Campaign.objects.filter(id=campaign.id).update(
            emails_opened=F('emails_opened') + 1
        )
        
        # Update member status
        campaign_member.email_opened = True
        campaign_member.email_opened_at = opened_at or timezone.now()
        campaign_member.save(update_fields=['email_opened', 'email_opened_at'])
        
        # Create activity for email opened
        Activity.objects.create(
            tenant=campaign.tenant,
            subject=f"Campaign email opened: {campaign.name}",
            description=f"Campaign member opened email",
            activity_type='email_engagement',
            entity_type='campaign',
            entity_id=campaign.id,
            assigned_to=campaign.created_by,
            created_by=campaign.created_by,
            status='completed',
            completed_at=timezone.now()
        )
        
        # Create follow-up activity if member shows engagement
        if campaign_member.email_clicked or campaign_member.form_submitted:
            Activity.objects.create(
                tenant=campaign.tenant,
                subject=f"Follow up on engaged campaign member",
                description=f"Member engaged with campaign email - follow up opportunity",
                activity_type='call',
                entity_type='campaign_member',
                entity_id=campaign_member.id,
                assigned_to=campaign.created_by,
                created_by=campaign.created_by,
                due_date=timezone.now() + timezone.timedelta(hours=24),
                status='pending',
                priority='high'
            )
        
        # Trigger workflows
        process_workflow_triggers_task.delay(
            tenant_id=campaign.tenant.id,
            trigger_type='campaign_email_opened',
            entity_data={
                'entity_type': 'campaign_email_engagement',
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'member_id': campaign_member.id,
                'engagement_type': 'email_opened',
                'engaged_at': (opened_at or timezone.now()).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling campaign email opened signal: {e}")


@receiver(campaign_email_clicked)
def handle_campaign_email_clicked_signal(sender, campaign_member, campaign, clicked_at=None, link_url=None, **kwargs):
    """
    Handle campaign email clicked event
    """
    try:
        logger.info(f"Campaign email clicked: {campaign.name} - Member: {campaign_member.id} - Link: {link_url}")
        
        # Update campaign email metrics
        from django.db.models import F
        Campaign.objects.filter(id=campaign.id).update(
            emails_clicked=F('emails_clicked') + 1
        )
        
        # Update member status
        campaign_member.email_clicked = True
        campaign_member.email_clicked_at = clicked_at or timezone.now()
        campaign_member.save(update_fields=['email_clicked', 'email_clicked_at'])
        
        # Create high-priority activity for clicked email
        Activity.objects.create(
            tenant=campaign.tenant,
            subject=f"🔥 Campaign email clicked: {campaign.name}",
            description=f"Member clicked on campaign email link: {link_url or 'Unknown'}",
            activity_type='email_engagement',
            entity_type='campaign',
            entity_id=campaign.id,
            assigned_to=campaign.created_by,
            created_by=campaign.created_by,
            status='completed',
            completed_at=timezone.now(),
            priority='high'
        )
        
        # Create immediate follow-up activity
        Activity.objects.create(
            tenant=campaign.tenant,
            subject=f"🎯 URGENT: Follow up on campaign click",
            description=f"Member clicked campaign link - immediate follow-up opportunity. Link: {link_url or 'N/A'}",
            activity_type='call',
            entity_type='campaign_member',
            entity_id=campaign_member.id,
            assigned_to=campaign.created_by,
            created_by=campaign.created_by,
            due_date=timezone.now() + timezone.timedelta(hours=2),
            status='pending',
            priority='critical'
        )
        
        # Send urgent notification
        if campaign.created_by:
            send_notification_task.delay(
                user_id=campaign.created_by.id,
                notification_type='campaign_email_clicked',
                title=f"🎯 Campaign Click Alert: {campaign.name}",
                message=f"A campaign member clicked your email! Follow up immediately while they're engaged.",
                related_object_type='campaign',
                related_object_id=campaign.id,
                tenant_id=campaign.tenant.id,
                priority='critical'
            )
        
        # Trigger workflows
        process_workflow_triggers_task.delay(
            tenant_id=campaign.tenant.id,
            trigger_type='campaign_email_clicked',
            entity_data={
                'entity_type': 'campaign_email_engagement',
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'member_id': campaign_member.id,
                'engagement_type': 'email_clicked',
                'link_url': link_url,
                'engaged_at': (clicked_at or timezone.now()).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling campaign email clicked signal: {e}")


@receiver(post_delete, sender=Campaign)
def handle_campaign_deleted(sender, instance, **kwargs):
    """
    Handle campaign deletion
    """
    try:
        logger.info(f"Campaign deleted: {instance.name} ({instance.id})")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='campaign',
            object_id=instance.id,
            changes={
                'deleted': True,
                'name': instance.name,
                'campaign_type': instance.campaign_type,
                'status': instance.status,
                'budget': float(instance.budget) if instance.budget else None
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in campaign post_delete signal: {e}")