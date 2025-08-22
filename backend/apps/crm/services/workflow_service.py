# ============================================================================
# backend/apps/crm/services/workflow_service.py - Advanced Workflow Automation Service
# ============================================================================

import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.template import Template, Context
from django.core.mail import send_mail
import logging

from .base import BaseService, ServiceException
from ..models import (
    WorkflowRule, WorkflowExecution, WorkflowAction, WorkflowCondition,
    WorkflowTrigger, WorkflowLog, AutomationSchedule, BusinessRule,
    Lead, Account, Opportunity, Activity, Campaign, Ticket
)

logger = logging.getLogger(__name__)


class WorkflowException(ServiceException):
    """Workflow service specific errors"""
    pass


class ConditionEvaluator:
    """Advanced condition evaluation engine"""
    
    def __init__(self):
        self.operators = {
            'equals': self._equals,
            'not_equals': self._not_equals,
            'greater_than': self._greater_than,
            'less_than': self._less_than,
            'greater_equal': self._greater_equal,
            'less_equal': self._less_equal,
            'contains': self._contains,
            'not_contains': self._not_contains,
            'starts_with': self._starts_with,
            'ends_with': self._ends_with,
            'in_list': self._in_list,
            'not_in_list': self._not_in_list,
            'is_empty': self._is_empty,
            'is_not_empty': self._is_not_empty,
            'matches_regex': self._matches_regex,
            'date_is': self._date_is,
            'date_before': self._date_before,
            'date_after': self._date_after,
            'date_range': self._date_range
        }
    
    def evaluate_conditions(self, conditions: List[Dict], obj: Any, 
                          logic_operator: str = 'AND') -> bool:
        """Evaluate multiple conditions with logic operators"""
        if not conditions:
            return True
        
        results = []
        for condition in conditions:
            result = self._evaluate_single_condition(condition, obj)
            results.append(result)
        
        if logic_operator.upper() == 'AND':
            return all(results)
        elif logic_operator.upper() == 'OR':
            return any(results)
        else:
            # Support for complex logic like "A AND (B OR C)"
            return self._evaluate_complex_logic(results, logic_operator)
    
    def _evaluate_single_condition(self, condition: Dict, obj: Any) -> bool:
        """Evaluate a single condition"""
        try:
            field_path = condition['field']
            operator = condition['operator']
            expected_value = condition['value']
            
            # Get actual value from object
            actual_value = self._get_field_value(obj, field_path)
            
            # Apply operator
            if operator in self.operators:
                return self.operators[operator](actual_value, expected_value)
            else:
                raise WorkflowException(f"Unknown operator: {operator}")
                
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False
    
    def _get_field_value(self, obj: Any, field_path: str) -> Any:
        """Get field value supporting dot notation (e.g., 'account.industry')"""
        try:
            parts = field_path.split('.')
            value = obj
            
            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            
            # Handle callable attributes
            if callable(value):
                value = value()
            
            return value
            
        except Exception:
            return None
    
    # Operator implementations
    def _equals(self, actual, expected): 
        return str(actual) == str(expected)
    
    def _not_equals(self, actual, expected): 
        return str(actual) != str(expected)
    
    def _greater_than(self, actual, expected): 
        try: return float(actual) > float(expected)
        except: return False
    
    def _contains(self, actual, expected): 
        return expected in str(actual) if actual else False
    
    def _matches_regex(self, actual, expected): 
        return bool(re.match(expected, str(actual))) if actual else False


class ActionExecutor:
    """Advanced action execution engine"""
    
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
        self.actions = {
            'send_email': self._send_email,
            'create_activity': self._create_activity,
            'update_field': self._update_field,
            'assign_owner': self._assign_owner,
            'add_tag': self._add_tag,
            'remove_tag': self._remove_tag,
            'create_opportunity': self._create_opportunity,
            'send_notification': self._send_notification,
            'webhook': self._execute_webhook,
            'run_calculation': self._run_calculation,
            'conditional_action': self._conditional_action,
            'delay_action': self._delay_action,
            'escalate': self._escalate,
            'create_ticket': self._create_ticket
        }
    
    def execute_actions(self, actions: List[Dict], obj: Any, 
                       workflow_context: Dict = None) -> List[Dict]:
        """Execute multiple actions with context"""
        results = []
        context = workflow_context or {}
        
        for action_config in actions:
            try:
                result = self._execute_single_action(action_config, obj, context)
                results.append({
                    'action': action_config['type'],
                    'success': True,
                    'result': result,
                    'executed_at': timezone.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Action execution failed: {e}", exc_info=True)
                results.append({
                    'action': action_config['type'],
                    'success': False,
                    'error': str(e),
                    'executed_at': timezone.now().isoformat()
                })
        
        return results
    
    def _execute_single_action(self, action_config: Dict, obj: Any, context: Dict) -> Any:
        """Execute a single action"""
        action_type = action_config['type']
        
        if action_type in self.actions:
            return self.actions[action_type](action_config, obj, context)
        else:
            raise WorkflowException(f"Unknown action type: {action_type}")
    
    def _send_email(self, config: Dict, obj: Any, context: Dict) -> Dict:
        """Send email action"""
        template_content = config.get('template', '')
        subject_template = config.get('subject', 'CRM Notification')
        recipients = config.get('recipients', [])
        
        # Process templates with object context
        template_context = {
            'object': obj,
            'user': self.user,
            'tenant': self.tenant,
            **context
        }
        
        # Render templates
        subject = Template(subject_template).render(Context(template_context))
        message = Template(template_content).render(Context(template_context))
        
        # Resolve recipients
        recipient_emails = self._resolve_recipients(recipients, obj)
        
        if recipient_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=None,  # Use default
                recipient_list=recipient_emails,
                fail_silently=False
            )
        
        return {
            'recipients_count': len(recipient_emails),
            'subject': subject
        }
    
    def _create_activity(self, config: Dict, obj: Any, context: Dict) -> Dict:
        """Create activity action"""
        activity_data = {
            'tenant': self.tenant,
            'subject': config.get('subject', 'Automated Activity'),
            'description': config.get('description', ''),
            'activity_type_id': config.get('activity_type_id'),
            'status': config.get('status', 'PLANNED'),
            'priority': config.get('priority', 'MEDIUM'),
            'start_datetime': timezone.now() + timedelta(hours=config.get('hours_offset', 0)),
            'created_by': self.user
        }
        
        # Link to related object
        if hasattr(obj, '_meta'):
            model_name = obj._meta.model_name
            if model_name == 'lead':
                activity_data['lead'] = obj
            elif model_name == 'account':
                activity_data['account'] = obj
            elif model_name == 'opportunity':
                activity_data['opportunity'] = obj
        
        activity = Activity.objects.create(**activity_data)
        
        return {'activity_id': activity.id}
    
    def _update_field(self, config: Dict, obj: Any, context: Dict) -> Dict:
        """Update field action"""
        field_name = config['field']
        new_value = config['value']
        
        # Process template values
        if isinstance(new_value, str) and '{{' in new_value:
            template_context = {'object': obj, 'user': self.user, **context}
            new_value = Template(new_value).render(Context(template_context))
        
        # Update the field
        setattr(obj, field_name, new_value)
        obj.save(update_fields=[field_name])
        
        return {
            'field': field_name,
            'old_value': getattr(obj, field_name, None),
            'new_value': new_value
        }


class WorkflowEngine:
    """Core workflow orchestration engine"""
    
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
        self.condition_evaluator = ConditionEvaluator()
        self.action_executor = ActionExecutor(tenant, user)
    
    def execute_workflow(self, workflow_rule: 'WorkflowRule', obj: Any, 
                        trigger_event: str = None) -> Dict:
        """Execute complete workflow"""
        try:
            execution_context = {
                'workflow_id': workflow_rule.id,
                'trigger_event': trigger_event,
                'object_type': obj._meta.model_name,
                'object_id': obj.id,
                'started_at': timezone.now(),
                'user_id': self.user.id if self.user else None
            }
            
            # Create execution record
            execution = WorkflowExecution.objects.create(
                workflow_rule=workflow_rule,
                trigger_event=trigger_event or 'manual',
                object_type=obj._meta.model_name,
                object_id=obj.id,
                status='RUNNING',
                started_at=timezone.now(),
                tenant=self.tenant,
                triggered_by=self.user,
                context=execution_context
            )
            
            try:
                # Evaluate conditions
                conditions_met = True
                if workflow_rule.conditions:
                    conditions_met = self.condition_evaluator.evaluate_conditions(
                        workflow_rule.conditions,
                        obj,
                        workflow_rule.condition_logic or 'AND'
                    )
                
                execution_results = {
                    'conditions_met': conditions_met,
                    'actions_executed': [],
                    'execution_time': None
                }
                
                if conditions_met:
                    # Execute actions
                    action_results = self.action_executor.execute_actions(
                        workflow_rule.actions,
                        obj,
                        execution_context
                    )
                    execution_results['actions_executed'] = action_results
                
                # Complete execution
                execution.status = 'COMPLETED'
                execution.completed_at = timezone.now()
                execution.results = execution_results
                execution.save()
                
                execution_results['execution_time'] = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
                
                return execution_results
                
            except Exception as e:
                # Handle execution failure
                execution.status = 'FAILED'
                execution.completed_at = timezone.now()
                execution.error_message = str(e)
                execution.save()
                raise
                
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            raise WorkflowException(f"Workflow execution failed: {str(e)}")


class WorkflowService(BaseService):
    """Comprehensive workflow automation service"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_engine = WorkflowEngine(self.tenant, self.user)
    
    # ============================================================================
    # WORKFLOW RULE MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_workflow_rule(self, rule_
        Create advanced workflow rule with conditions and actions
        
        Args: Workflow rule configuration
        
        Returns:
            WorkflowRule instance
        """
        self.context.operation = 'create_workflow_rule'
        
        try:
            self.validate_user_permission('crm.add_workflowrule')
            
            # Validate required fields
            required_fields = ['name', 'trigger_event', 'actions']
            is_valid, errors = self.validate_data(rule_data, {
                field: {'required': True} for field in required_fields
            })
            
            if not is_valid:
                raise WorkflowException(f"Validation failed: {', '.join(errors)}")
            
            # Validate actions format
            self._validate_workflow_actions(rule_data['actions'])
            
            # Create workflow rule
            workflow_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name=rule_data['name'],
                description=rule_data.get('description', ''),
                trigger_event=rule_data['trigger_event'],
                object_type=rule_data.get('object_type', 'lead'),
                conditions=rule_data.get('conditions', []),
                condition_logic=rule_data.get('condition_logic', 'AND'),
                actions=rule_data['actions'],
                is_active=rule_data.get('is_active', True),
                priority=rule_data.get('priority', 50),
                execution_limit=rule_data.get('execution_limit'),
                schedule_config=rule_data.get('schedule_config', {}),
                created_by=self.user,
                metadata={
                    'creation_source': 'manual',
                    'complexity_score': self._calculate_rule_complexity(rule_data),
                    'estimated_executions_per_day': rule_data.get('estimated_executions', 0)
                }
            )
            
            # Create individual condition and action records for better tracking
            self._create_workflow_components(workflow_rule, rule_data)
            
            # Validate workflow logic
            validation_results = self._validate_workflow_logic(workflow_rule)
            if not validation_results['is_valid']:
                workflow_rule.is_active = False
                workflow_rule.save()
                logger.warning(f"Workflow rule created but deactivated due to validation issues: {validation_results}")
            
            self.log_activity(
                'workflow_rule_created',
                'WorkflowRule',
                workflow_rule.id,
                {
                    'name': workflow_rule.name,
                    'trigger_event': workflow_rule.trigger_event,
                    'conditions_count': len(rule_data.get('conditions', [])),
                    'actions_count': len(rule_data['actions']),
                    'is_active': workflow_rule.is_active
                }
            )
            
            return workflow_rule
            
        except Exception as e:
            logger.error(f"Workflow rule creation failed: {e}", exc_info=True)
            raise WorkflowException(f"Workflow rule creation failed: {str(e)}")
    
    def trigger_workflow_by_event(self, event_type: str, obj: Any, 
                                 event List[Dict]:
        """
        Trigger workflows based on system events
        
        Args:
            event_type: Type of event that occurred
            obj: Object that triggered the event
            event_data: Additional event data
        
        Returns:
            List of workflow execution results
        """
        try:
            # Find matching workflow rules
            matching_workflows = WorkflowRule.objects.filter(
                tenant=self.tenant,
                is_active=True,
                trigger_event=event_type,
                object_type=obj._meta.model_name
            ).order_by('priority')
            
            execution_results = []
            
            for workflow_rule in matching_workflows:
                try:
                    # Check execution limits
                    if not self._check_execution_limits(workflow_rule, obj):
                        continue
                    
                    # Execute workflow
                    result = self.workflow_engine.execute_workflow(
                        workflow_rule, obj, event_type
                    )
                    
                    execution_results.append({
                        'workflow_id': workflow_rule.id,
                        'workflow_name': workflow_rule.name,
                        'execution_result': result
                    })
                    
                except Exception as e:
                    logger.error(f"Individual workflow execution failed: {e}")
                    execution_results.append({
                        'workflow_id': workflow_rule.id,
                        'workflow_name': workflow_rule.name,
                        'error': str(e)
                    })
            
            # Log event processing
            self.log_activity(
                'workflows_triggered_by_event',
                obj._meta.model_name,
                obj.id,
                {
                    'event_type': event_type,
                    'workflows_triggered': len(execution_results),
                    'successful_executions': sum(1 for r in execution_results if 'error' not in r)
                }
            )
            
            return execution_results
            
        except Exception as e:
            logger.error(f"Event-based workflow triggering failed: {e}", exc_info=True)
            raise WorkflowException(f"Event-based workflow triggering failed: {str(e)}")
    
    # ============================================================================
    # ADVANCED WORKFLOW FEATURES
    # ============================================================================
    
    def create_conditional_workflow(self, baseconditional_branches: List[Dict]) -> WorkflowRule:
        """
        Create complex conditional workflow with multiple branches
        
        Args: Base workflow configuration
            conditional_branches: List of conditional branch configurations
        
        Returns:
            Complex WorkflowRule instance
        """
        try:
            self.validate_user_permission('crm.add_workflowrule')
            
            # Create master workflow with conditional actions
            conditional_actions = []
            
            for branch in conditional_branches:
                conditional_action = {
                    'type': 'conditional_action',
                    'conditions': branch['conditions'],
                    'condition_logic': branch.get('condition_logic', 'AND'),
                    'actions': branch['actions'],
                    'branch_name': branch.get('name', f"Branch {len(conditional_actions) + 1}")
                }
                conditional_actions.append(conditional_action)
            
            # Add default action if provided
            if 
                conditional_actions.append({
                    'type': 'default_action',
                    'actions': base_rule_data['default_actions']
                })
            
            # Update base rule data
            base_rule_data['actions'] = conditional_actions
            base_rule_data['name'] = f"Conditional: {base_rule_data.get('name', 'Unnamed')}"
            
            workflow_rule = self.create_workflow_rule(base_rule_data)
            
            return workflow_rule
            
        except Exception as e:
            logger.error(f"Conditional workflow creation failed: {e}", exc_info=True)
            raise WorkflowException(f"Conditional workflow creation failed: {str(e)}")
    
    def create_scheduled_workflow(self, rule_data: Dict, 
                                 schedule_config: Dict) -> WorkflowRule:
        """
        Create scheduled workflow that runs at specific times
        
        Args: configuration
        
        Returns:
            Scheduled WorkflowRule instance
        """
        try:
            # Validate schedule configuration
            self._validate_schedule_config(schedule_config)
            
            # Set trigger event for scheduled workflows
            rule_data['trigger_event'] = 'scheduled'
            rule_data['schedule_config'] = schedule_config
            
            workflow_rule = self.create_workflow_rule(rule_data)
            
            # Create automation schedule
            AutomationSchedule.objects.create(
                workflow_rule=workflow_rule,
                schedule_type=schedule_config['type'],
                schedule_expression=schedule_config.get('expression', ''),
                timezone=schedule_config.get('timezone', 'UTC'),
                is_active=True,
                tenant=self.tenant,
                next_execution=self._calculate_next_execution(schedule_config)
            )
            
            return workflow_rule
            
        except Exception as e:
            logger.error(f"Scheduled workflow creation failed: {e}", exc_info=True)
            raise WorkflowException(f"Scheduled workflow creation failed: {str(e)}")
    
    def execute_bulk_workflow(self, workflow_id: int, object_ids: List[int], 
                             batch_size: int = 50) -> Dict:
        """
        Execute workflow on multiple objects in batches
        
        Args:
            workflow_id: Workflow rule ID
            object_ids: List of object IDs to process
            batch_size: Batch processing size
        
        Returns:
            Bulk execution results
        """
        try:
            workflow_rule = WorkflowRule.objects.get(id=workflow_id, tenant=self.tenant)
            self.validate_user_permission('crm.change_workflowrule', workflow_rule)
            
            # Get model class
            model_class = self._get_model_class(workflow_rule.object_type)
            
            results = {
                'total_objects': len(object_ids),
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'batch_results': []
            }
            
            # Process in batches
            for i in range(0, len(object_ids), batch_size):
                batch_ids = object_ids[i:i + batch_size]
                batch_objects = model_class.objects.filter(
                    id__in=batch_ids,
                    tenant=self.tenant
                )
                
                batch_result = {
                    'batch_number': (i // batch_size) + 1,
                    'batch_size': len(batch_objects),
                    'successful': 0,
                    'failed': 0,
                    'errors': []
                }
                
                for obj in batch_objects:
                    try:
                        self.workflow_engine.execute_workflow(
                            workflow_rule, obj, 'bulk_execution'
                        )
                        batch_result['successful'] += 1
                        results['successful'] += 1
                    except Exception as e:
                        batch_result['failed'] += 1
                        batch_result['errors'].append({
                            'object_id': obj.id,
                            'error': str(e)
                        })
                        results['failed'] += 1
                    
                    results['processed'] += 1
                
                results['batch_results'].append(batch_result)
            
            self.log_activity(
                'bulk_workflow_executed',
                'WorkflowRule',
                workflow_rule.id,
                {
                    'total_objects': results['total_objects'],
                    'successful': results['successful'],
                    'failed': results['failed']
                }
            )
            
            return results
            
        except WorkflowRule.DoesNotExist:
            raise WorkflowException("Workflow rule not found")
        except Exception as e:
            logger.error(f"Bulk workflow execution failed: {e}", exc_info=True)
            raise WorkflowException(f"Bulk workflow execution failed: {str(e)}")
    
    # ============================================================================
    # WORKFLOW ANALYTICS AND MONITORING
    # ============================================================================
    
    def get_workflow_performance_analytics(self, workflow_id: int = None, 
                                         period: str = '30d') -> Dict:
        """
        Get comprehensive workflow performance analytics
        
        Args:
            workflow_id: Specific workflow (all workflows if None)
            period: Analysis period
        
        Returns:
            Workflow performance data
        """
        try:
            # Calculate date range
            period_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = period_days.get(period, 30)
            start_date = timezone.now() - timedelta(days=days)
            
            # Build query
            executions_query = WorkflowExecution.objects.filter(
                tenant=self.tenant,
                started_at__gte=start_date
            )
            
            if workflow_id:
                executions_query = executions_query.filter(workflow_rule_id=workflow_id)
            
            # Calculate metrics
            total_executions = executions_query.count()
            successful_executions = executions_query.filter(status='COMPLETED').count()
            failed_executions = executions_query.filter(status='FAILED').count()
            
            # Performance metrics
            avg_execution_time = executions_query.filter(
                status='COMPLETED',
                completed_at__isnull=False
            ).aggregate(
                avg_time=models.Avg(
                    models.F('completed_at') - models.F('started_at')
                )
            )['avg_time']
            
            # Top performing workflows
            top_workflows = executions_query.values(
                'workflow_rule__name'
            ).annotate(
                execution_count=Count('id'),
                success_rate=Count('id', filter=Q(status='COMPLETED')) * 100.0 / Count('id')
            ).order_by('-execution_count')[:10]
            
            # Daily execution trends
            daily_trends = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                day_executions = executions_query.filter(
                    started_at__date=date.date()
                ).count()
                daily_trends.append({
                    'date': date.date().isoformat(),
                    'executions': day_executions
                })
            
            analytics_data = {
                'period': period,
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'success_rate': (successful_executions / total_executions * 100) if total_executions > 0 else 0,
                'average_execution_time': avg_execution_time.total_seconds() if avg_execution_time else 0,
                'top_workflows': list(top_workflows),
                'daily_trends': daily_trends,
                'generated_at': timezone.now().isoformat()
            }
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Workflow analytics generation failed: {e}", exc_info=True)
            raise WorkflowException(f"Workflow analytics generation failed: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _validate_workflow_actions(self, actions: List[Dict]):
        """Validate workflow actions format and content"""
        required_action_fields = ['type']
        
        for action in actions:
            for field in required_action_fields:
                if field not in action:
                    raise WorkflowException(f"Action missing required field: {field}")
            
            # Validate specific action types
            action_type = action['type']
            if action_type == 'send_email':
                if 'recipients' not in action or 'template' not in action:
                    raise WorkflowException("Email action requires 'recipients' and 'template'")
            
            elif action_type == 'update_field':
                if 'field' not in action or 'value' not in action:
                    raise WorkflowException("Update field action requires 'field' and 'value'")
    
    def _calculate_rule_complexity(self, rule
        """Calculate complexity score for workflow rule"""
        complexity = 0
        
        # Base complexity
        complexity += 1
        
        # Conditions complexity
        conditions = rule_data.get('conditions', [])
        complexity += len(conditions)
        
        # Actions complexity
        actions = rule_data.get('actions', [])
        complexity += len(actions) * 2  # Actions are more complex
        
        # Conditional logic complexity
        if rule_data.get('condition_logic', 'AND') not in ['AND', 'OR']:
            complexity += 3  # Complex logic
        
        return complexity
    
    def _get_model_class(self, object_type: str):
        """Get model class by object type string"""
        model_mapping = {
            'lead': Lead,
            'account': Account,
            'opportunity': Opportunity,
            'activity': Activity,
            'campaign': Campaign,
            'ticket': Ticket
        }
        
        return model_mapping.get(object_type)
    
    def _check_execution_limits(self, workflow_rule: WorkflowRule, obj: Any) -> bool:
        """Check if workflow execution limits are exceeded"""
        if not workflow_rule.execution_limit:
            return True
        
        # Check executions in last 24 hours
        recent_executions = WorkflowExecution.objects.filter(
            workflow_rule=workflow_rule,
            object_type=obj._meta.model_name,
            object_id=obj.id,
            started_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        return recent_executions < workflow_rule.execution_limit