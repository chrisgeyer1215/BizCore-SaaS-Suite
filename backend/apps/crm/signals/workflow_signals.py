"""
Workflow Signals
Handle workflow execution events and automation triggers
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction
import logging
import json

from ..models import (
    WorkflowRule, WorkflowExecution, Integration, 
    WebhookConfiguration, WebhookDelivery, AuditTrail
)
from ..tasks.workflow_tasks import execute_workflow_task
from ..tasks.notification_tasks import send_notification_task, send_system_alert_task

logger = logging.getLogger(__name__)

# Custom signals
workflow_triggered = Signal()
workflow_executed = Signal()
workflow_completed = Signal()
workflow_failed = Signal()
integration_synced = Signal()
webhook_delivered = Signal()
webhook_failed = Signal()


@receiver(post_save, sender=WorkflowRule)
def handle_workflow_rule_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle workflow rule creation and updates
    """
    try:
        if created:
            # Workflow rule created
            logger.info(f"Workflow rule created: {instance.name} ({instance.id}) - Trigger: {instance.trigger_type}")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='workflow_rule',
                object_id=instance.id,
                changes={
                    'created': True,
                    'name': instance.name,
                    'trigger_type': instance.trigger_type,
                    'trigger_entity': instance.trigger_entity,
                    'is_active': instance.is_active,
                    'conditions': instance.conditions,
                    'actions': instance.actions
                },
                timestamp=timezone.now()
            )
            
            # Send notification to creator
            if instance.created_by:
                send_notification_task.delay(
                    user_id=instance.created_by.id,
                    notification_type='workflow_created',
                    title=f"Workflow Created: {instance.name}",
                    message=f"Your {instance.trigger_type} workflow has been created and is {'active' if instance.is_active else 'inactive'}.",
                    related_object_type='workflow_rule',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='low'
                )
            
            # Validate workflow configuration
            validation_issues = validate_workflow_configuration(instance)
            if validation_issues:
                logger.warning(f"Workflow {instance.name} has configuration issues: {validation_issues}")
                
                # Send warning notification
                if instance.created_by:
                    send_notification_task.delay(
                        user_id=instance.created_by.id,
                        notification_type='workflow_validation_warning',
                        title=f"Workflow Configuration Issues: {instance.name}",
                        message=f"Your workflow has configuration issues: {', '.join(validation_issues)}",
                        related_object_type='workflow_rule',
                        related_object_id=instance.id,
                        tenant_id=instance.tenant.id,
                        priority='medium'
                    )
            
        else:
            # Workflow rule updated
            logger.info(f"Workflow rule updated: {instance.name} ({instance.id})")
            
            # Create audit trail for updates
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.modified_by,
                action='update',
                object_type='workflow_rule',
                object_id=instance.id,
                changes={
                    'updated': True,
                    'name': instance.name,
                    'is_active': instance.is_active,
                    'modified_by': instance.modified_by.get_full_name() if instance.modified_by else None
                },
                timestamp=timezone.now()
            )
            
    except Exception as e:
        logger.error(f"Error in workflow rule post_save signal: {e}")


@receiver(pre_save, sender=WorkflowRule)
def handle_workflow_rule_changes(sender, instance, **kwargs):
    """
    Handle workflow rule changes before saving
    """
    try:
        if instance.pk:  # Only for existing workflow rules
            try:
                old_workflow = WorkflowRule.objects.get(pk=instance.pk)
                
                # Check if workflow was activated
                if not old_workflow.is_active and instance.is_active:
                    logger.info(f"Workflow activated: {instance.name} ({instance.id})")
                    
                    # Set activation timestamp
                    instance.activated_at = timezone.now()
                    
                    # Send activation notification
                    transaction.on_commit(lambda: send_notification_task.delay(
                        user_id=instance.modified_by.id if instance.modified_by else instance.created_by.id,
                        notification_type='workflow_activated',
                        title=f"Workflow Activated: {instance.name}",
                        message=f"Your workflow is now active and will trigger on {instance.trigger_type} events.",
                        related_object_type='workflow_rule',
                        related_object_id=instance.id,
                        tenant_id=instance.tenant.id,
                        priority='medium'
                    ))
                
                # Check if workflow was deactivated
                elif old_workflow.is_active and not instance.is_active:
                    logger.info(f"Workflow deactivated: {instance.name} ({instance.id})")
                    
                    # Set deactivation timestamp
                    instance.deactivated_at = timezone.now()
                    
                    # Send deactivation notification
                    transaction.on_commit(lambda: send_notification_task.delay(
                        user_id=instance.modified_by.id if instance.modified_by else instance.created_by.id,
                        notification_type='workflow_deactivated',
                        title=f"Workflow Deactivated: {instance.name}",
                        message=f"Your workflow has been deactivated and will no longer trigger automatically.",
                        related_object_type='workflow_rule',
                        related_object_id=instance.id,
                        tenant_id=instance.tenant.id,
                        priority='low'
                    ))
                    
            except WorkflowRule.DoesNotExist:
                pass  # New workflow rule
                
    except Exception as e:
        logger.error(f"Error in workflow rule pre_save signal: {e}")


@receiver(post_save, sender=WorkflowExecution)
def handle_workflow_execution_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle workflow execution creation and updates
    """
    try:
        if created and instance.status == 'running':
            # Workflow execution started
            logger.info(f"Workflow execution started: {instance.workflow.name} ({instance.id})")
            
            # Send signal for workflow triggered
            workflow_triggered.send(
                sender=sender,
                workflow_execution=instance,
                workflow=instance.workflow
            )
            
        elif not created and instance.status == 'completed':
            # Workflow execution completed successfully
            logger.info(f"Workflow execution completed: {instance.workflow.name} ({instance.id}) - Actions: {instance.actions_executed}")
            
            # Send signal for workflow completed
            workflow_completed.send(
                sender=sender,
                workflow_execution=instance,
                workflow=instance.workflow,
                actions_executed=instance.actions_executed
            )
            
        elif not created and instance.status == 'failed':
            # Workflow execution failed
            logger.error(f"Workflow execution failed: {instance.workflow.name} ({instance.id}) - Error: {instance.error_message}")
            
            # Send signal for workflow failed
            workflow_failed.send(
                sender=sender,
                workflow_execution=instance,
                workflow=instance.workflow,
                error_message=instance.error_message
            )
            
    except Exception as e:
        logger.error(f"Error in workflow execution post_save signal: {e}")


@receiver(workflow_triggered)
def handle_workflow_triggered_signal(sender, workflow_execution, workflow, **kwargs):
    """
    Handle workflow triggered signal
    """
    try:
        # Update workflow statistics
        workflow.trigger_count = (workflow.trigger_count or 0) + 1
        workflow.last_triggered_at = timezone.now()
        workflow.save(update_fields=['trigger_count', 'last_triggered_at'])
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=workflow.tenant,
            user=None,  # System triggered
            action='workflow_triggered',
            object_type='workflow_rule',
            object_id=workflow.id,
            changes={
                'triggered': True,
                'execution_id': workflow_execution.id,
                'trigger_data': workflow_execution.trigger_data,
                'entity_type': workflow_execution.entity_type,
                'entity_id': workflow_execution.entity_id
            },
            timestamp=timezone.now()
        )
        
        # Log workflow trigger for analytics
        logger.info(f"Workflow triggered: {workflow.name} - Execution ID: {workflow_execution.id}")
        
    except Exception as e:
        logger.error(f"Error handling workflow triggered signal: {e}")


@receiver(workflow_completed)
def handle_workflow_completed_signal(sender, workflow_execution, workflow, actions_executed, **kwargs):
    """
    Handle workflow completion signal
    """
    try:
        # Update workflow statistics
        workflow.successful_executions = (workflow.successful_executions or 0) + 1
        workflow.last_successful_execution_at = timezone.now()
        
        # Calculate success rate
        total_executions = workflow.total_executions or 0
        if total_executions > 0:
            workflow.success_rate = (workflow.successful_executions / total_executions) * 100
        
        workflow.save(update_fields=[
            'successful_executions', 'last_successful_execution_at', 'success_rate'
        ])
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=workflow.tenant,
            user=None,  # System action
            action='workflow_completed',
            object_type='workflow_rule',
            object_id=workflow.id,
            changes={
                'completed': True,
                'execution_id': workflow_execution.id,
                'actions_executed': actions_executed,
                'execution_time': workflow_execution.execution_time,
                'result': workflow_execution.result
            },
            timestamp=timezone.now()
        )
        
        # Send success notification for important workflows
        if workflow.notify_on_success and workflow.created_by:
            send_notification_task.delay(
                user_id=workflow.created_by.id,
                notification_type='workflow_success',
                title=f"✅ Workflow Completed: {workflow.name}",
                message=f"Your workflow executed successfully with {actions_executed} actions.",
                related_object_type='workflow_rule',
                related_object_id=workflow.id,
                tenant_id=workflow.tenant.id,
                priority='low'
            )
        
        logger.info(f"Workflow completed successfully: {workflow.name} - {actions_executed} actions executed")
        
    except Exception as e:
        logger.error(f"Error handling workflow completion signal: {e}")


@receiver(workflow_failed)
def handle_workflow_failed_signal(sender, workflow_execution, workflow, error_message, **kwargs):
    """
    Handle workflow failure signal
    """
    try:
        # Update workflow statistics
        workflow.failed_executions = (workflow.failed_executions or 0) + 1
        workflow.last_failed_execution_at = timezone.now()
        workflow.last_error_message = error_message
        
        # Calculate failure rate
        total_executions = workflow.total_executions or 0
        if total_executions > 0:
            failure_rate = (workflow.failed_executions / total_executions) * 100
            workflow.failure_rate = failure_rate
            
            # Auto-disable workflow if failure rate is too high
            if failure_rate > 80 and total_executions > 5:
                workflow.is_active = False
                workflow.auto_disabled = True
                workflow.auto_disabled_reason = f"High failure rate: {failure_rate:.1f}%"
                workflow.auto_disabled_at = timezone.now()
                
                logger.warning(f"Auto-disabled workflow due to high failure rate: {workflow.name}")
        
        workflow.save(update_fields=[
            'failed_executions', 'last_failed_execution_at', 'last_error_message',
            'failure_rate', 'is_active', 'auto_disabled', 'auto_disabled_reason', 'auto_disabled_at'
        ])
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=workflow.tenant,
            user=None,  # System action
            action='workflow_failed',
            object_type='workflow_rule',
            object_id=workflow.id,
            changes={
                'failed': True,
                'execution_id': workflow_execution.id,
                'error_message': error_message,
                'execution_time': workflow_execution.execution_time,
                'auto_disabled': workflow.auto_disabled
            },
            timestamp=timezone.now()
        )
        
        # Send failure notification
        if workflow.created_by:
            send_notification_task.delay(
                user_id=workflow.created_by.id,
                notification_type='workflow_failed',
                title=f"❌ Workflow Failed: {workflow.name}",
                message=f"Your workflow failed to execute: {error_message}",
                related_object_type='workflow_rule',
                related_object_id=workflow.id,
                tenant_id=workflow.tenant.id,
                priority='high'
            )
        
        # Send system alert for critical failures
        if workflow.priority == 'critical' or workflow.auto_disabled:
            send_system_alert_task.delay(
                alert_type='workflow_failure',
                message=f"Critical workflow failure: {workflow.name} - {error_message}",
                severity='error',
                source=f"workflow_{workflow.id}",
                tenant_id=workflow.tenant.id
            )
        
        logger.error(f"Workflow failed: {workflow.name} - {error_message}")
        
    except Exception as e:
        logger.error(f"Error handling workflow failure signal: {e}")


@receiver(post_save, sender=Integration)
def handle_integration_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle integration creation and updates
    """
    try:
        if created:
            # Integration created
            logger.info(f"Integration created: {instance.name} ({instance.id}) - Provider: {instance.provider}")
            
            # Create audit trail
            AuditTrail.objects.create(
                tenant=instance.tenant,
                user=instance.created_by,
                action='create',
                object_type='integration',
                object_id=instance.id,
                changes={
                    'created': True,
                    'name': instance.name,
                    'provider': instance.provider,
                    'is_active': instance.is_active,
                    'sync_enabled': instance.sync_enabled
                },
                timestamp=timezone.now()
            )
            
            # Send notification
            if instance.created_by:
                send_notification_task.delay(
                    user_id=instance.created_by.id,
                    notification_type='integration_created',
                    title=f"Integration Created: {instance.name}",
                    message=f"Your {instance.provider} integration has been set up successfully.",
                    related_object_type='integration',
                    related_object_id=instance.id,
                    tenant_id=instance.tenant.id,
                    priority='medium'
                )
                
        # Handle sync completion
        elif (hasattr(instance, '_sync_completed') and instance._sync_completed and 
              instance.last_sync_completed_at):
            
            integration_synced.send(
                sender=sender,
                integration=instance,
                sync_result=instance.last_sync_result
            )
            
    except Exception as e:
        logger.error(f"Error in integration post_save signal: {e}")


@receiver(integration_synced)
def handle_integration_synced_signal(sender, integration, sync_result, **kwargs):
    """
    Handle integration sync completion
    """
    try:
        logger.info(f"Integration synced: {integration.name} - Records: {integration.records_synced}")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=integration.tenant,
            user=None,  # System sync
            action='integration_synced',
            object_type='integration',
            object_id=integration.id,
            changes={
                'synced': True,
                'records_synced': integration.records_synced,
                'sync_status': integration.sync_status,
                'sync_result': sync_result
            },
            timestamp=timezone.now()
        )
        
        # Send notification for successful sync
        if integration.sync_status == 'completed' and integration.created_by:
            send_notification_task.delay(
                user_id=integration.created_by.id,
                notification_type='integration_sync_success',
                title=f"✅ Sync Completed: {integration.name}",
                message=f"Successfully synced {integration.records_synced} records with {integration.provider}.",
                related_object_type='integration',
                related_object_id=integration.id,
                tenant_id=integration.tenant.id,
                priority='low'
            )
        
        # Send notification for failed sync
        elif integration.sync_status == 'failed' and integration.created_by:
            send_notification_task.delay(
                user_id=integration.created_by.id,
                notification_type='integration_sync_failed',
                title=f"❌ Sync Failed: {integration.name}",
                message=f"Integration sync failed: {integration.last_sync_error}",
                related_object_type='integration',
                related_object_id=integration.id,
                tenant_id=integration.tenant.id,
                priority='high'
            )
        
    except Exception as e:
        logger.error(f"Error handling integration sync signal: {e}")


@receiver(post_save, sender=WebhookDelivery)
def handle_webhook_delivery_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle webhook delivery attempts
    """
    try:
        if created:
            # New webhook delivery attempt
            if instance.success:
                webhook_delivered.send(
                    sender=sender,
                    webhook_delivery=instance,
                    webhook=instance.webhook
                )
            else:
                webhook_failed.send(
                    sender=sender,
                    webhook_delivery=instance,
                    webhook=instance.webhook,
                    error_message=instance.last_error
                )
                
    except Exception as e:
        logger.error(f"Error in webhook delivery post_save signal: {e}")


@receiver(webhook_delivered)
def handle_webhook_delivered_signal(sender, webhook_delivery, webhook, **kwargs):
    """
    Handle successful webhook delivery
    """
    try:
        logger.info(f"Webhook delivered successfully: {webhook.name} - Response: {webhook_delivery.response_status}")
        
        # Update webhook success statistics
        webhook.successful_deliveries = (webhook.successful_deliveries or 0) + 1
        webhook.last_successful_delivery_at = timezone.now()
        webhook.save(update_fields=['successful_deliveries', 'last_successful_delivery_at'])
        
        # Log successful delivery for debugging
        if webhook.log_deliveries:
            logger.debug(f"Webhook delivery details: {webhook.name} -> {webhook.url} - Payload: {webhook_delivery.payload}")
        
    except Exception as e:
        logger.error(f"Error handling webhook delivery signal: {e}")


@receiver(webhook_failed)
def handle_webhook_failed_signal(sender, webhook_delivery, webhook, error_message, **kwargs):
    """
    Handle failed webhook delivery
    """
    try:
        logger.error(f"Webhook delivery failed: {webhook.name} - Error: {error_message}")
        
        # Update webhook failure statistics
        webhook.failed_deliveries = (webhook.failed_deliveries or 0) + 1
        webhook.last_failed_delivery_at = timezone.now()
        webhook.last_error = error_message
        
        # Calculate failure rate
        total_deliveries = (webhook.successful_deliveries or 0) + (webhook.failed_deliveries or 0)
        if total_deliveries > 0:
            failure_rate = (webhook.failed_deliveries / total_deliveries) * 100
            webhook.failure_rate = failure_rate
            
            # Disable webhook if failure rate is too high
            if failure_rate > 90 and total_deliveries > 10:
                webhook.is_active = False
                webhook.auto_disabled = True
                webhook.auto_disabled_reason = f"High failure rate: {failure_rate:.1f}%"
                webhook.auto_disabled_at = timezone.now()
                
                logger.warning(f"Auto-disabled webhook due to high failure rate: {webhook.name}")
                
                # Send notification about auto-disable
                if webhook.created_by:
                    send_notification_task.delay(
                        user_id=webhook.created_by.id,
                        notification_type='webhook_auto_disabled',
                        title=f"⚠️ Webhook Auto-Disabled: {webhook.name}",
                        message=f"Webhook was disabled due to high failure rate ({failure_rate:.1f}%). Please check the endpoint.",
                        related_object_type='webhook',
                        related_object_id=webhook.id,
                        tenant_id=webhook.tenant.id,
                        priority='high'
                    )
        
        webhook.save(update_fields=[
            'failed_deliveries', 'last_failed_delivery_at', 'last_error', 
            'failure_rate', 'is_active', 'auto_disabled', 'auto_disabled_reason', 'auto_disabled_at'
        ])
        
        # Send system alert for critical webhook failures
        if webhook.is_critical or (webhook_delivery.attempts >= 3):
            send_system_alert_task.delay(
                alert_type='webhook_failure',
                message=f"Critical webhook failure: {webhook.name} - {error_message}",
                severity='warning',
                source=f"webhook_{webhook.id}",
                tenant_id=webhook.tenant.id
            )
        
    except Exception as e:
        logger.error(f"Error handling webhook failure signal: {e}")


def validate_workflow_configuration(workflow):
    """
    Validate workflow configuration and return list of issues
    """
    issues = []
    
    try:
        # Check if conditions are valid JSON
        if workflow.conditions:
            try:
                json.loads(workflow.conditions)
            except json.JSONDecodeError:
                issues.append("Invalid conditions JSON format")
        
        # Check if actions are valid JSON
        if workflow.actions:
            try:
                actions = json.loads(workflow.actions)
                if not isinstance(actions, list):
                    issues.append("Actions must be a JSON array")
                elif not actions:
                    issues.append("At least one action is required")
            except json.JSONDecodeError:
                issues.append("Invalid actions JSON format")
        else:
            issues.append("No actions defined")
        
        # Check trigger configuration
        if workflow.trigger_type == 'scheduled' and not workflow.schedule_frequency:
            issues.append("Schedule frequency required for scheduled workflows")
        
        # Check entity type for entity-based triggers
        entity_triggers = ['created', 'updated', 'deleted', 'status_changed']
        if workflow.trigger_type in entity_triggers and not workflow.trigger_entity:
            issues.append(f"Entity type required for {workflow.trigger_type} trigger")
        
    except Exception as e:
        issues.append(f"Validation error: {str(e)}")
    
    return issues


@receiver(post_delete, sender=WorkflowRule)
def handle_workflow_rule_deleted(sender, instance, **kwargs):
    """
    Handle workflow rule deletion
    """
    try:
        logger.info(f"Workflow rule deleted: {instance.name} ({instance.id})")
        
        # Create audit trail
        AuditTrail.objects.create(
            tenant=instance.tenant,
            user=getattr(instance, '_deleted_by', None),
            action='delete',
            object_type='workflow_rule',
            object_id=instance.id,
            changes={
                'deleted': True,
                'name': instance.name,
                'trigger_type': instance.trigger_type,
                'was_active': instance.is_active
            },
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error in workflow rule post_delete signal: {e}")