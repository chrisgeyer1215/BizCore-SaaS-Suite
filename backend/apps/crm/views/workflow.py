# ============================================================================
# backend/apps/crm/views/workflow.py - Workflow & Automation Views
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Q, Count, Sum, Avg, F, Case, When
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction
from django.forms import model_to_dict
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import WorkflowRule, WorkflowExecution, Integration, WebhookConfiguration, CustomField
from ..serializers import (
    WorkflowRuleSerializer, WorkflowExecutionSerializer, IntegrationSerializer,
    WebhookConfigurationSerializer, CustomFieldSerializer
)
from ..permissions import WorkflowPermission
from ..filters import WorkflowRuleFilter, WorkflowExecutionFilter
from ..services import WorkflowService, IntegrationService


class WorkflowRuleListView(CRMBaseMixin, ListView):
    """Workflow Rules list view with management capabilities"""
    
    model = WorkflowRule
    template_name = 'crm/workflow/rule_list.html'
    context_object_name = 'rules'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations
        queryset = queryset.annotate(
            execution_count=Count('executions'),
            success_count=Count('executions', filter=Q(executions__status='SUCCESS')),
            failure_count=Count('executions', filter=Q(executions__status='FAILED')),
            last_executed=F('executions__executed_at')
        ).select_related('created_by').prefetch_related('conditions', 'actions')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        trigger_type = self.request.GET.get('trigger_type')
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        
        target_model = self.request.GET.get('target_model')
        if target_model:
            queryset = queryset.filter(target_model=target_model)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        rules = self.get_queryset()
        context.update({
            'total_rules': rules.count(),
            'active_rules': rules.filter(is_active=True).count(),
            'trigger_types': WorkflowRule.TRIGGER_TYPES,
            'target_models': WorkflowRule.TARGET_MODELS,
            'rule_statistics': self.get_rule_statistics(rules),
            'recent_executions': self.get_recent_executions(),
        })
        
        return context
    
    def get_rule_statistics(self, rules):
        """Get workflow rule statistics"""
        total_executions = sum(rule.execution_count or 0 for rule in rules)
        total_successes = sum(rule.success_count or 0 for rule in rules)
        
        return {
            'total_executions': total_executions,
            'success_rate': (total_successes / total_executions * 100) if total_executions > 0 else 0,
            'rules_by_trigger': rules.values('trigger_type').annotate(
                count=Count('id')
            ).order_by('-count'),
            'rules_by_model': rules.values('target_model').annotate(
                count=Count('id')
            ).order_by('-count'),
        }
    
    def get_recent_executions(self):
        """Get recent workflow executions"""
        return WorkflowExecution.objects.filter(
            tenant=self.request.tenant
        ).select_related('rule', 'triggered_by').order_by('-executed_at')[:10]


class WorkflowRuleDetailView(CRMBaseMixin, DetailView):
    """Workflow Rule detail view with execution history"""
    
    model = WorkflowRule
    template_name = 'crm/workflow/rule_detail.html'
    context_object_name = 'rule'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('created_by').prefetch_related(
                'conditions', 'actions', 'executions__triggered_by'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rule = self.object
        
        context.update({
            'rule_analytics': self.get_rule_analytics(rule),
            'execution_history': self.get_execution_history(rule),
            'rule_conditions': self.get_rule_conditions(rule),
            'rule_actions': self.get_rule_actions(rule),
            'performance_metrics': self.get_performance_metrics(rule),
            'can_edit': self.can_edit_rule(rule),
            'test_data': self.get_test_data(rule),
        })
        
        return context
    
    def get_rule_analytics(self, rule):
        """Get rule performance analytics"""
        executions = rule.executions.all()
        
        if not executions.exists():
            return {
                'total_executions': 0,
                'success_rate': 0,
                'avg_execution_time': 0,
                'last_executed': None,
                'execution_trend': [],
            }
        
        total_executions = executions.count()
        successful_executions = executions.filter(status='SUCCESS').count()
        
        # Execution trend (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        daily_executions = executions.filter(
            executed_at__gte=thirty_days_ago
        ).extra({
            'day': 'date(executed_at)'
        }).values('day').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='SUCCESS'))
        ).order_by('day')
        
        return {
            'total_executions': total_executions,
            'success_rate': (successful_executions / total_executions * 100) if total_executions > 0 else 0,
            'avg_execution_time': executions.aggregate(
                avg_time=Avg('execution_time_ms')
            )['avg_time'] or 0,
            'last_executed': executions.order_by('-executed_at').first().executed_at if executions.exists() else None,
            'execution_trend': list(daily_executions),
            'error_analysis': self.get_error_analysis(rule),
        }
    
    def get_execution_history(self, rule):
        """Get detailed execution history"""
        return rule.executions.select_related('triggered_by').order_by('-executed_at')[:50]
    
    def get_rule_conditions(self, rule):
        """Get rule conditions with details"""
        conditions = []
        
        try:
            conditions_data = json.loads(rule.conditions) if rule.conditions else []
             = {
                    'field': condition.get('field', ''),
                    'operator': condition.get('operator', ''),
                    'value': condition.get('value', ''),
                    'field_type': condition.get('field_type', 'text'),
                    'description': self.format_condition_description(condition),
                }
                conditions.append(condition_info)
        
        except json.JSONDecodeError:
            conditions = [{'error': 'Invalid conditions format'}]
        
        return conditions
    
    def get_rule_actions(self, rule):
        """Get rule actions with details"""
        actions = []
        
        try:
            actions_data = json.loads(rule.actions) if rule.actions else []
            
            for action ininfo = {
                    'type': action.get('type', ''),
                    'target': action.get('target', ''),
                    'parameters': action.get('parameters', {}),
                    'description': self.format_action_description(action),
                }
                actions.append(action_info)
        
        except json.JSONDecodeError:
            actions = [{'error': 'Invalid actions format'}]
        
        return actions
    
    def get_performance_metrics(self, rule):
        """Get rule performance metrics"""
        executions = rule.executions.all()
        
        if not executions.exists():
            return {}
        
        # Performance by time of day
        hourly_performance = executions.extra({
            'hour': 'extract(hour from executed_at)'
        }).values('hour').annotate(
            count=Count('id'),
            success_rate=Count('id', filter=Q(status='SUCCESS')) * 100.0 / Count('id')
        ).order_by('hour')
        
        # Performance by day of week
        daily_performance = executions.extra({
            'weekday': 'extract(dow from executed_at)'
        }).values('weekday').annotate(
            count=Count('id'),
            success_rate=Count('id', filter=Q(status='SUCCESS')) * 100.0 / Count('id')
        ).order_by('weekday')
        
        return {
            'hourly_performance': list(hourly_performance),
            'daily_performance': list(daily_performance),
            'avg_execution_time': executions.aggregate(
                avg_time=Avg('execution_time_ms')
            )['avg_time'] or 0,
        }
    
    def get_error_analysis(self, rule):
        """Get error analysis for failed executions"""
        failed_executions = rule.executions.filter(status='FAILED')
        
        if not failed_executions.exists():
            return {}
        
        # Group errors by type
        error_types = {}
        for execution in failed_executions:
            error_msg = execution.error_message or 'Unknown error'
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
        
        return {
            'total_failures': failed_executions.count(),
            'error_types': error_types,
            'recent_errors': failed_executions.order_by('-executed_at')[:5],
        }
    
    def can_edit_rule(self, rule):
        """Check if user can edit rule"""
        return (
            rule.created_by == self.request.user or
            self.request.user.has_perm('crm.change_workflowrule')
        )
    
    def get_test_data(self, rule):
        """Get sample test data for rule"""
        # This would provide sample data structure based on target model
        target_model = rule.target_model.lower()
        
        test_data = {
            'lead': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'status': 'NEW',
                'source': 'Website',
                'score': 85,
            },
            'opportunity': {
                'name': 'Enterprise Deal',
                'amount': 50000,
                'stage': 'PROPOSAL',
                'probability': 60,
                'close_date': '2024-03-15',
            },
            'account': {
                'name': 'Acme Corp',
                'industry': 'Technology',
                'revenue': 1000000,
                'employees': 500,
            }
        }
        
        return test_data.get(target_model, {})
    
    def format_condition_description(self, condition):
        """Format condition into human readable description"""
        field = condition.get('field', '')
        operator = condition.get('operator', '')
        value = condition.get('value', '')
        
        operator_map = {
            'eq': 'equals',
            'ne': 'does not equal',
            'gt': 'is greater than',
            'lt': 'is less than',
            'contains': 'contains',
            'starts_with': 'starts with',
            'ends_with': 'ends with',
        }
        
        operator_text = operator_map.get(operator, operator)
        
        return f"{field} {operator_text} {value}"
    
    def format_action_description(self, action):
        """Format action into human readable description"""
        action_type = action.get('type', '')
        target = action.get('target', '')
        parameters = action.get('parameters', {})
        
        if action_type == 'send_email':
            return f"Send email to {target}"
        elif action_type == 'update_field':
            return f"Update {target} to {parameters.get('value', '')}"
        elif action_type == 'create_activity':
            return f"Create {parameters.get('activity_type', 'activity')}"
        elif action_type == 'assign_user':
            return f"Assign to {target}"
        elif action_type == 'webhook':
            return f"Send webhook to {target}"
        
        return f"{action_type} on {target}"


class WorkflowRuleCreateView(CRMBaseMixin, CreateView):
    """Create new workflow rule"""
    
    model = WorkflowRule
    template_name = 'crm/workflow/rule_create.html'
    fields = ['name', 'description', 'trigger_type', 'target_model', 'is_active']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'trigger_types': WorkflowRule.TRIGGER_TYPES,
            'target_models': WorkflowRule.TARGET_MODELS,
            'available_fields': self.get_available_fields(),
            'available_actions': self.get_available_actions(),
            'condition_operators': self.get_condition_operators(),
        })
        
        return context
    
    def get_available_fields(self):
        """Get available fields for each model"""
        from .. import models
        
        model_fields = {}
        
        for model_name in ['Lead', 'Opportunity', 'Account', 'Activity', 'Campaign']:
            model_class = getattr(models, model_name)
            fields = []
            
            for field in model_class._meta.fields:
                if not field.name.endswith('_id') and field.name not in ['tenant', 'created_by', 'updated_by']:
                    fields.append({
                        'name': field.name,
                        'verbose_name': field.verbose_name,
                        'type': field.__class__.__name__.lower(),
                    })
            
            model_fields[model_name.lower()] = fields
        
        return model_fields
    
    def get_available_actions(self):
        """Get available workflow actions"""
        return [
            {
                'type': 'send_email',
                'name': 'Send Email',
                'description': 'Send an email notification',
                'parameters': ['recipient', 'template', 'subject', 'message']
            },
            {
                'type': 'update_field',
                'name': 'Update Field',
                'description': 'Update a field value',
                'parameters': ['field', 'value']
            },
            {
                'type': 'create_activity',
                'name': 'Create Activity',
                'description': 'Create a follow-up activity',
                'parameters': ['activity_type', 'subject', 'assigned_to', 'due_date']
            },
            {
                'type': 'assign_user',
                'name': 'Assign User',
                'description': 'Assign record to a user',
                'parameters': ['user']
            },
            {
                'type': 'send_webhook',
                'name': 'Send Webhook',
                'description': 'Send data to external webhook',
                'parameters': ['url', 'method', 'headers', 'payload']
            },
            {
                'type': 'create_task',
                'name': 'Create Task',
                'description': 'Create a task for follow-up',
                'parameters': ['title', 'description', 'assigned_to', 'due_date']
            }
        ]
    
    def get_condition_operators(self):
        """Get available condition operators"""
        return [
            {'value': 'eq', 'name': 'Equals', 'types': ['text', 'number', 'date', 'boolean']},
            {'value': 'ne', 'name': 'Not Equals', 'types': ['text', 'number', 'date', 'boolean']},
            {'value': 'gt', 'name': 'Greater Than', 'types': ['number', 'date']},
            {'value': 'gte', 'name': 'Greater Than or Equal', 'types': ['number', 'date']},
            {'value': 'lt', 'name': 'Less Than', 'types': ['number', 'date']},
            {'value': 'lte', 'name': 'Less Than or Equal', 'types': ['number', 'date']},
            {'value': 'contains', 'name': 'Contains', 'types': ['text']},
            {'value': 'starts_with', 'name': 'Starts With', 'types': ['text']},
            {'value': 'ends_with', 'name': 'Ends With', 'types': ['text']},
            {'value': 'is_empty', 'name': 'Is Empty', 'types': ['text', 'number', 'date']},
            {'value': 'is_not_empty', 'name': 'Is Not Empty', 'types': ['text', 'number', 'date']},
            {'value': 'changed', 'name': 'Changed', 'types': ['any']},
            {'value': 'changed_to', 'name': 'Changed To', 'types': ['text', 'number', 'boolean']},
        ]
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        # Get conditions and actions from POST data
        conditions_data = self.request.POST.get('conditions_data')
        actions_data = self.request.POST.get('actions_data')
        
        if conditions
                form.instance.conditions = json.loads(conditions_data)
            except json.JSONDecodeError:
                form.add_error(None, 'Invalid conditions format')
                return self.form_invalid(
                form.instance.actions = json.loads(actions_data)
            except json.JSONDecodeError:
                form.add_error(None, 'Invalid actions format')
                return self.form_invalid(form)
        
        messages.success(self.request, f'Workflow rule "{form.instance.name}" created successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('crm:workflow-rule-detail', kwargs={'pk': self.object.pk})


class WorkflowRuleUpdateView(CRMBaseMixin, UpdateView):
    """Update workflow rule"""
    
    model = WorkflowRule
    template_name = 'crm/workflow/rule_update.html'
    fields = ['name', 'description', 'trigger_type', 'target_model', 'is_active']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rule = self.object
        
        # Parse existing conditions and actions
        try:
            existing_conditions = json.loads(rule.conditions) if rule.conditions else []
        except json.JSONDecodeError:
            existing_conditions = []
        
        try:
            existing_actions = json.loads(rule.actions) if rule.actions else []
        except json.JSONDecodeError:
            existing_actions = []
        
        context.update({
            'trigger_types': WorkflowRule.TRIGGER_TYPES,
            'target_models': WorkflowRule.TARGET_MODELS,
            'existing_conditions': existing_conditions,
            'existing_actions': existing_actions,
            'available_fields': WorkflowRuleCreateView.get_available_fields(self),
            'available_actions': WorkflowRuleCreateView.get_available_actions(self),
            'condition_operators': WorkflowRuleCreateView.get_condition_operators(self),
        })
        
        return context
    
    def form_valid(self, form):
        # Update conditions and actions
        conditions_data = self.request.POST.get('conditions_data')
        actions_data = self.request.POST.gettry:
                form.instance.conditions = json.loads(conditions_data)
            except json.JSONDecodeError:
                form.add_error(None, 'Invalid conditions format')
                return self
            try:
                form.instance.actions = json.loads(actions_data)
            except json.JSONDecodeError:
                form.add_error(None, 'Invalid actions format')
                return self.form_invalid(form)
        
        form.instance.updated_by = self.request.user
        
        messages.success(self.request, f'Workflow rule "{form.instance.name}" updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('crm:workflow-rule-detail', kwargs={'pk': self.object.pk})


class WorkflowExecutionListView(CRMBaseMixin, ListView):
    """Workflow execution history"""
    
    model = WorkflowExecution
    template_name = 'crm/workflow/execution_list.html'
    context_object_name = 'executions'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        queryset = queryset.select_related(
            'rule', 'triggered_by'
        ).order_by('-executed_at')
        
        # Apply filters
        rule_id = self.request.GET.get('rule')
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(executed_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(executed_at__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        executions = self.get_queryset()
        context.update({
            'total_executions': executions.count(),
            'successful_executions': executions.filter(status='SUCCESS').count(),
            'failed_executions': executions.filter(status='FAILED').count(),
            'rules': WorkflowRule.objects.filter(tenant=self.request.tenant, is_active=True),
            'execution_statistics': self.get_execution_statistics(executions),
        })
        
        return context
    
    def get_execution_statistics(self, executions):
        """Get execution statistics"""
        if not executions.exists():
            return {}
        
        # Success rate by rule
        rule_stats = executions.values('rule__name').annotate(
            total=Count('id'),
            success=Count('id', filter=Q(status='SUCCESS')),
            success_rate=Count('id', filter=Q(status='SUCCESS')) * 100.0 / Count('id')
        ).order_by('-total')
        
        # Executions by hour
        hourly_stats = executions.extra({
            'hour': 'extract(hour from executed_at)'
        }).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        return {
            'rule_performance': list(rule_stats),
            'hourly_distribution': list(hourly_stats),
            'avg_execution_time': executions.aggregate(
                avg_time=Avg('execution_time_ms')
            )['avg_time'] or 0,
        }


class IntegrationListView(CRMBaseMixin, ListView):
    """Integration management view"""
    
    model = Integration
    template_name = 'crm/workflow/integration_list.html'
    context_object_name = 'integrations'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        queryset = queryset.annotate(
            webhook_count=Count('webhooks'),
            last_sync=F('last_sync_at')
        ).select_related('created_by')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(service_type__icontains=search)
            )
        
        service_type = self.request.GET.get('service_type')
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        integrations = self.get_queryset()
        context.update({
            'total_integrations': integrations.count(),
            'active_integrations': integrations.filter(is_active=True).count(),
            'service_types': self.get_service_types(),
            'integration_templates': self.get_integration_templates(),
        })
        
        return context
    
    def get_service_types(self):
        """Get available service types"""
        return [
            {'value': 'email', 'name': 'Email Service', 'icon': 'mail'},
            {'value': 'sms', 'name': 'SMS Service', 'icon': 'message-circle'},
            {'value': 'crm', 'name': 'CRM System', 'icon': 'users'},
            {'value': 'accounting', 'name': 'Accounting Software', 'icon': 'dollar-sign'},
            {'value': 'marketing', 'name': 'Marketing Platform', 'icon': 'megaphone'},
            {'value': 'analytics', 'name': 'Analytics Service', 'icon': 'bar-chart'},
            {'value': 'storage', 'name': 'File Storage', 'icon': 'folder'},
            {'value': 'webhook', 'name': 'Webhook Service', 'icon': 'link'},
        ]
    
    def get_integration_templates(self):
        """Get pre-built integration templates"""
        return [
            {
                'name': 'Gmail Integration',
                'service_type': 'email',
                'description': 'Send emails through Gmail',
                'config_template': {
                    'client_id': '',
                    'client_secret': '',
                    'refresh_token': ''
                }
            },
            {
                'name': 'Slack Notifications',
                'service_type': 'webhook',
                'description': 'Send notifications to Slack channels',
                'config_template': {
                    'webhook_url': '',
                    'channel': '#general',
                    'username': 'CRM Bot'
                }
            },
            {
                'name': 'Zapier Integration',
                'service_type': 'webhook',
                'description': 'Connect with Zapier workflows',
                'config_template': {
                    'webhook_url': '',
                    'authentication': 'api_key'
                }
            }
        ]


class IntegrationDetailView(CRMBaseMixin, DetailView):
    """Integration detail view"""
    
    model = Integration
    template_name = 'crm/workflow/integration_detail.html'
    context_object_name = 'integration'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('created_by').prefetch_related(
                'webhooks', 'workflow_rules'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        integration = self.object
        
        context.update({
            'integration_status': self.get_integration_status(integration),
            'webhook_configurations': integration.webhooks.filter(is_active=True),
            'connected_workflows': integration.workflow_rules.filter(is_active=True),
            'sync_history': self.get_sync_history(integration),
            'test_results': self.get_test_results(integration),
            'can_edit': self.can_edit_integration(integration),
        })
        
        return context
    
    def get_integration_status(self, integration):
        """Get integration status and health check"""
        service = IntegrationService()
        
        try:
            status_info = service.check_integration_health(integration)
            return status_info
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'last_checked': timezone.now()
            }
    
    def get_sync_history(self, integration):
        """Get recent sync history"""
        # This would come from a SyncLog model
        return []
    
    def get_test_results(self, integration):
        """Get recent test results"""
        # This would come from integration test logs
        return []
    
    def can_edit_integration(self, integration):
        """Check if user can edit integration"""
        return (
            integration.created_by == self.request.user or
            self.request.user.has_perm('crm.change_integration')
        )


class CustomFieldListView(CRMBaseMixin, ListView):
    """Custom fields management"""
    
    model = CustomField
    template_name = 'crm/workflow/custom_field_list.html'
    context_object_name = 'custom_fields'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(field_name__icontains=search) |
                Q(label__icontains=search)
            )
        
        model_name = self.request.GET.get('model')
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        field_type = self.request.GET.get('field_type')
        if field_type:
            queryset = queryset.filter(field_type=field_type)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.select_related('created_by').order_by('model_name', 'sort_order')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        custom_fields = self.get_queryset()
        context.update({
            'total_fields': custom_fields.count(),
            'active_fields': custom_fields.filter(is_active=True).count(),
            'model_names': CustomField.MODEL_CHOICES,
            'field_types': CustomField.FIELD_TYPE_CHOICES,
            'fields_by_model': self.get_fields_by_model(custom_fields),
        })
        
        return context
    
    def get_fields_by_model(self, custom_fields):
        """Group fields by model"""
        fields_by_model = {}
        
        for field in custom_fields:
            model_name = field.model_name
            if model_name not in fields_by_model:
                fields_by_model[model_name] = []
            fields_by_model[model_name].append(field)
        
        return fields_by_model


# API ViewSets for Workflow & Automation

class WorkflowRuleViewSet(CRMBaseViewSet):
    """Workflow Rule API viewset"""
    
    queryset = WorkflowRule.objects.all()
    serializer_class = WorkflowRuleSerializer
    filterset_class = WorkflowRuleFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'trigger_type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('created_by').annotate(
            execution_count=Count('executions')
        )
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test workflow rule"""
        rule = self.get_object()
        test_data = request.data.get('test_data', {})
        
        try:
            service = WorkflowService()
            result = service.test_workflow_rule(rule, test_data)
            
            return Response({
                'success': True,
                'test_result': result,
                'message': 'Workflow test completed'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Manually execute workflow rule"""
        rule = self.get_object()
        target_id = request.data.get('target_id')
        
        if not target_id:
            return Response(
                {'error': 'Target ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = WorkflowService()
            execution = service.execute_workflow_rule(
                rule=rule,
                target_id=target_id,
                triggered_by=request.user,
                context=request.data.get('context', {})
            )
            
            serializer = WorkflowExecutionSerializer(execution)
            return Response({
                'success': True,
                'execution': serializer.data,
                'message': 'Workflow executed successfully'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """Get workflow rule executions"""
        rule = self.get_object()
        
        executions = rule.executions.select_related('triggered_by').order_by('-executed_at')
        
        # Apply pagination
        page = self.paginate_queryset(executions)
        if page is not None:
            serializer = WorkflowExecutionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = WorkflowExecutionSerializer(executions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get workflow rule templates"""
        templates = [
            {
                'name': 'Lead Assignment',
                'description': 'Automatically assign new leads to users',
                'trigger_type': 'CREATE',
                'target_model': 'LEAD',
                'conditions': [
                    {'field': 'source', 'operator': 'eq', 'value': 'Website'}
                ],
                'actions': [
                    {'type': 'assign_user', 'target': 'round_robin'}
                ]
            },
            {
                'name': 'High Value Opportunity Alert',
                'description': 'Send notification for high value opportunities',
                'trigger_type': 'CREATE',
                'target_model': 'OPPORTUNITY',
                'conditions': [
                    {'field': 'amount', 'operator': 'gt', 'value': '50000'}
                ],
                'actions': [
                    {'type': 'send_email', 'target': 'manager', 'template': 'high_value_opp'}
                ]
            },
            {
                'name': 'Follow-up Reminder',
                'description': 'Create follow-up activities for new leads',
                'trigger_type': 'CREATE',
                'target_model': 'LEAD',
                'conditions': [],
                'actions': [
                    {
                        'type': 'create_activity',
                        'parameters': {
                            'activity_type': 'CALL',
                            'subject': 'Follow up with new lead',
                            'due_days': 1
                        }
                    }
                ]
            }
        ]
        
        return Response(templates)


class WorkflowExecutionViewSet(CRMBaseViewSet):
    """Workflow Execution API viewset"""
    
    queryset = WorkflowExecution.objects.all()
    serializer_class = WorkflowExecutionSerializer
    filterset_class = WorkflowExecutionFilter
    ordering_fields = ['executed_at', 'execution_time_ms']
    ordering = ['-executed_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('rule', 'triggered_by')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get execution statistics"""
        queryset = self.get_queryset()
        
        # Date range filter
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timezone.timedelta(days=days)
        queryset = queryset.filter(executed_at__gte=start_date)
        
        stats = {
            'total_executions': queryset.count(),
            'successful_executions': queryset.filter(status='SUCCESS').count(),
            'failed_executions': queryset.filter(status='FAILED').count(),
            'avg_execution_time': queryset.aggregate(
                avg_time=Avg('execution_time_ms')
            )['avg_time'] or 0,
            'executions_by_rule': list(queryset.values('rule__name').annotate(
                count=Count('id'),
                success_rate=Count('id', filter=Q(status='SUCCESS')) * 100.0 / Count('id')
            ).order_by('-count')),
        }
        
        stats['success_rate'] = (
            stats['successful_executions'] / stats['total_executions'] * 100
            if stats['total_executions'] > 0 else 0
        )
        
        return Response(stats)


class IntegrationViewSet(CRMBaseViewSet):
    """Integration API viewset"""
    
    queryset = Integration.objects.all()
    serializer_class = IntegrationSerializer
    search_fields = ['name', 'description', 'service_type']
    ordering_fields = ['name', 'service_type', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('created_by').annotate(
            webhook_count=Count('webhooks')
        )
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test integration connection"""
        integration = self.get_object()
        
        try:
            service = IntegrationService()
            result = service.test_integration_connection(integration)
            
            return Response({
                'success': True,
                'connection_test': result,
                'message': 'Connection test completed'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Trigger manual sync"""
        integration = self.get_object()
        
        try:
            service = IntegrationService()
            sync_result = service.sync_integration(integration)
            
            # Update last sync time
            integration.last_sync_at = timezone.now()
            integration.save()
            
            return Response({
                'success': True,
                'sync_result': sync_result,
                'message': 'Sync completed successfully'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def available_services(self, request):
        """Get list of available integration services"""
        services = [
            {
                'type': 'email',
                'name': 'Email Services',
                'providers': ['Gmail', 'Outlook', 'SendGrid', 'Mailgun']
            },
            {
                'type': 'sms',
                'name': 'SMS Services',
                'providers': ['Twilio', 'Nexmo', 'AWS SNS']
            },
            {
                'type': 'crm',
                'name': 'CRM Systems',
                'providers': ['Salesforce', 'HubSpot', 'Pipedrive']
            },
            {
                'type': 'accounting',
                'name': 'Accounting Software',
                'providers': ['QuickBooks', 'Xero', 'FreshBooks']
            },
            {
                'type': 'marketing',
                'name': 'Marketing Platforms',
                'providers': ['Mailchimp', 'Constant Contact', 'Campaign Monitor']
            }
        ]
        
        return Response(services)


class WebhookConfigurationViewSet(CRMBaseViewSet):
    """Webhook Configuration API viewset"""
    
    queryset = WebhookConfiguration.objects.all()
    serializer_class = WebhookConfigurationSerializer
    search_fields = ['name', 'url']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('integration', 'created_by')
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test webhook configuration"""
        webhook = self.get_object()
        test_payload = request.data.get('test_payload', {})
        
        try:
            service = IntegrationService()
            result = service.test_webhook(webhook, test_payload)
            
            return Response({
                'success': True,
                'test_result': result,
                'message': 'Webhook test completed'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_test(self, request):
        """Test multiple webhooks"""
        webhook_ids = request.data.get('webhook_ids', [])
        test_payload = request.data.get('test_payload', {})
        
        if not webhook_ids:
            return Response(
                {'error': 'Webhook IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = IntegrationService()
            results = []
            
            webhooks = self.get_queryset().filter(id__in=webhook_ids)
            for webhook in webhooks:
                try:
                    result = service.test_webhook(webhook, test_payload)
                    results.append({
                        'webhook_id': webhook.id,
                        'webhook_name': webhook.name,
                        'success': True,
                        'result': result
                    })
                except Exception as e:
                    results.append({
                        'webhook_id': webhook.id,
                        'webhook_name': webhook.name,
                        'success': False,
                        'error': str(e)
                    })
            
            return Response({
                'success': True,
                'results': results,
                'message': f'Tested {len(results)} webhooks'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CustomFieldViewSet(CRMBaseViewSet):
    """Custom Field API viewset"""
    
    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
    search_fields = ['field_name', 'label']
    ordering_fields = ['label', 'model_name', 'sort_order', 'created_at']
    ordering = ['model_name', 'sort_order']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('created_by')
    
    @action(detail=False, methods=['get'])
    def by_model(self, request):
        """Get custom fields grouped by model"""
        model_name = request.query_params.get('model')
        
        if model_name:
            fields = self.get_queryset().filter(
                model_name=model_name,
                is_active=True
            ).order_by('sort_order')
        else:
            fields = self.get_queryset().filter(is_active=True)
        
        # Group by model
        fields_by_model = {}
        for field in fields:
            model = field.model_name
            if model not in fields_by_model:
                fields_by_model[model] = []
            
            serializer = self.get_serializer(field)
            fields_by_model[model].append(serializer.data)
        
        if model_name:
            return Response(fields_by_model.get(model_name, []))
        
        return Response(fields_by_model)
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder custom fields"""
        field_orders = request.data.get('field_orders', [])
        
        if not field_orders:
            return Response(
                {'error': 'Field orders are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                for order_data in field_orders:
                    field_id = order_data.get('field_id')
                    sort_order = order_data.get('sort_order')
                    
                    CustomField.objects.filter(
                        id=field_id,
                        tenant=request.tenant
                    ).update(sort_order=sort_order)
                
                return Response({
                    'success': True,
                    'message': f'Reordered {len(field_orders)} fields'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )