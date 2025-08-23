"""
Finance Workflow Integration Service

Provides comprehensive workflow automation integration between finance and workflow engine,
enabling intelligent automation of financial processes and business rules.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, Count, Avg
from django.contrib.auth import get_user_model

from apps.core.models import TenantBaseModel
from apps.finance.models.journal import JournalEntry
from apps.finance.models.invoicing import Invoice, InvoiceItem
from apps.finance.models.payments import Payment, PaymentAllocation
from apps.finance.models.base import Account

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class WorkflowTriggerData:
    """Represents data for workflow triggers."""
    object_type: str
    object_id: int
    action: str
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    triggered_by: Optional[User] = None
    timestamp: datetime = field(default_factory=timezone.now)


@dataclass
class WorkflowActionResult:
    """Represents result of workflow action execution."""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class FinanceWorkflowIntegrationService:
    """
    Comprehensive workflow integration service for finance module.
    
    Features:
    - Automated journal entry creation based on business rules
    - Invoice approval workflows
    - Payment processing automation
    - Financial threshold alerts
    - Reconciliation workflows
    - Budget variance notifications
    - Financial reporting automation
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = logging.getLogger(f'{__name__}.{tenant.schema_name}')
    
    # ==================== Workflow Trigger Management ====================
    
    def register_invoice_workflows(self) -> Dict[str, Any]:
        """Register invoice-related workflow triggers."""
        try:
            from apps.crm.models.workflow import WorkflowRule
            
            workflows_created = []
            
            # Invoice Creation Workflow
            invoice_creation_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Invoice Creation Automation",
                description="Automate actions when invoices are created",
                trigger_type="CREATE",
                trigger_object="Invoice",
                trigger_conditions={
                    "status": ["DRAFT", "SENT"],
                    "amount__gte": 1000
                },
                actions=[
                    {
                        "type": "SEND_EMAIL",
                        "template": "invoice_created_notification",
                        "recipients": ["finance_team@company.com"],
                        "data": {
                            "invoice_number": "{{object.number}}",
                            "amount": "{{object.total_amount}}",
                            "customer": "{{object.customer.name}}"
                        }
                    },
                    {
                        "type": "CREATE_TASK",
                        "title": "Review High-Value Invoice",
                        "description": "Invoice {{object.number}} requires review due to high amount",
                        "assigned_to": "finance_manager",
                        "due_date": "+2 days"
                    }
                ],
                is_active=True
            )
            workflows_created.append(invoice_creation_rule.id)
            
            # Invoice Payment Workflow
            payment_received_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Invoice Payment Processing",
                description="Process actions when invoice payments are received",
                trigger_type="FIELD_CHANGE",
                trigger_object="Invoice",
                trigger_conditions={
                    "field": "status",
                    "from_value": ["SENT", "OVERDUE"],
                    "to_value": "PAID"
                },
                actions=[
                    {
                        "type": "UPDATE_FIELD",
                        "target": "customer",
                        "field": "credit_rating",
                        "value": "+10",
                        "operation": "increment"
                    },
                    {
                        "type": "SEND_EMAIL",
                        "template": "payment_received_confirmation",
                        "recipients": ["{{object.customer.email}}"],
                        "data": {
                            "invoice_number": "{{object.number}}",
                            "amount_paid": "{{object.total_amount}}",
                            "payment_date": "{{now}}"
                        }
                    }
                ],
                is_active=True
            )
            workflows_created.append(payment_received_rule.id)
            
            # Overdue Invoice Workflow
            overdue_workflow = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Overdue Invoice Automation",
                description="Handle overdue invoices with automated follow-up",
                trigger_type="TIME_BASED",
                trigger_object="Invoice",
                trigger_conditions={
                    "status": "SENT",
                    "due_date__lt": "today",
                    "days_overdue": {"gte": 1}
                },
                actions=[
                    {
                        "type": "UPDATE_FIELD",
                        "field": "status",
                        "value": "OVERDUE"
                    },
                    {
                        "type": "SEND_EMAIL",
                        "template": "overdue_invoice_reminder",
                        "recipients": ["{{object.customer.email}}"],
                        "data": {
                            "invoice_number": "{{object.number}}",
                            "amount_due": "{{object.total_amount}}",
                            "days_overdue": "{{object.days_overdue}}"
                        }
                    },
                    {
                        "type": "CREATE_TASK",
                        "title": "Follow Up Overdue Invoice",
                        "description": "Invoice {{object.number}} is {{object.days_overdue}} days overdue",
                        "assigned_to": "collections_team",
                        "priority": "HIGH"
                    }
                ],
                schedule_type="RECURRING",
                recurrence_pattern={
                    "frequency": "daily",
                    "time": "09:00"
                },
                is_active=True
            )
            workflows_created.append(overdue_workflow.id)
            
            return {
                "success": True,
                "workflows_created": workflows_created,
                "message": f"Created {len(workflows_created)} invoice workflows"
            }
            
        except Exception as e:
            self.logger.error(f"Error registering invoice workflows: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def register_payment_workflows(self) -> Dict[str, Any]:
        """Register payment-related workflow triggers."""
        try:
            from apps.crm.models.workflow import WorkflowRule
            
            workflows_created = []
            
            # Large Payment Approval Workflow
            large_payment_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Large Payment Approval",
                description="Require approval for large payments",
                trigger_type="CREATE",
                trigger_object="Payment",
                trigger_conditions={
                    "amount__gte": 10000,
                    "status": "PENDING"
                },
                actions=[
                    {
                        "type": "UPDATE_FIELD",
                        "field": "status",
                        "value": "PENDING_APPROVAL"
                    },
                    {
                        "type": "CREATE_TASK",
                        "title": "Approve Large Payment",
                        "description": "Payment of {{object.amount}} requires approval",
                        "assigned_to": "finance_director",
                        "priority": "HIGH",
                        "due_date": "+1 day"
                    },
                    {
                        "type": "SEND_EMAIL",
                        "template": "payment_approval_required",
                        "recipients": ["finance_director@company.com"],
                        "data": {
                            "payment_id": "{{object.id}}",
                            "amount": "{{object.amount}}",
                            "vendor": "{{object.vendor.name}}"
                        }
                    }
                ],
                is_active=True
            )
            workflows_created.append(large_payment_rule.id)
            
            # Failed Payment Workflow
            failed_payment_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Failed Payment Processing",
                description="Handle failed payment attempts",
                trigger_type="FIELD_CHANGE",
                trigger_object="Payment",
                trigger_conditions={
                    "field": "status",
                    "to_value": "FAILED"
                },
                actions=[
                    {
                        "type": "SEND_EMAIL",
                        "template": "payment_failed_notification",
                        "recipients": ["finance_team@company.com"],
                        "data": {
                            "payment_id": "{{object.id}}",
                            "amount": "{{object.amount}}",
                            "failure_reason": "{{object.failure_reason}}"
                        }
                    },
                    {
                        "type": "CREATE_TASK",
                        "title": "Investigate Failed Payment",
                        "description": "Payment {{object.id}} failed: {{object.failure_reason}}",
                        "assigned_to": "finance_team",
                        "priority": "HIGH"
                    },
                    {
                        "type": "WEBHOOK",
                        "url": "/api/finance/payments/retry-schedule",
                        "method": "POST",
                        "data": {
                            "payment_id": "{{object.id}}",
                            "retry_count": "{{object.retry_count|add:1}}"
                        }
                    }
                ],
                is_active=True
            )
            workflows_created.append(failed_payment_rule.id)
            
            return {
                "success": True,
                "workflows_created": workflows_created,
                "message": f"Created {len(workflows_created)} payment workflows"
            }
            
        except Exception as e:
            self.logger.error(f"Error registering payment workflows: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def register_accounting_workflows(self) -> Dict[str, Any]:
        """Register accounting and journal entry workflows."""
        try:
            from apps.crm.models.workflow import WorkflowRule
            
            workflows_created = []
            
            # Journal Entry Validation Workflow
            journal_validation_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Journal Entry Validation",
                description="Validate journal entries before posting",
                trigger_type="FIELD_CHANGE",
                trigger_object="JournalEntry",
                trigger_conditions={
                    "field": "status",
                    "to_value": "PENDING_APPROVAL"
                },
                actions=[
                    {
                        "type": "WEBHOOK",
                        "url": "/api/finance/journal/validate",
                        "method": "POST",
                        "data": {
                            "journal_entry_id": "{{object.id}}",
                            "validation_type": "automated"
                        }
                    }
                ],
                is_active=True
            )
            workflows_created.append(journal_validation_rule.id)
            
            # Month-End Close Workflow
            month_end_rule = WorkflowRule.objects.create(
                tenant=self.tenant,
                name="Month-End Close Automation",
                description="Automate month-end closing procedures",
                trigger_type="TIME_BASED",
                trigger_object="JournalEntry",
                trigger_conditions={
                    "date__month": "{{last_month}}",
                    "status": "DRAFT"
                },
                actions=[
                    {
                        "type": "CREATE_TASK",
                        "title": "Review Month-End Entries",
                        "description": "Review and approve month-end journal entries",
                        "assigned_to": "accounting_manager",
                        "due_date": "+2 days"
                    },
                    {
                        "type": "SEND_EMAIL",
                        "template": "month_end_reminder",
                        "recipients": ["accounting_team@company.com"],
                        "data": {
                            "month": "{{last_month_name}}",
                            "pending_entries": "{{pending_count}}"
                        }
                    }
                ],
                schedule_type="SCHEDULED",
                schedule_datetime=timezone.now().replace(day=1, hour=9, minute=0),
                recurrence_pattern={
                    "frequency": "monthly",
                    "day_of_month": 1
                },
                is_active=True
            )
            workflows_created.append(month_end_rule.id)
            
            return {
                "success": True,
                "workflows_created": workflows_created,
                "message": f"Created {len(workflows_created)} accounting workflows"
            }
            
        except Exception as e:
            self.logger.error(f"Error registering accounting workflows: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== Workflow Action Execution ====================
    
    def execute_finance_action(self, action_config: Dict[str, Any], 
                             trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Execute finance-specific workflow action."""
        try:
            action_type = action_config.get('type')
            
            if action_type == 'CREATE_JOURNAL_ENTRY':
                return self._create_automated_journal_entry(action_config, trigger_data)
            elif action_type == 'APPROVE_INVOICE':
                return self._approve_invoice(action_config, trigger_data)
            elif action_type == 'PROCESS_PAYMENT':
                return self._process_automated_payment(action_config, trigger_data)
            elif action_type == 'CALCULATE_FINANCIAL_METRICS':
                return self._calculate_financial_metrics(action_config, trigger_data)
            elif action_type == 'RECONCILE_ACCOUNTS':
                return self._reconcile_accounts(action_config, trigger_data)
            elif action_type == 'GENERATE_FINANCIAL_REPORT':
                return self._generate_financial_report(action_config, trigger_data)
            else:
                return WorkflowActionResult(
                    success=False,
                    message=f"Unknown finance action type: {action_type}"
                )
                
        except Exception as e:
            self.logger.error(f"Error executing finance action: {e}")
            return WorkflowActionResult(
                success=False,
                message=str(e),
                errors=[str(e)]
            )
    
    def _create_automated_journal_entry(self, action_config: Dict[str, Any], 
                                      trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Create automated journal entry based on trigger."""
        try:
            with transaction.atomic():
                # Extract entry configuration
                entry_config = action_config.get('journal_entry', {})
                
                # Create journal entry
                journal_entry = JournalEntry.objects.create(
                    tenant=self.tenant,
                    description=entry_config.get('description', f'Automated entry for {trigger_data.object_type}'),
                    reference=f"AUTO-{trigger_data.object_type}-{trigger_data.object_id}",
                    entry_date=timezone.now().date(),
                    created_by=trigger_data.triggered_by,
                    status='DRAFT'
                )
                
                # Add journal lines
                lines_config = entry_config.get('lines', [])
                total_debits = Decimal('0')
                total_credits = Decimal('0')
                
                for line_config in lines_config:
                    account_code = line_config.get('account_code')
                    account = Account.objects.get(
                        tenant=self.tenant,
                        code=account_code
                    )
                    
                    debit_amount = Decimal(str(line_config.get('debit', 0)))
                    credit_amount = Decimal(str(line_config.get('credit', 0)))
                    
                    from apps.finance.models.journal import JournalLine
                    JournalLine.objects.create(
                        journal_entry=journal_entry,
                        account=account,
                        description=line_config.get('description', ''),
                        debit=debit_amount,
                        credit=credit_amount
                    )
                    
                    total_debits += debit_amount
                    total_credits += credit_amount
                
                # Validate balanced entry
                if total_debits != total_credits:
                    raise ValidationError(f"Journal entry is not balanced: Debits {total_debits}, Credits {total_credits}")
                
                # Auto-approve if configured
                if action_config.get('auto_approve', False):
                    journal_entry.status = 'APPROVED'
                    journal_entry.approved_by = trigger_data.triggered_by
                    journal_entry.approved_at = timezone.now()
                    journal_entry.save()
                
                return WorkflowActionResult(
                    success=True,
                    message=f"Created journal entry {journal_entry.reference}",
                    data={
                        'journal_entry_id': journal_entry.id,
                        'reference': journal_entry.reference,
                        'amount': float(total_debits)
                    }
                )
                
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to create journal entry: {e}",
                errors=[str(e)]
            )
    
    def _approve_invoice(self, action_config: Dict[str, Any], 
                        trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Approve invoice automatically."""
        try:
            invoice = Invoice.objects.get(
                tenant=self.tenant,
                id=trigger_data.object_id
            )
            
            # Check approval conditions
            approval_conditions = action_config.get('conditions', {})
            
            if approval_conditions.get('max_amount'):
                if invoice.total_amount > Decimal(str(approval_conditions['max_amount'])):
                    return WorkflowActionResult(
                        success=False,
                        message="Invoice amount exceeds auto-approval limit"
                    )
            
            # Approve invoice
            invoice.status = 'APPROVED'
            invoice.approved_by = trigger_data.triggered_by
            invoice.approved_at = timezone.now()
            invoice.save()
            
            return WorkflowActionResult(
                success=True,
                message=f"Invoice {invoice.number} approved automatically",
                data={
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.number,
                    'approved_at': invoice.approved_at.isoformat()
                }
            )
            
        except Invoice.DoesNotExist:
            return WorkflowActionResult(
                success=False,
                message="Invoice not found"
            )
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to approve invoice: {e}",
                errors=[str(e)]
            )
    
    def _process_automated_payment(self, action_config: Dict[str, Any], 
                                 trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Process automated payment."""
        try:
            payment_config = action_config.get('payment', {})
            
            # Get invoice if this is invoice-triggered
            if trigger_data.object_type == 'Invoice':
                invoice = Invoice.objects.get(
                    tenant=self.tenant,
                    id=trigger_data.object_id
                )
                
                # Create payment
                payment = Payment.objects.create(
                    tenant=self.tenant,
                    amount=invoice.total_amount,
                    payment_date=timezone.now().date(),
                    payment_method=payment_config.get('method', 'BANK_TRANSFER'),
                    reference=f"AUTO-PAY-{invoice.number}",
                    status='PROCESSING',
                    created_by=trigger_data.triggered_by
                )
                
                # Create payment allocation
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    amount=invoice.total_amount
                )
                
                return WorkflowActionResult(
                    success=True,
                    message=f"Created automated payment for invoice {invoice.number}",
                    data={
                        'payment_id': payment.id,
                        'amount': float(payment.amount),
                        'invoice_number': invoice.number
                    }
                )
            
            return WorkflowActionResult(
                success=False,
                message="Automated payment only supported for invoices"
            )
            
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to process automated payment: {e}",
                errors=[str(e)]
            )
    
    def _calculate_financial_metrics(self, action_config: Dict[str, Any], 
                                   trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Calculate and store financial metrics."""
        try:
            metrics = {}
            
            # Calculate various metrics based on configuration
            metric_types = action_config.get('metrics', [])
            
            for metric_type in metric_types:
                if metric_type == 'accounts_receivable':
                    ar_total = Invoice.objects.filter(
                        tenant=self.tenant,
                        status__in=['SENT', 'OVERDUE']
                    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
                    metrics['accounts_receivable'] = float(ar_total)
                
                elif metric_type == 'monthly_revenue':
                    current_month = timezone.now().replace(day=1)
                    revenue = Invoice.objects.filter(
                        tenant=self.tenant,
                        status='PAID',
                        paid_date__gte=current_month
                    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
                    metrics['monthly_revenue'] = float(revenue)
                
                elif metric_type == 'overdue_invoices':
                    overdue_count = Invoice.objects.filter(
                        tenant=self.tenant,
                        status='OVERDUE'
                    ).count()
                    metrics['overdue_invoices'] = overdue_count
            
            # Store metrics (could be saved to a metrics table)
            # For now, return in response
            
            return WorkflowActionResult(
                success=True,
                message="Financial metrics calculated successfully",
                data={'metrics': metrics}
            )
            
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to calculate financial metrics: {e}",
                errors=[str(e)]
            )
    
    def _reconcile_accounts(self, action_config: Dict[str, Any], 
                          trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Perform automated account reconciliation."""
        try:
            # This would integrate with the AI bank reconciliation service
            from apps.finance.services.ai_bank_reconciliation import AIBankReconciliationService
            
            reconciliation_config = action_config.get('reconciliation', {})
            account_id = reconciliation_config.get('account_id')
            
            if not account_id:
                return WorkflowActionResult(
                    success=False,
                    message="Account ID required for reconciliation"
                )
            
            # Run AI reconciliation
            ai_service = AIBankReconciliationService(self.tenant)
            result = ai_service.process_bank_statement(
                account_id=account_id,
                auto_match=True,
                confidence_threshold=0.85
            )
            
            return WorkflowActionResult(
                success=True,
                message=f"Reconciliation completed: {result['matches_found']} matches found",
                data=result
            )
            
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to reconcile accounts: {e}",
                errors=[str(e)]
            )
    
    def _generate_financial_report(self, action_config: Dict[str, Any], 
                                 trigger_data: WorkflowTriggerData) -> WorkflowActionResult:
        """Generate automated financial report."""
        try:
            from apps.finance.services.ai_financial_reporting import AIFinancialReportingService
            
            report_config = action_config.get('report', {})
            report_type = report_config.get('type', 'monthly_summary')
            
            ai_service = AIFinancialReportingService(self.tenant)
            
            if report_type == 'monthly_summary':
                report = ai_service.generate_monthly_financial_summary()
            elif report_type == 'cash_flow':
                report = ai_service.generate_cash_flow_analysis()
            elif report_type == 'profit_loss':
                report = ai_service.generate_profit_loss_analysis()
            else:
                return WorkflowActionResult(
                    success=False,
                    message=f"Unknown report type: {report_type}"
                )
            
            # Email report if configured
            if report_config.get('email_recipients'):
                # Send email with report (implementation depends on email service)
                pass
            
            return WorkflowActionResult(
                success=True,
                message=f"Generated {report_type} report successfully",
                data={'report': report}
            )
            
        except Exception as e:
            return WorkflowActionResult(
                success=False,
                message=f"Failed to generate financial report: {e}",
                errors=[str(e)]
            )
    
    # ==================== Workflow Integration Setup ====================
    
    def setup_complete_finance_workflows(self) -> Dict[str, Any]:
        """Set up complete finance workflow integration."""
        try:
            results = {
                'invoice_workflows': self.register_invoice_workflows(),
                'payment_workflows': self.register_payment_workflows(),
                'accounting_workflows': self.register_accounting_workflows()
            }
            
            total_workflows = sum([
                len(result.get('workflows_created', [])) 
                for result in results.values() 
                if result.get('success')
            ])
            
            return {
                'success': True,
                'total_workflows_created': total_workflows,
                'results': results,
                'message': f"Successfully set up {total_workflows} finance workflows"
            }
            
        except Exception as e:
            self.logger.error(f"Error setting up finance workflows: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get status of finance workflow integration."""
        try:
            from apps.crm.models.workflow import WorkflowRule, WorkflowExecution
            
            # Count workflows by trigger type
            workflows_by_type = {}
            workflow_rules = WorkflowRule.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
            
            for rule in workflow_rules:
                trigger_type = rule.trigger_type
                if trigger_type not in workflows_by_type:
                    workflows_by_type[trigger_type] = 0
                workflows_by_type[trigger_type] += 1
            
            # Get execution statistics
            executions = WorkflowExecution.objects.filter(
                tenant=self.tenant,
                workflow_rule__trigger_object__in=['Invoice', 'Payment', 'JournalEntry']
            )
            
            execution_stats = {
                'total_executions': executions.count(),
                'successful_executions': executions.filter(status='COMPLETED').count(),
                'failed_executions': executions.filter(status='FAILED').count(),
                'pending_executions': executions.filter(status='PENDING').count()
            }
            
            return {
                'success': True,
                'total_workflows': workflow_rules.count(),
                'workflows_by_type': workflows_by_type,
                'execution_stats': execution_stats,
                'integration_status': 'active' if workflow_rules.exists() else 'inactive'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }