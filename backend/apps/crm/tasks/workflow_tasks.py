"""
Workflow Tasks
Handle workflow execution, automation triggers, and business process management
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
import logging
import json
from datetime import timedelta
from typing import Dict, Any, List

from .base import TenantAwareTask, RetryableTask, MonitoredTask, ScheduledTask
from ..models import (
    WorkflowRule, WorkflowExecution, WorkflowAction, WorkflowCondition,
    Lead, Opportunity, Account, Contact, Activity, Ticket,
    Integration, WebhookConfiguration
)
from ..services.workflow_service import WorkflowService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=RetryableTask, bind=True)
def execute_workflow_task(self, tenant_id, workflow_id, trigger_data, entity_type=None, entity_id=None):
    """
    Execute a specific workflow with trigger data
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        workflow = WorkflowRule.objects.get(id=workflow_id, tenant=tenant)
        service = WorkflowService(tenant=tenant)
        
        # Create workflow execution record
        execution = WorkflowExecution.objects.create(
            tenant=tenant,
            workflow=workflow,
            trigger_data=trigger_data,
            entity_type=entity_type,
            entity_id=entity_id,
            status='running',
            started_at=timezone.now()
        )
        
        try:
            # Check if workflow conditions are met
            conditions_met = service.evaluate_workflow_conditions(
                workflow=workflow,
                trigger_data=trigger_data,
                entity_type=entity_type,
                entity_id=entity_id
            )
            
            if not conditions_met:
                execution.status = 'skipped'
                execution.completed_at = timezone.now()
                execution.result = {'reason': 'Conditions not met'}
                execution.save()
                
                logger.info(f"Workflow {workflow.name} skipped - conditions not met")
                return {'status': 'skipped', 'execution_id': execution.id}
            
            # Execute workflow actions
            execution_result = service.execute_workflow_actions(
                workflow=workflow,
                trigger_data=trigger_data,
                entity_type=entity_type,
                entity_id=entity_id,
                execution=execution
            )
            
            # Update execution record
            execution.status = 'completed' if execution_result['success'] else 'failed'
            execution.completed_at = timezone.now()
            execution.result = execution_result
            execution.actions_executed = execution_result.get('actions_executed', 0)
            execution.error_message = execution_result.get('error_message')
            execution.save()
            
            # Update workflow statistics
            workflow.total_executions = (workflow.total_executions or 0) + 1
            if execution_result['success']:
                workflow.successful_executions = (workflow.successful_executions or 0) + 1
            else:
                workflow.failed_executions = (workflow.failed_executions or 0) + 1
            
            workflow.last_executed_at = timezone.now()
            workflow.save(update_fields=[
                'total_executions', 'successful_executions', 'failed_executions', 'last_executed_at'
            ])
            
            logger.info(f"Workflow {workflow.name} executed: {execution_result['actions_executed']} actions")
            
            return {
                'status': execution.status,
                'execution_id': execution.id,
                'actions_executed': execution_result.get('actions_executed', 0),
                'result': execution_result
            }
            
        except Exception as e:
            # Update execution with error
            execution.status = 'failed'
            execution.completed_at = timezone.now()
            execution.error_message = str(e)
            execution.save()
            
            # Update workflow failure count
            workflow.failed_executions = (workflow.failed_executions or 0) + 1
            workflow.save(update_fields=['failed_executions'])
            
            raise
            
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_workflow_triggers_task(self, tenant_id, trigger_type, entity_data):
    """
    Process workflow triggers for entity changes
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = WorkflowService(tenant=tenant)
        
        # Find workflows that match this trigger
        workflows = WorkflowRule.objects.filter(
            tenant=tenant,
            is_active=True,
            trigger_type=trigger_type,
            trigger_entity=entity_data.get('entity_type')
        )
        
        triggered_workflows = 0
        
        for workflow in workflows:
            try:
                # Check if workflow should be triggered
                should_trigger = service.should_trigger_workflow(
                    workflow=workflow,
                    entity_data=entity_data,
                    trigger_type=trigger_type
                )
                
                if should_trigger:
                    # Execute workflow asynchronously
                    execute_workflow_task.delay(
                        tenant_id=tenant.id,
                        workflow_id=workflow.id,
                        trigger_data=entity_data,
                        entity_type=entity_data.get('entity_type'),
                        entity_id=entity_data.get('entity_id')
                    )
                    
                    triggered_workflows += 1
                    
            except Exception as e:
                logger.error(f"Failed to process trigger for workflow {workflow.id}: {e}")
        
        logger.info(f"Triggered {triggered_workflows} workflows for {trigger_type}")
        
        return {
            'status': 'completed',
            'triggered_workflows': triggered_workflows,
            'trigger_type': trigger_type
        }
        
    except Exception as e:
        logger.error(f"Workflow trigger processing failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def process_scheduled_workflows_task(self, tenant_id=None):
    """
    Process scheduled workflows (time-based triggers)
    """
    try:
        # Find scheduled workflows that should run
        now = timezone.now()
        
        workflows_query = WorkflowRule.objects.filter(
            is_active=True,
            trigger_type='scheduled'
        ).filter(
            Q(next_run_at__lte=now) | Q(next_run_at__isnull=True)
        )
        
        if tenant_id:
            tenant = get_tenant_by_id(tenant_id)
            workflows_query = workflows_query.filter(tenant=tenant)
        
        executed_workflows = 0
        
        for workflow in workflows_query:
            try:
                service = WorkflowService(tenant=workflow.tenant)
                
                # Check if it's time to run this workflow
                if service.is_workflow_due(workflow):
                    # Execute workflow
                    execute_workflow_task.delay(
                        tenant_id=workflow.tenant.id,
                        workflow_id=workflow.id,
                        trigger_data={'trigger_type': 'scheduled', 'executed_at': now.isoformat()}
                    )
                    
                    # Update next run time
                    next_run = service.calculate_next_run_time(workflow)
                    workflow.next_run_at = next_run
                    workflow.save(update_fields=['next_run_at'])
                    
                    executed_workflows += 1
                    
            except Exception as e:
                logger.error(f"Failed to execute scheduled workflow {workflow.id}: {e}")
        
        logger.info(f"Executed {executed_workflows} scheduled workflows")
        
        return {
            'status': 'completed',
            'executed_workflows': executed_workflows
        }
        
    except Exception as e:
        logger.error(f"Scheduled workflow processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def sync_integration_data_task(self, tenant_id, integration_id, sync_type='full'):
    """
    Synchronize data with external integrations
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        integration = Integration.objects.get(id=integration_id, tenant=tenant)
        service = WorkflowService(tenant=tenant)
        
        # Update integration status
        integration.last_sync_started_at = timezone.now()
        integration.sync_status = 'syncing'
        integration.save(update_fields=['last_sync_started_at', 'sync_status'])
        
        try:
            # Perform synchronization
            sync_result = service.sync_integration_data(
                integration=integration,
                sync_type=sync_type
            )
            
            # Update integration with results
            integration.sync_status = 'completed'
            integration.last_sync_completed_at = timezone.now()
            integration.last_sync_result = sync_result
            integration.records_synced = sync_result.get('records_synced', 0)
            integration.sync_errors = sync_result.get('errors', [])
            integration.save()
            
            logger.info(f"Integration sync completed: {sync_result.get('records_synced', 0)} records")
            
            return {
                'status': 'completed',
                'integration_name': integration.name,
                'sync_result': sync_result
            }
            
        except Exception as e:
            # Update integration with error
            integration.sync_status = 'failed'
            integration.last_sync_completed_at = timezone.now()
            integration.last_sync_error = str(e)
            integration.save()
            raise
            
    except Exception as e:
        logger.error(f"Integration sync failed: {e}")
        raise


@shared_task(base=RetryableTask, bind=True)
def execute_webhook_task(self, tenant_id, webhook_id, payload_data, event_type):
    """
    Execute webhook delivery
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        webhook = WebhookConfiguration.objects.get(id=webhook_id, tenant=tenant)
        service = WorkflowService(tenant=tenant)
        
        # Execute webhook
        delivery_result = service.execute_webhook(
            webhook=webhook,
            payload=payload_data,
            event_type=event_type
        )
        
        # Log webhook delivery
        from ..models import WebhookDelivery
        WebhookDelivery.objects.create(
            tenant=tenant,
            webhook=webhook,
            event_type=event_type,
            payload=payload_data,
            response_status=delivery_result.get('status_code'),
            response_body=delivery_result.get('response_body'),
            delivery_time=delivery_result.get('delivery_time'),
            success=delivery_result.get('success', False),
            delivered_at=timezone.now()
        )
        
        logger.info(f"Webhook delivered: {webhook.name} - Status: {delivery_result.get('status_code')}")
        
        return {
            'status': 'delivered' if delivery_result.get('success') else 'failed',
            'webhook_name': webhook.name,
            'response_status': delivery_result.get('status_code'),
            'delivery_time': delivery_result.get('delivery_time')
        }
        
    except Exception as e:
        logger.error(f"Webhook execution failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def optimize_workflows_task(self, tenant_id, optimization_rules=None):
    """
    Optimize workflow performance and suggest improvements
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = WorkflowService(tenant=tenant)
        
        # Default optimization rules
        default_rules = {
            'disable_failing_workflows': True,
            'failure_threshold': 80,  # 80% failure rate
            'min_executions': 10,
            'optimize_conditions': True,
            'consolidate_similar': True,
            'update_trigger_frequency': True
        }
        
        rules = optimization_rules or default_rules
        
        # Get workflow performance data
        workflows = WorkflowRule.objects.filter(tenant=tenant, is_active=True)
        optimization_results = []
        
        for workflow in workflows:
            try:
                # Analyze workflow performance
                performance = service.analyze_workflow_performance(workflow)
                
                optimizations = []
                
                # Check failure rate
                if (rules.get('disable_failing_workflows', False) and
                    performance.get('total_executions', 0) >= rules.get('min_executions', 10) and
                    performance.get('failure_rate', 0) >= rules.get('failure_threshold', 80)):
                    
                    workflow.is_active = False
                    workflow.disabled_reason = f"High failure rate: {performance.get('failure_rate', 0):.1f}%"
                    workflow.save(update_fields=['is_active', 'disabled_reason'])
                    optimizations.append('disabled_high_failure_rate')
                
                # Optimize conditions
                if rules.get('optimize_conditions', False):
                    condition_optimizations = service.optimize_workflow_conditions(workflow)
                    if condition_optimizations:
                        optimizations.extend(condition_optimizations)
                
                # Update trigger frequency for scheduled workflows
                if (rules.get('update_trigger_frequency', False) and 
                    workflow.trigger_type == 'scheduled'):
                    
                    optimal_frequency = service.calculate_optimal_frequency(workflow)
                    if optimal_frequency != workflow.schedule_frequency:
                        workflow.schedule_frequency = optimal_frequency
                        workflow.save(update_fields=['schedule_frequency'])
                        optimizations.append(f'updated_frequency_to_{optimal_frequency}')
                
                if optimizations:
                    optimization_results.append({
                        'workflow_id': workflow.id,
                        'workflow_name': workflow.name,
                        'performance': performance,
                        'optimizations': optimizations
                    })
                    
            except Exception as e:
                logger.error(f"Failed to optimize workflow {workflow.id}: {e}")
        
        # Find and consolidate similar workflows
        if rules.get('consolidate_similar', False):
            consolidation_results = service.find_consolidation_opportunities(tenant)
            optimization_results.extend(consolidation_results)
        
        logger.info(f"Optimized {len(optimization_results)} workflows")
        
        return {
            'status': 'completed',
            'optimized_workflows': len(optimization_results),
            'optimization_results': optimization_results
        }
        
    except Exception as e:
        logger.error(f"Workflow optimization failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def create_workflow_from_pattern_task(self, tenant_id, pattern_data, template_type='lead_nurturing'):
    """
    Create new workflows based on detected patterns or templates
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = WorkflowService(tenant=tenant)
        
        # Generate workflow from pattern or template
        workflow_config = service.generate_workflow_from_pattern(
            pattern_data=pattern_data,
            template_type=template_type
        )
        
        # Create workflow
        workflow = service.create_workflow_from_config(
            config=workflow_config,
            tenant=tenant
        )
        
        logger.info(f"Created workflow from pattern: {workflow.name}")
        
        return {
            'status': 'created',
            'workflow_id': workflow.id,
            'workflow_name': workflow.name,
            'template_type': template_type
        }
        
    except Exception as e:
        logger.error(f"Pattern-based workflow creation failed: {e}")
        raise


@shared_task(base=MonitoredTask, bind=True)
def bulk_workflow_execution_task(self, tenant_id, workflow_id, entity_ids, entity_type):
    """
    Execute workflow for multiple entities in bulk
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        workflow = WorkflowRule.objects.get(id=workflow_id, tenant=tenant)
        service = WorkflowService(tenant=tenant)
        
        execution_results = []
        successful_executions = 0
        failed_executions = 0
        
        for entity_id in entity_ids:
            try:
                # Get entity data
                entity_data = service.get_entity_data(entity_type, entity_id, tenant)
                
                # Execute workflow for this entity
                result = service.execute_workflow_sync(
                    workflow=workflow,
                    trigger_data=entity_data,
                    entity_type=entity_type,
                    entity_id=entity_id
                )
                
                if result.get('success'):
                    successful_executions += 1
                else:
                    failed_executions += 1
                
                execution_results.append({
                    'entity_id': entity_id,
                    'status': 'success' if result.get('success') else 'failed',
                    'actions_executed': result.get('actions_executed', 0),
                    'error': result.get('error_message')
                })
                
            except Exception as e:
                failed_executions += 1
                execution_results.append({
                    'entity_id': entity_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"Bulk workflow execution: {successful_executions} success, {failed_executions} failed")
        
        return {
            'status': 'completed',
            'workflow_name': workflow.name,
            'total_entities': len(entity_ids),
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'execution_results': execution_results
        }
        
    except Exception as e:
        logger.error(f"Bulk workflow execution failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_workflow_executions_task(self, tenant_id=None, days_to_keep=90):
    """
    Clean up old workflow execution records
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        query = WorkflowExecution.objects.filter(
            completed_at__lt=cutoff_date
        )
        
        if tenant_id:
            tenant = get_tenant_by_id(tenant_id)
            query = query.filter(tenant=tenant)
        
        # Archive execution statistics before deletion
        execution_stats = query.aggregate(
            total_executions=Count('id'),
            successful_executions=Count('id', filter=Q(status='completed')),
            failed_executions=Count('id', filter=Q(status='failed'))
        )
        
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} workflow execution records")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'execution_statistics': execution_stats
        }
        
    except Exception as e:
        logger.error(f"Workflow execution cleanup failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def validate_workflow_integrity_task(self, tenant_id):
    """
    Validate workflow integrity and fix common issues
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = WorkflowService(tenant=tenant)
        
        workflows = WorkflowRule.objects.filter(tenant=tenant, is_active=True)
        validation_results = []
        
        for workflow in workflows:
            try:
                # Validate workflow configuration
                validation_result = service.validate_workflow_configuration(workflow)
                
                if not validation_result['is_valid']:
                    # Try to fix issues automatically
                    fix_result = service.fix_workflow_issues(
                        workflow=workflow,
                        issues=validation_result['issues']
                    )
                    
                    validation_results.append({
                        'workflow_id': workflow.id,
                        'workflow_name': workflow.name,
                        'issues_found': validation_result['issues'],
                        'fixes_applied': fix_result.get('fixes_applied', []),
                        'status': 'fixed' if fix_result.get('success') else 'needs_attention'
                    })
                
            except Exception as e:
                validation_results.append({
                    'workflow_id': workflow.id,
                    'workflow_name': workflow.name,
                    'error': str(e),
                    'status': 'error'
                })
        
        return {
            'status': 'completed',
            'workflows_validated': workflows.count(),
            'issues_found': len(validation_results),
            'validation_results': validation_results
        }
        
    except Exception as e:
        logger.error(f"Workflow validation failed: {e}")
        raise