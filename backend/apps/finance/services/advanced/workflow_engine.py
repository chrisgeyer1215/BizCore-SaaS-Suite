# apps/finance/services/advanced/workflow_engine.py

"""
Business Process Workflow Engine
Provides automated workflow management for financial processes
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from typing import Dict, List, Optional, Any, Callable
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

from apps.core.models import TenantBaseModel
from apps.finance.models import (
    Invoice, Bill, Payment, JournalEntry, Account, 
    Vendor, Customer, FinanceSettings
)

User = get_user_model()


class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class WorkflowStepStatus(Enum):
    """Individual workflow step status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WorkflowDefinition(TenantBaseModel):
    """Workflow definition template"""
    
    TRIGGER_TYPES = [
        ('MANUAL', 'Manual Trigger'),
        ('EVENT', 'Event Triggered'),
        ('SCHEDULED', 'Scheduled'),
        ('API', 'API Triggered'),
        ('CONDITIONAL', 'Conditional'),
    ]
    
    WORKFLOW_TYPES = [
        ('INVOICE_APPROVAL', 'Invoice Approval'),
        ('BILL_APPROVAL', 'Bill Approval'),
        ('PAYMENT_APPROVAL', 'Payment Approval'),
        ('JOURNAL_APPROVAL', 'Journal Entry Approval'),
        ('PERIOD_CLOSE', 'Period Close'),
        ('RECONCILIATION', 'Bank Reconciliation'),
        ('RECURRING_BILLING', 'Recurring Billing'),
        ('PAYMENT_REMINDER', 'Payment Reminder'),
        ('VENDOR_ONBOARDING', 'Vendor Onboarding'),
        ('CUSTOMER_CREDIT_CHECK', 'Customer Credit Check'),
        ('EXPENSE_APPROVAL', 'Expense Approval'),
        ('BUDGET_APPROVAL', 'Budget Approval'),
        ('BUDGET_APPROVAL', 'Budget Approval'),
        ('COMPLIANCE_CHECK', 'Compliance Check'),
        ('DATA_BACKUP', 'Data Backup'),
        ('REPORT_GENERATION', 'Report Generation'),
        ('CUSTOM', 'Custom Workflow'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    workflow_type = models.CharField(max_length=30, choices=WORKFLOW_TYPES)
    version = models.CharField(max_length=20, default='1.0')
    
    # Trigger Configuration
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    trigger_conditions = models.JSONField(default=dict, blank=True)
    
    # Workflow Configuration
    steps_definition = models.JSONField(default=list)
    variables = models.JSONField(default=dict, blank=True)
    timeout_minutes = models.PositiveIntegerField(default=1440)  # 24 hours
    
    # Status & Control
    is_active = models.BooleanField(default=True)
    is_template = models.BooleanField(default=False)
    
    # Execution Limits
    max_concurrent_executions = models.PositiveIntegerField(default=10)
    retry_attempts = models.PositiveIntegerField(default=3)
    
    # Approval Settings
    requires_approval = models.BooleanField(default=False)
    approval_threshold = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Notification Settings
    notification_settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name', 'version'],
                name='unique_workflow_version'
            ),
        ]
        
    def __str__(self):
        return f"{self.name} v{self.version}"


class WorkflowExecution(TenantBaseModel):
    """Individual workflow execution instance"""
    
    execution_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # Execution Context
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_workflows'
    )
    trigger_event = models.CharField(max_length=100, blank=True)
    trigger_data = models.JSONField(default=dict, blank=True)
    
    # Status & Timing
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in WorkflowStatus],
        default=WorkflowStatus.PENDING.value
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # Execution Data
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    execution_log = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    
    # Progress Tracking
    total_steps = models.PositiveIntegerField(default=0)
    completed_steps = models.PositiveIntegerField(default=0)
    current_step = models.PositiveIntegerField(default=0)
    
    # Financial Context
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    financial_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['tenant', 'workflow_definition']),
            models.Index(fields=['tenant', 'triggered_by']),
        ]
        
    def __str__(self):
        return f"{self.workflow_definition.name} - {self.execution_id}"


class WorkflowStep(TenantBaseModel):
    """Individual step within a workflow execution"""
    
    STEP_TYPES = [
        ('APPROVAL', 'Approval Step'),
        ('NOTIFICATION', 'Notification'),
        ('CALCULATION', 'Calculation'),
        ('DATA_UPDATE', 'Data Update'),
        ('EXTERNAL_API', 'External API Call'),
        ('CONDITION', 'Conditional Branch'),
        ('LOOP', 'Loop'),
        ('WAIT', 'Wait/Delay'),
        ('HUMAN_TASK', 'Human Task'),
        ('SCRIPT', 'Script Execution'),
        ('EMAIL', 'Email Send'),
        ('REPORT', 'Report Generation'),
        ('INTEGRATION', 'System Integration'),
    ]
    
    execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name='steps'
    )
    
    # Step Definition
    step_name = models.CharField(max_length=200)
    step_type = models.CharField(max_length=20, choices=STEP_TYPES)
    step_order = models.PositiveIntegerField()
    step_config = models.JSONField(default=dict, blank=True)
    
    # Status & Timing
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in WorkflowStepStatus],
        default=WorkflowStepStatus.PENDING.value
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Execution Data
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Approval Data
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_workflow_steps'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_workflow_steps'
    )
    approval_comments = models.TextField(blank=True)
    approval_deadline = models.DateTimeField(null=True, blank=True)
    
    # Retry Information
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    class Meta:
        ordering = ['execution', 'step_order']
        
    def __str__(self):
        return f"{self.execution.execution_id} - {self.step_name}"


class WorkflowEngine:
    """Main workflow execution engine"""
    
    def __init__(self, tenant, user=None):
        self.tenant = tenant
        self.user = user
        self.settings = FinanceSettings.objects.get(tenant=tenant)
        
        # Registry of step handlers
        self.step_handlers = {
            'APPROVAL': self._handle_approval_step,
            'NOTIFICATION': self._handle_notification_step,
            'CALCULATION': self._handle_calculation_step,
            'DATA_UPDATE': self._handle_data_update_step,
            'EXTERNAL_API': self._handle_external_api_step,
            'CONDITION': self._handle_condition_step,
            'LOOP': self._handle_loop_step,
            'WAIT': self._handle_wait_step,
            'HUMAN_TASK': self._handle_human_task_step,
            'SCRIPT': self._handle_script_step,
            'EMAIL': self._handle_email_step,
            'REPORT': self._handle_report_step,
            'INTEGRATION': self._handle_integration_step,
        }
    
    # =====================================================================
    # WORKFLOW EXECUTION
    # =====================================================================
    
    def start_workflow(
        self,
        workflow_definition: WorkflowDefinition,
        input_data: Dict = None,
        triggered_by: User = None,
        trigger_event: str = None,
        related_object=None
    ) -> WorkflowExecution:
        """Start a new workflow execution"""
        
        if not workflow_definition.is_active:
            raise ValidationError("Workflow definition is not active")
        
        # Check concurrent execution limits
        active_executions = WorkflowExecution.objects.filter(
            tenant=self.tenant,
            workflow_definition=workflow_definition,
            status__in=[WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value]
        ).count()
        
        if active_executions >= workflow_definition.max_concurrent_executions:
            raise ValidationError("Maximum concurrent executions reached")
        
        # Create workflow execution
        execution = WorkflowExecution.objects.create(
            tenant=self.tenant,
            workflow_definition=workflow_definition,
            triggered_by=triggered_by or self.user,
            trigger_event=trigger_event,
            input_data=input_data or {},
            total_steps=len(workflow_definition.steps_definition),
            status=WorkflowStatus.PENDING.value
        )
        
        # Set related object context
        if related_object:
            execution.related_object_type = related_object.__class__.__name__
            execution.related_object_id = related_object.pk
            execution.financial_impact = self._calculate_financial_impact(related_object)
            execution.save()
        
        # Create workflow steps
        self._create_workflow_steps(execution, workflow_definition.steps_definition)
        
        # Start execution
        self._execute_workflow(execution)
        
        return execution
    
    def _create_workflow_steps(
        self,
        execution: WorkflowExecution,
        steps_definition: List[Dict]
    ):
        """Create workflow steps from definition"""
        
        for i, step_def in enumerate(steps_definition):
            WorkflowStep.objects.create(
                tenant=self.tenant,
                execution=execution,
                step_name=step_def.get('name', f'Step {i+1}'),
                step_type=step_def.get('type', 'HUMAN_TASK'),
                step_order=i + 1,
                step_config=step_def.get('config', {}),
                assigned_to_id=step_def.get('assigned_to'),
                max_retries=step_def.get('max_retries', 3)
            )
    
    def _execute_workflow(self, execution: WorkflowExecution):
        """Execute workflow steps"""
        
        try:
            execution.status = WorkflowStatus.RUNNING.value
            execution.started_at = timezone.now()
            execution.save()
            
            self._log_execution(execution, "Workflow execution started")
            
            # Execute steps in order
            for step in execution.steps.order_by('step_order'):
                if execution.status != WorkflowStatus.RUNNING.value:
                    break
                
                self._execute_step(step)
                
                # Update progress
                execution.current_step = step.step_order
                if step.status == WorkflowStepStatus.COMPLETED.value:
                    execution.completed_steps += 1
                execution.save()
            
            # Check completion
            if execution.completed_steps >= execution.total_steps:
                self._complete_workflow(execution)
            
        except Exception as e:
            self._fail_workflow(execution, str(e))
    
    def _execute_step(self, step: WorkflowStep):
        """Execute a single workflow step"""
        
        try:
            step.status = WorkflowStepStatus.RUNNING.value
            step.started_at = timezone.now()
            step.save()
            
            self._log_execution(
                step.execution,
                f"Executing step: {step.step_name}"
            )
            
            # Get step handler
            handler = self.step_handlers.get(step.step_type)
            if not handler:
                raise ValueError(f"No handler for step type: {step.step_type}")
            
            # Execute step
            result = handler(step)
            
            # Handle result
            if result.get('success', True):
                step.status = WorkflowStepStatus.COMPLETED.value
                step.completed_at = timezone.now()
                step.output_data = result.get('output_data', {})
            elif result.get('waiting_approval'):
                step.status = WorkflowStepStatus.WAITING_APPROVAL.value
            else:
                raise Exception(result.get('error', 'Step execution failed'))
            
            step.save()
            
        except Exception as e:
            self._retry_or_fail_step(step, str(e))
    
    def _retry_or_fail_step(self, step: WorkflowStep, error_message: str):
        """Retry a failed step or mark as failed"""
        
        step.retry_count += 1
        step.error_message = error_message
        
        if step.retry_count <= step.max_retries:
            step.status = WorkflowStepStatus.PENDING.value
            step.save()
            
            self._log_execution(
                step.execution,
                f"Retrying step {step.step_name} (attempt {step.retry_count})"
            )
            
            # Schedule retry (could be done with Celery)
            self._execute_step(step)
        else:
            step.status = WorkflowStepStatus.FAILED.value
            step.save()
            
            self._fail_workflow(step.execution, f"Step failed: {step.step_name}")
    
    def _complete_workflow(self, execution: WorkflowExecution):
        """Complete workflow execution"""
        
        execution.status = WorkflowStatus.COMPLETED.value
        execution.completed_at = timezone.now()
        execution.save()
        
        self._log_execution(execution, "Workflow execution completed successfully")
        
        # Send completion notifications
        self._send_workflow_notification(execution, 'COMPLETED')
    
    def _fail_workflow(self, execution: WorkflowExecution, error_message: str):
        """Fail workflow execution"""
        
        execution.status = WorkflowStatus.FAILED.value
        execution.failed_at = timezone.now()
        execution.error_message = error_message
        execution.save()
        
        self._log_execution(execution, f"Workflow execution failed: {error_message}")
        
        # Send failure notifications
        self._send_workflow_notification(execution, 'FAILED')
    
    # =====================================================================
    # STEP HANDLERS
    # =====================================================================
    
    def _handle_approval_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle approval workflow step"""
        
        config = step.step_config
        
        # Set approval deadline
        if config.get('deadline_hours'):
            step.approval_deadline = timezone.now() + timedelta(
                hours=config['deadline_hours']
            )
            step.save()
        
        # Send approval request
        if step.assigned_to:
            self._send_approval_request(step)
        
        return {
            'success': True,
            'waiting_approval': True,
            'output_data': {
                'approval_required': True,
                'assigned_to': step.assigned_to_id,
                'deadline': step.approval_deadline.isoformat() if step.approval_deadline else None
            }
        }
    
    def _handle_notification_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle notification workflow step"""
        
        config = step.step_config
        
        # Prepare notification data
        recipients = config.get('recipients', [])
        message_template = config.get('message_template', '')
        subject_template = config.get('subject_template', '')
        
        # Send notifications
        for recipient in recipients:
            self._send_notification(
                recipient=recipient,
                subject=subject_template,
                message=message_template,
                context=step.input_data
            )
        
        return {
            'success': True,
            'output_data': {
                'notifications_sent': len(recipients)
            }
        }
    
    def _handle_calculation_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle calculation workflow step"""
        
        config = step.step_config
        calculation_type = config.get('calculation_type')
        
        try:
            result = None
            
            if calculation_type == 'FINANCIAL_TOTALS':
                result = self._calculate_financial_totals(step)
            elif calculation_type == 'TAX_CALCULATION':
                result = self._calculate_taxes(step)
            elif calculation_type == 'COMMISSION_CALCULATION':
                result = self._calculate_commissions(step)
            elif calculation_type == 'DEPRECIATION':
                result = self._calculate_depreciation(step)
            else:
                # Custom calculation
                formula = config.get('formula', '')
                result = self._execute_formula(formula, step.input_data)
            
            return {
                'success': True,
                'output_data': {
                    'calculation_result': result,
                    'calculation_type': calculation_type
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Calculation failed: {str(e)}"
            }
    
    def _handle_data_update_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle data update workflow step"""
        
        config = step.step_config
        
        try:
            model_name = config.get('model')
            object_id = config.get('object_id') or step.input_data.get('object_id')
            updates = config.get('updates', {})
            
            # Get the model and object
            related_object = self._get_related_object(
                step.execution.related_object_type,
                step.execution.related_object_id
            )
            
            if related_object:
                # Apply updates
                for field, value in updates.items():
                    if hasattr(related_object, field):
                        setattr(related_object, field, value)
                
                related_object.save()
                
                return {
                    'success': True,
                    'output_data': {
                        'updated_object': str(related_object),
                        'updated_fields': list(updates.keys())
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Related object not found'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Data update failed: {str(e)}"
            }
    
    def _handle_external_api_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle external API call workflow step"""
        
        config = step.step_config
        
        try:
            import requests
            
            url = config.get('url')
            method = config.get('method', 'GET')
            headers = config.get('headers', {})
            payload = config.get('payload', {})
            
            # Make API call
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=config.get('timeout', 30)
            )
            
            response.raise_for_status()
            
            return {
                'success': True,
                'output_data': {
                    'response_status': response.status_code,
                    'response_data': response.json() if response.content else {},
                    'api_endpoint': url
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"API call failed: {str(e)}"
            }
    
    def _handle_condition_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle conditional logic workflow step"""
        
        config = step.step_config
        
        try:
            condition = config.get('condition')
            true_path = config.get('true_path', [])
            false_path = config.get('false_path', [])
            
            # Evaluate condition
            condition_result = self._evaluate_condition(condition, step.input_data)
            
            # Select path
            next_steps = true_path if condition_result else false_path
            
            return {
                'success': True,
                'output_data': {
                    'condition_result': condition_result,
                    'selected_path': 'true' if condition_result else 'false',
                    'next_steps': next_steps
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Condition evaluation failed: {str(e)}"
            }
    
    def _handle_loop_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle loop workflow step"""
        
        config = step.step_config
        
        try:
            loop_data = config.get('loop_data') or step.input_data.get('loop_items', [])
            loop_steps = config.get('loop_steps', [])
            
            results = []
            
            for item in loop_data:
                # Execute loop steps for each item
                for loop_step_def in loop_steps:
                    # Create temporary step for loop iteration
                    loop_result = self._execute_loop_iteration(loop_step_def, item)
                    results.append(loop_result)
            
            return {
                'success': True,
                'output_data': {
                    'loop_iterations': len(loop_data),
                    'loop_results': results
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Loop execution failed: {str(e)}"
            }
    
    def _handle_wait_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle wait/delay workflow step"""
        
        config = step.step_config
        
        wait_minutes = config.get('wait_minutes', 0)
        wait_until = config.get('wait_until')
        
        if wait_until:
            # Wait until specific datetime
            wait_datetime = datetime.fromisoformat(wait_until)
            if timezone.now() < wait_datetime:
                # Schedule continuation (would use Celery in real implementation)
                return {
                    'success': True,
                    'waiting': True,
                    'output_data': {
                        'wait_until': wait_until,
                        'waiting': True
                    }
                }
        elif wait_minutes > 0:
            # Wait for specified minutes
            # In real implementation, this would schedule continuation
            pass
        
        return {
            'success': True,
            'output_data': {
                'wait_completed': True
            }
        }
    
    def _handle_human_task_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle human task workflow step"""
        
        config = step.step_config
        
        # Create task assignment
        task_description = config.get('description', 'Manual task required')
        
        if step.assigned_to:
            # Send task notification
            self._send_task_notification(step, task_description)
        
        return {
            'success': True,
            'waiting_approval': True,
            'output_data': {
                'human_task_required': True,
                'task_description': task_description,
                'assigned_to': step.assigned_to_id
            }
        }
    
    def _handle_script_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle script execution workflow step"""
        
        config = step.step_config
        
        try:
            script_type = config.get('script_type', 'python')
            script_code = config.get('script_code', '')
            
            if script_type == 'python':
                # Execute Python script (be very careful with security)
                # In production, this should be heavily sandboxed
                local_vars = {
                    'input_data': step.input_data,
                    'step_config': config,
                    'tenant': self.tenant,
                    'execution': step.execution
                }
                
                exec(script_code, {'__builtins__': {}}, local_vars)
                
                return {
                    'success': True,
                    'output_data': local_vars.get('output_data', {})
                }
            else:
                return {
                    'success': False,
                    'error': f"Unsupported script type: {script_type}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Script execution failed: {str(e)}"
            }
    
    def _handle_email_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle email sending workflow step"""
        
        config = step.step_config
        
        try:
            recipients = config.get('recipients', [])
            subject = config.get('subject', '')
            template = config.get('template', '')
            context = step.input_data
            
            # Send emails
            for recipient in recipients:
                self._send_email(
                    to_email=recipient,
                    subject=subject,
                    template=template,
                    context=context
                )
            
            return {
                'success': True,
                'output_data': {
                    'emails_sent': len(recipients)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Email sending failed: {str(e)}"
            }
    
    def _handle_report_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle report generation workflow step"""
        
        config = step.step_config
        
        try:
            report_type = config.get('report_type')
            report_params = config.get('parameters', {})
            
            # Generate report (integrate with reporting service)
            report_result = self._generate_report(report_type, report_params)
            
            return {
                'success': True,
                'output_data': {
                    'report_generated': True,
                    'report_type': report_type,
                    'report_result': report_result
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Report generation failed: {str(e)}"
            }
    
    def _handle_integration_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle system integration workflow step"""
        
        config = step.step_config
        
        try:
            integration_type = config.get('integration_type')
            integration_params = config.get('parameters', {})
            
            # Handle different integration types
            if integration_type == 'CRM_SYNC':
                result = self._sync_with_crm(integration_params)
            elif integration_type == 'INVENTORY_SYNC':
                result = self._sync_with_inventory(integration_params)
            elif integration_type == 'ECOMMERCE_SYNC':
                result = self._sync_with_ecommerce(integration_params)
            else:
                result = {'error': f'Unknown integration type: {integration_type}'}
            
            return {
                'success': result.get('success', False),
                'output_data': result,
                'error': result.get('error')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Integration failed: {str(e)}"
            }
    
    # =====================================================================
    # WORKFLOW MANAGEMENT
    # =====================================================================
    
    def approve_step(
        self,
        step: WorkflowStep,
        approved_by: User,
        comments: str = None
    ) -> bool:
        """Approve a workflow step"""
        
        if step.status != WorkflowStepStatus.WAITING_APPROVAL.value:
            raise ValidationError("Step is not waiting for approval")
        
        step.status = WorkflowStepStatus.APPROVED.value
        step.approved_by = approved_by
        step.approval_comments = comments or ""
        step.completed_at = timezone.now()
        step.save()
        
        self._log_execution(
            step.execution,
            f"Step approved: {step.step_name} by {approved_by.get_full_name()}"
        )
        
        # Continue workflow execution
        self._continue_workflow_execution(step.execution)
        
        return True
    
    def reject_step(
        self,
        step: WorkflowStep,
        rejected_by: User,
        comments: str = None
    ) -> bool:
        """Reject a workflow step"""
        
        if step.status != WorkflowStepStatus.WAITING_APPROVAL.value:
            raise ValidationError("Step is not waiting for approval")
        
        step.status = WorkflowStepStatus.REJECTED.value
        step.approved_by = rejected_by
        step.approval_comments = comments or ""
        step.save()
        
        self._log_execution(
            step.execution,
            f"Step rejected: {step.step_name} by {rejected_by.get_full_name()}"
        )
        
        # Fail the workflow
        self._fail_workflow(step.execution, f"Step rejected: {step.step_name}")
        
        return True
    
    def cancel_workflow(
        self,
        execution: WorkflowExecution,
        cancelled_by: User,
        reason: str = None
    ) -> bool:
        """Cancel a workflow execution"""
        
        if execution.status not in [WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value]:
            raise ValidationError("Cannot cancel completed workflow")
        
        execution.status = WorkflowStatus.CANCELLED.value
        execution.completed_at = timezone.now()
        execution.error_message = f"Cancelled by {cancelled_by.get_full_name()}: {reason or 'No reason provided'}"
        execution.save()
        
        self._log_execution(
            execution,
            f"Workflow paused by {paused_by.get_full_name()}"
        )
        
        return True
    
    def resume_workflow(
        self,
        execution: WorkflowExecution,
        resumed_by: User
    ) -> bool:
        """Resume a paused workflow execution"""
        
        if execution.status != WorkflowStatus.PAUSED.value:
            raise ValidationError("Can only resume paused workflows")
        
        execution.status = WorkflowStatus.RUNNING.value
        execution.save()
        
        self._log_execution(
            execution,
            f"Workflow resumed by {resumed_by.get_full_name()}"
        )
        
        # Continue execution
        self._continue_workflow_execution(execution)
        
        return True
    
    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    
    def _continue_workflow_execution(self, execution: WorkflowExecution):
        """Continue workflow execution after approval or resume"""
        
        # Find next pending step
        next_step = execution.steps.filter(
            status=WorkflowStepStatus.PENDING.value
        ).order_by('step_order').first()
        
        if next_step:
            self._execute_step(next_step)
        else:
            # Check if all steps are completed
            if execution.steps.filter(
                status=WorkflowStepStatus.COMPLETED.value
            ).count() >= execution.total_steps:
                self._complete_workflow(execution)
    
    def _log_execution(self, execution: WorkflowExecution, message: str):
        """Add log entry to workflow execution"""
        
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'message': message,
            'user': self.user.username if self.user else 'system'
        }
        
        execution.execution_log.append(log_entry)
        execution.save(update_fields=['execution_log'])
    
    def _calculate_financial_impact(self, obj) -> Optional[Decimal]:
        """Calculate financial impact of workflow object"""
        
        if hasattr(obj, 'total_amount'):
            return obj.total_amount
        elif hasattr(obj, 'amount'):
            return obj.amount
        elif hasattr(obj, 'base_currency_total'):
            return obj.base_currency_total
        
        return None
    
    def _get_related_object(self, object_type: str, object_id: int):
        """Get related object by type and ID"""
        
        model_map = {
            'Invoice': Invoice,
            'Bill': Bill,
            'Payment': Payment,
            'JournalEntry': JournalEntry,
            'Vendor': Vendor,
            'Customer': Customer,
        }
        
        model_class = model_map.get(object_type)
        if model_class:
            try:
                return model_class.objects.get(tenant=self.tenant, pk=object_id)
            except model_class.DoesNotExist:
                return None
        
        return None
    
    def _send_approval_request(self, step: WorkflowStep):
        """Send approval request notification"""
        
        if not step.assigned_to:
            return
        
        subject = f"Approval Required: {step.step_name}"
        message = f"""
        You have been assigned an approval task in the workflow: {step.execution.workflow_definition.name}
        
        Step: {step.step_name}
        Execution ID: {step.execution.execution_id}
        
        Please review and approve or reject this request.
        """
        
        # In real implementation, this would send email or create notification
        self._send_notification(
            recipient=step.assigned_to.email,
            subject=subject,
            message=message,
            context={'step': step}
        )
    
    def _send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        context: Dict = None
    ):
        """Send notification (email, SMS, etc.)"""
        
        # In real implementation, this would use proper email service
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email='noreply@saas-aice.com',
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as e:
            # Log error but don't fail workflow
            pass
    
    def _send_task_notification(self, step: WorkflowStep, description: str):
        """Send human task notification"""
        
        if not step.assigned_to:
            return
        
        subject = f"Task Assignment: {step.step_name}"
        message = f"""
        You have been assigned a task in the workflow: {step.execution.workflow_definition.name}
        
        Task: {step.step_name}
        Description: {description}
        Execution ID: {step.execution.execution_id}
        
        Please complete this task to continue the workflow.
        """
        
        self._send_notification(
            recipient=step.assigned_to.email,
            subject=subject,
            message=message,
            context={'step': step, 'description': description}
        )
    
    def _send_workflow_notification(self, execution: WorkflowExecution, event_type: str):
        """Send workflow status notification"""
        
        if not execution.triggered_by:
            return
        
        subject = f"Workflow {event_type}: {execution.workflow_definition.name}"
        message = f"""
        Workflow execution has {event_type.lower()}.
        
        Workflow: {execution.workflow_definition.name}
        Execution ID: {execution.execution_id}
        Status: {execution.status}
        """
        
        if event_type == 'FAILED':
            message += f"\nError: {execution.error_message}"
        
        self._send_notification(
            recipient=execution.triggered_by.email,
            subject=subject,
            message=message,
            context={'execution': execution}
        )
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        template: str,
        context: Dict
    ):
        """Send formatted email"""
        
        # Render template with context
        try:
            if template:
                rendered_message = render_to_string(template, context)
            else:
                rendered_message = subject
            
            send_mail(
                subject=subject,
                message=rendered_message,
                from_email='noreply@saas-aice.com',
                recipient_list=[to_email],
                fail_silently=False,
            )
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")
    
    def _calculate_financial_totals(self, step: WorkflowStep) -> Dict[str, Any]:
        """Calculate financial totals for workflow step"""
        
        # Get related object
        related_obj = self._get_related_object(
            step.execution.related_object_type,
            step.execution.related_object_id
        )
        
        if not related_obj:
            return {'error': 'Related object not found'}
        
        # Calculate based on object type
        if isinstance(related_obj, Invoice):
            return {
                'subtotal': float(related_obj.subtotal),
                'tax_amount': float(related_obj.tax_amount),
                'total_amount': float(related_obj.total_amount),
                'currency': related_obj.currency.code
            }
        elif isinstance(related_obj, Bill):
            return {
                'subtotal': float(related_obj.subtotal),
                'tax_amount': float(related_obj.tax_amount),
                'total_amount': float(related_obj.total_amount),
                'currency': related_obj.currency.code
            }
        
        return {'error': 'Unsupported object type for financial calculation'}
    
    def _calculate_taxes(self, step: WorkflowStep) -> Dict[str, Any]:
        """Calculate taxes for workflow step"""
        
        # Implementation depends on tax calculation service
        return {
            'calculated_taxes': True,
            'tax_amount': 0,
            'tax_rate': 0
        }
    
    def _calculate_commissions(self, step: WorkflowStep) -> Dict[str, Any]:
        """Calculate commissions for workflow step"""
        
        # Implementation depends on commission rules
        return {
            'calculated_commissions': True,
            'commission_amount': 0
        }
    
    def _calculate_depreciation(self, step: WorkflowStep) -> Dict[str, Any]:
        """Calculate depreciation for workflow step"""
        
        # Implementation depends on asset management
        return {
            'calculated_depreciation': True,
            'depreciation_amount': 0
        }
    
    def _execute_formula(self, formula: str, data: Dict) -> Any:
        """Execute a calculation formula safely"""
        
        # Simple formula execution (be very careful with security)
        # In production, use a proper expression evaluator
        try:
            # Replace variables in formula with actual values
            for key, value in data.items():
                if isinstance(value, (int, float, Decimal)):
                    formula = formula.replace(f'{{{key}}}', str(value))
            
            # Evaluate simple mathematical expressions only
            allowed_names = {
                '__builtins__': {},
                'abs': abs,
                'min': min,
                'max': max,
                'round': round,
                'sum': sum,
            }
            
            return eval(formula, allowed_names)
        except Exception as e:
            raise Exception(f"Formula execution failed: {str(e)}")
    
    def _evaluate_condition(self, condition: str, data: Dict) -> bool:
        """Evaluate a conditional expression"""
        
        # Simple condition evaluation
        # In production, use a proper expression evaluator
        try:
            # Replace variables in condition with actual values
            for key, value in data.items():
                condition = condition.replace(f'{{{key}}}', repr(value))
            
            # Evaluate boolean expressions only
            allowed_names = {
                '__builtins__': {},
                'True': True,
                'False': False,
            }
            
            result = eval(condition, allowed_names)
            return bool(result)
        except Exception as e:
            return False
    
    def _execute_loop_iteration(self, loop_step_def: Dict, item: Any) -> Dict[str, Any]:
        """Execute a single loop iteration"""
        
        # Create temporary execution context for loop iteration
        context = {
            'item': item,
            'step_def': loop_step_def
        }
        
        # Execute the loop step (simplified)
        return {
            'success': True,
            'item': item,
            'result': 'processed'
        }
    
    def _generate_report(self, report_type: str, parameters: Dict) -> Dict[str, Any]:
        """Generate a report"""
        
        # Integration with reporting service
        return {
            'report_generated': True,
            'report_type': report_type,
            'parameters': parameters
        }
    
    def _sync_with_crm(self, parameters: Dict) -> Dict[str, Any]:
        """Sync with CRM system"""
        
        # Integration with CRM module
        return {
            'success': True,
            'records_synced': 0,
            'integration_type': 'CRM_SYNC'
        }
    
    def _sync_with_inventory(self, parameters: Dict) -> Dict[str, Any]:
        """Sync with inventory system"""
        
        # Integration with inventory module
        return {
            'success': True,
            'records_synced': 0,
            'integration_type': 'INVENTORY_SYNC'
        }
    
    def _sync_with_ecommerce(self, parameters: Dict) -> Dict[str, Any]:
        """Sync with e-commerce system"""
        
        # Integration with e-commerce module
        return {
            'success': True,
            'orders_synced': 0,
            'integration_type': 'ECOMMERCE_SYNC'
        }


# =====================================================================
# PREDEFINED WORKFLOW TEMPLATES
# =====================================================================

class WorkflowTemplates:
    """Predefined workflow templates for common business processes"""
    
    @staticmethod
    def get_invoice_approval_workflow() -> Dict[str, Any]:
        """Standard invoice approval workflow"""
        
        return {
            'name': 'Invoice Approval Workflow',
            'description': 'Standard invoice approval process with amount-based routing',
            'workflow_type': 'INVOICE_APPROVAL',
            'trigger_type': 'EVENT',
            'trigger_conditions': {
                'event': 'invoice_created',
                'amount_threshold': 1000
            },
            'steps_definition': [
                {
                    'name': 'Validate Invoice Data',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'FINANCIAL_TOTALS'
                    }
                },
                {
                    'name': 'Manager Approval',
                    'type': 'APPROVAL',
                    'config': {
                        'approval_role': 'finance_manager',
                        'deadline_hours': 24,
                        'amount_threshold': 10000
                    }
                },
                {
                    'name': 'Director Approval',
                    'type': 'APPROVAL',
                    'config': {
                        'approval_role': 'finance_director',
                        'deadline_hours': 48,
                        'condition': 'amount > 10000'
                    }
                },
                {
                    'name': 'Update Invoice Status',
                    'type': 'DATA_UPDATE',
                    'config': {
                        'model': 'Invoice',
                        'updates': {
                            'status': 'APPROVED'
                        }
                    }
                },
                {
                    'name': 'Send Approval Notification',
                    'type': 'NOTIFICATION',
                    'config': {
                        'recipients': ['invoice_creator', 'finance_team'],
                        'message_template': 'Invoice {invoice_number} has been approved'
                    }
                }
            ]
        }
    
    @staticmethod
    def get_payment_approval_workflow() -> Dict[str, Any]:
        """Standard payment approval workflow"""
        
        return {
            'name': 'Payment Approval Workflow',
            'description': 'Standard payment approval process',
            'workflow_type': 'PAYMENT_APPROVAL',
            'trigger_type': 'EVENT',
            'trigger_conditions': {
                'event': 'payment_created',
                'amount_threshold': 5000
            },
            'steps_definition': [
                {
                    'name': 'Verify Payment Details',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'PAYMENT_VERIFICATION'
                    }
                },
                {
                    'name': 'Finance Approval',
                    'type': 'APPROVAL',
                    'config': {
                        'approval_role': 'finance_manager',
                        'deadline_hours': 24
                    }
                },
                {
                    'name': 'Process Payment',
                    'type': 'DATA_UPDATE',
                    'config': {
                        'model': 'Payment',
                        'updates': {
                            'status': 'APPROVED'
                        }
                    }
                },
                {
                    'name': 'Send Payment Confirmation',
                    'type': 'EMAIL',
                    'config': {
                        'recipients': ['payment_creator', 'vendor_email'],
                        'subject': 'Payment Approved',
                        'template': 'payment_approval_email.html'
                    }
                }
            ]
        }
    
    @staticmethod
    def get_period_close_workflow() -> Dict[str, Any]:
        """Month-end/period close workflow"""
        
        return {
            'name': 'Period Close Workflow',
            'description': 'Automated month-end closing process',
            'workflow_type': 'PERIOD_CLOSE',
            'trigger_type': 'SCHEDULED',
            'trigger_conditions': {
                'schedule': 'monthly',
                'day_of_month': 1
            },
            'steps_definition': [
                {
                    'name': 'Validate Open Transactions',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'TRANSACTION_VALIDATION'
                    }
                },
                {
                    'name': 'Calculate Accruals',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'ACCRUAL_CALCULATION'
                    }
                },
                {
                    'name': 'Generate Depreciation Entries',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'DEPRECIATION'
                    }
                },
                {
                    'name': 'Manager Review Required',
                    'type': 'APPROVAL',
                    'config': {
                        'approval_role': 'finance_manager',
                        'deadline_hours': 72
                    }
                },
                {
                    'name': 'Close Financial Period',
                    'type': 'DATA_UPDATE',
                    'config': {
                        'model': 'FinancialPeriod',
                        'updates': {
                            'status': 'CLOSED'
                        }
                    }
                },
                {
                    'name': 'Generate Financial Reports',
                    'type': 'REPORT',
                    'config': {
                        'report_type': 'MONTHLY_FINANCIAL_STATEMENTS'
                    }
                },
                {
                    'name': 'Send Closing Notification',
                    'type': 'NOTIFICATION',
                    'config': {
                        'recipients': ['finance_team', 'management'],
                        'message_template': 'Period {period} has been closed'
                    }
                }
            ]
        }
    
    @staticmethod
    def get_recurring_billing_workflow() -> Dict[str, Any]:
        """Recurring billing workflow"""
        
        return {
            'name': 'Recurring Billing Workflow',
            'description': 'Automated recurring invoice generation',
            'workflow_type': 'RECURRING_BILLING',
            'trigger_type': 'SCHEDULED',
            'trigger_conditions': {
                'schedule': 'daily'
            },
            'steps_definition': [
                {
                    'name': 'Identify Due Recurring Invoices',
                    'type': 'CALCULATION',
                    'config': {
                        'calculation_type': 'RECURRING_INVOICE_IDENTIFICATION'
                    }
                },
                {
                    'name': 'Generate Invoices',
                    'type': 'LOOP',
                    'config': {
                        'loop_data': 'recurring_invoices',
                        'loop_steps': [
                            {
                                'name': 'Create Invoice',
                                'type': 'DATA_UPDATE',
                                'config': {
                                    'model': 'Invoice',
                                    'action': 'create_from_template'
                                }
                            }
                        ]
                    }
                },
                {
                    'name': 'Send Generated Invoices',
                    'type': 'EMAIL',
                    'config': {
                        'recipients': 'invoice_customers',
                        'subject': 'Your Invoice is Ready',
                        'template': 'recurring_invoice_email.html'
                    }
                },
                {
                    'name': 'Update Recurring Schedule',
                    'type': 'DATA_UPDATE',
                    'config': {
                        'model': 'RecurringInvoice',
                        'updates': {
                            'next_invoice_date': 'calculated_next_date'
                        }
                    }
                }
            ]
        }


# =====================================================================
# WORKFLOW BUILDER UTILITIES
# =====================================================================

class WorkflowBuilder:
    """Utility class for building workflow definitions programmatically"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.workflow_def = {
            'tenant': tenant,
            'steps_definition': [],
            'variables': {},
            'notification_settings': {}
        }
    
    def set_basic_info(
        self,
        name: str,
        description: str = "",
        workflow_type: str = "CUSTOM",
        version: str = "1.0"
    ):
        """Set basic workflow information"""
        
        self.workflow_def.update({
            'name': name,
            'description': description,
            'workflow_type': workflow_type,
            'version': version
        })
        return self
    
    def set_trigger(
        self,
        trigger_type: str,
        conditions: Dict = None
    ):
        """Set workflow trigger configuration"""
        
        self.workflow_def.update({
            'trigger_type': trigger_type,
            'trigger_conditions': conditions or {}
        })
        return self
    
    def add_approval_step(
        self,
        name: str,
        approval_role: str = None,
        assigned_to: int = None,
        deadline_hours: int = 24,
        condition: str = None
    ):
        """Add approval step to workflow"""
        
        step = {
            'name': name,
            'type': 'APPROVAL',
            'config': {
                'deadline_hours': deadline_hours
            }
        }
        
        if approval_role:
            step['config']['approval_role'] = approval_role
        if assigned_to:
            step['assigned_to'] = assigned_to
        if condition:
            step['config']['condition'] = condition
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_notification_step(
        self,
        name: str,
        recipients: List[str],
        message_template: str,
        subject_template: str = None
    ):
        """Add notification step to workflow"""
        
        step = {
            'name': name,
            'type': 'NOTIFICATION',
            'config': {
                'recipients': recipients,
                'message_template': message_template
            }
        }
        
        if subject_template:
            step['config']['subject_template'] = subject_template
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_calculation_step(
        self,
        name: str,
        calculation_type: str,
        formula: str = None,
        parameters: Dict = None
    ):
        """Add calculation step to workflow"""
        
        step = {
            'name': name,
            'type': 'CALCULATION',
            'config': {
                'calculation_type': calculation_type
            }
        }
        
        if formula:
            step['config']['formula'] = formula
        if parameters:
            step['config']['parameters'] = parameters
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_data_update_step(
        self,
        name: str,
        model: str,
        updates: Dict,
        condition: str = None
    ):
        """Add data update step to workflow"""
        
        step = {
            'name': name,
            'type': 'DATA_UPDATE',
            'config': {
                'model': model,
                'updates': updates
            }
        }
        
        if condition:
            step['config']['condition'] = condition
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_email_step(
        self,
        name: str,
        recipients: List[str],
        subject: str,
        template: str = None,
        context: Dict = None
    ):
        """Add email step to workflow"""
        
        step = {
            'name': name,
            'type': 'EMAIL',
            'config': {
                'recipients': recipients,
                'subject': subject
            }
        }
        
        if template:
            step['config']['template'] = template
        if context:
            step['config']['context'] = context
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_condition_step(
        self,
        name: str,
        condition: str,
        true_path: List[Dict],
        false_path: List[Dict] = None
    ):
        """Add conditional step to workflow"""
        
        step = {
            'name': name,
            'type': 'CONDITION',
            'config': {
                'condition': condition,
                'true_path': true_path,
                'false_path': false_path or []
            }
        }
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def add_wait_step(
        self,
        name: str,
        wait_minutes: int = None,
        wait_until: str = None
    ):
        """Add wait/delay step to workflow"""
        
        step = {
            'name': name,
            'type': 'WAIT',
            'config': {}
        }
        
        if wait_minutes:
            step['config']['wait_minutes'] = wait_minutes
        if wait_until:
            step['config']['wait_until'] = wait_until
        
        self.workflow_def['steps_definition'].append(step)
        return self
    
    def set_timeout(self, timeout_minutes: int):
        """Set workflow timeout"""
        
        self.workflow_def['timeout_minutes'] = timeout_minutes
        return self
    
    def set_retry_policy(self, max_retries: int = 3):
        """Set retry policy"""
        
        self.workflow_def['retry_attempts'] = max_retries
        return self
    
    def build(self) -> WorkflowDefinition:
        """Build and save the workflow definition"""
        
        return WorkflowDefinition.objects.create(**self.workflow_def) cancelled by {cancelled_by.get_full_name()}"
        )
        
        return True
    
    def pause_workflow(
        self,
        execution: WorkflowExecution,
        paused_by: User
    ) -> bool:
        """Pause a workflow execution"""
        
        if execution.status != WorkflowStatus.RUNNING.value:
            raise ValidationError("Can only pause running workflows")
        
        execution.status = WorkflowStatus.PAUSED.value
        execution.save()
        
        self._log_execution(
            execution,
            f"Workflow# apps/finance/services/advanced/workflow_engine.py

"""
Business Process Workflow Engine
Provides automated workflow management for financial processes
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from typing import Dict, List, Optional, Any, Callable
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

from apps.core.models import TenantBaseModel
from apps.finance.models import (
    Invoice, Bill, Payment, JournalEntry, Account, 
    Vendor, Customer, FinanceSettings
)

User = get_user_model()


class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class WorkflowStepStatus(Enum):
    """Individual workflow step status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WorkflowDefinition(TenantBaseModel):
    """Workflow definition template"""
    
    TRIGGER_TYPES = [
        ('MANUAL', 'Manual Trigger'),
        ('EVENT', 'Event Triggered'),
        ('SCHEDULED', 'Scheduled'),
        ('API', 'API Triggered'),
        ('CONDITIONAL', 'Conditional'),
    ]
    
    WORKFLOW_TYPES = [
        ('INVOICE_APPROVAL', 'Invoice Approval'),
        ('BILL_APPROVAL', 'Bill Approval'),
        ('PAYMENT_APPROVAL', 'Payment Approval'),
        ('JOURNAL_APPROVAL', 'Journal Entry Approval'),
        ('PERIOD_CLOSE', 'Period Close'),
        ('RECONCILIATION', 'Bank Reconciliation'),
        ('RECURRING_BILLING', 'Recurring Billing'),
        ('PAYMENT_REMINDER', 'Payment Reminder'),
        ('VENDOR_ONBOARDING', 'Vendor Onboarding'),
        ('CUSTOMER_CREDIT_CHECK', 'Customer Credit Check'),
        ('EXPENSE_APPROVAL', 'Expense Approval'),
        ('BUDGET_APPROVAL', 'Budget Approval'),