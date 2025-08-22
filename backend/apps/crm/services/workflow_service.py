# ============================================================================
# backend/apps/crm/services/workflow_service.py - Workflow Automation Service
# ============================================================================

from typing import Dict, List, Any, Optional
from django.db import transaction, models
from django.utils import timezone
from django.template import Context, Template
from django.core.mail import send_mail
from datetime import datetime, timedelta
import json
import re

from .base import BaseService, CacheableMixin, NotificationMixin, CRMServiceException
from ..models import WorkflowRule, WorkflowExecution, Lead, Account, Opportunity, Activity


class WorkflowService(BaseService, CacheableMixin, NotificationMixin):
    """Advanced workflow automation engine"""
    
    def __init__(self, tenant, user=None):
        super().__init__(tenant, user)
        self.execution_context = {}
    
    @transaction.atomic
    def execute_workflow_rule(self, workflow_rule: WorkflowRule, trigger workflow rule with comprehensive logging"""
        execution = WorkflowExecution.objects.create(
            tenant=self.tenant,
            workflow_rule=workflow_rule,
            triggered_by=self.user,
            started_at=timezone.now(),
            status='RUNNING',
            execution_data=trigger_data
        )
        
        try:
            # Validate trigger conditions
            if not self._evaluate_trigger_conditions(workflow_rule, trigger_data):
                execution.status = 'COMPLETED'
                execution.completed_at = timezone.now()
                execution.save()
                return {'status': 'skipped', 'reason': 'conditions_not_met'}
            
            # Execute actions
            results = []
            for action in workflow_rule.actions:
                try:
                    result = self._execute_action(action, trigger_data, workflow_rule)
                    results.append({
                        'action_type': action.get('type'),
                        'status': 'success',
                        'result': result
                    })
                except Exception as e:
                    error_msg = str(e)
                    results.append({
                        'action_type': action.get('type'),
                        'status': 'error',
                        'error': error_msg
                    })
                    
                    # Handle errors based on configuration
                    if workflow_rule.on_error_action == 'STOP':
                        raise CRMServiceException(f"Workflow stopped due to error: {error_msg}")
                    elif workflow_rule.on_error_action == 'NOTIFY':
                        self._notify_admin_of_error(workflow_rule, error_msg)
            
            # Update execution record
            execution.status = 'COMPLETED'
            execution.completed_at = timezone.now()
            execution.execution_data.update({'results': results})
            execution.save()
            
            # Update workflow statistics
            workflow_rule.execution_count += 1
            workflow_rule.success_count += 1
            workflow_rule.last_executed = timezone.now()
            workflow_rule.save()
            
            return {
                'status': 'completed',
                'execution_id': execution.id,
                'results': results
            }
            
        except Exception as e:
            execution.status = 'FAILED'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
            
            workflow_rule.execution_count += 1
            workflow_rule.failure_count += 1
            workflow_rule.save()
            
            self.logger.error(f"Workflow execution failed: {workflow_rule.name} - {str(e)}")
            raise
    
    def trigger_workflows(self, trigger_type: str, obj: models.Model, 
                         changes: Dict = None) -> List[Dict]:
        """Trigger all applicable workflows for an event"""
        workflows = WorkflowRule.objects.filter(
            tenant=self.tenant,
            is_active=True,
            trigger_type=trigger_type,
            trigger_object=obj.__class__.__name__.lower()
        ).order_by('execution_order')
        
        results = []
        trigger_data = {
            'object_type': obj.__class__.__name__,
            'object_id': obj.id,
            'object_data': self._serialize_object(obj),
            'changes': changes or {},
            'timestamp': timezone.now().isoformat(),
            'user_id': self.user.id if self.user else None,
        }
        
        for workflow in workflows:
            try:
                if workflow.schedule_type == 'IMMEDIATE':
                    result = self.execute_workflow_rule(workflow, trigger_data)
                    results.append(result)
                else:
                    # Schedule for later execution
                    self._schedule_workflow_execution(workflow, trigger_data)
                    results.append({'status': 'scheduled', 'workflow_id': workflow.id})
            except Exception as e:
                self.logger.error(f"Error executing workflow {workflow.name}: {e}")
                results.append({
                    'status': 'error',
                    'workflow_id': workflow.id,
                    'error': str(e)
                })
        
        return results
    
    def createowRule:
        """Create new workflow rule with validation"""
        self.require_permission('can_manage_workflows')
        
        # Validate workflow configuration
        self._validate_workflow_config(workflow_data)
        
        workflow_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
        })
        
        workflow = WorkflowRule.objects.create(**workflow_data)
        
        # Test workflow if in test mode
        if workflow_data.get('test_mode'):
            test_result = self._test_workflow_rule(workflow)
            return workflow, test_result
        
        self.logger.info(f"Workflow rule created: {workflow.name}")
        return workflow
    
    def _evaluate_trigger_conditions(self, workflow_rule: WorkflowRule, :
        """Evaluate if trigger conditions are met"""
        conditions = workflow_rule.trigger_conditions
        if not conditions:
            return True
        
        obj_data = trigger_data.get('object_data', {})
        changes = trigger_data.get('changes', {})
        
        # Evaluate each condition
        for condition in conditions.get('conditions', []):
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if not self._evaluate_condition(obj_data, field, operator, value, changes):
                return False
        
        return True
    
    def _execute_action(self, action: Dict
                       workflow_rule: WorkflowRule) -> Any:
        """Execute a single workflow action"""
        action_type = action.get('type')
        
        if action_type == 'SEND_EMAIL':
            return self._execute_email_action(action, trigger_data)
        elif action_type == 'CREATE_TASK':
            return self._execute_task_action(action, trigger_data)
        elif action_type == 'UPDATE_FIELD':
            return self._execute_update_action(action, trigger_data)
        elif action_type == 'ASSIGN_RECORD':
            return self._execute_assign_action(action, trigger_data)
        elif action_type == 'CREATE_RECORD':
            return self._execute_create_action(action, trigger_data)
        elif action_type == 'SEND_SMS':
            return self._execute_sms_action(action, trigger_data)
        elif action_type == 'WEBHOOK':
            return self._execute_webhook_action(action, trigger_data)
        elif action_type == 'SCORE_UPDATE':
            return self._execute_scoring_action(action, trigger_data)
        else:
            raise CRMServiceException(f"Unknown action type: {action_type}")
    
    def _execute_email_action(self, action: Dict, trigger
        """Execute email sending action"""
        email_config = action.get('config', {})
        
        # Get recipients
        recipients = self._resolve_recipients(email_config.get('recipients'), trigger_data)
        
        # Process email template
        template_content = email_config.get('template')
        if template_content:
            context = self._build_email_context(trigger_data)
            
            subject_template = Template(template_content.get('subject', ''))
            body_template = Template(template_content.get('body', ''))
            
            subject = subject_template.render(Context(context))
            body = body_template.render(Context(context))
        else:
            subject = email_config.get('subject', 'Workflow Notification')
            body = email_config.get('body', 'This is an automated notification.')
        
        # Send emails
        sent_count = 0
        for recipient in recipients:
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=email_config.get('from_email'),
                    recipient_list=[recipient],
                    html_message=body if email_config.get('is_html') else None
                )
                sent_count += 1
            except Exception as e:
                self.logger.error(f"Failed to send email to {recipient}: {e}")
        
        return {
            'sent_count': sent_count,
            'total_recipients': len(recipients),
            'subject': subject
        }
    
    def _execute_task_action(self, Dict) -> Dict:
        """Execute task creation action"""
        task_config = action.get('config', {})
        
        # Resolve assignee
        assignee = self._resolve_user(task_config.get('assignee'), trigger_data)
        
        # Create activity/task
        activity_data = {
            'tenant': self.tenant,
            'subject': self._resolve_template(task_config.get('subject'), trigger_data),
            'description': self._resolve_template(task_config.get('description'), trigger_data),
            'activity_type': self._get_task_activity_type(),
            'assigned_to': assignee,
            'start_datetime': timezone.now() + timedelta(minutes=task_config.get('delay_minutes', 0)),
            'end_datetime': timezone.now() + timedelta(
                minutes=task_config.get('delay_minutes', 0) + task_config.get('duration_minutes', 60)
            ),
            'status': 'PLANNED',
            'priority': task_config.get('priority', 'MEDIUM'),
            'created_by': self.user,
        }
        
        # Link to triggered object
        obj_type = trigger_data.get('object_type')
        obj_id = trigger_data.get('object_id')
        if obj_type and obj_id:
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get(model=obj_type.lower())
            activity_data['content_type'] = content_type
            activity_data['object_id'] = str(obj_id)
        
        activity = Activity.objects.create(**activity_data)
        
        return {
            'activity_id': activity.id,
            'assignee': assignee.get_full_name() if assignee else None,
            'subject': activity.subject
        }
    
    def _execute_update_action(self, Dict) -> Dict:
        """Execute field update action"""
        update_config = action.get('config', {})
        
        # Get the object to update
        obj_type = trigger_data.get('object_type')
        obj_id = trigger_data.get('object_id')
        
        model_class = self._get_model_class(obj_type)
        obj = model_class.objects.get(id=obj_id, tenant=self.tenant)
        
        updated_fields = {}
        for field_update in update_config.get('field_updates', []):
            field_name = field_update.get('field')
            new_value = self._resolve_value(field_update.get('value'), trigger_data)
            
            if hasattr(obj, field_name):
                old_value = getattr(obj, field_name)
                setattr(obj, field_name, new_value)
                updated_fields[field_name] = {'old': old_value, 'new': new_value}
        
        obj.updated_by = self.user
        obj.save()
        
        return {
            'object_id': obj.id,
            'updated_fields': updated_fields
        }
    
    def _ Dict) -> Dict:
        """Execute record assignment action"""
        assign_config = action.get('config', {})
        
        # Get the object to assign
        obj_type = trigger_data.get('object_type')
        obj_id = trigger_data.get('object_id')
        
        model_class = self._get_model_class(obj_type)
        obj = model_class.objects.get(id=obj_id, tenant=self.tenant)
        
        # Resolve assignee
        assignee = self._resolve_user(assign_config.get('assignee'), trigger_data)
        
        if hasattr(obj, 'owner'):
            old_owner = obj.owner
            obj.owner = assignee
            obj.updated_by = self.user
            obj.save()
            
            return {
                'object_id': obj.id,
                'old_owner': old_owner.get_full_name() if old_owner else None,
                'new_owner': assignee.get_full_name() if assignee else None
            }
        
        raise CRMServiceException(f"Object type {obj_type} does not support assignment")
    
    def _execute_webhook_action(self, action: Dict Dict:
        """Execute webhook call action"""
        import requests
        
        webhook_config = action.get('config', {})
        url = webhook_config.get('url')
        method = webhook_config.get('method', 'POST')
        headers = webhook_config.get('headers', {})
        
        # Prepare payload
        payload = {
            'tenant_id': str(self.tenant.id),
            'trigger_data': trigger_data,
            'timestamp': timezone.now().isoformat(),
        }
        
        # Add custom data
        if webhook_config.get('custom_data'):
            payload.update(webhook_config['custom_data'])
        
        # Make request
        try:
            response = requests.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            return {
                'status_code': response.status_code,
                'response_size': len(response.content),
                'success': True
            }
        except requests.RequestException as e:
            return {
                'error': str(e),
                'success': False
            }
    
    def _execute_scoring_action(self, action: Dict, triggerd/account scoring update"""
        from .scoring_service import ScoringService
        
        scoring_config = action.get('config', {})
        obj_type = trigger_data.get('object_type')
        obj_id = trigger_data.get('object_id')
        
        scoring_service = ScoringService(self.tenant, self.user)
        
        if obj_type.lower() == 'lead':
            lead = Lead.objects.get(id=obj_id, tenant=self.tenant)
            result = scoring_service.calculate_lead_score(lead)
            return {'lead_id': lead.id, 'new_score': result['total_score']}
        elif obj_type.lower() == 'account':
            account = Account.objects.get(id=obj_id, tenant=self.tenant)
            result = scoring_service.calculate_account_score(account)
            return {'account_id': account.id, 'new_score': result['total_score']}
        
        raise CRMServiceException(f"Scoring not supported for object type: {obj_type}")
    
    def _resolve_recipients(self, recipients_config: List,str]:
        """Resolve email recipients from configuration"""
        recipients = []
        
        for recipient_config in recipients_config:
            if recipient_config.get('type') == 'field':
                # Get email from object field
                field_value = self._get_field_value(trigger_data, recipient_config.get('field'))
                if field_value and '@' in str(field_value):
                    recipients.append(str(field_value))
            elif recipient_config.get('type') == 'user':
                # Get specific user email
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=recipient_config.get('user_id'))
                    recipients.append(user.email)
                except User.DoesNotExist:
                    pass
            elif recipient_config.get('type') == 'role':
                # Get users with specific role
                self._get_role_emails(recipient_config.get('role'), recipients)
        
        return recipients
    
    def _resolve_template) -> str:
        """Resolve template string with trigger data"""
        if not template_str:
            return ''
        
        context = self._build_email_context(trigger_data)
        template = Template(template_str)
        return template.render(Context(context))
    
    def _buil
        """Build context for email templates"""
        context = {
            'tenant': self.tenant.name,
            'user': self.user.get_full_name() if self.user else 'System',
            'timestamp': timezone.now(),
            'object_data': trigger_data.get('object_data', {}),
            'changes': trigger_data.get('changes', {}),
        }
        
        # Add object-specific context
        obj_type = trigger_data.get('object_type', '').lower()
        if obj_type == 'lead':
            context['lead'] = trigger_data.get('object_data', {})
        elif obj_type == 'account':
            context['account'] = trigger_data.get('object_data', {})
        elif obj_type == 'opportunity':
            context['opportunity'] = trigger_data.get('object_data', {})
        
        return context
    
    def _serialize_object(self, obj: models.Model) -> Dict:
        """Serialize model object for workflow context"""
        data = {}
        
        for field in obj._meta.fields:
            field_name = field.name
            field_value = getattr(obj, field_name)
            
            # Handle different field types
            if hasattr(field_value, 'isoformat'):  # DateTime fields
                data[field_name] = field_value.isoformat()
            elif isinstance(field_value, models.Model):  # Foreign keys
                data[field_name] = str(field_value)
                data[f'{field_name}_id'] = field_value.id
            else:
                data[field_name] = str(field_value) if field_value is not None else None
        
        return data
    
    def _validate_workflow_config(self, workflow
        required_fields = ['name', 'trigger_type', 'trigger_object', 'actions']
        for field in required_fields:
            if not workflow_data.get(field):
                raise CRMServiceException(f"Missing required field: {field}")
        
        # Validate actions
        for action in workflow_data.get('actions', []):
            if not action.get('type'):
                raise CRMServiceException("Action must have a type")
            
            # Validate specific action configurations
            self._validate_action_config(action)
    
    def _validate_action_config(self, action: Dict):
        """Validate individual action configuration"""
        action_type = action.get('type')
        config = action.get('config', {})
        
        if action_type == 'SEND_EMAIL':
            if not config.get('recipients'):
                raise CRMServiceException("Email action must have recipients")
        elif action_type == 'CREATE_TASK':
            if not config.get('subject'):
                raise CRMServiceException("Task action must have a subject")
        elif action_type == 'WEBHOOK':
            if not config.get('url'):
                raise CRMServiceException("Webhook action must have a URL")
    
    def get_workflow_analytics(self, workflow_id: int = None) -> Dict:
        """Get workflow execution analytics"""
        queryset = WorkflowExecution.objects.filter(tenant=self.tenant)
        
        if workflow_id:
            queryset = queryset.filter(workflow_rule_id=workflow_id)
        
        # Execution summary
        total_executions = queryset.count()
        successful = queryset.filter(status='COMPLETED').count()
        failed = queryset.filter(status='FAILED').count()
        
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0
        
        # Performance metrics
        avg_execution_time = queryset.filter(
            started_at__isnull=False,
            completed_at__isnull=False
        ).extra(
            select={'duration': 'EXTRACT(EPOCH FROM (completed_at - started_at))'}
        ).aggregate(avg_duration=models.Avg('duration'))['avg_duration'] or 0
        
        # Most active workflows
        workflow_stats = WorkflowRule.objects.filter(
            tenant=self.tenant
        ).values(
            'id', 'name'
        ).annotate(
            executions=models.Count('executions'),
            success_count=models.Sum('success_count'),
            failure_count=models.Sum('failure_count')
        ).order_by('-executions')[:10]
        
        # Execution trends
        daily_stats = queryset.extra(
            select={'date': 'DATE(started_at)'}
        ).values('date').annotate(
            count=models.Count('id'),
            success=models.Count('id', filter=models.Q(status='COMPLETED')),
            failed=models.Count('id', filter=models.Q(status='FAILED'))
        ).order_by('date')
        
        return {
            'summary': {
                'total_executions': total_executions,
                'successful': successful,
                'failed': failed,
                'success_rate': round(success_rate, 2),
                'avg_execution_time': round(avg_execution_time, 2),
            },
            'top_workflows': list(workflow_stats),
            'daily_trends': list(daily_stats),
        }